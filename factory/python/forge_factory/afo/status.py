"""AFO-T005/T072 (AFO-FR-006/071, AT-066) - FR -> task -> acceptance -> evidence matrix for Feature 005.

Task status comes ONLY from `evidence/v0.4/runs/AFO-T*/latest.json` (exit code and log hash checked) and from the
blocker register `evidence/afo/blockers.json` (BLOCKED / PARTIAL / DEFERRED with a reason), never from the
`tasks.md` boxes (scripts/mark_task.py checks a box only with PASS evidence; the spec validator rejects any other
check) or the requirements' NOT_IMPLEMENTED design status. A requirement is COVERED only when every task it plans
is PASS.

  python -m forge_factory.afo.status      -> docs/afo/AFO-STATUS.md + evidence/afo/status.json
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys

from ..common import REPO_ROOT, pretty_json, utc_now

SPEC = REPO_ROOT / "specs/005-autonomous-factory-operations"
RUNS = REPO_ROOT / "evidence/v0.4/runs"
BLOCKERS = REPO_ROOT / "evidence/afo/blockers.json"
MD = REPO_ROOT / "docs/afo/AFO-STATUS.md"
JS = REPO_ROOT / "evidence/afo/status.json"


def _csv(name: str) -> list[dict]:
    with (SPEC / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def task_status(tid: str, blockers: dict) -> dict:
    p = RUNS / tid / "latest.json"
    if p.is_file():
        rec = json.loads(p.read_text())
        log = REPO_ROOT / rec.get("log", "")
        ok_log = log.is_file() and hashlib.sha256(log.read_bytes()).hexdigest() == rec.get("log_sha256")
        if rec.get("status") == "PASS" and rec.get("exit_code") == 0 and ok_log:
            b = blockers.get(tid)
            if b and b.get("status") == "PARTIAL":
                return {"status": "PARTIAL", "reason": b["reason"], "evidence": str(p.relative_to(REPO_ROOT))}
            return {"status": "PASS", "evidence": str(p.relative_to(REPO_ROOT))}
        return {"status": "FAIL", "evidence": str(p.relative_to(REPO_ROOT)),
                "reason": "evidence log hash mismatch" if not ok_log else f"exit {rec.get('exit_code')}"}
    b = blockers.get(tid)
    if b:
        return {"status": b["status"], "reason": b["reason"]}
    return {"status": "NOT_RUN"}


def report() -> dict:
    blockers = json.loads(BLOCKERS.read_text()) if BLOCKERS.is_file() else {}
    tasks = {t["task_id"]: {**t, **task_status(t["task_id"], blockers)} for t in _csv("planned-traceability.csv")}
    frs = []
    for r in _csv("requirements.csv"):
        ts = [t for t in r["planned_tasks"].split(";") if t]
        st = [tasks[t]["status"] for t in ts]
        cov = "COVERED" if all(s == "PASS" for s in st) else "PARTIAL" if any(s == "PASS" for s in st) else "OPEN"
        frs.append({"id": r["requirement_id"], "priority": r["priority"], "coverage": cov,
                    "tasks": {t: tasks[t]["status"] for t in ts}, "acceptance": r["acceptance_tests"].split(";")})
    count = lambda xs, k: {s: sum(1 for x in xs if x[k] == s) for s in sorted({x[k] for x in xs})}  # noqa: E731
    return {"schema": "forge-c/afo-status/0.1", "generated_at": utc_now(), "tasks": tasks, "requirements": frs,
            "task_counts": count(list(tasks.values()), "status"), "fr_counts": count(frs, "coverage"),
            "note": "status from executed evidence and the blocker register only; tasks.md boxes are not read"}


def markdown(rep: dict) -> str:
    tc = ", ".join(f"{k} {v}" for k, v in rep["task_counts"].items())
    fc = ", ".join(f"{k} {v}" for k, v in rep["fr_counts"].items())
    lines = ["# Feature 005 (AFO) status - generated from evidence records", "",
             f"Generated {rep['generated_at']}. {rep['note']}.", "", f"Tasks: {tc}.", f"FRs: {fc}.", "",
             "| Task | M | P | Status | ATs | Evidence / reason |", "|---|---|---|---|---|---|"]
    for tid, t in rep["tasks"].items():
        lines.append(f"| {tid} | {t['milestone']} | {t['priority']} | {t['status']} | "
                     f"{t['planned_test_refs'].replace(';', ', ')} | {t.get('evidence') or t.get('reason', '')} |")
    lines += ["", "| FR | P | Coverage | Tasks |", "|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['priority']} | {r['coverage']} | "
              + ", ".join(f"{k}={v}" for k, v in r["tasks"].items()) + " |" for r in rep["requirements"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    rep = report()
    MD.parent.mkdir(parents=True, exist_ok=True)
    JS.parent.mkdir(parents=True, exist_ok=True)
    MD.write_text(markdown(rep))
    JS.write_text(pretty_json(rep))
    print(json.dumps({"tasks": rep["task_counts"], "frs": rep["fr_counts"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
