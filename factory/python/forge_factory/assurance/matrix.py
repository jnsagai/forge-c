"""EASA-T071 — FR -> task -> acceptance test -> evidence matrix, from evidence records ONLY.

Status lives here, never in the tasks.md boxes (scripts/mark_task.py checks a box only with PASS evidence):
PASS needs evidence/v0.4/runs/<task>/latest.json with status PASS, exit 0, and a git_head that is an ancestor of
the current HEAD (evidence for code that is not on this branch does not count) and a log whose sha256 matches the
record. BLOCKED/NOT_APPLICABLE/PARTIAL come only from the blocker register `evidence/easa/blockers.json` with a
reason; a blocker without one is FAIL. Everything else is NOT_RUN or FAIL.
An FR is COVERED only if every one of its tasks is PASS; PARTIAL if some are. The owner addendum's tasks (T073-T079,
refs EASA-OR-*) are reported in their own section.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, sha256_file, utc_now
from .contracts import SPEC_DIR

RUNS = REPO_ROOT / "evidence/v0.4/runs"
BLOCKERS = REPO_ROOT / "evidence/easa/blockers.json"
ADDENDUM = "owner-addendum-2026-10-17.md"
BLOCKER_STATES = ("BLOCKED", "NOT_APPLICABLE", "PARTIAL")


def _ancestor(rev: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", rev, "HEAD"], cwd=REPO_ROOT,
                          capture_output=True).returncode == 0


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def task_status(task: str, blockers: dict) -> dict:
    b = blockers.get(task)
    if b is not None and (b.get("status") not in BLOCKER_STATES or not str(b.get("reason") or "").strip()):
        return {"status": "FAIL", "reason": "INVALID_BLOCKER_RECORD (status must be one of "
                f"{'/'.join(BLOCKER_STATES)} with a reason)"}
    p = RUNS / task / "latest.json"
    if p.is_file():
        try:
            rec = json.loads(p.read_text())
        except ValueError:
            return {"status": "FAIL", "reason": "EVIDENCE_NOT_JSON", "evidence": _rel(p)}
        log = REPO_ROOT / str(rec.get("log") or "")
        if rec.get("log") and (not log.is_file() or sha256_file(log) != rec.get("log_sha256")):
            return {"status": "FAIL", "reason": "LOG_HASH_MISMATCH", "evidence": _rel(p)}
        ok = rec.get("status") == "PASS" and rec.get("exit_code") == 0 and bool(rec.get("log"))
        if ok and not _ancestor(rec.get("git_head", "")):
            return {"status": "FAIL", "reason": "evidence git_head not on this branch", "evidence": _rel(p)}
        if ok:
            if b and b.get("status") == "PARTIAL":
                return {"status": "PARTIAL", "reason": b["reason"], "evidence": _rel(p)}
            return {"status": "PASS", "evidence": _rel(p), "git_head": rec["git_head"][:12]}
        if b:  # a failed attempt stays visible next to the blocker reason
            return {"status": b["status"], "reason": b["reason"], "evidence": _rel(p)}
        return {"status": "FAIL", "reason": f"status {rec.get('status')} exit {rec.get('exit_code')}", "evidence": _rel(p)}
    if b:
        return {"status": b["status"], "reason": b["reason"]}
    return {"status": "NOT_RUN"}


_TASK = r"^- \[[ xX]\] \*\*(EASA-T\d{3}) \[(P\d)\]\*\* (.*?)\*\*Refs:\*\* (.*?)\. \*\*Acceptance:\*\* (.*?)\."


def _tasks(text: str, blockers: dict, refs_rx: str) -> dict:
    return {m.group(1): {"priority": m.group(2), "title": m.group(3).strip(), "frs": re.findall(refs_rx, m.group(4)),
                         "ats": re.findall(r"EASA-AT-\d{3}", m.group(5)), **task_status(m.group(1), blockers)}
            for m in re.finditer(_TASK, text, re.M)}


def build() -> dict:
    blockers = json.loads(BLOCKERS.read_text()) if BLOCKERS.is_file() else {}
    tasks = _tasks((SPEC_DIR / "tasks.md").read_text(encoding="utf-8"), blockers, r"EASA-FR-\d{3}")
    add_p = SPEC_DIR / ADDENDUM
    addendum = _tasks(add_p.read_text(encoding="utf-8"), blockers, r"EASA-OR-\d{3}") if add_p.is_file() else {}
    frs = []
    for r in csv.DictReader((SPEC_DIR / "planned-traceability.csv").open()):
        ts = r["tasks"].split(";")
        st = [tasks.get(t, {}).get("status", "NOT_RUN") for t in ts]
        cov = "COVERED" if all(s == "PASS" for s in st) else ("PARTIAL" if any(s in ("PASS", "PARTIAL") for s in st)
                                                             else ("BLOCKED" if any(s == "BLOCKED" for s in st) else "OPEN"))
        frs.append({"fr": r["requirement_id"], "priority": r["priority"], "tasks": ts, "task_status": st,
                    "acceptance_tests": r["tests"].split(";"), "coverage": cov})
    counts: dict[str, int] = {}
    for t in tasks.values():
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    return {"schema": "forge-c/easa-matrix/0.1", "generated_at": utc_now(), "git_head": head, "tasks": tasks,
            "task_counts": counts, "fr_matrix": frs, "addendum_tasks": addendum,
            "addendum_counts": {s: sum(1 for t in addendum.values() if t["status"] == s)
                                for s in sorted({t["status"] for t in addendum.values()})},
            "fr_counts": {c: sum(1 for f in frs if f["coverage"] == c) for c in ("COVERED", "PARTIAL", "BLOCKED", "OPEN")},
            "statement": "Bounded engineering evidence; no ISO 26262 / Automotive SPICE conformance claim."}


def markdown(rep: dict) -> str:
    c, f = rep["task_counts"], rep["fr_counts"]
    lines = ["# Feature 006 (EASA) status — generated from evidence records", "",
             f"Generated {rep['generated_at']} at `{rep['git_head'][:12]}`. Task status comes only from "
             "`evidence/v0.4/runs/EASA-T*/latest.json` and the blocker register; `tasks.md` boxes are not read "
             "(a box is checked only by scripts/mark_task.py with PASS evidence).", "",
             "Tasks: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())) + ".",
             "FRs: " + ", ".join(f"{k} {v}" for k, v in f.items()) + ".", "",
             "| Task | P | Status | ATs | Evidence / reason |", "|---|---|---|---|---|"]
    for tid, t in rep["tasks"].items():
        lines.append(f"| {tid} | {t['priority']} | {t['status']} | {', '.join(a[-3:] for a in t['ats'])} | "
                     f"{t.get('evidence') or t.get('reason') or '-'} |")
    ad = rep.get("addendum_tasks") or {}
    if ad:
        lines += ["", "## Owner addendum 2026-10-17 (EASA-OR-001..011)", "",
                  "Tasks: " + ", ".join(f"{k} {v}" for k, v in sorted(rep["addendum_counts"].items())) + ".", "",
                  "| Task | P | Status | ATs | Evidence / reason |", "|---|---|---|---|---|"]
        for tid, t in ad.items():
            lines.append(f"| {tid} | {t['priority']} | {t['status']} | {', '.join(a[-3:] for a in t['ats'])} | "
                         f"{t.get('evidence') or t.get('reason') or '-'} |")
    lines += ["", "| FR | P | Coverage | Tasks |", "|---|---|---|---|"]
    for r in rep["fr_matrix"]:
        lines.append(f"| {r['fr']} | {r['priority']} | {r['coverage']} | "
                     + ", ".join(f"{t[-4:]}={s}" for t, s in zip(r["tasks"], r["task_status"], strict=True)) + " |")
    return "\n".join(lines) + "\n\n" + rep["statement"] + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.assurance.matrix")
    ap.add_argument("--json", type=Path, default=REPO_ROOT / "evidence/easa/status/easa-matrix.json")
    ap.add_argument("--md", type=Path, default=REPO_ROOT / "docs/assurance/EASA-STATUS.md")
    a = ap.parse_args(argv)
    rep = build()
    for p, body in ((a.json, pretty_json(rep)), (a.md, markdown(rep))):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    print(f"tasks={len(rep['tasks'])} {rep['task_counts']} frs={rep['fr_counts']}")
    return 0 if len(rep["tasks"]) == 72 and len(rep["fr_matrix"]) == 72 else 1


if __name__ == "__main__":
    sys.exit(main())
