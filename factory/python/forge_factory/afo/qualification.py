"""Executable Feature 014 campaign preparation, bounded native stepping and reporting.

Freeze before live execution. `step` uses existing local-agent/native reconciliation,
never its own inference engine or job budgets. It requires pre-provisioned, approved
AFO job bindings, a current signed campaign runbook and exact candidate identity.
Missing authority/inputs produce explicit blockers; dry-run is not qualification.
"""

from __future__ import annotations
import argparse
import json
import socket
import statistics
import subprocess
from pathlib import Path
from ..common import REPO_ROOT, sha256_file, utc_now
from .durable import Refused, digest, immutable_json

STAGES = ("protocol", "rcc", "benchmark", "operation-24", "operation-72", "operation-168")
FAULTS = (
    "last-job-success",
    "last-job-failure",
    "last-job-block",
    "empty-queue",
    "drained-queue",
    "dependency-outage",
    "clean-exit",
    "crash",
    "hang",
    "reboot",
    "restart-limit",
    "poison-head",
    "resource-pressure",
    "operator-stop-resume",
    "post-campaign-continuity",
    "later-authorized-intake",
)


def revision():
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
    ).stdout.strip()


def freeze(stage, destination, *, identity, inputs=(), jobs=None, baseline=None, model_profile=None):
    from ..lrtx.role_capability import key

    if stage not in STAGES:
        raise Refused("UNKNOWN_CAMPAIGN_STAGE")
    key(identity)
    template = REPO_ROOT / "factory/qualification/014/protocol-cases.json"
    cases = json.loads(template.read_text())["cases"] if stage == "protocol" else []
    from ..lrtx.seeded import CATALOGUE, catalogue_hash

    product_cases = []
    if stage == "benchmark":
        from ..lrtx.campaign import load as load_product_campaign

        product = load_product_campaign(REPO_ROOT / "specs/010-local-rtx-optimization/campaign.yaml")
        for case in product["cases"]:
            for repeat in range(1, case.get("repeat", 1) + 1):
                product_cases.append(
                    {
                        **case,
                        "repeat": repeat,
                        "trial_id": f"{case['id']}:{repeat:02}",
                        "profile": "local-rtx-v2-omniverse2",
                        "model": model_profile,
                    }
                )
    count = 100 if stage == "protocol" else 30 if stage == "benchmark" else 1
    refs = []
    for raw in inputs:
        p = Path(raw)
        if p.is_symlink() or not p.is_file():
            raise Refused("QUALIFICATION_INPUT_UNAVAILABLE", str(p))
        refs.append({"path": str(p.resolve()), "sha256": sha256_file(p)})
    manifest = {
        "schema": "forge-c/qualification-014/1",
        "stage": stage,
        "created_at": utc_now(),
        "source_revision": revision(),
        "execution_host": "omniverse2",
        "identity": identity,
        "identity_sha256": key(identity),
        "cases": cases,
        "product_cases": product_cases,
        "critical_defect_ids": [c["id"] for c in CATALOGUE],
        "independent_defect_catalogue_sha256": catalogue_hash(),
        "expected_trials": count,
        "template_sha256": sha256_file(template),
        "inputs": refs,
        "jobs": jobs or {},
        "baseline": baseline,
        "faults": list(FAULTS) if stage.startswith("operation-") else [],
        "bounds": {
            "probe_gap_seconds": 600,
            "control_cycle_seconds": 120,
            "restore_seconds": 600,
            "eligible_queue_seconds": 600,
            "immediate_start_burst": 5,
            "start_interval_seconds": 600,
            "slow_recovery_cooldown_seconds": 600,
            "verification_workers": 1,
            "inference_requests": 1,
            "batch_items": 32,
            "post_campaign_seconds": 1200,
        },
        "criteria": {
            "protocol_correct": 100,
            "protocol_false_success": 0,
            "product_ready_min": 27,
            "product_trials": 30,
            "critical_detection": 1.0,
            "false_ready": 0,
            "structured_invalid_rate_below": 0.01,
            "median_input_reduction_min": 0.5,
        },
        "service_persists_after_campaign": True,
        "authorization_ref": None,
        "model_profile": model_profile,
    }
    immutable_json(Path(destination), manifest)
    return manifest


def validate(manifest):
    if manifest.get("schema") != "forge-c/qualification-014/1" or manifest.get("stage") not in STAGES:
        raise Refused("CAMPAIGN_MANIFEST_INVALID")
    from ..lrtx.role_capability import key

    if key(manifest["identity"]) != manifest["identity_sha256"]:
        raise Refused("CAMPAIGN_IDENTITY_CHANGED")
    if manifest["stage"] == "protocol":
        cases = manifest["cases"]
        if len(cases) != 20 or len({c["case_id"] for c in cases}) != 20 or any(c["repeats"] != 5 for c in cases):
            raise Refused("PROTOCOL_DENOMINATOR_CHANGED")
    if manifest["stage"] == "benchmark" and (
        len(manifest["product_cases"]) != 30 or len({c["trial_id"] for c in manifest["product_cases"]}) != 30
    ):
        raise Refused("FROZEN_PRODUCT_COHORT_CHANGED")
    if manifest["expected_trials"] != (100 if manifest["stage"] == "protocol" else 30 if manifest["stage"] == "benchmark" else 1):
        raise Refused("CAMPAIGN_DENOMINATOR_CHANGED")
    for ref in manifest["inputs"]:
        p = Path(ref["path"])
        if not p.is_file() or p.is_symlink() or sha256_file(p) != ref["sha256"]:
            raise Refused("CAMPAIGN_FROZEN_INPUT_CHANGED")
    if manifest["service_persists_after_campaign"] is not True:
        raise Refused("CAMPAIGN_CANNOT_STOP_FACTORY")
    return digest(manifest)


def preflight(manifest, *, live=False, authorization_ref=None):
    sha = validate(manifest)
    blockers = []
    if not manifest.get("model_profile"):
        blockers.append("EXACT_MODEL_PROFILE_NOT_PROVISIONED")
    if not manifest["inputs"]:
        blockers.append("FROZEN_PRIMARY_INPUTS_NOT_PROVISIONED")
    if manifest["stage"] == "protocol" and len(manifest["jobs"]) != 100:
        blockers.append("APPROVED_100_JOB_BINDINGS_NOT_PROVISIONED")
    if (manifest["stage"] in ("benchmark", "rcc") or manifest["stage"].startswith("operation-")) and not manifest["jobs"]:
        blockers.append("APPROVED_PRODUCT_JOB_BINDINGS_NOT_PROVISIONED")
    if live:
        from . import authz, host
        from .policy import load

        eff = load()
        if socket.gethostname().split(".")[0] not in ("omniverse", "omniverse2"):
            blockers.append("QWEN_MUST_EXECUTE_ON_OMNIVERSE")
        if revision() != manifest["source_revision"]:
            blockers.append("QUALIFICATION_REVISION_CHANGED")
        if not host.preflight()["ok"]:
            blockers.append("AUTHORITATIVE_DATA_MOUNT_NOT_READY")
        auth = authz.find(
            eff.mode,
            eff.sha256 or "",
            ref=authorization_ref,
            action="recover_workorder",
            request={"model": manifest.get("model_profile")},
        )
        if not auth.allow:
            blockers.append(auth.code)
        else:
            grant = json.loads((authz.AUTH_DIR / f"{authorization_ref}.json").read_text())
            if grant.get("signed_runbook_ref") != "qualification-014:" + sha:
                blockers.append("SIGNED_CAMPAIGN_RUNBOOK_MISMATCH")
    return {
        "manifest_sha256": sha,
        "status": "BLOCKED" if blockers else "PREPARED_NOT_RUN",
        "blockers": blockers,
        "runtime_implementation": "SEPARATE_TEST_EVIDENCE",
        "local_model_capability": "NOT_RUN",
        "product_success": "NOT_RUN",
        "learning_benefit": "NOT_RUN",
        "operational_availability": "NOT_RUN",
    }


def step(manifest, authorization_ref, destination, *, store=None):
    """One bounded native control-plane step. Repeated calls adopt the same job; campaign end never stops services."""
    report = preflight(manifest, live=True, authorization_ref=authorization_ref)
    if report["blockers"]:
        return report
    if manifest["stage"] != "protocol":
        return {**report, "status": "BLOCKED", "blockers": ["USE_APPROVED_PRODUCT_OR_SOAK_ENTRYPOINT_FOR_THIS_STAGE"]}
    from .queue import Store
    from .policy import load
    from . import local_agent

    store = store or Store()
    eff = load()
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    for case in manifest["cases"]:
        for repeat in range(5):
            trial = f"{case['case_id']}:{repeat}"
            path = dest / (trial.replace(":", "-") + ".json")
            if path.exists():
                continue
            binding = manifest["jobs"].get(trial)
            if not binding:
                raise Refused("CAMPAIGN_JOB_BINDING_MISSING", trial)
            with store.tx() as c:
                row = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (binding["job_id"],)).fetchone()
            if not row:
                raise Refused("CAMPAIGN_JOB_UNPROVISIONED", trial)
            job = json.loads(row[0])
            if job["case_sha256"] != binding["case_sha256"] or job.get("mission_id") != binding["mission_id"]:
                raise Refused("CAMPAIGN_JOB_REBOUND", trial)
            job = local_agent.poll(store, store.order(job["order_id"]), job, eff)
            if job["state"] in ("PREPARED", "LAUNCHING", "RUNNING"):
                return {"status": "IN_PROGRESS", "trial": trial, "job_id": job["job_id"]}
            from .completion_receipt import Receipts

            receipt = Receipts(store).latest(job["receipt_id"]) if job.get("receipt_id") else None
            observed = (
                receipt["decision"]
                if receipt and receipt["admissibility_state"] == "ACCEPTED"
                else "REJECTED"
                if receipt
                else "FAILED_PROTOCOL"
            )
            row = {
                "trial_id": trial,
                "case_id": case["case_id"],
                "repeat": repeat,
                "expected": case["expected"],
                "observed": observed,
                "manifest_sha256": report["manifest_sha256"],
                "native_run_id": job.get("run_id"),
                "job_id": job["job_id"],
                "receipt": receipt,
                "reported_tokens": job.get("reported_tokens"),
                "reserved_tokens": job["reserved_tokens"],
                "false_success": None,
                "duplicate_effects": None,
                "authority_escapes": None,
                "usage_unknown": job.get("reported_tokens") is None,
            }
            immutable_json(path, row)
            return {"status": "RECORDED", "trial": trial, "row_sha256": sha256_file(path)}
    return {
        "status": "CAMPAIGN_WINDOW_COMPLETE",
        "factory_service": "CONTINUES_UNCHANGED",
        "report": protocol_report(manifest, load_rows(dest)),
    }


def load_rows(directory):
    return [json.loads(p.read_text()) for p in sorted(Path(directory).glob("*.json"))]


def protocol_report(manifest, rows):
    sha = validate(manifest)
    expected = {f"{c['case_id']}:{i}": c for c in manifest["cases"] for i in range(5)}
    ids = [r["trial_id"] for r in rows]
    if len(set(ids)) != len(ids) or any(i not in expected for i in ids):
        raise Refused("PROTOCOL_TRIAL_IDENTITY_CHANGED")
    correct = useful = 0
    failures = []
    for row in rows:
        case = expected[row["trial_id"]]
        if row["manifest_sha256"] != sha:
            raise Refused("PROTOCOL_RESULT_MANIFEST_CHANGED")
        receipt = row.get("receipt") or {}
        ok = (
            row["observed"] == case["expected"]
            and row.get("native_run_id")
            and row.get("false_success") is False
            and row.get("duplicate_effects") == 0
            and row.get("authority_escapes") == 0
        )
        if case["recoverable"]:
            ok = (
                ok
                and receipt.get("admissibility_state") == "ACCEPTED"
                and receipt.get("decision") == "PROPOSE_REPAIR"
                and bool(receipt.get("bound_plan"))
            )
        correct += bool(ok)
        useful += bool(receipt.get("admissibility_state") == "ACCEPTED" and receipt.get("decision") == "PROPOSE_REPAIR")
        if not ok:
            failures.append(row["trial_id"])
    return {
        "status": "NOT_RUN"
        if not rows
        else "PASS"
        if len(rows) == 100 and correct == 100
        else "FAIL"
        if failures or len(rows) == 100
        else "INCOMPLETE",
        "expected_denominator": 100,
        "observed_denominator": len(rows),
        "correct_outcomes": correct,
        "useful_plan_count": useful,
        "failures": failures,
        "missing": sorted(set(expected) - set(ids)),
        "usage_unknown": sum(r.get("usage_unknown", True) for r in rows),
        "native_capability_only": True,
        "product_recovery_proven": False,
        "availability_proven": False,
    }


def product_report(manifest, rows):
    validate(manifest)
    planned = {c["trial_id"] for c in manifest["product_cases"]}
    ids = [r["trial_id"] for r in rows]
    if len(set(ids)) != len(ids) or not set(ids) <= planned:
        raise Refused("BENCHMARK_DENOMINATOR_CHANGED")
    if not rows:
        return {"status": "NOT_RUN", "expected_denominator": 30}
    ready = sum(r.get("sealed_ready") is True and r.get("native_all_six_gates") is True for r in rows)
    critical = [d for r in rows for d in r.get("critical_defects", [])]
    missing_critical = sorted(set(manifest["critical_defect_ids"]) - {d.get("case_id") for d in critical})
    complete = all(
        type(r.get(k)) is int and r[k] >= 0
        for r in rows
        for k in ("structured_calls", "invalid_structured", "complete_prompt_tokens")
    )
    calls = sum(r["structured_calls"] for r in rows) if complete else None
    invalid = sum(r["invalid_structured"] for r in rows) if complete else None
    prompts = [r["complete_prompt_tokens"] for r in rows] if complete else []
    base = (manifest.get("baseline") or {}).get("median_complete_prompt_tokens")
    reduction = 1 - statistics.median(prompts) / base if prompts and base else None
    ok = (
        len(rows) == 30
        and ready >= 27
        and not missing_critical
        and critical
        and all(d.get("independently_detected") is True for d in critical)
        and all(r.get("false_ready") is False and r.get("required_evidence_complete") is True for r in rows)
        and complete
        and calls > 0
        and invalid / calls < 0.01
        and reduction is not None
        and reduction >= 0.5
    )
    return {
        "status": "PASS" if ok else "FAIL" if len(rows) == 30 else "INCOMPLETE",
        "expected_denominator": 30,
        "observed_denominator": len(rows),
        "verified_ready": ready,
        "critical_exposures": len(critical),
        "missing_critical_cases": missing_critical,
        "complete_accounting": complete,
        "structured_calls": calls,
        "invalid_rate": invalid / calls if calls else None,
        "median_prompt_reduction": reduction,
        "learning_benefit": "SEPARATE_COMPARISON",
        "operational_availability": "SEPARATE_CAMPAIGN",
    }


def inspector_report(required_obligations, claims, independent_verdicts):
    required = set(required_obligations)
    if len({v["obligation_id"] for v in independent_verdicts}) != len(independent_verdicts):
        raise Refused("INSPECTION_ORACLE_DUPLICATED")
    known = {
        v["obligation_id"]: v
        for v in independent_verdicts
        if v.get("producer") in ("reference", "metamorphic", "mutant", "SMT", "deterministic_gate") and v.get("evidence_ref")
    }
    unverified = sorted(required - set(known))
    escaped = sorted(k for k in required & set(known) if known[k].get("pass") is False and claims.get(k) == "PASS")
    return {
        "status": "PASS" if not unverified and not escaped else "FAIL",
        "required": len(required),
        "independently_covered": len(required & set(known)),
        "unverified": unverified,
        "escaped_defects": escaped,
        "same_model_agreement_is_independent_evidence": False,
    }


def configuration_comparison(manifest, baseline, candidate):
    from ..lrtx.role_capability import IDENTITY

    if baseline.get("manifest_sha256") != digest(manifest) or candidate.get("manifest_sha256") != digest(manifest):
        raise Refused("COMPARISON_CASES_CHANGED")
    if baseline.get("measured") is not True or not baseline.get("native_run_ids"):
        raise Refused("UNCHANGED_BASELINE_MEASUREMENT_REQUIRED")
    changed = [k for k in IDENTITY if baseline["identity"][k] != candidate["identity"][k]]
    if len(changed) != 1:
        raise Refused("ONE_CONTROLLED_CONFIGURATION_FACTOR_REQUIRED")
    if baseline["case_ids"] != candidate["case_ids"] or not candidate.get("independent_outcomes"):
        raise Refused("COMPARISON_DENOMINATOR_OR_ORACLE_MISSING")
    return {
        "changed_factor": changed[0],
        "baseline_identity": baseline["identity"],
        "candidate_identity": candidate["identity"],
        "rcc_success_prerequisite": False,
        "automatic_selection": False,
        "automatic_deployment": False,
    }


def rcc_report(package_path, gates):
    from .dispatch import package_verdict

    verdict = package_verdict(Path(package_path))
    ready = (
        verdict.get("verdict") == "READY_FOR_OFFLINE_REVIEW"
        and set(gates) == {f"SWE.{i}" for i in range(1, 7)}
        and all(v == "PASS" for v in gates.values())
    )
    return {
        "status": "PASS" if ready else "FAIL",
        "package_verdict": verdict,
        "gates": gates,
        "gpio_requires": [
            "RCC_READY",
            "QUALIFIED_GPIO_PROFILE",
            "AUTHORITATIVE_GPIO_INPUTS",
            "FROZEN_INTAKE",
            "CURRENT_GPIO_AUTHORITY",
        ],
    }


def gpio_admission(prerequisites):
    required = ("rcc_ready", "qualified_profile", "authoritative_inputs", "frozen_intake", "authorized")
    missing = [k for k in required if prerequisites.get(k) is not True]
    return {"admit": not missing, "missing": missing}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["freeze", "dry-run", "step", "report"])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--stage", choices=STAGES, default="protocol")
    ap.add_argument("--identity", type=Path)
    ap.add_argument("--input", type=Path, action="append", default=[])
    ap.add_argument("--jobs", type=Path)
    ap.add_argument("--results", type=Path)
    ap.add_argument("--authorization-ref")
    ap.add_argument("--model-profile")
    args = ap.parse_args(argv)
    if args.command == "freeze":
        if args.identity is None:
            ap.error("--identity is required for freeze")
        manifest = freeze(
            args.stage,
            args.manifest,
            identity=json.loads(args.identity.read_text()),
            inputs=args.input,
            jobs=json.loads(args.jobs.read_text()) if args.jobs else None,
            model_profile=args.model_profile,
        )
        out = {"status": "FROZEN_NOT_RUN", "manifest_sha256": digest(manifest)}
    else:
        manifest = json.loads(args.manifest.read_text())
        if args.command == "dry-run":
            out = preflight(manifest)
        elif args.command == "step":
            if args.results is None:
                ap.error("--results required")
            out = step(manifest, args.authorization_ref, args.results)
        else:
            rows = load_rows(args.results) if args.results else []
            out = protocol_report(manifest, rows) if manifest["stage"] == "protocol" else product_report(manifest, rows)
    print(json.dumps(out, indent=2))
    return 2 if out.get("status") in ("FAIL", "BLOCKED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
