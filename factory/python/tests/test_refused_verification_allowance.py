"""Unexecuted preflight refusals preserve repair capacity, never refund executed or uncertain work."""
import json

import pytest
from forge_factory import development_execution as D
from forge_factory.lrtx import tools
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import tests as T


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({
        "work_order": "WO-REFUSED", "purpose": "ASPICE_ONLY",
        "development_execution": D.binding(D.NAME, "ASPICE_ONLY")}))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")
    monkeypatch.setenv("FORGE_ROLE", "swe4-author")
    monkeypatch.setenv("FORGE_PHASE", "SWE.4")
    monkeypatch.setenv("FORGE_WORKSPACE", str(ws))
    return ws


def call(ws, route):
    if route == "native":
        op = next(o for o in T.OPERATIONS if o.name == "run_unit")
        return sdk.invoke("forge-tests-mcp", op, {"coverage": False})
    return tools.call(ws, "forge-tests-mcp", "run_unit", {"coverage": False}, "swe4-author", "SWE.4")


@pytest.mark.parametrize("route", ["native", "structured"])
def test_refusals_are_journaled_but_first_real_execution_can_still_run(workspace, route):
    ws = workspace
    for _ in range(3):
        out = call(ws, route)
        assert out["status"] == "BLOCKED" and out["metrics"]["verification_executed"] is False
    assert not (ws / "build/tests-unit").exists()
    with D.phase_state(ws, "SWE.4") as state:
        assert not state.get("failed_checks") and state["repair_pass"] is None
    p = ws / "software/tests/unit/test_real.c"
    p.parent.mkdir(parents=True)
    p.write_text('#include <stdio.h>\nint main(void) { volatile int x = 2; '
                 'if (x + 3 != 5) { return 1; } puts("UT-001 PASS"); return 0; }\n')
    out = call(ws, route)
    assert out["status"] == "PASS" and out["metrics"]["executables"] == 1
    records = [json.loads(l) for l in (ws / "evidence/tool-results.jsonl").read_text().splitlines()]
    assert [r["result"]["status"] for r in records] == ["BLOCKED", "BLOCKED", "BLOCKED", "PASS"]


@pytest.mark.parametrize("route", ["native", "structured"])
def test_actual_compile_failures_still_exhaust_the_same_finite_allowance(workspace, route):
    p = workspace / "software/tests/unit/test_broken.c"
    p.parent.mkdir(parents=True)
    p.write_text('this is not valid C;\n')
    assert call(workspace, route)["status"] == "FAIL"
    assert call(workspace, route)["status"] == "FAIL"
    out = call(workspace, route)
    assert out["status"] == "BLOCKED" and "DEVELOPMENT_PHASE_REPAIR_EXHAUSTED" in out["summary"]


@pytest.mark.parametrize("route", ["native", "structured"])
@pytest.mark.parametrize("status,metrics", [
    ("BLOCKED", {}), ("FAIL", {"verification_executed": False}), ("UNAVAILABLE", {}),
    ("BLOCKED", {"verification_executed": 0})])
def test_missing_or_contradictory_provenance_does_not_refund(workspace, monkeypatch, route, status, metrics):
    op = next(o for o in T.OPERATIONS if o.name == "run_unit")
    monkeypatch.setattr(op, "handler", lambda ctx, a: sdk.result(ctx, status, "control", metrics=metrics))
    for _ in range(2):
        assert call(workspace, route)["status"] == status
    assert call(workspace, route)["status"] == "BLOCKED"
    with D.phase_state(workspace, "SWE.4") as state:
        assert state["failed_checks"]["forge-tests-mcp.run_unit"] == 2


@pytest.mark.parametrize("route", ["native", "structured"])
def test_uncertain_handler_exception_remains_charged(workspace, monkeypatch, route):
    op = next(o for o in T.OPERATIONS if o.name == "run_unit")
    def fail(ctx, a):
        raise RuntimeError("uncertain execution")
    monkeypatch.setattr(op, "handler", fail)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="uncertain execution"):
            call(workspace, route)
    assert call(workspace, route)["status"] == "BLOCKED"


def test_structured_refusal_still_uses_the_cumulative_mission_tool_debit(workspace, monkeypatch):
    from forge_factory.afo import tool_accounting
    charges = []
    def charge(ws, event):
        charges.append(event)
        return {"mission_id": "existing-mission", "job_id": "existing-job", "event_id": event}
    monkeypatch.setattr(tool_accounting, "charge", charge)
    for _ in range(3):
        assert call(workspace, "structured")["status"] == "BLOCKED"
    records = [json.loads(l) for l in (workspace / "evidence/tool-results.jsonl").read_text().splitlines()]
    assert len(charges) == len(set(charges)) == 3
    assert [r["mission_tool_charge"]["event_id"] for r in records] == charges


@pytest.mark.parametrize("route", ["native", "structured"])
def test_preflight_keeps_previous_failures_and_does_not_claim_a_post_repair_execution(workspace, route):
    with D.phase_state(workspace, "SWE.4") as state:
        state["failed_checks"] = {"forge-tests-mcp.run_unit": 1}
        state["repair_mutation_started"] = True
    assert call(workspace, route)["status"] == "BLOCKED"
    with D.phase_state(workspace, "SWE.4") as state:
        assert state["failed_checks"] == {"forge-tests-mcp.run_unit": 1}
        assert not state.get("verification_after_repair")


@pytest.mark.parametrize("route", ["native", "structured"])
def test_missing_pinned_gtest_toolchain_is_an_unexecuted_preflight(workspace, monkeypatch, route):
    from forge_factory import gtest_toolchain
    p = workspace / "software/tests/unit/test_cpp.cpp"
    p.parent.mkdir(parents=True)
    p.write_text('#include <gtest/gtest.h>\nTEST(Unit, UT_001) { EXPECT_EQ(1, 1); }\n')
    def unavailable():
        raise gtest_toolchain.GtestToolchainError("pinned fixture toolchain unavailable")
    monkeypatch.setattr(gtest_toolchain, "load", unavailable)
    for _ in range(3):
        out = call(workspace, route)
        assert out["status"] == "BLOCKED" and out["metrics"]["verification_executed"] is False
    with D.phase_state(workspace, "SWE.4") as state:
        assert not state.get("failed_checks")
