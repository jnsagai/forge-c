"""Finite deterministic preflight/control-flow tests. Native engine checks are separate."""

import json
from types import SimpleNamespace

import pytest
from forge_factory.afo.durable import digest
from forge_factory.lrtx import swe1_semantic as S
from forge_factory.safec_bridge import client as CL
from forge_factory.safec_bridge import contracts as C


@pytest.fixture
def ctx(tmp_path):
    domain = {"registers": [{"register_id": "TST_CR", "fields": [{"field_id": "LATCH", "fact_id": "SOURCE-LATCH"}]}]}
    value = SimpleNamespace(
        domain=domain,
        domain_raw=C.canonical_bytes(domain),
        ws=tmp_path,
        limits=CL.Limits(),
        calls=[],
        pin=SimpleNamespace(expected=lambda: {"semantic_profile": "register-io-0.1"}),
    )

    def validate(intents, tag):
        value.calls.append((intents, tag, value.limits))
        assert intents[0]["source_fact_ids"] == ["SOURCE-LATCH"]
        state = getattr(value, "status", "PASS")
        if state == "FAULT":
            raise S.EngineFault("SYNTHETIC_ENGINE_UNREACHABLE")
        return SimpleNamespace(status=state, admissible=state == "PASS", result={"findings": []}), {}, tmp_path / tag

    value.validate = validate
    return value


REQUIRED = [{"register": "TST_CR", "field": "LATCH", "action": "set_field"}]


@pytest.mark.parametrize(
    "state,expected",
    [
        ("PASS", "PASS_REQUIRED_FORMS_ONLY"),
        ("UNSUPPORTED", "CAPABILITY_LIMIT"),
        ("FAIL", "REQUIRED_OPERATION_INVALID"),
        ("FAULT", "ENGINE_FAULT"),
    ],
)
def test_typed_scoped_outcomes_restore_limits_without_model_calls(ctx, state, expected):
    ctx.status = state
    old = ctx.limits
    out = S.preflight_required(ctx, REQUIRED)
    assert out["status"] == expected and out["model_calls"] == 0
    assert out["expected_operations"] == 1 and ctx.limits is old
    assert out["configuration_sha256"] == digest(REQUIRED)
    assert len(ctx.calls) == 1
    assert ctx.calls[0][2].timeout_s <= 60


@pytest.mark.parametrize("bound", [True, 0, -1, float("nan"), float("inf"), 61])
def test_invalid_resource_bounds_never_invoke_engine(ctx, bound):
    with pytest.raises(S.EngineFault, match="CONFIGURATION_INVALID"):
        S.preflight_required(ctx, REQUIRED, maximum_seconds=bound)
    assert ctx.calls == []


@pytest.mark.parametrize("required", [None, [], REQUIRED * 33])
def test_finite_declared_scope_required(ctx, required):
    with pytest.raises(S.EngineFault, match="CONFIGURATION_INVALID"):
        S.preflight_required(ctx, required)
    assert ctx.calls == []


def test_partial_preflight_deadline_is_unknown_and_no_more_engine_calls(ctx, monkeypatch):
    ticks = iter([0, 0, 61, 61])
    monkeypatch.setattr("time.monotonic", lambda: next(ticks))
    out = S.preflight_required(ctx, REQUIRED * 2)
    assert out["status"] == "INCOMPLETE_PREFLIGHT_DEADLINE"
    assert len(ctx.calls) == 1 and out["expected_operations"] == 2 and out["model_calls"] == 0


def test_actual_author_visit_blocks_before_any_group_or_model(ctx, monkeypatch):
    from forge_factory import layer

    ctx.status = "UNSUPPORTED"
    monkeypatch.setattr(S.V1, "inventory", lambda ws: {"missing_sections": []})
    monkeypatch.setattr(S, "Context", lambda ws: ctx)
    manifest = {"peripheral_profile_sha256": "fixed", "semantic_required_operations": REQUIRED}
    monkeypatch.setattr(S.V1, "_manifest", lambda ws: manifest)
    monkeypatch.setattr(layer, "profile", lambda ws: {"sha256": "fixed", "semantic_required_operations": REQUIRED})
    monkeypatch.setattr(S, "_run_group", lambda *a, **k: pytest.fail("author must not run after capability block"))
    monkeypatch.setattr(S.S, "packet", lambda *a, **k: pytest.fail("no model packet after capability block"))
    monkeypatch.setattr(S.V1, "reply", lambda ws, status, issues, budget: {"status": status, "issues": issues, "budget": budget})
    result = S._visit(ctx.ws, "unused-model", {"calls": 0}, {})
    assert result["status"] == "FAILED" and "CAPABILITY_LIMIT" in result["issues"][0]
    assert result["budget"]["calls"] == 0
    record = ctx.ws / ".forge-run/lrtx/SWE.1/required-operation-preflight.json"
    assert json.loads(record.read_bytes())["status"] == "CAPABILITY_LIMIT"


def test_changed_or_removed_frozen_scope_is_refused_before_model(ctx, monkeypatch):
    from forge_factory import layer

    monkeypatch.setattr(S.V1, "inventory", lambda ws: {"missing_sections": []})
    monkeypatch.setattr(S, "Context", lambda ws: ctx)
    monkeypatch.setattr(S.V1, "_manifest", lambda ws: {"peripheral_profile_sha256": "fixed"})
    monkeypatch.setattr(layer, "profile", lambda ws: {"sha256": "fixed", "semantic_required_operations": REQUIRED})
    with pytest.raises(S.EngineFault, match="SCOPE_CHANGED"):
        S._visit(ctx.ws, "unused", {"calls": 0}, {})
    assert not ctx.calls
