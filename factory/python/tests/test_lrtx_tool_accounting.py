"""Real compiled structured tools share the native hook's existing mission cap.

All mission authority and source inputs below are explicit synthetic fixtures.
No model, grant signing, deployment or native inference release is performed.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from forge_factory.afo import tool_accounting
from forge_factory.afo.durable import Refused
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from forge_factory.lrtx import tools as T
from forge_factory.mcp.servers import tests as operations
from forge_factory.policy.authz import Binding
from forge_factory.policy.fabro_hook import handle


@pytest.fixture
def mission(tmp_path, monkeypatch):
    for key in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + key + "_DIR", str(tmp_path / key))
    ws = tmp_path / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-TOOL-ACCOUNTING", "layer": "LL"}))
    test = ws / "software/tests/unit/test_counter.c"
    test.parent.mkdir(parents=True)
    source = ws / "software/src/counter.c"
    source.parent.mkdir(parents=True)
    source.write_text("int counter_read(void) { return 7; }\n")
    test.write_text('#include <stdio.h>\nint counter_read(void);\n'
                    'int main(void) { if (counter_read() != 7) { puts("UT-001 FAIL"); return 1; } '
                    'puts("UT-001 PASS"); return 0; }\n')
    store = Store()
    ledger = MissionLedger(store)
    ledger.register("mission", "fixture:counter", dict(max_attempts=3, max_jobs=2, max_requests=9,
                    max_tokens=1000, max_tools=2, max_corrections=1, deadline=time.time() + 600),
                    "AUTH-SYNTHETIC-NOT-LIVE", authorize=lambda *a: True)
    ledger.execution("mission", "native-job", "PRODUCT", reserved_tokens=100)
    binding_path = ws / ".forge-run/durable-binding.json"
    binding_path.write_text(json.dumps({"mission_id": "mission", "job_id": "native-job"}))
    binding = Binding("tool-fixture", str(ws), {"swe4_author": {"role": "swe4-author", "phase": "SWE.4"}})
    return SimpleNamespace(ws=ws, ledger=ledger, store=store, path=binding_path, binding=binding)


def run(m):
    return T.call(m.ws, "forge-tests-mcp", "run_unit", {}, "swe4-author", "SWE.4")


def hook(m, event_id="native-tool-1"):
    return handle({"event": "pre_tool_use", "run_id": "WO-TOOL-ACCOUNTING", "node_id": "swe4_author",
                   "tool_name": "mcp__forge_tests_mcp__run_unit", "tool_input": {}, "tool_call_id": event_id}, m.binding)


def test_native_and_actual_structured_unit_tool_share_one_cumulative_allowance(mission):
    m = mission
    executions = Executions(m.store)
    executions.reserve("native-job", "mission", "a" * 32)
    assert hook(m).allow
    assert run(m)["status"] == "PASS"  # Real compiler and host executable; not a tool-result substitution.
    assert m.ledger.snapshot("mission")["tools"] == 2
    record = json.loads((m.ws / "evidence/tool-results.jsonl").read_text().splitlines()[-1])
    charge = record["mission_tool_charge"]
    assert charge["mission_id"] == "mission" and charge["job_id"] == "native-job"
    with m.store.tx() as c:
        row = c.execute("SELECT * FROM afo_mission_counters WHERE event_id=?", (charge["event_id"],)).fetchone()
        assert row["job_id"] == "native-job" and row["kind"] == "TOOL"
    assert hook(m).allow  # Same hook invocation is an idempotent debit, never another allowance.
    assert not hook(m, "native-tool-2").allow
    executions.dispatch_intent("native-job")
    executions.adopt("native-job", ["synthetic-native-identity"])
    executions.outcome("native-job", "BLOCKED", "synthetic terminal task with native work unresolved")
    denied = run(m)
    assert denied["status"] == "BLOCKED" and denied["issues"] == ["MISSION_MAX_TOOLS_EXHAUSTED"]
    assert denied["metrics"]["handler_executed"] is False
    assert m.ledger.snapshot("mission")["tools"] == 2
    assert executions.get("native-job")["resource_lease"] == "HELD"


def test_handler_failure_is_charged_before_execution_and_restart_does_not_refund(mission, monkeypatch):
    m = mission
    op = next(o for o in operations.OPERATIONS if o.name == "run_unit")
    actual = op.handler

    def crash(ctx, args):
        assert m.ledger.snapshot("mission")["tools"] == 1
        raise RuntimeError("synthetic handler crash")

    monkeypatch.setattr(op, "handler", crash)
    with pytest.raises(RuntimeError, match="synthetic handler crash"):
        run(m)
    assert m.ledger.snapshot("mission")["tools"] == 1
    monkeypatch.setattr(op, "handler", actual)
    assert run(m)["status"] == "PASS"
    assert MissionLedger(Store()).snapshot("mission")["tools"] == 2
    denied = run(m)
    assert denied["status"] == "BLOCKED" and denied["issues"] == ["MISSION_MAX_TOOLS_EXHAUSTED"]
    assert denied["metrics"]["handler_executed"] is False
    assert m.ledger.snapshot("mission")["charged_tokens"] == 100


def test_concurrent_hook_and_structured_debits_cannot_both_take_the_last_slot(mission):
    m = mission
    tool_accounting.charge(m.ws, "already-spent")
    def attempt(kind):
        if kind == "hook":
            return hook(m).allow
        return run(m)["status"] == "PASS"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, ["hook", "structured"]))
    assert sum(outcomes) == 1 and m.ledger.snapshot("mission")["tools"] == 2


@pytest.mark.parametrize("raw,code", [
    ('[]', "TOOL_MISSION_BINDING_INVALID"),
    ('{"mission_id":"mission"}', "TOOL_MISSION_BINDING_INVALID"),
    ('{"mission_id":"mission","mission_id":"different","job_id":"native-job"}', "DUPLICATE_JSON_KEY"),
    ('{', "INVALID_JSON"),
])
def test_invalid_durable_binding_refuses_both_paths_without_handler_or_debit(mission, raw, code):
    m = mission
    m.path.write_text(raw)
    assert not hook(m).allow
    denied = run(m)
    assert denied["status"] == "BLOCKED" and denied["issues"] == [code]
    assert m.ledger.snapshot("mission")["tools"] == 0 and not (m.ws / "build").exists()


def test_dangling_binding_symlink_is_not_a_legacy_workspace(mission):
    m = mission
    m.path.unlink()
    m.path.symlink_to(m.ws / "missing-binding")
    with pytest.raises(Refused, match="TOOL_MISSION_BINDING_UNSAFE"):
        tool_accounting.charge(m.ws, "event")
    assert not hook(m).allow
    assert run(m)["issues"] == ["TOOL_MISSION_BINDING_UNSAFE"]
    assert m.ledger.snapshot("mission")["tools"] == 0


def test_legacy_workspace_and_ungranted_operation_keep_their_existing_behavior(mission):
    m = mission
    with pytest.raises(T.ToolRefused, match="ROLE_NOT_GRANTED"):
        T.call(m.ws, "forge-tests-mcp", "run_unit", {}, "swe1-author", "SWE.1")
    assert m.ledger.snapshot("mission")["tools"] == 0
    m.path.unlink()
    assert run(m)["status"] == "PASS"
    assert "mission_tool_charge" not in json.loads((m.ws / "evidence/tool-results.jsonl").read_text().splitlines()[-1])
    assert m.ledger.snapshot("mission")["tools"] == 0


def test_real_failing_driver_and_subsequent_repair_both_consume_the_same_cap(mission):
    m = mission
    source = m.ws / "software/src/counter.c"
    source.write_text("int counter_read(void) { return 8; }\n")  # Explicit prototype mutant, not production.
    failed = run(m)
    assert failed["status"] == "FAIL" and any("TEST_FAIL:" in issue for issue in failed["issues"])
    source.write_text("int counter_read(void) { return 7; }\n")
    assert run(m)["status"] == "PASS"
    records = [json.loads(line) for line in (m.ws / "evidence/tool-results.jsonl").read_text().splitlines()]
    assert [r["result"]["status"] for r in records] == ["FAIL", "PASS"]
    assert len({r["mission_tool_charge"]["event_id"] for r in records}) == 2
    denied = run(m)
    assert denied["status"] == "BLOCKED" and denied["issues"] == ["MISSION_MAX_TOOLS_EXHAUSTED"]
    assert denied["metrics"]["handler_executed"] is False
    assert m.ledger.snapshot("mission")["tools"] == 2


def test_structured_tools_share_native_development_verification_limits(mission, monkeypatch):
    from forge_factory import development_execution as D
    from forge_factory.common import pretty_json
    from forge_factory.mcp import sdk
    from forge_factory.release import aspice

    m = mission
    # Explicit development-policy fixture, not a deployment or product judgment.
    doc = {"work_order": "WO-TOOL-ACCOUNTING", "purpose": "ASPICE_ONLY", "layer": "LL",
           "aspice_development": aspice.binding()}
    doc["development_execution"] = D.binding(D.NAME, "ASPICE_ONLY")
    (m.ws / ".forge-run/manifest.json").write_text(pretty_json(doc))
    m.path.unlink()  # Exercise the separate legacy per-phase limit, without a shared mission cap.
    source = m.ws / "software/src/counter.c"
    source.write_text("int counter_read(void) { return 8; }\n")
    assert run(m)["status"] == "FAIL"
    # The native SDK uses this same verification state; switching callers cannot refill it.
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")  # SDK test authorization fixture, never a production profile.
    monkeypatch.setenv("FORGE_ROLE", "swe4-author")
    monkeypatch.setenv("FORGE_PHASE", "SWE.4")
    monkeypatch.setenv("FORGE_WORKSPACE", str(m.ws))
    op = next(o for o in operations.OPERATIONS if o.name == "run_unit")
    assert sdk.invoke("forge-tests-mcp", op, {})["status"] == "FAIL"
    before = (m.ws / "build/tests-unit/results.json").read_bytes()
    denied = run(m)
    assert denied["status"] == "BLOCKED" and denied["issues"] == ["DEVELOPMENT_PHASE_REPAIR_EXHAUSTED"]
    assert denied["metrics"]["handler_executed"] is False
    assert (m.ws / "build/tests-unit/results.json").read_bytes() == before
    assert m.ledger.snapshot("mission")["tools"] == 0
