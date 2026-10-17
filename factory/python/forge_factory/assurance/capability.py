"""EASA-T014 and AT-074 — method -> evidence -> real capability. A method maps only to MCP operations that are
implemented AND backed by an installed tool (`mcp.preflight.op_catalog`); design-review methods map to a controlled
review (human or independent inspector), never to a tool PASS. Metric records are validated so that an unobserved
measurement can never carry a number (EASA-FR-018/068)."""
from __future__ import annotations

from ..mcp.preflight import op_catalog
from . import contracts

A, T, S, B, R, D = ("forge-analysis-mcp", "forge-tests-mcp", "forge-sim-mcp", "forge-build-mcp",
                    "forge-evidence-mcp", "forge-docs-mcp")
SUPPORT: dict[str, list[str]] = {  # method id prefix -> supporting real operations
    "ISO6-T01-1A": [f"{A}.clang_tidy"], "ISO6-T01-1B": [f"{A}.cppcheck"], "ISO6-T01-1C": [f"{A}.clang_tidy"],
    "ISO6-T01-1F": [f"{D}.render_diagram"], "ISO6-T01-1G": [f"{A}.clang_tidy"], "ISO6-T01-1H": [f"{A}.clang_tidy"],
    "ISO6-T04-1B": [f"{R}.check_inspection"], "ISO6-T06-1C": [f"{A}.clang_analyze", f"{A}.cppcheck"],
    "ISO6-T06-1F": [f"{A}.clang_analyze"], "ISO6-T06-1G": [f"{A}.clang_tidy"], "ISO6-T06-1H": [f"{A}.cppcheck"],
    "ISO6-T06-1I": [f"{A}.cppcheck"], "ISO6-T07-1C": [f"{R}.check_inspection"],
    "ISO6-T07-1H": [f"{A}.cppcheck", f"{A}.clang_analyze", f"{A}.clang_tidy"],
    "ISO6-T07-1J": [f"{T}.run_unit"], "ISO6-T07-1K": [f"{T}.run_unit"], "ISO6-T08-1A": [f"{T}.run_unit"],
    "ISO6-T08-1C": [f"{T}.run_unit"], "ISO6-T09-1A": [f"{T}.llvm_coverage"], "ISO6-T09-1B": [f"{T}.llvm_coverage"],
    "ISO6-T10-1A": [f"{T}.run_integration", f"{S}.run_renode"], "ISO6-T10-1B": [f"{T}.run_integration"],
    "ISO6-T10-1D": [f"{B}.measure_elf", f"{B}.stack_usage"], "ISO6-T10-1G": [f"{A}.cppcheck", f"{A}.clang_analyze"],
    "ISO6-T11-1A": [f"{T}.run_integration"], "ISO6-T11-1C": [f"{T}.run_integration"],
    "ISO6-T14-1A": [f"{T}.run_robot", f"{S}.run_renode"], "ISO6-T15-1A": [f"{T}.run_robot"],
    "ISO6-T15-1B": [f"{T}.run_robot"], "ISO6-T15-1F": [f"{T}.run_robot"],
}
NEEDS_PHYSICAL = {"ISO6-T13-1A": "no hardware-in-the-loop rig registered", "ISO6-T13-1B": "no ECU network rig registered"}


def resolve(catalog: dict, ops: dict | None = None) -> list[dict]:
    ops = ops if ops is not None else op_catalog()
    out = []
    for m in catalog["methods"]:
        mid, kind = m["method_id"], m.get("default_evidence_kind")
        adapters = [{"op": o, "status": (ops.get(o) or {}).get("status", "NOT_REGISTERED")} for o in SUPPORT.get(mid, [])]
        ok = [a for a in adapters if a["status"] == "OK"]
        if mid in NEEDS_PHYSICAL:
            res, why = "NOT_SUPPORTED", NEEDS_PHYSICAL[mid]
        elif kind == "tool_execution":
            res = "SUPPORTED" if adapters and len(ok) == len(adapters) else ("PARTIAL" if ok else "NOT_SUPPORTED")
            why = None if res == "SUPPORTED" else "required tool operation not available: " + ",".join(
                a["op"] for a in adapters if a["status"] != "OK")
        else:  # design_review / inspection: controlled review, tools only support it
            res, why = "CONTROLLED_REVIEW", "evidence is a controlled human/independent-inspector review"
        out.append({"method_id": mid, "evidence_kind": kind, "adapters": adapters, "resolution": res, "reason": why})
    return out


def metric_findings(rec: dict) -> list[str]:
    """AT-074: a NOT_RUN/NOT_SUPPORTED/UNKNOWN metric must not carry numbers; MEASURED needs runs and counts."""
    issues = contracts.errors("coverage-evidence", rec)
    st = rec.get("status")
    if st != "MEASURED":
        if rec.get("measured") or rec.get("covered") is not None or rec.get("total") is not None:
            issues.append(f"FABRICATED_METRIC:{rec.get('kind')}:{st}")
    else:
        if not rec.get("measured") or rec.get("covered") is None or not rec.get("total"):
            issues.append("MEASURED_WITHOUT_COUNTS")
        elif rec["covered"] > rec["total"]:
            issues.append("COVERED_EXCEEDS_TOTAL")
        if not rec.get("test_run_refs"):
            issues.append("MEASURED_WITHOUT_TEST_RUN_REF")
    for k in ("percent", "pct", "score"):
        if k in rec:
            issues.append(f"PERCENT_WITHOUT_COUNTS_FIELD:{k}")
    return issues
