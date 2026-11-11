"""CAPA-224 (owner lane, 8 orders e.g. WO-F014-SWE6-AFOQUAL-20261104-L90V ended PLAN_REJECTED:BUDGET_VARIANTS_EXHAUSTED):
every rejected plan was a DEFER_TRANSIENT_DEPENDENCY retry with 0 of 2 transient retries used. The variant budget counted
VALIDATED CLOSE_BLOCKED plans of the whole mission cohort as strategy variants, was applied to DEFER retries (which have
their own transient budget), and the retry number counted only EXECUTED retries while its fingerprint was compared with
every plan of the cohort (PLAN_ALREADY_TRIED)."""
import json
import types

from forge_factory.afo import local_agent
from forge_factory.afo import recovery as R

EFF = types.SimpleNamespace(get=lambda k: {
    "budgets.max_order_attempts": 6, "budgets.max_strategy_variants_per_phase": 2,
    "budgets.max_retries_per_transient_operation": 2, "budgets.max_recovery_model_calls_per_order": 4,
    "budgets.max_order_wall_seconds": 10 ** 9, "engineering.allowed_model_profiles": []}.get(k))
ORDER = {"order_id": "afo-o", "envelope": json.dumps({"model_profile": "m"}), "created_epoch": 0}


def _plan(strategy, phase="SWE.6", status="VALIDATED", ref=None):
    return {"strategy": strategy, "status": status, "source": "RULE", "attempt_id": "a0",
            "plan_fingerprint": ref or f"fp-{strategy}-{status}", "failure_fingerprint": "cfp1-other",
            "record": {"affected_phase": phase, "model_profile": None}}


def _history(monkeypatch, ps):
    monkeypatch.setattr(R, "strategy_history", lambda store, oid: ps)
    monkeypatch.setattr(local_agent, "records", lambda store, oid: [])
    return types.SimpleNamespace(attempts=lambda oid: [{"attempt_id": "a1"}])


def _bundle(cls):
    return {"order_id": "afo-o", "attempt_id": "a1", "fingerprint": "cfp1-x", "failure_class": cls, "phase": "SWE.6"}


def test_close_blocked_plans_are_not_strategy_variants(monkeypatch):
    store = _history(monkeypatch, [_plan("CLOSE_BLOCKED")] * 5 + [_plan("REWORK_LOCAL")])
    assert R.budget_snapshot(store, ORDER, EFF)["variants_by_phase"]["SWE.6"] == 1


def test_a_transient_retry_is_not_checked_against_the_variant_budget(monkeypatch):
    store = _history(monkeypatch, [_plan("REWORK_LOCAL", ref=f"fp{i}") for i in range(3)])
    defer = R._base(_bundle("TRANSIENT_DEPENDENCY"), "DEFER_TRANSIENT_DEPENDENCY", "SWE.6", "r",
                    material_difference_ref="transient_retry:1")
    issues = R.validate(defer, _bundle("TRANSIENT_DEPENDENCY"), store=store, order=ORDER, eff=EFF, auth_models=None)
    assert "BUDGET_VARIANTS_EXHAUSTED" not in issues and "BUDGET_TRANSIENT_RETRIES_EXHAUSTED" not in issues
    rework = R._base(_bundle("PRODUCT_QUALITY"), "REWORK_LOCAL", "SWE.6", "r")
    assert "BUDGET_VARIANTS_EXHAUSTED" in R.validate(rework, _bundle("PRODUCT_QUALITY"), store=store, order=ORDER,
                                                    eff=EFF, auth_models=None)


def test_the_retry_number_skips_numbers_already_planned_in_the_cohort(monkeypatch):
    store = _history(monkeypatch, [_plan("DEFER_TRANSIENT_DEPENDENCY", status="REJECTED"),
                                   _plan("DEFER_TRANSIENT_DEPENDENCY", status="VALIDATED", ref="fp2")])
    assert R.next_transient_retry(store, ORDER) == 3
    assert R.budget_snapshot(store, ORDER, EFF)["transient_retries"] == 0  # the budget still counts executions only
