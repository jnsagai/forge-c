"""T016 — forge-evidence-mcp: baseline freeze, trace validation, inspection recording, packaging.

All writes go through deterministic engines (inspection engine, release finalizer); the calling role is
taken from the authorization ticket, so an author cannot record an inspection and an inspector cannot
freeze a baseline. Released archives are written once and never modified.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...inspection.engine import InspectionError, Store
from ..sdk import Operation, ToolContext, ToolDenied, ToolInput, build_server, result

Phase = Literal["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]


class FreezeIn(ToolInput):
    phase: Phase


class TraceIn(ToolInput):
    pass


class ItemVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["PASS", "FAIL", "NOT_APPLICABLE"]
    evidence_refs: list[str] = Field(default_factory=list, max_length=10)
    findings: list[str] = Field(default_factory=list, max_length=10)


class InspectIn(ToolInput):
    phase: Phase
    baseline_id: str = Field(pattern=r"^BL-SWE\.[1-6]-\d{3}$")
    # Small models often send bare verdict strings; accepted and normalised (evidence = inspected baseline record).
    verdicts: dict[str, ItemVerdict | Literal["PASS", "FAIL", "NOT_APPLICABLE"]] | str = Field(max_length=4000)


_ITEM = re.compile(r"\b([A-Z0-9]{2,8}-\d{2})\s*[=:]\s*(PASS|FAIL|NOT_APPLICABLE)\b", re.I)


def parse_verdict_string(text: str) -> dict[str, dict]:
    """'SWE2-01=PASS; SWE2-02=FAIL:missing budget' -> verdict objects (flat form for small models).

    Items are located by their IDs, so any separator works ('; ', newline, '. ' - r33 used full stops)."""
    out: dict[str, dict] = {}
    hits = list(_ITEM.finditer(text))
    for k, m in enumerate(hits):
        end = hits[k + 1].start() if k + 1 < len(hits) else len(text)
        note = text[m.end():end].strip().lstrip(":").strip().rstrip(";.,").strip()
        out[m.group(1).upper()] = {"verdict": m.group(2).upper(), "evidence_refs": [],
                                   "findings": [note[:120]] if note else []}
    return out


class PackageIn(ToolInput):
    pass


def freeze_baseline(ctx: ToolContext, a: FreezeIn) -> dict:
    if ctx.phase and ctx.phase != a.phase:
        raise ToolDenied("PHASE_MISMATCH", f"{ctx.phase}!={a.phase}")
    try:
        bl = Store(ctx.workspace).freeze(a.phase, ctx.role)
    except InspectionError as exc:
        return result(ctx, "BLOCKED", f"freeze refused: {exc}"[:160], issues=[str(exc)[:120]], tool="forge-baseline")
    return result(ctx, "PASS", f"{bl['baseline_id']} frozen ({len(bl['files'])} files)",
                  [f"configuration/baselines/{a.phase}/{bl['baseline_id']}.json"], [],
                  {"baseline_hash": bl["baseline_hash"], "files": len(bl["files"])}, "forge-baseline",
                  input_obj=a.model_dump())


def validate_trace(ctx: ToolContext, a: TraceIn) -> dict:
    req = ctx.workspace / "workproducts/SWE.1/software_requirements.md"
    tr = ctx.workspace / "traceability/requirements_to_tests.csv"
    issues = []
    reqs = sorted(set(re.findall(r"\*\*(SWR-[A-Z0-9_.-]+)\*\*", req.read_text()))) if req.is_file() else []
    if not reqs:
        issues.append("TRACE_NO_REQUIREMENTS")
    rows = []
    if tr.is_file():
        rows = list(csv.DictReader(io.StringIO(tr.read_text())))
    else:
        issues.append("TRACE_FILE_MISSING:traceability/requirements_to_tests.csv")
    traced = {r.get("requirement_id", "").strip() for r in rows}
    # Test files exist only from SWE.4 on: before a SWE.4 baseline, a missing file is a planned link, not a defect.
    tests_due = any((ctx.workspace / "configuration/baselines/SWE.4").glob("BL-*.json"))
    planned = 0
    for r in reqs:
        if r not in traced:
            issues.append(f"UNTRACED:{r}")
    for row in rows:
        rid, test = row.get("requirement_id", "").strip(), (row.get("test_id") or "").strip()
        if rid and rid not in reqs:
            issues.append(f"TRACE_UNKNOWN_REQ:{rid}")
        if rid and not test:
            issues.append(f"NO_TEST_FOR:{rid}")
        tfile = (row.get("test_file") or "").strip()
        if tfile:
            try:
                tpath = ctx.path(tfile, must_exist=True, kind="file")
                # r41: the trace must not cite test ids the test file does not contain (false traceability)
                if tests_due and test and not re.search(rf"\b{re.escape(test)}\b", tpath.read_text(errors="replace")):
                    issues.append(f"TEST_ID_NOT_IN_FILE:{test}:{tfile[:50]}")
            except ToolDenied:
                if tests_due:
                    issues.append(f"TEST_FILE_MISSING:{tfile[:60]}")
                else:
                    planned += 1
    covered = len([r for r in reqs if r in traced])
    return result(ctx, "PASS" if not issues else "FAIL", f"{covered}/{len(reqs)} requirements traced"
                  + (f"; {planned} test links planned (test files are due at SWE.4)" if planned else ""), [], issues,
                  {"requirements": len(reqs), "traced": covered, "rows": len(rows), "planned_test_links": planned,
                   "test_files_required": tests_due}, "forge-trace-gate", input_obj=a.model_dump())


def check_inspection(ctx: ToolContext, a: InspectIn) -> dict:
    base_ref = f"configuration/baselines/{a.phase}/{a.baseline_id}.json"
    if isinstance(a.verdicts, str):
        verdicts = parse_verdict_string(a.verdicts)
    else:
        verdicts = {k: (v.model_dump() if isinstance(v, ItemVerdict) else
                        {"verdict": v, "evidence_refs": [base_ref], "findings": []}) for k, v in a.verdicts.items()}
    for v in verdicts.values():
        if not v["evidence_refs"]:
            v["evidence_refs"] = [base_ref]
    try:
        rec = Store(ctx.workspace).record_inspection(a.phase, ctx.role, a.baseline_id, verdicts)
    except InspectionError as exc:
        return result(ctx, "BLOCKED", f"inspection refused: {exc}"[:160], issues=[str(exc)[:120]],
                      tool="forge-inspection")
    return result(ctx, "PASS" if rec["verdict"] == "PASS" else "FAIL",
                  f"{rec['inspection_id']} {rec['verdict']} ({len(rec['findings'])} findings)",
                  [f"inspection/{a.phase}/{rec['inspection_id']}.json"],
                  [f"{f['id']}:{f['severity']}" for f in rec["findings"]], {"stale": bool(rec["stale_reason"])},
                  "forge-inspection", input_obj=a.model_dump())


def build_package(ctx: ToolContext, a: PackageIn) -> dict:
    from ...release.finalize import finalize

    out = finalize(ctx.workspace, ctx.run_id)
    return result(ctx, "PASS" if out["package_status"] in ("READY_FOR_OFFLINE_REVIEW", "BLOCKED") else "FAIL",
                  f"package {out['package_status']} gaps={out['gap_count']}", [out["archive_ref"]],
                  [f"GAP:{g}"[:120] for g in out.get("gaps", [])[:10]],
                  {"package_status": out["package_status"], "gap_count": out["gap_count"]}, "forge-packager-v0.4")


OPERATIONS = [
    Operation("freeze_baseline", FreezeIn, freeze_baseline, "Freeze your phase outputs to a content-hash baseline."),
    Operation("validate_trace", TraceIn, validate_trace, "Check SWR requirement <-> test traceability."),
    Operation("check_inspection", InspectIn, check_inspection, "Record an inspection of a frozen baseline (inspectors)."),
    Operation("build_package", PackageIn, build_package, "Build the offline review package (READY or BLOCKED)."),
]

if __name__ == "__main__":
    build_server("forge-evidence-mcp", OPERATIONS).run("stdio")
