"""Feature 010 P1: single-request admission, cancellation and timing in the local gateway (LRTX-T009/T010)."""
from __future__ import annotations

import asyncio
import json

import httpx
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as gw
from forge_factory.lrtx import admission as la


def _never():
    async def f():
        return False
    return f


def test_one_at_a_time_with_observable_queue():
    async def scenario():
        adm = la.Admission(1, 4, 30, poll_s=0.01)
        order, tickets = [], []

        async def job(i):
            t = await adm.enter(_never())
            tickets.append(t)
            order.append(("in", i, adm.inflight))
            await asyncio.sleep(0.05)
            order.append(("out", i))
            adm.leave(t)
        await asyncio.gather(*(job(i) for i in range(3)))
        return adm, order, tickets
    adm, order, tickets = asyncio.run(scenario())
    assert all(o[2] == 1 for o in order if o[0] == "in")  # never two in flight
    assert [o[0] for o in order] == ["in", "out"] * 3
    assert sorted(t.depth_at_arrival for t in tickets) == [0, 1, 2] and max(t.wait_ms for t in tickets) >= 90
    assert adm.snapshot()["admitted"] == 3 and adm.inflight == 0


def test_backpressure_timeout_and_cancel_while_waiting_release_nothing_twice():
    async def scenario():
        adm = la.Admission(1, 1, 0.1, poll_s=0.01)
        holder = await adm.enter(_never())
        waiting = asyncio.ensure_future(adm.enter(_never()))
        await asyncio.sleep(0.02)
        full = await adm.enter(_never())  # queue (1) full
        timed_out = await waiting  # waited beyond max_wait_s
        gone = {"v": False}

        async def disc():
            return gone["v"]
        cancel = asyncio.ensure_future(la.Admission.enter(adm, disc))
        await asyncio.sleep(0.02)
        gone["v"] = True
        cancelled = await cancel
        adm.leave(holder)
        adm.leave(holder)  # idempotent
        fresh = await adm.enter(_never())
        return adm, full, timed_out, cancelled, fresh
    adm, full, timed_out, cancelled, fresh = asyncio.run(scenario())
    assert (full.refused, timed_out.refused, cancelled.refused, fresh.refused) == (
        "queue_full", "wait_timeout", "cancelled_waiting", None)
    assert adm.inflight == 1 and adm.sem.locked()


def test_running_request_is_cancelled_when_the_caller_disconnects():
    async def scenario():
        state = {"n": 0}

        async def disc():
            state["n"] += 1
            return state["n"] > 2

        async def slow():
            await asyncio.sleep(10)
        return await la.run_cancellable(slow(), disc, poll_s=0.01)
    assert asyncio.run(scenario()) == (None, True)


def _upstream(request: httpx.Request) -> httpx.Response:
    lines = [{"choices": [{"delta": {"content": "Hel"}}]},
             {"choices": [{"delta": {"content": "lo"}, "finish_reason": "stop"}],
              "usage": {"prompt_tokens": 50, "completion_tokens": 2}}]
    return httpx.Response(200, text="".join("data: " + json.dumps(x) + "\n\n" for x in lines) + "data: [DONE]\n\n",
                          headers={"content-type": "text/event-stream"})


def test_admitted_gateway_meters_queue_load_prefill_decode_and_resources(tmp_path, monkeypatch):
    monkeypatch.setattr(la, "loaded", lambda url, m: False)
    monkeypatch.setattr(la, "preload", lambda url, m: {"status": "OK", "load_ms": 1234.0})
    monkeypatch.setattr(la, "resources", lambda url=None: {"gpu": {"status": "UNKNOWN"}})
    meter = tmp_path / "u.jsonl"
    c = TestClient(gw.create_app("http://up", meter, transport=httpx.MockTransport(_upstream),
                                 admission=la.Admission(1, 2, 10)))
    r = c.post("/v1/chat/completions", json={"model": "qwen3:8b", "stream": True, "messages": []})
    assert r.status_code == 200 and "Hel" in r.text
    rec, res = [json.loads(x) for x in meter.read_text().splitlines()]
    loc = rec["local"]
    assert loc["model_loaded_before"] is False and loc["load"]["load_ms"] == 1234.0
    assert loc["queue_depth_at_arrival"] == 0 and loc["delta_chunks"] == 2 and isinstance(loc["prefill_ms"], float)
    assert "content" not in json.dumps(rec).replace("content_chars", "") and "resources_after" in res
    assert c.get("/health").json()["admission"]["admitted"] == 1


def test_gateway_without_admission_keeps_its_meter_format(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_GATEWAY_MAX_INFLIGHT", raising=False)
    meter = tmp_path / "u.jsonl"
    c = TestClient(gw.create_app("http://up", meter, transport=httpx.MockTransport(_upstream)))
    c.post("/v1/chat/completions", json={"model": "m", "stream": True, "messages": []})
    rec = json.loads(meter.read_text())
    assert "local" not in rec and "admission" not in c.get("/health").json()
    assert set(rec) == {"ts_utc", "model", "tokens_input", "tokens_output", "tokens_cache_hit", "basis",
                        "reasoning_stripped", "latency_ms", "content_chars", "tool_calls", "finish_reason", "attempt",
                        "dropped_output"}


def test_implausible_gpu_power_is_not_energy_data(monkeypatch):
    class R:
        stdout = "6696, 8188, 0, 590.01, 115.00, 57\n"
    monkeypatch.setattr(la.subprocess, "run", lambda *a, **k: R())
    g = la._nvidia()
    assert g["power_w"] is None and g["power_status"].startswith("UNKNOWN")
    R.stdout = "6696, 8188, 40, 54.2, 115.00, 60\n"
    assert la._nvidia()["power_w"] == 54.2
