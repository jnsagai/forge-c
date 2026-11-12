"""Owner-authorized SSA/TAA deferral for development; no engineering-gate waiver.

Legacy and FORMAL_REVIEW work orders retain their original policies. New development
orders bind this owner decision and the unchanged formal policy hashes. Neither
this record nor a development READY package is a safety approval.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from ..assurance.policy import _human
from ..assurance.scope import DOC_FILES
from ..common import REPO_ROOT, load_yaml, pretty_json, sha256_file

PURPOSES = ("DEVELOPMENT", "FORMAL_REVIEW")
POLICY = "config/factory/development-safety-policy.yaml"
BASES = tuple(f"factory/release-manager/policies/release-package-policy-v{v}.json" for v in ("0.4", "0.5"))
SNAPSHOT = "configuration/development-safety-policy.json"
DEFERRALS = "safety/development-signature-deferrals.json"


def binding(purpose, *, repo=None):
    root = Path(repo or REPO_ROOT)
    if purpose not in PURPOSES:
        raise ValueError("WORK_ORDER_PURPOSE_INVALID")
    if purpose != "DEVELOPMENT":
        return None
    path = root / POLICY
    if not path.is_file():
        return None
    policy = load_yaml(path)
    if (
        not isinstance(policy, dict) or policy.get("schema") != "forge-c/development-safety-policy/1"
        or type(policy.get("enabled")) is not bool or policy.get("purpose") != "DEVELOPMENT"
        or policy.get("deferred_documents") != list(DOC_FILES)
        or not _human(policy.get("approved_by")) or not policy.get("approved_at")
        or not isinstance(policy.get("decision"), str) or not policy["decision"].strip()
    ):
        raise ValueError("DEVELOPMENT_SAFETY_POLICY_INVALID")
    if not policy["enabled"]:
        return None
    return {"schema": "forge-c/development-safety-binding/1", "purpose": purpose,
            "policy_ref": {"path": POLICY, "sha256": sha256_file(path)}, "owner_decision": policy,
            "validator_sha256": sha256_file(Path(__file__)),
            "base_policies": {p: sha256_file(root / p) for p in BASES},
            "safety_approval": None, "scope": "DEVELOPMENT_ONLY_SIGNATURES_DEFERRED"}


def selected(manifest, *, repo=None):
    """A purpose flag alone cannot activate the exception; require the bound decision."""
    saved = manifest.get("development_safety")
    if saved is None:
        return None
    if manifest.get("purpose") != "DEVELOPMENT" or saved != binding("DEVELOPMENT", repo=repo):
        raise ValueError("DEVELOPMENT_SAFETY_BINDING_CHANGED")
    return saved


def effective_policy(base: Path, ws: Path, stage: Path) -> Path:
    """Derive only the two document deferrals; leave all mechanical gates intact.

    Invalid/revoked bindings produce an ordinary blocking finding and use the
    strict policy, so terminal finalization can still publish a BLOCKED package.
    """
    path = Path(ws) / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text()) if path.is_file() else {}
    try:
        record = selected(manifest)
    except ValueError:
        quality_path = stage / "quality/final-gates.json"
        quality = json.loads(quality_path.read_text())
        finding = {"id": "DEVELOPMENT_SAFETY_BINDING_CHANGED", "severity": "major",
                   "detail": "Development deferral unavailable; strict package policy retained"}
        if finding not in quality.setdefault("open_findings", []):
            quality["open_findings"].append(finding)
        quality_path.write_text(pretty_json(quality))
        return base
    if record is None:
        return base
    relative = base.relative_to(REPO_ROOT).as_posix()
    if relative not in record["base_policies"] or sha256_file(base) != record["base_policies"][relative]:
        raise ValueError("DEVELOPMENT_BASE_POLICY_CHANGED")
    policy = copy.deepcopy(json.loads(base.read_text()))
    policy["required_files"] = [p for p in policy["required_files"] if p not in DOC_FILES.values()]
    policy["required_files"] += [SNAPSHOT, DEFERRALS]
    policy["extends"] = {"path": relative, "sha256": sha256_file(base)}
    policy["schema"] += "-development"
    policy["safety_target"] = "DEVELOPMENT evidence only; allocated ASIL unchanged; SSA/TAA signatures deferred"
    for name, value in ((SNAPSHOT, record), (DEFERRALS, {
        "schema": "forge-c/development-signature-deferrals/1", "status": "DEFERRED_DEVELOPMENT",
        "documents": list(DOC_FILES), "owner_decision": record["owner_decision"]["decision"],
        "recorded_document_issues": manifest.get("owner_safety_document_issues", []),
        "safety_approval": None, "formal_review_signature_requirement": "REQUIRED",
    })):
        out = stage / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(pretty_json(value))
    destination = stage / "configuration" / (base.stem + "-development.json")
    destination.write_text(pretty_json(policy))
    return destination
