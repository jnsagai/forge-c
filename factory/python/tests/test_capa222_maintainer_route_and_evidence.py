"""CAPA-222 (owner 2026-11-10 "go ahead with 1, 2 and 3"): the factory maintainer never ran on a real defect. TIM LL
L43R/L43S failed the same SWE.1 set inspection on a factory-side cause (CAPA-218); both were classed PRODUCT_QUALITY and
went to the recovery planner, never to the maintainer, and the maintainer case carried no run evidence. Now a failure
that matches an open, still-unfixed CAPA published by the CRE observer (supervisor/factory-defect-routes.json, fresh) is
a FACTORY_CODE_DEFECT, and the maintainer case carries a bounded, hash-frozen view of the failed run."""
import inspect
import json
import time

from forge_factory.afo import bundle as B
from forge_factory.afo import line_maintenance as LM
from forge_factory.afo import maintainer as M


def _routes(tmp_path, monkeypatch, routes, age=0):
    sup = tmp_path / "state/supervisor"
    sup.mkdir(parents=True)
    (sup / "factory-defect-routes.json").write_text(json.dumps(
        {"schema": "forge-c/factory-defect-routes/1", "generated_epoch": time.time() - age, "routes": routes}))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))


WS = "/x/workorders/WO-F014-SWE1-TIML-20261107-L43T/workspace"
DOM = {"error_code": "INSPECTION_FAIL:SWE1-05", "failure_class": "PRODUCT_QUALITY"}
CAPA = {"capa_id": "CAPA-223", "hypothesis": "cross-cutting source page"}


def test_a_failure_matching_an_open_routed_capa_goes_to_the_maintainer(tmp_path, monkeypatch):
    _routes(tmp_path, monkeypatch, {"TIML|SWE.1|INSPECTION_FAIL": CAPA})
    assert B.routed_capa(WS, "SWE.1", DOM) == CAPA
    assert B.route_class("PRODUCT_QUALITY", WS, "SWE.1", DOM) == ("FACTORY_CODE_DEFECT", CAPA)
    assert B.route_class("UNKNOWN", WS, "SWE.1", DOM)[0] == "FACTORY_CODE_DEFECT"


def test_other_parts_phases_kinds_classes_and_stale_tables_are_not_routed(tmp_path, monkeypatch):
    _routes(tmp_path, monkeypatch, {"TIML|SWE.1|INSPECTION_FAIL": CAPA}, age=3 * 3600)
    assert B.routed_capa(WS, "SWE.1", DOM) is None  # stale: the observer stopped publishing
    monkeypatch.delenv("FORGE_STATE_DIR")
    _routes(tmp_path / "b", monkeypatch, {"TIML|SWE.1|INSPECTION_FAIL": CAPA})
    assert B.routed_capa(WS.replace("TIML", "SPIL"), "SWE.1", DOM) is None
    assert B.routed_capa(WS, "SWE.2", DOM) is None
    assert B.routed_capa(WS, "SWE.1", {"error_code": "MISSING_REQUIRED_OUTPUT:x.md"}) is None
    for cls in ("INFRASTRUCTURE", "TRANSIENT_DEPENDENCY", "SECURITY", "SPECIFICATION_GAP"):
        assert B.route_class(cls, WS, "SWE.1", DOM) == (cls, None)


def test_without_a_route_table_nothing_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "none"))
    assert B.route_class("PRODUCT_QUALITY", WS, "SWE.1", DOM) == ("PRODUCT_QUALITY", None)


def test_build_applies_the_route():
    src = inspect.getsource(B.build)
    assert "route_class(afo_class(dom, open_capa), ws, phase, dom)" in src


def test_run_evidence_is_bounded_and_names_the_routed_capa(tmp_path, monkeypatch):
    ws = tmp_path / "workorders/WO-F014-SWE1-TIML-20261107-L43T/workspace"
    (ws / "inspection/SWE.1").mkdir(parents=True)
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "inspection/SWE.1/INS-SWE.1-004.json").write_text(json.dumps(
        {"findings": [{"id": "SWE1-05", "severity": "major", "detail": "x" * 5000}] * 30}))
    (ws / ".forge-run/gates/gate-log.jsonl").write_text("\n".join(json.dumps(
        {"phase": "SWE.1", "step": "inspect", "gate": {"decision": "REWORK", "reason": "r" * 900}}) for _ in range(90)))
    (ws / "workproducts/SWE.1/software_requirements.md").write_text("req")
    _routes(tmp_path, monkeypatch, {"TIML|SWE.1|INSPECTION_FAIL": CAPA})
    ev = B.run_evidence(ws, "SWE.1", DOM)
    assert ev["schema"] == "forge-c/maintainer-run-evidence/1" and ev["routed_capa"] == CAPA
    assert len(ev["set_inspection_findings"]) <= 12 and all(len(f["detail"]) <= 800 for f in ev["set_inspection_findings"])
    assert len(ev["gate_tail"]) <= 40 and ev["workproducts"][0]["path"] == "workproducts/SWE.1/software_requirements.md"
    assert len(json.dumps(ev).encode()) <= 24576


def test_the_maintainer_case_and_its_read_tool_carry_the_evidence():
    assert "run_evidence" in inspect.signature(M.prepare).parameters
    assert "run_evidence=" in inspect.getsource(LM.prepare)
    from forge_factory.mcp.servers import maintainer as S

    src = inspect.getsource(S.read_case)
    assert "run_evidence" in src and "RUN_EVIDENCE_CHANGED" in src
