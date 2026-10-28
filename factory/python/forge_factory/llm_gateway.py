"""Forge-C local LLM gateway (model-free, deterministic) between Fabro and local Ollama.

Why: Fabro 0.362 persists provider `reasoning` output in its run events, and Qwen3 on Ollama
thinks by default. FR-025 forbids storing hidden reasoning. This gateway:

* sets `reasoning_effort="none"` (Ollama => think=false) on every chat request, except for the models a local profile
  names in `gateway.reasoning` (owner decision 2026-10-22, ADR-0015 addendum): a model that cannot answer with
  reasoning off (gpt-oss returns empty content) reasons at the profile's fixed effort, with extra output tokens for it;
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

        _ROLE_TOOLS = {
            a.id: {fabro_tool_name(t) for t in a.allowed_tools} | _NATIVE_READ | (set() if a.readonly else _NATIVE_WRITE)
            for a in load_agents(include_afo=True)[0]
        }
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


EFFORTS = ("low", "medium", "high", "xhigh")


def reasoning_policy() -> dict[str, dict]:
    """model -> {effort, extra_output_tokens} from FORGE_GATEWAY_REASONING (set by the local stack from its profile).
    Unset or invalid: no exception, every model reasons 'none' (the behaviour before the owner decision)."""
    try:
        pol = json.loads(os.environ.get("FORGE_GATEWAY_REASONING") or "{}")
    except ValueError:
        return {}
    return {m: v for m, v in pol.items() if isinstance(v, dict) and v.get("effort") in EFFORTS} if isinstance(pol, dict) else {}


def sanitize_request(body: dict, *, policy=None) -> dict:
    body = scope_tools(body)
    out = {k: v for k, v in body.items() if k not in ("reasoning", "think", "thinking")}
    pol = (reasoning_policy() if policy is None else policy).get(out.get("model"))
    out["reasoning_effort"] = pol["effort"] if pol else "none"
    if pol and pol.get("extra_output_tokens"):  # the reasoning would otherwise use up the answer's reserve
        for key in ("max_tokens", "max_completion_tokens"):
            if type(out.get(key)) is int and out[key] > 0:
                out[key] += int(pol["extra_output_tokens"])
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
            f.write(
                json.dumps(
                    {"ts_utc": utc_now(), "model": model or "unknown", "refused": reason, "upstream_called": False},
                    sort_keys=True,
                )
                + "\n"
            )

    def record_resources(self, model: str | None, resources: dict) -> None:
        """Feature 010 admission gateway: resource observation after a request (no tokens, no content)."""
        with self.path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps({"ts_utc": utc_now(), "model": model or "unknown", "resources_after": resources}, sort_keys=True)
                + "\n"
            )

    def record_sample(self, resources: dict) -> None:
        """Feature 010 admission gateway: periodic resource sample (no request, no content)."""
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts_utc": utc_now(), "sample": resources}, sort_keys=True) + "\n")

    def record(
        self,
        model: str | None,
        usage: dict | None,
        stripped: bool,
        latency_ms: float,
        shape: dict | None = None,
        local: dict | None = None,
    ) -> None:
        rec = {
            "ts_utc": utc_now(),
            "model": model or "unknown",
            "tokens_input": (usage or {}).get("prompt_tokens"),
            "tokens_output": (usage or {}).get("completion_tokens"),
            "tokens_cache_hit": (usage or {}).get("prompt_cache_hit_tokens"),
            "basis": "reported" if usage else "unknown",
            "reasoning_stripped": stripped,
            "latency_ms": round(latency_ms, 1),
        }
        if shape is not None:  # response shape only (never content): exposes upstream-dropped tool calls (ADR-0005)
            rec.update(
                {
                    "content_chars": shape["content_chars"],
                    "tool_calls": shape["tool_calls"],
                    "finish_reason": shape.get("finish_reason"),
                    "attempt": shape.get("attempt", 0),
                    "dropped_output": dropped(usage, shape),
                }
            )
        if local is not None:  # feature 010 admission gateway only: queue/load/prefill/decode timing, resources
            rec["local"] = local
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")


PROVIDER_HOSTS = {"api.deepseek.com": "deepseek"}  # upstream host -> run-model provider (model-suspensions.yaml)


def suspended(upstream: str, path: Path | None = None) -> dict | None:
    """The owner's suspension of this upstream's provider, read on every request (lifting it needs no restart)."""
    from urllib.parse import urlparse

    from .workorder import suspension

    provider = PROVIDER_HOSTS.get(urlparse(upstream).hostname or "")
    return suspension(provider, path) if provider else None


def create_app(
    upstream: str = UPSTREAM,
    meter_path: Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    admission: Any = None,
) -> FastAPI:
    """`admission` (feature 010, lrtx.admission.Admission; from FORGE_GATEWAY_MAX_INFLIGHT when not given) turns on the
    single-request queue, cancellation and timing; without it the gateway behaves as before."""
    if admission is None and os.environ.get("FORGE_GATEWAY_MAX_INFLIGHT"):
        from .lrtx import admission as lrtx_admission

        admission = lrtx_admission.from_env()
    adm = admission
    sample_s = float(os.environ.get("FORGE_GATEWAY_SAMPLE_S", "0")) if adm is not None else 0.0
    lifespan = None
    if sample_s > 0:  # feature 010: periodic resource samples (GPU power for energy integration)
        import asyncio
        import contextlib

        @contextlib.asynccontextmanager
        async def lifespan(_app):
            from .lrtx import admission as la

            async def loop() -> None:
                while True:
                    meter.record_sample(await asyncio.to_thread(la.resources, upstream.removesuffix("/v1")))
                    await asyncio.sleep(sample_s)

            task = asyncio.get_running_loop().create_task(loop())
            yield
            task.cancel()

    app = FastAPI(title="forge-llm-gateway", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    meter = Meter(meter_path or state_dir() / "llm-gateway" / "usage.jsonl")
    client = httpx.AsyncClient(base_url=upstream, timeout=httpx.Timeout(600.0, connect=10.0), transport=transport)
    # F014 (owner 2026-10-26: a runtime that serves parallel requests): a local profile may serve a model from its own
    # llama.cpp server with several request slots; that model's chat requests go there, every other model to Ollama
    routes = json.loads(os.environ.get("FORGE_GATEWAY_ROUTES") or "{}")
    routed = {m: httpx.AsyncClient(base_url=u.rstrip("/"), timeout=httpx.Timeout(600.0, connect=10.0), transport=transport)
              for m, u in routes.items()}

    def cl(body: dict | None) -> httpx.AsyncClient:
        return routed.get((body or {}).get("model"), client)

    @app.get("/health")
    async def health() -> dict:
        if adm is not None:
            return {"status": "ok", "upstream": upstream, "admission": adm.snapshot()}
        return {"status": "ok", "upstream": upstream}

    def refused(model: str | None) -> JSONResponse | None:
        s = suspended(upstream)
        if not s:
            return None
        meter.refusal(model, f"MODEL_SUSPENDED:{s['provider']}:{s['decision']}")
        return JSONResponse(
            {
                "error": {
                    "message": f"MODEL_SUSPENDED: {s['provider']} is suspended by the owner "
                    f"({s['decision']}); the forge gateway did not call the provider",
                    "type": "model_suspended",
                }
            },
            status_code=503,
        )

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
            return JSONResponse(
                {"error": {"message": f"forge gateway cost cap {COST_CAP_USD} USD reached", "type": "cost_cap"}}, status_code=429
            )
        auth = request.headers.get("authorization")  # the caller's credential is forwarded, never stored
        headers = {"Authorization": auth} if auth else None
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return JSONResponse({"error": {"message": "invalid JSON body"}}, status_code=400)
        binding = body.pop("forge_execution", None)
        native_id = request.headers.get("x-session-id")
        if binding is None and native_id and os.environ.get("FORGE_DURABLE_NATIVE_HEADER") == "1":
            # Enable only after pinned Fabro header propagation is measured on the actual local profile.
            import uuid

            from .afo.durable import Refused
            from .afo.product_job import from_native
            from .afo.queue import Store

            try:
                binding = {**from_native(Store(), native_id), "request_id": "native-request-" + uuid.uuid4().hex}
            except Refused as exc:
                return JSONResponse({"error": {"type": exc.code}}, status_code=429)
        body = sanitize_request(body)
        if binding is not None:
            return await durable_request(request, binding, body, headers)
        # Legacy calls retain their existing behavior, but cannot bypass a held durable native execution.
        from .afo.queue import Store, default_path

        if default_path().exists() or os.environ.get("FORGE_DURABLE_AUTONOMY") == "1":
            from .afo.request_admission import unbound_allowed

            if not unbound_allowed(Store()):
                return JSONResponse({"error": {"type": "durable_execution_busy_or_unbound"}}, status_code=429)
        if adm is not None:
            return await admitted(request, body, headers)
        if body.get("stream"):
            body.setdefault("stream_options", {"include_usage": True})

            async def attempt() -> tuple[int, list[str], dict | None, bool, dict]:
                upstream_resp = await cl(body).send(
                    cl(body).build_request("POST", "/v1/chat/completions", json=body, headers=headers), stream=True
                )
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
            r = await cl(body).post("/v1/chat/completions", json=body, headers=headers)
            try:
                data = r.json()
            except ValueError:
                return Response(r.content, status_code=r.status_code)
            data, stripped = strip_reasoning(data)
            nshape: dict[str, Any] | None = None
            if isinstance(data, dict) and data.get("choices"):
                ch = data["choices"][0]
                msg = ch.get("message") or {}
                nshape = {
                    "content_chars": len(msg.get("content") or ""),
                    "tool_calls": len(msg.get("tool_calls") or []),
                    "finish_reason": ch.get("finish_reason"),
                    "attempt": n,
                }
            usage = data.get("usage") if isinstance(data, dict) else None
            meter.record(body.get("model"), usage, stripped, (time.monotonic() - t0) * 1000, nshape)
            if r.status_code != 200 or nshape is None or not dropped(usage, nshape):
                break
        return JSONResponse(data, status_code=r.status_code)

    async def durable_request(request, binding, body, headers):
        from .afo import request_admission as durable
        from .afo.durable import Refused
        from .afo.queue import Store

        store = Store()
        try:
            rec = durable.reserve(store, binding, body)
        except (Refused, KeyError, ValueError) as exc:
            code = exc.code if isinstance(exc, Refused) else "INVALID_DURABLE_BINDING"
            meter.refusal(body.get("model"), code)
            return JSONResponse({"error": {"type": code}}, status_code=429)
        # No transparent retry: each new generation needs its own durable reservation.
        usage, completed, started = None, False, False
        ticket = None
        try:
            if adm is not None:
                ticket = await adm.enter(request.is_disconnected)
                if ticket.refused:
                    return JSONResponse({"error": {"type": "admission_" + ticket.refused}}, status_code=429)
            durable.start(store, rec, body)
            started = True
            status, payload, usage, stripped, shape, timing = await _timed(body, headers, bool(body.get("stream")))
            # A complete provider response with a finish reason is generation quiescence; transport close is not.
            completed = status == 200 and shape.get("finish_reason") is not None
            meter.record(
                body.get("model"),
                usage,
                stripped,
                timing.get("total_ms", 0),
                shape,
                {"request_id": rec["request_id"], "mission_id": rec["mission_id"]},
            )
            if body.get("stream"):

                async def chunks():
                    for line in payload:
                        yield line

                return StreamingResponse(chunks(), status_code=status, media_type="text/event-stream")
            return (
                JSONResponse(payload, status_code=status)
                if isinstance(payload, (dict, list))
                else Response(payload, status_code=status)
            )
        except Refused as exc:
            meter.refusal(body.get("model"), exc.code)
            return JSONResponse({"error": {"type": exc.code}}, status_code=429)
        except httpx.HTTPError:
            meter.refusal(body.get("model"), "PROVIDER_REQUEST_OUTCOME_UNKNOWN")
            return JSONResponse({"error": {"type": "PROVIDER_REQUEST_OUTCOME_UNKNOWN"}}, status_code=502)
        finally:
            durable.reconcile(store, rec["request_id"], usage, completed=completed or not started)
            if ticket is not None and not ticket.refused:
                adm.leave(ticket)

    async def admitted(request: Request, body: dict, headers: dict | None):
        """Feature 010 (LRTX-FR-006/FR-007): one request at a time, bounded waiting, cancellation, separate timings.
        Streaming responses stay fully buffered so an empty (dropped) answer is retried before anything reaches the
        caller - partial tool calls are never forwarded and then replayed."""
        import asyncio

        from .lrtx import admission as la

        model = body.get("model")
        ticket = await adm.enter(request.is_disconnected)
        if ticket.refused:
            meter.refusal(model, f"ADMISSION_{ticket.refused.upper()}")
            return JSONResponse(
                {"error": {"message": f"forge gateway admission: {ticket.refused}", "type": "admission_" + ticket.refused}},
                status_code=429 if ticket.refused == "queue_full" else 503,
            )
        try:
            ollama = upstream.removesuffix("/v1")
            if model in routed:  # a resident llama.cpp server: no Ollama load state, nothing to preload
                was_loaded, load = True, None
            else:
                was_loaded = await asyncio.to_thread(la.loaded, ollama, model) if model else None
                load = await asyncio.to_thread(la.preload, ollama, model) if was_loaded is False else None
            before = await asyncio.to_thread(la.resources, ollama)
            stream = bool(body.get("stream"))
            if stream:
                body.setdefault("stream_options", {"include_usage": True})
            status, payload, usage = 0, None, None
            for n in range(DROP_RETRIES + 1):
                t0 = time.monotonic()
                res, cancelled = await la.run_cancellable(_timed(body, headers, stream), request.is_disconnected)
                if cancelled:
                    adm.stats["cancelled_running"] += 1
                    meter.refusal(model, "ADMISSION_CANCELLED_RUNNING")
                    return Response(status_code=499)
                status, payload, usage, stripped, shape, timing = res
                local = {
                    "queue_wait_ms": ticket.wait_ms,
                    "queue_depth_at_arrival": ticket.depth_at_arrival,
                    "model_loaded_before": was_loaded,
                    "load": load if n == 0 else None,
                    **timing,
                    "resources_before": before if n == 0 else None,
                    **({"served_by": "llama-server"} if model in routed else {}),
                }
                meter.record(model, usage, stripped, (time.monotonic() - t0) * 1000, {**shape, "attempt": n}, local)
                if status != 200 or not dropped(usage, shape):
                    break
            after = await asyncio.to_thread(la.resources, ollama)
            meter.record_resources(model, after)
        finally:
            adm.leave(ticket)
        if stream:

            async def gen():
                for line in payload:
                    yield line

            return StreamingResponse(gen(), status_code=status, media_type="text/event-stream")
        return (
            JSONResponse(payload, status_code=status)
            if isinstance(payload, dict | list)
            else Response(payload, status_code=status)
        )

    async def _timed(body: dict, headers: dict | None, stream: bool):
        """One upstream attempt with wall-clock phases: time to first generated delta (prompt processing; the model is
        already loaded) and generation (first to last delta). Tool calls that arrive in a single final chunk make the
        split unobservable: decode_ms is then UNKNOWN."""
        t0 = time.monotonic()
        shape: dict[str, Any] = {"content_chars": 0, "tool_calls": 0, "finish_reason": None}
        if not stream:
            r = await cl(body).post("/v1/chat/completions", json=body, headers=headers)
            total = (time.monotonic() - t0) * 1000
            try:
                data = r.json()
            except ValueError:
                return r.status_code, r.content, None, False, shape, {"total_ms": round(total, 1)}
            data, stripped = strip_reasoning(data)
            if isinstance(data, dict) and data.get("choices"):
                ch = data["choices"][0]
                msg = ch.get("message") or {}
                shape = {
                    "content_chars": len(msg.get("content") or ""),
                    "tool_calls": len(msg.get("tool_calls") or []),
                    "finish_reason": ch.get("finish_reason"),
                }
            usage = data.get("usage") if isinstance(data, dict) else None
            return (
                r.status_code,
                data,
                usage,
                stripped,
                shape,
                {"total_ms": round(total, 1), "prefill_ms": "UNKNOWN (non-streaming)", "decode_ms": "UNKNOWN (non-streaming)"},
            )
        up = cl(body)
        resp = await up.send(up.build_request("POST", "/v1/chat/completions", json=body, headers=headers), stream=True)
        lines: list[str] = []
        usage, stripped, first, last, deltas = None, False, None, None, 0
        try:
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line[6:].strip() not in ("", "[DONE]"):
                    try:
                        chunk = json.loads(line[6:])
                    except ValueError:
                        lines.append(line + "\n")
                        continue
                    chunk, r_ = strip_reasoning(chunk)
                    stripped |= r_
                    usage = chunk.get("usage") or usage
                    for ch in chunk.get("choices") or []:
                        delta = ch.get("delta") or {}
                        if delta.get("content") or delta.get("tool_calls"):
                            now = time.monotonic()
                            first = first or now
                            last = now
                            deltas += 1
                        shape["content_chars"] += len(delta.get("content") or "")
                        shape["tool_calls"] += len(delta.get("tool_calls") or [])
                        shape["finish_reason"] = ch.get("finish_reason") or shape["finish_reason"]
                    lines.append("data: " + json.dumps(chunk, separators=(",", ":")) + "\n")
                else:
                    lines.append(line + "\n")
        finally:
            await resp.aclose()
        end = time.monotonic()
        ms = lambda a, b: round((b - a) * 1000, 1)  # noqa: E731
        timing = {
            "total_ms": ms(t0, end),
            "first_delta_ms": ms(t0, first) if first else None,
            "delta_chunks": deltas,
            "prefill_ms": ms(t0, first)
            if first and deltas > 1
            else "UNKNOWN (answer arrived in one chunk: the first-delta time includes generation)",
            "decode_ms": ms(first, last) if first and deltas > 1 else "UNKNOWN (single final chunk)",
            "basis": "gateway wall clock around the upstream stream; model preloaded separately",
        }
        out = int((usage or {}).get("completion_tokens") or 0)
        if first and deltas > 1 and last > first:
            timing["decode_tokens_per_s"] = round(out / (last - first), 2)
        inp = int((usage or {}).get("prompt_tokens") or 0)
        if first and first > t0 and deltas > 1:
            timing["prefill_tokens_per_s"] = round(inp / (first - t0), 1)
        return resp.status_code, lines, usage, stripped, shape, timing

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
