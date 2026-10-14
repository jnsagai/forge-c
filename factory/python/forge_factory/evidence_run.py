"""Run a verification command and record task evidence (command, versions, exit code, hashes).

Usage: python -m forge_factory.evidence_run --task T005 -- <command...>

A textual PASS is not evidence. This writes evidence/v0.4/runs/<task>/<stamp>.json plus the
captured log, hashing both, so a task checkbox can reference a reproducible record.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import time

from .common import REPO_ROOT, pretty_json, sha256_bytes, utc_now

EVIDENCE_ROOT = REPO_ROOT / "evidence" / "v0.4" / "runs"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def record(task: str, cmd: list[str], timeout: int = 1800) -> dict:
    if not task.replace("-", "").isalnum():
        raise ValueError("task id must be alphanumeric/dash")
    started = time.monotonic()
    ts = utc_now()
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, timeout=timeout,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        out, code = proc.stdout + b"\n--- stderr ---\n" + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        out, code = (exc.stdout or b"") + b"\nTIMEOUT\n", 124
    duration = round(time.monotonic() - started, 3)
    stamp = ts.replace(":", "").replace("-", "").replace(".", "")[:15]
    out_dir = EVIDENCE_ROOT / task
    out_dir.mkdir(parents=True, exist_ok=True)
    log_name = f"{stamp}.log"
    (out_dir / log_name).write_bytes(out)
    rec = {
        "schema": "forge-c/task-evidence/0.4",
        "task": task,
        "status": "PASS" if code == 0 else "FAIL",
        "command": cmd,
        "exit_code": code,
        "ts_utc": ts,
        "duration_s": duration,
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "host": {"node": platform.node(), "system": platform.platform(), "python": sys.version.split()[0]},
        "log": f"evidence/v0.4/runs/{task}/{log_name}",
        "log_sha256": sha256_bytes(out),
    }
    (out_dir / f"{stamp}.json").write_text(pretty_json(rec), encoding="utf-8")
    (out_dir / "latest.json").write_text(pretty_json(rec), encoding="utf-8")
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        ap.error("missing command")
    rec = record(a.task, cmd, a.timeout)
    print(f"{rec['task']} {rec['status']} — {rec['log']} — exit:{rec['exit_code']}")
    return 0 if rec["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
