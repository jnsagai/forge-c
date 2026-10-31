"""Separately signed, finite product-role experiments; never capability receipts.

The normal production grant and mission limits still admit every job/request.
An additional owner-signed qualification grant permits measuring unqualified
roles on exactly the frozen orders/configurations, without claiming competence.
"""

from __future__ import annotations

import json
import time

from ..common import state_dir
from .durable import Refused, digest, strict_json


def resolve(ref):
    from .diagnosis_packet import scoped_path

    sha = ref.get("sha256") if isinstance(ref, dict) else None
    if ref != {"path": f"afo/product-role-trials/{sha}.json", "sha256": sha}:
        raise Refused("PRODUCT_ROLE_TRIAL_REFERENCE_INVALID")
    document = strict_json(scoped_path(state_dir(), ref["path"]).read_bytes(), 4 * 1024 * 1024)
    if digest(document) != sha or document.get("schema") != "forge-c/product-role-trial/1":
        raise Refused("PRODUCT_ROLE_TRIAL_CHANGED")
    return document


def authorized(ref, job, eff):
    from ..lrtx.role_capability import key
    from . import authz
    from .local_agent import request_for
    from .queue import Store

    trial = resolve(ref)
    order = Store().order(job["order_id"])
    if (
        not order
        or trial.get("qualification_only") is not True
        or job["order_id"] not in trial.get("order_ids", [])
        or trial.get("source_revision") != (job.get("factory_revision") or {}).get("commit")
        or trial.get("profile") != job.get("profile")
        or trial.get("model") != job.get("model")
        or type(trial.get("deadline_epoch")) not in (int, float)
        or not time.time() < trial["deadline_epoch"]
    ):
        raise Refused("PRODUCT_ROLE_TRIAL_BINDING_CHANGED")
    roles = trial.get("roles")
    allowed = {f"swe{i}-{r}" for i in range(1, 7) for r in ("author", "inspector")}
    # The existing six-phase workflow ends with a read-only inventory role.
    # It still needs its own signed experimental configuration or measured receipt.
    allowed |= {"release-manager", "afo-recovery-planner", "afo-factory-maintainer"}
    if not isinstance(roles, dict) or not roles or not set(roles) <= allowed:
        raise Refused("PRODUCT_ROLE_TRIAL_ROLES_INVALID")
    context_ceiling = 65536
    if any(isinstance(values, list) and any(isinstance(i, dict) and type(i.get("context_tokens")) is int
            and i["context_tokens"] > context_ceiling for i in values) for values in roles.values()):
        from pathlib import Path

        from ..common import sha256_file
        from ..lrtx.profile import load as load_profile

        prof = load_profile(job["profile"])
        configured = prof.get("runtime", {})
        context_ceiling = min(int(configured["ollama"]["OLLAMA_CONTEXT_LENGTH"]),
                              configured.get("fabro_context_tokens", 65536),
                              configured.get("context_limit_tokens", 65536))
        allocation_ref = trial.get("context_allocation_ref") or {}
        path = Path(allocation_ref.get("path", ""))
        if (trial.get("profile_sha256") != prof["_sha256"] or not path.is_file() or path.is_symlink()
                or sha256_file(path) != allocation_ref.get("sha256")):
            raise Refused("PRODUCT_ROLE_TRIAL_CONTEXT_ALLOCATION_UNBOUND")
        allocation = json.loads(path.read_text())
        if (allocation.get("status") != "PASS_ALLOCATION_ONLY"
                or allocation.get("provider_context_tokens", 0) < context_ceiling
                or allocation.get("model_digest") != job.get("model_digest")
                or allocation.get("precision") != job.get("precision")
                or allocation.get("provider_slot_count") != 1 or allocation.get("kv_precision") != "f16"):
            raise Refused("PRODUCT_ROLE_TRIAL_CONTEXT_NOT_ALLOCATED")
    for role, identities in roles.items():
        if not isinstance(identities, list) or not 1 <= len(identities) <= 32:
            raise Refused("PRODUCT_ROLE_TRIAL_CONFIGURATIONS_UNBOUNDED")
        for identity in identities:
            key(identity)
            if (
                identity["role"] != role
                or identity["adapter_revision"] != trial["source_revision"]
                or identity["model_digest"] != job.get("model_digest")
                or identity["precision"] != job.get("precision")
                or identity["context_tokens"] > context_ceiling
            ):
                raise Refused("PRODUCT_ROLE_TRIAL_CONFIGURATION_CHANGED")
    authref = trial.get("authorization_ref")
    grant = authz.find(eff.mode, eff.sha256 or "", ref=authref, action="recover_workorder", request=request_for(order))
    if not grant.allow:
        raise Refused(grant.code)
    record = json.loads((authz.AUTH_DIR / f"{authref}.json").read_text())
    if record.get("signed_runbook_ref") != "qualification-product-014:" + ref["sha256"]:
        raise Refused("PRODUCT_ROLE_TRIAL_NOT_OWNER_SIGNED")
    return trial


def bind(ref, job, eff):
    if ref:
        trial = authorized(ref, job, eff)
        if job.get("role") == "afo-recovery-planner":
            classes = {i["task_class"] for i in trial["roles"].get(job["role"], [])}
            if len(classes) != 1:
                raise Refused("PRODUCT_ROLE_TRIAL_TASK_CLASS_AMBIGUOUS")
            # A signed adapter choice, not a measured capability or extra budget.
            job["product_role_task_class"] = next(iter(classes))
        job["product_role_trial"] = ref
    return job


def identity(job, role, body, eff):
    trial = authorized(job["product_role_trial"], job, eff)
    if not isinstance(body, dict):
        raise Refused("PRODUCT_ROLE_TRIAL_REQUEST_REQUIRED")
    mode = (body.get("response_format") or {}).get("type") or ("tool" if body.get("tools") else "unconstrained")
    candidates = [
        i
        for i in trial["roles"].get(role, [])
        if i["schema_mode"] == mode
        and i["reasoning"] == body.get("reasoning_effort", "none")
        and all(body.get(k) == v for k, v in i["sampling"].items())
    ]
    if len(candidates) != 1:
        raise Refused("PRODUCT_ROLE_TRIAL_CONFIGURATION_UNDECLARED")
    selected = job.get("product_role_task_class")
    if role == "afo-recovery-planner" and selected is not None and selected != candidates[0]["task_class"]:
        raise Refused("PRODUCT_ROLE_TRIAL_TASK_CLASS_CHANGED")
    return candidates[0]


def preflight(workspace, job, requests):
    """Measure supplied complete role requests using normal admission, without reserving or sending.

    This is executable preparation, not runtime qualification or launch authority.
    Future requests still pass the gateway's live authorization/accounting checks.
    No prompt text or hidden reasoning is returned in the public report.
    """
    from pathlib import Path

    from .. import provided_requirements
    from ..common import sha256_file
    from ..llm_gateway import sanitize_request
    from ..lrtx import profile, role_capability
    from ..workflow.builder import build
    from ..workorder import factory_revision, local_profile_structured, section_map
    from .diagnosis_packet import measure_request

    ws = Path(workspace)
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    revision = factory_revision()
    if revision.get("dirty") or revision.get("commit") != (job.get("factory_revision") or {}).get("commit"):
        raise Refused("PRODUCT_PREFLIGHT_SOURCE_CHANGED_OR_DIRTY")
    prof = profile.load(job["profile"])
    model = prof["models"]["allowed"].get(job["model"])
    if not model or model["digest"] != job.get("model_digest") or model["quantization"] != job.get("precision"):
        raise Refused("PRODUCT_PREFLIGHT_MODEL_CHANGED")
    # Use the same source inventory as launch. Request-only legacy fixtures may
    # omit it; an actual ASPICE scope still refuses any unresolved section.
    sections = section_map(ws) if (ws / "inputs/index.md").is_file() else {}
    _, nodes = build(man["work_order"], goal="Role admission preflight", sections=sections,
                     layer=man.get("layer", "LL+HAL"), brownfield=man.get("code_mode"),
                     peripheral=man.get("peripheral"), operation_scope=man.get("operation_scope"),
                     delivery_style=((man.get("delivery") or {}).get("build") or {}).get("style"),
                     structured=local_profile_structured(prof, man, job["model"]), assessment_manifest=man,
                     execution_policy=man.get("development_execution"))
    roles = {n["role"] for n in nodes.values()}
    if any(not isinstance(r, dict) or set(r) != {"role", "body"} or r["role"] not in roles for r in requests):
        raise Refused("PRODUCT_PREFLIGHT_REQUEST_INVENTORY_INVALID")
    imported = None
    if man.get("provided_requirements"):
        provided_requirements.validate(ws)  # Review and source/scope bindings remain required.
        if provided_requirements.findings(ws):
            raise Refused("PRODUCT_PREFLIGHT_ASSISTED_INPUT_NOT_VALIDATED")
        receipt = ws / ".forge-run/provided-requirements-receipt.json"
        imported = sha256_file(receipt)
    rows = []
    for role in sorted(roles):
        supplied = [r["body"] for r in requests if r["role"] == role]
        if role == "swe1-author" and imported:
            if supplied:
                raise Refused("PRODUCT_PREFLIGHT_IMPORTED_AUTHOR_MUST_NOT_INFER")
            rows.append({"role": role, "status": "NO_INFERENCE_IMPORTED_REQUIREMENTS", "receipt_sha256": imported})
            continue
        if not supplied:
            rows.append({"role": role, "status": "NOT_RUN", "reason": "COMPLETE_SERIALIZED_REQUEST_MISSING"})
        for body in supplied:
            row = {"role": role, "supplied_request_sha256": digest(body)}
            try:
                if not isinstance(body, dict) or body.get("model") != job["model"]:
                    raise Refused("PRODUCT_PREFLIGHT_REQUEST_MODEL_CHANGED")
                effective = sanitize_request(body, policy=prof.get("gateway", {}).get("reasoning", {}), role=role)
                measured = measure_request(effective)
                caps = [effective[k] for k in ("max_tokens", "max_completion_tokens") if effective.get(k) is not None]
                if len(caps) != 1 or type(caps[0]) is not int or caps[0] < 1:
                    raise Refused("PROVIDER_OUTPUT_CAP_MISSING_OR_AMBIGUOUS")
                row.update(measurement=measured, effective_output_cap=caps[0],
                           effective_reasoning=effective.get("reasoning_effort"),
                           conservative_reservation=measured["input_tokens"] + caps[0])
                admission = role_capability.admit_job(job, role, input_tokens=measured["input_tokens"],
                                                     output_tokens=caps[0], body=effective)
                row.update(status="PASS_STATIC_ADMISSION", qualification_only=admission.get("qualification_only", False))
            except Refused as exc:
                row.update(status="REFUSED", reason=exc.code)
            rows.append(row)
    return {"schema": "forge-c/product-request-preflight/1", "source_revision": revision["commit"],
            "profile": prof["id"], "profile_sha256": prof["_sha256"], "model_digest": model["digest"],
            "work_order": man["work_order"], "required_roles": sorted(roles), "rows": rows,
            "status": "PASS_STATIC_ADMISSION" if all(r["status"] in
                      ("PASS_STATIC_ADMISSION", "NO_INFERENCE_IMPORTED_REQUIREMENTS") for r in rows) else "NOT_RUN",
            "runtime_qualification": "NOT_RUN", "generation_performed": False,
            "reservation_performed": False, "launch_authority": False,
            "live_authority": "NOT_CHECKED_BY_STATIC_PREFLIGHT"}


def main(argv=None):
    import argparse
    from pathlib import Path

    from .durable import immutable_json

    ap = argparse.ArgumentParser(description="Read-only complete product-role request admission preflight")
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--job", type=Path, required=True)
    ap.add_argument("--requests", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        result = preflight(args.workspace, strict_json(args.job.read_bytes(), 4 * 1024 * 1024),
                           strict_json(args.requests.read_bytes(), 4 * 1024 * 1024))
    except (Refused, ValueError) as exc:
        result = {"schema": "forge-c/product-request-preflight/1", "status": "NOT_RUN",
                  "blockers": [str(exc).split(":", 1)[0]], "runtime_qualification": "NOT_RUN",
                  "generation_performed": False, "reservation_performed": False, "launch_authority": False}
    immutable_json(args.out, result)
    print(json.dumps({"status": result["status"], "runtime_qualification": "NOT_RUN", "out": str(args.out)}))
    return 0 if result["status"] == "PASS_STATIC_ADMISSION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
