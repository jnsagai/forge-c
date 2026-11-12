"""Owner development exception with synthetic package fixtures, never product qualification."""
import copy
import json
import zipfile

import pytest
import yaml
from forge_factory import workorder as WO
from forge_factory.assurance import package as A
from forge_factory.assurance.scope import DOC_FILES
from forge_factory.common import REPO_ROOT, sha256_file
from forge_factory.release import development as D
from forge_factory.release import finalize as F


@pytest.fixture
def package(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws, stage = tmp_path / "ws", tmp_path / "stage"
    (ws / ".forge-run").mkdir(parents=True)
    manifest = {"purpose": "DEVELOPMENT", "development_safety": D.binding("DEVELOPMENT"),
                "owner_safety_documents": [], "owner_safety_document_issues": [
                    "SAFETY_DOC_NOT_REGISTERED:" + key for key in DOC_FILES]}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    base = json.loads(F.POLICY_V05.read_text())
    # Complete only for the unchanged MECHANICAL packager; these bytes are not
    # compiler/verification or product evidence and never count toward DA-T027.
    for name in base["required_files"]:
        if name in DOC_FILES.values():
            continue
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic fixture\n")
    for pattern in base["required_patterns"]:
        path = stage / pattern.replace("*", "fixture")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic fixture\n")
    quality = {"run_status": "COMPLETED", "open_findings": [],
               "checks": dict.fromkeys(base["required_quality_checks"], True)}
    (stage / base["quality_report"]).parent.mkdir(parents=True, exist_ok=True)
    (stage / base["quality_report"]).write_text(json.dumps(quality))
    return ws, stage, manifest, base


def build(tmp_path, stage, policy, name="fixture"):
    return F._packager().build(stage, tmp_path / (name + "-out"), name, policy)


def test_development_defers_exactly_ssa_taa_and_records_unapproved_status(package, tmp_path):
    ws, stage, manifest, base = package
    original = sha256_file(F.POLICY_V05)
    strict = build(tmp_path, stage, F.POLICY_V05, "strict")
    assert strict["package_status"] == "BLOCKED" and strict["gap_count"] == 2
    policy = D.effective_policy(F.POLICY_V05, ws, stage)
    effective = json.loads(policy.read_text())
    assert set(base["required_files"]) - set(effective["required_files"]) == set(DOC_FILES.values())
    assert effective["required_quality_checks"] == base["required_quality_checks"]
    assert effective["required_patterns"] == base["required_patterns"]
    assert effective["required_sections"] == base["required_sections"]
    assert effective["require_completed_run"] and effective["require_no_open_findings"]
    assert json.loads((stage / D.SNAPSHOT).read_text()) == manifest["development_safety"]
    deferrals = json.loads((stage / D.DEFERRALS).read_text())
    assert deferrals["safety_approval"] is None and deferrals["status"] == "DEFERRED_DEVELOPMENT"
    assert deferrals["formal_review_signature_requirement"] == "REQUIRED"
    result = build(tmp_path, stage, policy, "development")
    assert result["package_status"] == "READY_FOR_OFFLINE_REVIEW" and result["gap_count"] == 0
    assert sha256_file(F.POLICY_V05) == original
    assert not any((stage / path).exists() for path in DOC_FILES.values())


@pytest.mark.parametrize("change", ["failed-phase", "unfinished", "open-finding", "missing-safety-requirements"])
def test_engineering_failures_still_block_development_packages(package, tmp_path, change):
    ws, stage, _, base = package
    path = stage / base["quality_report"]
    quality = json.loads(path.read_text())
    if change == "failed-phase":
        quality["checks"]["swe1_inspection"] = False
    elif change == "unfinished":
        quality["run_status"] = "INCOMPLETE"
    elif change == "open-finding":
        quality["open_findings"] = [{"id": "REAL-DEFECT", "severity": "major"}]
    else:
        (stage / "safety/software_safety_requirements.md").unlink()
    path.write_text(json.dumps(quality))
    result = build(tmp_path, stage, D.effective_policy(F.POLICY_V05, ws, stage))
    assert result["package_status"] == "BLOCKED" and result["gap_count"] > 0


@pytest.mark.parametrize("change", ["purpose-only", "formal", "legacy"])
def test_only_a_bound_development_decision_can_select_the_exception(package, tmp_path, change):
    ws, stage, manifest, _ = package
    if change == "formal":
        manifest = {"purpose": "FORMAL_REVIEW"}
    elif change == "legacy":
        manifest = {}
    else:
        manifest.pop("development_safety")
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    assert D.effective_policy(F.POLICY_V05, ws, stage) == F.POLICY_V05
    assert build(tmp_path, stage, F.POLICY_V05)["package_status"] == "BLOCKED"


@pytest.mark.parametrize("change", ["hash", "purpose", "decision", "revoked"])
def test_changed_or_revoked_bindings_are_blocking_even_with_both_documents(package, tmp_path, monkeypatch, change):
    ws, stage, manifest, _ = package
    for name in DOC_FILES.values():
        (stage / name).write_text("synthetic intact formal document\n")
    if change == "hash":
        manifest["development_safety"]["policy_ref"]["sha256"] = "0" * 64
    elif change == "purpose":
        manifest["purpose"] = "FORMAL_REVIEW"
    elif change == "decision":
        manifest["development_safety"]["owner_decision"]["approved_by"] = "qwen"
    else:
        root = tmp_path / "revoked"
        path = root / D.POLICY
        path.parent.mkdir(parents=True)
        policy = copy.deepcopy(manifest["development_safety"]["owner_decision"])
        policy["enabled"] = False
        path.write_text(yaml.safe_dump(policy))
        monkeypatch.setattr(D, "REPO_ROOT", root)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    assert D.effective_policy(F.POLICY_V05, ws, stage) == F.POLICY_V05
    result = build(tmp_path, stage, F.POLICY_V05)
    assert result["package_status"] == "BLOCKED" and result["gap_count"] > 0


@pytest.mark.parametrize("purpose", D.PURPOSES)
def test_prepare_binds_the_owner_policy_without_signing_or_reclassifying_asil(tmp_path, monkeypatch, purpose):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws, manifest = WO.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-DEV-POLICY", purpose=purpose)
    assert manifest["purpose"] == purpose and manifest["safety_target"] == "B"
    if purpose == "DEVELOPMENT":
        assert D.selected(manifest)["safety_approval"] is None
    else:
        assert "development_safety" not in manifest
    scope = json.loads((ws / ".forge-run/safety_scope.json").read_text())
    assert scope["scope"]["target_asil"] == "B"


def test_assurance_defers_documents_without_claiming_qm_or_waiving_hsi(package):
    ws, stage, manifest, _ = package
    scope = {"scope": {"scope_id": "SC-T", "work_order_id": "WO-T", "target_asil": "B",
             "source_requirements_hash": "B0", "hsi_hash": "h", "allocation_review_ref": "r",
             "product_asil_source": "approved:test"}, "na": {}}
    (ws / A.SCOPE_FILE).write_text(json.dumps(scope))
    out = A.scope_dispositions(ws, stage)
    assert out["target_asil"] == "B" and out["safety_approval"] is None
    assert set(out["dispositions"].values()) == {"DEFERRED_DEVELOPMENT"}
    assert out["issues"] == [] and out["status"] == "DEVELOPMENT_DEFERRED"
    scope["scope"]["target_asil"] = "QM"
    (ws / A.SCOPE_FILE).write_text(json.dumps(scope))
    assert A.scope_dispositions(ws, stage)["status"] == "DEVELOPMENT_DEFERRED"
    scope["scope"]["target_asil"] = "B"
    scope["na"] = {"software_safety_analysis": {"rationale": "not allowed for an ASIL B fixture", "approved_by": "Owner"}}
    (ws / A.SCOPE_FILE).write_text(json.dumps(scope))
    assert "NA_NOT_PERMITTED_FOR_ASIL:software_safety_analysis" in A.scope_dispositions(ws, stage)["issues"]
    scope["na"] = {}
    scope["scope"]["hsi_hash"] = None
    (ws / A.SCOPE_FILE).write_text(json.dumps(scope))
    out = A.scope_dispositions(ws, stage)
    assert "SAFETY_EVIDENCE_MISSING:hsi" in out["issues"] and out["status"] == "BLOCKED"
    manifest.pop("development_safety")
    manifest["purpose"] = "FORMAL_REVIEW"
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    out = A.scope_dispositions(ws, stage)
    assert set(out["dispositions"].values()) == {"MISSING"}


def test_unknown_purpose_is_refused():
    with pytest.raises(ValueError, match="PURPOSE_INVALID"):
        D.binding("production-looking-typo")


def test_finalizer_seals_development_deferrals_and_retains_formal_signature_gaps(package, tmp_path, monkeypatch):
    from test_m7_governance_release import complete_workspace

    _, _, manifest, _ = package
    ws = tmp_path / "finalizer-ws"
    ws.mkdir()
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(tmp_path / "archives"))
    complete_workspace(ws)  # Existing synthetic six-phase evidence fixture.
    path = ws / ".forge-run/manifest.json"
    prepared = json.loads(path.read_text())
    prepared.update(manifest)
    manifest = prepared
    path.write_text(json.dumps(manifest))
    development = F.finalize(ws, "development-signature-fixture")
    assert development["package_status"] == "READY_FOR_OFFLINE_REVIEW", development["gaps"]
    assert development["scope"] == "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED"
    assert development["work_order_purpose"] == "DEVELOPMENT"
    assert development["policy"].endswith("release-package-policy-v0.5-development.json")
    with zipfile.ZipFile(development["archive"]) as archive:
        report = json.loads(archive.read("evidence/" + D.DEFERRALS))
        assert report["status"] == "DEFERRED_DEVELOPMENT" and report["safety_approval"] is None
        assert "evidence/" + D.SNAPSHOT in archive.namelist()
    digest = sha256_file(development["archive"])
    manifest.pop("development_safety")
    manifest["purpose"] = "FORMAL_REVIEW"
    path.write_text(json.dumps(manifest))
    formal = F.finalize(ws, "formal-signature-fixture")
    assert formal["package_status"] == "BLOCKED"
    assert all("missing_or_empty_file:" + rel in formal["gaps"] for rel in DOC_FILES.values())
    assert sha256_file(development["archive"]) == digest
