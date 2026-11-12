"""Feature 017 T026: the tenant gateway (FR-008 to FR-013, FR-025 to FR-030, contracts/model-channel.md)."""
import asyncio
import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from model_tier.catalog import Catalog, Model, SwapPolicy
from model_tier.swap import SwapController
from model_tier.tenant_gateway import OutcomeLog, create_app, read_secret, shares_from

A, B = "ornith-1.5-35b-a3b-q8", "qwen3.6-35b-a3b-fp8"
KEYS = {"factory-a": "KEY-A-0001", "factory-b": "KEY-B-0002", "neighbour": "KEY-N-0003", "off": "KEY-OFF"}


def ident(name, fp, mode):
    return {"name": name, "revision_fingerprint": fp * 64, "precision": "fp8" if name == B else "other",
            "reasoning_mode": mode, "context_limit": 65536, "engine": {"name": "x", "version": "1"}, "attested": True}


def catalog():
    models = {
        A: Model(model=A, engine="llama.cpp", launch_kind="process", engine_url="http://eng-a", vram_mib=42000,
                 full_capacity={"context_per_sequence": 65536, "sequences": 4}, reasoning_mode="on",
                 identity=ident(A, "a", "on"), load_timeout_s=5, served_name="ornith"),
        B: Model(model=B, engine="vllm", launch_kind="compose", engine_url="http://eng-b", vram_mib=44000,
                 full_capacity={"context_per_sequence": 65536, "sequences": 2}, reasoning_mode="off",
                 identity=ident(B, "b", "off"), load_timeout_s=5)}
    return Catalog(site="t", gpu_vram_mib=49140, models=models,
                   policy=SwapPolicy(drain_max_s=2, min_residency_s=0, swap_after_wait_s=0, max_wait_s=3, max_swaps_per_hour=99))


def tenant(tid, models=(A, B), **kw):
    t = {"tenant_id": tid, "key_sha256": hashlib.sha256(KEYS[tid].encode()).hexdigest(), "guaranteed_concurrency": 0,
         "max_concurrency": 2, "queue_limit": 4, "queue_timeout_s": 3, "priority": 0, "max_context": 65536,
         "reasoning_mode": "on", "enabled": True, "allowed_models": list(models)}
    t.update(kw)
    return t


class Eng:
    def __init__(self, name, gpu):
        self.name, self.gpu = name, gpu

    async def prepare(self):
        return {"warm": True}

    async def load(self):
        self.gpu.add(self.name)
        return {"warm": True}

    async def unload(self):
        self.gpu.discard(self.name)

    async def identity(self):
        return ident(self.name, "a" if self.name == A else "b", "on" if self.name == A else "off")


def make(tmp_path, tenants=None, engine_reply=None):
    cat, gpu, seen = catalog(), set(), []

    def engine(req):
        body = json.loads(req.content)
        seen.append({"host": req.url.host, "auth": req.headers.get("authorization"), "body": body})
        if engine_reply:
            return engine_reply(req, body)
        if body.get("stream"):
            chunks = ['data: {"choices":[{"delta":{"content":"hi"}}]}', 'data: {"choices":[],"usage":{"prompt_tokens":5,'
                      '"completion_tokens":1}}', "data: [DONE]"]
            return httpx.Response(200, text="\n\n".join(chunks) + "\n\n", headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={"choices": [{"message": {"content": f"answer from {req.url.host}"}}],
                                         "usage": {"prompt_tokens": 11, "completion_tokens": 3}})
    http = httpx.AsyncClient(transport=httpx.MockTransport(engine))
    cfg = {"tenants": tenants or [tenant("factory-a"), tenant("factory-b", guaranteed_concurrency=1), tenant("neighbour", (B,))],
           "reasoning_finding_threshold": 2}
    log = OutcomeLog(tmp_path / "outcomes.jsonl")
    ctl = SwapController(cat, {m: Eng(m, gpu) for m in cat.models}, record=log.write, tick_s=0.01)
    app = create_app(cfg, cat, ctl, shares_from(cfg, cat), http=http, engine_key="ENGINE-INTERNAL", log=log)
    return app, seen, tmp_path / "outcomes.jsonl", ctl


def H(tid):
    return {"Authorization": f"Bearer {KEYS[tid]}"}


def chat(model, **kw):
    return {"model": model, "messages": [{"role": "user", "content": "SECRET-PROMPT-TEXT"}], "max_tokens": 64, **kw}


def test_authentication_and_model_listing(tmp_path):
    app, seen, _, _ = make(tmp_path)
    with TestClient(app) as c:
        assert c.post("/v1/chat/completions", json=chat(B)).status_code == 401
        r = c.post("/v1/chat/completions", json=chat(B), headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401 and r.json()["error"]["forge_reason"] == "credential_refused"
        assert seen == []  # FR-009: no model work without a valid credential
        assert [m["id"] for m in c.get("/v1/models", headers=H("neighbour")).json()["data"]] == [B]
        ident_b = c.get("/forge/v1/identity", params={"model": B}, headers=H("factory-a")).json()
        assert ident_b["revision_fingerprint"] == "b" * 64 and ident_b["attested"] is True
        assert c.get("/forge/v1/identity", params={"model": A}, headers=H("neighbour")).status_code == 404


def test_swap_is_invisible_and_answers_come_from_the_named_model(tmp_path):
    app, seen, log, _ = make(tmp_path)
    with TestClient(app) as c:
        out = []
        for m in (A, B, A):
            r = c.post("/v1/chat/completions", json=chat(m), headers=H("factory-a"))
            assert r.status_code == 200
            out.append((r.json()["choices"][0]["message"]["content"], r.headers["x-forge-model-identity"],
                        int(r.headers["x-forge-swap-ms"]) >= 0))
    assert out == [("answer from eng-a", "a" * 16, True), ("answer from eng-b", "b" * 16, True),
                   ("answer from eng-a", "a" * 16, True)]
    assert seen[0]["body"]["model"] == "ornith" and seen[1]["body"]["model"] == B  # engine names from the catalog
    assert all(s["auth"] == "Bearer ENGINE-INTERNAL" for s in seen)  # engines use the internal key, never a tenant key
    assert seen[1]["body"]["chat_template_kwargs"] == {"enable_thinking": False}  # catalog: Qwen3.6 non-thinking
    assert "chat_template_kwargs" not in seen[0]["body"]  # Ornith keeps its own reasoning setting
    text = log.read_text()
    assert "SECRET-PROMPT-TEXT" not in text and "answer from" not in text  # FR-012: metadata only
    recs = [json.loads(x) for x in text.splitlines()]
    assert sum(1 for r in recs if r.get("kind") == "swap") == 3
    assert all("prompt_tokens" in r for r in recs if r.get("status") == 200)


def test_unknown_model_and_context_are_refused_before_any_engine_call(tmp_path):
    app, seen, _, _ = make(tmp_path)
    with TestClient(app) as c:
        r = c.post("/v1/chat/completions", json=chat("gpt-x"), headers=H("factory-a"))
        assert r.status_code == 404 and r.json()["error"]["forge_reason"] == "model_not_offered"
        big = chat(B, max_tokens=1000)
        big["messages"][0]["content"] = "x" * (4 * 70000)
        r = c.post("/v1/chat/completions", json=big, headers=H("factory-a"))
        assert r.status_code == 400 and r.json()["error"]["forge_reason"] == "context_exceeded"
    assert seen == []


def test_engine_context_refusal_maps_to_the_same_reason(tmp_path):
    app, _, _, _ = make(tmp_path, engine_reply=lambda req, body: httpx.Response(
        400, json={"error": {"message": "This model's maximum context length is 65536 tokens"}}))
    with TestClient(app) as c:
        r = c.post("/v1/chat/completions", json=chat(B), headers=H("factory-a"))
    assert r.status_code == 400 and r.json()["error"]["forge_reason"] == "context_exceeded"


def test_reasoning_content_with_thinking_off_is_a_finding(tmp_path):
    reply = {"choices": [{"message": {"content": "x", "reasoning_content": "thought"}}], "usage": {}}
    app, _, log, _ = make(tmp_path, engine_reply=lambda req, body: httpx.Response(200, json=reply))
    with TestClient(app) as c:
        for _ in range(3):
            c.post("/v1/chat/completions", json=chat(B), headers=H("factory-a"))
    recs = [json.loads(x) for x in log.read_text().splitlines()]
    assert sum(1 for r in recs if r.get("finding") == "REASONING_CONTENT_WITH_THINKING_OFF") == 1
    assert "thought" not in log.read_text()


def test_streaming_passes_through_and_releases(tmp_path):
    app, _, log, ctl = make(tmp_path)
    with TestClient(app) as c:
        r = c.post("/v1/chat/completions", json=chat(B, stream=True), headers=H("factory-a"))
        assert r.status_code == 200 and "data: [DONE]" in r.text and r.headers["x-forge-model-identity"] == "b" * 16
        assert ctl.inflight[B] == 0
    rec = [json.loads(x) for x in log.read_text().splitlines() if '"status": 200' in x][-1]
    assert rec["prompt_tokens"] == 5 and rec["completion_tokens"] == 1


def test_share_exhausted_is_429(tmp_path):
    slow = {"n": 0}

    async def reply(req, body):  # pragma: no cover - replaced below by a sync handler
        raise AssertionError

    def handler(req, body):
        slow["n"] += 1
        import time
        time.sleep(0.3)
        return httpx.Response(200, json={"choices": [], "usage": {}})
    app, _, _, _ = make(tmp_path, tenants=[tenant("factory-a", max_concurrency=1, queue_limit=0)], engine_reply=handler)
    with TestClient(app) as c:
        async def two():
            t = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=t, base_url="http://gw") as ac:
                return await asyncio.gather(*(ac.post("/v1/chat/completions", json=chat(B), headers=H("factory-a"))
                                              for _ in range(2)))
        codes = sorted(r.status_code for r in c.portal.call(two))
    assert codes == [200, 429]


def test_configuration_refuses_tenants_beyond_the_catalog(tmp_path):
    with pytest.raises(ValueError, match="TENANT_MODEL_NOT_IN_CATALOG"):
        make(tmp_path, tenants=[tenant("factory-a", ("nope",))])
    with pytest.raises(ValueError, match="TENANT_CONTEXT_ABOVE_MODEL"):
        make(tmp_path, tenants=[tenant("factory-a", max_context=131072)])


def test_disabled_tenant_is_refused(tmp_path):
    app, _, _, _ = make(tmp_path, tenants=[tenant("factory-a"), tenant("off", enabled=False)])
    with TestClient(app) as c:
        assert c.get("/v1/models", headers=H("off")).status_code == 401


def test_secret_reader_requires_a_private_file(tmp_path):
    import os
    p = tmp_path / "s"
    p.write_text("engine-internal=E-KEY\n")
    os.chmod(p, 0o600)
    assert read_secret(p, "engine-internal") == "E-KEY"
    os.chmod(p, 0o640)
    with pytest.raises(RuntimeError, match="NOT_PRIVATE"):
        read_secret(p, "engine-internal")


def test_capa240_reasoning_content_with_thinking_on_is_no_finding(tmp_path):
    """CAPA-240 (017 smoke windows 2026-11-11): qwen3.8 runs with thinking ON (catalog and tenants reasoning_mode 'on'),
    yet the gateway raised REASONING_CONTENT_WITH_THINKING_OFF for its expected reasoning text. The finding is raised only
    for a request whose thinking the gateway switched off."""
    reply = {"choices": [{"message": {"content": "x", "reasoning_content": "thought"}}], "usage": {}}
    app, _, log, _ = make(tmp_path, engine_reply=lambda req, body: httpx.Response(200, json=reply))
    with TestClient(app) as c:
        for _ in range(4):
            c.post("/v1/chat/completions", json=chat(A), headers=H("factory-a"))
    recs = [json.loads(x) for x in log.read_text().splitlines()]
    assert not any(r.get("finding") == "REASONING_CONTENT_WITH_THINKING_OFF" for r in recs)
    assert all(r.get("reasoning_content_seen") for r in recs if r.get("status") == 200)


def test_native_route_serves_the_named_model_tokenizer_and_template(tmp_path):
    """CAPA-197 parity in external mode: the factory measures a request with the served model's own tokenizer."""
    from urllib.parse import quote

    def reply(req, body):
        if req.url.path == "/tokenize":
            return httpx.Response(200, json={"tokens": [1, 2, 3], "host": req.url.host})
        if req.url.path == "/apply-template":
            return httpx.Response(200, json={"prompt": "<rendered>", "model": body.get("model")})
        return httpx.Response(200, json={"choices": [{"message": {"content": f"answer from {req.url.host}"}}]})
    app, seen, log, _ = make(tmp_path, engine_reply=reply)
    base = f"/forge/v1/native/{quote(A, safe='')}"
    with TestClient(app) as c:
        r = c.post(base + "/tokenize", json={"content": "SECRET-PROMPT-TEXT", "add_special": True}, headers=H("factory-a"))
        assert r.status_code == 200 and r.json()["tokens"] == [1, 2, 3] and r.json()["host"] == "eng-a"
        assert r.headers["x-forge-model-identity"] == "a" * 16
        r = c.post(base + "/apply-template", json={"model": A, "messages": []}, headers=H("factory-a"))
        assert r.json() == {"prompt": "<rendered>", "model": "ornith"}  # the engine's own model name
        r = c.post(base + "/v1/chat/completions", json=chat(A), headers=H("factory-a"))
        assert r.status_code == 200 and r.json()["choices"][0]["message"]["content"] == "answer from eng-a"
        assert c.post(base + "/v1/chat/completions", json=chat(B), headers=H("factory-a")).status_code == 400
        assert c.post(base + "/tokenize", json={"content": "x"}).status_code == 401
        assert c.post(f"/forge/v1/native/{quote(A, safe='')}/tokenize", json={"content": "x"},
                      headers=H("neighbour")).status_code == 404  # not an allowed model of that tenant
        assert c.post(f"/forge/v1/native/{quote(B, safe='')}/tokenize", json={"content": "x"},
                      headers=H("factory-a")).json()["error"]["forge_reason"] == "native_op_not_offered"  # vLLM
        assert c.post(base + "/props", json={}, headers=H("factory-a")).status_code == 404
    text = log.read_text()
    assert "SECRET-PROMPT-TEXT" not in text and '"native_op": "tokenize"' in text
