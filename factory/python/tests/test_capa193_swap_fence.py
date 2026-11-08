"""CAPA-193: a model swap serializes against request reservations with a COMMITTED job-scoped fence, never by holding
the line queue's write lock for the whole swap (9-27 s observed 2026-11-08; "database is locked" ended the owner
guardian twice). A dead swapper releases the fence, as its dying connection used to release the lock."""
# ruff: noqa: F811
import os
import subprocess
import sys

import pytest
from forge_factory.afo import line_stack_lifecycle as A
from forge_factory.afo import queue as Q
from forge_factory.afo.durable import Refused
from forge_factory.afo.execution_lifecycle import Executions
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401


def request(p, name):
    return p.ledger.reserve_request(
        "mission-test", p.ctx.job_id, name, body_sha256="a" * 64, input_tokens=6000, output_cap=6000, authorize=lambda: True
    )


def fence(p, **change):
    value = {**A.swap_fence(p.ctx.job_id, "model-x", "ACTIVE"), **change}
    with p.store.tx() as c:
        A._write_swap_fence(c, p.ctx.job_id, value)
    return value


def test_reservation_refused_while_a_live_swap_fence_is_active(protocol):
    p = protocol
    Executions(p.store).reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    before = p.ledger.snapshot("mission-test")
    fence(p)
    with pytest.raises(Refused, match="MODEL_SWAP_IN_PROGRESS"):
        request(p, "during-swap")
    assert p.ledger.snapshot("mission-test") == before  # nothing reserved or charged
    fence(p, state="DONE")
    assert request(p, "after-swap")["replay"] is False


def test_dead_swapper_does_not_fence_forever(protocol):
    p = protocol
    Executions(p.store).reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    from forge_factory.lrtx.stack import process_identity

    me = process_identity(os.getpid())
    fence(p, pid=child.pid, identity={**me, "start_ticks": "1"})  # an identity no live process has
    with p.store.tx() as c:
        assert not A.swap_in_progress(c, p.ctx.job_id)
    assert request(p, "after-dead-swapper")["replay"] is False


def test_fence_without_identity_or_other_job_never_fences(protocol):
    p = protocol
    fence(p, identity=None)
    with p.store.tx() as c:
        assert not A.swap_in_progress(c, p.ctx.job_id)
        assert not A.swap_in_progress(c, "afo-product-other")


def test_line_queue_busy_timeout_outlasts_observed_stalls():
    assert Q.BUSY_TIMEOUT_S >= 60
