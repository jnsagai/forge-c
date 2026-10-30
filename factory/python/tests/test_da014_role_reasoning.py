"""Role effort changes are pinned, measured and admitted; they grant no role capability."""
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as G
from forge_factory.afo import product_role_trial as T
from forge_factory.afo.diagnosis_packet import measure_request
from forge_factory.afo.durable import Refused
from forge_factory.lrtx import profile
from forge_factory.lrtx import role_capability as C
from test_da014_product_role_trial import trial as trial_fixture

PROFILE = "local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector"
MODEL = "qwen3.8:27b-q8_0"


@pytest.fixture(name="trial")
def mixed_trial(tmp_path, monkeypatch):
    return trial_fixture.__wrapped__(tmp_path, monkeypatch)


@pytest.mark.parametrize("role,effort", [(f"swe{n}-{r}", e) for n in range(1, 7)
                                       for r, e in (("author", "medium"), ("inspector", "xhigh"))]
                         + [("afo-recovery-planner", "medium"), ("afo-factory-maintainer", "medium")])
def test_pinned_profile_selects_exact_role_despite_contradictory_caller(role, effort):
    p = profile.load(PROFILE)
    before = {"model": MODEL, "messages": [], "reasoning_effort": "none", "max_tokens": 2048,
              "chat_template_kwargs": {"enable_thinking": False, "other": "retained"}}
    out = G.sanitize_request(before, policy=p["gateway"]["reasoning"], role=role)
    assert out["reasoning_effort"] == effort and out["chat_template_kwargs"] == {
        "enable_thinking": True, "other": "retained"}
    assert out["max_tokens"] == 34816 and before["max_tokens"] == 2048
    assert out["messages"] == before["messages"]
    assert measure_request(out)["sha256"] != measure_request(before)["sha256"]


def test_native_skill_role_and_binding_role_use_the_same_selection():
    p = profile.load(PROFILE)
    body = {"model": MODEL, "messages": [{"role": "system", "content": "skill_name swe2-inspector"}]}
    assert G.sanitize_request(body, policy=p["gateway"]["reasoning"])["reasoning_effort"] == "xhigh"
    assert G.sanitize_request(body, policy=p["gateway"]["reasoning"], role="swe2-author")["reasoning_effort"] == "medium"
    assert G.sanitize_request({"model": MODEL}, policy=p["gateway"]["reasoning"])["reasoning_effort"] == "medium"


def test_gateway_sends_mixed_efforts_serially_and_keeps_hidden_reasoning_private(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_GATEWAY_REASONING", json.dumps(profile.load(PROFILE)["gateway"]["reasoning"]))
    sent = []

    def upstream(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}", "reasoning_content": "SECRET"},
                                                    "finish_reason": "stop"}],
                                        "usage": {"prompt_tokens": 5, "completion_tokens": 2}})

    meter = tmp_path / "usage.jsonl"
    with TestClient(G.create_app("http://upstream", meter, transport=httpx.MockTransport(upstream))) as c:
        for role in ("swe1-author", "swe1-inspector"):
            r = c.post("/chat/completions", json={"model": MODEL, "max_tokens": 2048,
                       "messages": [{"role": "system", "content": "skill_name " + role}]})
            assert r.status_code == 200 and "SECRET" not in r.text
    assert [b["reasoning_effort"] for b in sent] == ["medium", "xhigh"]
    assert len(meter.read_text().splitlines()) == 2 and "SECRET" not in meter.read_text()


def test_durable_binding_role_is_applied_before_reservation_and_measurement(tmp_path, monkeypatch):
    from forge_factory.afo import queue, request_admission

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_GATEWAY_REASONING", json.dumps(profile.load(PROFILE)["gateway"]["reasoning"]))
    monkeypatch.setattr(queue, "Store", lambda: object())
    received = []

    def reserve(store, binding, body):
        received.append((binding, body, measure_request(body)))
        raise Refused("PROBE_ONLY_NO_NATIVE_EFFECT")

    monkeypatch.setattr(request_admission, "reserve", reserve)

    def upstream(request):
        pytest.fail("a refused reservation must not reach inference")

    with TestClient(G.create_app("http://upstream", tmp_path / "meter.jsonl",
                                transport=httpx.MockTransport(upstream))) as c:
        result = c.post("/chat/completions", json={"model": MODEL, "max_tokens": 2048,
                        "messages": [{"role": "system", "content": "skill_name swe1-author"}],
                        "forge_execution": {"job_id": "fixture", "nonce": "nonce", "request_id": "one",
                                            "role": "swe1-inspector"}})
    assert result.status_code == 429 and len(received) == 1
    binding, actual, measured = received[0]
    assert binding["role"] == "swe1-inspector" and actual["reasoning_effort"] == "xhigh"
    assert actual["max_tokens"] == 34816 and "forge_execution" not in actual
    assert measured["sha256"] == measure_request(actual)["sha256"]


@pytest.mark.parametrize("mapping", [{"swe1-inspector": "unsupported"}, {"invented-role": "xhigh"}, "xhigh"])
def test_invalid_override_never_reaches_a_provider(mapping):
    with pytest.raises(ValueError, match="INVALID_ROLE_REASONING_POLICY"):
        G.sanitize_request({"model": MODEL}, policy={MODEL: {"effort": "medium", "role_efforts": mapping}})


def test_signed_experiment_still_requires_each_roles_actual_reasoning_identity(trial):
    author = trial.doc["roles"]["swe1-author"][0]
    author["reasoning"] = "medium"
    inspector = copy.deepcopy(author)
    inspector.update(role="swe1-inspector", reasoning="xhigh")
    trial.doc["roles"]["swe1-inspector"] = [inspector]
    T.bind(trial.publish(trial.doc), trial.job, trial.eff)
    policy = {"local": {"effort": "medium", "role_efforts": {"swe1-inspector": "xhigh"}}}
    raw = {"model": "local", "response_format": {"type": "json_schema"}, "temperature": 0, "max_tokens": 64}
    for role in ("swe1-author", "swe1-inspector"):
        effective = G.sanitize_request(raw, policy=policy, role=role)
        assert C.admit_job(trial.job, role, input_tokens=100, output_tokens=64, body=effective)["qualified"] is False
    wrong = G.sanitize_request(raw, policy=policy, role="swe1-inspector")
    with pytest.raises(Refused, match="CONFIGURATION_UNDECLARED"):
        C.admit_job(trial.job, "swe1-author", input_tokens=100, output_tokens=64, body=wrong)
