"""A native compaction note must not break Qwen's single-initial-system template."""
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as gw
from forge_factory.lrtx import profile

MODEL = "qwen3.8:27b-q8_0"
POLICY = {MODEL: {"effort": "medium", "system_message_order": "merge_first"}}


def conversation():
    return [
        {"role": "system", "content": "Role contract; retain every requirement."},
        {"role": "user", "content": "Implement the full declared scope."},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call-1", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "call-1", "content": "Evidence: α\nEnd of required source."},
        {"role": "system", "content": "Compacted memory: unresolved obligation remains; no accepted PASS."},
        {"role": "user", "content": "Continue."},
    ]


def test_late_system_note_preserves_evidence_and_tool_protocol_without_mutation():
    messages = conversation()
    original = copy.deepcopy(messages)
    output = gw.sanitize_request({"model": MODEL, "messages": messages}, policy=POLICY)
    assert messages == original
    out = output["messages"]
    assert out[0]["role"] == "system" and sum(m["role"] == "system" for m in out) == 1
    assert out[0]["content"] == messages[0]["content"] + "\n\n" + messages[4]["content"]
    assert out[1:] == [m for m in messages if m["role"] != "system"]
    assert out[3]["tool_call_id"] == out[2]["tool_calls"][0]["id"]


def test_text_parts_metadata_and_multiple_system_notes_are_not_discarded():
    messages = [{"role": "user", "content": "Task"},
                {"role": "system", "name": "memory", "content": [
                    {"type": "text", "text": "first α", "cache_control": {"type": "ephemeral"}},
                    {"type": "input_text", "text": "second\nthird"}]},
                {"role": "system", "content": "final evidence"}]
    out = gw.system_messages_first(messages)
    assert out[1:] == messages[:1]
    for text in ("first α", "second\nthird", "final evidence", '"name": "memory"', '"cache_control"'):
        assert text in out[0]["content"]


@pytest.mark.parametrize("messages", [[], [{"role": "user", "content": "task"}],
    [{"role": "system", "content": [{"type": "text", "text": "already initial"}], "name": "contract"},
     {"role": "user", "content": "task"}]])
def test_already_compatible_messages_are_unchanged(messages):
    assert gw.system_messages_first(messages) == messages


def test_other_models_and_profiles_require_explicit_opt_in():
    messages = conversation()
    assert gw.sanitize_request({"model": MODEL, "messages": messages}, policy={})["messages"] == messages
    assert gw.sanitize_request({"model": "other", "messages": messages}, policy=POLICY)["messages"] == messages
    with pytest.raises(ValueError, match="CONTENT_UNSUPPORTED"):
        gw.system_messages_first([{"role": "user", "content": "task"},
                                  {"role": "system", "content": [{"type": "image_url", "image_url": "x"}]}])


@pytest.mark.parametrize("stream", [False, True])
def test_real_gateway_path_sends_canonical_messages_to_template_transport(tmp_path, monkeypatch, stream):
    monkeypatch.setenv("FORGE_GATEWAY_REASONING", json.dumps(POLICY))
    seen = []

    def native(req):
        body = json.loads(req.content)
        seen.append(body)
        if any(m["role"] == "system" for m in body["messages"][1:]):
            return httpx.Response(400, json={"error": "System message must be at the beginning."})
        if body.get("stream"):
            return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"ok"},'
                                  '"finish_reason":"stop"}],"usage":{"completion_tokens":1}}\n\n'
                                  'data: [DONE]\n\n', headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                                         "usage": {"completion_tokens": 1}})

    client = TestClient(gw.create_app("http://native", tmp_path / "meter.jsonl", transport=httpx.MockTransport(native)))
    result = client.post("/v1/chat/completions", json={"model": MODEL, "messages": conversation(), "stream": stream})
    assert result.status_code == 200 and "ok" in result.text and len(seen) == 1
    assert seen[0]["messages"][1:] == [m for m in conversation() if m["role"] != "system"]


def test_native_artifact_profile_explicitly_selects_compatibility():
    p = profile.load("local-rtx-v2-omniverse2-q38-qm-native-artifacts")
    assert p["gateway"]["reasoning"][MODEL]["system_message_order"] == "merge_first"
