"""EASA-T071 — FR -> task -> acceptance test -> evidence matrix, from evidence records ONLY.

The authored tasks.md keeps its unchecked boxes (validate_spec.py counts them by design), so status lives here:
PASS needs evidence/v0.4/runs/<task>/latest.json with status PASS, exit 0, and a git_head that is an ancestor of
the current HEAD (evidence for code that is not on this branch does not count). BLOCKED/NOT_APPLICABLE come only
from the blocker register `evidence/easa/blockers.json` with a reason; everything else is NOT_RUN or FAIL.
An FR is COVERED only if every one of its tasks is PASS; PARTIAL if some are.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, utc_now
from .contracts import SPEC_DIR

RUNS = REPO_ROOT / "evidence/v0.4/runs"
BLOCKERS = REPO_ROOT / "evidence/easa/blockers.json"


def _ancestor(rev: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", rev, "HEAD"], cwd=REPO_ROOT,
                          capture_output=True).returncode == 0


def task_status(task: str, blockers: dict) -> dict:
    p = RUNS / task / "latest.json"
    if p.is_file():
        rec = json.loads(p.read_text())
        ok = rec.get("status") == "PASS" and rec.get("exit_code") == 0
        if ok and not _ancestor(rec.get("git_head", "")):
            return {"status": "FAIL", "reason": "evidence git_head not on this branch", "evidence": str(p.relative_to(REPO_ROOT))}
        if ok:
            b = blockers.get(task)
            if b and b.get("status") == "PARTIAL":
                return {"status": "PARTIAL", "reason": b["reason"], "evidence": str(p.relative_to(REPO_ROOT))}
            return {"status": "PASS", "evidence": str(p.relative_to(REPO_ROOT)), "git_head": rec["git_head"][:12]}
        return {"status": "FAIL", "reason": f"exit {rec.get('exit_code')}", "evidence": str(p.relative_to(REPO_ROOT))}
    if task in blockers:
        return {"status": blockers[task]["status"], "reason": blockers[task]["reason"]}
    return {"status": "NOT_RUN"}


def build() -> dict:
    blockers = json.loads(BLOCKERS.read_text()) if BLOCKERS.is_file() else {}
    tasks_md = (SPEC_DIR / "tasks.md").read_text(encoding="utf-8")
    tasks = {}
    for m in re.finditer(r"^- \[[ xX]\] \*\*(EASA-T\d{3}) \[(P\d)\]\*\* (.*?)\*\*Refs:\*\* (.*?)\. \*\*Acceptance:\*\* (.*?)\.",
                         tasks_md, re.M):
        tasks[m.group(1)] = {"priority": m.group(2), "title": m.group(3).strip(),
                             "frs": re.findall(r"EASA-FR-\d{3}", m.group(4)), "ats": re.findall(r"EASA-AT-\d{3}", m.group(5)),
                             **task_status(m.group(1), blockers)}
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
            "task_counts": counts, "fr_matrix": frs,
            "fr_counts": {c: sum(1 for f in frs if f["coverage"] == c) for c in ("COVERED", "PARTIAL", "BLOCKED", "OPEN")},
            "statement": "Bounded engineering evidence; no ISO 26262 / Automotive SPICE conformance claim."}


def markdown(rep: dict) -> str:
    c, f = rep["task_counts"], rep["fr_counts"]
    lines = ["# Feature 006 (EASA) status — generated from evidence records", "",
             f"Generated {rep['generated_at']} at `{rep['git_head'][:12]}`. Task status comes only from "
             "`evidence/v0.4/runs/EASA-T*/latest.json` and the blocker register; the authored `tasks.md` boxes stay "
             "unchecked by design.", "",
             "Tasks: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())) + ".",
             "FRs: " + ", ".join(f"{k} {v}" for k, v in f.items()) + ".", "",
             "| Task | P | Status | ATs | Evidence / reason |", "|---|---|---|---|---|"]
    for tid, t in rep["tasks"].items():
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
