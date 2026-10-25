"""Feature 015 (F015-T002, FR-004..FR-006): the STM32N6 ST-code benchmark queue on the production line.

One work order at a time, in queue order, launched like every production run (Codex authors, Claude inspectors; the
caller provides the cloud-bench environment, so the runs appear on the Fabro monitor under its source). For each item:
- skipped when its example does not exist yet (peripheral not onboarded);
- skipped when it already has a recorded outcome or a launched attempt without one (UNFINISHED_ATTEMPT: the run may
  still be live); a retry is an explicit `--retry ID` and gets a new work order id;
- otherwise launched with `--detach`, then the runner waits for the release package and records the outcome from the
  recorded evidence only: package status, gap count, the phases whose inspection passed, duration.
Nothing is marked READY by the runner; the gates, inspectors and release manager decide.

    python -m forge_factory.benchmark.queue run [--queue FILE] [--only ID] [--retry ID] [--poll 120]
    python -m forge_factory.benchmark.queue status [--queue FILE]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from ..afo.runtime import PROFILES
from ..common import REPO_ROOT, load_yaml, state_dir, utc_now

QUEUE = REPO_ROOT / "config/factory/benchmark/st-driver-queue.yaml"
_P = PROFILES["codex-claude"]  # one definition of the production line, shared with AFO (Codex authors, Claude
# inspectors; the run model is nominal: DeepSeek is suspended and serves no agent node)
LINE = ["--acp-authors", _P["acp_authors"], "--acp-inspectors", _P["acp_inspectors"], "--model", _P["model"],
        "--provider", _P["provider"]]
PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")


def load(path: Path = QUEUE) -> dict:
    q = load_yaml(path)
    ids = [i["id"] for i in q["items"]]
    if len(ids) != len(set(ids)):
        raise ValueError("QUEUE_DUPLICATE_ITEM_ID")
    return q


def state_path(q: dict) -> Path:
    return state_dir() / "benchmark" / q["id"] / "state.json"


def read_state(q: dict) -> dict:
    p = state_path(q)
    return json.loads(p.read_text()) if p.is_file() else {"queue": q["id"], "items": {}}


def write_state(q: dict, st: dict) -> None:
    p = state_path(q)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1, sort_keys=True) + "\n")
    tmp.replace(p)


def work_order_id(q: dict, item: dict, attempt: int) -> str:
    return f"{q['work_order_prefix']}-{item['id'].upper()}-r{attempt}"


def outcome(ws: Path) -> dict | None:
    """The recorded outcome of a finished work order (None while its package does not exist)."""
    pkg_p = ws / ".forge-run/package.json"
    if not pkg_p.is_file():
        return None
    pkg = json.loads(pkg_p.read_text())
    log_p = ws / ".forge-run/gates/gate-log.jsonl"
    rows = [json.loads(x) for x in log_p.read_text().splitlines() if x.strip()] if log_p.is_file() else []
    passed = [p for p in PHASES if any(r.get("phase") == p and r.get("step") == "inspect" and
                                       (r.get("gate") or {}).get("decision") == "PASS" for r in rows)]
    blocked = next((r.get("phase") for r in rows if r.get("step") == "route" and
                    (r.get("gate") or {}).get("decision") == "BLOCKED"), None)
    return {"package_status": pkg.get("package_status"), "gap_count": pkg.get("gap_count"),
            "archive_sha256": pkg.get("archive_sha256"), "finalized_at": pkg.get("finalized_at"),
            "phases_passed": passed, "blocked_at": blocked}


def launch(example: Path, wo: str) -> dict:
    cmd = [sys.executable, "-m", "forge_factory.workorder", "--example", str(example), "--wo", wo, *LINE, "--detach"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT / "factory/python", check=False)
    last = (res.stdout.strip().splitlines() or [""])[-1]
    try:
        rec = json.loads(last)
    except ValueError:
        rec = {}
    if res.returncode != 0 or not rec.get("fabro_run_id"):
        raise RuntimeError(f"LAUNCH_FAILED:{wo}:{res.returncode}:{(res.stderr or res.stdout).strip()[-400:]}")
    return rec


def _elapsed_s(start: str, end: str | None) -> float | None:
    if not end:
        return None
    f = "%Y-%m-%dT%H:%M:%S"
    a = datetime.strptime(start[:19], f).replace(tzinfo=UTC)
    b = datetime.strptime(end[:19], f).replace(tzinfo=UTC)
    return (b - a).total_seconds()


def run(q: dict, only: str | None = None, retry: str | None = None, poll_s: float = 120.0, launcher=launch,
        sleep=time.sleep) -> dict:
    st = read_state(q)
    for item in q["items"]:
        if only and item["id"] != only:
            continue
        rec = st["items"].setdefault(item["id"], {"attempts": []})
        example = REPO_ROOT / item["example"]
        if not (example / "workorder.json").is_file():
            rec["status"] = "SKIPPED_NOT_ONBOARDED"
            write_state(q, st)
            continue
        done = [a for a in rec["attempts"] if a.get("outcome")]
        if done and retry != item["id"]:
            continue
        open_ = [a for a in rec["attempts"] if not a.get("outcome") and not a.get("launch_error")]
        if open_ and retry != item["id"]:  # a launched attempt without outcome (runner stopped, run maybe live):
            rec["status"] = "UNFINISHED_ATTEMPT"  # reported, never launched again; a retry is explicit (--retry)
            write_state(q, st)
            continue
        wo = work_order_id(q, item, len(rec["attempts"]) + 1)
        att = {"work_order": wo, "started_at": utc_now()}
        rec["attempts"].append(att)
        rec["status"] = "RUNNING"
        write_state(q, st)
        try:
            lr = launcher(example, wo)
        except RuntimeError as exc:
            att["launch_error"] = str(exc)[:500]
            rec["status"] = "LAUNCH_FAILED"
            write_state(q, st)
            continue
        att.update({"fabro_run_id": lr["fabro_run_id"], "workspace": lr["workspace"]})
        write_state(q, st)
        ws = Path(lr["workspace"])
        while (out := outcome(ws)) is None:
            sleep(poll_s)
        att["outcome"] = out
        att["duration_s"] = _elapsed_s(att["started_at"], out.get("finalized_at"))
        rec["status"] = out["package_status"] or "UNKNOWN"
        write_state(q, st)
    return st


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "status"])
    ap.add_argument("--queue", type=Path, default=QUEUE)
    ap.add_argument("--only", default=None)
    ap.add_argument("--retry", default=None, help="launch this item again under a new work order id")
    ap.add_argument("--poll", type=float, default=120.0)
    a = ap.parse_args(argv)
    q = load(a.queue)
    st = run(q, a.only, a.retry, a.poll) if a.cmd == "run" else read_state(q)
    print(json.dumps({k: {"status": v.get("status"), "attempts": [x["work_order"] for x in v.get("attempts", [])]}
                      for k, v in st["items"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
