"""Freeze concrete protocol inputs before owner signing or any native admission.

The register fixture is an explicitly seeded qualification case, not an incident
from a product run. An independent compiled reference supplies its counterexample.
This preparation command creates no grants, missions, orders, jobs or inference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from ..common import REPO_ROOT, sha256_file, utc_now
from . import diagnosis_packet as packets
from .durable import Refused, digest, immutable_json
from .queue import order_id_for

PROFILE = "local-rtx-v2-omniverse2"
MODEL = "qwen3.6:35b-a3b"
CONTRACT = """# Seeded REG32 qualification fixture (not an STM32 product)
SWR-001 / USPEC-001: reg_enable(before) shall return the 32-bit register value
with EN (bit 0, mask UINT32_C(1)) set and every other bit unchanged.
The operation shall be idempotent. Inputs include zero and full-width boundaries.
This is a frozen protocol test, not a production failure or a promoted remedy.
"""
IMPLEMENTATION = "#include <stdint.h>\nuint32_t reg_enable(uint32_t before) { return before | UINT32_C(2); }\n"
REFERENCE = "#include <stdint.h>\nuint32_t reg_enable(uint32_t before) { return before | UINT32_C(1); }\n"
CHECKER = r"""#include <stdint.h>
#include <stdio.h>
uint32_t reg_enable(uint32_t before);
int main(void) {
    const uint32_t edge[] = {UINT32_C(0x80000000), UINT32_C(0xffffffff), UINT32_C(0xfffffffe), UINT32_C(0x7fffffff)};
    unsigned int failures = 0, checked = 0;
    uint32_t first_in = 0, first_out = 0, first_expected = 0;
    for (unsigned int i = 0; i < 260; ++i) {
        uint32_t input = i < 256 ? (uint32_t)i : edge[i - 256];
        uint32_t output = reg_enable(input), expected = input | UINT32_C(1);
        ++checked;
        if (output != expected || reg_enable(output) != output) {
            if (failures == 0) { first_in = input; first_out = output; first_expected = expected; }
            ++failures;
        }
    }
    printf("{\"checked\":%u,\"failures\":%u,\"input\":%u,\"observed\":%u,\"expected\":%u}\n",
           checked, failures, (unsigned int)first_in, (unsigned int)first_out, (unsigned int)first_expected);
    return failures == 0 ? 0 : 1;
}
"""

# These are prospective, declared interventions. Only a separately authorized
# native fault executor may apply one; preparation never mutates a sealed source.
FAULT_RECIPES = {
    "stale-primary": {"boundary": "before-evidence-read", "recipe": "change-primary-after-seal"},
    "cross-case-reference": {"boundary": "after-provider-response", "recipe": "foreign-evidence-reference"},
    "symlink-escape": {"boundary": "before-evidence-read", "recipe": "replace-primary-with-external-symlink"},
    "administrative-forgery": {"boundary": "after-provider-response", "recipe": "add-forbidden-order-id"},
    "reworded-strategy": {"boundary": "after-provider-response", "recipe": "replay-tried-signature-with-new-wording"},
    "empty-output": {"boundary": "after-provider-response", "recipe": "drop-content"},
    "malformed-output": {"boundary": "after-provider-response", "recipe": "truncate-json"},
    "revoked-before-dispatch": {"boundary": "before-native-dispatch", "recipe": "revoke-execution-authority"},
    "expired-mission": {"boundary": "before-native-dispatch", "recipe": "already-expired-mission"},
    "lost-launch-ack": {"boundary": "after-native-acceptance", "recipe": "drop-launch-acknowledgement"},
    "cancel-ack-still-live": {"boundary": "during-native-execution", "recipe": "cancel-ack-with-live-request"},
    "unqualified-local-alternative": {"boundary": "after-provider-response", "recipe": "select-unqualified-model"},
}


def reference(root: Path, compiler: Path) -> dict:
    """Run only this module's fixed C fixture, never model/candidate-supplied code."""
    compiler = compiler.resolve()
    if not compiler.is_file() or not os.access(compiler, os.X_OK):
        raise Refused("QUALIFICATION_REFERENCE_COMPILER_UNAVAILABLE")
    root.mkdir(parents=True)
    (root / "checker.c").write_text(CHECKER)
    env = {"PATH": str(compiler.parent) + ":/usr/bin:/bin", "TMPDIR": str(root), "HOME": str(root), "LANG": "C.UTF-8"}
    rows = {}
    for label, source in (("seeded", IMPLEMENTATION), ("reference", REFERENCE)):
        path = root / (label + ".c")
        path.write_text(source)
        binary = root / label
        command = [
            str(compiler),
            "-std=c11",
            "-O0",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(path),
            str(root / "checker.c"),
            "-o",
            str(binary),
        ]
        compiled = subprocess.run(command, env=env, capture_output=True, timeout=30)
        if compiled.returncode:
            raise Refused("QUALIFICATION_REFERENCE_COMPILE_FAILED", label)
        result = subprocess.run([str(binary)], env=env, capture_output=True, timeout=5)
        fact = json.loads(result.stdout)
        if fact["checked"] != 260 or result.returncode != (1 if label == "seeded" else 0):
            raise Refused("QUALIFICATION_REFERENCE_RESULT_UNEXPECTED", label)
        rows[label] = {
            **fact,
            "exit_code": result.returncode,
            "source_sha256": sha256_file(path),
            "binary_sha256": sha256_file(binary),
            "command": command,
        }
    if rows["seeded"]["failures"] == 0 or rows["reference"]["failures"] != 0:
        raise Refused("QUALIFICATION_COUNTEREXAMPLE_NOT_ESTABLISHED")
    report = {
        "schema": "forge-c/protocol-reference-fixture/1",
        "producer": "REFERENCE_HARNESS",
        "compiler": str(compiler),
        "compiler_sha256": sha256_file(compiler),
        "checker_sha256": sha256_file(root / "checker.c"),
        "rows": rows,
        "scope": "256_LOW_BYTE_INPUTS_AND_FOUR_32_BIT_BOUNDARIES_PLUS_IDEMPOTENCE_NOT_PRODUCT_ACCEPTANCE",
    }
    immutable_json(root / "report.json", report)
    return report


def prepare(root, *, compiler, campaign_id, authorization_ref, model=MODEL, profile=PROFILE, qualification_job_tokens=None,
            stage="protocol"):
    """Materialize every exact source case of the stage's frozen catalogue (protocol: 100; targeted: its own size);
    administrative admission remains separate."""
    from ..lrtx.profile import load as load_profile
    from ..registry.agents import load_agents
    from .durable_agent import request_material
    from .semantic_proposal import signature

    root = Path(root).resolve()
    if root.exists():
        raise Refused("QUALIFICATION_INPUT_ROOT_ALREADY_EXISTS")
    if (
        not campaign_id
        or len(campaign_id) > 64
        or not authorization_ref
        or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for c in campaign_id)
    ):
        raise Refused("QUALIFICATION_INPUT_ID_INVALID")
    if compiler is None:
        raise Refused("QUALIFICATION_REFERENCE_COMPILER_UNAVAILABLE")
    selected = load_profile(profile)
    if model not in selected["models"]["allowed"]:
        raise Refused("QUALIFICATION_MODEL_NOT_IN_PINNED_PROFILE")
    configured_context = int(selected["runtime"]["ollama"]["OLLAMA_CONTEXT_LENGTH"])
    if qualification_job_tokens is not None and (
        type(qualification_job_tokens) is not int or not 0 < qualification_job_tokens <= configured_context
    ):
        raise Refused("QUALIFICATION_INITIAL_RESERVATIONS_INVALID")
    root.mkdir(parents=True, mode=0o700)
    report = reference(root / "reference", Path(compiler))
    revision = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True).strip()),
    }
    from .qualification import CATALOGUES

    if stage not in CATALOGUES:
        raise Refused("QUALIFICATION_INPUT_STAGE_INVALID")
    template_path = REPO_ROOT / CATALOGUES[stage]
    catalogue = json.loads(template_path.read_text())["cases"]
    registry_default = next(a.max_stage_tokens for a in load_agents(include_afo=True)[0] if a.id == "afo-recovery-planner")
    reserved = registry_default if qualification_job_tokens is None else qualification_job_tokens
    mission = "qualification-014-" + campaign_id
    tenant = mission
    jobs, trials = {}, []
    counterexample = report["rows"]["seeded"]
    for scenario in catalogue:
        name = scenario["case_id"]
        for repeat in range(scenario["repeats"]):
            trial = f"{name}:{repeat}"
            directory = root / "cases" / trial.replace(":", "-")
            ws = directory / "workspace"
            for phase in ("SWE.1", "SWE.2", "SWE.3"):
                (ws / "workproducts" / phase).mkdir(parents=True, exist_ok=True)
            (ws / "software/hal").mkdir(parents=True)
            (ws / ".forge-run").mkdir()
            contract = CONTRACT + (
                "\nEN reste activé; les autres bits restent inchangés — exigence vérifiée.\n"
                if name == "unicode-contract"
                else ""
            )
            (ws / "workproducts/SWE.1/software_requirements.md").write_text(contract)
            (ws / "workproducts/SWE.2/software_architecture.md").write_text(
                "SWU-REG32 implements SWR-001 using EN mask " + ("2" if name == "upstream-owner" else "1") + ".\n"
            )
            (ws / "workproducts/SWE.3/unit_specifications.md").write_text(contract)
            (ws / "software/hal/reg32.c").write_text(IMPLEMENTATION)
            immutable_json(
                ws / ".forge-run/manifest.json",
                {
                    "work_order": "QUAL014-" + trial.replace(":", "-"),
                    "local_profile": {"id": profile},
                    "evaluation_holdout": True,
                    "fixture_kind": "SEEDED_PROTOCOL_NOT_PRODUCT",
                    "factory_revision": revision,
                },
            )
            immutable_json(ws / ".forge-run/model-profile.json", {"default": model})
            request = "QUAL014-" + campaign_id + "-" + trial.replace(":", "-")
            oid = order_id_for(tenant, request)
            aid = oid + "-a1"
            bundle = {
                "schema_version": "1.0",
                "bundle_id": "qualification-fb-" + digest([campaign_id, trial])[:20],
                "order_id": oid,
                "attempt_id": aid,
                "phase": "SWE.3",
                "failure_class": "PRODUCT_QUALITY",
                "fingerprint": "qualification-reg32-" + digest([IMPLEMENTATION, CONTRACT])[:20],
                "gate_result": "BLOCKED",
                "error_code": "SEEDED_REG32_COUNTEREXAMPLE",
                "artifact_refs": [],
                "evidence_refs": ["reference-harness:" + digest(report)],
                "input_digests": {},
                "requirements_refs": ["SWR-001", "USPEC-001"],
                "redacted_summary": (
                    "Explicit qualification fixture: compiled seeded implementation fails the frozen REG32 contract; "
                    "not an historical product incident."
                ),
                "context_truncated": False,
                "untrusted_source_refs": [],
            }
            findings = [
                {
                    "id": "counterexample",
                    "obligation_id": "USPEC-001",
                    "detail": (
                        f"For input {counterexample['input']}, compiled reg_enable returned {counterexample['observed']}; "
                        f"SWR-001 requires {counterexample['expected']}."
                    ),
                }
            ]
            if name == "late-finding":
                findings = [
                    {
                        "id": f"context-{i}",
                        "obligation_id": "USPEC-001",
                        "detail": (
                            "Fixture inventory context; this observation does not resolve "
                            "the decisive register-effect counterexample."
                        ),
                    }
                    for i in range(8)
                ] + findings
            if name == "upstream-owner":
                findings[0]["detail"] += (
                    " Implementation follows SWE.2 mask 2, which contradicts SWE.1 mask 1; the owning design must be corrected."
                )
            missing = (
                ["AUTHORITATIVE_INPUT:EN ownership contract unavailable"]
                if name == "missing-primary"
                else ["DEPENDENCY:SWR-EN-ALLOCATION unavailable"]
                if name == "missing-dependency"
                else []
            )
            primary = [
                "workproducts/SWE.1/software_requirements.md",
                "workproducts/SWE.2/software_architecture.md",
                "workproducts/SWE.3/unit_specifications.md",
                "software/hal/reg32.c",
            ]
            if name == "missing-primary":
                primary = ["software/hal/reg32.c"]
            ref = packets.seal(
                ws,
                bundle,
                findings,
                [{"path": p} for p in primary],
                missing=missing,
                required_obligations=["SWR-001", "USPEC-001"],
                techniques=[] if name == "no-allowed-strategy" else None,
                prior_strategies=[
                    signature(
                        {
                            "decision": "PROPOSE_REPAIR",
                            "strategy": "REWORK_LOCAL",
                            "affected_phase": "SWE.3",
                            "technique_id": "repair-implementation",
                            "target_obligations": ["USPEC-001"],
                            "artifact_scope": ["software/hal"],
                            "validation_expectations": [{"test_ref": "gate:SWE.3:route=PASS"}],
                        }
                    )
                ]
                if name == "reworded-strategy"
                else [],
            )
            # The runtime resolves packets in its own state directory; intake imports this hash-bound copy.
            immutable_json(root / "packets" / ref["path"], packets.load(ref))
            doc = {
                "bundle": bundle,
                "workspace": str(ws),
                "requirements_sha256": sha256_file(ws / "workproducts/SWE.1/software_requirements.md"),
                "budget": {"attempts": 1},
                "allowed_strategies": [
                    "REWORK_LOCAL",
                    "RESTART_FROM_LAST_VALID_CHECKPOINT",
                    "RETURN_TO_OWNING_UPSTREAM_PHASE",
                    "SWITCH_PREAPPROVED_MODEL_PROFILE",
                    "CLOSE_BLOCKED",
                ],
                "mission_id": mission,
                "packet_ref": ref,
                "qualification_fixture": {
                    "trial_id": trial,
                    "source_kind": "SEEDED_PROTOCOL_NOT_PRODUCT",
                    "evaluation_holdout": True,
                    "prospective_fault": FAULT_RECIPES.get(name),
                    "reference_report_sha256": digest(report),
                    "expected": scenario["expected"],
                    "requires": ["INDEPENDENTLY_MEASURED_AUTHORIZED_LOCAL_ALTERNATIVE"]
                    if name == "qualified-local-alternative"
                    else [],
                },
            }
            case = directory / "case.json"
            immutable_json(case, doc)
            jid = "afo-agent-" + hashlib.sha256(f"{aid}:afo-recovery-planner".encode()).hexdigest()[:24]
            job = {
                "case": str(case),
                "model": model,
                "profile": profile,
                "role": "afo-recovery-planner",
                "reserved_tokens": reserved,
            }
            _, measure = request_material(job)
            jobs[trial] = {"job_id": jid, "case": str(case), "case_sha256": sha256_file(case), "mission_id": mission}
            launch = directory / "input-manifest.json"
            immutable_json(
                launch,
                {
                    "kind": "QUALIFICATION_PROTOCOL_FIXTURE",
                    "case": str(case),
                    "case_sha256": sha256_file(case),
                    "profile": profile,
                    "model_profile": model,
                    "evaluation_holdout": True,
                },
            )
            envelope = {
                "schema_version": "1.0",
                "request_id": request,
                "tenant_scope": tenant,
                "manifest_sha256": sha256_file(launch),
                "input_manifest_ref": str(launch.relative_to(root)),
                "approved_by": "jefferson",
                "authorization_ref": authorization_ref,
                "driver_class": "QUALIFICATION_REG32_PROTOCOL",
                "target": "Virtual REG32 fixture; no production MCU acceptance",
                "safety_scope": "NOT_APPLICABLE: qualification fixture only",
                "model_profile": model,
                "submitted_utc": utc_now(),
                "priority": "NORMAL",
            }
            immutable_json(directory / "envelope.json", envelope)
            # Intake re-verifies these exact bytes; inputs.json is itself bound by the signed manifest.
            intake = {
                name: {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}
                for name, path in (
                    ("envelope", directory / "envelope.json"),
                    ("launch_manifest", launch),
                    ("run_manifest", ws / ".forge-run/manifest.json"),
                    ("model_profile", ws / ".forge-run/model-profile.json"),
                )
            }
            trials.append(
                {
                    "trial_id": trial,
                    "expected": scenario["expected"],
                    "recoverable": scenario["recoverable"],
                    "case": jobs[trial],
                    "order_id": oid,
                    "attempt_id": aid,
                    "envelope": str(directory / "envelope.json"),
                    "intake": intake,
                    "request_measurement": measure,
                    "output_reserve": measure["effective_output_cap"],
                    "job_token_reservation": reserved,
                    "prospective_fault": FAULT_RECIPES.get(name),
                    "prerequisites": doc["qualification_fixture"]["requires"],
                }
            )
    result = {
        "schema": "forge-c/protocol-inputs-014/1",
        "scope": "FROZEN_SEEDED_INPUTS_NOT_NATIVE_QUALIFICATION",
        "campaign_id": campaign_id,
        "stage": stage,
        "mission_id": mission,
        "root": str(root),
        "template_sha256": sha256_file(template_path),
        "generator_revision": revision,
        "generator_sha256": sha256_file(Path(__file__)),
        "model_configuration": {
            "profile": profile,
            "profile_sha256": selected["_sha256"],
            "model": model,
            "model_digest": selected["models"]["allowed"][model]["digest"],
            "precision": selected["models"]["allowed"][model]["quantization"],
            "reasoning_effort": trials[0]["request_measurement"]["effective_reasoning_effort"],
            "configured_context_not_qualified": selected["runtime"]["ollama"].get("OLLAMA_CONTEXT_LENGTH"),
        },
        "reference_report": {"path": str(root / "reference/report.json"), "sha256": sha256_file(root / "reference/report.json")},
        "jobs": jobs,
        "trials": trials,
        "count": len(trials),
        "requested_initial_reservations": {binding["job_id"]: reserved for binding in jobs.values()},
        "registry_default_tokens": registry_default,
        "allowances_authorized": False,
        "runtime_admission_created": False,
        "grants_created": 0,
        "inference_requests": 0,
    }
    immutable_json(root / "jobs.json", jobs)
    immutable_json(root / "requested-initial-reservations.json", result["requested_initial_reservations"])
    immutable_json(root / "inputs.json", result)
    return result


def readiness(inputs, *, protocol_faults=None, trial_ids=None):
    """Report actual input/recipe prerequisites; this never grants native authority."""
    from .qualification import CATALOGUES

    root = Path(inputs["root"]).resolve()
    stage = inputs.get("stage", "protocol")  # inputs prepared before targeted runs existed are protocol inputs
    template = REPO_ROOT / CATALOGUES[stage]
    if inputs.get("schema") != "forge-c/protocol-inputs-014/1" or inputs["template_sha256"] != sha256_file(template):
        raise Refused("QUALIFICATION_INPUT_TEMPLATE_CHANGED")
    cases = json.loads(template.read_text())["cases"]
    expected = {f"{case['case_id']}:{i}" for case in cases for i in range(case["repeats"])}
    n = 100 if stage == "protocol" else len(expected)
    selected = expected if trial_ids is None else set(trial_ids)
    if not selected or not selected <= expected:
        raise Refused("QUALIFICATION_TRIAL_SCOPE_INVALID")
    if (
        len(inputs["trials"]) != n
        or {t["trial_id"] for t in inputs["trials"]} != expected
        or set(inputs["jobs"]) != expected
        or len({j["job_id"] for j in inputs["jobs"].values()}) != n
    ):
        raise Refused("QUALIFICATION_INPUT_DENOMINATOR_CHANGED")
    oracle = inputs["reference_report"]
    if Path(oracle["path"]).is_symlink() or sha256_file(Path(oracle["path"])) != oracle["sha256"]:
        raise Refused("QUALIFICATION_REFERENCE_REPORT_CHANGED")
    blockers = set()
    if inputs["generator_revision"].get("dirty"):
        blockers.add("QUALIFICATION_INPUT_GENERATOR_SOURCE_DIRTY")
    for trial in inputs["trials"]:
        binding = inputs["jobs"][trial["trial_id"]]
        path = Path(binding["case"])
        if path.is_symlink() or root not in path.resolve().parents or sha256_file(path) != binding["case_sha256"]:
            raise Refused("QUALIFICATION_SOURCE_CASE_CHANGED", trial["trial_id"])
        doc = json.loads(path.read_text())
        if doc["qualification_fixture"]["trial_id"] != trial["trial_id"] or doc["mission_id"] != binding["mission_id"]:
            raise Refused("QUALIFICATION_SOURCE_CASE_REBOUND", trial["trial_id"])
        if trial["trial_id"] not in selected:
            continue
        blockers.update(doc["qualification_fixture"]["requires"])
        recipe = doc["qualification_fixture"].get("prospective_fault")
        if recipe:
            from .protocol_faults import SUPPORTED

            if trial["trial_id"].rsplit(":", 1)[0] not in SUPPORTED or (protocol_faults or {}).get(trial["trial_id"]) != recipe:
                blockers.add("NATIVE_PROTOCOL_FAULT_EXECUTOR_NOT_PROVISIONED")
        if trial["request_measurement"]["input_tokens"] + trial["output_reserve"] > trial["job_token_reservation"]:
            blockers.add("COMPLETE_SERIALIZED_CASE_EXCEEDS_JOB_ENVELOPE")
    return {
        "status": "BLOCKED" if blockers else "INPUTS_PREPARED_NOT_NATIVE_QUALIFIED",
        "blockers": sorted(blockers),
        "source_cases": n,
        "evaluated_trial_count": len(selected),
        "inference_requests": 0,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--compiler", type=Path, default=shutil.which("clang"))
    ap.add_argument("--campaign-id", required=True)
    ap.add_argument("--authorization-ref", required=True)
    ap.add_argument(
        "--qualification-job-tokens", type=int, help="explicit prospective envelope to freeze and sign; grants no allowance"
    )
    ap.add_argument("--profile", default=PROFILE, help="pinned local profile the frozen cases bind (default: %(default)s)")
    ap.add_argument("--model", default=MODEL, help="model of that profile the frozen cases bind (default: %(default)s)")
    ap.add_argument("--stage", choices=("protocol", "targeted"), default="protocol",
                    help="frozen case catalogue: the 20x5 protocol or the targeted runs (default: %(default)s)")
    args = ap.parse_args(argv)
    result = prepare(
        args.out,
        compiler=args.compiler,
        campaign_id=args.campaign_id,
        authorization_ref=args.authorization_ref,
        qualification_job_tokens=args.qualification_job_tokens,
        profile=args.profile,
        model=args.model,
        stage=args.stage,
    )
    print(
        json.dumps(
            {
                "count": result["count"],
                "inputs": str(args.out / "inputs.json"),
                "inference_requests": 0,
                "runtime_admission_created": False,
                "readiness": readiness(result),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
