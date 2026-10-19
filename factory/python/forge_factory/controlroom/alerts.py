"""Alerts (CR-T034; research R8): deterministic conditions over the floor snapshot, the scorecard and the control
charts. An alert's id is a hash of (condition, subject), so a condition that persists is the same alert, updated -
never duplicated. Safety/process violations are critical and not filterable (FR-017). Acknowledgement lives only
in the viewer's browser; the server keeps no alert state and no alert changes factory state (FR-018).
"""
from __future__ import annotations

import hashlib
import json

SEVERITY = {"SAFETY_PROCESS_VIOLATION": "critical", "STATION_BLOCKED": "critical", "LEAD_TIME_OVER_LIMIT": "warning",
            "REWORK_BUDGET_NEAR": "warning", "YIELD_BELOW_THRESHOLD": "warning", "YIELD_OUT_OF_CONTROL": "warning",
            "FEED_STALE": "warning"}
ORDER = {"critical": 0, "warning": 1, "info": 2}


def alert(condition: str, subject: dict, reason: str, since: str | None, evidence: list[str] | None = None) -> dict:
    aid = "al-" + hashlib.sha256(json.dumps([condition, subject], sort_keys=True).encode()).hexdigest()[:16]
    return {"alert_id": aid, "condition": condition, "severity": SEVERITY[condition], "subject": subject,
            "reason": reason[:300], "since": since, "evidence": (evidence or [])[:10],
            "filterable": condition != "SAFETY_PROCESS_VIOLATION"}


def from_floor(floor: dict, cfg: dict) -> list[dict]:
    out = []
    live = [u for u in floor["units"] if not u.get("package") and u["status"] != "STOPPED"]
    for s in floor["stations"]:
        if s["andon"] == "BLOCKED":
            for wo in s["units"]:
                u = next((x for x in floor["units"] if x["work_order"] == wo), None)
                if u and u["status"] in ("BLOCKED", "STOPPED"):
                    out.append(alert("STATION_BLOCKED", {"station": s["station_id"], "work_order": wo},
                                     f"{s['station_id']}: {u['reason'] or 'stopped'}", u["station_since"], s["evidence"]))
    for u in live:
        if u["elapsed_s"] > cfg["lead_time_limit_s"]:
            out.append(alert("LEAD_TIME_OVER_LIMIT", {"work_order": u["work_order"]},
                             f"in progress for {int(u['elapsed_s'] // 60)} min (limit {cfg['lead_time_limit_s'] // 60} min)",
                             u["admitted_at"]))
        st = u["station"]
        used, budget = (u.get("rework_cycles") or {}).get(st, 0), (u.get("rework_budget") or {}).get(st)
        if budget and used / budget >= cfg["rework_near_ratio"]:
            out.append(alert("REWORK_BUDGET_NEAR", {"station": st, "work_order": u["work_order"]},
                             f"{st}: {used} of {budget} rework cycles used", u["station_since"]))
    if floor.get("stale"):
        out.append(alert("FEED_STALE", {}, f"no new record for {floor['data_age_s']} s while units are in progress",
                         floor["generated_at"]))
    return out


def from_scorecard(sc: dict | None, cfg: dict) -> list[dict]:
    if not sc or sc.get("status") != "OK":
        return []
    out = []
    for m in sc["kpis"]:
        if m["metric_id"] == "K20" and m["display"] == "VALUE" and (m["value"] or 0) > 0:
            out.append(alert("SAFETY_PROCESS_VIOLATION", {"window": sc["window"]["kind"]},
                             f"{int(m['value'])} safety/process violation(s) recorded (K20)", sc["window"]["start_utc"],
                             m.get("evidence_refs")))
        if m["metric_id"] == "K02" and m["display"] == "VALUE" and m["status"] == "MEASURED" \
                and m["value"] < cfg["yield_threshold"]:
            ph = (m.get("filters") or {}).get("phase")
            out.append(alert("YIELD_BELOW_THRESHOLD", {"station": ph},
                             f"{ph} first-pass yield {round(m['value'] * 100)} % < {round(cfg['yield_threshold'] * 100)} % "
                             f"(n={m['sample_count']}, {sc['window']['kind']})", sc["window"]["start_utc"]))
    return out


def from_quality(q: dict | None) -> list[dict]:
    out = []
    for st, ch in ((q or {}).get("charts") or {}).items():
        c = ch.get("first_pass_yield") or {}
        n = len(c.get("points") or [])
        last = [v for v in c.get("violations") or [] if v["point_index"] == n - 1]
        if c.get("status") == "OK" and last:
            out.append(alert("YIELD_OUT_OF_CONTROL", {"station": st},
                             f"{st} first-pass yield: latest day violates {', '.join(v['rule'] for v in last)}",
                             c["points"][-1]["t"]))
    return out


def collect(floor: dict, cfg: dict, sc: dict | None = None, q: dict | None = None) -> dict:
    seen: dict[str, dict] = {}
    for a in from_floor(floor, cfg) + from_scorecard(sc, cfg) + from_quality(q):
        seen.setdefault(a["alert_id"], a)
    alerts = sorted(seen.values(), key=lambda a: (ORDER[a["severity"]], a["condition"], a["alert_id"]))
    return {"alerts": alerts, "violations_open": sum(1 for a in alerts if a["condition"] == "SAFETY_PROCESS_VIOLATION")}
