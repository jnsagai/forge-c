"""017 T044 finding (smoke windows 2026-11-11): with one engine sequence (total_slots 1) and the factory's guaranteed
slot, the sim-neighbour tenant (guarantee 0) was refused 429 queue_timeout on every request - an idle reserved slot was
never lent. US2 scenario 10 / SC-012: every tenant keeps progressing; SC-003: the factory keeps its guaranteed share and
its waits are bounded."""
from __future__ import annotations

import asyncio

import pytest

from model_tier.shares import Refused, Shares, TenantShare

# the recipe's shares (deploy/recipe/model-tier/tenants.yaml) on a one-sequence engine
FACTORY = TenantShare("forge-qual", 1, 2, 16, 900, 0)
NEIGHBOUR = TenantShare("sim-neighbour", 0, 1, 64, 0.2, 5)


def test_an_idle_reserved_slot_is_lent_to_a_tenant_without_guarantee():
    async def go():
        s = Shares([FACTORY, NEIGHBOUR], total_slots=1)
        wait = await s.acquire("sim-neighbour")  # the factory is idle: its reserved slot is lent at once
        return wait, s.snapshot()
    wait, snap = asyncio.run(go())
    assert wait == 0.0 and snap["sim-neighbour"]["in_use"] == 1


def test_the_guarantee_holds_while_its_slot_is_lent():
    async def go():
        s = Shares([FACTORY, NEIGHBOUR], total_slots=1)
        await s.acquire("sim-neighbour")
        wait = await s.acquire("forge-qual")  # admitted at once: the engine queues it behind the lent request
        with pytest.raises(Refused) as e:  # the neighbour stays within its own maximum (1)
            await s.acquire("sim-neighbour")
        return wait, s.snapshot(), e.value
    wait, snap, err = asyncio.run(go())
    assert wait == 0.0 and snap["forge-qual"]["in_use"] == 1
    assert (err.status, err.reason) == (429, "queue_timeout")


def test_both_tenants_progress_when_the_factory_works_continuously():
    """The smoke plan's shape: the factory asks one request at a time while the neighbour saturates its share."""
    async def go():
        s = Shares([FACTORY, NEIGHBOUR], total_slots=1)
        served = {"forge-qual": 0, "sim-neighbour": 0}

        async def call(tid, hold):
            await s.acquire(tid)
            try:
                await asyncio.sleep(hold)
                served[tid] += 1
            finally:
                s.release(tid)

        async def factory():
            for _ in range(20):
                await call("forge-qual", 0.005)

        async def neighbour():
            for _ in range(5):
                await call("sim-neighbour", 0.005)
        await asyncio.gather(factory(), neighbour(), neighbour())
        return served
    served = asyncio.run(go())
    assert served == {"forge-qual": 20, "sim-neighbour": 10}


def test_nothing_is_lent_when_every_slot_is_in_use():
    async def go():
        s = Shares([FACTORY, NEIGHBOUR], total_slots=1)
        await s.acquire("forge-qual")  # the only slot is busy, not idle
        with pytest.raises(Refused) as e:
            await s.acquire("sim-neighbour")
        return e.value
    assert asyncio.run(go()).reason == "queue_timeout"
