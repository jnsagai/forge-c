"""Feature 017 T028: the factory works against (a) the Forge-C tenant gateway and (b) a bare OpenAI-compatible
service with only /v1/models and chat (contracts/model-channel.md); on (b) identity is unattested."""
import asyncio
import hashlib

import httpx
from forge_factory.modelservice import client as K
from model_tier.catalog import Catalog, Model, SwapPolicy
from model_tier.shares import Shares, TenantShare
from model_tier.swap import SwapController
from model_tier.tenant_gateway import OutcomeLog, create_app

QWEN = "qwen3.6-35b-a3b-fp8"
IDENT = {"name": QWEN, "revision_fingerprint": "b" * 64, "precision": "fp8", "reasoning_mode": "off", "context_limit": 65536,
         "engine": {"name": "vllm", "version": "0.32.0"}, "attested": True}
PROFILE = {"mode": "external", "base_url": "http://svc/v1", "credential_ref": "forge-qual",
           "expected_identity": {QWEN: {"precision": "fp8", "reasoning_mode": "off", "min_context_limit": 65536}},
           "share": {"concurrency": 1, "queue_wait_max_s": 60}}


class Eng:
    async def prepare(self):
        return {"warm": True}

    async def load(self):
        return {"warm": True}

    async def unload(self):
        pass

    async def identity(self):
        return dict(IDENT)


def _tenant_gateway(tmp_path):
    cat = Catalog(site="t", gpu_vram_mib=49140, policy=SwapPolicy(1, 0, 0, 5, 99), models={QWEN: Model(
        model=QWEN, engine="vllm", launch_kind="compose", engine_url="http://eng", vram_mib=44000,
        full_capacity={"context_per_sequence": 65536, "sequences": 2}, reasoning_mode="off", identity=IDENT, load_timeout_s=5)})
    cfg = {"tenants": [{"tenant_id": "forge-qual", "key_sha256": hashlib.sha256(b"K").hexdigest(), "guaranteed_concurrency": 1,
                        "max_concurrency": 1, "queue_limit": 2, "queue_timeout_s": 5, "priority": 0, "max_context": 65536,
                        "reasoning_mode": "off", "enabled": True, "allowed_models": [QWEN]}]}
    ctl = SwapController(cat, {QWEN: Eng()}, tick_s=0.01)
    engine = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": []})))
    return create_app(cfg, cat, ctl, Shares([TenantShare("forge-qual", 1, 1, 2, 5, 0)], 2), http=engine, engine_key="E",
                      log=OutcomeLog(tmp_path / "o.jsonl"), start_controller=False)


def _sync_over_asgi(app):
    """A synchronous httpx transport that drives the ASGI app (the client under test is synchronous)."""
    asgi = httpx.ASGITransport(app=app)

    class T(httpx.BaseTransport):
        def handle_request(self, request):
            async def go():
                async with httpx.AsyncClient(transport=asgi, base_url="http://svc") as c:
                    r = await c.request(request.method, str(request.url), headers=request.headers, content=request.content)
                    return httpx.Response(r.status_code, headers=r.headers, content=r.content)
            return asyncio.run(go())
    return T()


def test_against_the_forge_tenant_gateway_identity_is_attested(tmp_path):
    c = K.ModelServiceClient(PROFILE, httpx.Client(transport=_sync_over_asgi(_tenant_gateway(tmp_path))), key=lambda: "K")
    got = c.preflight([QWEN])
    assert got[QWEN]["attested"] is True and got[QWEN]["revision_fingerprint"] == "b" * 64


def test_against_a_bare_openai_service_identity_is_unattested():
    def bare(req):
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"object": "list", "data": [{"id": QWEN, "object": "model", "max_model_len": 65536}]})
        return httpx.Response(404, json={"detail": "Not Found"})
    c = K.ModelServiceClient(PROFILE, httpx.Client(transport=httpx.MockTransport(bare)), key=lambda: "K")
    got = c.preflight([QWEN])
    assert got[QWEN]["attested"] is False and c.links[QWEN].state == K.PINNED
