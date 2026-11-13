"""Per-tenant shares of the model service (feature 017, FR-010, FR-033).

A request takes one of its tenant's slots on arrival and holds it until it is answered, also while it waits for a
swap, so a tenant flooding requests for a model that is not loaded uses up its own share only. A tenant always gets
its guaranteed slots; it may borrow idle slots up to its maximum only while no other tenant's guarantee is at risk.
Waiting requests are served by tenant priority (lower value first), then arrival.

Work-conserving lending (T044 finding, windows 2026-11-11: the sim-neighbour tenant got 0 of 4 requests, each refused
429 queue_timeout after 600 s): on a host whose engines serve one sequence (total_slots 1) the factory's guarantee
reserved the only slot even while it was idle, so a tenant without a guarantee could never run - against US2 scenario
10 / SC-012 ("every tenant keeps progressing within the maximum wait"). A slot that is reserved but idle is now lent
to a tenant under its maximum while no tenant with an unmet guarantee is waiting. The guarantee still holds: its owner
is admitted at once (the engine queues it), and its extra wait is at most the lent requests in flight - recorded as
queue time per request (SC-003: waits recorded and bounded).
"""
from __future__ import annotations

import asyncio
import itertools
import time
from dataclasses import dataclass


class Refused(Exception):
    """An explicit refusal with an HTTP status and a machine reason (contracts/model-channel.md)."""

    def __init__(self, status: int, reason: str, detail: str = ""):
        super().__init__(f"{status}:{reason}{':' + detail if detail else ''}")
        self.status, self.reason, self.detail = status, reason, detail


@dataclass(frozen=True)
class TenantShare:
    tenant_id: str
    guaranteed: int
    max_concurrency: int
    queue_limit: int
    queue_timeout_s: float
    priority: int


class Shares:
    def __init__(self, tenants: list[TenantShare], total_slots: int, clock=time.monotonic):
        if sum(t.guaranteed for t in tenants) > total_slots:
            raise ValueError("GUARANTEED_SHARES_EXCEED_SLOTS")
        self.t = {x.tenant_id: x for x in tenants}
        self.total, self.clock = total_slots, clock
        self.in_use = dict.fromkeys(self.t, 0)
        self._waiting: list[tuple[int, int, str, asyncio.Future]] = []
        self._seq = itertools.count()

    def _reserved(self) -> int:
        return sum(max(self.in_use[k], v.guaranteed) for k, v in self.t.items())

    def _can_take(self, tid: str) -> bool:
        t, used = self.t[tid], self.in_use[tid]
        if used < t.guaranteed:
            return True
        if used >= t.max_concurrency:
            return False
        if self._reserved() < self.total:
            return True
        # lend an idle reserved slot, never while a tenant whose guarantee is unmet is waiting
        return sum(self.in_use.values()) < self.total and not any(
            not w[3].done() and self.in_use[w[2]] < self.t[w[2]].guaranteed for w in self._waiting)

    def waiting(self, tid: str) -> int:
        return sum(1 for w in self._waiting if w[2] == tid and not w[3].done())

    async def acquire(self, tid: str) -> float:
        """Take a slot for tenant `tid`; returns the queue wait in ms. Raises Refused(429, share_exhausted|queue_timeout)."""
        if tid not in self.t:
            raise Refused(401, "credential_refused")
        t0 = self.clock()
        if not any(not w[3].done() for w in self._waiting) and self._can_take(tid):
            self.in_use[tid] += 1
            return 0.0
        if self.waiting(tid) >= self.t[tid].queue_limit:
            raise Refused(429, "share_exhausted")
        fut = asyncio.get_running_loop().create_future()
        entry = (self.t[tid].priority, next(self._seq), tid, fut)
        self._waiting.append(entry)
        self._grant()
        try:
            await asyncio.wait_for(asyncio.shield(fut), timeout=self.t[tid].queue_timeout_s)
        except TimeoutError:
            if fut.done() and not fut.cancelled():  # granted at the last moment: keep it
                return (self.clock() - t0) * 1000
            fut.cancel()
            raise Refused(429, "queue_timeout") from None
        finally:
            if entry in self._waiting:
                self._waiting.remove(entry)
        return (self.clock() - t0) * 1000

    def release(self, tid: str) -> None:
        self.in_use[tid] = max(0, self.in_use[tid] - 1)
        self._grant()

    def _grant(self) -> None:
        for entry in sorted(self._waiting):
            _, _, tid, fut = entry
            if fut.done():
                continue
            if self._can_take(tid):
                self.in_use[tid] += 1
                fut.set_result(True)

    def snapshot(self) -> dict:
        return {k: {"in_use": self.in_use[k], "waiting": self.waiting(k)} for k in self.t}
