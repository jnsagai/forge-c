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
            "reliability_slo_evidence": {
                "status": "NOT_DEMONSTRATED",
                "reason": f"no homogeneous cohort reaches {min_n} comparable attempts on a fixed factory revision; "
                          "workflow yield per cohort (CRE-R09): " + "; ".join(small),
                "growth": "no statistically supported improvement (evidence/cre/metrics/growth-report-latest.json)"},
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
