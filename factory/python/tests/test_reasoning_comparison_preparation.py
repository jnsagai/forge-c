"""Controlled pilot preparation uses real reference compilation and never calls a model."""
import copy
import json
import shutil
from pathlib import Path

import pytest

from forge_factory.afo import configuration_comparison as comparison
from forge_factory.afo.durable import Refused
from forge_factory.common import REPO_ROOT, sha256_file
from forge_factory.llm_gateway import sanitize_request
from forge_factory.lrtx import reasoning_comparison as R

EVIDENCE = REPO_ROOT / "evidence/014-durable-local-autonomy/reasoning-speed-20261030"


@pytest.fixture
def capabilities(tmp_path):
    p = tmp_path / "native-template-preflight.json"
    shutil.copyfile(EVIDENCE / p.name, p)
    return {"path": str(p), "sha256": sha256_file(p)}


def test_real_template_rejects_high_and_medium_changes_gateway_effort_without_changing_the_model(capabilities):
    observed = json.loads(Path(capabilities["path"]).read_text())
    rows = {r["effort"]: r for r in observed["rows"]}
    assert rows["high"]["http_status"] == 500 and rows["high"]["unsupported_effort_error"]
    assert rows["medium"]["http_status"] == rows["xhigh"]["http_status"] == 200
    assert observed["model_requests"] == 0 and observed["request_ledger_before"] == observed["request_ledger_after"]
    profiles = R.comparable_profiles()
    body = {"model": R.MODEL, "messages": [], "max_tokens": 2048, "reasoning_effort": "high"}
    for effort in R.EFFORTS:
        actual = sanitize_request(body, policy=profiles[effort]["gateway"]["reasoning"])
        assert actual["reasoning_effort"] == effort and actual["max_tokens"] == 34816
    with pytest.raises(Refused, match="EFFORT_INVALID"):
        R.selected_profile("high")


def test_compiled_eight_case_pilot_is_frozen_and_still_not_native_measurement(tmp_path, monkeypatch, capabilities):
    compiler = shutil.which("clang")
    assert compiler, "pinned compiler is required for this meaningful preparation test"
    # A preparation bug must never turn this local test into model execution.
    from forge_factory.lrtx import structured
    from forge_factory.afo import queue
    monkeypatch.setattr(structured, "call", lambda *a, **k: pytest.fail("preparation attempted inference"))
    monkeypatch.setattr(queue, "Store", lambda *a, **k: pytest.fail("preparation created an authoritative queue"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "original-state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "original-events"))
    out = tmp_path / "pilot"
    report = R.prepare(out, compiler=compiler, capabilities_ref=capabilities)
    assert report["status"] == "PREPARED_NOT_RUN" and report["model_requests"] == 0
    assert report["case_count_per_effort"] == 8 and len(report["case_ids"]) == 8
    assert report["efforts"] == ["xhigh", "medium"]
    assert report["unsupported"]["high"]["status"] == "UNSUPPORTED_MODEL_TEMPLATE"
    assert report["unsupported"]["high"]["speed"] is None and not report["unsupported"]["high"]["silently_mapped"]
    import os
    assert os.environ["FORGE_STATE_DIR"] == str(tmp_path / "original-state")
    assert os.environ["FORGE_EVENTS_DIR"] == str(tmp_path / "original-events")
    assert not list(out.rglob("*.sqlite3"))
    for effort in R.EFFORTS:
        inp = json.loads((out / effort / "inputs.json").read_text())
        reference = json.loads(Path(inp["reference_report"]["path"]).read_text())
        assert reference["rows"]["seeded"]["checked"] == reference["rows"]["reference"]["checked"] == 260
        assert reference["rows"]["seeded"]["failures"] == 194 and reference["rows"]["reference"]["failures"] == 0
        assert len(inp["trials"]) == 8 and all(t["output_reserve"] == 34816 for t in inp["trials"])
        assert all(t["request_measurement"]["effective_reasoning_effort"] == effort for t in inp["trials"])
        assert not inp["runtime_admission_created"]
    plan = json.loads((out / "medium-comparison-plan.json").read_text())
    assert comparison.Q.comparison_identity("reasoning", plan["baseline_identity"], plan["candidate_identity"]) == ["reasoning"]
    missing = json.loads((out / "medium-comparison-NOT-RUN.json").read_text())
    assert missing["status"] == "NOT_RUN" and not missing["automatic_selection"]
    assert set(missing["blockers"]) == {"BASELINE_MEASUREMENT_NOT_RUN", "CANDIDATE_MEASUREMENT_NOT_RUN"}
    protocol = json.loads((REPO_ROOT / "factory/qualification/014/protocol-cases.json").read_text())
    assert len(protocol["cases"]) == 20 and all(c["repeats"] == 5 for c in protocol["cases"])
    with pytest.raises(Refused, match="ROOT_ALREADY_EXISTS"):
        R.prepare(out, compiler=compiler, capabilities_ref=capabilities)


@pytest.mark.parametrize("change", ["hash", "model", "high-accepted", "medium-is-xhigh"])
def test_missing_or_misleading_effort_controls_cannot_be_a_benchmark(tmp_path, capabilities, change):
    p = Path(capabilities["path"])
    if change == "hash":
        p.write_text("{}")
    else:
        d = json.loads(p.read_text())
        if change == "model":
            d["model_digest"] = "different-model"
        else:
            row = next(r for r in d["rows"] if r["effort"] == ("high" if change == "high-accepted" else "medium"))
            row["http_status"] = 200
            row["xhigh_instruction_present"] = True
        p.write_text(json.dumps(d))
        capabilities["sha256"] = sha256_file(p)
    with pytest.raises(Refused, match="TEMPLATE_PREFLIGHT"):
        R.prepare(tmp_path / "must-not-exist", compiler="/unused", capabilities_ref=capabilities)
    assert not (tmp_path / "must-not-exist").exists()


@pytest.mark.parametrize("change", ["mtp", "context", "kv", "sampling"])
def test_multiple_factors_cannot_be_disguised_as_reasoning_speed(monkeypatch, change):
    original = R.profile.load
    def changed(ident):
        p = copy.deepcopy(original(ident))
        if ident.endswith("medium-trial"):
            if change == "mtp":
                p["runtime"]["llama_server"]["mtp_draft"] = 4
            elif change == "context":
                p["runtime"]["ollama"]["OLLAMA_CONTEXT_LENGTH"] = "131072"
            elif change == "kv":
                p["runtime"]["ollama"]["OLLAMA_KV_CACHE_TYPE"] = "q8_0"
            else:
                p["structured"]["inspector_sampling"]["default"]["temperature"] = 0.7
        return p
    monkeypatch.setattr(R.profile, "load", changed)
    with pytest.raises(Refused, match="COMPARISON_.*CHANGED"):
        R.comparable_profiles()


def test_failed_preparation_restores_the_existing_environment(tmp_path, monkeypatch, capabilities):
    import os
    monkeypatch.setenv("FORGE_STATE_DIR", "existing-state")
    monkeypatch.delenv("FORGE_EVENTS_DIR", raising=False)
    def fail(*a, **k):
        raise Refused("SYNTHETIC_PREPARATION_FAILURE")
    monkeypatch.setattr(R.inputs, "prepare", fail)
    with pytest.raises(Refused, match="SYNTHETIC_PREPARATION_FAILURE"):
        R.prepare(tmp_path / "partial", compiler="/unused", capabilities_ref=capabilities)
    assert os.environ["FORGE_STATE_DIR"] == "existing-state" and "FORGE_EVENTS_DIR" not in os.environ

