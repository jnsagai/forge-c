"""LRTX-T003 (LRTX-FR-004): preserve the running Codex/Claude deployment before any local-profile host change.

    python -m forge_factory.lrtx.hostsnap --backup <dir outside the repo> [--evidence <json>]

Read-only towards the deployment. Records the checkouts the running services execute from (HEAD, branch, dirty
changes saved as a binary patch plus untracked files), the effective non-secret configuration of those processes,
tool/adapter/model identities, and copies every review archive (zip + sidecar) into the backup, verifies each copy
against its sidecar and its internal SHA256SUMS.txt, then restores the reference archive from the backup copy into
a scratch directory and re-checks it. Credentials are never read: login homes are recorded as present/absent only,
environment values whose name looks secret are redacted, Fabro's server.env is not opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from ..common import pretty_json, sha256_file, utc_now

SECRET_NAME = re.compile(r"TOKEN|KEY|SECRET|PASS|AUTH|CRED|COOKIE|SESSION", re.I)
ENV_KEEP = re.compile(r"^(FORGE_|OLLAMA_|FABRO_|PYTHONPATH$|CODEX_HOME$|CLAUDE_CONFIG_DIR$|PATH$|DOTNET_)")
SERVICE_MARKERS = ("forge_factory", "fabro server start", "ollama serve")
CREDENTIAL_HOMES = ("claude-home", "codex-home")  # factory login homes: presence only, never opened


def _run(*cmd: str, cwd: Path | None = None, env: dict | None = None, timeout: int = 60) -> str:
    try:
        out = subprocess.run(list(cmd), cwd=cwd, env=env, capture_output=True, timeout=timeout)
        return out.stdout.decode(errors="replace").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def redact_env(env: dict[str, str]) -> dict[str, str]:
    return {k: ("<redacted>" if SECRET_NAME.search(k) else v) for k, v in sorted(env.items()) if ENV_KEEP.match(k)}


def services(data_root: str, uid: int | None = None) -> list[dict]:
    """The Forge-C deployment's processes (own user only; other projects' Fabro servers are excluded): pid, cmdline,
    cwd and allow-listed, redacted environment."""
    uid = os.getuid() if uid is None else uid
    out = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid != uid:
                continue
            cmd = (p / "cmdline").read_bytes().split(b"\0")
            text = " ".join(c.decode(errors="replace") for c in cmd if c)
            forge = "forge_factory" in text or data_root in text
            if not forge or not any(m in text for m in SERVICE_MARKERS) or "lrtx.hostsnap" in text \
                    or text.startswith(("/bin/bash", "/bin/sh")):
                continue
            env = dict(kv.decode(errors="replace").split("=", 1) for kv in (p / "environ").read_bytes().split(b"\0")
                       if b"=" in kv)
            out.append({"pid": int(p.name), "cmdline": text, "cwd": os.readlink(p / "cwd"), "env": redact_env(env)})
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda r: r["pid"])


def git_root(path: str | Path) -> Path | None:
    top = _run("git", "rev-parse", "--show-toplevel", cwd=Path(path)) if Path(path).is_dir() else ""
    return Path(top) if top else None


def checkout_roots(procs: list[dict]) -> list[Path]:
    """Git checkouts the services execute code from (cwd and PYTHONPATH entries)."""
    roots: set[Path] = set()
    for p in procs:
        for cand in [p["cwd"], *p["env"].get("PYTHONPATH", "").split(":")]:
            if cand and (r := git_root(cand)) is not None:
                roots.add(r)
    return sorted(roots)


def snapshot_checkout(root: Path, dest: Path) -> dict:
    """HEAD/branch/status, dirty tracked changes as a binary patch and untracked (not ignored) files as a tar.
    Ignored owner inputs (examples/*/inputs) are hashed and copied: they are untracked yet required by work orders."""
    dest.mkdir(parents=True, exist_ok=True)
    head = _run("git", "rev-parse", "HEAD", cwd=root)
    patch = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=root, capture_output=True).stdout
    (dest / "tracked.patch").write_bytes(patch)
    untracked = [x for x in _run("git", "ls-files", "--others", "--exclude-standard", "-z", cwd=root).split("\0") if x]
    with tarfile.open(dest / "untracked.tar", "w") as tf:
        for rel in untracked:
            tf.add(root / rel, arcname=rel, recursive=False)
    owner_inputs = []
    for f in sorted(root.glob("examples/*/inputs/*")):
        if f.is_file() and _run("git", "check-ignore", str(f.relative_to(root)), cwd=root):
            rel = f.relative_to(root)
            (dest / "owner-inputs" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest / "owner-inputs" / rel)
            owner_inputs.append({"path": str(rel), "sha256": sha256_file(f), "bytes": f.stat().st_size})
    return {"path": str(root), "head": head, "branch": _run("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=root),
            "tree": _run("git", "rev-parse", "HEAD^{tree}", cwd=root),
            "status_porcelain": _run("git", "status", "--porcelain", cwd=root).splitlines(),
            "dirty_tracked": bool(patch), "tracked_patch_sha256": hashlib.sha256(patch).hexdigest(),
            "untracked": untracked, "untracked_tar_sha256": sha256_file(dest / "untracked.tar"),
            "ignored_owner_inputs": owner_inputs}


def _get_json(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310 - loopback Ollama URL
            return json.loads(r.read())
    except (OSError, ValueError):
        return None


def ollama_models(url: str) -> dict:
    tags = _get_json(url.rstrip("/") + "/api/tags")
    if tags is None:
        return {"url": url, "status": "UNREACHABLE"}
    return {"url": url, "status": "OK", "version": (_get_json(url.rstrip("/") + "/api/version") or {}).get("version"),
            "models": [{"name": m["name"], "digest": m.get("digest"), "size": m.get("size"),
                        "quantization": (m.get("details") or {}).get("quantization_level"),
                        "parameter_size": (m.get("details") or {}).get("parameter_size"),
                        "family": (m.get("details") or {}).get("family")} for m in tags.get("models") or []]}


def tool_versions(data_root: Path) -> dict:
    tc = data_root / "toolchains"
    fab = os.environ.get("FORGE_FABRO_BIN", str(Path.home() / ".fabro/bin/fabro"))

    def pkg_version(p: Path) -> str | None:
        try:
            return json.loads(p.read_text()).get("version")
        except (OSError, ValueError):
            return None
    venv_py = data_root / "venv/bin/python"
    freeze = _run(str(venv_py), "-I", "-c", "import importlib.metadata as m; print('\\n'.join(sorted("
                  "f'{d.metadata[\"Name\"]}=={d.version}' for d in m.distributions())))") if venv_py.is_file() else ""
    return {
        "fabro": {"path": fab, "version": _run(fab, "--version", env={
            **os.environ, "FABRO_NO_UPGRADE_CHECK": "1", "HOME": os.environ.get("FORGE_FABRO_HOME", str(Path.home()))}),
                  "sha256": sha256_file(Path(fab)) if Path(fab).is_file() else None},
        "ollama": {"path": str(data_root / "ollama-0.34.0/bin/ollama"),
                   "sha256": sha256_file(data_root / "ollama-0.34.0/bin/ollama")
                   if (data_root / "ollama-0.34.0/bin/ollama").is_file() else None},
        "claude_agent_acp": sorted(filter(None, (pkg_version(p) for p in
                                                 tc.glob("claude-agent-acp-*/node_modules/*/claude-agent-acp/package.json")))),
        "codex_acp": sorted(d.name for d in tc.glob("codex-acp-*")),
        "codex": sorted(d.name for d in tc.glob("codex-0.*")),
        "llvm": _run(str(tc / "LLVM-19.1.7-Linux-X64/bin/clang"), "--version").splitlines()[:1],
        "renode": sorted(d.name for d in (tc / "renode").glob("renode_*")),
        "plantuml": sorted(f.name for f in (tc / "plantuml").glob("*.jar")),
        "podman": _run("podman", "--version"), "git": _run("git", "--version"),
        "python_venv": _run(str(venv_py), "--version") if venv_py.is_file() else None,
        "pip_freeze_sha256": hashlib.sha256(freeze.encode()).hexdigest() if freeze else None,
        "pip_freeze": freeze.splitlines()}


def config_files(data_root: Path) -> list[dict]:
    """Non-secret configuration copied by hash (no file holding credentials is opened)."""
    cands = [data_root / "fabro/settings.toml", data_root / "fabro-cloud/settings.toml",
             Path.home() / ".config/systemd/user/forge-supervisor.service"]
    return [{"path": str(p), "sha256": sha256_file(p), "bytes": p.stat().st_size} for p in cands if p.is_file()]


def credential_homes(data_root: Path) -> list[dict]:
    return [{"path": str(data_root / h), "present": (data_root / h).is_dir(), "contents_read": False}
            for h in CREDENTIAL_HOMES]


def sqlite_backup(src: Path, dst: Path) -> dict:
    """Consistent copy of a live SQLite store through the backup API (the service keeps running)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as s, sqlite3.connect(dst) as d:
        s.backup(d)
    ok = sqlite3.connect(dst).execute("PRAGMA integrity_check").fetchone()[0]
    return {"path": str(src), "copy": str(dst), "copy_sha256": sha256_file(dst), "integrity_check": ok}


def verify_zip(z: Path) -> dict:
    """Sidecar sha256 and every member listed in the archive's SHA256SUMS.txt."""
    side = z.with_name(z.name + ".sha256")
    want = side.read_text().split()[0] if side.is_file() else None
    got = sha256_file(z)
    bad, n = [], 0
    with zipfile.ZipFile(z) as zf:
        names = set(zf.namelist())
        if "SHA256SUMS.txt" in names:
            for line in zf.read("SHA256SUMS.txt").decode().splitlines():
                if not line.strip():
                    continue
                h, rel = line.split(maxsplit=1)
                rel = rel.lstrip("*")
                n += 1
                if rel not in names or hashlib.sha256(zf.read(rel)).hexdigest() != h:
                    bad.append(rel)
    return {"archive": z.name, "sha256": got, "sidecar_match": want == got if want else None,
            "members_checked": n, "member_mismatches": bad}


def preserve_archives(archive_dir: Path, dest: Path) -> dict:
    """Copy every review archive (zip + sidecar) read-only into `dest` and verify the copies."""
    rows = []
    for z in sorted(archive_dir.glob("*/*.zip")):
        tgt = dest / z.parent.name
        tgt.mkdir(parents=True, exist_ok=True)
        for f in (z, z.with_name(z.name + ".sha256")):
            if f.is_file():
                shutil.copy2(f, tgt / f.name)
                (tgt / f.name).chmod(0o444)
        src_sha = sha256_file(z)
        r = verify_zip(tgt / z.name)
        rows.append({"work_order": z.parent.name, **r, "original_sha256": src_sha,
                     "copy_equals_original": r["sha256"] == src_sha})
    ok = all(r["copy_equals_original"] and r["sidecar_match"] is not False and not r["member_mismatches"] for r in rows)
    return {"source": str(archive_dir), "copied_to": str(dest), "archives": len(rows), "all_verified": ok,
            "not_copied": "archives/staging (unpacked build directories the zips were made from)", "rows": rows}


def restore_check(zip_copy: Path) -> dict:
    """Read-only restore: extract the preserved copy into scratch space and re-hash every member."""
    with tempfile.TemporaryDirectory(prefix="lrtx-restore-") as td:
        with zipfile.ZipFile(zip_copy) as zf:
            zf.extractall(td)  # noqa: S202 - the factory's own review archive, hash-checked against its sidecar
        sums = (Path(td) / "SHA256SUMS.txt").read_text().splitlines()
        bad = [rel.lstrip("*") for h, rel in (ln.split(maxsplit=1) for ln in sums if ln.strip())
               if sha256_file(Path(td) / rel.lstrip("*")) != h]
        pkg = json.loads((Path(td) / "manifest.json").read_text()) if (Path(td) / "manifest.json").is_file() else {}
    return {"archive": str(zip_copy), "files_rehashed": len(sums), "mismatches": bad,
            "package_status": pkg.get("status"), "gap_count": pkg.get("gap_count"), "status": "PASS" if not bad else "FAIL"}


def snapshot(backup: Path, reference_wo: str = "WO-0009B-STM32N6-IWDG-HAL-rc4") -> dict:
    data_root = Path(os.environ.get("FORGE_DATA_ROOT", ""))
    archive_dir = Path(os.environ.get("FORGE_ARCHIVE_DIR", data_root / "archives"))
    state = Path(os.environ.get("FORGE_STATE_DIR", data_root / "state"))
    for root in (data_root, archive_dir, state):
        if not root.is_dir():
            raise FileNotFoundError(root)
    if backup.resolve().is_relative_to(archive_dir.resolve()) or git_root(backup.parent) is not None:
        raise ValueError(f"BACKUP_INSIDE_DEPLOYMENT_OR_REPO:{backup}")
    backup.mkdir(parents=True, exist_ok=False)
    backup.chmod(0o700)
    procs = services(str(data_root))
    roots = checkout_roots(procs)
    checkouts = [snapshot_checkout(r, backup / "checkouts" / r.name) for r in roots]
    stores = [sqlite_backup(p, backup / "state" / p.relative_to(state)) for p in sorted(state.glob("*/*.sqlite3"))]
    arch = preserve_archives(archive_dir, backup / "archives")
    ref = backup / "archives" / reference_wo / f"forge-c-{reference_wo}-review.zip"
    rec = {"schema": "forge-c/lrtx-host-snapshot/1", "recorded_at": utc_now(), "host": os.uname().nodename,
           "purpose": "LRTX-T003: preserve the running Codex/Claude deployment before local-profile host changes",
           "backup_dir": str(backup), "data_root": str(data_root),
           "services": [{k: p[k] for k in ("pid", "cmdline", "cwd", "env")} for p in procs],
           "checkouts": checkouts, "tools": tool_versions(data_root),
           "models": ollama_models(os.environ.get("FORGE_OLLAMA_URL", "http://127.0.0.1:11435")),
           "config_files": config_files(data_root), "credential_homes": credential_homes(data_root),
           "state_stores": stores, "archives": {k: v for k, v in arch.items() if k != "rows"},
           "archive_rows": arch["rows"],
           "restore_check": restore_check(ref) if ref.is_file() else {"status": "NOT_RUN", "reason": f"{ref} missing"},
           "not_preserved": ["Fabro run storage (live server databases; run results are in the archives and state "
                             "stores)", "model weights (23 GB, identified by digest; re-pullable)",
                             "credentials (login homes recorded as present only)"]}
    (backup / "snapshot.json").write_text(pretty_json(rec))
    (backup / "snapshot.json").chmod(0o400)
    return rec


def summary(rec: dict) -> dict:
    """Repository-safe summary (no environment values beyond names/paths, no file contents)."""
    return {"schema": rec["schema"], "recorded_at": rec["recorded_at"], "backup_dir": rec["backup_dir"],
            "snapshot_sha256": sha256_file(Path(rec["backup_dir"]) / "snapshot.json"),
            "services": [{"pid": p["pid"], "cmd": p["cmdline"][:160], "cwd": p["cwd"]} for p in rec["services"]],
            "checkouts": [{k: c[k] for k in ("path", "head", "branch", "tree", "dirty_tracked", "tracked_patch_sha256",
                                             "untracked", "status_porcelain")}
                          | {"ignored_owner_inputs": len(c["ignored_owner_inputs"])} for c in rec["checkouts"]],
            "tools": {k: v for k, v in rec["tools"].items() if k != "pip_freeze"},
            "models": rec["models"], "config_files": rec["config_files"], "credential_homes": rec["credential_homes"],
            "state_stores": rec["state_stores"], "archives": rec["archives"],
            "archive_failures": [r for r in rec["archive_rows"] if not r["copy_equals_original"]
                                 or r["sidecar_match"] is False or r["member_mismatches"]],
            "restore_check": rec["restore_check"], "not_preserved": rec["not_preserved"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backup", type=Path, required=True)
    ap.add_argument("--evidence", type=Path, default=None, help="write the repository-safe summary here")
    a = ap.parse_args(argv)
    rec = snapshot(a.backup)
    s = summary(rec)
    if a.evidence:
        a.evidence.parent.mkdir(parents=True, exist_ok=True)
        a.evidence.write_text(pretty_json(s))
    ok = rec["archives"]["all_verified"] and rec["restore_check"].get("status") == "PASS" and all(
        x["integrity_check"] == "ok" for x in rec["state_stores"])
    print(json.dumps({"status": "PASS" if ok else "FAIL", "archives": rec["archives"]["archives"],
                      "checkouts": [(c["path"], c["head"][:10], c["dirty_tracked"], len(c["untracked"]))
                                    for c in rec["checkouts"]], "restore": rec["restore_check"].get("status")}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
