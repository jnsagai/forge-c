"""Feature 020 T032: the benchmark comparison (FR-024, SC-008) from a fixture functional SWE.1 workspace.

Metrics only: the pilot side is computed from the SWE.1 work products, the benchmark side is a private numbers-only
file; both validate against contracts/benchmark-metrics.schema.json and every metric is reported for both sides."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from forge_factory.benchmark import compare as C

REPO = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((REPO / "specs/020-usart-benchmark-pilot/contracts/benchmark-metrics.schema.json").read_text())
FIXED = {"status": "draft", "asil": "QM", "cal": "0", "allocated_interface": "not applicable until SWE.2",
         "allocated_operation": "not applicable until SWE.2"}


def _req(n, *, type_="functional", group="use_case", links=None, use_cases=("UC-01",), vm="test", tl="component",
         pre="the module is initialised", statement=None):
    return {"id": f"SWR-{n:03d}", "task": "t", "key": f"k{n}", "title": f"Requirement {n}",
            "statement": statement or f"When the application calls Mod_Send, the module shall transmit item {n}.",
            "type": type_, "precondition": pre, "origin_group": group,
            "links": [{"kind": "trace", "input_id": "IN-01", "locator": "p.1"}] if links is None else links,
            "use_cases": list(use_cases), "verification_method": vm, "test_level": tl, **FIXED}


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    reqs = [
        _req(1),
        _req(2, links=[{"kind": "trace", "input_id": "IN-01", "locator": "p.2"},
                       {"kind": "derive", "input_id": "IN-02", "locator": "s.3", "rationale": "r"}]),
        _req(3, type_="design_constraint", group="hal_design_constraint", use_cases=(), vm="inspection",
             tl="not_testable", pre="none", statement="The module shall follow the guideline naming rule."),
        _req(4, group="awaiting_traceability", links=[], use_cases=("UC-02",)),
    ]
    files = {
        "workproducts/SWE.1/requirement_attributes.json": {"schema": "x", "template": "swe1-functional-v1",
                                                           "requirements": reqs},
        "inputs/governance-inventory.json": {
            "schema": "forge-c/governance-inventory/1", "module": "MOD", "inputs": [],
            "api": [{"function": f, "component": "HAL", "file": "m.h", "scope_class": c, "scope_group": "g"}
                    for f, c in (("Mod_Send", "in"), ("Mod_Recv", "in"), ("Mod_Init", "in"), ("Mod_Lin", "out"))],
            "rm_features": [{"feature": "transmit", "scope_class": "in"}, {"feature": "lin", "scope_class": "out"}],
            "not_delivered": [{"capability": "loopback", "note": "n"}]},
        "workproducts/SWE.1/governance/governance-package.json": {
            "schema": "forge-c/governance-package/1", "package_version": "v", "inventory_sha256": "0" * 64,
            "actors": [], "assumptions": [], "open_points": [], "coverage": {},
            "use_cases": [{"use_case_id": "UC-01", "title": "send", "actor_id": "A", "goal": "g",
                           "functions": ["Mod_Send"], "rm_features": ["transmit"], "origin": "generated"},
                          {"use_case_id": "UC-02", "title": "receive", "actor_id": "A", "goal": "g",
                           "functions": ["Mod_Recv"], "origin": "generated"}]},
    }
    for rel, doc in files.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc))
    return ws


BENCH = {"side": "benchmark", "requirement_count": 5, "by_type": {"functional": 4, "design_constraint": 1},
         "attribute_completeness": {"statement": 1.0, "precondition": 0.4}, "by_origin_group": {"groups_defined": 3},
         "link_kinds": {"trace": 4, "derive": 2}, "verification_methods": {"test": 4, "inspection": 1},
         "test_levels": {"component": 4, "not_testable": 1}}


def test_pilot_metrics_from_the_functional_swe1(tmp_path):
    m = C.pilot_metrics(_workspace(tmp_path))
    jsonschema.validate(m, SCHEMA)
    assert m["side"] == "pilot" and m["requirement_count"] == 4
    assert m["by_type"] == {"functional": 3, "design_constraint": 1}
    assert m["by_origin_group"]["use_case"] == 2 and m["by_origin_group"]["awaiting_traceability"] == 1
    assert m["by_origin_group"]["hal_design_constraint"] == 1
    assert m["link_kinds"] == {"trace": 3, "derive": 1, "awaiting": 1}
    assert m["verification_methods"] == {"test": 3, "inspection": 1}
    assert m["test_levels"] == {"component": 3, "not_testable": 1}
    ac = m["attribute_completeness"]
    assert ac["statement"] == 1.0 and ac["precondition"] == 0.75  # "none" is not a value (as the benchmark's N/A)
    assert ac["allocated_interface"] == 0.0  # a placeholder until SWE.2 is not an allocation
    assert ac["links"] == 0.75
    sc = m["scope_coverage"]
    assert sc["in_scope_functions"] == 3 and sc["out_of_scope_functions"] == 1
    assert sc["in_scope_functions_covered_share"] == pytest.approx(2 / 3)  # Mod_Init in no requirement
    assert sc["not_delivered_capabilities"] == 1
    assert sc["in_scope_rm_features"] == 1 and sc["in_scope_rm_features_covered_share"] == 1.0
    assert sc["traced_share"] == 0.75 and sc["derived_share"] == 0.25 and sc["awaiting_share"] == 0.25


def test_the_report_holds_both_sides_for_every_metric(tmp_path):
    bench = tmp_path / "metrics.json"
    bench.write_text(json.dumps(BENCH))
    out = tmp_path / "out"
    rc = C.main(["--pilot", str(_workspace(tmp_path)), "--benchmark", str(bench), "--out", str(out)])
    assert rc == 0
    rep = json.loads((out / "comparison.json").read_text())
    jsonschema.validate(rep["pilot"], SCHEMA)
    jsonschema.validate(rep["benchmark"], SCHEMA)
    metrics = {r["metric"] for r in rep["rows"]}
    for key in C.METRICS:
        assert key in metrics, key
        rows = [r for r in rep["rows"] if r["metric"] == key]
        assert all("pilot" in r and "benchmark" in r for r in rows)
    assert {"metric": "requirement_count", "category": "", "pilot": 4, "benchmark": 5} in rep["rows"]
    # a category the benchmark does not report is shown as not reported, never as a zero
    row = next(r for r in rep["rows"] if r["metric"] == "link_kinds" and r["category"] == "awaiting")
    assert row["benchmark"] is None
    assert rep["not_delivered"] == ["loopback"]
    md = (out / "comparison.md").read_text()
    assert "| requirement_count |" in md and "not reported" in md


@pytest.mark.parametrize("case", ["missing", "invalid", "pilot_side"])
def test_a_missing_or_invalid_benchmark_file_is_refused(tmp_path, case, capsys):
    bench = tmp_path / "metrics.json"
    if case == "invalid":
        bench.write_text(json.dumps({**BENCH, "statement_text": "x"}))
    elif case == "pilot_side":
        bench.write_text(json.dumps({**BENCH, "side": "pilot"}))
    out = tmp_path / "out"
    rc = C.main(["--pilot", str(_workspace(tmp_path)), "--benchmark", str(bench), "--out", str(out)])
    assert rc == 2
    err = capsys.readouterr().err
    assert ("BENCHMARK_METRICS_MISSING" if case == "missing" else "BENCHMARK_METRICS_INVALID") in err
    assert not out.exists()


def test_a_workspace_without_a_functional_swe1_is_refused(tmp_path, capsys):
    bench = tmp_path / "metrics.json"
    bench.write_text(json.dumps(BENCH))
    rc = C.main(["--pilot", str(tmp_path / "empty"), "--benchmark", str(bench), "--out", str(tmp_path / "o")])
    assert rc == 2 and "PILOT_SWE1_MISSING" in capsys.readouterr().err


def test_preserve_flags_a_guarded_metric_that_dropped(tmp_path):
    """D34 (owner: "in the new runs, preserve what is already good compared to the benchmark")."""
    bench = tmp_path / "metrics.json"
    bench.write_text(json.dumps(BENCH))
    ws = _workspace(tmp_path)
    v = ws / ".forge-run/lrtx/SWE.1/phase1"
    v.mkdir(parents=True)
    (v / "verdicts.jsonl").write_text("".join(json.dumps({"tk": f"t|k{n}", "passed": n != 2}) + "\n" for n in range(4)))
    (ws / ".forge-run/lrtx/SWE.1/governance").mkdir(parents=True)
    (ws / ".forge-run/lrtx/SWE.1/governance/status.json").write_text(json.dumps({"state": "COVERAGE_PASS"}))
    assert C.main(["--pilot", str(ws), "--benchmark", str(bench), "--out", str(tmp_path / "base")]) == 0
    base = json.loads((tmp_path / "base/comparison.json").read_text())
    assert base["quality"] == {"iq_first_pass_share": 0.75, "iq_judged": 4, "governance_pass": 1.0}
    # the rerun loses a trace link (traced share 0.75 -> 0.5) and keeps everything else
    p = ws / "workproducts/SWE.1/requirement_attributes.json"
    d = json.loads(p.read_text())
    d["requirements"][0]["links"] = [{"kind": "derive", "input_id": "IN-01", "locator": "p.1", "rationale": "r"}]
    p.write_text(json.dumps(d))
    assert C.main(["--pilot", str(ws), "--benchmark", str(bench), "--out", str(tmp_path / "new"),
                   "--preserve", str(tmp_path / "base/comparison.json")]) == 0
    rep = json.loads((tmp_path / "new/comparison.json").read_text())
    st = {(x["metric"], x["category"]): x["status"] for x in rep["preserve"]}
    assert st[("scope_coverage", "traced_share")] == "REGRESSED"
    assert st[("attribute_completeness", "statement")] == "PRESERVED"
    assert st[("quality", "iq_first_pass_share")] == "PRESERVED"
    assert len(st) == len(C.GUARDED)
    assert "Preserved against the baseline run" in (tmp_path / "new/comparison.md").read_text()


def test_a_missing_baseline_is_refused(tmp_path, capsys):
    bench = tmp_path / "metrics.json"
    bench.write_text(json.dumps(BENCH))
    rc = C.main(["--pilot", str(_workspace(tmp_path)), "--benchmark", str(bench), "--out", str(tmp_path / "o"),
                 "--preserve", str(tmp_path / "nope.json")])
    assert rc == 2 and "BASELINE_COMPARISON_MISSING" in capsys.readouterr().err
