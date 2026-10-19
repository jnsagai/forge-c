"""T051/KPI-T020 — FR -> task -> test -> evidence coverage matrix and implementation status report.

Status per task comes ONLY from evidence records (evidence/v0.4/runs/<task>/latest.json): PASS needs exit 0 and a
checked box; everything else is FAIL or NOT_RUN. A P0 requirement without a PASS task is reported as a gap.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .common import REPO_ROOT, pretty_json, utc_now

FEATURES = {"002": REPO_ROOT / "specs/002-self-healing-factory", "003": REPO_ROOT / "specs/003-manufacturing-kpis",
            "004": REPO_ROOT / "specs/004-continuous-reliability-engineering"}


def tasks(feature_dir: Path, prefix: str) -> list[dict]:
    out = []
    for line in (feature_dir / "tasks.md").read_text().splitlines():
        m = re.match(rf"^- \[([ X])\] \*\*({prefix}\d{{3}})\b.*?\[(P\d)\]\*?\*?(.*)$", line)
        if not m:
            continue
        frs = sorted(set(re.findall(r"CRE-FR-\d{3}", line))) if prefix == "CRE-T" else \
            sorted(set(re.findall(r"(?:KPI-)?FR-\d{3}", line)))
        if "FR-001..FR-040" in line:
            frs = [f"FR-{i:03d}" for i in range(1, 41)]
        if "all KPI-FR" in line:
            frs = ["KPI-FR-ALL"]
        refs = re.findall(r"`(evidence/v0\.4/runs/[^`]+)`", line)
        out.append({"task": m.group(2), "checked": m.group(1) == "X", "priority": m.group(3), "frs": frs,
                    "evidence": refs, "line": line[:200]})
    return out


def evidence_status(t: dict) -> str:
    if not t["evidence"]:
        return "NOT_RUN"
    sts = []
    for ref in t["evidence"]:
        p = REPO_ROOT / ref
        if not p.is_file():
            return "NOT_RUN"
        rec = json.loads(p.read_text())
        sts.append(rec["status"] == "PASS" and rec["exit_code"] == 0)
    return "PASS" if all(sts) and t["checked"] else "FAIL"


def cre_matrix() -> tuple[list[dict], list[dict], list[str]]:
    """Feature 004: CRE-T tasks (status from evidence only) and the CRE-FR -> task coverage; unmet P0 = gap."""
    d = FEATURES["004"]
    if not (d / "tasks.md").is_file():
        return [], [], []
    t004 = tasks(d, "CRE-T")
    for t in t004:
        t["status"] = evidence_status(t)
    frs = {m.group(1): m.group(2) for m in re.finditer(r"^\| (CRE-FR-\d{3}) \| .+? \| (P\d) \|$",
                                                       (d / "spec.md").read_text(), re.M)}
    rows, gaps = [], []
    for fr, prio in sorted(frs.items()):
        ts = [t for t in t004 if fr in t["frs"]]
        passed = [t["task"] for t in ts if t["status"] == "PASS"]
        status = "COVERED" if passed else ("BLOCKED" if prio == "P0" else "GAP")
        if not passed and prio == "P0":
            gaps.append(fr)
        rows.append({"fr": fr, "priority": prio, "tasks": [t["task"] for t in ts], "passing_tasks": passed,
                     "status": status})
    return t004, rows, gaps


def build() -> dict:
    spec = (FEATURES["002"] / "spec.md").read_text()
    frs = {m.group(1): m.group(3) for m in re.finditer(r"^\| (FR-\d{3}) \| (.+?) \| (P\d) \|$", spec, re.M)}
    t002 = tasks(FEATURES["002"], "T")
    t003 = tasks(FEATURES["003"], "KPI-T") if (FEATURES["003"] / "tasks.md").is_file() else []
    for t in t002 + t003:
        t["status"] = evidence_status(t)
    at = {m.group(1): m.group(2) for m in re.finditer(r"^\| (AT-\d{2}) \| .+? \| .+? \| (.+?) \|$",
                                                      (FEATURES["002"] / "acceptance-tests.md").read_text(), re.M)}
    fr_rows, gaps = [], []
    for fr, prio in sorted(frs.items()):
        ts = [t for t in t002 if fr in t["frs"]]
        passed = [t["task"] for t in ts if t["status"] == "PASS"]
        status = "COVERED" if passed else "GAP"
        if status == "GAP" and prio == "P0":
            gaps.append(fr)
        fr_rows.append({"fr": fr, "priority": prio, "tasks": [t["task"] for t in ts], "passing_tasks": passed,
                        "status": status})
    t004, cre_rows, cre_gaps = cre_matrix()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    return {"schema": "forge-c/implementation-status/0.4", "generated_at": utc_now(), "git_head": head,
            "tasks_002": t002, "tasks_003": t003, "fr_matrix": fr_rows, "acceptance_tests": at, "p0_gaps": gaps,
            "tasks_004": t004, "cre_fr_matrix": cre_rows, "cre_p0_gaps": cre_gaps,
            "summary": {"002_pass": sum(t["status"] == "PASS" for t in t002), "002_total": len(t002),
                        "003_pass": sum(t["status"] == "PASS" for t in t003), "003_total": len(t003),
                        "004_pass": sum(t["status"] == "PASS" for t in t004), "004_total": len(t004),
                        "cre_fr_covered": sum(r["status"] == "COVERED" for r in cre_rows), "cre_fr_total": len(cre_rows),
                        "fr_covered": sum(r["status"] == "COVERED" for r in fr_rows), "fr_total": len(fr_rows)},
            "release_semantics": "Factory outputs are READY_FOR_OFFLINE_REVIEW or BLOCKED only; no ASIL B approval."}


def markdown(rep: dict) -> str:
    s = rep["summary"]
    lines = ["# Forge-C implementation status (generated from evidence records)", "",
             f"Generated {rep['generated_at']} at commit `{rep['git_head'][:12]}`. Status is derived only from "
             "`evidence/v0.4/runs/*/latest.json`; a checkbox without a passing evidence record is not PASS.", "",
             f"* Feature 002: **{s['002_pass']}/{s['002_total']}** tasks PASS",
             f"* Feature 003 (KPI): **{s['003_pass']}/{s['003_total']}** tasks PASS",
             f"* Functional requirements covered by a passing task: **{s['fr_covered']}/{s['fr_total']}**",
             f"* P0 requirement gaps: {', '.join(rep['p0_gaps']) or 'none'}", "",
             "## Feature 002 tasks", "", "| Task | P | Status | FRs | Evidence |", "|---|---|---|---|---|"]
    for t in rep["tasks_002"]:
        ev = "<br>".join(t["evidence"][:2]) or "-"
        lines.append(f"| {t['task']} | {t['priority']} | {t['status']} | {', '.join(t['frs'][:6])}"
                     f"{'…' if len(t['frs']) > 6 else ''} | {ev} |")
    if rep["tasks_003"]:
        lines += ["", "## Feature 003 tasks", "", "| Task | P | Status | Evidence |", "|---|---|---|---|"]
        for t in rep["tasks_003"]:
            lines.append(f"| {t['task']} | {t['priority']} | {t['status']} | {'<br>'.join(t['evidence'][:2]) or '-'} |")
    if rep.get("tasks_004"):
        lines += ["", f"## Feature 004 (CRE) tasks — {s['004_pass']}/{s['004_total']} PASS; CRE-FR covered "
                  f"{s['cre_fr_covered']}/{s['cre_fr_total']}; unmet P0: {', '.join(rep['cre_p0_gaps']) or 'none'}", "",
                  "| Task | P | Status | Evidence |", "|---|---|---|---|"]
        for t in rep["tasks_004"]:
            lines.append(f"| {t['task']} | {t['priority']} | {t['status']} | {'<br>'.join(t['evidence'][:2]) or '-'} |")
    lines += ["", "## FR → task matrix", "", "| FR | P | Tasks | Passing | Status |", "|---|---|---|---|---|"]
    for r in rep["fr_matrix"]:
        lines.append(f"| {r['fr']} | {r['priority']} | {', '.join(r['tasks'])} | {', '.join(r['passing_tasks']) or '-'} | "
                     f"{r['status']} |")
    lines += ["", "## Acceptance tests → tasks", "", "| AT | Tasks |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(rep["acceptance_tests"].items())]
    lines += ["", rep["release_semantics"], ""]
    return "\n".join(lines)


def main() -> int:
    rep = build()
    (REPO_ROOT / "evidence/v0.4/implementation-status.json").write_text(pretty_json(rep))
    (REPO_ROOT / "docs/IMPLEMENTATION-STATUS-v0.4.md").write_text(markdown(rep))
    s = rep["summary"]
    print(f"002 {s['002_pass']}/{s['002_total']} PASS; 003 {s['003_pass']}/{s['003_total']}; "
          f"004 {s['004_pass']}/{s['004_total']}; FR {s['fr_covered']}/{s['fr_total']}; P0 gaps: {rep['p0_gaps']}; "
          f"CRE-FR {s['cre_fr_covered']}/{s['cre_fr_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
