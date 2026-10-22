"""LRTX-T009/T010: single-request admission for the local inference backend, plus per-request timing and resource
observations (LRTX-FR-006, FR-007).

Enabled only in a gateway started with FORGE_GATEWAY_MAX_INFLIGHT (scripts/forge_lrtx.sh); the existing gateways
(:11436 local, :11437 cloud) do not set it and keep their behaviour. Waiting is bounded (max_wait_s), the queue is
bounded (max_queue, then 429 backpressure), a caller that disconnects while queued or while its request runs is
dropped and its upstream request closed, so nothing accumulates behind the GPU.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Ticket:
    arrived: float
    depth_at_arrival: int
    admitted: float | None = None
    refused: str | None = None
    obs: dict = field(default_factory=dict)

    @property
    def wait_ms(self) -> float:
        return round(((self.admitted or time.monotonic()) - self.arrived) * 1000, 1)


class Admission:
    def __init__(self, max_inflight: int = 1, max_queue: int = 8, max_wait_s: float = 1800.0, poll_s: float = 0.5):
        self.sem = asyncio.Semaphore(max_inflight)
        self.max_inflight, self.max_queue, self.max_wait_s, self.poll_s = max_inflight, max_queue, max_wait_s, poll_s
        self.waiting = 0
        self.inflight = 0
        self.stats = {"admitted": 0, "queue_full": 0, "wait_timeout": 0, "cancelled_waiting": 0,
                      "cancelled_running": 0}

    def snapshot(self) -> dict:
        return {"max_inflight": self.max_inflight, "max_queue": self.max_queue, "max_wait_s": self.max_wait_s,
                "waiting": self.waiting, "inflight": self.inflight, **self.stats}

    async def enter(self, is_disconnected) -> Ticket:
        """Wait for the single slot. `is_disconnected` is the caller's async disconnect probe."""
        t = Ticket(time.monotonic(), self.waiting + self.inflight)
        if self.inflight >= self.max_inflight and self.waiting >= self.max_queue:
            self.stats["queue_full"] += 1
            t.refused = "queue_full"
            return t
        self.waiting += 1
        acquire = asyncio.ensure_future(self.sem.acquire())
        try:
            while True:
                done, _ = await asyncio.wait({acquire}, timeout=self.poll_s)
                if done:
                    break
                reason = None
                if await is_disconnected():
                    reason = "cancelled_waiting"
                elif time.monotonic() - t.arrived > self.max_wait_s:
                    reason = "wait_timeout"
                if reason:
                    acquire.cancel()
                    try:
                        await acquire
                    except asyncio.CancelledError:
                        pass
                    if acquire.done() and not acquire.cancelled():  # slot granted while cancelling: give it back
                        self.sem.release()
                    self.stats[reason] += 1
                    t.refused = reason
                    return t
        finally:
            self.waiting -= 1
        self.inflight += 1
        self.stats["admitted"] += 1
        t.admitted = time.monotonic()
        return t

    def leave(self, t: Ticket) -> None:
        if t.admitted is not None and t.refused != "released":
            self.inflight -= 1
            self.sem.release()
            t.refused = "released" if t.refused is None else t.refused


async def run_cancellable(coro, is_disconnected, poll_s: float = 0.5):
    """Run the upstream call; when the caller goes away the task is cancelled (its upstream connection closes, which
    stops generation in Ollama). Returns (result, cancelled)."""
    task = asyncio.ensure_future(coro)
    while True:
        done, _ = await asyncio.wait({task}, timeout=poll_s)
        if done:
            return task.result(), False
        if await is_disconnected():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001, S110 - the caller is gone either way
                pass
            return None, True


def from_env(env: dict[str, str] | None = None) -> Admission | None:
    env = dict(os.environ if env is None else env)
    if not env.get("FORGE_GATEWAY_MAX_INFLIGHT"):
        return None
    return Admission(int(env["FORGE_GATEWAY_MAX_INFLIGHT"]), int(env.get("FORGE_GATEWAY_MAX_QUEUE", "8")),
                     float(env.get("FORGE_GATEWAY_MAX_WAIT_S", "1800")))


# ---- resources (LRTX-FR-007): observed values only; anything not measurable is UNKNOWN -------------------------------

def _nvidia() -> dict:
    q = "memory.used,memory.total,utilization.gpu,power.draw,power.max_limit,temperature.gpu"
    try:
        out = subprocess.run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"], capture_output=True,
                             text=True, timeout=5).stdout.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return {"status": "UNKNOWN"}
    vals = [v.strip() for v in out.split(",")]

    def num(v: str) -> float | None:
        try:
            return float(v)
        except ValueError:
            return None
    used, total, util, power, limit, temp = (num(v) for v in vals)
    # the laptop driver reports implausible board power (e.g. 590 W on a ~100 W part): such readings are not energy data
    plausible = power is not None and limit is not None and 0 < power <= limit * 1.1
    return {"status": "OK", "mem_used_mib": used, "mem_total_mib": total, "util_pct": util, "temp_c": temp,
            "power_w": power if plausible else None,
            "power_status": "GPU_BOARD_REPORTED" if plausible else f"UNKNOWN (implausible reading {power} W, limit {limit} W)"}


def _meminfo() -> dict:
    try:
        kv = {ln.split(":")[0]: int(ln.split()[1]) for ln in Path("/proc/meminfo").read_text().splitlines()}
        psi = Path("/proc/pressure/memory").read_text().split()[1].split("=")[1] \
            if Path("/proc/pressure/memory").is_file() else None
    except (OSError, ValueError, IndexError):
        return {"status": "UNKNOWN"}
    return {"status": "OK", "mem_available_mib": kv["MemAvailable"] // 1024, "mem_total_mib": kv["MemTotal"] // 1024,
            "swap_used_mib": (kv["SwapTotal"] - kv["SwapFree"]) // 1024, "psi_some_avg10": float(psi) if psi else None}


def _residency(ollama_url: str) -> dict:
    try:
        with urllib.request.urlopen(ollama_url.rstrip("/") + "/api/ps", timeout=5) as r:  # noqa: S310 - loopback
            models = json.loads(r.read()).get("models") or []
    except (OSError, ValueError):
        return {"status": "UNKNOWN"}
    return {"status": "OK", "loaded": [{"name": m.get("name"), "size": m.get("size"), "size_vram": m.get("size_vram"),
                                        "vram_fraction": round(m["size_vram"] / m["size"], 3) if m.get("size") else None,
                                        "context_length": m.get("context_length")} for m in models]}


def resources(ollama_url: str | None = None) -> dict:
    out = {"ts": time.time(), "gpu": _nvidia(), "host": _meminfo(),
           "wall_energy": "UNKNOWN (no wall-power meter on this host)"}
    if ollama_url:
        out["residency"] = _residency(ollama_url)
    return out


def loaded(ollama_url: str, model: str) -> bool | None:
    r = _residency(ollama_url)
    return None if r["status"] != "OK" else any(m["name"] == model for m in r["loaded"])


def preload(ollama_url: str, model: str, keep_alive: str = "30m") -> dict:
    """Load the model explicitly (empty generate) so its load time is measured apart from prompt processing."""
    body = json.dumps({"model": model, "keep_alive": keep_alive}).encode()
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(ollama_url.rstrip("/") + "/api/generate", data=body,  # noqa: S310 - loopback
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:  # noqa: S310
            data = json.loads(r.read())
    except (OSError, ValueError) as exc:
        return {"status": "FAILED", "detail": str(exc)[:200], "wall_ms": round((time.monotonic() - t0) * 1000, 1)}
    wall = round((time.monotonic() - t0) * 1000, 1)
    if data.get("load_duration"):
        return {"status": "OK", "load_ms": round(data["load_duration"] / 1e6, 1), "wall_ms": wall,
                "basis": "ollama load_duration"}
    # Ollama 0.34 answers a prompt-less load with done_reason "load" and no durations: the wall clock is the load time
    return {"status": "OK", "load_ms": wall, "wall_ms": wall, "basis": "wall clock of the explicit load request",
            "done_reason": data.get("done_reason")}
