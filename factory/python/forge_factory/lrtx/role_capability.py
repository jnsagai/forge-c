"""Pinned per-role capability envelopes; diagnosis is not author/inspector qualification."""

from __future__ import annotations
import json
from pathlib import Path
from ..afo.durable import Refused, digest, immutable_json
from ..common import state_dir, sha256_file

IDENTITY = (
    "role",
    "model_digest",
    "precision",
    "reasoning",
    "schema_mode",
    "adapter_revision",
    "context_tokens",
    "sampling",
    "task_class",
)


def key(identity):
    if (
        set(identity) != set(IDENTITY)
        or not identity["model_digest"]
        or type(identity["context_tokens"]) is not int
        or identity["context_tokens"] < 1
        or any(
            not isinstance(identity[k], str) or not identity[k] or len(identity[k]) > 256
            for k in IDENTITY
            if k not in ("context_tokens", "sampling")
        )
        or not isinstance(identity["sampling"], dict)
        or not identity["sampling"]
    ):
        raise Refused("ROLE_CAPABILITY_IDENTITY_INCOMPLETE")
    return digest(identity)


def record(identity, *, report_path, report_sha256, expected_manifest_sha256):
    """Only independent campaign tooling supplies this receipt, never a model or capability self-assessment."""
    ident = key(identity)
    p = Path(report_path)
    if p.is_symlink() or sha256_file(p) != report_sha256:
        raise Refused("CAPABILITY_REPORT_CHANGED")
    report = json.loads(p.read_text())
    if (
        report.get("manifest_sha256") != expected_manifest_sha256
        or report.get("identity_sha256") != ident
        or report.get("status") != "PASS"
        or not report.get("independent_oracle_refs")
        or report.get("execution_host") not in ("omniverse", "omniverse2")
    ):
        raise Refused("CAPABILITY_NOT_INDEPENDENTLY_QUALIFIED")
    envelope = report.get("envelope") or {}
    if type(envelope.get("max_obligations")) is not int or envelope["max_obligations"] < 1:
        raise Refused("ROLE_CAPABILITY_ENVELOPE_UNMEASURED")
    for ref in report["independent_oracle_refs"]:
        if (
            not isinstance(ref, dict)
            or ref.get("producer") not in ("CRE", "reference", "metamorphic", "mutant", "deterministic_gate")
            or Path(ref["path"]).is_symlink()
            or sha256_file(Path(ref["path"])) != ref["sha256"]
        ):
            raise Refused("ROLE_CAPABILITY_ORACLE_UNRESOLVED")
    rec = {
        "schema": "forge-c/role-capability/1",
        "identity": identity,
        "identity_sha256": ident,
        "report": {"path": str(p), "sha256": report_sha256},
        "manifest_sha256": expected_manifest_sha256,
        "envelope": report["envelope"],
        "qualified": True,
    }
    out = state_dir() / "lrtx/capabilities/roles" / f"{ident}.json"
    immutable_json(out, rec)
    return {"path": str(out), "sha256": sha256_file(out)}


def require(ref, identity, *, semantic_obligations=None):
    if not ref:
        raise Refused("CAPABILITY_LIMIT", "role has no measured independent capability receipt")
    p = Path(ref["path"])
    root = (state_dir() / "lrtx/capabilities/roles").resolve()
    if p.is_symlink() or root not in p.resolve().parents or sha256_file(p) != ref["sha256"]:
        raise Refused("ROLE_CAPABILITY_REFERENCE_CHANGED")
    rec = json.loads(p.read_text())
    if rec["identity_sha256"] != key(identity) or rec["identity"] != identity or rec["qualified"] is not True:
        raise Refused("ROLE_CAPABILITY_IDENTITY_MISMATCH")
    q = rec["report"]
    if sha256_file(Path(q["path"])) != q["sha256"]:
        raise Refused("ROLE_CAPABILITY_REPORT_STALE")
    report = json.loads(Path(q["path"]).read_text())
    for oracle in report["independent_oracle_refs"]:
        path = Path(oracle["path"])
        if path.is_symlink() or sha256_file(path) != oracle["sha256"]:
            raise Refused("ROLE_CAPABILITY_ORACLE_STALE")
    if semantic_obligations is not None and semantic_obligations > rec["envelope"]["max_obligations"]:
        raise Refused("CAPABILITY_LIMIT", "coherent objective exceeds measured semantic complexity")
    return rec


def admit_job(job, role, *, input_tokens, output_tokens, body=None):
    """Production role admission or a separately signed qualification campaign, never blanket model competence."""
    from ..afo import authz
    from ..afo.policy import load

    eff = load()
    campaign = job.get("qualification_manifest_sha256")
    if campaign:
        grant = authz.find(eff.mode, eff.sha256 or "", ref=eff.get("authorization_ref"), action="recover_workorder")
        if not grant.allow:
            raise Refused(grant.code)
        record = json.loads((authz.AUTH_DIR / f"{eff.get('authorization_ref')}.json").read_text())
        if record.get("signed_runbook_ref") != "qualification-014:" + campaign:
            raise Refused("QUALIFICATION_CAMPAIGN_NOT_AUTHORIZED")
        entry = {"identity": job.get("qualification_identity")}
        if job.get("model") != job.get("qualification_model_profile"):
            raise Refused("QUALIFICATION_MODEL_PROFILE_CHANGED")
    else:
        entry = (job.get("role_capabilities") or {}).get(role)
        if not entry:
            raise Refused("CAPABILITY_LIMIT", "role capability has not been independently measured")
    identity = entry["identity"]
    if not identity:
        raise Refused("QUALIFICATION_IDENTITY_NOT_PROVISIONED")
    key(identity)
    if identity["role"] != role or job.get("model_digest") != identity["model_digest"]:
        raise Refused("ROLE_CAPABILITY_MODEL_OR_ROLE_CHANGED")
    revision = (job.get("factory_revision") or {}).get("commit")
    if revision and identity["adapter_revision"] != revision:
        raise Refused("ROLE_CAPABILITY_ADAPTER_CHANGED")
    if job.get("precision") and identity["precision"] != job["precision"]:
        raise Refused("ROLE_CAPABILITY_PRECISION_CHANGED")
    if body is not None:
        mode = (body.get("response_format") or {}).get("type") or ("tool" if body.get("tools") else "unconstrained")
        if mode != identity["schema_mode"] or body.get("reasoning_effort", "none") != identity["reasoning"]:
            raise Refused("ROLE_CAPABILITY_REASONING_OR_SCHEMA_CHANGED")
        if any(body.get(k) != v for k, v in identity["sampling"].items()):
            raise Refused("ROLE_CAPABILITY_SAMPLING_CHANGED")
    rec = (
        {"qualification_only": True}
        if campaign
        else require(entry["ref"], identity, semantic_obligations=1 if role == "afo-recovery-planner" else None)
    )
    if input_tokens + output_tokens > identity["context_tokens"]:
        raise Refused("CAPABILITY_LIMIT", "complete serialized request exceeds qualified context allowance")
    return rec


def local_alternatives(manifest, phase, *, allowed_profiles, adapter_revision):
    """Only operator-pinned, independently qualified local author/inspector pairs."""
    from .profile import load

    local = manifest.get("profile")
    if not local or not manifest.get("qualified_local_alternatives"):
        return []
    profile = load(local)
    roles = [phase.lower().replace(".", "") + suffix for suffix in ("-author", "-inspector")]
    eligible = []
    for entry in manifest.get("qualified_local_alternatives") or []:
        model = entry.get("model_profile")
        info = profile["models"]["allowed"].get(model)
        if model not in allowed_profiles or not info:
            continue
        try:
            for role in roles:
                cap = entry["role_capabilities"][role]
                identity = cap["identity"]
                if (
                    identity["role"] != role
                    or identity["model_digest"] != info["digest"]
                    or identity["precision"] != info["quantization"]
                    or identity["adapter_revision"] != adapter_revision
                ):
                    raise Refused("LOCAL_ALTERNATIVE_IDENTITY_MISMATCH")
                require(cap["ref"], identity)
            eligible.append(model)
        except (Refused, KeyError, TypeError, OSError, ValueError):
            continue
    return eligible
