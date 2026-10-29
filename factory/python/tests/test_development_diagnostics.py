"""Positive independent executable recheck; all semantic verdicts are named fixtures.

The frozen ST code and independently expected host tests are unchanged. Only a
design workproduct gains an unresolved fixture finding. Real tool execution,
hashes, existing gates, ledger, reservation and blocked packaging are exercised.
"""
import json
import shutil
import time
from types import SimpleNamespace

import pytest
from forge_factory import development_diagnostics as F
from forge_factory import development_execution as D
from forge_factory import provided_requirements as P
from forge_factory import workorder as W
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store as Queue
from forge_factory.brownfield.inject import inject
from forge_factory.common import sha256_file
from forge_factory.inspection import gate
from forge_factory.lrtx import tools
from forge_factory.release import finalize
from incremental_idr_anchor import Anchor
from test_incremental_delivery import EX
from test_simulation_performance import TEST


@pytest.fixture(scope="module")
def accepted_cache(tmp_path_factory):
    """Run real six-phase tools once, then clone the immutable accepted fixture for negative controls."""
    root = tmp_path_factory.mktemp("accepted-diagnostic-inputs")
    with pytest.MonkeyPatch.context() as mp:
        for key in ("STATE", "EVENTS", "ARCHIVE"):
            mp.setenv("FORGE_" + key + "_DIR", str(root / key))
        ws, man = W.prepare(EX.parent / "0014e-st-cube-crc-idr-simulation", "WO-DIAGNOSTIC-IDR-FIXTURE",
                          purpose="ASPICE_ONLY")
        document, _ = P.validate(ws)
        assert document["review"]["payload_sha256"] == "af48340bdc64510347f2aa236114b601f86ad24a0fbd062e82f07e4eed770463"
        assert any(d["id"] == "OD-2026-10-25-01" for d in man["owner_dispositions"])
        anchor = Anchor(ws, mp)
        assert P.materialize(ws)["status"] == "PASS"  # Actual reviewed nine-requirement payload.
        anchor.finish("SWE.1")  # Explicit inspector-verdict fixture, not external acceptance or Qwen.
        assert inject(ws)["status"] == "INJECTED"
        anchor.architecture()
        anchor.implementation()
        anchor.unit()
        anchor.write("SWE.5", {"software/tests/target/test_performance.c": TEST})
        anchor.integration()
        anchor.validation()
        assert finalize.finalize(ws, "accepted-input-fixture")["package_status"] == "READY_FOR_OFFLINE_REVIEW"
    return root


@pytest.fixture
def ready(accepted_cache, tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)
    for key in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + key + "_DIR", str(tmp_path / key))
    shutil.copytree(accepted_cache / "STATE/workorders", tmp_path / "STATE/workorders")
    ws = tmp_path / "STATE/workorders/WO-DIAGNOSTIC-IDR-FIXTURE/workspace"
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    from forge_factory.inspection.engine import Store
    anchor = SimpleNamespace(store=Store(ws))
    store = anchor.store
    design = ws / "workproducts/SWE.3/detailed_design.md"
    design.write_text(design.read_text() + "\nUnresolved design-document fixture finding.\n")
    assert gate.step_author(store, "SWE.3", json.dumps(
        {"status": "PASS", "artifacts": [], "issues": [], "next_action": "next"})) == 0
    baseline = store.latest_baseline("SWE.3")
    checks = store.applicable(store.checklist("SWE.3"))["checks"]
    verdicts = {c["id"]: {"verdict": "PASS", "evidence_refs": [str(design.relative_to(ws))]} for c in checks}
    item = next(c for c in checks if c.get("required") and not c.get("deterministic_check"))["id"]
    verdicts[item] = {"verdict": "FAIL", "evidence_refs": [str(design.relative_to(ws))],
                      "findings": ["Explicit unresolved design-document fixture; no inspection acceptance."]}
    for _ in range(2):
        assert store.record_inspection("SWE.3", "swe3-inspector", baseline["baseline_id"], verdicts)["verdict"] == "FAIL"
    assert gate.step_route(store, "SWE.3") == 1  # Real unchanged-failure stop; no fabricated budget exhaustion.
    queue = Queue()
    ledger = MissionLedger(queue)
    ledger.register("diagnostic-fixture", "fixture:accepted-idr", dict(max_attempts=3, max_jobs=1,
                    max_requests=5, max_tokens=1000, max_tools=1, max_corrections=1,
                    deadline=time.time() + 600), "AUTH-FIXTURE-NOT-LIVE", authorize=lambda *a: True)
    ledger.execution("diagnostic-fixture", "native-fixture", "PRODUCT", reserved_tokens=100)
    execution = Executions(queue)
    execution.reserve("native-fixture", "diagnostic-fixture", "a" * 32)
    execution.dispatch_intent("native-fixture")
    execution.adopt("native-fixture", ["synthetic-native-identity"])
    (ws / ".forge-run/durable-binding.json").write_text(json.dumps(
        {"mission_id": "diagnostic-fixture", "job_id": "native-fixture"}))
    return SimpleNamespace(ws=ws, store=store, man=man, ledger=ledger, execution=execution)


def test_real_independent_unit_recheck_does_not_accept_the_failed_product(ready):
    m = ready
    original = m.store.inspections("SWE.3")[-1]
    header = m.ws / "software/ll/stm32n6xx_ll_crc.h"
    before = sha256_file(header)
    counts = {p: len(m.store.baselines(p)) for p in ("SWE.3", "SWE.4")}
    result = F.recheck(m.store)
    assert result["status"] == "PROVISIONAL_RECHECK_RECORDED" and result["tool_result"]["status"] == "PASS"
    assert result["independent_inputs_unchanged"] and result["acceptance_effect"] == "NONE"
    assert m.ledger.snapshot("diagnostic-fixture")["tools"] == 1
    assert m.store.inspections("SWE.3")[-1] == original and m.store.gate("SWE.3")["decision"] != "PASS"
    assert m.store.gate("SWE.4")["decision"] != "PASS"  # Its historical acceptance remains stale.
    assert {p: len(m.store.baselines(p)) for p in counts} == counts
    assert sha256_file(header) == before
    assert F.recheck(m.store)["status"] == "ALREADY_RESERVED"
    assert m.ledger.snapshot("diagnostic-fixture")["tools"] == 1
    package = finalize.finalize(m.ws, "provisional-independent-recheck-fixture")
    assert package["package_status"] == "BLOCKED"
    assert len(finalize.advisory_register(m.ws)) == 2
    assert m.execution.get("native-fixture")["resource_lease"] == "HELD"


@pytest.mark.parametrize("change", ["test", "unit_oracle", "code", "primary", "integrity", "terminal", "binding", "author_contract"])
def test_unknown_changed_or_unavailable_independent_inputs_block_before_execution(ready, change):
    m = ready
    paths = {"test": m.ws / "software/tests/unit/test_crc.c",
             "unit_oracle": m.ws / F.UNITS,
             "code": m.ws / "software/ll/stm32n6xx_ll_crc.h",
             "primary": m.ws / m.man["inputs"][0]["path"]}
    if change in paths:
        p = paths[change]
        p.chmod(0o644)
        p.write_text(p.read_text() + "\n/* changed fixture input */\n")
    elif change == "integrity":
        p = m.ws / "evidence/test-integrity.jsonl"
        records = [json.loads(line) for line in p.read_text().splitlines()]
        next(r for r in reversed(records) if r["op"] == "run_unit")["status"] = "FAIL"
        p.write_text("".join(json.dumps(r) + "\n" for r in records))
    elif change == "author_contract":
        p = m.ws / ".forge-run/gates/gate-log.jsonl"
        records = [json.loads(line) for line in p.read_text().splitlines()]
        next(r for r in reversed(records) if r.get("step") == "author")["finding"] = "AGENT_OUTPUT_CONTRACT_VIOLATION"
        p.write_text("".join(json.dumps(r) + "\n" for r in records))
    elif change == "terminal":
        m.execution.outcome("native-fixture", "BLOCKED", "synthetic terminal task; native not quiescent")
    else:
        (m.ws / ".forge-run/durable-binding.json").unlink()
    result = F.recheck(m.store)
    assert result["status"] == "NOT_ELIGIBLE"
    assert m.ledger.snapshot("diagnostic-fixture")["tools"] == 0
    assert m.store.gate("SWE.3")["decision"] != "PASS"
    assert not (m.ws / ".forge-run/lrtx/SWE.3/independent-unit-recheck.json").exists()
    assert m.execution.get("native-fixture")["resource_lease"] == "HELD"


def test_crash_keeps_the_intent_charge_and_unknown_completion_without_retry(ready, monkeypatch):
    from forge_factory.mcp.servers import tests

    m = ready
    op = next(o for o in tests.OPERATIONS if o.name == "run_unit")
    def crash(*a):
        raise RuntimeError("explicit diagnostic handler crash fixture")
    monkeypatch.setattr(op, "handler", crash)
    with pytest.raises(RuntimeError, match="diagnostic handler crash"):
        F.recheck(m.store)
    assert F.recheck(m.store)["status"] == "ALREADY_RESERVED"
    assert m.ledger.snapshot("diagnostic-fixture")["tools"] == 1
    assert finalize.advisory_register(m.ws)[-1]["status"] == "RESERVED_UNKNOWN_COMPLETION"


def test_exhausted_shared_allowance_is_a_blocked_recheck_without_lease_release(ready):
    m = ready
    m.ledger.count("diagnostic-fixture", "native-fixture", "TOOL", "already-spent")
    result = F.recheck(m.store)
    assert result["tool_result"]["status"] == "BLOCKED"
    assert result["tool_result"]["metrics"]["handler_executed"] is False
    assert m.ledger.snapshot("diagnostic-fixture")["tools"] == 1
    assert m.execution.get("native-fixture")["resource_lease"] == "HELD"


def test_inputs_changed_during_execution_disqualify_provisional_result(ready, monkeypatch):
    m = ready
    actual = tools.call
    def changed(*args, **kwargs):
        result = actual(*args, **kwargs)
        p = m.ws / "software/tests/unit/test_crc.c"
        p.write_text(p.read_text() + "\n/* changed during recheck fixture */\n")
        return result
    monkeypatch.setattr(tools, "call", changed)
    result = F.recheck(m.store)
    assert result["tool_result"]["status"] == "PASS"
    assert result["status"] == "INPUT_CHANGED_DURING_RECHECK" and not result["independent_inputs_unchanged"]
    assert m.store.gate("SWE.4")["decision"] != "PASS"


def test_only_high_development_policy_wires_bounded_diagnostic_work():
    from forge_factory.workflow.builder import build

    high, _ = build("WO-FIXTURE", layer="LL", execution_policy=D.binding(D.HIGH, "ASPICE_ONLY"))
    legacy, _ = build("WO-FIXTURE", layer="LL", execution_policy=D.binding(D.NAME, "ASPICE_ONLY"))
    assert "swe3_route -> swe3_independent_unit_recheck" in high
    assert "swe3_independent_unit_recheck -> upstream_swe1" in high
    assert 'timeout="1000s"' in high and "swe3_independent_unit_recheck" not in legacy


def test_lost_result_receipt_recovers_observation_without_reexecuting(ready, monkeypatch):
    m = ready
    actual = F.immutable_json
    def lost(path, document):
        if path.name.endswith("-result.json"):
            raise OSError("synthetic lost result receipt after actual tool execution")
        return actual(path, document)
    monkeypatch.setattr(F, "immutable_json", lost)
    with pytest.raises(OSError, match="lost result receipt"):
        F.recheck(m.store)
    monkeypatch.setattr(F, "immutable_json", actual)
    result = F.recheck(m.store)
    assert result["status"] == "ALREADY_RESERVED"
    assert result["completion_status"] == "TOOL_RESULT_RECOVERED_INPUT_CONTINUITY_UNPROVEN"
    assert m.ledger.snapshot("diagnostic-fixture")["tools"] == 1
    assert F.recheck(m.store)["completion_status"] == result["completion_status"]
    assert m.store.gate("SWE.3")["decision"] != "PASS"


def test_short_remaining_mission_window_refuses_before_reserving_work(ready, monkeypatch):
    m = ready
    deadline = m.ledger.snapshot("diagnostic-fixture")["limits"]["deadline"]
    monkeypatch.setattr(F.time, "time", lambda: deadline - 5)
    result = F.recheck(m.store)
    assert result["status"] == "NOT_ELIGIBLE" and result["reason"] == "DIAGNOSTIC_VERIFICATION_WINDOW_TOO_SMALL"
    assert m.ledger.snapshot("diagnostic-fixture")["tools"] == 0


@pytest.mark.parametrize("mode", ["PAUSED", "DRAINING", "STOPPED"])
def test_operator_intent_prevents_new_diagnostic_activity(ready, monkeypatch, mode):
    from forge_factory.afo.operations import Intent

    m = ready
    folder = m.ws.parent / "private-operator-fixture"
    folder.mkdir(mode=0o700)
    path = folder / "intent.json"
    Intent(path).set(mode, actor="SyntheticFixtureOperator", reason="private deterministic test", initialize=True)
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(path))
    result = F.recheck(m.store)
    assert result["reason"] == "DIAGNOSTIC_OPERATOR_INTENT_NOT_RUNNING"
    assert m.ledger.snapshot("diagnostic-fixture")["tools"] == 0


def test_newer_operator_stop_during_proof_fences_tool_dispatch(ready, monkeypatch):
    from forge_factory.afo.operations import Intent

    m = ready
    folder = m.ws.parent / "private-operator-fixture"
    folder.mkdir(mode=0o700)
    path = folder / "intent.json"
    intent = Intent(path)
    intent.set("RUNNING", actor="SyntheticFixtureOperator", reason="private test", initialize=True)
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(path))
    actual = F.proof
    def stopped(store):
        result = actual(store)
        intent.set("STOPPED", actor="SyntheticFixtureOperator", reason="concurrent stop fixture")
        return result
    monkeypatch.setattr(F, "proof", stopped)
    result = F.recheck(m.store)
    assert result["status"] == "OPERATOR_INTENT_CHANGED_BEFORE_RECHECK" and not result["handler_executed"]
    assert m.ledger.snapshot("diagnostic-fixture")["tools"] == 0
    assert F.recheck(m.store)["completion_status"] == result["status"]


def test_reviewed_example_reuses_only_the_existing_exact_header_naming_approval(ready):
    from forge_factory.inspection.defects import owner_dispositions

    m = ready
    decision = next(d for d in owner_dispositions(m.ws) if d["id"] == "OD-2026-10-25-01")
    assert decision["approved_by"] == "Jefferson Nascimento" and decision["approved_at"] == "2026-10-25"
    assert "All 5 LL headers" in decision["reference"]
    assert W.owner_dispositions_for("simulation-performance") == []
