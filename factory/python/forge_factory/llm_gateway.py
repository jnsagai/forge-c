"""Forge-C local LLM gateway (model-free, deterministic) between Fabro and local Ollama.

Why: Fabro 0.362 persists provider `reasoning` output in its run events, and Qwen3 on Ollama
thinks by default. FR-025 forbids requesting or storing hidden reasoning. This gateway:

* forces `reasoning_effort="none"` (Ollama => think=false) on every chat request;
* strips any `reasoning`/`reasoning_content`/`thinking` fields from responses and stream deltas;
* appends reported token usage (never estimated here) to a JSONL meter for T041;
* re-sends the identical request (bounded, FORGE_GATEWAY_DROP_RETRIES) when the upstream returned an empty
  answer for generated output (dropped tool call, ADR-0003 addendum); every attempt is metered.

It never calls a model on its own and holds no credentials. Bind loopback only.

CAPA-052 (h001, OD-2026-10-20-03): while the owner suspends the upstream's provider (config/factory/model-suspensions.yaml),
every request is refused here and never reaches the provider - Fabro's server-side run-title generation called the
suspended DeepSeek through this gateway once per run, outside the workflow graph that CAPA-051 guards.
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


_ROLE_RE = __import__("re").compile(r"skill_name\s+([a-z0-9][a-z0-9-]{2,40})")
_NATIVE_READ = {"use_skill", "read_file", "read_many_files", "grep", "glob", "list_dir", "update_plan"}
_NATIVE_WRITE = {"write_file", "edit_file", "apply_patch"}
_ROLE_TOOLS: dict[str, set[str]] | None = None


def role_tools() -> dict[str, set[str]]:
    """role -> tool names the role may be offered (MCP grants + safe natives). Enforcement stays in the hook."""
    global _ROLE_TOOLS
    if _ROLE_TOOLS is None:
        from .registry.agents import load_agents
        from .registry.mcp_registry import fabro_tool_name

        _ROLE_TOOLS = {a.id: {fabro_tool_name(t) for t in a.allowed_tools} | _NATIVE_READ
                       | (set() if a.readonly else _NATIVE_WRITE) for a in load_agents()[0]}
    return _ROLE_TOOLS


def detect_role(messages: list) -> str | None:
    for m in messages or []:
        if isinstance(m, dict) and m.get("role") in ("user", "system") and isinstance(m.get("content"), str):
            hit = _ROLE_RE.search(m["content"])
            if hit and hit.group(1) in role_tools():
                return hit.group(1)
    return None


def scope_tools(body: dict) -> dict:
    tools = body.get("tools")
    role = detect_role(body.get("messages") or [])
    if not isinstance(tools, list) or role is None:
        return body
    allowed = role_tools()[role]
    kept = [t for t in tools if isinstance(t, dict) and (t.get("function") or {}).get("name") in allowed]
    return {**body, "tools": kept}


def sanitize_request(body: dict) -> dict:
    body = scope_tools(body)
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


# Ollama 0.34 + qwen3 (no-think) sometimes returns neither content nor a tool call for a generated tool call
# (ADR-0005 #13). The identical client request is re-sent at most DROP_RETRIES times; every attempt is metered.
DROP_RETRIES = int(os.environ.get("FORGE_GATEWAY_DROP_RETRIES", "2"))


def dropped(usage: dict | None, shape: dict) -> bool:
    out = int((usage or {}).get("completion_tokens") or 0)
    return out > 32 and shape["content_chars"] == 0 and shape["tool_calls"] == 0


PRICES = {k: float(os.environ.get(f"FORGE_GATEWAY_PRICE_{k.upper()}_PER_M", "0")) for k in ("miss", "hit", "out")}
COST_CAP_USD = float(os.environ.get("FORGE_GATEWAY_COST_CAP_USD", "0"))  # 0 = no cap (local upstream)


def spent_usd(meter_path: Path) -> float:
    """Cost of every metered attempt from provider-reported usage (cache hits priced separately)."""
    total = 0.0
    for line in meter_path.read_text().splitlines() if meter_path.is_file() else []:
        r = json.loads(line)
        hit = int(r.get("tokens_cache_hit") or 0)
        miss = int(r.get("tokens_input") or 0) - hit
        total += (miss * PRICES["miss"] + hit * PRICES["hit"] + int(r.get("tokens_output") or 0) * PRICES["out"]) / 1e6
    return total


class Meter:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def refusal(self, model: str | None, reason: str) -> None:
        """CAPA-052: a request refused before any upstream call (no tokens, no cost)."""
        with self.path.open("a") as f:
            f.write(json.dumps({"ts_utc": utc_now(), "model": model or "unknown", "refused": reason,
                                "upstream_called": False}, sort_keys=True) + "\n")

    def record(self, model: str | None, usage: dict | None, stripped: bool, latency_ms: float,
               shape: dict | None = None) -> None:
        rec = {"ts_utc": utc_now(), "model": model or "unknown",
               "tokens_input": (usage or {}).get("prompt_tokens"),
               "tokens_output": (usage or {}).get("completion_tokens"),
               "tokens_cache_hit": (usage or {}).get("prompt_cache_hit_tokens"),
               "basis": "reported" if usage else "unknown",
               "reasoning_stripped": stripped, "latency_ms": round(latency_ms, 1)}
        if shape is not None:  # response shape only (never content): exposes upstream-dropped tool calls (ADR-0005)
            rec.update({"content_chars": shape["content_chars"], "tool_calls": shape["tool_calls"],
                        "finish_reason": shape.get("finish_reason"), "attempt": shape.get("attempt", 0),
                        "dropped_output": dropped(usage, shape)})
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")


PROVIDER_HOSTS = {"api.deepseek.com": "deepseek"}  # upstream host -> run-model provider (model-suspensions.yaml)


def suspended(upstream: str, path: Path | None = None) -> dict | None:
    """The owner's suspension of this upstream's provider, read on every request (lifting it needs no restart)."""
    from urllib.parse import urlparse

    from .workorder import suspension

    provider = PROVIDER_HOSTS.get(urlparse(upstream).hostname or "")
    return suspension(provider, path) if provider else None


def create_app(upstream: str = UPSTREAM, meter_path: Path | None = None,
               transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    app = FastAPI(title="forge-llm-gateway", docs_url=None, redoc_url=None, openapi_url=None)
    meter = Meter(meter_path or state_dir() / "llm-gateway" / "usage.jsonl")
    client = httpx.AsyncClient(base_url=upstream, timeout=httpx.Timeout(600.0, connect=10.0),
                               transport=transport)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "upstream": upstream}

    def refused(model: str | None) -> JSONResponse | None:
        s = suspended(upstream)
        if not s:
            return None
        meter.refusal(model, f"MODEL_SUSPENDED:{s['provider']}:{s['decision']}")
        return JSONResponse({"error": {"message": f"MODEL_SUSPENDED: {s['provider']} is suspended by the owner "
                                       f"({s['decision']}); the forge gateway did not call the provider",
                                       "type": "model_suspended"}}, status_code=503)

    @app.get("/v1/models")
    async def models() -> Response:
        if (r := refused(None)) is not None:
            return r
        r = await client.get("/v1/models")
        return Response(r.content, status_code=r.status_code, media_type="application/json")

    @app.post("/v1/chat/completions")
    @app.post("/chat/completions")
    async def chat(request: Request):
        if (r := refused(None)) is not None:  # CAPA-052: before reading the body, before any upstream call
            return r
        if COST_CAP_USD > 0 and spent_usd(meter.path) >= COST_CAP_USD:  # paid upstream: hard spend cap
            return JSONResponse({"error": {"message": f"forge gateway cost cap {COST_CAP_USD} USD reached",
                                           "type": "cost_cap"}}, status_code=429)
        auth = request.headers.get("authorization")  # the caller's credential is forwarded, never stored
        headers = {"Authorization": auth} if auth else None
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return JSONResponse({"error": {"message": "invalid JSON body"}}, status_code=400)
        body = sanitize_request(body)
        if body.get("stream"):
            body.setdefault("stream_options", {"include_usage": True})

            async def attempt() -> tuple[int, list[str], dict | None, bool, dict]:
                upstream_resp = await client.send(client.build_request("POST", "/v1/chat/completions", json=body,
                                                                       headers=headers),
                                                  stream=True)
                lines: list[str] = []
                usage, stripped = None, False
                shape: dict[str, Any] = {"content_chars": 0, "tool_calls": 0, "finish_reason": None}
                try:
                    async for line in upstream_resp.aiter_lines():
                        if line.startswith("data: ") and line[6:].strip() not in ("", "[DONE]"):
                            try:
                                chunk = json.loads(line[6:])
                            except ValueError:
                                lines.append(line + "\n")
                                continue
                            chunk, r = strip_reasoning(chunk)
                            stripped |= r
                            usage = chunk.get("usage") or usage
                            for ch in chunk.get("choices") or []:
                                delta = ch.get("delta") or {}
                                shape["content_chars"] += len(delta.get("content") or "")
                                shape["tool_calls"] += len(delta.get("tool_calls") or [])
                                shape["finish_reason"] = ch.get("finish_reason") or shape["finish_reason"]
                            lines.append("data: " + json.dumps(chunk, separators=(",", ":")) + "\n")
                        else:
                            lines.append(line + "\n")
                finally:
                    await upstream_resp.aclose()
                return upstream_resp.status_code, lines, usage, stripped, shape

            for n in range(DROP_RETRIES + 1):  # buffered so an empty (dropped) upstream answer can be retried
                t0 = time.monotonic()
                status, lines, usage, stripped, shape = await attempt()
                meter.record(body.get("model"), usage, stripped, (time.monotonic() - t0) * 1000, {**shape, "attempt": n})
                if status != 200 or not dropped(usage, shape):
                    break

            async def gen():
                for line in lines:
                    yield line

            return StreamingResponse(gen(), status_code=status, media_type="text/event-stream")
        for n in range(DROP_RETRIES + 1):
            t0 = time.monotonic()
            r = await client.post("/v1/chat/completions", json=body, headers=headers)
            try:
                data = r.json()
            except ValueError:
                return Response(r.content, status_code=r.status_code)
            data, stripped = strip_reasoning(data)
            nshape: dict[str, Any] | None = None
            if isinstance(data, dict) and data.get("choices"):
                ch = data["choices"][0]
                msg = ch.get("message") or {}
                nshape = {"content_chars": len(msg.get("content") or ""), "tool_calls": len(msg.get("tool_calls") or []),
                         "finish_reason": ch.get("finish_reason"), "attempt": n}
            usage = data.get("usage") if isinstance(data, dict) else None
            meter.record(body.get("model"), usage, stripped, (time.monotonic() - t0) * 1000, nshape)
            if r.status_code != 200 or nshape is None or not dropped(usage, nshape):
                break
        return JSONResponse(data, status_code=r.status_code)

    return app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=11436)
    ap.add_argument("--upstream", default=UPSTREAM)
    ap.add_argument("--meter", type=Path, default=None, help="usage JSONL (default state/llm-gateway/usage.jsonl)")
    a = ap.parse_args(argv)
    if a.host not in ("127.0.0.1", "::1", "localhost"):
        raise SystemExit("gateway must bind loopback")
    import uvicorn

    uvicorn.run(create_app(a.upstream, a.meter), host=a.host, port=a.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
