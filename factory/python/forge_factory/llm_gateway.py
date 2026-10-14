"""Forge-C local LLM gateway (model-free, deterministic) between Fabro and local Ollama.

Why: Fabro 0.362 persists provider `reasoning` output in its run events, and Qwen3 on Ollama
thinks by default. FR-025 forbids requesting or storing hidden reasoning. This gateway:

* forces `reasoning_effort="none"` (Ollama => think=false) on every chat request;
* strips any `reasoning`/`reasoning_content`/`thinking` fields from responses and stream deltas;
* appends reported token usage (never estimated here) to a JSONL meter for T041.

It never calls a model on its own and holds no credentials. Bind loopback only.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .common import state_dir, utc_now

REASONING_KEYS = ("reasoning", "reasoning_content", "thinking", "reasoning_details")
UPSTREAM = os.environ.get("FORGE_OLLAMA_URL", "http://127.0.0.1:11435").rstrip("/")


def sanitize_request(body: dict) -> dict:
    out = {k: v for k, v in body.items() if k not in ("reasoning", "think", "thinking")}
    out["reasoning_effort"] = "none"
    msgs = []
    for m in out.get("messages") or []:
        if isinstance(m, dict):
            m = {k: v for k, v in m.items() if k not in REASONING_KEYS}
        msgs.append(m)
    if "messages" in out:
        out["messages"] = msgs
    return out


def strip_reasoning(obj: Any) -> tuple[Any, bool]:
    """Recursively drop reasoning keys. Returns (clean_obj, removed_any)."""
    removed = False
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            if k in REASONING_KEYS:
                removed = True
                continue
            cv, r = strip_reasoning(v)
            removed |= r
            clean[k] = cv
        return clean, removed
    if isinstance(obj, list):
        items = []
        for v in obj:
            cv, r = strip_reasoning(v)
            removed |= r
            items.append(cv)
        return items, removed
    return obj, False


class Meter:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, model: str | None, usage: dict | None, stripped: bool, latency_ms: float) -> None:
        rec = {"ts_utc": utc_now(), "model": model or "unknown",
               "tokens_input": (usage or {}).get("prompt_tokens"),
               "tokens_output": (usage or {}).get("completion_tokens"),
               "basis": "reported" if usage else "unknown",
               "reasoning_stripped": stripped, "latency_ms": round(latency_ms, 1)}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")


def create_app(upstream: str = UPSTREAM, meter_path: Path | None = None,
               transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    app = FastAPI(title="forge-llm-gateway", docs_url=None, redoc_url=None, openapi_url=None)
    meter = Meter(meter_path or state_dir() / "llm-gateway" / "usage.jsonl")
    client = httpx.AsyncClient(base_url=upstream, timeout=httpx.Timeout(600.0, connect=10.0),
                               transport=transport)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "upstream": upstream}

    @app.get("/v1/models")
    async def models() -> Response:
        r = await client.get("/v1/models")
        return Response(r.content, status_code=r.status_code, media_type="application/json")

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return JSONResponse({"error": {"message": "invalid JSON body"}}, status_code=400)
        body = sanitize_request(body)
        started = time.monotonic()
        if body.get("stream"):
            body.setdefault("stream_options", {"include_usage": True})
            req = client.build_request("POST", "/v1/chat/completions", json=body)
            upstream_resp = await client.send(req, stream=True)

            async def gen():
                usage, stripped = None, False
                try:
                    async for line in upstream_resp.aiter_lines():
                        if line.startswith("data: ") and line[6:].strip() not in ("", "[DONE]"):
                            try:
                                chunk = json.loads(line[6:])
                            except ValueError:
                                yield line + "\n"
                                continue
                            chunk, r = strip_reasoning(chunk)
                            stripped |= r
                            usage = chunk.get("usage") or usage
                            yield "data: " + json.dumps(chunk, separators=(",", ":")) + "\n"
                        else:
                            yield line + "\n"
                finally:
                    await upstream_resp.aclose()
                    meter.record(body.get("model"), usage, stripped, (time.monotonic() - started) * 1000)

            return StreamingResponse(gen(), status_code=upstream_resp.status_code,
                                     media_type="text/event-stream")
        r = await client.post("/v1/chat/completions", json=body)
        try:
            data = r.json()
        except ValueError:
            return Response(r.content, status_code=r.status_code)
        data, stripped = strip_reasoning(data)
        meter.record(body.get("model"), data.get("usage") if isinstance(data, dict) else None, stripped,
                     (time.monotonic() - started) * 1000)
        return JSONResponse(data, status_code=r.status_code)

    return app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=11436)
    ap.add_argument("--upstream", default=UPSTREAM)
    a = ap.parse_args(argv)
    if a.host not in ("127.0.0.1", "::1", "localhost"):
        raise SystemExit("gateway must bind loopback")
    import uvicorn

    uvicorn.run(create_app(a.upstream), host=a.host, port=a.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
