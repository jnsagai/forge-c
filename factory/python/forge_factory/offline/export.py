"""DA-T056 / DA-FR-056: export finished local runs for development, as a deterministic, hash-listed zip.

    python -m forge_factory.offline.export --run <workspace> [--run <workspace> ...] --out <bundle.zip>
    python -m forge_factory.offline.export --verify <bundle.zip>

What travels in full (the allowlist, RECORDS): run identity and profile, gate logs, the local inspector's records
(question identities, structured answers, claims and rule decisions), inspection results, the advisory gap register with
its attempt records, owner dispositions, and usage/timing logs. Every other workspace file is listed by hash only, so
development can check it holds the same frozen inputs; prompts are reproducible from those inputs and the revision.
Vendor inputs and document indexes are NEVER_CONTENT. Inside exported JSON, keys that carry prompts or reasoning are
removed and secrets redacted; both are counted per file in the manifest, so nothing disappears silently. Building the
same runs twice gives byte-identical bundles. Nothing here opens a network connection.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

from ..afo.bundle import SECRET
from ..common import REPO_ROOT

SCHEMA = "forge-c/offline-export/1"
CONTRACT = REPO_ROOT / "specs/014-durable-local-autonomy/contracts/offline-export-manifest.schema.json"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
RECORDS = (".forge-run/manifest.json", ".forge-run/model-profile.json", ".forge-run/local-profile.json",
           ".forge-run/binding.json", ".forge-run/durable-binding.json", ".forge-run/preflight.json",
           ".forge-run/package.json", ".forge-run/safety_scope.json", ".forge-run/recovery-plan.json",
           ".forge-run/owner_dispositions.json", ".forge-run/fabro_run_id", ".forge-run/gates/",
           ".forge-run/assurance/gate-log.jsonl", ".forge-run/lrtx/", ".forge-run/advisory/", ".forge-run/defects/",
           ".forge-run/checklists/", ".forge-run/resume/", ".forge-run/acp/", "inspection/")
RECORD_SUFFIXES = (".json", ".jsonl", "fabro_run_id")
NEVER_CONTENT = ("inputs/", ".forge-run/index/", ".forge-run/diagnosis-evidence/", ".forge-run/fabro_server.json",
                 ".forge-run/test-snapshots/", ".forge-run/knowledge/")
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}
STRIP = ("prompt", "prompts", "system_prompt", "raw_prompt", "messages", "raw_response", "response_text", "reasoning",
         "reasoning_content", "thinking", "chain_of_thought", "cot")
SECRET_KEY = re.compile(r"(?i)^(api[_-]?key|.*(secret|password|passwd)|(access|auth|bearer|refresh|fabro)?[_-]?token|"
                        r"authorization)$")


def _under(rel: str, prefixes: tuple[str, ...]) -> bool:
    return any(rel == p or (p.endswith("/") and rel.startswith(p)) for p in prefixes)


def _clean(o, n: list[int]):
    """Drop STRIP keys at any depth and redact secrets in strings; n = [stripped, redactions]."""
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if k.lower() in STRIP:
                n[0] += 1
                continue
            if SECRET_KEY.match(k) and isinstance(v, str) and v:
                n[1] += 1
                out[k] = "[REDACTED]"
                continue
            out[k] = _clean(v, n)
        return out
    if isinstance(o, list):
        return [_clean(v, n) for v in o]
    if isinstance(o, str):
        s, k = SECRET.subn("[REDACTED]", o)
        n[1] += k
        return s
    return o


def _export_bytes(rel: str, data: bytes) -> tuple[bytes, int, int]:
    n = [0, 0]
    text = data.decode("utf-8", errors="replace")
    if rel.endswith(".json"):
        try:
            return (json.dumps(_clean(json.loads(text), n), indent=1, sort_keys=True) + "\n").encode(), n[0], n[1]
        except ValueError:
            pass
    elif rel.endswith(".jsonl"):
        lines = []
        for line in text.splitlines():
            try:
                lines.append(json.dumps(_clean(json.loads(line), n), sort_keys=True))
            except ValueError:
                lines.append(_clean(line, n))
        return ("\n".join(lines) + "\n" if lines else "").encode(), n[0], n[1]
    return _clean(text, n).encode(), n[0], n[1]  # unparsable record: text with secrets redacted


def _walk(ws: Path):
    for p in sorted(ws.rglob("*")):
        rel = p.relative_to(ws).as_posix()
        if set(rel.split("/")) & SKIP_DIRS or p.is_symlink() or not p.is_file():
            continue
        yield rel, p


def _revision() -> tuple[str, bool]:
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "factory", "config"], cwd=REPO_ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return head.stdout.strip(), bool(dirty)
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN", False


def _run(ws: Path) -> tuple[dict, dict[str, bytes]]:
    man = json.loads((ws / ".forge-run/manifest.json").read_text()) if (ws / ".forge-run/manifest.json").is_file() else {}
    prof = json.loads((ws / ".forge-run/model-profile.json").read_text()) \
        if (ws / ".forge-run/model-profile.json").is_file() else {}
    wo = str(man.get("work_order") or ws.parent.name)
    files, blobs = [], {}
    for rel, p in _walk(ws):
        data = p.read_bytes()
        row = {"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        if _under(rel, NEVER_CONTENT):
            row["content"] = "NEVER_CONTENT"
        elif _under(rel, RECORDS) and rel.endswith(RECORD_SUFFIXES):
            out, stripped, red = _export_bytes(rel, data)
            row.update(content="INCLUDED", exported_sha256=hashlib.sha256(out).hexdigest(), stripped_keys=stripped,
                       redactions=red)
            blobs[rel] = out
        else:
            row["content"] = "HASH_ONLY"
        files.append(row)
    ident = hashlib.sha256("".join(f"{f['path']}\0{f['sha256']}\n" for f in files).encode()).hexdigest()[:12]
    key = re.sub(r"[^A-Za-z0-9._-]", "_", wo) + "-" + ident
    local = man.get("local_profile") if isinstance(man.get("local_profile"), dict) else {}
    return {"run_key": key, "workorder": wo, "profile": local.get("id") if isinstance(local.get("id"), str) else None,
            "model": prof.get("default") if isinstance(prof.get("default"), str) else None, "files": files}, blobs


def _check(manifest: dict) -> None:
    from jsonschema import Draft202012Validator

    errs = [e.message[:160] for e in Draft202012Validator(json.loads(CONTRACT.read_text())).iter_errors(manifest)]
    if errs:
        raise ValueError(f"EXPORT_MANIFEST_INVALID: {errs[:3]}")


def build(workspaces: list[Path], out: Path) -> dict:
    runs, blobs = [], {}
    for ws in workspaces:
        r, b = _run(Path(ws))
        if r["run_key"] in {x["run_key"] for x in runs}:
            raise ValueError(f"DUPLICATE_RUN: {r['run_key']}")
        runs.append(r)
        blobs.update({f"runs/{r['run_key']}/{k}": v for k, v in b.items()})
    runs.sort(key=lambda r: r["run_key"])
    rev, dirty = _revision()
    inc = [f for r in runs for f in r["files"] if f["content"] == "INCLUDED"]
    manifest = {"schema": SCHEMA, "factory": {"revision": rev, "dirty": dirty},
                "rules": {"included": list(RECORDS), "never_content": list(NEVER_CONTENT), "stripped_keys": list(STRIP)},
                "runs": runs,
                "totals": {"runs": len(runs), "files": sum(len(r["files"]) for r in runs), "included": len(inc),
                           "stripped_keys": sum(f["stripped_keys"] for f in inc),
                           "redactions": sum(f["redactions"] for f in inc)}}
    _check(manifest)
    mbytes = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode()
    sums = {"MANIFEST.json": hashlib.sha256(mbytes).hexdigest()} | \
        {k: hashlib.sha256(v).hexdigest() for k, v in sorted(blobs.items())}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in [("MANIFEST.json", mbytes),
                           ("SHA256SUMS.txt", "".join(f"{h}  {n}\n" for n, h in sums.items()).encode()),
                           *sorted(blobs.items())]:
            zi = zipfile.ZipInfo(name, FIXED_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o444 << 16
            zf.writestr(zi, data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())
    digest = hashlib.sha256(buf.getvalue()).hexdigest()
    out.with_name(out.name + ".sha256").write_text(f"{digest}  {out.name}\n")
    return {"bundle": str(out), "sha256": digest, **manifest["totals"], "factory": manifest["factory"]}


def verify(bundle: Path) -> list[str]:
    """Issues found in a bundle (empty = intact): every listed hash, the manifest contract and the file inventory."""
    issues = []
    with zipfile.ZipFile(bundle) as zf:
        names = set(zf.namelist())
        sums = {}
        for line in zf.read("SHA256SUMS.txt").decode().splitlines():
            h, _, n = line.partition("  ")
            sums[n] = h
        for n, h in sums.items():
            if n not in names:
                issues.append(f"MISSING:{n}")
            elif hashlib.sha256(zf.read(n)).hexdigest() != h:
                issues.append(f"HASH_MISMATCH:{n}")
        issues += [f"UNLISTED:{n}" for n in sorted(names - set(sums) - {"SHA256SUMS.txt"})]
        if "MANIFEST.json" in names:
            m = json.loads(zf.read("MANIFEST.json"))
            try:
                _check(m)
            except ValueError as e:
                issues.append(str(e))
            for r in m.get("runs", []):
                for f in r.get("files", []):
                    n = f"runs/{r['run_key']}/{f['path']}"
                    if f.get("content") == "INCLUDED" and sums.get(n) != f.get("exported_sha256"):
                        issues.append(f"MANIFEST_MISMATCH:{n}")
                    if f.get("content") != "INCLUDED" and n in names:
                        issues.append(f"CONTENT_NOT_ALLOWED:{n}")
    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--verify", type=Path)
    a = ap.parse_args(argv)
    if a.verify:
        issues = verify(a.verify)
        print(json.dumps({"status": "INTACT" if not issues else "INVALID", "issues": issues[:20]}))
        return 1 if issues else 0
    if not a.run or not a.out:
        ap.error("--run and --out are required to build")
    print(json.dumps(build(a.run, a.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
