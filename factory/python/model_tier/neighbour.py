"""Simulated second tenant: configurable synthetic load on an OpenAI-compatible endpoint (feature 017, FR-013, T036).

Prompts are generated from a fixed synthetic vocabulary; no real input is ever sent. The summary holds metadata
only (counts, status codes, latencies and the service's queue/swap headers), never prompt or reply text. The API key
is read from an environment variable named on the command line, never passed as an argument.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

import httpx

_WORDS = ("amber", "basalt", "cobalt", "delta", "ember", "fjord", "garnet", "harbor", "indigo", "juniper", "krypton",
          "lagoon", "meadow", "nimbus", "onyx", "prairie", "quartz", "ridge", "sierra", "tundra")


@dataclass
class NeighbourConfig:
    base_url: str
    api_key: str
    model: str
    concurrency: int
    prompt_tokens: int
    max_tokens: int
    duration_s: float

    def __post_init__(self) -> None:
        if self.concurrency < 1 or self.prompt_tokens < 1 or self.max_tokens < 1 or self.duration_s <= 0:
            raise ValueError("concurrency, prompt_tokens, max_tokens and duration_s must be positive")


def synthetic_prompt(n_tokens: int, seq: int) -> str:
    """About ``n_tokens`` synthetic words; ``seq`` varies the text so prefix caching does not hide the load."""
    return " ".join(_WORDS[(seq * 7 + i) % len(_WORDS)] for i in range(n_tokens))


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile; ``None`` for no values."""
    if not values:
        return None
    s = sorted(values)
    return s[max(0, math.ceil(q / 100 * len(s)) - 1)]


def _header_ms(headers: httpx.Headers, name: str) -> float | None:
    try:
        return float(headers[name]) if name in headers else None
    except ValueError:
        return None


async def run(cfg: NeighbourConfig, client: httpx.AsyncClient | None = None, clock: Callable[[], float] = time.monotonic) -> dict:
    """Send requests from ``cfg.concurrency`` workers until ``cfg.duration_s`` elapses; return a metadata summary."""
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    statuses: Counter[str] = Counter()
    latencies: list[float] = []
    queue_ms: list[float] = []
    swap_ms: list[float] = []
    seq = 0
    deadline = clock() + cfg.duration_s
    own = client is None
    http = client or httpx.AsyncClient(timeout=httpx.Timeout(max(60.0, cfg.duration_s)))

    async def worker() -> None:
        nonlocal seq
        while clock() < deadline:
            seq += 1
            body = {"model": cfg.model, "max_tokens": cfg.max_tokens,
                    "messages": [{"role": "user", "content": synthetic_prompt(cfg.prompt_tokens, seq)}]}
            t0 = clock()
            try:
                r = await http.post(url, json=body, headers=headers)
            except httpx.HTTPError:
                statuses["error"] += 1
                latencies.append((clock() - t0) * 1000)
                continue
            latencies.append((clock() - t0) * 1000)
            statuses[str(r.status_code)] += 1
            if (q := _header_ms(r.headers, "x-forge-queue-ms")) is not None:
                queue_ms.append(q)
            if (s := _header_ms(r.headers, "x-forge-swap-ms")) is not None:
                swap_ms.append(s)

    try:
        await asyncio.gather(*(worker() for _ in range(cfg.concurrency)))
    finally:
        if own:
            await http.aclose()
    return {
        "requests": sum(statuses.values()),
        "ok": sum(n for k, n in statuses.items() if k.startswith("2") and len(k) == 3),
        "by_status": dict(sorted(statuses.items())),
        "latency_ms": {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95), "max": max(latencies, default=None)},
        "queue_ms_p95": percentile(queue_ms, 95),
        "swap_ms_max": max(swap_ms, default=None),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI: run the neighbour and print the JSON summary. Exit 2 when the key variable is unset."""
    p = argparse.ArgumentParser(prog="model_tier.neighbour", description="Synthetic second-tenant load (FR-013)")
    p.add_argument("--base-url", required=True, help="OpenAI-compatible base URL, e.g. http://127.0.0.1:8000/v1")
    p.add_argument("--key-env", required=True, help="name of the environment variable holding the API key")
    p.add_argument("--model", required=True)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--prompt-tokens", type=int, default=512)
    p.add_argument("--max-tokens", type=int, default=128)
    p.add_argument("--duration", type=float, default=60.0, help="seconds")
    a = p.parse_args(argv)
    key = os.environ.get(a.key_env, "")
    if not key:
        print(json.dumps({"error": "KEY_ENV_UNSET", "key_env": a.key_env}), file=sys.stderr)
        return 2
    cfg = NeighbourConfig(a.base_url, key, a.model, a.concurrency, a.prompt_tokens, a.max_tokens, a.duration)
    print(json.dumps(asyncio.run(run(cfg)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
