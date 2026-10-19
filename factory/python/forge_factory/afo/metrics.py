"""AFO-T062/T063 (AFO-FR-008/065/066; AT-037/057/058) - AFO measurements with provenance and uncertainty.

Units and denominators (never a universal "100 % reliable"):
  AFO-M01 service availability  - healthy / covered seconds from real soak samples (soak.report); none -> UNKNOWN
  AFO-M02 READY yield           - orders READY_FOR_OFFLINE_REVIEW / terminal orders (READY + BLOCKED); a BLOCKED archive
                                  is a valid terminal outcome, never an accepted package (AT-037/057)
  AFO-M03 valid terminal rate   - terminal orders whose last attempt has a sealed package verdict / terminal orders
  AFO-M04 attempts per order    - mean and max over ORDERS (one order with many attempts is one unit, AT-058)
  AFO-M05 eligible-recovery rate - orders READY after an executed recovery plan / orders with an executed plan
  AFO-M06 operator interventions - operator actions (denials excluded) per terminal order
  AFO-M07 escaped failures      - UNKNOWN: no post-release defect source exists yet (never reported as zero)
Cohorts are homogeneous: driver class | model profile | AFO policy sha256 | factory revision of the last attempt. Every
ratio carries numerator, denominator, a Wilson 95 % interval and the order ids it counted; n below MIN_N is
INSUFFICIENT_DATA (the interval is still shown - a zero-success small cohort reports its uncertainty).
"""
from __future__ import annotations

import json

from ..common import sha256_bytes, utc_now
from ..reliability.metrics import wilson

FORMULA_VERSION = "afo-metrics-1.0"
MIN_N = 5
TERMINAL = ("READY_FOR_OFFLINE_REVIEW", "BLOCKED")


def _ratio(mid: str, cohort: str, k: int, n: int, refs: list[str], unit: str = "ratio") -> dict:
    ci = wilson(k, n)
    return {"metric_id": mid, "cohort": cohort, "numerator": k, "denominator": n, "unit": unit,
            "value": round(k / n, 6) if n else None, "ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
            "status": "UNKNOWN" if n == 0 else ("INSUFFICIENT_DATA" if n < MIN_N else "MEASURED"),
            "provenance_sha256": sha256_bytes(json.dumps(sorted(refs)).encode()), "refs": sorted(refs)[:50],
            "formula_version": FORMULA_VERSION}


def _orders(c) -> list[dict]:
    out = []
    for o in c.execute("SELECT order_id, envelope, state, policy_sha256 FROM afo_work_orders"):
        atts = [json.loads(r["record"]) | {"state": r["state"]} for r in c.execute(
            "SELECT record, state FROM afo_attempts WHERE order_id=? ORDER BY seq", (o["order_id"],))]
        env = json.loads(o["envelope"])
        rev = (atts[-1].get("factory_revision") if atts else None) or "none"
        out.append({"order_id": o["order_id"], "state": o["state"], "attempts": atts,
                    "cohort": f"{env.get('driver_class')}|{env.get('model_profile')}|{(o['policy_sha256'] or 'none')[:12]}"
                              f"|{rev[:12]}"})
    return out


def compute(soak_ids: list[str] | None = None) -> dict:
    from . import soak
    from .dashboard_api import _table, ro

    out = {"schema": "forge-c/afo-measurements/0.1", "generated_utc": utc_now(), "formula_version": FORMULA_VERSION,
           "measurements": []}
    ms = out["measurements"]
    reps = [soak.report(s) for s in (soak_ids or [])]
    cov = sum(r["covered_hours"] for r in reps)
    ms.append({"metric_id": "AFO-M01", "cohort": "host", "unit": "fraction of covered time",
               "value": round(sum(r["healthy_hours"] for r in reps) / cov, 6) if cov else None,
               "numerator": round(sum(r["healthy_hours"] for r in reps), 4), "denominator": round(cov, 4),
               "status": "MEASURED" if cov else "UNKNOWN", "refs": [f"soak:{r['soak_id']}" for r in reps],
               "unknown_exposure": sum(len(r["observation_holes"]) + len(r["clock_or_boot_jumps"]) for r in reps),
               "formula_version": FORMULA_VERSION,
               "note": "no soak samples -> UNKNOWN (the Conductor heartbeat keeps no history)" if not cov else ""})
    with ro() as c:
        orders = _orders(c) if c is not None else []
        plans = {r["order_id"] for r in c.execute("SELECT order_id FROM afo_recovery_plans WHERE status='VALIDATED'")} \
            if c is not None and _table(c, "afo_recovery_plans") else set()
        acts = c.execute("SELECT COUNT(*) FROM afo_operator_actions WHERE action NOT LIKE 'denied:%'").fetchone()[0] \
            if c is not None else 0
    for cohort in sorted({o["cohort"] for o in orders}) or ["none"]:
        co = [o for o in orders if o["cohort"] == cohort]
        term = [o for o in co if o["state"] in TERMINAL]
        ready = [o["order_id"] for o in term if o["state"] == "READY_FOR_OFFLINE_REVIEW"]
        ms.append(_ratio("AFO-M02", cohort, len(ready), len(term), [o["order_id"] for o in term]))
        sealed = [o["order_id"] for o in term if o["attempts"] and o["attempts"][-1].get("terminal_package_status")
                  in TERMINAL]
        ms.append(_ratio("AFO-M03", cohort, len(sealed), len(term), [o["order_id"] for o in term]))
        n_att = [len(o["attempts"]) for o in co if o["attempts"]]
        ms.append({"metric_id": "AFO-M04", "cohort": cohort, "unit": "attempts per order", "denominator": len(n_att),
                   "value": round(sum(n_att) / len(n_att), 3) if n_att else None, "max": max(n_att) if n_att else None,
                   "status": "UNKNOWN" if not n_att else ("INSUFFICIENT_DATA" if len(n_att) < MIN_N else "MEASURED"),
                   "formula_version": FORMULA_VERSION})
        rec = [o for o in term if o["order_id"] in plans]
        ms.append(_ratio("AFO-M05", cohort, sum(o["state"] == "READY_FOR_OFFLINE_REVIEW" for o in rec), len(rec),
                         [o["order_id"] for o in rec]))
    n_term = sum(o["state"] in TERMINAL for o in orders)
    ms.append({"metric_id": "AFO-M06", "cohort": "all", "unit": "operator actions per terminal order",
               "numerator": acts, "denominator": n_term, "value": round(acts / n_term, 3) if n_term else None,
               "status": "MEASURED" if n_term else "UNKNOWN", "formula_version": FORMULA_VERSION})
    ms.append({"metric_id": "AFO-M07", "cohort": "all", "unit": "escaped failures per READY order", "value": None,
               "status": "UNKNOWN", "formula_version": FORMULA_VERSION,
               "note": "no post-release defect source; never reported as zero"})
    return out
