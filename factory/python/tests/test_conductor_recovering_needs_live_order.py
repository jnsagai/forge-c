"""An issue is RECOVERING only while a later order of the part is launched and active (owner 2026-11-09: the
dashboard showed the supervisor "reparing USART" from a never-launched order of a lineage put ON_HOLD)."""
from forge_factory.afo import line_conductor as L

NOW = 1_800_000_000.0


def _o(wo, created, *, rid=None, activity=None, package=None, phase="SWE.1", passed=()):
    return {"wo": wo, "tag": "USARTL", "phase": phase, "created": created, "rid": rid, "package": package,
            "passed": set(passed), "activity": activity if activity is not None else created}


def test_a_never_launched_later_order_is_not_a_recovery():
    orders = [_o("L42D", NOW - 50000), _o("L42I", NOW - 3600)]
    assert L._later(orders, "USARTL", "SWE.1", NOW - 50000, launched=False, now=NOW) == (None, None)


def test_a_launched_active_later_order_is_a_recovery_under_way():
    orders = [_o("L42D", NOW - 50000), _o("L42E", NOW - 3600, rid="01RUN", activity=NOW - 60)]
    assert L._later(orders, "USARTL", "SWE.1", NOW - 50000, launched=False, now=NOW) == ("RECOVERING", "L42E")


def test_a_launched_later_order_without_activity_for_hours_is_not_a_recovery():
    orders = [_o("L42D", NOW - 90000), _o("L42E", NOW - 80000, rid="01RUN", activity=NOW - L.RECOVERY_LIVE_S - 1)]
    assert L._later(orders, "USARTL", "SWE.1", NOW - 90000, launched=False, now=NOW) == (None, None)


def test_a_later_order_that_passed_the_phase_still_resolves_the_issue():
    orders = [_o("L42D", NOW - 50000), _o("L42F", NOW - 3600, rid="01RUN", passed=("SWE.1",))]
    assert L._later(orders, "USARTL", "SWE.1", NOW - 50000, launched=False, now=NOW) == ("RESOLVED", "L42F")
