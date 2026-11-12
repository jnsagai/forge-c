"""CAPA-215 (owner 2026-11-10 "for 2. I agree"): TIM LL L43K failed on a transient queue snapshot deadline (CAPA-214);
the rule-based recovery plan was DEFER_TRANSIENT_DEPENDENCY, yet every recovery plan of an SWE.1 order was parked as
LINE_RECOVERY_OWNER_CHANGE_REQUIRED, so a 3-second blip blocked the order until new source. A transient-dependency retry
changes no owner input, model, profile or policy: it now retries without the owner. Model/profile switches, closing
and every other SWE.1 strategy still need the owner."""
from __future__ import annotations

import inspect

import pytest

from forge_factory.afo import line_recovery_coordination as LC
from forge_factory.afo import line_recovery_worker as LW


def _plan(strategy, phase="SWE.1", **kw):
    return {"strategy": strategy, "affected_phase": phase, **kw}


def test_a_transient_retry_of_an_swe1_order_needs_no_owner():
    assert LC.owner_change_required(_plan("DEFER_TRANSIENT_DEPENDENCY")) is False


@pytest.mark.parametrize("plan", [
    _plan("SWITCH_PREAPPROVED_MODEL_PROFILE"),
    _plan("CLOSE_BLOCKED", phase="SWE.3"),
    _plan("DEFER_TRANSIENT_DEPENDENCY", model_profile="other-profile"),
    _plan("REPAIR_PHASE"),
    _plan("REPAIR_PHASE", phase="SWE.3", owner_phase="SWE.1"),
])
def test_owner_changes_stay_parked(plan):
    assert LC.owner_change_required(plan) is True


def test_other_phases_keep_their_rules():
    assert LC.owner_change_required(_plan("REPAIR_PHASE", phase="SWE.3")) is False


def test_every_refusal_site_uses_the_one_rule():
    for fn in (LC._decision, LC.continuation, LW._replan):
        src = inspect.getsource(fn)
        assert "owner_change_required(" in src and '== "SWE.1"' not in src, fn.__name__
