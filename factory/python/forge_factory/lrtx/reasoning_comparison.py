"""Prepare a controlled reasoning-speed pilot through existing Feature 014 qualification.

No inference, grants, missions, queue entries or service changes. The initial
pilot measures recovery diagnosis only; authors, inspectors and complete mixed
reasoning pipelines still need their own runs. Native execution uses the existing
qualification intake, Conductor, gateway ledger and independent audit producer.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import time
from pathlib import Path

from ..afo import configuration_comparison as comparison
from ..afo import qualification as qualification
from ..afo import qualification_inputs as inputs
from ..afo.durable import Refused, digest, immutable_json
from ..common import REPO_ROOT, sha256_file
from . import profile
from .structured import skill

BASE = "local-rtx-v2-omniverse2-q38-qm-demo-repair-mtp"
EFFORTS = ("xhigh", "medium")
MODEL = "qwen3.8:27b-q8_0"


def selected_profile(effort):
    if effort not in EFFORTS:
        raise Refused("REASONING_COMPARISON_EFFORT_INVALID")
    return BASE if effort == "xhigh" else BASE + "-" + effort + "-trial"


def comparable_profiles():
    """Only the two actual effort controls and non-execution metadata may differ."""
    found = {effort: profile.load(selected_profile(effort)) for effort in EFFORTS}
    normalized = {}
    for effort, original in found.items():
        p = copy.deepcopy(original)
        if (p["models"]["default"] != MODEL or p["runtime"]["llama_server"]["mtp_draft"] != 3
                or p["runtime"]["ollama"]["OLLAMA_KV_CACHE_TYPE"] != "f16"
                or int(p["runtime"]["ollama"]["OLLAMA_CONTEXT_LENGTH"]) != 262144
                or p["runtime"]["llama_server"]["slots"] != 1
                or p["runtime"]["llama_server"]["reasoning_effort"] != effort
                or p["gateway"]["reasoning"][MODEL]["effort"] != effort):
            raise Refused("REASONING_COMPARISON_EFFECTIVE_CONTROLS_CHANGED", effort)
        for key in ("id", "status", "description", "_path", "_sha256"):
            p.pop(key, None)
        p["runtime"]["llama_server"]["reasoning_effort"] = "CONTROLLED_FACTOR"
        p["gateway"]["reasoning"][MODEL]["effort"] = "CONTROLLED_FACTOR"
        normalized[effort] = p
    if any(p != normalized["xhigh"] for p in normalized.values()):
        raise Refused("REASONING_COMPARISON_MULTIPLE_FACTORS_CHANGED")
    return found


def _put(path, value):
    immutable_json(path, value)
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def prepare(root, *, compiler, capabilities_ref):
    """Freeze actual cases/measurements and preregistration; native results remain NOT_RUN."""
    profiles = comparable_profiles()
    ref = capabilities_ref
    cp = Path(ref["path"])
    if cp.is_symlink() or sha256_file(cp) != ref["sha256"]:
        raise Refused("REASONING_TEMPLATE_PREFLIGHT_CHANGED")
    capabilities = json.loads(cp.read_text())
    observations = {r["effort"]: r for r in capabilities.get("rows", [])}
    if (capabilities.get("test_kind") != "NATIVE_TEMPLATE_RENDER_ONLY_NO_INFERENCE"
            or capabilities.get("native_model_alias") != MODEL
            or capabilities.get("model_digest") != profiles["xhigh"]["models"]["allowed"][MODEL]["digest"]
            or capabilities.get("model_requests") != 0
            or capabilities.get("request_ledger_before") != capabilities.get("request_ledger_after")
            or observations.get("xhigh", {}).get("http_status") != 200
            or observations.get("medium", {}).get("http_status") != 200
            or observations.get("xhigh", {}).get("xhigh_instruction_present") is not True
            or observations.get("medium", {}).get("xhigh_instruction_present") is not False
            or observations.get("high", {}).get("http_status") != 500
            or observations.get("high", {}).get("unsupported_effort_error") is not True):
        raise Refused("REASONING_TEMPLATE_PREFLIGHT_INCOMPATIBLE")
    root = Path(root).resolve()
    if root.exists():
        raise Refused("REASONING_COMPARISON_ROOT_ALREADY_EXISTS")
    root.mkdir(parents=True, mode=0o700)
    before = {k: os.environ.get(k) for k in ("FORGE_STATE_DIR", "FORGE_EVENTS_DIR")}
    prepared = {}
    try:
        os.environ["FORGE_STATE_DIR"] = str(root / "preparation-state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "preparation-events")
        for effort in EFFORTS:
            prepared[effort] = inputs.prepare(
                root / effort, compiler=compiler, campaign_id="q38-reasoning-" + effort,
                authorization_ref="AUTH-014-REASONING-" + effort.upper() + "-DRAFT",
                model=MODEL, profile=selected_profile(effort),
                qualification_job_tokens=262144, stage="targeted",
            )
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    baseline = prepared["xhigh"]
    revision = baseline["generator_revision"]["commit"]
    if any(p["generator_revision"] != baseline["generator_revision"] for p in prepared.values()):
        raise Refused("REASONING_COMPARISON_SOURCE_CHANGED")
    cases = qualification.frozen_trials(json.loads(
        (REPO_ROOT / qualification.CATALOGUES["targeted"]).read_text())["cases"])
    for effort, p in prepared.items():
        if [t["trial_id"] for t in p["trials"]] != cases:
            raise Refused("REASONING_COMPARISON_DENOMINATOR_CHANGED")
        if any(t["request_measurement"]["effective_reasoning_effort"] != effort
               or t["output_reserve"] != 34816
               or t["request_measurement"]["input_tokens"] + t["output_reserve"] > 262144 for t in p["trials"]):
            raise Refused("REASONING_COMPARISON_REQUEST_IDENTITY_CHANGED", effort)
    # Controls freeze shared task/role instructions and primary sources. Distinct
    # qualification orders retain distinct administrative bindings, as in normal intake.
    controls = {
        "prompts": {"request_builder_sha256": sha256_file(REPO_ROOT / "factory/python/forge_factory/afo/durable_agent.py"),
                    "skill_sha256": skill("afo-recovery-planner")["sha256"],
                    "case_catalogue_sha256": baseline["template_sha256"],
                    "native_template_preflight_ref": capabilities_ref,
                    "native_chat_template_sha256": capabilities["template_sha256"],
                    "administrative_order_and_artifact_bindings": "distinct per trial; never normalized out of admission"},
        "oracles": {"checker_sha256": digest(inputs.CHECKER), "contract_sha256": digest(inputs.CONTRACT),
                    "seeded_source_sha256": digest(inputs.IMPLEMENTATION),
                    "reference_source_sha256": digest(inputs.REFERENCE),
                    "compiler_sha256": sha256_file(Path(compiler).resolve())},
        "workload": {"case_ids": cases, "role": "afo-recovery-planner", "repeats": 2,
                     "scope": "SEEDED_PROTOCOL_DIAGNOSIS_PILOT_NOT_AUTHOR_INSPECTOR_OR_PRODUCT_QUALIFICATION"},
        "admission": {"inference_requests": 1, "verification_workers": 1, "context_tokens": 262144,
                      "model_digest": profiles["xhigh"]["models"]["allowed"][MODEL]["digest"],
                      "precision": "Q8_0", "kv_precision": "f16", "mtp_draft": 3,
                      "gateway_extra_output_tokens": 32768, "requested_answer_tokens": 2048,
                      "sampling": {"temperature": 0}},
        "measurement": {"count_all_attempts": True, "include_learning_overhead": True,
                        "wall_time": "gateway latency plus job/retry/load time separately",
                        "decode_rate": "native backend output tokens / native eval seconds; UNKNOWN if uncorrelated",
                        "reasoning_tokens": "included in reported completion tokens; content not collected",
                        "thermal_order": "serial, baseline xhigh first; same case order; temperature/power recorded",
                        "effective_effort": "verify gateway-transformed request and actual native settings",
                        "artifact_policy": "designated proposals only; no raw prompts or hidden reasoning in public results"},
        "quality_gates": {"expected_outcomes": "existing targeted catalogue",
                          "oracle": "real compiled 260-input reference fixture plus unchanged semantic broker",
                          "same_model_agreement_is_independent_evidence": False,
                          "missing_native_oracle": "UNKNOWN", "automatic_selection": False},
    }
    refs = {name: _put(root / "controls" / (name + ".json"), data) for name, data in controls.items()}
    identities = {
        effort: {"role": "afo-recovery-planner", "model_digest": profiles[effort]["models"]["allowed"][MODEL]["digest"],
                 "precision": "Q8_0", "reasoning": effort, "schema_mode": "json_schema",
                 "adapter_revision": revision, "context_tokens": 262144,
                 "sampling": {"temperature": 0}, "task_class": "PROTOCOL_DIAGNOSIS"}
        for effort in EFFORTS
    }
    plans = {}
    for effort in ("medium",):
        plan = {"schema": "forge-c/configuration-comparison-plan/1", "comparison_factor": "reasoning",
                "baseline_identity": identities["xhigh"], "candidate_identity": identities[effort],
                "case_ids": cases, "controls": refs, "registered_at": time.time()}
        plans[effort] = _put(root / (effort + "-comparison-plan.json"), plan)
        comparison.validate_plan(plan)
        _put(root / (effort + "-comparison-NOT-RUN.json"), comparison.report(plan))
    manifests = {}
    for effort, p in prepared.items():
        manifests[effort] = qualification.freeze(
            "targeted", root / effort / "campaign-unsigned.json", identity=identities[effort],
            inputs=[str(Path(p["root"]) / "inputs.json"), *[r["path"] for r in refs.values()],
                    *[r["path"] for r in plans.values()]],
            jobs=p["jobs"], model_profile=MODEL,
            job_token_reservations=p["requested_initial_reservations"],
        )
    report = {"schema": "forge-c/reasoning-comparison-preparation/1", "status": "PREPARED_NOT_RUN",
              "source_revision": revision, "source_dirty": baseline["generator_revision"]["dirty"],
              "requested_efforts": ["xhigh", "high", "medium"], "efforts": list(EFFORTS),
              "unsupported": {"high": {"status": "UNSUPPORTED_MODEL_TEMPLATE", "native_preflight_ref": capabilities_ref,
                                        "model_requests": 0, "speed": None, "silently_mapped": False}},
              "case_count_per_effort": len(cases), "case_ids": cases,
              "native_host": "omniverse2", "start_requires_current_ll_native_quiescent_and_resources_released": True,
              "inputs": {e: {"path": str(root / e / "inputs.json"),
                             "sha256": sha256_file(root / e / "inputs.json")} for e in EFFORTS},
              "manifest_sha256": {e: digest(m) for e, m in manifests.items()},
              "signed_grants_created": 0, "mission_or_job_created": False, "model_requests": 0,
              "product_pipeline_comparison": "NOT_RUN; separate author-medium/inspector-xhigh evaluation; high unsupported by pinned template",
              "mtp_comparison": "NEXT_SEPARATE_FACTOR; no simultaneous reasoning/MTP change",
              "native_blockers": ["CURRENT_LL_QUIESCENCE_NOT_OBSERVED_BY_THIS_PREPARER", "NATIVE_CLEAN_REVISION_PREPARATION_REQUIRED",
                                  "EXACT_FINITE_CAMPAIGN_SIGNING_AND_PROVISIONING_REQUIRED",
                                  "INDEPENDENT_NATIVE_AUDIT_AND_OBSERVED_SETTINGS_NOT_RUN"]}
    _put(root / "preparation.json", report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--compiler", required=True, type=Path)
    p.add_argument("--capabilities", required=True, type=Path, help="actual native zero-inference template preflight JSON")
    args = p.parse_args(argv)
    result = prepare(args.out, compiler=args.compiler, capabilities_ref={"path": str(args.capabilities.resolve()), "sha256": sha256_file(args.capabilities)})
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

