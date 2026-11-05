"""Preserve actionable launch causes without relaxing the native-effect boundary."""
# ruff: noqa: F811
import json

import pytest
from forge_factory.afo import line_recovery_coordination as K
from forge_factory.afo import line_recovery_product as P
from forge_factory.afo import local_agent as L
from forge_factory.afo.durable import Refused
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from test_line_recovery_product_bridge import product  # noqa: F401


@pytest.mark.parametrize("code", ["GUARD_FAIL", "INPUT_UNAVAILABLE", "STACK_STOP_FAILED"])
def test_prelaunch_code_survives_real_outbox_and_no_dispatch_proof(product, code):
    p = product
    calls = []

    def before_native(order, cfg):
        calls.append(order.wo)
        return dict(outcome=code)

    result = P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, cfg=p.cfg, launch=before_native)
    job = P.registered(p.store, P.job_id(p.aid))
    ex = Executions(p.store)
    proof = ex._evidence(job["job_id"], "LAUNCH_NOT_STARTED")
    assert proof["failure_type"] == code
    live = ex.get(job["job_id"])
    assert live["task_outcome"] == "BLOCKED" and live["resource_lease"] == "RELEASED"
    assert live["execution_liveness"] == "NOT_STARTED" and live["native_run_ids"] == []
    assert ex._evidence(job["job_id"], "PRODUCT_NATIVE_SUBMIT_INTENT") is None
    assert result["actions"][0]["job_id"] == job["job_id"]
    assert K.command(p.store, p.cmd["command_id"])["state"] == "QUARANTINED"
    charged = MissionLedger(p.store).snapshot("fixture-mission")
    assert charged["attempts"] == 1
    P.dispatch(p.store, K.command(p.store, p.cmd["command_id"]), p.worker, p.spec, p.eff, p.client,
               launch=lambda *a: pytest.fail("known refusal must not replay the native launch"))
    assert calls == [p.spec["wo"]]
    assert MissionLedger(p.store).snapshot("fixture-mission") == charged


@pytest.mark.parametrize("bad", ["bad code", "GUARD_FAIL\nSECRET", "X" * 129, "", None])
def test_untrusted_or_malformed_codes_never_become_durable_diagnostic_keys(bad):
    cause = Refused(bad, "PRIVATE_DETAIL")
    exc = L.LaunchNotStarted(dict(job_id="CONTROL", nonce="CONTROL"), cause)
    assert exc.failure_type == "Refused"
    assert "PRIVATE_DETAIL" not in json.dumps(dict(failure_type=exc.failure_type))
    assert exc.job_id == exc.nonce == "CONTROL"


def test_other_exception_cannot_supply_a_refusal_code():
    cause = RuntimeError("PRIVATE_DETAIL")
    cause.code = "GUARD_FAIL"
    assert L.LaunchNotStarted(dict(job_id="CONTROL", nonce="CONTROL"), cause).failure_type == "RuntimeError"


def test_invoked_transport_failure_keeps_uncertainty_and_spend(product):
    p = product

    def transport(order, cfg):
        raise TimeoutError("not proof that a native process did not start")

    P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, cfg=p.cfg, launch=transport)
    job = P.registered(p.store, P.job_id(p.aid))
    ex = Executions(p.store)
    assert ex.get(job["job_id"])["resource_lease"] == "HELD"
    assert ex._evidence(job["job_id"], "LAUNCH_NOT_STARTED") is None
    assert MissionLedger(p.store).snapshot("fixture-mission")["attempts"] == 1
