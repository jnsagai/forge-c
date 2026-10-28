"""Owner-scoped ASPICE development: functional failures still block; no safety claim."""
import copy
import json
import zipfile

import pytest
import yaml
from forge_factory import workorder as W
from forge_factory.afo import runtime
from forge_factory.assurance import package, scope
from forge_factory.brownfield import resume
from forge_factory.common import REPO_ROOT, sha256_file
from forge_factory.lrtx import profile, runner, swe1
from forge_factory.release import aspice as A
from forge_factory.release import finalize as F


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws, manifest = W.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-ASPICE", purpose=A.PURPOSE)
    return ws, manifest


def test_prepare_retains_original_allocation_as_history_without_reclassifying(ws):
    ws, m = ws
    assert m["historical_safety_scope"]["scope"]["target_asil"] == "B"
    assert "safety_target" not in m and "owner_safety_documents" not in m
    assert not (ws / scope.SCOPE_FILE).exists()
    assert A.selected(m)["safety_approval"] is None
    assert "NOT_ASSESSED" in m["target"]["safety_allocation"]
    assert "No safety approval" in swe1.safety_text(ws)
    assert package.scope_dispositions(ws, ws / "stage")["status"] == "NOT_ASSESSED_ASPICE_ONLY"
    assert scope.workspace_scope_findings(ws, "SWE.1") == []


@pytest.mark.parametrize("change", ["missing", "policy", "purpose", "disabled"])
def test_missing_changed_or_revoked_scope_fails_closed(ws, tmp_path, monkeypatch, change):
    ws, m = ws
    if change == "missing":
        m.pop("aspice_development")
    elif change == "policy":
        m["aspice_development"]["policy_ref"]["sha256"] = "0" * 64
    elif change == "purpose":
        m["purpose"] = "FORMAL_REVIEW"
    else:
        root = tmp_path / "policy"
        path = root / A.POLICY
        path.parent.mkdir(parents=True)
        policy = copy.deepcopy(m["aspice_development"]["owner_decision"])
        policy["enabled"] = False
        path.write_text(yaml.safe_dump(policy))
        monkeypatch.setattr(A, "REPO_ROOT", root)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    assert scope.workspace_scope_findings(ws, "SWE.1") == ["ASPICE_SCOPE_BINDING_CHANGED"]
    with pytest.raises(ValueError):
        swe1.safety_text(ws)


def test_profile_selects_existing_non_safec_paths_and_preserves_xhigh(ws):
    ws, m = ws
    p = profile.load("local-rtx-v2-omniverse2-q38-aspice")
    A.validate_profile(A.PURPOSE, p)
    assert "safec" not in p
    assert p["gateway"]["reasoning"][p["models"]["default"]]["effort"] == "xhigh"
    assert p["runtime"]["fabro_max_output_tokens"] + 32768 < p["runtime"]["fabro_context_tokens"]
    m["local_profile"] = {"id": p["id"]}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    assert runner.author_module(ws, "author", "SWE.1") == "swe1"
    assert runner.inspector_module(ws, "SWE.1") == "review"
    for purpose in ("DEVELOPMENT", "FORMAL_REVIEW"):
        with pytest.raises(ValueError, match="PROFILE_MISMATCH"):
            A.validate_profile(purpose, p)
    with pytest.raises(ValueError, match="PROFILE_MISMATCH"):
        A.validate_profile(A.PURPOSE, profile.load("local-rtx-v2-omniverse2-q38-quality"))


def test_afo_launcher_forwards_explicit_scope_without_changing_legacy_default(monkeypatch):
    calls = []
    monkeypatch.setattr(W, "run", lambda *a, **kw: calls.append(kw) or {"fabro_run_id": "native-fixture"})
    for purpose in (None, A.PURPOSE):
        manifest = {"example": "examples/fixture"}
        if purpose:
            manifest["purpose"] = purpose
        runtime.launcher(manifest, "WO-FIXTURE", {})
    assert "purpose" not in calls[0] and calls[1]["purpose"] == A.PURPOSE


def test_resume_contract_binds_scope_without_changing_old_contracts(ws):
    _, m = ws
    before = copy.deepcopy(resume.contract(m))
    m["aspice_development"]["policy_ref"]["sha256"] = "1" * 64
    assert resume.contract(m) != before
    legacy = resume.contract({})
    assert "aspice_development" not in legacy and "historical_safety_scope" not in legacy


@pytest.mark.parametrize("fault", [None, "static", "trace", "inspection", "open-finding", "unfinished"])
def test_finalizer_removes_only_safety_obligations_and_preserves_engineering_gates(tmp_path, monkeypatch, fault):
    from test_m7_governance_release import complete_workspace

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(tmp_path / "archives"))
    ws = tmp_path / "ws"
    ws.mkdir()
    complete_workspace(ws)  # Synthetic six-phase evidence, not product qualification.
    path = ws / ".forge-run/manifest.json"
    m = json.loads(path.read_text())
    m.update(purpose=A.PURPOSE, aspice_development=A.binding())
    path.write_text(json.dumps(m))
    stage = tmp_path / "stage"
    F.build_staging(ws, stage, "fixture", None)
    for f in (stage / "safety").glob("*"):
        if f.is_file():
            f.unlink()
    base_sha = sha256_file(F.POLICY_V05)
    p = A.effective_policy(F.POLICY_V05, ws, stage)
    policy = json.loads(p.read_text())
    base = json.loads(F.POLICY_V05.read_text())
    assert set(base["required_files"]) - set(policy["required_files"]) == {
        f for f in base["required_files"] if f.startswith("safety/")}
    assert set(base["required_quality_checks"]) - set(policy["required_quality_checks"]) == {"safety_gaps_declared"}
    assert policy["required_patterns"] == base["required_patterns"]
    qpath = stage / "quality/final-gates.json"
    q = json.loads(qpath.read_text())
    if fault in ("static", "trace", "inspection"):
        q["checks"][{"static": "static_analysis", "trace": "traceability", "inspection": "swe1_inspection"}[fault]] = False
    elif fault == "open-finding":
        q["open_findings"].append({"id": "REAL-DEFECT", "severity": "major"})
    elif fault == "unfinished":
        q["run_status"] = "INCOMPLETE"
    qpath.write_text(json.dumps(q))
    # Operational/KPI inventory is produced by the real finalizer, independently
    # tested below. For this direct policy test use v0.4 (same engineering checks).
    p = A.effective_policy(F.POLICY_V04, ws, stage)
    result = F._packager().build(stage, tmp_path / "out", "fixture", p)
    assert result["package_status"] == ("BLOCKED" if fault else "READY_FOR_OFFLINE_REVIEW")
    assert sha256_file(F.POLICY_V05) == base_sha


def test_real_finalizer_seals_unassessed_scope_in_archive(tmp_path, monkeypatch):
    from test_m7_governance_release import complete_workspace

    for name in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + name + "_DIR", str(tmp_path / name))
    ws = tmp_path / "ws"
    ws.mkdir()
    complete_workspace(ws)
    path = ws / ".forge-run/manifest.json"
    m = json.loads(path.read_text())
    m.update(purpose=A.PURPOSE, aspice_development=A.binding())
    path.write_text(json.dumps(m))
    result = F.finalize(ws, "aspice-fixture")
    assert result["package_status"] == "READY_FOR_OFFLINE_REVIEW", result["gaps"]
    assert result["work_order_purpose"] == A.PURPOSE
    with zipfile.ZipFile(result["archive"]) as archive:
        record = json.loads(archive.read("evidence/" + A.SNAPSHOT))
        assert record["safety_approval"] is None and record["assessed_aspice_compliance"] is None


def test_tampered_binding_blocks_packaging_even_with_safety_files_present(tmp_path, monkeypatch):
    from test_m7_governance_release import complete_workspace

    for name in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + name + "_DIR", str(tmp_path / name))
    ws = tmp_path / "ws"
    ws.mkdir()
    complete_workspace(ws)
    path = ws / ".forge-run/manifest.json"
    m = json.loads(path.read_text())
    m.update(purpose=A.PURPOSE, aspice_development=A.binding())
    m["aspice_development"]["policy_ref"]["sha256"] = "0" * 64
    path.write_text(json.dumps(m))
    result = F.finalize(ws, "tampered-aspice-fixture")
    assert result["package_status"] == "BLOCKED"
    assert any("ASPICE_SCOPE_BINDING_CHANGED" in str(g) for g in result["gaps"])
