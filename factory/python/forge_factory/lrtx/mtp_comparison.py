"""Freeze an MTP speed pilot using existing qualification inputs and accounting.

This preparer never executes models, creates authority or changes services. MTP
is a runtime factor, not a new role-capability identity or a qualified model.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import time
from pathlib import Path

from ..afo import qualification as Q
from ..afo import qualification_inputs as inputs
from ..afo.durable import Refused, digest, immutable_json
from ..common import REPO_ROOT, sha256_file
from . import profile
from .reasoning_comparison import BASE, MODEL, validate_template_preflight
from .structured import skill

# A fresh baseline is required at the same revision as every candidate.
DRAFTS = (3, 2, 4, 6)


def selected_profile(draft):
    if type(draft) is not int or draft not in DRAFTS:
        raise Refused("MTP_COMPARISON_DRAFT_INVALID")
    return BASE if draft == 3 else BASE + f"-draft{draft}-trial"


def comparable_profiles():
    found = {n: profile.load(selected_profile(n)) for n in DRAFTS}
    normalized = {}
    for n, original in found.items():
        p = copy.deepcopy(original)
        if (p["models"]["default"] != MODEL
                or p["models"]["allowed"][MODEL]["quantization"] != "Q8_0"
                or p["runtime"]["llama_server"]["mtp_draft"] != n
                or p["runtime"]["llama_server"]["reasoning_effort"] != "xhigh"
                or p["gateway"]["reasoning"][MODEL]["effort"] != "xhigh"
                or p["runtime"]["llama_server"]["slots"] != 1
                or p["runtime"]["ollama"]["OLLAMA_KV_CACHE_TYPE"] != "f16"
                or int(p["runtime"]["ollama"]["OLLAMA_CONTEXT_LENGTH"]) != 262144):
            raise Refused("MTP_COMPARISON_EFFECTIVE_CONTROLS_CHANGED", str(n))
        for key in ("id", "description", "status", "_path", "_sha256"):
            p.pop(key, None)
        p["runtime"]["llama_server"]["mtp_draft"] = "CONTROLLED_FACTOR"
        normalized[n] = p
    if any(p != normalized[3] for p in normalized.values()):
        raise Refused("MTP_COMPARISON_MULTIPLE_FACTORS_CHANGED")
    return found


def prepare(root, *, compiler, capabilities_ref, campaign_prefix):
    profiles = comparable_profiles()
    capabilities = validate_template_preflight(
        capabilities_ref, profiles[3]["models"]["allowed"][MODEL]["digest"]
    )
    # All resulting trial/mission identities are caller-selected and frozen;
    # existing identifiers are never refreshed to obtain a new allowance.
    if (not isinstance(campaign_prefix, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,47}", campaign_prefix)):
        raise Refused("MTP_COMPARISON_CAMPAIGN_ID_INVALID")
    root = Path(root).resolve()
    if root.exists():
        raise Refused("MTP_COMPARISON_ROOT_ALREADY_EXISTS")
    root.mkdir(parents=True, mode=0o700)
    before = {k: os.environ.get(k) for k in ("FORGE_STATE_DIR", "FORGE_EVENTS_DIR")}
    prepared = {}
    try:
        os.environ["FORGE_STATE_DIR"] = str(root / "preparation-state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "preparation-events")
        for n in DRAFTS:
            prepared[n] = inputs.prepare(
                root / f"draft{n}", compiler=compiler,
                campaign_id=f"{campaign_prefix}-d{n}",
                authorization_ref=f"AUTH-014-MTPSPEED-{campaign_prefix.upper()}-D{n}",
                model=MODEL, profile=selected_profile(n),
                qualification_job_tokens=262144, stage="targeted",
            )
    finally:
        for k, value in before.items():
            if value is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = value
    baseline = prepared[3]
    source = baseline["generator_revision"]
    cases = Q.frozen_trials(json.loads((REPO_ROOT / Q.CATALOGUES["targeted"]).read_text())["cases"])
    for p in prepared.values():
        if p["generator_revision"] != source or [t["trial_id"] for t in p["trials"]] != cases:
            raise Refused("MTP_COMPARISON_SOURCE_OR_DENOMINATOR_CHANGED")
        if any(t["request_measurement"]["effective_reasoning_effort"] != "xhigh"
               or t["output_reserve"] != 34816
               or t["request_measurement"]["input_tokens"] + t["output_reserve"] > 262144
               for t in p["trials"]):
            raise Refused("MTP_COMPARISON_REQUEST_CONFIGURATION_CHANGED")
    identity = {
        "role": "afo-recovery-planner",
        "model_digest": profiles[3]["models"]["allowed"][MODEL]["digest"],
        "precision": "Q8_0", "reasoning": "xhigh", "schema_mode": "json_schema",
        "adapter_revision": source["commit"], "context_tokens": 262144,
        "sampling": {"temperature": 0}, "task_class": "PROTOCOL_DIAGNOSIS",
    }
    plan = {
        "schema": "forge-c/mtp-speed-plan/1", "status": "PREREGISTERED_NOT_RUN",
        "registered_at": time.time(), "runtime_factor": "mtp_draft", "draft_order": list(DRAFTS),
        "source_revision": source, "case_ids": cases, "identity": identity,
        "capabilities_ref": capabilities_ref,
        "native_chat_template_sha256": capabilities["template_sha256"],
        "profiles": {str(n): {"id": selected_profile(n), "sha256": profiles[n]["_sha256"]}
                     for n in DRAFTS},
        "controls": {
            "role_instructions_sha256": skill("afo-recovery-planner")["sha256"],
            "request_builder_sha256": sha256_file(REPO_ROOT / "factory/python/forge_factory/afo/durable_agent.py"),
            "catalogue_sha256": baseline["template_sha256"],
            "seeded_source_sha256": digest(inputs.IMPLEMENTATION),
            "reference_source_sha256": digest(inputs.REFERENCE),
            "checker_sha256": digest(inputs.CHECKER),
            "compiler_sha256": sha256_file(Path(compiler).resolve()),
            "model": MODEL, "context_tokens": 262144, "kv_precision": "f16",
            "reasoning": "xhigh", "temperature": 0, "one_inference": True,
            "gateway_extra_output_tokens": 32768, "requested_answer_tokens": 2048,
            "independent_oracle": "COMPILED_260_INPUT_REFERENCE_PLUS_EXISTING_QUALIFICATION_AUDIT",
            "administrative_bindings": "distinct, preserved per trial; no hash normalization",
        },
        "measurement": {
            "native_decode": "correlated native eval tokens/seconds, includes reasoning tokens",
            "end_to_end": "separate gateway/job/admission/load/failure/unknown-usage costs",
            "thermal_order": "serial baseline3 then2,4,6; temperature/power recorded; not randomized",
            "effective_settings": "kernel-observed provider argv and gateway effort before each cohort",
            "failure_policy": "retain every trial; no model retry, mission reset or reduced denominator",
            "no_raw_prompts_or_hidden_reasoning": True,
        },
        "capability_identity_changed": False,
        "formal_configuration_comparison": "NOT_QUALIFIED_RUNTIME_FACTOR_NOT_IN_ROLE_IDENTITY",
        "author_inspector_product_qualification": "NOT_RUN",
        "automatic_selection": False, "automatic_deployment": False,
    }
    immutable_json(root / "mtp-plan.json", plan)
    manifests = {}
    for n, p in prepared.items():
        manifests[n] = Q.freeze(
            "targeted", root / f"draft{n}" / "campaign-unsigned.json",
            identity=identity, inputs=[str(root / f"draft{n}" / "inputs.json"), str(root / "mtp-plan.json")],
            jobs=p["jobs"], model_profile=MODEL,
            job_token_reservations=p["requested_initial_reservations"],
        )
    report = {
        "schema": "forge-c/mtp-speed-preparation/1", "status": "PREPARED_NOT_RUN",
        "source_revision": source, "draft_order": list(DRAFTS), "case_count_per_draft": len(cases),
        "case_ids": cases, "plan_sha256": digest(plan),
        "manifest_sha256": {str(n): digest(m) for n, m in manifests.items()},
        "model_requests": 0, "signed_grants_created": 0, "mission_or_job_created": False,
        "execution_host": "omniverse2", "service_changes": False,
        "start_requires": ["NATIVE_EXACT_SOURCE_QUALIFICATION", "QUIESCENT_NATIVE_AND_REQUESTS",
                           "EXACT_FINITE_SIGNED_MANIFEST_MISSION_POLICY",
                           "KERNEL_OBSERVED_CONFIGURATION", "ONE_ADMITTED_INFERENCE"],
        "role_product_learning_availability": "NOT_QUALIFIED_BY_THIS_PREPARATION",
    }
    immutable_json(root / "preparation.json", report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--compiler", required=True, type=Path)
    p.add_argument("--capabilities", required=True, type=Path)
    p.add_argument("--campaign-prefix", required=True)
    a = p.parse_args(argv)
    print(json.dumps(prepare(
        a.out, compiler=a.compiler,
        capabilities_ref={"path": str(a.capabilities.resolve()), "sha256": sha256_file(a.capabilities)},
        campaign_prefix=a.campaign_prefix,
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

