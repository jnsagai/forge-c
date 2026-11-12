"""MTP preparation preserves one runtime factor, frozen oracle coverage and existing authorities."""
import copy
import json
import os
import shutil
from pathlib import Path

import pytest
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused
from forge_factory.common import REPO_ROOT, sha256_file
from forge_factory.lrtx import mtp_comparison as M


@pytest.fixture
def capabilities(tmp_path):
    p = tmp_path / "template.json"
    shutil.copyfile(REPO_ROOT / "evidence/014-durable-local-autonomy/reasoning-speed-20261030/native-template-preflight.json", p)
    return {"path": str(p), "sha256": sha256_file(p)}


@pytest.mark.parametrize("draft", [True, 2.0, 0, 1, 5, 8, "3", None])
def test_only_the_explicit_integer_sweep_is_selectable(draft):
    with pytest.raises(Refused, match="DRAFT_INVALID"):
        M.selected_profile(draft)


@pytest.mark.parametrize("change", ["effort", "context", "kv", "sampling", "gateway", "gates", "role-budget"])
def test_another_changed_factor_is_refused_before_preparation(monkeypatch, change):
    original = M.profile.load

    def altered(ident):
        p = copy.deepcopy(original(ident))
        if "draft4-trial" in ident:
            if change == "effort":
                p["gateway"]["reasoning"][M.MODEL]["effort"] = "medium"
            elif change == "context":
                p["runtime"]["ollama"]["OLLAMA_CONTEXT_LENGTH"] = "131072"
            elif change == "kv":
                p["runtime"]["ollama"]["OLLAMA_KV_CACHE_TYPE"] = "q8_0"
            elif change == "sampling":
                p["structured"]["inspector_sampling"]["default"]["temperature"] = 0.7
            elif change == "gateway":
                p["gateway"]["reasoning"][M.MODEL]["extra_output_tokens"] += 1
            elif change == "gates":
                p["structured"]["advisory_continue"] = False
            else:
                p["afo"]["role_job_tokens"]["afo-recovery-planner"] += 1
        return p

    monkeypatch.setattr(M.profile, "load", altered)
    with pytest.raises(Refused, match="MTP_COMPARISON_.*CHANGED"):
        M.comparable_profiles()


def test_compiled_four_variant_preparation_creates_no_runtime_authority(tmp_path, monkeypatch, capabilities):
    from forge_factory.afo import queue
    from forge_factory.lrtx import structured

    monkeypatch.setattr(queue, "Store", lambda *a, **k: pytest.fail("preparation opened authoritative queue"))
    monkeypatch.setattr(structured, "call", lambda *a, **k: pytest.fail("preparation attempted inference"))
    monkeypatch.setenv("FORGE_STATE_DIR", "original-state")
    monkeypatch.delenv("FORGE_EVENTS_DIR", raising=False)
    compiler = shutil.which("clang")
    assert compiler, "real compiler is required"
    out = tmp_path / "mtp"
    result = M.prepare(out, compiler=compiler, capabilities_ref=capabilities, campaign_prefix="q38-mtp-test")
    assert result["draft_order"] == [3, 2, 4, 6]
    assert result["case_count_per_draft"] == 8
    assert result["model_requests"] == result["signed_grants_created"] == 0
    assert not result["mission_or_job_created"] and not result["service_changes"]
    assert not list(out.rglob("*.sqlite3"))
    assert os.environ["FORGE_STATE_DIR"] == "original-state" and "FORGE_EVENTS_DIR" not in os.environ
    plan = json.loads((out / "mtp-plan.json").read_text())
    assert plan["runtime_factor"] == "mtp_draft"
    assert plan["capability_identity_changed"] is False
    identities = []
    for draft in M.DRAFTS:
        E = out / f"draft{draft}"
        manifest = json.loads((E / "campaign-unsigned.json").read_text())
        Q.validate(manifest)
        identities.append(manifest["identity"])
        inp = json.loads((E / "inputs.json").read_text())
        ref = json.loads(Path(inp["reference_report"]["path"]).read_text())
        assert ref["rows"]["seeded"]["checked"] == ref["rows"]["reference"]["checked"] == 260
        assert ref["rows"]["seeded"]["failures"] == 194 and ref["rows"]["reference"]["failures"] == 0
        assert len(inp["trials"]) == 8
        assert all(t["request_measurement"]["effective_reasoning_effort"] == "xhigh" for t in inp["trials"])
        assert all(t["output_reserve"] == 34816 for t in inp["trials"])
        assert "mission" not in manifest and manifest["authorization_ref"] is None
    assert all(identity == identities[0] for identity in identities)
    with pytest.raises(Refused, match="ROOT_ALREADY_EXISTS"):
        M.prepare(out, compiler=compiler, capabilities_ref=capabilities, campaign_prefix="q38-mtp-new")


def test_corrupt_native_template_proof_cannot_become_a_pilot(tmp_path, capabilities):
    Path(capabilities["path"]).write_text("{}")
    with pytest.raises(Refused, match="TEMPLATE_PREFLIGHT_CHANGED"):
        M.prepare(tmp_path / "absent", compiler="/unused", capabilities_ref=capabilities, campaign_prefix="valid")
    assert not (tmp_path / "absent").exists()


def test_failed_case_preparation_restores_live_environment(tmp_path, monkeypatch, capabilities):
    monkeypatch.setenv("FORGE_STATE_DIR", "existing-state")
    monkeypatch.setenv("FORGE_EVENTS_DIR", "existing-events")

    def fail(*a, **k):
        raise Refused("SYNTHETIC_PREPARATION_FAILURE")

    monkeypatch.setattr(M.inputs, "prepare", fail)
    with pytest.raises(Refused, match="SYNTHETIC"):
        M.prepare(tmp_path / "partial", compiler="/unused", capabilities_ref=capabilities, campaign_prefix="valid")
    assert os.environ["FORGE_STATE_DIR"] == "existing-state" and os.environ["FORGE_EVENTS_DIR"] == "existing-events"

