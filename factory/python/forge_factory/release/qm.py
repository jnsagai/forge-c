"""Owner-selected QM development through the existing scope, checklist and release gates."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from ..afo.durable import digest
from ..assurance.policy import _human
from ..common import REPO_ROOT, load_yaml, pretty_json, sha256_file
from .development import BASES

PURPOSE = "QM"
FIELD = "qm_development"
POLICY = "config/factory/qm-development-policy.yaml"
SNAPSHOT = "configuration/qm-development-policy.json"
TAILORED = {"SWE1-01", "SWE1-03", "SWE2-04", "SWE6-03", "SWE6-06"}
STATEMENT = ("OUT_OF_SCOPE: QM development selected by the owner. No software safety requirements, "
             "allocated safety safe state or safety assurance are required. Functional requirements, "
             "startup/error behavior, resource constraints, traceability and verification remain required.")


def binding(*, repo=None):
    root = Path(repo or REPO_ROOT)
    policy = load_yaml(root / POLICY)
    if (not isinstance(policy, dict) or policy.get("schema") != "forge-c/qm-development-policy/1"
            or policy.get("purpose") != PURPOSE or policy.get("enabled") is not True
            or not _human(policy.get("approved_by")) or not policy.get("approved_at")
            or not policy.get("decision") or not policy.get("request")
            or policy.get("classification") != "QM" or policy.get("safety_approval") is not None
            or policy.get("assessed_aspice_compliance") is not None
            or not isinstance(policy.get("criterion_tailoring"), dict)
            or set(policy["criterion_tailoring"]) != TAILORED):
        raise ValueError("QM_SCOPE_POLICY_INVALID_OR_DISABLED")
    if any(not isinstance(change, dict) or set(change) != {"original_criterion_sha256", "criterion"}
           or not isinstance(change["criterion"], str) or len(change["criterion"].strip()) < 20
           or not isinstance(change["original_criterion_sha256"], str)
           or len(change["original_criterion_sha256"]) != 64
           or set(change["original_criterion_sha256"]) - set("0123456789abcdef")
           for change in policy["criterion_tailoring"].values()):
        raise ValueError("QM_CHECKLIST_TAILORING_INVALID")
    return {"schema": "forge-c/qm-development-binding/1", "purpose": PURPOSE,
            "policy_ref": {"path": POLICY, "sha256": sha256_file(root / POLICY)},
            "owner_decision": policy, "validator_sha256": sha256_file(Path(__file__)),
            "base_policies": {p: sha256_file(root / p) for p in BASES},
            "base_checklists": {f"SWE.{n}": sha256_file(root / f"factory/release-manager/checklists/SWE.{n}.yaml")
                                for n in range(1, 7)},
            "classification": "QM", "statement": STATEMENT, "safety_approval": None}


def selected(manifest):
    saved = manifest.get(FIELD)
    if manifest.get("purpose") != PURPOSE:
        if saved is not None:
            raise ValueError("QM_SCOPE_BINDING_CHANGED")
        return None
    if saved is None or saved != binding() or manifest.get("safety_target") != "QM":
        raise ValueError("QM_SCOPE_BINDING_CHANGED")
    return saved


def scope_record(work_order, inputs_sha256):
    policy = binding()["owner_decision"]
    return {"scope": {"scope_id": policy["decision"], "work_order_id": work_order,
                      "target_asil": "QM", "source_requirements_hash": inputs_sha256,
                      "hsi_hash": None, "allocation_review_ref": None,
                      "product_asil_source": "owner decision: " + policy["decision"]},
            "approved_by": policy["approved_by"], "approved_at": policy["approved_at"],
            "documents": [], "document_issues": [],
            "na": {key: {"approved_by": policy["approved_by"], "approved_at": policy["approved_at"],
                         "rationale": "Owner explicitly selected QM development: " + policy["request"]}
                   for key in ("software_safety_analysis", "tool_assurance_assessment")}}


def workspace_record(ws):
    ws = Path(ws)
    manifest = ws / ".forge-run/manifest.json"
    if not manifest.is_file():
        return None
    man = json.loads(manifest.read_text())
    record = selected(man)
    if record:
        expected = scope_record(man["work_order"], digest(sorted((i["path"], i.get("sha256")) for i in man["inputs"])))
        path = ws / ".forge-run/safety_scope.json"
        if path.is_symlink() or json.loads(path.read_text()) != expected:
            raise ValueError("QM_SCOPE_RECORD_CHANGED")
    return record


def validate_profile(purpose, prof):
    if (purpose != PURPOSE or prof.get("work_order_purpose") != PURPOSE
            or prof.get("safec") or (prof.get("structured") or {}).get("semantic_phases")
            or (prof.get("structured") or {}).get("semantic_inspect_phases")):
        raise ValueError("QM_SCOPE_PROFILE_MISMATCH")


def checklist(manifest, resolved):
    record = selected(manifest)
    if not record:
        return resolved
    phase = resolved["phase"]
    if sha256_file(REPO_ROOT / f"factory/release-manager/checklists/{phase}.yaml") != record["base_checklists"][phase]:
        raise ValueError("QM_CHECKLIST_BASE_CHANGED")
    changes = record["owner_decision"]["criterion_tailoring"]
    checks, applied = [], {}
    for check in resolved["checks"]:
        change = changes.get(check["id"])
        if change:
            if digest(check["criterion"]) != change["original_criterion_sha256"]:
                raise ValueError("QM_CHECKLIST_CRITERION_CHANGED")
            applied[check["id"]] = {"original": check["criterion"], "criterion": change["criterion"]}
            check = {**check, "criterion": change["criterion"]}
        checks.append(check)
    return {**resolved, "checks": checks, "qm_tailoring": applied,
            "sha256": digest({"base_checklist_sha256": resolved["sha256"],
                              "qm_binding_sha256": digest(record), "checks": checks})}


def effective_policy(base, ws, stage):
    from .aspice import effective_policy as previous

    try:
        record = workspace_record(ws)
    except (OSError, ValueError, KeyError):
        qpath = stage / "quality/final-gates.json"
        quality = json.loads(qpath.read_text())
        quality.setdefault("open_findings", []).append({"id": "QM_SCOPE_BINDING_CHANGED", "severity": "major",
                                                       "detail": "QM scope invalid; strict release policy retained"})
        qpath.write_text(pretty_json(quality))
        return base
    if not record:
        return previous(base, ws, stage)
    relative = base.relative_to(REPO_ROOT).as_posix()
    if record["base_policies"].get(relative) != sha256_file(base):
        raise ValueError("QM_BASE_POLICY_CHANGED")
    policy = copy.deepcopy(json.loads(base.read_text()))
    policy["required_files"] = [p for p in policy["required_files"] if not p.startswith("safety/")] + [SNAPSHOT]
    policy["required_sections"] = [p for p in policy["required_sections"] if p != "safety"]
    policy["required_quality_checks"] = [p for p in policy["required_quality_checks"] if p != "safety_gaps_declared"]
    policy.update(extends={"path": relative, "sha256": sha256_file(base)},
                  schema=policy["schema"] + "-qm-development", safety_target="QM", assurance_statement=STATEMENT)
    (stage / SNAPSHOT).parent.mkdir(parents=True, exist_ok=True)
    (stage / SNAPSHOT).write_text(pretty_json(record))
    path = stage / "configuration" / (base.stem + "-qm-development.json")
    path.write_text(pretty_json(policy))
    return path
