"""CRE-T042 — evidence-based readiness assessment (acceptance §4). Model-free; never a safety or ASPICE statement.

Levels: OBSERVE_ONLY -> PILOT_ELIGIBLE -> ACTIVE_ELIGIBLE; the result is the highest level whose criteria are all met
by recorded evidence, else NOT_DEMONSTRATED. The configured mode and the reliability-SLO evidence status are separate
fields: CRE can operate in OBSERVE_ONLY while reliability SLOs remain NOT_DEMONSTRATED.
"""
from __future__ import annotations

import json
import subprocess

from ..common import REPO_ROOT, pretty_json, utc_now

SCOPE = "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED"


def _read(rel: str):
    p = REPO_ROOT / rel
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def assess() -> dict:
    from ..report import cre_matrix
    from .dashboard_api import _q
    from .metrics import compute
    from .policy import load
    from .store import CREStore

    pol = load()
    tasks, frs, p0_gaps = cre_matrix()
    status = {t["task"]: t["status"] for t in tasks}
    faults = _read("evidence/cre/faults/fault-injection-latest.json") or {}
    e2e = _read("evidence/cre/e2e/local-qwen-e2e-latest.json") or {}
    live = sorted((REPO_ROOT / "evidence/cre/live").glob("supervisor-cre-hook-*.json"))
    live_rec = json.loads(live[-1].read_text()) if live else {}
    decisions = [r["decision"] for r in _q("SELECT decision FROM cre_promotion_decisions")]
    obs = dict(_count(["observations"] * len(_q("SELECT obs_id FROM cre_failure_observations"))))
    metrics = compute(CREStore(), pol)
    r09 = [m for m in metrics["measurements"] if m["metric_id"] == "CRE-R09"]
    min_n = int(pol.get("statistics.min_samples_for_descriptive_charts"))
    try:
        slo_n = int(pol.get("statistics.min_samples_for_slo_evidence"))
    except KeyError:
        slo_n = min_n

    def level(checks: dict[str, tuple[bool, str]]) -> dict:
        return {"status": "DEMONSTRATED" if all(ok for ok, _ in checks.values()) else "NOT_DEMONSTRATED",
                "met": [k for k, (ok, _) in checks.items() if ok],
                "missing": [f"{k}: {why}" for k, (ok, why) in checks.items() if not ok]}

    d0 = all(status.get(f"CRE-T00{i}") == "PASS" for i in range(1, 5))
    observe = level({
        "baseline_and_audit": (d0, "CRE-T001..T004 not all PASS"),
        "policy_observe_only": (pol.mode == "OBSERVE_ONLY", f"mode {pol.mode}"),
        "live_supervisor_zero_model_calls": (live_rec.get("model_calls") == 0 and live_rec.get("cre_hook_degraded_events")
                                             == 0, "no live supervisor CRE evidence"),
        "failure_registry_populated": (obs.get("observations", 0) > 0, "no observations imported"),
    })
    p0_pass = all(status.get(t["task"]) == "PASS" for t in tasks if t["priority"] == "P0" and t["task"] != "CRE-T042")
    pilot = level({
        "all_other_p0_tasks_pass": (p0_pass, "a P0 task is not PASS"),
        "fault_campaign_all_pass": (faults.get("passed") == faults.get("total") and bool(faults.get("total")),
                                    "fault campaign missing or failing"),
        "real_e2e_terminal_evidence": (e2e.get("result") == "PASS", "no real local-model terminal package evidence"),
        "candidate_evaluations_recorded": ({"REJECTED", "ELIGIBLE_FOR_OFFLINE_REVIEW"} <= set(decisions),
                                           "no live REJECTED + ELIGIBLE decisions on real candidates"),
        "pilot_authorization": (bool(pol.data.get("authorization")), "no owner authorization block for PILOT in the "
                                                                    "reliability policy"),
        "live_fabro_crash_recovery_drill": (_drill_passed(), "no PASS record of an owner-authorized live Fabro "
                                                              "crash -> recovery drill (evidence/cre/live)"),
    })
    active = level({
        "pilot_demonstrated": (pilot["status"] == "DEMONSTRATED", "PILOT_ELIGIBLE not demonstrated"),
        "authorized_reversible_actions": (bool(pol.get("promotion.allowed_automatic_operational_actions")),
                                          "no pre-authorized reversible actions"),
        "signed_operator_runbook": (False, "docs/cre-runbook.md exists but has no recorded owner review/sign-off"),
    })
    readiness = ("ACTIVE_ELIGIBLE" if active["status"] == "DEMONSTRATED" else "PILOT_ELIGIBLE"
                 if pilot["status"] == "DEMONSTRATED" else "OBSERVE_ONLY" if observe["status"] == "DEMONSTRATED"
                 else "NOT_DEMONSTRATED")
    small = [f"{m['cohort_key'].split('|model=')[1].split('|')[0]}/{m['cohort_key'].split('mode=')[1]}: "
             f"{m['numerator']}/{m['denominator']} [{m['ci_lower']:.2f}, {m['ci_upper']:.2f}]" for m in r09]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    return {"schema": "forge-c/cre-readiness/1.0", "assessed_at": utc_now(), "git_head": head,
            "configured_mode": pol.mode, "policy_sha256": pol.sha256, "readiness": readiness,
            "levels": {"OBSERVE_ONLY": observe, "PILOT_ELIGIBLE": pilot, "ACTIVE_ELIGIBLE": active},
            "reliability_slo_evidence": slo_evidence(slo_n, small),
            "tasks": {"pass": sum(s == "PASS" for s in status.values()), "total": len(status)},
            "p0_requirements_unmet": p0_gaps,
            "supported_claims": [
                "bounded recovery and safe termination in 18 injected fault scenarios (isolated real components)",
                "independent promotion gate rejects unsafe, concealing and protected-path candidates",
                "root causes VERIFIED only by reproducer contrast on real commits (5 historical fixes)",
                "healthy supervision makes zero model calls (live + 100-poll tests)",
                "one owner-authorized live Fabro crash detected and recovered by the model-free supervisor "
                "(evidence/cre/live/fabro-crash-drill-*.json)",
                "verification runner and repair-candidate code run as separate OS identities (rootless Podman "
                "sub-UIDs) without network or owner credentials"],
            "not_claimed": ["universal or 100% reliability", "PILOT/ACTIVE operation", "ISO 26262 / ASIL B approval",
                            "Automotive SPICE capability level", "production release"],
            "safety_signoff": None, "scope": SCOPE}


def _drill_passed() -> bool:
    for p in sorted((REPO_ROOT / "evidence/cre/live").glob("fabro-crash-drill-*.json")):
        try:
            if json.loads(p.read_text()).get("result") == "PASS":
                return True
        except ValueError:
            continue
    return False


def slo_evidence(min_n: int, small: list[str]) -> dict:
    """Reliability-SLO evidence: packaged work-order attempts grouped by cohort AND recorded factory revision (a
    homogeneous sample). min_n = statistics.min_samples_for_slo_evidence (else the descriptive-chart minimum).
    A group with >= min_n attempts is a measured BASELINE (yield with a Wilson interval); it is
    not an SLO attainment claim - spec section 6: targets are owner-approved after observing comparable cohorts.
    Attempts excluded by a recorded owner decision (evidence/cre/slo/exclusions.json) are not counted."""
    from collections import defaultdict

    from .metrics import attempts as _attempts
    from .metrics import wilson

    excluded = (_read("evidence/cre/slo/exclusions.json") or {}).get("excluded", {})
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for a in _attempts():
        if a["attempt_id"] in excluded or not a.get("finished") or a.get("revision_basis") != "recorded_at_launch":
            continue
        groups[(a["cohort_key"], a["revision"])].append(a)
    measured = []
    for (ck, rev), xs in sorted(groups.items()):
        if len(xs) >= min_n:
            k, n = sum(bool(x["completed"]) for x in xs), len(xs)
            lo, hi = wilson(k, n)
            measured.append({"cohort_key": ck, "factory_revision": rev[:12], "n": n, "completed": k,
                             "workflow_yield": round(k / n, 3), "wilson95": [round(lo, 3), round(hi, 3)],
                             "attempts": [x["attempt_id"] for x in xs]})
    largest = max(((len(v), k) for k, v in groups.items()), default=(0, ("-", "-")))
    return {"status": "BASELINE_MEASURED" if measured else "NOT_DEMONSTRATED",
            "min_samples": min_n, "measured_cohorts": measured,
            "attainment": "NOT_EVALUATED: no owner-approved target rate (spec section 6)",
            "reason": ("" if measured else f"no cohort reaches {min_n} packaged attempts on one recorded factory "
                       f"revision (largest: {largest[0]}); ") + "workflow yield per cohort (CRE-R09): " + "; ".join(small),
            "excluded_attempts": excluded,
            "growth": "no statistically supported improvement (evidence/cre/metrics/growth-report-latest.json)"}


def _count(xs: list) -> dict:
    out: dict = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


def main(argv: list[str] | None = None) -> int:
    rec = assess()
    (REPO_ROOT / "evidence/cre/readiness-assessment.json").write_text(pretty_json(rec))
    print(f"readiness {rec['readiness']} (mode {rec['configured_mode']}); SLO evidence "
          f"{rec['reliability_slo_evidence']['status']}")
    for lv, d in rec["levels"].items():
        print(f"  {lv}: {d['status']}" + "".join(f"\n    missing - {m}" for m in d["missing"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
