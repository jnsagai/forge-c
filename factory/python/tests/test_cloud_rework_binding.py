"""Failed findings are bound to the immutable M3 order and forwarded without accepting their verdict."""
import hashlib
import json
from types import SimpleNamespace as S

import pytest
from forge_factory.afo import line_cloud as C
from forge_factory.afo import line_orders as LO


def spec():
    return {"wo": "WO-NEW", "stop_after": "SWE.4", "resume_from": "WO-GOOD"}


def context():
    return {"source_work_order": "WO-FAILED", "phase": "SWE.4", "inspection_sha256": "b" * 64,
            "gate_log_sha256": "a" * 64}


def test_optional_binding_preserves_legacy_digest_and_binds_each_context_field():
    old = spec()
    identity = {k: old.get(k) for k in LO.ORDER_KEYS}
    assert LO._digest(old) == LO.sha256_bytes(LO.canonical_json(identity))
    new = {**old, "rework_context": context()}
    sealed = LO._digest(new)
    assert sealed != LO._digest(old)
    for key in context():
        assert LO._digest({**new, "rework_context": {**context(), key: "different"}}) != sealed


def test_exact_three_cli_arguments_carry_bound_findings_not_verdicts():
    assert C.context_arguments(spec()) == []
    assert C.context_arguments({**spec(), "rework_context": context()}) == [
        "--rework-from", "WO-FAILED", "--rework-inspection-sha256", "b" * 64,
        "--rework-gates-sha256", "a" * 64]
    assert "PASS" not in json.dumps(C.context_arguments({**spec(), "rework_context": context()}))


@pytest.mark.parametrize("key,value", [("phase", "SWE.3"), ("gate_log_sha256", "unknown"),
                                        ("source_work_order", "WO-NEW"), ("inspection_sha256", None)])
def test_conflicting_or_unbound_context_is_refused(key, value):
    with pytest.raises(ValueError, match="CLOUD_REWORK_BINDING_INVALID"):
        C.context_arguments({**spec(), "rework_context": {**context(), key: value}})


@pytest.mark.parametrize("inspected", [False, True])
def test_planner_pins_actual_terminal_gate_and_inspection_bytes(tmp_path, inspected):
    ws = tmp_path / "workspace"
    gate = ws / ".forge-run/gates/gate-log.jsonl"
    gate.parent.mkdir(parents=True)
    body = b'{"phase":"SWE.4","step":"route","gate":{"decision":"BLOCKED"}}\n'
    gate.write_bytes(body)
    inspection = ws / "inspection/SWE.4/INS-SWE.4-001.json"
    if inspected:
        inspection.parent.mkdir(parents=True)
        inspection.write_text('{"verdict":"FAIL"}')
    line = S(workspace=lambda wo: ws, ended_run=lambda wo, rid: wo == "WO-FAILED" and rid == "native-exact")
    plan = S(order={**spec(), "phase": "SWE.4"}, current=S(wo="WO-FAILED", phase="SWE.4", rid="native-exact"))
    result = C.failed_context(line, plan)
    assert result == {**context(), "gate_log_sha256": hashlib.sha256(body).hexdigest(),
                      "inspection_sha256": LO.sha256_bytes(inspection.read_bytes()) if inspected else "ABSENT"}
    line.ended_run = lambda *a: False
    with pytest.raises(ValueError, match="NOT_KNOWN_TERMINAL"):
        C.failed_context(line, plan)


def test_rework_reference_cannot_follow_source_symlinks(tmp_path):
    ws = tmp_path / "workspace"
    (ws / ".forge-run/gates").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_text("untrusted foreign data")
    (ws / ".forge-run/gates/gate-log.jsonl").symlink_to(outside)
    line = S(workspace=lambda wo: ws, ended_run=lambda *a: True)
    plan = S(order={**spec(), "phase": "SWE.4"}, current=S(wo="WO-FAILED", phase="SWE.4", rid="known"))
    with pytest.raises(ValueError, match="SOURCE_INVALID"):
        C.failed_context(line, plan)
