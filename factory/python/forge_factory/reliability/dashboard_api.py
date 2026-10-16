"""CRE-T035/T036 — read-only Reliability projections for the existing 002 dashboard (no second UI, no writes).

* Every query opens the CRE tables READ-ONLY (sqlite `mode=ro`); viewing can never change capture, state or policy.
* Display filters (class, cohort, metric, recurring) select rows only; denominators are reported with every value.
* Security denials are visible to the auditor role only (same channel split as the trace viewer).
* Anomaly cues (CRE-T036) are diagnostic: they are derived for display and never dispatch repairs or edit gates.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from ..common import REPO_ROOT, state_dir

_CACHE: dict[str, tuple[float, object]] = {}


def _db() -> Path:
    return state_dir() / "supervisor" / "incidents.sqlite3"


def _q(sql: str, args: tuple = ()) -> list[dict]:
    p = _db()
    if not p.is_file():
        return []
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, args)]
    except sqlite3.OperationalError:
        return []  # CRE tables not migrated yet => empty, shown as such
    finally:
        c.close()


def summary(role: str) -> dict:
    from .policy import load
    from .taxonomy import CLASSIFIER_VERSION

    pol = load()
    modes = _q("SELECT failure_class, recurring, significant, occurrences FROM cre_failure_modes")
    capa = _q("SELECT state, root_cause_status FROM cre_capa")
    dec = _q("SELECT decision FROM cre_promotion_decisions")
    ver = _q("SELECT max(version) v FROM cre_schema_version")
    readiness = REPO_ROOT / "evidence/cre/readiness-assessment.json"
    out = {"mode": pol.mode, "policy_sha256": pol.sha256, "classifier_version": CLASSIFIER_VERSION,
           "schema_version": ver[0]["v"] if ver else None,
           "failure_modes": {"total": len(modes), "recurring": sum(m["recurring"] for m in modes),
                             "significant": sum(m["significant"] for m in modes),
                             "observations": sum(m["occurrences"] for m in modes),
                             "by_class": _count([m["failure_class"] for m in modes])},
           "capa": {"total": len(capa), "by_state": _count([c["state"] for c in capa]),
                    "root_cause": _count([c["root_cause_status"] for c in capa])},
           "promotions": _count([d["decision"] for d in dec]),
           "rollbacks": len(_q("SELECT seq FROM cre_rollbacks")),
           "readiness": json.loads(readiness.read_text()).get("readiness") if readiness.is_file() else "NOT_ASSESSED",
           "note": "read-only projection; safety readiness is never inferred from a metric tile"}
    if role == "auditor":
        out["security_denials"] = len(_q("SELECT event_id FROM cre_events WHERE type='cre.security_denial'"))
    return out


def _count(xs: list) -> dict:
    out: dict = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def failure_modes(failure_class: str | None = None, recurring: bool | None = None, limit: int = 50) -> dict:
    q, a = "SELECT * FROM cre_failure_modes WHERE 1=1", []
    if failure_class:
        q += " AND failure_class=?"
        a.append(failure_class)
    if recurring is not None:
        q += " AND recurring=?"
        a.append(int(recurring))
    rows = _q(q + " ORDER BY distinct_attempts DESC, occurrences DESC LIMIT ?", (*a, limit))
    total = sum(r["occurrences"] for r in rows)
    cum = 0
    for r in rows:  # Pareto share of the displayed (filtered) set - numerator and denominator move together
        cum += r["occurrences"]
        r["pareto_share"] = round(cum / total, 4) if total else None
    return {"items": rows, "denominator_observations": total, "filters": {"class": failure_class,
                                                                         "recurring": recurring}}


def observations(fingerprint: str, limit: int = 50) -> dict:
    rows = _q("SELECT obs_id, attempt_id, phase, ts_utc, outcome, disposition, source_ref, evidence_sha256, excerpt, "
              "cohort, factory_version FROM cre_failure_observations WHERE fingerprint=? AND obs_id NOT IN "
              "(SELECT obs_id FROM cre_observation_retractions) ORDER BY ts_utc LIMIT ?", (fingerprint, limit))
    return {"fingerprint": fingerprint, "items": rows}


def capas() -> dict:
    out = []
    for r in _q("SELECT capa_id, record FROM cre_capa ORDER BY capa_id"):
        rec = json.loads(r["record"])
        rec["history"] = _q("SELECT from_state, to_state, at, reason FROM cre_capa_history WHERE capa_id=? ORDER BY seq",
                            (r["capa_id"],))
        rec["links"] = _q("SELECT kind, ref FROM cre_capa_links WHERE capa_id=? ORDER BY seq", (r["capa_id"],))
        out.append(rec)
    return {"items": out}


def promotions() -> dict:
    return {"items": [json.loads(r["record"]) for r in
                      _q("SELECT record FROM cre_promotion_decisions ORDER BY at DESC LIMIT 50")]}


def metrics(metric: str | None = None, cohort: str | None = None) -> dict:
    hit = _CACHE.get("metrics")
    if hit is None or time.time() - hit[0] > 60:
        p = REPO_ROOT / "evidence/cre/metrics/reliability-metrics-latest.json"
        _CACHE["metrics"] = (time.time(), json.loads(p.read_text()) if p.is_file() else {"measurements": []})
    rep = _CACHE["metrics"][1]
    rows = [m for m in rep.get("measurements", [])  # type: ignore[union-attr]
            if (not metric or m["metric_id"].startswith(metric)) and (not cohort or cohort in m["cohort_key"])]
    return {"computed_at": rep.get("computed_at"), "formula_version": rep.get("formula_version"),  # type: ignore[union-attr]
            "items": rows, "note": "every value carries n, interval and status; NOT_COMPUTABLE is not zero"}


def anomalies() -> dict:
    """CRE-T036 diagnostic cues: recurring significant failure modes seen again in the most recent attempts.
    Read-only: never dispatches a repair, never changes a gate or threshold."""
    recent = _q("SELECT attempt_id, max(ts_utc) t FROM cre_failure_observations GROUP BY attempt_id "
                "ORDER BY t DESC LIMIT 5")
    last = [r["attempt_id"] for r in recent]
    if not last:
        return {"items": [], "basis": "no observations"}
    qmarks = ",".join("?" * len(last))
    rows = _q(f"SELECT m.fingerprint, m.error_code, m.operation, m.distinct_attempts, count(o.obs_id) recent "  # noqa: S608
              f"FROM cre_failure_modes m JOIN cre_failure_observations o ON o.fingerprint=m.fingerprint "
              f"WHERE m.recurring=1 AND o.attempt_id IN ({qmarks}) GROUP BY m.fingerprint ORDER BY recent DESC",
              tuple(last))
    return {"items": rows, "basis": f"recurring modes present in the {len(last)} most recent attempts",
            "action": "DIAGNOSTIC_ONLY"}
