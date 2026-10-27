"""Frozen fault-class predicates on synthetic source timelines, never live soak evidence."""

import copy

import pytest
from forge_factory.afo import operational_facts as F
from forge_factory.afo.durable import Refused

BOUNDS = {
    "probe_gap_seconds": 600,
    "restore_seconds": 600,
    "control_cycle_seconds": 120,
    "eligible_queue_seconds": 600,
    "post_campaign_seconds": 1200,
}


def snapshot(at, *, mode="RUNNING", epoch=3):
    return {
        "wall": at,
        "completed_wall": at,
        "complete": True,
        "unit": {"ActiveState": "active", "MainPID": "100", "Result": "success"},
        "health": dict.fromkeys(("conductor", "fabro", "gateway", "data_volume"), True),
        "heartbeat": {"pid": 100, "cycle": at, "epoch": at, "ok": True},
        "intent": {"mode": mode, "epoch": epoch, "effective_stop": False},
        "boot_id": "old-boot",
        "free_bytes": 1000,
        "ledger": {
            "orders": [],
            "attempts": [],
            "controls": {},
            "afo_request_ledger": [],
            "afo_execution_liveness": [],
            "afo_mission_executions": [],
        },
    }


def order(oid="order-one", state="RUNNING", valid=True, created=1):
    return {
        "order_id": oid,
        "state": state,
        "authorization_id": "fixture-current-grant",
        "created_epoch": created,
        "envelope_valid": valid,
        "terminal_reason": None,
    }


def attempt(oid="order-one", state="SUCCEEDED", seq=1):
    return {"order_id": oid, "state": state, "attempt_seq": seq, "fabro_run_id": "native-real-shape-fixture"}


def scenario(fault):
    manifest = {"bounds": BOUNDS, "stage": "operation-24"}
    rows = [snapshot(t) for t in [100, 110, 150, 250]]
    params = {}
    at = 105
    if fault.startswith("last-job-"):
        params = {"order_id": "order-one"}
        rows[0]["ledger"]["orders"] = [order()]
        for r in rows[1:]:
            target = order(state="READY_FOR_OFFLINE_REVIEW" if fault == "last-job-success" else "BLOCKED")
            target["terminal_reason"] = "package BLOCKED / BLOCKED, 1 gaps"
            r["ledger"]["orders"] = [target]
            r["ledger"]["attempts"] = [attempt(state="FAILED" if fault == "last-job-failure" else "SUCCEEDED")]
    elif fault == "drained-queue":
        for r in rows[1:]:
            r["intent"].update(mode="DRAINING", epoch=4)
            r["ledger"]["controls"] = {"draining": "1"}
    elif fault == "dependency-outage":
        params = {"dependency": "gateway"}
        rows[1]["health"]["gateway"] = False
    elif fault == "reboot":
        for r in rows[1:]:
            r["boot_id"] = "new-boot"
    elif fault == "restart-limit":
        rows[1]["unit"].update(ActiveState="failed", MainPID="0", Result="start-limit-hit")
        rows[1]["health"]["conductor"] = False
        for r in rows[2:]:
            r["unit"]["MainPID"] = "200"
            r["heartbeat"]["pid"] = 200
    elif fault == "poison-head":
        params = {"order_id": "order-one", "eligible_order_id": "order-two"}
        rows[0]["ledger"]["orders"] = [order(state="QUEUED", valid=False), order("order-two", "QUEUED", created=2)]
        for r in rows[1:]:
            r["ledger"]["orders"] = [order(state="BLOCKED", valid=False), order("order-two", "RUNNING", created=2)]
    elif fault == "resource-pressure":
        params = {"minimum_free_bytes": 500}
        rows[1]["free_bytes"] = 100
    elif fault == "operator-stop-resume":
        for r in rows[1:3]:
            r["intent"].update(mode="STOPPED", epoch=4, effective_stop=True)
            r["unit"].update(ActiveState="inactive", MainPID="0")
            r["health"]["conductor"] = False
        rows[3]["intent"].update(epoch=5)
    elif fault == "post-campaign-continuity":
        rows = [snapshot(t) for t in [0, 86400, 87000, 87600]]
        at = 86400
    elif fault == "later-authorized-intake":
        params = {"order_id": "order-one"}
        for r in rows[1:]:
            r["ledger"]["orders"] = [order()]
            r["ledger"]["attempts"] = [attempt(state="RUNNING")]
    return manifest, params, {"at": at}, rows


@pytest.mark.parametrize("fault", sorted(F.PARAMETERS))
def test_every_external_class_requires_actual_exposure_and_appropriate_restoration(fault):
    m, p, receipt, rows = scenario(fault)
    exposed, restored = F.external(m, fault, p, receipt, rows)
    assert exposed and restored is not None, fault
    assert restored["wall"] > receipt["at"]
    assert F.external(m, fault, p, receipt, [rows[0]]) == (False, None)
    broken = copy.deepcopy(rows)
    for r in broken[1:]:
        r["health"]["conductor"] = False
    assert F.external(m, fault, p, receipt, broken)[1] is None


def test_case_coverage_matches_the_actual_campaign_catalogue():
    from forge_factory.afo.operational_campaign import SIGNALS
    from forge_factory.afo.qualification import FAULTS

    assert set(F.PARAMETERS) | set(SIGNALS) == set(FAULTS)
    assert not set(F.PARAMETERS) & set(SIGNALS)


def test_healthy_requires_fresh_heartbeat_from_the_actual_unit_process():
    s = snapshot(100)
    assert F.healthy(s)
    for change in [{"pid": 99}, {"epoch": -1000}, {"ok": False}]:
        assert not F.healthy({**s, "heartbeat": {**s["heartbeat"], **change}})


@pytest.mark.parametrize("fault", ["last-job-success", "last-job-failure", "last-job-block", "empty-queue", "drained-queue"])
def test_queue_end_requires_an_additional_control_window_and_cycle(fault):
    m, p, receipt, rows = scenario(fault)
    assert F.external(m, fault, p, receipt, rows[:3])[1] is None
    for r in rows[1:]:
        r["heartbeat"]["cycle"] = 1
    assert F.external(m, fault, p, receipt, rows)[1] is None


def test_a_historical_failed_attempt_cannot_be_the_last_failed_job():
    m, p, rec, rows = scenario("last-job-failure")
    for r in rows[1:]:
        r["ledger"]["attempts"].append(attempt(state="SUCCEEDED", seq=2))
    assert F.external(m, "last-job-failure", p, rec, rows) == (False, None)


def test_operator_stop_cannot_be_confirmed_with_held_capacity_or_new_requests():
    for change in ("held", "new-request", "no-effective-stop"):
        m, p, rec, rows = scenario("operator-stop-resume")
        if change == "held":
            rows[1]["ledger"]["afo_execution_liveness"] = [{"resource_lease": "HELD"}]
        elif change == "new-request":
            rows[2]["ledger"]["afo_request_ledger"] = [{"request_id": "unapproved-new", "state": "QUIESCENT"}]
        else:
            for r in rows[1:3]:
                r["intent"]["effective_stop"] = False
        assert F.external(m, "operator-stop-resume", p, rec, rows) == (False, None)


def test_stop_allows_bounded_reconciliation_before_effective_shutdown():
    m, p, rec, rows = scenario("operator-stop-resume")
    rows[1]["intent"]["effective_stop"] = False
    rows[1]["unit"].update(ActiveState="active", MainPID="100")
    rows[1]["ledger"]["afo_execution_liveness"] = [{"resource_lease": "HELD"}]
    assert F.external(m, "operator-stop-resume", p, rec, rows)[1] is rows[-1]


def test_restore_bounds_and_real_dependency_failure_cannot_be_skipped():
    m, p, rec, rows = scenario("dependency-outage")
    rows[1]["health"]["gateway"] = True
    assert F.external(m, "dependency-outage", p, rec, rows) == (False, None)
    m, p, rec, rows = scenario("restart-limit")
    m = {**m, "bounds": {**m["bounds"], "restore_seconds": 20}}
    assert F.external(m, "restart-limit", p, rec, rows) == (True, None)


@pytest.mark.parametrize(
    "bad", [{}, {"minimum_free_bytes": -1}, {"minimum_free_bytes": True}, {"minimum_free_bytes": 10, "extra": "unfrozen"}]
)
def test_external_fixture_parameters_are_frozen_and_typed(bad):
    ref = {"path": "/fixture-plan.json", "sha256": "0" * 64}
    doc = {
        "schema": "forge-c/operational-exposure-fixture/1",
        "fault": "resource-pressure",
        "observer_plan_ref": ref,
        "unit": "fixture.service",
        "parameters": bad,
    }
    with pytest.raises(Refused):
        F.validate_fixture(doc, "resource-pressure", ref, "fixture.service")
