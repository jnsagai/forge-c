"""Feature 014 DA-T034 (owner 2026-11-11 "go ahead with 1, 2 and 3"): bounded sequential candidate search with stall
detection. When the same failure fingerprint survives STALL_AFTER executed non-transient recovery plans in the
lineage, the candidate search stops with a typed RECOVERY_STALLED block before any further planner call (the
fingerprint's recurrence after each executed plan is the independent verifier result; confidence never counts)."""
import inspect
import types

from forge_factory.afo import recovery as R


def _p(strategy, fp="cfp1-x", status="EXECUTED"):
    return {"strategy": strategy, "status": status, "failure_fingerprint": fp, "record": {"affected_phase": "SWE.1"}}


def _stub(monkeypatch, ps):
    monkeypatch.setattr(R, "strategy_history", lambda store, oid: ps)
    return types.SimpleNamespace()


B = {"fingerprint": "cfp1-x", "phase": "SWE.1"}
O = {"order_id": "afo-o"}


def test_two_executed_plans_on_the_same_failure_stall_the_search(monkeypatch):
    s = _stub(monkeypatch, [_p("REWORK_LOCAL"), _p("RETURN_TO_OWNING_UPSTREAM_PHASE")])
    assert R.search_stalled(s, O, B) == "RECOVERY_STALLED:SAME_FAILURE_AFTER_2_PLANS"


def test_other_failures_transient_retries_and_unexecuted_plans_do_not_count(monkeypatch):
    s = _stub(monkeypatch, [_p("REWORK_LOCAL"), _p("REWORK_LOCAL", fp="cfp1-y"), _p("DEFER_TRANSIENT_DEPENDENCY"),
                            _p("RETURN_TO_OWNING_UPSTREAM_PHASE", status="REJECTED"),
                            _p("RETURN_TO_OWNING_UPSTREAM_PHASE", status="VALIDATED")])
    assert R.search_stalled(s, O, B) is None


def test_decide_checks_the_stall_before_the_planner():
    src = inspect.getsource(R.decide)
    assert src.index("search_stalled(") < src.index("planner(bundle")
