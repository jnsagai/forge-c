"""Tenant gateway of the model service (feature 017; FR-008 to FR-013, FR-025 to FR-033; contracts/model-channel.md).

The only published entry to the models. It knows tenants, never factories: a tenant is a hashed API key, a share,
a priority, a context limit and the catalog models it may name. For every chat request it authenticates, checks
the model and the context, takes a slot of the tenant's share, asks the swap controller for the model (which may
swap, invisibly to the caller) and forwards to the engine with the engines' internal key. Replies carry the model's
identity prefix, the queue time and the swap time. The outcome log holds metadata only, never content (FR-012).

    python -m model_tier.tenant_gateway --config tenants.yaml --secrets FILE --listen 127.0.0.1:18480 --state DIR
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import json
import os
import stat
import time
import uuid
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from . import catalog as C
from .identity import short
from .shares import Refused, Shares, TenantShare
from .swap import SwapController

CONTEXT_WORDS = ("maximum context length", "context length", "too many tokens", "exceeds the context")


def read_secret(path: Path, name: str) -> str:
    """name=value lines in a file readable by its owner only (the model tier's own reader; no factory code)."""
    st = Path(path).stat()
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise RuntimeError("SECRETS_FILE_NOT_PRIVATE")
    for line in Path(path).read_text().splitlines():
        k, sep, v = line.partition("=")
        if sep and k.strip() == name and not k.strip().startswith("#"):
            return v.strip()
    raise RuntimeError(f"SECRET_NOT_FOUND:{name}")


def estimate_tokens(body: dict) -> int:
    """A deliberately low estimate (about 4 characters per token), so only clearly oversized requests are refused
    here; the engine enforces the exact limit and its refusal is mapped to the same reason."""
    text = json.dumps(body.get("messages") or [], ensure_ascii=False) + json.dumps(body.get("tools") or [], ensure_ascii=False)
    return len(text) // 4


def _err(status: int, reason: str, detail: str = "", headers: dict | None = None) -> JSONResponse:
    return JSONResponse({"error": {"type": reason, "forge_reason": reason, "message": detail or reason}}, status_code=status,
                        headers=headers)


class OutcomeLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch(mode=0o600)

    def write(self, rec: dict) -> None:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **rec}
        with open(self.path, "a") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")


def create_app(cfg: dict, cat: C.Catalog, controller: SwapController, shares: Shares, *, http: httpx.AsyncClient,
               engine_key: str | None, log: OutcomeLog, start_controller: bool = True) -> FastAPI:
    tenants = {t["tenant_id"]: t for t in cfg["tenants"]}
    for t in tenants.values():
        bad = [m for m in t["allowed_models"] if m not in cat.models]
        if bad:
            raise ValueError(f"TENANT_MODEL_NOT_IN_CATALOG:{t['tenant_id']}:{','.join(bad)}")
        if any(t["max_context"] > cat.models[m].context for m in t["allowed_models"]):
            raise ValueError(f"TENANT_CONTEXT_ABOVE_MODEL:{t['tenant_id']}")
    threshold = int(cfg.get("reasoning_finding_threshold", 3))
    reasoning_seen: dict[str, int] = {}
    eh = {"Authorization": f"Bearer {engine_key}"} if engine_key else {}

    @contextlib.asynccontextmanager
    async def lifespan(app):
        if start_controller:
            await controller.start()
        try:
            yield
        finally:
            if start_controller:
                await controller.close()

    app = FastAPI(title="forge-model-tier", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    def tenant_of(request: Request) -> dict | None:
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        h = hashlib.sha256(auth[7:].strip().encode()).hexdigest()
        found = None
        for t in tenants.values():
            if hmac.compare_digest(h, t["key_sha256"]):
                found = t
        return found if found and found.get("enabled", True) else None

    @app.get("/health")
    async def health():
        return {"status": "ok", "state": controller.state}

    @app.get("/v1/models")
    async def models(request: Request):
        t = tenant_of(request)
        if t is None:
            return _err(401, "credential_refused")
        return {"object": "list", "data": [{"id": m, "object": "model", "owned_by": "forge-model-tier",
                                            "max_model_len": cat.models[m].context} for m in t["allowed_models"]]}

    @app.get("/forge/v1/catalog")
    async def catalog_view(request: Request):
        t = tenant_of(request)
        if t is None:
            return _err(401, "credential_refused")
        return {"models": [{"model": m, "loaded": controller.loaded == m} for m in t["allowed_models"]]}

    @app.get("/forge/v1/identity")
    async def identity_view(request: Request, model: str):
        t = tenant_of(request)
        if t is None:
            return _err(401, "credential_refused")
        if model not in t["allowed_models"]:
            return _err(404, "model_not_offered", model)
        return {**cat.models[model].identity, "attested": True}

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        t0, rid = time.monotonic(), uuid.uuid4().hex[:16]
        t = tenant_of(request)
        rec = {"request_id": rid, "tenant_id": t["tenant_id"] if t else None}
        if t is None:
            log.write({**rec, "status": 401, "forge_reason": "credential_refused"})
            return _err(401, "credential_refused")
        try:
            body = await request.json()
        except ValueError:
            return _err(400, "invalid_request")
        name = body.get("model")
        rec["model"] = name
        if name not in t["allowed_models"]:
            log.write({**rec, "status": 404, "forge_reason": "model_not_offered"})
            return _err(404, "model_not_offered", str(name))
        m = cat.models[name]
        limit = min(int(t["max_context"]), m.context)
        if estimate_tokens(body) + int(body.get("max_tokens") or body.get("max_completion_tokens") or 0) > limit:
            log.write({**rec, "status": 400, "forge_reason": "context_exceeded"})
            return _err(400, "context_exceeded", f"limit {limit}")
        thinking_off = m.reasoning_mode == "off" or t.get("reasoning_mode") == "off"
        if thinking_off:
            body["chat_template_kwargs"] = {**(body.get("chat_template_kwargs") or {}), "enable_thinking": False}
        body["model"] = m.name_on_engine
        try:
            queue_ms = await shares.acquire(t["tenant_id"])
        except Refused as r:
            log.write({**rec, "status": r.status, "forge_reason": r.reason})
            return _err(r.status, r.reason)
        lease = None
        try:
            lease = await controller.acquire(name, int(t.get("priority", 0)))
        except Refused as r:
            shares.release(t["tenant_id"])
            log.write({**rec, "status": r.status, "forge_reason": r.reason, "queue_ms": round(queue_ms)})
            return _err(r.status, r.reason, r.detail)
        except BaseException:
            shares.release(t["tenant_id"])
            raise
        hdr = {"x-forge-model-identity": short(m.identity), "x-forge-queue-ms": str(round(queue_ms)),
               "x-forge-swap-ms": str(round(lease.swap_ms))}
        rec.update(model_fingerprint_prefix=short(m.identity), queue_ms=round(queue_ms), swap_wait_ms=round(lease.swap_ms))

        def done(status, usage=None, reason=None, reasoning=False):
            lease.release()
            shares.release(t["tenant_id"])
            u = usage or {}
            if reasoning and thinking_off:  # CAPA-240: reasoning text is expected when thinking is on
                reasoning_seen[name] = reasoning_seen.get(name, 0) + 1
                if reasoning_seen[name] == threshold:
                    log.write({"kind": "finding", "finding": "REASONING_CONTENT_WITH_THINKING_OFF", "model": name})
            log.write({**rec, "status": status, "forge_reason": reason, "total_ms": round((time.monotonic() - t0) * 1000),
                       "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
                       "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
                       "reasoning_content_seen": reasoning})

        url = m.engine_url + "/v1/chat/completions"
        if body.get("stream"):
            req = http.build_request("POST", url, json=body, headers=eh, timeout=None)
            try:
                up = await http.send(req, stream=True)
            except httpx.HTTPError:
                done(503, reason="model_unavailable")
                return _err(503, "model_unavailable", headers=hdr)

            async def relay():
                usage, seen = None, False
                try:
                    async for line in up.aiter_lines():
                        if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]"):
                            with contextlib.suppress(ValueError):
                                chunk = json.loads(line[5:])
                                usage = chunk.get("usage") or usage
                                seen = seen or any((c.get("delta") or {}).get("reasoning_content")
                                                   for c in chunk.get("choices") or [])
                        yield line + "\n"
                finally:
                    await up.aclose()
                    done(up.status_code, usage, reasoning=seen)
            return StreamingResponse(relay(), status_code=up.status_code, media_type="text/event-stream", headers=hdr)
        try:
            up = await http.post(url, json=body, headers=eh, timeout=None)
        except httpx.HTTPError:
            done(503, reason="model_unavailable")
            return _err(503, "model_unavailable", headers=hdr)
        try:
            data = up.json()
        except ValueError:
            data = None
        if up.status_code == 400 and any(w in up.text.lower() for w in CONTEXT_WORDS):
            done(400, reason="context_exceeded")
            return _err(400, "context_exceeded", headers=hdr)
        seen = bool(data) and any((c.get("message") or {}).get("reasoning_content") for c in data.get("choices") or [])
        done(up.status_code, (data or {}).get("usage"), reasoning=seen)
        return JSONResponse(data if data is not None else {"error": {"type": "engine_error"}}, status_code=up.status_code,
                            headers=hdr)

    return app


def shares_from(cfg: dict, cat: C.Catalog) -> Shares:
    return Shares([TenantShare(t["tenant_id"], t["guaranteed_concurrency"], t["max_concurrency"], t["queue_limit"],
                               t["queue_timeout_s"], t["priority"]) for t in cfg["tenants"] if t.get("enabled", True)],
                  total_slots=int(cfg.get("total_slots") or cat.max_sequences))  # engines queue beyond their own sequences


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    from .engines import build
    from .ramstage import RamStage

    ap = argparse.ArgumentParser(prog="model_tier.tenant_gateway")
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--secrets", required=True, type=Path)
    ap.add_argument("--listen", default="127.0.0.1:18480")
    ap.add_argument("--state", required=True, type=Path)
    a = ap.parse_args(argv)
    cfg = yaml.safe_load(a.config.read_text())
    C.validate(cfg, "tenant-config.schema.json")
    base = a.config.parent
    cat = C.load(base / cfg["catalog"], base / cfg["identity_lock"])
    pol = cat.policy
    ram = RamStage(Path(pol.stage_dir or "/dev/shm/forge-model-tier"), pol.ram_budget_gib, pol.ram_reserve_gib)
    key = read_secret(a.secrets, cfg["engine_key_ref"])
    os.environ.setdefault("FORGE_MODEL_TIER_ENGINE_KEY", key)  # read by the compose file of the engines
    log = OutcomeLog(a.state / cfg["outcome_log"])
    http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=None))
    engines = build(cat, http=http, ram=ram, engine_key=key, log_dir=a.state / "engine-logs")
    controller = SwapController(cat, engines, record=log.write)
    app = create_app(cfg, cat, controller, shares_from(cfg, cat), http=http, engine_key=key, log=log)
    host, port = a.listen.rsplit(":", 1)
    uvicorn.run(app, host=host, port=int(port), log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
