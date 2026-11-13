"""On-demand model swapping (feature 017, FR-025 to FR-031, FR-033; data-model SwapEvent and tier states).

One model is on the GPU at a time (48 GB holds one at full capacity). A request names a model; if it is loaded and
no swap is draining it, the request goes straight through. Otherwise it waits while the controller decides:

* the next model is the one whose waiting requests score highest, `age x (1 + 1/(1 + priority))` (FR-033);
* a swap starts only after the loaded model's minimum residency, and only when the loaded model is idle or the
  other model's oldest request has waited `swap_after_wait_s` (no thrash, FR-028);
* a swap stops admitting work to the loaded model, lets in-flight requests finish (never cut off; at the drain
  limit the swap is postponed), unloads, loads the target, checks its identity and then releases the waiters;
* a failed load or a wrong identity refuses that model's waiters with 503 model_unavailable and leaves the tier
  EMPTY: a request is never answered by a model it did not name (FR-027);
* every swap is recorded as metadata only (FR-030); a swap rate above the policy raises a finding.

Engines keep models warm in host RAM between swaps (FR-031); the controller only asks them to load and unload.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from . import identity as I
from .catalog import Catalog
from .shares import Refused

EMPTY, LOADING, SERVING, DRAINING, UNLOADING = "EMPTY", "LOADING", "SERVING", "DRAINING", "UNLOADING"


class Engine(Protocol):
    async def prepare(self) -> dict: ...      # warm-up at service start: {"warm": bool, "reason": str}
    async def load(self) -> dict: ...         # onto the GPU: {"warm": bool}
    async def unload(self) -> None: ...       # off the GPU (kept warm in RAM where the strategy allows)
    async def identity(self) -> dict: ...     # identity of what the engine now serves


@dataclass(eq=False)
class Waiter:
    model: str
    priority: int
    t0: float
    fut: asyncio.Future = field(repr=False)


@dataclass
class Lease:
    model: str
    swap_ms: float
    controller: SwapController = field(repr=False)
    released: bool = False

    def release(self) -> None:
        if not self.released:
            self.released = True
            self.controller._done(self.model)


class SwapController:
    def __init__(self, catalog: Catalog, engines: dict[str, Engine], record: Callable[[dict], None] | None = None,
                 clock: Callable[[], float] = time.monotonic, tick_s: float = 0.5):
        missing = set(catalog.models) - set(engines)
        if missing:
            raise ValueError("ENGINE_MISSING:" + ",".join(sorted(missing)))
        self.cat, self.engines, self.clock, self.tick_s = catalog, engines, clock, tick_s
        self.record = record or (lambda ev: None)
        self.state, self.loaded, self.loaded_since = EMPTY, None, 0.0
        self.inflight = dict.fromkeys(catalog.models, 0)
        self.waiters: dict[str, list[Waiter]] = {m: [] for m in catalog.models}
        self.swaps: list[float] = []
        self._kick = asyncio.Event()
        self._task: asyncio.Task | None = None
        self.warm: dict[str, dict] = {}

    # ---- lifecycle -------------------------------------------------------------------------------------------
    async def start(self) -> dict:
        """Warm every catalog model once (FR-031) and start scheduling. The GPU is left EMPTY."""
        for name, eng in self.engines.items():
            self.warm[name] = await eng.prepare()
            if not self.warm[name].get("warm"):
                self.record({"kind": "finding", "finding": "MODEL_NOT_WARM", "model": name,
                             "reason": self.warm[name].get("reason", "")})
        self._task = asyncio.create_task(self._loop())
        return self.warm

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self.loaded:
            await self.engines[self.loaded].unload()
            self.loaded, self.state = None, EMPTY

    # ---- requests ----------------------------------------------------------------------------------------------
    async def acquire(self, model: str, priority: int = 0) -> Lease:
        if model not in self.cat.models:
            raise Refused(404, "model_not_offered", model)
        if self.state == SERVING and self.loaded == model:
            self.inflight[model] += 1
            return Lease(model, 0.0, self)
        w = Waiter(model, priority, self.clock(), asyncio.get_running_loop().create_future())
        self.waiters[model].append(w)
        self._kick.set()
        try:
            swap_ms = await asyncio.wait_for(asyncio.shield(w.fut), timeout=self.cat.policy.max_wait_s)
        except TimeoutError:
            if w.fut.done() and not w.fut.cancelled() and w.fut.exception() is None:
                return Lease(model, w.fut.result(), self)
            w.fut.cancel()
            raise Refused(429, "queue_timeout", model) from None
        finally:
            if w in self.waiters[model]:
                self.waiters[model].remove(w)
        return Lease(model, swap_ms, self)

    def _done(self, model: str) -> None:
        self.inflight[model] = max(0, self.inflight[model] - 1)
        self._kick.set()

    def snapshot(self) -> dict:
        return {"state": self.state, "loaded": self.loaded, "inflight": dict(self.inflight),
                "waiting": {m: sum(1 for w in ws if not w.fut.done()) for m, ws in self.waiters.items()}}

    # ---- scheduling ----------------------------------------------------------------------------------------------
    def _pending(self, model: str) -> list[Waiter]:
        return [w for w in self.waiters[model] if not w.fut.done()]

    def _score(self, model: str, now: float) -> float:
        return max((now - w.t0) * (1 + 1 / (1 + w.priority)) for w in self._pending(model))

    def _grant(self, model: str, swap_ms: float) -> None:
        for w in self._pending(model):
            self.inflight[model] += 1
            w.fut.set_result(swap_ms)

    async def _loop(self) -> None:
        while True:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._kick.wait(), timeout=self.tick_s)
            self._kick.clear()
            await self._step()

    async def _step(self) -> None:
        now, pol = self.clock(), self.cat.policy
        if self.state == SERVING and self._pending(self.loaded):
            self._grant(self.loaded, 0.0)  # queued while a postponed swap was draining
        wanted = [m for m in self.cat.models if m != self.loaded and self._pending(m)]
        if not wanted:
            return
        target = max(wanted, key=lambda m: (self._score(m, now), m))
        if self.loaded is None:
            await self._swap(None, target, "queue_age")
            return
        idle = self.inflight[self.loaded] == 0 and not self._pending(self.loaded)
        resident = now - self.loaded_since >= pol.min_residency_s
        oldest = max(now - w.t0 for w in self._pending(target))
        if resident and (idle or oldest >= pol.swap_after_wait_s):
            await self._swap(self.loaded, target, "idle" if idle else "queue_age")

    async def _swap(self, frm: str | None, to: str, trigger: str) -> None:
        pol, t0 = self.cat.policy, self.clock()
        ev = {"kind": "swap", "swap_id": uuid.uuid4().hex[:12], "from_model": frm, "to_model": to, "trigger": trigger,
              "waiting_requests": len(self._pending(to)), "drain_ms": 0.0, "unload_ms": 0.0, "load_ms": 0.0}
        if frm is not None:
            self.state = DRAINING
            while self.inflight[frm] > 0:
                if self.clock() - t0 > pol.drain_max_s:  # never cut a request off: postpone the swap
                    self.state = SERVING
                    self.record({**ev, "outcome": "DRAIN_TIMEOUT", "drain_ms": (self.clock() - t0) * 1000})
                    return
                self._kick.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._kick.wait(), timeout=self.tick_s)
            t1 = self.clock()
            ev["drain_ms"] = (t1 - t0) * 1000
            self.state = UNLOADING
            try:
                await self.engines[frm].unload()
            except Exception as exc:  # cannot free the GPU: stay on the current model, refuse nothing
                self.state = SERVING
                self.record({**ev, "outcome": "UNLOAD_FAILED", "error": f"{type(exc).__name__}"})
                return
            ev["unload_ms"] = (self.clock() - t1) * 1000
            self.loaded = None
        self.state, t2 = LOADING, self.clock()
        model = self.cat.models[to]
        try:
            res = await asyncio.wait_for(self.engines[to].load(), timeout=model.load_timeout_s)
            got = await self.engines[to].identity()
            diff = I.verify(model.identity, got)
            if diff:
                raise Refused(503, "model_unavailable", "IDENTITY_MISMATCH:" + ",".join(diff))
        except Exception as exc:
            outcome = "IDENTITY_MISMATCH" if isinstance(exc, Refused) else "LOAD_FAILED"
            with contextlib.suppress(Exception):
                await self.engines[to].unload()
            self.state, self.loaded = EMPTY, None
            for w in self._pending(to):
                w.fut.set_exception(Refused(503, "model_unavailable", f"{to}:{outcome}"))
            self.record({**ev, "outcome": outcome, "load_ms": (self.clock() - t2) * 1000, "identity_verified": False,
                         "error": f"{type(exc).__name__}"})
            return
        now = self.clock()
        ev.update(load_ms=(now - t2) * 1000, warm=bool((res or {}).get("warm")), identity_verified=True, outcome="OK")
        self.loaded, self.loaded_since, self.state = to, now, SERVING
        self._grant(to, (now - t0) * 1000)
        self.swaps = [t for t in self.swaps if now - t < 3600] + [now]
        self.record(ev)
        if len(self.swaps) > self.cat.policy.max_swaps_per_hour:
            self.record({"kind": "finding", "finding": "SWAP_RATE_HIGH", "swaps_last_hour": len(self.swaps)})
