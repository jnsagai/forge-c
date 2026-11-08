"""Feature 017 T035: the catalog is the owner lane's own models with today's arguments, never hand-typed
(owner 2026-11-08: "we don't work with qwen 3.6 here")."""
import json

import pytest
import yaml
from forge_factory.modelservice import catalog_gen as G
from model_tier import catalog as C

Q38, ORN = "qwen3.8:27b-q8_0", "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"
ARGS = {
    Q38: ["--model", "/srv/blobs/sha256-" + "2" * 64, "--alias", Q38, "--host", "127.0.0.1", "--port", "11457", "--no-webui",
          "--offline", "-c", "65536", "-np", "1", "--jinja", "--reasoning", "on", "--cache-type-k", "q8_0", "--cache-type-v",
          "q8_0", "--flash-attn", "on", "-b", "1024", "-ub", "512", "--spec-type", "draft-mtp", "--spec-draft-n-max", "3",
          "--reasoning-effort", "medium", "--reasoning-format", "deepseek", "--gpu-layers", "all"],
    ORN: ["--model", "/srv/blobs/sha256-" + "d" * 64, "--alias", ORN, "--host", "127.0.0.1", "--port", "11457", "--no-webui",
          "--offline", "-c", "262144", "-np", "1", "--jinja", "--reasoning", "on", "--cache-type-k", "f16", "--cache-type-v",
          "f16", "--flash-attn", "on", "-b", "2048", "-ub", "2048", "--spec-type", "none", "--gpu-layers", "all", "--fit", "off"],
}
PROF = {"runtime": {"llama_server": {"model": Q38, "vram_required_mib": 46000},
                    "llama_server_alternates": {ORN: {"vram_required_mib": 44000}}}}


def spec(root, prof, ports, env, model=None):
    m = model or Q38
    args = list(ARGS[m])
    args[args.index("--port") + 1] = str(ports["llama"])
    return ["/srv/llama-server", *args], {"LD_LIBRARY_PATH": "/srv/lib", "OTHER": "x"}, "http://h/health", [m]


def _inputs(tmp_path):
    (tmp_path / "lock.json").write_text(json.dumps({"images": {}, "model_files": {}}))
    params = {"site": "omniverse2", "parameters": {k: {"value": v, "description": k} for k, v in {
        "gpu_vram_mib": 49140, "ram_budget_gib": 80, "ram_reserve_gib": 24}.items()}, "not_proven_here": []}
    (tmp_path / "params.yaml").write_text(yaml.safe_dump(params))
    return tmp_path / "lock.json", tmp_path / "params.yaml"


def test_catalog_is_the_lane_models_with_todays_arguments(tmp_path):
    lock, params = _inputs(tmp_path)
    doc = G.generate(prof=PROF, root=tmp_path, lock_path=lock, params_path=params, out=tmp_path / "catalog.yaml", spec=spec)
    assert [m["model"] for m in doc["models"]] == [Q38, ORN]  # exactly the two models used here; no vLLM, no Qwen3.6
    for i, m in enumerate(doc["models"]):
        expect = list(ARGS[m["model"]])
        expect[expect.index("--model") + 1] = "{model_path}"
        expect[expect.index("--port") + 1] = str(G.BASE_PORT + i)
        assert m["process"]["args"] == expect and m["process"]["binary"] == "/srv/llama-server"
        assert m["engine"] == "llama.cpp" and m["warm_strategy"] == "page_cache" and m["process"]["env"] == {"LD_LIBRARY_PATH": "/srv/lib"}
    q, o = doc["models"]
    assert q["full_capacity"]["mtp_draft"] == 3 and q["full_capacity"]["context_per_sequence"] == 65536 and q["vram_mib"] == 46000
    assert o["full_capacity"]["context_per_sequence"] == 262144 and o["full_capacity"]["kv_cache_type"] == "f16"
    cat = C.load(tmp_path / "catalog.yaml", lock)
    assert set(cat.models) == {Q38, ORN} and set(json.loads(lock.read_text())["identities"]) == {Q38, ORN}


def test_lock_must_agree_with_the_profile(tmp_path):
    lock, params = _inputs(tmp_path)
    lock.write_text(json.dumps({"model_files": {ORN: {"files": [{"path": "x", "sha256": "e" * 64, "bytes": 1}]}}}))
    with pytest.raises(RuntimeError, match="LOCK_DISAGREES_WITH_PROFILE"):
        G.generate(prof=PROF, root=tmp_path, lock_path=lock, params_path=params, out=tmp_path / "c.yaml", spec=spec)
    assert not (tmp_path / "c.yaml").exists()


def test_profile_without_llama_server_models_is_refused(tmp_path):
    lock, params = _inputs(tmp_path)
    with pytest.raises(RuntimeError, match="PROFILE_HAS_NO_LLAMA_SERVER_MODELS"):
        G.generate(prof={"runtime": {}}, root=tmp_path, lock_path=lock, params_path=params, out=tmp_path / "c.yaml", spec=spec)
