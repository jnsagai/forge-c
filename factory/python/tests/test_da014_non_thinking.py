"""Explicit non-thinking is profile-bound and included in actual context accounting."""
import copy
import json
import shutil
from pathlib import Path

import pytest
from forge_factory import llm_gateway as G
from forge_factory.lrtx import profile

BASE = "local-rtx-v2-omniverse2-q38-qm-demo-repair-mtp"
MODEL = "qwen3.8:27b-q8_0"


def test_none_policy_reaches_native_template_and_preserves_common_output_ceiling(monkeypatch):
    p = profile.load(BASE + "-nothink-trial")
    monkeypatch.setenv("FORGE_GATEWAY_REASONING", json.dumps(p["gateway"]["reasoning"]))
    body = {"model": MODEL, "max_tokens": 2048, "messages": [],
            "chat_template_kwargs": {"enable_thinking": True, "other": "retained"}}
    before = copy.deepcopy(body)
    actual = G.sanitize_request(body)
    assert actual["reasoning_effort"] == "none"
    assert actual["chat_template_kwargs"] == {"enable_thinking": False, "other": "retained"}
    assert actual["max_tokens"] == 34816
    assert body == before
    baseline = G.sanitize_request(body, policy=profile.load(BASE)["gateway"]["reasoning"])
    assert baseline["reasoning_effort"] == "xhigh" and baseline["max_tokens"] == actual["max_tokens"]


def test_unselected_default_and_existing_efforts_keep_their_wire_contract():
    body = {"model": MODEL, "messages": [], "max_tokens": 2048}
    for policy, effort, cap in [({}, "none", 2048),
                                ({MODEL: {"effort": "medium", "extra_output_tokens": 32768}}, "medium", 34816)]:
        out = G.sanitize_request(body, policy=policy)
        assert out["reasoning_effort"] == effort and out["max_tokens"] == cap
        assert "chat_template_kwargs" not in out


def test_profile_changes_only_reasoning_controls_and_descriptive_metadata():
    baseline, candidate = [copy.deepcopy(profile.load(p)) for p in [BASE, BASE + "-nothink-trial"]]
    for p in (baseline, candidate):
        for key in ("id", "description", "status", "_path", "_sha256"):
            p.pop(key, None)
    server = candidate["runtime"]["llama_server"]
    assert server["reasoning"] == "off" and "reasoning_effort" not in server
    assert candidate["gateway"]["reasoning"][MODEL]["effort"] == "none"
    server.update(reasoning="on", reasoning_effort="xhigh")
    candidate["gateway"]["reasoning"][MODEL]["effort"] = "xhigh"
    assert candidate == baseline


def test_complete_request_measurement_includes_explicit_thinking_control(tmp_path, monkeypatch):
    from forge_factory.afo import diagnosis_packet as P
    from forge_factory.afo import durable_agent as D
    from test_da014_diagnosis_context_contract import case_job
    job, _, _ = case_job(tmp_path, monkeypatch)
    job["profile"] = BASE + "-nothink-trial"
    body, measured = D.request_material(job)
    effective = G.sanitize_request(body, policy=profile.load(job["profile"])["gateway"]["reasoning"])
    assert effective["chat_template_kwargs"]["enable_thinking"] is False
    assert measured["effective_reasoning_effort"] == "none"
    assert measured["effective_output_cap"] == 34816
    assert measured["sha256"] == P.measure_request(effective)["sha256"]


def test_native_server_is_explicitly_off_with_same_mtp_and_context(tmp_path):
    from forge_factory.lrtx import stack
    from test_da014_llama_server import MODEL as OLD_MODEL
    from test_da014_llama_server import _root
    root, original = _root(tmp_path)
    source = root / "ollama-models/manifests/registry.ollama.ai/library/qwen3.6/35b-a3b"
    target = source.parents[1] / "qwen3.8/27b-q8_0"
    target.parent.mkdir()
    target.write_bytes(source.read_bytes())
    p = copy.deepcopy(profile.load(BASE + "-nothink-trial"))
    p["models"]["allowed"][MODEL]["digest"] = original["models"]["allowed"][OLD_MODEL]["digest"]
    argv, _, _, models = stack.llama_server_spec(root, p, p["deployment"]["ports"], {})
    assert models == [MODEL]
    assert argv[argv.index("--reasoning") + 1] == "off"
    assert "--reasoning-effort" not in argv
    assert argv[argv.index("--spec-draft-n-max") + 1] == "3"
    assert argv[argv.index("-c") + 1] == "262144" and argv[argv.index("-np") + 1] == "1"


def proof_refs(tmp_path):
    from forge_factory.common import REPO_ROOT, sha256_file
    refs = []
    for name in ("native-template-preflight.json", "reasoning-disabled-template-preflight.json"):
        src = REPO_ROOT / "evidence/014-durable-local-autonomy/reasoning-speed-20261030" / name
        path = tmp_path / name
        shutil.copyfile(src, path)
        refs.append({"path": str(path), "sha256": sha256_file(path)})
    return refs


def test_real_compiled_three_effort_preparation_is_new_identity_not_budget_reset(tmp_path, monkeypatch):
    from forge_factory.afo import queue
    from forge_factory.lrtx import reasoning_comparison as R
    from forge_factory.lrtx import structured
    monkeypatch.setattr(queue, "Store", lambda *a, **k: pytest.fail("preparer opened authoritative queue"))
    monkeypatch.setattr(structured, "call", lambda *a, **k: pytest.fail("preparer attempted inference"))
    cap, off = proof_refs(tmp_path)
    result = R.prepare(tmp_path / "prepared", compiler=shutil.which("clang"), capabilities_ref=cap,
                       non_thinking_ref=off, campaign_prefix="q38-new-thinking-study")
    assert result["efforts"] == ["xhigh", "medium", "none"]
    assert result["model_requests"] == result["signed_grants_created"] == 0
    assert result["mission_or_job_created"] is False
    assert not list((tmp_path / "prepared").rglob("*.sqlite3"))
    for effort in result["efforts"]:
        inp = json.loads((tmp_path / "prepared" / effort / "inputs.json").read_text())
        assert inp["campaign_id"] == "q38-new-thinking-study-" + effort
        envelope = json.loads((tmp_path / "prepared" / effort / "cases/late-finding-0/envelope.json").read_text())
        assert envelope["authorization_ref"] == "AUTH-014-REASONING-Q38-NEW-THINKING-STUDY-" + effort.upper()
        assert inp["count"] == 8
        assert all(t["request_measurement"]["effective_reasoning_effort"] == effort
                   and t["output_reserve"] == 34816 for t in inp["trials"])
        reference = json.loads(Path(inp["reference_report"]["path"]).read_text())
        assert reference["rows"]["reference"]["checked"] == 260
        assert reference["rows"]["reference"]["failures"] == 0


@pytest.mark.parametrize("change", ["hash", "template", "open-thinking", "generation"])
def test_unproven_off_controls_are_refused_before_creating_cases(tmp_path, change):
    from forge_factory.afo.durable import Refused
    from forge_factory.common import sha256_file
    from forge_factory.lrtx import reasoning_comparison as R
    cap, off = proof_refs(tmp_path)
    p = Path(off["path"])
    d = json.loads(p.read_text())
    if change == "template":
        d["template_sha256"] = "different-template"
    elif change == "open-thinking":
        d["rows"][1]["ends_closed_empty_thinking"] = False
    elif change == "generation":
        d["model_generation_requests"] = 1
    p.write_text(json.dumps(d))
    if change != "hash":
        off["sha256"] = sha256_file(p)
    with pytest.raises(Refused, match="NON_THINKING_TEMPLATE_PREFLIGHT"):
        R.prepare(tmp_path / "absent", compiler="/unused", capabilities_ref=cap,
                  non_thinking_ref=off, campaign_prefix="off-test")
    assert not (tmp_path / "absent").exists()
