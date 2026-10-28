"""Prospective owner-selected ASPICE engineering scope, without safety assurance.

This is a development scope, not an ASPICE assessment or a product ASIL change.
Existing DEVELOPMENT and FORMAL_REVIEW bindings/policies remain unchanged.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from ..assurance.policy import _human
from ..common import REPO_ROOT, load_yaml, pretty_json, sha256_file
from .development import BASES

PURPOSE = "ASPICE_ONLY"
POLICY = "config/factory/aspice-development-policy.yaml"
SNAPSHOT = "configuration/aspice-development-policy.json"
STATEMENT = ("ASPICE-only engineering development. Safety assurance is not assessed in this lane. "
             "No safety approval, ASIL classification or formally assessed ASPICE compliance is claimed.")


def binding(*, repo=None):
    root = Path(repo or REPO_ROOT)
    path = root / POLICY
    policy = load_yaml(path) if path.is_file() else None
    if (not isinstance(policy, dict) or policy.get("schema") != "forge-c/aspice-development-policy/1"
            or policy.get("enabled") is not True or policy.get("purpose") != PURPOSE
            or not _human(policy.get("approved_by")) or not policy.get("approved_at")
            or not policy.get("decision") or not policy.get("request")
            or policy.get("safety_approval") is not None
            or policy.get("assessed_aspice_compliance") is not None):
        raise ValueError("ASPICE_SCOPE_POLICY_INVALID_OR_DISABLED")
    return {"schema": "forge-c/aspice-development-binding/1", "purpose": PURPOSE,
            "policy_ref": {"path": POLICY, "sha256": sha256_file(path)}, "owner_decision": policy,
            "validator_sha256": sha256_file(Path(__file__)),
            "base_policies": {p: sha256_file(root / p) for p in BASES},
            "safety_approval": None, "assessed_aspice_compliance": None, "statement": STATEMENT}


def selected(manifest, *, repo=None):
    saved = manifest.get("aspice_development")
    if manifest.get("purpose") != PURPOSE:
        if saved is not None:
            raise ValueError("ASPICE_SCOPE_BINDING_CHANGED")
        return None
    if saved is None or saved != binding(repo=repo):
        raise ValueError("ASPICE_SCOPE_BINDING_CHANGED")
    return saved


def workspace_record(ws):
    path = Path(ws) / ".forge-run/manifest.json"
    return selected(json.loads(path.read_text())) if path.is_file() else None


def validate_profile(purpose, prof):
    """A nonsemantic profile cannot silently change a formal order's scope."""
    selected_purpose = (prof or {}).get("work_order_purpose")
    structured = (prof or {}).get("structured") or {}
    if ((selected_purpose is not None and purpose != selected_purpose)
            or (purpose == PURPOSE and (
                selected_purpose != PURPOSE
                or structured.get("semantic_phases")
                or structured.get("semantic_inspect_phases")))):
        raise ValueError("ASPICE_SCOPE_PROFILE_MISMATCH")


def effective_policy(base, ws, stage):
    """Remove only safety artifacts/checks; every functional quality gate remains."""
    from .development import effective_policy as legacy

    path = Path(ws) / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text()) if path.is_file() else {}
    try:
        record = selected(manifest)
    except ValueError:
        quality_path = stage / "quality/final-gates.json"
        quality = json.loads(quality_path.read_text())
        quality.setdefault("open_findings", []).append({
            "id": "ASPICE_SCOPE_BINDING_CHANGED", "severity": "major",
            "detail": "ASPICE-only scope unavailable; strict package policy retained"})
        quality_path.write_text(pretty_json(quality))
        return base
    if record is None:
        return legacy(base, ws, stage)
    relative = base.relative_to(REPO_ROOT).as_posix()
    if record["base_policies"].get(relative) != sha256_file(base):
        raise ValueError("ASPICE_BASE_POLICY_CHANGED")
    policy = copy.deepcopy(json.loads(base.read_text()))
    policy["required_files"] = [p for p in policy["required_files"] if not p.startswith("safety/")]
    policy["required_files"].append(SNAPSHOT)
    policy["required_sections"] = [p for p in policy["required_sections"] if p != "safety"]
    policy["required_quality_checks"] = [p for p in policy["required_quality_checks"] if p != "safety_gaps_declared"]
    policy.update(extends={"path": relative, "sha256": sha256_file(base)},
                  schema=policy["schema"] + "-aspice-development", safety_target="NOT_ASSESSED",
                  assurance_statement=STATEMENT)
    out = stage / SNAPSHOT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pretty_json(record))
    destination = stage / "configuration" / (base.stem + "-aspice-development.json")
    destination.write_text(pretty_json(policy))
    return destination
