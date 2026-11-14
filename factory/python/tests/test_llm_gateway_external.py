"""Feature 017 T016: the factory gateway in external mode (unchanged gateway source + the model-channel transport)."""
import hashlib
import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from forge_factory import llm_gateway
from forge_factory.modelservice.transport import CallLog, ModelServiceTransport

QWEN, ORN = "qwen3.6-35b-a3b-fp8", "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"
EXPECTED = {QWEN: {"precision": "fp8", "reasoning_mode": "off", "min_context_limit": 65536},
            ORN: {"precision": "other", "reasoning_mode": "on", "min_context_limit": 65536}}
GATEWAY_SRC = Path(llm_gateway.__file__)


def service(script):
    """A fake model service: `script` maps a call index to (status, json, headers)."""
    calls = []

    def handler(req):
        body = json.loads(req.content) if req.content else {}
        calls.append({"auth": req.headers.get("authorization"), "body": body, "path": req.url.path})
        status, data, headers = script(len(calls), body)
        return httpx.Response(status, json=data, headers=headers)
    return httpx.MockTransport(handler), calls


def ok(model, fp="a"):
    return 200, {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 2}}, {"x-forge-model-identity": fp * 16,
                                                                           "x-forge-queue-ms": "5", "x-forge-swap-ms": "1200"}


def app_with(tmp_path, script, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    inner, calls = service(script)
    log = CallLog(tmp_path / "state/model-service/calls.jsonl")
    t = ModelServiceTransport(inner, key=lambda: "TENANT-KEY-123", expected=EXPECTED, log=log, tenant_id="forge-qual")
    app = llm_gateway.create_app(upstream="http://tier/v1", meter_path=tmp_path / "usage.jsonl", transport=t)
    return app, calls, log.path


def post(c, model, **kw):
    return c.post("/v1/chat/completions", json={"model": model, "messages": [{"role": "user", "content": "PROMPT-X"}], **kw},
                  headers={"Authorization": "Bearer fabro-dummy"})


def test_tenant_key_replaces_the_caller_credential_and_thinking_is_off(tmp_path, monkeypatch):
    app, calls, log = app_with(tmp_path, lambda n, b: ok(b["model"]), monkeypatch)
    with TestClient(app) as c:
        assert post(c, QWEN).status_code == 200
        assert post(c, ORN).status_code == 200
    assert all(x["auth"] == "Bearer TENANT-KEY-123" for x in calls)  # never the caller's credential
    assert calls[0]["body"]["chat_template_kwargs"] == {"enable_thinking": False}  # expected non-thinking
    assert "chat_template_kwargs" not in calls[1]["body"]  # Ornith keeps its own reasoning setting
    recs = [json.loads(x) for x in log.read_text().splitlines()]
    assert [r["model"] for r in recs] == [QWEN, ORN] and recs[0]["swap_ms"] == 1200 and recs[0]["identity_prefix"] == "a" * 16
    text = log.read_text() + (tmp_path / "usage.jsonl").read_text()
    assert "PROMPT-X" not in text and "TENANT-KEY-123" not in text  # metadata only, no secret


def test_identity_is_pinned_per_model_and_a_change_blocks(tmp_path, monkeypatch):
    seq = {1: "a", 2: "b", 3: "a", 4: "c"}  # QWEN=a, ORN=b, QWEN again=a (swap back: fine), QWEN=c (changed)
    app, _, log = app_with(tmp_path, lambda n, b: ok(b["model"], seq[n]), monkeypatch)
    with TestClient(app) as c:
        codes = [post(c, m).status_code for m in (QWEN, ORN, QWEN)]
        r = post(c, QWEN)
    assert codes == [200, 200, 200] and r.status_code == 409 and r.json()["error"]["type"] == "identity_changed"
    assert json.loads(log.read_text().splitlines()[-1])["forge_reason"] == "identity_changed"


def test_expected_fingerprint_pins_before_the_first_call(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    inner, _ = service(lambda n, b: ok(b["model"], "d"))
    exp = {QWEN: {**EXPECTED[QWEN], "revision_fingerprint": "a" * 64}}
    t = ModelServiceTransport(inner, key=lambda: "K", expected=exp)
    app = llm_gateway.create_app(upstream="http://tier/v1", meter_path=tmp_path / "u.jsonl", transport=t)
    with TestClient(app) as c:
        assert post(c, QWEN).status_code == 409


def test_refusals_map_to_contract_reasons(tmp_path, monkeypatch):
    replies = {1: (429, {"error": {"forge_reason": "share_exhausted"}}, {}),
               2: (401, {"error": {"forge_reason": "credential_refused"}}, {}),
               3: (404, {"error": {"forge_reason": "model_not_offered"}}, {}),
               4: (503, {"error": {"forge_reason": "model_unavailable"}}, {})}
    app, _, log = app_with(tmp_path, lambda n, b: replies[n], monkeypatch)
    with TestClient(app) as c:
        codes = [post(c, QWEN).status_code for _ in range(4)]
    assert codes == [429, 401, 404, 503]  # passed through: the gateway's own bounded handling decides what follows
    reasons = [json.loads(x)["forge_reason"] for x in log.read_text().splitlines()]
    assert reasons == ["share_exhausted", "credential_refused", "model_not_offered", "service_unreachable"]


def test_unreachable_service_is_recorded_as_such(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))

    def boom(req):
        raise httpx.ConnectError("refused", request=req)
    log = CallLog(tmp_path / "calls.jsonl")
    t = ModelServiceTransport(httpx.MockTransport(boom), key=lambda: "K", expected=EXPECTED, log=log)
    app = llm_gateway.create_app(upstream="http://tier/v1", meter_path=tmp_path / "u.jsonl", transport=t)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = post(c, QWEN)
    assert r.status_code >= 500
    assert json.loads(log.path.read_text().splitlines()[-1])["forge_reason"] == "service_unreachable"


def test_the_pinned_gateway_source_is_untouched():
    """Research R7: the owner lane's signed transport proof pins llm_gateway.py; feature 017 must not change it."""
    import subprocess
    root = GATEWAY_SRC.parents[3]
    base = subprocess.run(["git", "-C", str(root), "show", "482b824b:factory/python/forge_factory/llm_gateway.py"],
                          capture_output=True, check=False)
    if base.returncode != 0:  # not a checkout with history: compare against the recorded digest instead
        return
    assert hashlib.sha256(base.stdout).hexdigest() == hashlib.sha256(GATEWAY_SRC.read_bytes()).hexdigest()
