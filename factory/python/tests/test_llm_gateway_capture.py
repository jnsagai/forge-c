"""Feature 017 T064/T065 (US6): the per-node exchange log in the new shape - captured at the factory's model channel,
off by default, private, without hidden reasoning or secrets, attached to its node by the exporter."""
import json
import stat

import httpx
from fastapi.testclient import TestClient
from forge_factory import llm_gateway
from forge_factory.lrtx import model_exchanges as M
from forge_factory.modelservice.transport import Capture, ModelServiceTransport

QWEN = "qwen3.6-35b-a3b-fp8"
EXP = {QWEN: {"precision": "fp8", "reasoning_mode": "off", "min_context_limit": 65536}}


def _svc(stream=False):
    def h(req):
        if stream:
            sse = ('data: {"choices":[{"delta":{"content":"Hel"}}]}\n\ndata: {"choices":[{"delta":{"content":"lo",'
                   '"reasoning_content":"HIDDEN-THOUGHT"},"finish_reason":"stop"}],"usage":{"prompt_tokens":12,'
                   '"completion_tokens":2}}\n\ndata: [DONE]\n\n')
            return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream", "x-forge-model-identity": "b" * 16})
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hello", "reasoning_content": "HIDDEN-THOUGHT"},
                                                      "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 12, "completion_tokens": 2}},
                              headers={"x-forge-model-identity": "b" * 16})
    return httpx.MockTransport(h)


def _app(tmp_path, monkeypatch, stream=False, switch=None):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    root = tmp_path / "state/model-exchanges"
    root.mkdir(parents=True)
    if switch is not None:
        (root / "capture.json").write_text(json.dumps(switch))
    t = ModelServiceTransport(_svc(stream), key=lambda: "TENANT-SECRET-KEY", expected=EXP, tenant_id="forge-qual",
                              capture=Capture(root))
    return llm_gateway.create_app(upstream="http://tier/v1", meter_path=tmp_path / "u.jsonl", transport=t), root


def _call(app, **kw):
    with TestClient(app) as c:
        return c.post("/v1/chat/completions", json={"model": QWEN, "messages": [
            {"role": "user", "content": "Describe GPIO. api_key=sk-LEAK0123456789abcdef"}], **kw})


def _files(root):
    return sorted((root / "gateway").glob("*/*.json")) if (root / "gateway").is_dir() else []


def test_off_by_default_and_when_the_switch_says_so(tmp_path, monkeypatch):
    app, root = _app(tmp_path, monkeypatch)
    assert _call(app).status_code == 200 and _files(root) == []
    app, root = _app(tmp_path / "b", monkeypatch, switch={"structured": True})
    assert _call(app).status_code == 200 and _files(root) == []  # the structured switch does not turn this on


def test_one_private_record_per_call_without_reasoning_or_secrets(tmp_path, monkeypatch):
    app, root = _app(tmp_path, monkeypatch, switch={"gateway": True})
    r = _call(app)
    assert r.status_code == 200
    files = _files(root)
    assert len(files) == 1 and stat.S_IMODE(files[0].stat().st_mode) == 0o600
    assert stat.S_IMODE((root / "gateway").stat().st_mode) == 0o700
    rec = json.loads(files[0].read_text())
    text = files[0].read_text()
    assert rec["kind"] == "gateway" and rec["model"] == QWEN and rec["identity_prefix"] == "b" * 16
    assert rec["reply"]["text"] == "Hello" and rec["reply"]["usage"]["prompt_tokens"] == 12
    assert rec["request"]["messages"][0]["role"] == "user" and "Describe GPIO" in text
    assert "HIDDEN-THOUGHT" not in text and "sk-LEAK0123456789abcdef" not in text and "TENANT-SECRET-KEY" not in text


def test_streamed_calls_are_captured_too(tmp_path, monkeypatch):
    app, root = _app(tmp_path, monkeypatch, stream=True, switch={"gateway": True})
    r = _call(app, stream=True)
    assert r.status_code == 200
    rec = json.loads(_files(root)[0].read_text())
    assert rec["reply"]["text"] == "Hello" and rec["reply"]["usage"]["completion_tokens"] == 2
    assert "HIDDEN-THOUGHT" not in _files(root)[0].read_text()


def test_capture_failure_never_fails_the_call(tmp_path, monkeypatch):
    app, root = _app(tmp_path, monkeypatch, switch={"gateway": True})
    (root / "gateway").write_text("not a directory")  # any write will fail
    assert _call(app).status_code == 200


def test_exporter_attaches_each_capture_to_its_turn_once():
    visits = [{"node": "swe1_inspector", "turns": [
        {"i": 1, "requested_model": QWEN, "started": "2026-11-08T10:00:01Z", "prompt_tokens": 9000, "usage": {"output": 40}},
        {"i": 2, "model": QWEN, "started": "2026-11-08T10:00:06Z", "prompt_tokens": 10200, "usage": {"output": 10}}]}]
    recs = [{"kind": "gateway", "model": QWEN, "at": "2026-11-08T10:00:06Z", "reply": {"usage": {"prompt_tokens": 10200}}},
            {"kind": "gateway", "model": QWEN, "at": "2026-11-08T10:00:01Z", "reply": {"usage": {"prompt_tokens": 9000}}},
            {"kind": "gateway", "model": QWEN, "at": "2026-11-08T13:00:00Z", "reply": {"usage": {"prompt_tokens": 9000}}},
            {"kind": "gateway", "model": "other", "at": "2026-11-08T10:00:01Z", "reply": {"usage": {"prompt_tokens": 9000}}}]
    assert M.attach_gateway(visits, recs) == 2
    got = {r["turn"]: r["at"] for r in visits[0]["gateway_captured"]}
    assert got == {1: "2026-11-08T10:00:01Z", 2: "2026-11-08T10:00:06Z"}
