"""Feature 017 T009: pinned artefact downloads (resume, verification, lock)."""
import hashlib
import json

import httpx
import pytest
from forge_factory.modelservice import artefacts as A

BLOB = b"0123456789" * 1000
SHA = hashlib.sha256(BLOB).hexdigest()


def _client(blob=BLOB, ranges=True, calls=None):
    def handler(req):
        if calls is not None:
            calls.append(dict(req.headers))
        rng = req.headers.get("range")
        if rng and ranges:
            start = int(rng.split("=")[1].split("-")[0])
            return httpx.Response(206, content=blob[start:])
        return httpx.Response(200, content=blob)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_download_verifies_and_resumes(tmp_path):
    dest = tmp_path / "m/model.bin"
    dest.parent.mkdir()
    (tmp_path / "m/model.bin.part").write_bytes(BLOB[:4000])  # an interrupted earlier download
    calls = []
    rec = A.download("http://x/model.bin", dest, sha256=SHA, size=len(BLOB), client=_client(calls=calls))
    assert rec["sha256"] == SHA and dest.read_bytes() == BLOB and not (tmp_path / "m/model.bin.part").exists()
    assert calls[0]["range"] == "bytes=4000-"
    # already present and correct: no request at all
    calls.clear()
    A.download("http://x/model.bin", dest, sha256=SHA, client=_client(calls=calls))
    assert calls == []


def test_wrong_hash_or_size_is_deleted_and_refused(tmp_path):
    dest = tmp_path / "model.bin"
    with pytest.raises(A.ArtefactError, match="SHA256_MISMATCH"):
        A.download("http://x/model.bin", dest, sha256="0" * 64, client=_client())
    assert not dest.exists() and not dest.with_name("model.bin.part").exists()
    with pytest.raises(A.ArtefactError, match="SIZE_MISMATCH"):
        A.download("http://x/model.bin", dest, size=5, client=_client())
    assert not dest.with_name("model.bin.part").exists()


def test_http_error_is_named(tmp_path):
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    with pytest.raises(A.ArtefactError, match="HTTP_404"):
        A.download("http://x/nope", tmp_path / "n", client=c)


def test_hf_snapshot_pins_every_file(tmp_path):
    rev = "c" * 40
    files = {"config.json": b'{"a":1}', "model-00001.safetensors": BLOB}

    def handler(req):
        if req.url.path.startswith("/api/models/"):
            assert req.url.path.endswith(f"/revision/{rev}")
            sib = [{"rfilename": "config.json", "size": 7},
                   {"rfilename": "model-00001.safetensors", "size": len(BLOB), "lfs": {"sha256": SHA, "size": len(BLOB)}}]
            return httpx.Response(200, json={"sha": rev, "siblings": sib})
        name = req.url.path.split(f"/resolve/{rev}/")[1]
        return httpx.Response(200, content=files[name])

    c = httpx.Client(transport=httpx.MockTransport(handler))
    out = A.hf_snapshot("Qwen/X", rev, tmp_path / "snap", client=c, base="http://hub")
    assert [f["path"] for f in out] == ["config.json", "model-00001.safetensors"] and out[1]["sha256"] == SHA
    assert (tmp_path / "snap/config.json").read_bytes() == b'{"a":1}'
    with pytest.raises(A.ArtefactError, match="REVISION_NOT_A_COMMIT"):
        A.hf_snapshot("Qwen/X", "main", tmp_path / "s2", client=c, base="http://hub")


def test_hf_snapshot_refuses_moved_revision_and_unsafe_paths(tmp_path):
    rev = "d" * 40
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"sha": "e" * 40, "siblings": []})))
    with pytest.raises(A.ArtefactError, match="REVISION_MOVED"):
        A.hf_snapshot("Qwen/X", rev, tmp_path, client=c, base="http://hub")
    c = httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"sha": rev, "siblings": [{"rfilename": "../escape"}]})))
    with pytest.raises(A.ArtefactError, match="UNSAFE_PATH"):
        A.hf_snapshot("Qwen/X", rev, tmp_path, client=c, base="http://hub")


def test_lock_merges_sections(tmp_path):
    lock = tmp_path / "recipe.lock.json"
    lock.write_text(json.dumps({"images": {"a": "sha256:" + "1" * 64}, "fabro_version": "0.362.0"}))
    A.update_lock(lock, images={"vllm": "sha256:" + "2" * 64}, model_files={"m": {"files": []}})
    doc = json.loads(lock.read_text())
    assert set(doc["images"]) == {"a", "vllm"} and doc["fabro_version"] == "0.362.0" and "m" in doc["model_files"]
    assert A.main(["image", "--name", "x", "--digest", "sha256:" + "3" * 64, "--lock", str(lock)]) == 0
    with pytest.raises(A.ArtefactError, match="DIGEST_INVALID"):
        A.main(["image", "--name", "x", "--digest", "latest", "--lock", str(lock)])
