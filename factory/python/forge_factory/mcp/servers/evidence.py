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

from ...inspection.engine import InspectionError, Store, load_checklist
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


# r56: DeepSeek wrote "SWE5-05=Rework finding: ..." - a failure in other words. Fail synonyms map to FAIL (the
# conservative direction); a pass is only ever the literal PASS.
_FAIL_WORDS = "FAIL|FAILED|REWORK|REJECT|REJECTED|NOK|NOT_OK"
_ITEM = re.compile(rf"\b([A-Z0-9]{{2,8}}-\d{{2}})\s*[=:]\s*(PASS|NOT_APPLICABLE|{_FAIL_WORDS})\b", re.I)


def parse_verdict_string(text: str) -> dict[str, dict]:
    """'SWE2-01=PASS; SWE2-02=FAIL:missing budget' -> verdict objects (flat form for small models).

    Items are located by their IDs, so any separator works ('; ', newline, '. ' - r33 used full stops)."""
    out: dict[str, dict] = {}
    hits = list(_ITEM.finditer(text))
    for k, m in enumerate(hits):
        end = hits[k + 1].start() if k + 1 < len(hits) else len(text)
        note = text[m.end():end].strip().lstrip(":").strip().rstrip(";.,").strip()
        word = m.group(2).upper()
        out[m.group(1).upper()] = {"verdict": word if word in ("PASS", "NOT_APPLICABLE") else "FAIL", "evidence_refs": [],
                                   "findings": [note[:120]] if note else []}
    return out


class PackageIn(ToolInput):
    pass


def _list(v: list[str] | str) -> list[str]:
    """Small models send comma/space separated strings for lists; accepted and normalised."""
    items = v if isinstance(v, list) else re.split(r"[,\s]+", v)
    return [x.strip() for x in items if x and x.strip()]


class DefectIn(ToolInput):
    kind: Literal["CODE", "ARCHITECTURE", "REQUIREMENT", "TEST", "INPUT", "FACTORY"]
    summary: str = Field(min_length=10, max_length=400)
    requirement_ids: list[str] | str = Field(default_factory=list, max_length=400)
    test_files: list[str] | str = Field(default_factory=list, max_length=600)
    evidence_refs: list[str] | str = Field(default_factory=list, max_length=600)
    requirement_quote: str = Field(default="", max_length=300)


class RejectIn(ToolInput):
    defect_id: str = Field(pattern=r"^DEF-\d{3}$")
    reason: str = Field(min_length=10, max_length=400)


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
    # r56: an item without a recognisable verdict used to be recorded as FAIL:MISSING_VERDICT, which lost the
    # inspector's finding and sent the author into a rework cycle with nothing to fix. Refuse instead (nothing is
    # recorded) so the inspector resubmits; the inspector node is bounded by max_visits and its turn cap.
    try:
        checklist = load_checklist(a.phase)
    except Exception:  # noqa: BLE001 - the engine reports checklist problems itself
        checklist = {"checks": []}
    missing = [c["id"] for c in checklist["checks"]
               if c.get("required") and not c.get("deterministic_check") and c["id"] not in verdicts]
    if missing:
        return result(ctx, "FAIL", f"inspection not recorded: no PASS/FAIL/NOT_APPLICABLE verdict for "
                      f"{', '.join(missing)}; resubmit EVERY item as ID=PASS or ID=FAIL:<finding>"[:160],
                      issues=[f"INCOMPLETE_VERDICTS:{m}" for m in missing][:10], tool="forge-inspection")
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


def report_defect(ctx: ToolContext, a: DefectIn) -> dict:
    """ADR-0008: a defect this role may not fix (CODE->SWE.3, ARCHITECTURE->SWE.2, REQUIREMENT->SWE.1), a declared
    correction of a test in the own phase (TEST), or an escalation (INPUT, FACTORY). Validated deterministically."""
    from ...inspection import defects

    if not ctx.phase:
        raise ToolDenied("NO_PHASE", "report_defect needs the node's phase")
    try:
        rec = defects.report(ctx.workspace, detected_phase=ctx.phase, reported_by=ctx.role, kind=a.kind,
                             summary=a.summary, requirement_ids=_list(a.requirement_ids),
                             test_files=_list(a.test_files), evidence_refs=_list(a.evidence_refs),
                             requirement_quote=a.requirement_quote)
    except defects.DefectError as exc:
        return result(ctx, "FAIL", f"defect not recorded: {exc}"[:160], issues=[str(exc)[:120]], tool="forge-defects")
    return result(ctx, "PASS", f"{rec['id']} {rec['kind']} -> {rec['target_phase'] or 'human'} {rec['status']}",
                  [f"{defects.DIR}/{rec['id']}.json"], [], {"target_phase": rec["target_phase"]}, "forge-defects",
                  input_obj=a.model_dump())


def reject_defect(ctx: ToolContext, a: RejectIn) -> dict:
    """The target phase's author rejects a reported defect (the downstream test is wrong), with a recorded reason."""
    from ...inspection import defects

    try:
        rec = defects.reject(ctx.workspace, a.defect_id, ctx.role, a.reason)
    except defects.DefectError as exc:
        return result(ctx, "FAIL", f"not rejected: {exc}"[:160], issues=[str(exc)[:120]], tool="forge-defects")
    return result(ctx, "PASS", f"{rec['id']} REJECTED", [f"{defects.DIR}/{rec['id']}.json"], [], {}, "forge-defects",
                  input_obj=a.model_dump())


OPERATIONS = [
    Operation("freeze_baseline", FreezeIn, freeze_baseline, "Freeze your phase outputs to a content-hash baseline."),
    Operation("validate_trace", TraceIn, validate_trace, "Check SWR requirement <-> test traceability."),
    Operation("check_inspection", InspectIn, check_inspection, "Record an inspection of a frozen baseline (inspectors)."),
    Operation("build_package", PackageIn, build_package, "Build the offline review package (READY or BLOCKED)."),
    Operation("report_defect", DefectIn, report_defect, "Report a defect you may not fix: CODE (SWE.3), ARCHITECTURE "
              "(SWE.2), REQUIREMENT (SWE.1); declare a TEST correction in your phase; escalate INPUT/FACTORY."),
    Operation("reject_defect", RejectIn, reject_defect, "Target-phase author: reject a reported defect with a reason."),
]

if __name__ == "__main__":
    build_server("forge-evidence-mcp", OPERATIONS).run("stdio")
