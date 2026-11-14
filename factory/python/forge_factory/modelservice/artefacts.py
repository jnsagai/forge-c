"""Pinned artefacts for the deployment recipe (feature 017, T009/T010, FR-017).

Downloads resume from a `.part` file, are verified against a pinned sha256 (and size when known), and are deleted
on a mismatch, so a wrong file is never left where the recipe would use it. Model repositories are fetched at an
exact revision and every file is recorded with its sha256 in `recipe.lock.json`. Nothing here touches the GPU.

CLI:
  python -m forge_factory.modelservice.artefacts hf   --repo R --revision SHA --dest DIR [--lock L --model NAME]
  python -m forge_factory.modelservice.artefacts url  --url U --dest FILE --sha256 H
  python -m forge_factory.modelservice.artefacts file --path P [--lock L --model NAME]
  python -m forge_factory.modelservice.artefacts image --name N --digest sha256:... --lock L
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx

CHUNK = 8 << 20


class ArtefactError(RuntimeError):
    """Machine reason in the message: SHA256_MISMATCH:<file>, SIZE_MISMATCH:<file>, HTTP_<code>:<url>, ..."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def record_file(path: Path, root: Path | None = None) -> dict:
    p = Path(path)
    return {"path": (p.relative_to(root) if root else p).as_posix(), "sha256": sha256_file(p), "bytes": p.stat().st_size}


def download(url: str, dest: Path, *, sha256: str | None = None, size: int | None = None,
             client: httpx.Client | None = None, headers: dict | None = None) -> dict:
    """Fetch `url` to `dest` (resuming a previous `.part`), verify, and return its record."""
    dest = Path(dest)
    if dest.is_file() and (sha256 is None or sha256_file(dest) == sha256) and (size is None or dest.stat().st_size == size):
        return record_file(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    own = client is None
    client = client or httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60.0, read=300.0))
    try:
        have = part.stat().st_size if part.is_file() else 0
        h = dict(headers or {})
        if have:
            h["Range"] = f"bytes={have}-"
        with client.stream("GET", url, headers=h) as r:
            if r.status_code == 416 and have:  # already complete
                pass
            elif r.status_code not in (200, 206):
                raise ArtefactError(f"HTTP_{r.status_code}:{url}")
            else:
                mode = "ab" if (have and r.status_code == 206) else "wb"
                with open(part, mode) as f:
                    for chunk in r.iter_bytes(CHUNK):
                        f.write(chunk)
    finally:
        if own:
            client.close()
    if size is not None and part.stat().st_size != size:
        got = part.stat().st_size
        part.unlink()
        raise ArtefactError(f"SIZE_MISMATCH:{dest.name}:{got}!={size}")
    got = sha256_file(part)
    if sha256 is not None and got != sha256:
        part.unlink()
        raise ArtefactError(f"SHA256_MISMATCH:{dest.name}")
    os.replace(part, dest)
    return {"path": dest.as_posix(), "sha256": got, "bytes": dest.stat().st_size}


def hf_snapshot(repo: str, revision: str, dest: Path, *, client: httpx.Client | None = None,
                base: str = "https://huggingface.co") -> list[dict]:
    """Every file of `repo` at the exact commit `revision`, verified against the hub's LFS sha256 where it has one.
    Returns [{path, sha256, bytes}] relative to `dest`, sorted by path."""
    if len(revision) != 40:
        raise ArtefactError("REVISION_NOT_A_COMMIT")
    own = client is None
    client = client or httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60.0, read=300.0))
    try:
        r = client.get(f"{base}/api/models/{repo}/revision/{revision}", params={"blobs": "true"})
        if r.status_code != 200:
            raise ArtefactError(f"HTTP_{r.status_code}:{repo}@{revision}")
        meta = r.json()
        if meta.get("sha") != revision:
            raise ArtefactError("REVISION_MOVED")
        out = []
        for s in sorted(meta.get("siblings") or [], key=lambda s: s["rfilename"]):
            name = s["rfilename"]
            if name.startswith("/") or ".." in Path(name).parts:
                raise ArtefactError(f"UNSAFE_PATH:{name}")
            lfs = s.get("lfs") or {}
            rec = download(f"{base}/{repo}/resolve/{revision}/{name}", Path(dest) / name,
                           sha256=lfs.get("sha256"), size=lfs.get("size") or s.get("size"), client=client)
            out.append({"path": name, "sha256": rec["sha256"], "bytes": rec["bytes"]})
        return out
    finally:
        if own:
            client.close()


def update_lock(lock: Path, **sections) -> dict:
    """Merge sections into recipe.lock.json: dict sections merge by key, list sections replace, scalars set."""
    lock = Path(lock)
    doc = json.loads(lock.read_text()) if lock.is_file() else {}
    for k, v in sections.items():
        if isinstance(v, dict) and isinstance(doc.get(k), dict):
            doc[k] = {**doc[k], **v}
        else:
            doc[k] = v
    tmp = lock.with_name(lock.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, lock)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="artefacts")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("hf")
    a.add_argument("--repo", required=True)
    a.add_argument("--revision", required=True)
    a.add_argument("--dest", required=True, type=Path)
    a.add_argument("--lock", type=Path)
    a.add_argument("--model")
    b = sub.add_parser("url")
    b.add_argument("--url", required=True)
    b.add_argument("--dest", required=True, type=Path)
    b.add_argument("--sha256", required=True)
    c = sub.add_parser("file")
    c.add_argument("--path", required=True, type=Path)
    c.add_argument("--lock", type=Path)
    c.add_argument("--model")
    d = sub.add_parser("image")
    d.add_argument("--name", required=True)
    d.add_argument("--digest", required=True)
    d.add_argument("--lock", required=True, type=Path)
    x = ap.parse_args(argv)
    if x.cmd == "hf":
        files = hf_snapshot(x.repo, x.revision, x.dest)
        if x.lock and x.model:
            update_lock(x.lock, model_files={x.model: {"source": f"hf:{x.repo}@{x.revision}", "root": str(x.dest),
                                                       "files": files}})
        print(json.dumps({"files": len(files), "bytes": sum(f["bytes"] for f in files)}))
    elif x.cmd == "url":
        print(json.dumps(download(x.url, x.dest, sha256=x.sha256)))
    elif x.cmd == "file":
        rec = record_file(x.path)
        if x.lock and x.model:
            update_lock(x.lock, model_files={x.model: {"source": "local", "root": str(x.path.parent),
                                                       "files": [{**rec, "path": x.path.name}]}})
        print(json.dumps(rec))
    elif x.cmd == "image":
        if not x.digest.startswith("sha256:") or len(x.digest) != 71:
            raise ArtefactError("DIGEST_INVALID")
        update_lock(x.lock, images={x.name: x.digest})
        print(json.dumps({x.name: x.digest}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
