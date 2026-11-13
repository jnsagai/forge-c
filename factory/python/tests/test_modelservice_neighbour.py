"""Feature 017 T036: simulated second tenant (FR-013), metadata only, synthetic prompts only."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from model_tier import neighbour as N


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def cfg(**kw):
    base = {"base_url": "http://svc/v1/", "api_key": "sk-neighbour", "model": "m1", "concurrency": 1, "prompt_tokens": 16,
            "max_tokens": 8, "duration_s": 5.0}
    return N.NeighbourConfig(**{**base, **kw})


def go(c, handler, clock):
    async def inner():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await N.run(c, client=client, clock=clock)
    return asyncio.run(inner())


def test_counts_status_headers_and_stop_at_duration():
    clock, seen = Clock(), []
    plan = [(200, {"x-forge-queue-ms": "5"}), (429, {}), (200, {"x-forge-queue-ms": "40", "x-forge-swap-ms": "12000"}),
            (503, {}), (200, {"x-forge-swap-ms": "bogus"})]

    async def handler(req: httpx.Request):
        seen.append(req)
        status, hdr = plan[len(seen) - 1]
        clock.t += 1.0  # each request takes 1 s; duration 5 s -> exactly 5 requests
        return httpx.Response(status, headers=hdr, json={"choices": [{"message": {"content": "reply text"}}]})

    s = go(cfg(), handler, clock)
    assert s["requests"] == 5 == len(seen)
    assert s["ok"] == 3
    assert s["by_status"] == {"200": 3, "429": 1, "503": 1}
    assert s["latency_ms"] == {"p50": 1000.0, "p95": 1000.0, "max": 1000.0}
    assert s["queue_ms_p95"] == 40.0
    assert s["swap_ms_max"] == 12000.0
    req = seen[0]
    assert str(req.url) == "http://svc/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer sk-neighbour"
    body = json.loads(req.content)
    assert body["model"] == "m1" and body["max_tokens"] == 8
    assert len(body["messages"][0]["content"].split()) == 16
    dumped = json.dumps(s)
    assert "reply text" not in dumped and "sk-neighbour" not in dumped and "amber" not in dumped


def test_concurrency_and_errors():
    clock, n = Clock(), {"v": 0}

    async def handler(req):
        n["v"] += 1
        i = n["v"]
        await asyncio.sleep(0)  # let the workers interleave
        clock.t += 0.5
        if i % 4 == 0:
            raise httpx.ConnectError("down", request=req)
        return httpx.Response(200)

    s = go(cfg(concurrency=3, duration_s=3.0), handler, clock)
    assert s["requests"] == n["v"] and s["requests"] >= 6
    assert s["by_status"]["error"] == n["v"] // 4
    assert s["ok"] == s["requests"] - s["by_status"]["error"]
    assert s["queue_ms_p95"] is None and s["swap_ms_max"] is None


def test_no_request_after_deadline():
    clock = Clock()

    async def handler(req):
        clock.t += 10.0
        return httpx.Response(200)

    assert go(cfg(duration_s=5.0), handler, clock)["requests"] == 1


def test_percentile_math():
    v = [float(x) for x in range(1, 101)]
    assert N.percentile(v, 50) == 50.0 and N.percentile(v, 95) == 95.0 and N.percentile(v, 100) == 100.0
    assert N.percentile([3.0, 1.0, 2.0], 50) == 2.0
    assert N.percentile([7.0], 95) == 7.0
    assert N.percentile([], 95) is None


def test_synthetic_prompts_vary_and_are_synthetic():
    a, b = N.synthetic_prompt(32, 1), N.synthetic_prompt(32, 2)
    assert a != b and len(a.split()) == 32
    assert set(a.split()) <= set(N._WORDS)


@pytest.mark.parametrize("bad", [{"concurrency": 0}, {"prompt_tokens": 0}, {"max_tokens": 0}, {"duration_s": 0}])
def test_config_validation(bad):
    with pytest.raises(ValueError):
        cfg(**bad)


def test_main_key_from_env_only(monkeypatch, capsys):
    monkeypatch.delenv("NEIGHBOUR_KEY", raising=False)
    args = ["--base-url", "http://svc/v1", "--key-env", "NEIGHBOUR_KEY", "--model", "m1", "--duration", "1"]
    assert N.main(args) == 2
    assert "KEY_ENV_UNSET" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        N.main([*args, "--api-key", "sk-x"])

    captured = {}

    async def fake_run(c, client=None, clock=None):
        captured["cfg"] = c
        return {"requests": 0, "ok": 0, "by_status": {}, "latency_ms": {}, "queue_ms_p95": None, "swap_ms_max": None}

    monkeypatch.setenv("NEIGHBOUR_KEY", "sk-from-env")
    monkeypatch.setattr(N, "run", fake_run)
    assert N.main([*args, "--concurrency", "2", "--prompt-tokens", "64", "--max-tokens", "4"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["requests"] == 0
    c = captured["cfg"]
    assert (c.api_key, c.concurrency, c.prompt_tokens, c.max_tokens, c.duration_s) == ("sk-from-env", 2, 64, 4, 1.0)
