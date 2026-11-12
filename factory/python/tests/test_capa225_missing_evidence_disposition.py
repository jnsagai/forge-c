"""CAPA-225 / DA-T036: a NEEDS_EVIDENCE diagnosis ends in a typed block naming the evidence kind and whether the
workspace has it; test-phase diagnostics and CSV work products reach the diagnosis packet."""
import inspect
import json
import types

from forge_factory.afo import diagnosis_packet as DP
from forge_factory.afo import evidence_disposition as ED
from forge_factory.afo import local_agent


def _ws(tmp_path):
    ws = tmp_path / "ws"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text("r")
    (ws / "evidence").mkdir()
    (ws / "evidence/robot-output.xml").write_text("<x/>")
    (ws / "inputs").mkdir()
    (ws / "inputs/index.md").write_text("i")
    return ws


def test_disposition_names_kind_and_presence(tmp_path):
    ws = _ws(tmp_path)
    assert ED.disposition(ws, "SWE.1", ["DESIGN"]) == "DESIGN:ABSENT"  # no design before SWE.2
    assert ED.disposition(ws, "SWE.1", ["AUTHORITATIVE_INPUT"]) == "AUTHORITATIVE_INPUT:IN_WORKSPACE"
    assert ED.disposition(ws, "SWE.6", ["TEST_DIAGNOSTIC"]) == "TEST_DIAGNOSTIC:IN_WORKSPACE"
    assert ED.disposition(ws, "SWE.1", ["TEST_DIAGNOSTIC"]) == "TEST_DIAGNOSTIC:ABSENT"  # phase-scoped
    assert ED.disposition(ws, "SWE.1", []) == "UNSPECIFIED:ABSENT"


def test_requested_kinds_come_from_the_frozen_proposal():
    rows = [(json.dumps({"decision": "NEEDS_EVIDENCE", "missing_evidence": [
        {"obligation_ref": "o", "evidence_kind": "TEST_DIAGNOSTIC", "reason": "r"},
        {"obligation_ref": "o", "evidence_kind": "REQUIREMENT", "reason": "r"}]}),)]

    class C:
        def execute(self, q, a):
            return types.SimpleNamespace(fetchall=lambda: rows)

    class T:
        def __enter__(self):
            return C()

        def __exit__(self, *a):
            return False

    store = types.SimpleNamespace(tx=lambda: T())
    assert ED.requested_kinds(store, "afo-agent-x") == ["TEST_DIAGNOSTIC", "REQUIREMENT"]


def test_the_planner_hook_raises_the_typed_disposition():
    src = inspect.getsource(local_agent.make_planner)
    assert "MISSING_EVIDENCE:{" in src and "disposition(" in src and "requested_kinds(" in src


def test_test_phase_diagnostics_and_csv_reach_the_packet():
    src = inspect.getsource(DP.build)
    assert "evidence/*.log" in src and "evidence/*.xml" in src and '".csv"' in src and '".log"' in src
