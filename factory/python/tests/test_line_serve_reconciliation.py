"""Model-free regressions for the TIM SWE.1 continuation's serve fence."""

from contextlib import contextmanager

import pytest
from forge_factory.afo import line_stack_lifecycle as lifecycle
from forge_factory.afo.durable import Refused


def test_native_execution_observation_can_advance_without_changing_authority():
    before = {
        "revision": 10, "last_reconciled_at": "before", "lease_epoch": 7,
        "launch_nonce": "same-nonce", "authorization_state": "VALID",
        "native_run_ids": ["same-run"], "cancellation_state": "NOT_REQUESTED",
        "resource_lease": "HELD",
    }
    refreshed = before | {"revision": 11, "last_reconciled_at": "after"}
    assert lifecycle._same_serve_execution(before, refreshed)
    for changed in (
        {"revision": 9}, {"lease_epoch": 8}, {"launch_nonce": "other"},
        {"authorization_state": "REVOKED"}, {"native_run_ids": ["other-run"]},
        {"cancellation_state": "REQUESTED"}, {"resource_lease": "RELEASED"},
    ):
        assert not lifecycle._same_serve_execution(before, refreshed | changed)


@pytest.mark.parametrize("ready_on", [2, None])
def test_serve_rechecks_busy_requests_before_any_effect(monkeypatch, ready_on):
    entered = []
    waits = []

    @contextmanager
    def fence(*args, **kwargs):
        entered.append(len(entered) + 1)
        if entered[-1] != ready_on:
            raise Refused(lifecycle.SERVE_REQUESTS_BUSY)
        yield "verified"

    monkeypatch.setattr(lifecycle, "fenced", fence)
    monkeypatch.setattr(lifecycle.time, "sleep", waits.append)
    if ready_on:
        with lifecycle._serve_fence({}, "pinned-model", "/workspace") as guard:
            assert guard == "verified"
        assert entered == [1, 2] and waits == [1]
    else:
        with pytest.raises(Refused, match=lifecycle.SERVE_REQUESTS_BUSY):
            with lifecycle._serve_fence({}, "pinned-model", "/workspace"):
                pytest.fail("provider effects with an outstanding request")
        assert entered == [1, 2, 3] and waits == [1, 1]


def test_retry_stops_at_the_effect_boundary(monkeypatch):
    entered = []

    @contextmanager
    def fence(*args, **kwargs):
        entered.append(True)
        yield "verified"

    monkeypatch.setattr(lifecycle, "fenced", fence)
    with pytest.raises(Refused, match=lifecycle.SERVE_REQUESTS_BUSY):
        with lifecycle._serve_fence({}, "pinned-model", "/workspace"):
            raise Refused(lifecycle.SERVE_REQUESTS_BUSY)
    assert entered == [True]
