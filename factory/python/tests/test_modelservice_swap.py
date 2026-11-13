"""Feature 017 T027: on-demand swaps at full capacity, invisible to tenants and fair between them (FR-025..FR-033)."""
import asyncio

import pytest
from model_tier.catalog import Catalog, Model, SwapPolicy
from model_tier.shares import Refused, Shares, TenantShare
from model_tier.swap import EMPTY, SERVING, SwapController

A, B = "ornith-1.5-35b-a3b-q8", "qwen3.6-35b-a3b-fp8"


def ident(name, fp):
    return {"name": name, "revision_fingerprint": fp * 64, "precision": "fp8", "reasoning_mode": "off",
            "context_limit": 65536, "engine": {"name": "x", "version": "1"}, "attested": True}


def catalog(**pol):
    p = dict(drain_max_s=2.0, min_residency_s=0.0, swap_after_wait_s=0.05, max_wait_s=3.0, max_swaps_per_hour=1000)
    p.update(pol)
    models = {m: Model(model=m, engine="vllm", launch_kind="compose", engine_url="http://e", vram_mib=40000,
                       full_capacity={"context_per_sequence": 65536, "sequences": 4}, reasoning_mode="off",
                       identity=ident(m, fp), load_timeout_s=5, warm_strategy="vllm_sleep", ram_gib=35)
              for m, fp in ((A, "a"), (B, "b"))}
    return Catalog(site="test", gpu_vram_mib=49140, models=models, policy=SwapPolicy(**p))


class FakeEngine:
    def __init__(self, name, log, gpu, load_s=0.02, fail=False, wrong_identity=False, cold=False):
        self.name, self.log, self.gpu, self.load_s = name, log, gpu, load_s
        self.fail, self.wrong, self.cold, self.sources = fail, wrong_identity, cold, []

    async def prepare(self):
        self.log.append(("prepare", self.name))
        return {"warm": not self.cold, "reason": "RAM_BUDGET" if self.cold else ""}

    async def load(self):
        assert not self.gpu, f"GPU still held by {self.gpu} while loading {self.name}"  # full capacity: one at a time
        await asyncio.sleep(self.load_s)
        if self.fail:
            raise RuntimeError("engine did not become healthy")
        self.gpu.add(self.name)
        self.sources.append("disk" if self.cold else "ram")
        self.log.append(("load", self.name))
        return {"warm": not self.cold}

    async def unload(self):
        self.gpu.discard(self.name)
        self.log.append(("unload", self.name))

    async def identity(self):
        return ident(self.name, "f" if self.wrong else ("a" if self.name == A else "b"))


def controller(cat=None, **eng):
    log, gpu, events = [], set(), []
    engines = {m: FakeEngine(m, log, gpu, **eng.get(m, {})) for m in (A, B)}
    c = SwapController(cat or catalog(), engines, record=events.append, tick_s=0.01)
    return c, engines, log, events


async def call(c, model, hold=0.0, prio=0):
    lease = await c.acquire(model, prio)
    served = c.loaded
    await asyncio.sleep(hold)
    lease.release()
    return served, lease.swap_ms


def test_alternating_requests_are_each_answered_by_the_model_they_name():
    async def go():
        c, engines, log, events = controller()
        await c.start()
        served = []
        for m in (A, B, A, B, A):
            got, _ = await call(c, m, hold=0.01)
            served.append((m, got))
        await c.close()
        return served, log, events, engines
    served, log, events, engines = asyncio.run(go())
    assert all(m == got for m, got in served)  # SC-009
    swaps = [e for e in events if e["kind"] == "swap"]
    assert [e["outcome"] for e in swaps] == ["OK"] * 5 and all(e["identity_verified"] and e["warm"] for e in swaps)
    assert engines[A].sources == ["ram"] * 3 and engines[B].sources == ["ram"] * 2  # FR-031: never from disk


def test_drain_finishes_in_flight_work_before_unload():
    async def go():
        c, _, log, events = controller()
        await c.start()
        long = asyncio.create_task(call(c, A, hold=0.3))
        await asyncio.sleep(0.05)
        other = asyncio.create_task(call(c, B))
        await asyncio.sleep(0.05)
        late = asyncio.create_task(call(c, A))  # arrives while A drains: must queue, not slip in
        r = await asyncio.gather(long, other, late)
        await c.close()
        return r, log, events
    (long, other, late), log, events = asyncio.run(go())
    assert long[0] == A and other[0] == B and late[0] == A
    assert log.index(("unload", A)) > 0 and log[log.index(("unload", A)) - 1] == ("load", A)
    drain = next(e for e in events if e["kind"] == "swap" and e["from_model"] == A)
    assert drain["drain_ms"] >= 150  # it waited for the long request, it did not cut it off


def test_drain_limit_postpones_the_swap_and_cuts_nothing():
    async def go():
        c, _, _, events = controller(catalog(drain_max_s=0.05, max_wait_s=0.5))
        await c.start()
        long = asyncio.create_task(call(c, A, hold=0.8))
        await asyncio.sleep(0.05)
        with pytest.raises(Refused) as e:
            await c.acquire(B)
        r = await long
        await c.close()
        return r, events, e.value
    r, events, refused = asyncio.run(go())
    assert r[0] == A and refused.status == 429 and refused.reason == "queue_timeout"
    assert any(e.get("outcome") == "DRAIN_TIMEOUT" for e in events)


def test_min_residency_and_batching_prevent_thrash():
    async def go():
        c, _, _, events = controller(catalog(min_residency_s=0.3, swap_after_wait_s=0.0))
        await c.start()
        tasks = [asyncio.create_task(call(c, m, hold=0.02)) for m in (A, B, A, B, A, B, A, B)]
        r = await asyncio.gather(*tasks)
        await c.close()
        return r, events
    r, events = asyncio.run(go())
    assert all(m == got for m, (got, _) in zip((A, B) * 4, r, strict=True))
    assert len([e for e in events if e["kind"] == "swap"]) <= 3  # 8 alternating requests, served in 2-3 batches


def test_failed_load_refuses_that_models_waiters_and_never_serves_another_model():
    async def go():
        c, _, _, events = controller(**{B: {"fail": True}})
        await c.start()
        await call(c, A)
        with pytest.raises(Refused) as e:
            await c.acquire(B)
        state = (c.state, c.loaded)
        got = await call(c, A)
        await c.close()
        return e.value, state, got, events
    refused, state, got, events = asyncio.run(go())
    assert refused.status == 503 and refused.reason == "model_unavailable" and state == (EMPTY, None)
    assert got[0] == A and any(e.get("outcome") == "LOAD_FAILED" for e in events)


def test_identity_mismatch_after_load_is_refused():
    async def go():
        c, engines, _, events = controller(**{B: {"wrong_identity": True}})
        await c.start()
        with pytest.raises(Refused) as e:
            await c.acquire(B)
        await c.close()
        return e.value, events, engines
    refused, events, engines = asyncio.run(go())
    assert refused.reason == "model_unavailable" and "IDENTITY_MISMATCH" in refused.detail
    assert any(e.get("outcome") == "IDENTITY_MISMATCH" for e in events) and not engines[B].gpu


def test_unknown_model_is_refused_without_any_swap():
    async def go():
        c, _, log, _ = controller()
        await c.start()
        with pytest.raises(Refused) as e:
            await c.acquire("gpt-unknown")
        await c.close()
        return e.value, log
    refused, log = asyncio.run(go())
    assert refused.status == 404 and refused.reason == "model_not_offered" and not any(x[0] == "load" for x in log)


def test_cold_fallback_still_answers_and_is_a_finding():
    async def go():
        c, engines, _, events = controller(**{B: {"cold": True}})
        await c.start()
        got = await call(c, B)
        await c.close()
        return got, engines, events
    got, engines, events = asyncio.run(go())
    assert got[0] == B and engines[B].sources == ["disk"]
    assert any(e.get("finding") == "MODEL_NOT_WARM" and e["model"] == B for e in events)


def test_swap_rate_finding():
    async def go():
        c, _, _, events = controller(catalog(max_swaps_per_hour=2))
        await c.start()
        for m in (A, B, A, B):
            await call(c, m)
        await c.close()
        return events
    events = asyncio.run(go())
    assert any(e.get("finding") == "SWAP_RATE_HIGH" for e in events)
    assert all("messages" not in e and "content" not in e for e in events)  # metadata only


def test_two_factories_and_a_neighbour_all_progress_and_keep_their_share():
    """FR-033 / SC-012: tenants preferring different models progress; a flood takes only the flooder's own slots."""
    async def go():
        c, _, _, _ = controller(catalog(min_residency_s=0.05, swap_after_wait_s=0.05, max_wait_s=5.0))
        shares = Shares([TenantShare("factory-a", 1, 2, 50, 10, 0), TenantShare("factory-b", 1, 2, 50, 10, 0),
                         TenantShare("neighbour", 1, 2, 100, 10, 5)], total_slots=4)
        await c.start()

        async def tenant_call(tid, model, prio):
            await shares.acquire(tid)
            try:
                return tid, model, await call(c, model, hold=0.01, prio=prio)
            finally:
                shares.release(tid)

        flood = [asyncio.create_task(tenant_call("neighbour", B, 5)) for _ in range(40)]
        work = [asyncio.create_task(tenant_call("factory-a", A, 0)) for _ in range(6)]
        work += [asyncio.create_task(tenant_call("factory-b", A if i % 2 else B, 0)) for i in range(6)]
        peak = 0
        while not all(t.done() for t in work):
            peak = max(peak, shares.in_use["neighbour"])
            await asyncio.sleep(0.005)
        results = await asyncio.gather(*work, *flood)
        await c.close()
        return results, peak
    results, peak = asyncio.run(go())
    assert all(model == served for _, model, (served, _) in results)
    assert sum(1 for r in results if r[0] == "factory-a") == 6 and sum(1 for r in results if r[0] == "factory-b") == 6
    assert peak <= 2  # the neighbour never exceeded its own maximum, whatever it flooded


def test_shares_guarantee_and_queue_limits():
    async def go():
        s = Shares([TenantShare("f", 1, 1, 1, 0.1, 0), TenantShare("n", 1, 3, 0, 0.1, 5)], total_slots=2)
        await s.acquire("n")
        await s.acquire("f")  # guaranteed, even though n would like more
        with pytest.raises(Refused) as e1:
            await s.acquire("n")  # n at 1 of max 3, but the only spare slot belongs to f's guarantee -> no queue room
        t = asyncio.create_task(s.acquire("f"))  # queues (limit 1)
        await asyncio.sleep(0)
        with pytest.raises(Refused) as e2:
            await s.acquire("f")
        with pytest.raises(Refused) as e3:
            await t
        with pytest.raises(ValueError):
            Shares([TenantShare("x", 3, 3, 0, 1, 0)], total_slots=2)
        return e1.value, e2.value, e3.value
    e1, e2, e3 = asyncio.run(go())
    assert (e1.status, e1.reason) == (429, "share_exhausted") and e2.reason == "share_exhausted"
    assert e3.reason == "queue_timeout"


def test_state_after_start_is_empty_and_serving_after_first_request():
    async def go():
        c, _, log, _ = controller()
        await c.start()
        s0 = c.state
        await call(c, B)
        s1 = (c.state, c.loaded)
        await c.close()
        return s0, s1, log
    s0, s1, log = asyncio.run(go())
    assert s0 == EMPTY and s1 == (SERVING, B) and log[:2] == [("prepare", A), ("prepare", B)]
