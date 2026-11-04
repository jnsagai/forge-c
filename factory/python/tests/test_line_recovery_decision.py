"""The existing deterministic decision path cannot short-circuit an authorized line planner to legacy deferral."""
import pytest
from forge_factory.afo import recovery, planner, line_recovery
from forge_factory.afo.queue import QueueError
from test_afo_local_autonomy import local, order  # noqa: F401


def test_development_deferral_remains_default_but_verified_line_reaches_existing_planner(local, monkeypatch):
    from forge_factory import development_execution

    s, o, bundle, eff, ws, _ = local
    eff.policy["engineering"]["allowed_model_profiles"] = []
    monkeypatch.setattr(development_execution, "selected", lambda _: True)
    calls = []

    def invoke(*args):
        calls.append(args)
        raise planner.Pending("durable-line-job")

    result = recovery.decide(s, o, bundle, ws=ws, eff=eff, auth_models=None, planner=invoke)
    assert result["plan"]["rationale_code"] == "DEFERRED_BY_DEVELOPMENT_POLICY"
    assert calls == []
    monkeypatch.setattr(line_recovery, "context", lambda *a: {"status": "BOUND_CONTEXT_ONLY_NO_DISPATCH"})
    with pytest.raises(planner.Pending, match="durable-line-job"):
        recovery.decide(s, o, bundle, ws=ws, eff=eff, auth_models=None, planner=invoke,
                        line_origin={"campaign_path": "/approved/campaign"})
    assert len(calls) == 1


def test_line_context_refusal_never_reaches_model_planner(local, monkeypatch):
    s, o, bundle, eff, ws, _ = local
    def refuse(*args):
        raise line_recovery.BindingRefused("LINE_AUTH_REFUSED")
    monkeypatch.setattr(line_recovery, "context", refuse)
    with pytest.raises(line_recovery.BindingRefused, match="LINE_AUTH_REFUSED"):
        recovery.decide(s, o, bundle, ws=ws, eff=eff, auth_models=None,
                        planner=lambda *a: pytest.fail("unbound planner invocation"),
                        line_origin={"campaign_path": "/approved/campaign"})
    with pytest.raises(QueueError, match="BUNDLE_ORDER_MISMATCH"):
        recovery.decide(s, o, dict(bundle, order_id="foreign"), ws=ws, eff=eff, auth_models=None,
                        line_origin={"campaign_path": "/approved/campaign"})
