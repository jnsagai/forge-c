"""CRE D5 (CRE-T030..T034) — reliability analytics, ADR-CRE-005. Deterministic, model-free, additive to 003.

* Units: the driver ORDER (K-series semantics) and, separately labelled, the work-order ATTEMPT. Retries never add
  orders (R01); attempt-level measures (R09, R10) are named distinctly and never relabel K01..K20.
* Every binomial value carries n, a Wilson score interval and its assumptions; zero failures report the exact one-sided
  upper bound (~3/n, rule of three), never 100%. Missing data is UNKNOWN / NOT_COMPUTABLE / NOT_APPLICABLE.
* Cohorts (driver, target, model, code model, provider, mode) are never pooled without a declared normalization.
* SPC is measurement-only: limits need a frozen calibration window of >= min_samples comparable samples, otherwise
  INSUFFICIENT_BASELINE; signals are diagnostic events, never gate or policy changes.
* K16/K17 (003) are reused from the KPI snapshot, not recomputed or redefined.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, sha256_bytes, state_dir, utc_now
from . import events as E
from .observe import attempt_context
from .policy import CRE_CONTRACTS_DIR, Policy
from .store import CREStore

FORMULA_VERSION = "cre-metrics-1.0"
Z = {0.9: 1.6448536269514722, 0.95: 1.959963984540054, 0.99: 2.5758293035489004}
PRICES = {"miss": 0.14, "hit": 0.0028, "out": 0.28}  # USD per 1M tokens (gateway defaults; ESTIMATED cost basis)
COHORT_KEYS = ("driver_class", "target", "model", "code_model", "provider", "mode")


def wilson(k: int, n: int, conf: float = 0.95) -> tuple[float, float] | None:
    if n <= 0:
        return None
    z = Z[conf]
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def zero_failure_upper(n: int, conf: float = 0.95) -> float | None:
    """Exact one-sided upper bound on the failure probability after n independent successes (~3/n at 95%)."""
    return None if n <= 0 else 1 - (1 - conf) ** (1 / n)


def _validator():
    from jsonschema import Draft202012Validator

    return Draft202012Validator(json.loads((CRE_CONTRACTS_DIR / "reliability-measurement.schema.json").read_text()))


def measurement(metric_id: str, cohort: str, start: str, end: str, num: int | None, den: int | None, *,
                policy: Policy, unit: str = "ratio", status: str | None = None, value: float | None = None,
                assumptions: list[str] | None = None, notes: list[str] | None = None,
                provenance: list[str] | None = None, binomial: bool = True) -> dict:
    conf = float(policy.get("statistics.confidence_level"))
    st = status
    if st is None:
        st = "NOT_COMPUTABLE" if not den else "MEASURED"
    if value is None and den and num is not None and st in ("MEASURED", "ESTIMATED"):
        value = num / den
    ci = wilson(num, den, conf) if binomial and den and num is not None and st in ("MEASURED", "ESTIMATED") else None
    notes = list(notes or [])
    if binomial and den and num is not None and st == "MEASURED":
        notes.append(f"n={den}")
        if num == den:
            notes.append(f"all {den} trials succeeded: upper {int(conf * 100)}% bound on the failure probability "
                         f"{zero_failure_upper(den, conf):.3f} (~3/n) - not 100% reliability")
        if den < 30:
            notes.append("small sample: descriptive only, no reliability claim")
    rec = {"schema_version": "1.0", "metric_id": metric_id, "formula_version": FORMULA_VERSION, "cohort_key": cohort,
           "start_utc": start, "end_utc": end, "numerator": num, "denominator": den,
           "value": None if value is None else round(value, 6), "unit": unit,
           "ci_method": f"wilson_score_{int(conf * 100)}" if ci else None,
           "ci_lower": None if ci is None else round(ci[0], 6), "ci_upper": None if ci is None else round(ci[1], 6),
           "status": st, "assumptions": assumptions or [], "quality_notes": notes,
           "provenance_refs": provenance or ["cre:observations"], "policy_sha256": policy.sha256}
    errs = [e.message for e in _validator().iter_errors(rec)]
    if errs:
        raise ValueError(f"MEASUREMENT_SCHEMA:{metric_id}:{errs[0][:120]}")
    return rec


# ---- data assembly (read-only, deterministic) ---------------------------------------------------------------------
def attempts(workspaces: list[Path] | None = None) -> list[dict]:
    wss = workspaces if workspaces is not None else sorted((state_dir() / "workorders").glob("*/workspace"))
    out = []
    for ws in wss:
        c = attempt_context(ws)
        if c is None:
            continue
        first_inspect: dict[str, str] = {}
        passed, visits, author = set(), defaultdict(int), defaultdict(int)
        log = ws / ".forge-run/gates/gate-log.jsonl"
        for line in log.read_text().splitlines() if log.is_file() else []:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("ts", "") < c["created_at"] or not r.get("phase"):
                continue
            g = r.get("gate") or {}
            if r.get("step") == "inspect" and g.get("decision") in ("PASS", "REWORK", "BLOCKED"):
                first_inspect.setdefault(r["phase"], g["decision"])
                if g["decision"] == "PASS":
                    passed.add(r["phase"])
            if r.get("step") == "author":
                author[r["phase"]] += 1
            visits[r["phase"]] += 1
        try:
            pkg = json.loads((ws / ".forge-run/package.json").read_text())
        except (OSError, ValueError):
            pkg = {}
        out.append({"attempt_id": c["attempt_id"], "order_id": c["order_id"], "started": c["created_at"],
                    "finished": pkg.get("finalized_at"), "cohort": c["cohort"], "cohort_key": c["cohort_key"],
                    "revision": c["factory_revision"].get("commit", "UNKNOWN"),
                    "revision_basis": c["factory_revision"].get("basis", "UNKNOWN"),
                    "completed": "SWE.6" in passed, "phases_passed": sorted(passed), "first_inspection": first_inspect,
                    "author_visits": dict(author), "package_status": pkg.get("package_status")})
    return sorted(out, key=lambda a: (a["started"], a["attempt_id"]))


def cloud_tokens(a: dict, meter: Path) -> dict:
    """ESTIMATED attribution by time window (the cloud server runs one work order at a time); missing => UNKNOWN."""
    if not meter.is_file() or not a.get("finished"):
        return {"status": "UNKNOWN"}
    tin = tout = hit = calls = 0
    unknown = 0
    for line in meter.read_text().splitlines():
        r = json.loads(line)
        if not (a["started"] <= r.get("ts_utc", "") <= a["finished"]):
            continue
        calls += 1
        if r.get("tokens_input") is None:
            unknown += 1
            continue
        tin += int(r["tokens_input"])
        tout += int(r.get("tokens_output") or 0)
        hit += int(r.get("tokens_cache_hit") or 0)
    if not calls:
        return {"status": "UNKNOWN"}
    usd = ((tin - hit) * PRICES["miss"] + hit * PRICES["hit"] + tout * PRICES["out"]) / 1e6
    return {"status": "ESTIMATED", "calls": calls, "calls_without_usage": unknown, "tokens_input": tin,
            "tokens_output": tout, "tokens_cache_hit": hit, "usd": round(usd, 4),
            "method": "provider-reported usage in the attempt's [created_at, finalized_at] window"}


def comparable(a: dict, b: dict, normalization: dict | None = None) -> list[str]:
    """CRE-T034: cohort keys that differ (and are not declared normalized) make a comparison invalid."""
    norm = set((normalization or {}).get("ignore_keys", []))
    return [k for k in COHORT_KEYS if k not in norm and a.get(k) != b.get(k)]


# ---- metrics -------------------------------------------------------------------------------------------------------
def compute(store: CREStore, policy: Policy, atts: list[dict] | None = None, now: str | None = None) -> dict:
    atts = atts if atts is not None else attempts()
    # canonical input: order of delivery and duplicates never change a metric (replay/batch = incremental)
    atts = sorted({a["attempt_id"]: a for a in atts}.values(), key=lambda a: (a["started"], a["attempt_id"]))
    now = now or utc_now()
    start = atts[0]["started"] if atts else now
    out: list[dict] = []
    # R01 workflow first-attempt success per ORDER (retries never add orders)
    by_order: dict[str, list[dict]] = defaultdict(list)
    for a in atts:
        by_order[a["order_id"]].append(a)
    firsts = [sorted(v, key=lambda a: a["started"])[0] for v in by_order.values()]
    out.append(measurement("CRE-R01", "all-orders", start, now, sum(f["completed"] for f in firsts), len(firsts),
                           policy=policy, assumptions=["unit = driver order; retries are attempts of the same order"],
                           notes=[f"orders: {sorted(by_order)}", f"attempts: {len(atts)}"],
                           provenance=["workorders:gate-logs"]))
    cohorts: dict[str, list[dict]] = defaultdict(list)
    for a in atts:
        cohorts[a["cohort_key"]].append(a)
    for ck, xs in sorted(cohorts.items()):
        # R09 attempt completion (all SWE.1-6 inspection gates PASS) - attempt-level, not an order KPI
        out.append(measurement("CRE-R09", ck, xs[0]["started"], now, sum(x["completed"] for x in xs), len(xs),
                               policy=policy, assumptions=["attempts are not independent: the factory revision changed "
                                                           "between most attempts (non-stationary process)"],
                               provenance=["workorders:gate-logs"]))
        # R02 retry amplification = author visits / (attempt, phase) pairs visited
        visits = sum(sum(x["author_visits"].values()) for x in xs)
        pairs = sum(len(x["author_visits"]) for x in xs)
        out.append(measurement("CRE-R02", ck, xs[0]["started"], now, visits, pairs, policy=policy, unit="visits/phase",
                               binomial=False, notes=[f"excess author visits {visits - pairs}"],
                               provenance=["workorders:gate-logs"]))
        # R10 attempt-level station first pass per phase (first inspection verdict in the attempt)
        for ph in ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"):
            seen = [x["first_inspection"][ph] for x in xs if ph in x["first_inspection"]]
            out.append(measurement(f"CRE-R10-{ph}", ck, xs[0]["started"], now, sum(v == "PASS" for v in seen), len(seen),
                                   policy=policy, assumptions=["attempt-level; K01 (003) remains the order-level FPY"],
                                   provenance=["workorders:gate-logs"]))
    # R03 recurrences after a verified fix (from CAPA records) per eligible exposure
    with store.conn() as c:
        rec_links = c.execute("SELECT capa_id, count(*) FROM cre_capa_links WHERE kind='RECURRENCE' GROUP BY 1").fetchall()
        capas = [json.loads(r[0]) for r in c.execute("SELECT record FROM cre_capa")]
        modes = [dict(r) for r in c.execute("SELECT recurring, significant FROM cre_failure_modes")]
        decisions = [r[0] for r in c.execute("SELECT decision FROM cre_promotion_decisions")]
        rollbacks = c.execute("SELECT count(*) FROM cre_rollbacks").fetchone()[0]
        has_002 = c.execute("SELECT count(*) FROM sqlite_master WHERE name='incidents'").fetchone()[0]
        inc = [dict(r) for r in c.execute("SELECT incident_id, created_at, state FROM incidents")] if has_002 else []
        hist = [dict(r) for r in c.execute("SELECT incident_id, to_state, at FROM incident_history")] if has_002 else []
    out.append(measurement("CRE-R03", "capa-verified-fixes", start, now, sum(n for _, n in rec_links), len(capas),
                           policy=policy, binomial=False, unit="recurrences/CAPA",
                           notes=["recurrence = same error code + operation in an attempt containing the fix",
                                  f"recurring failure modes {sum(m['recurring'] for m in modes)}/{len(modes)}"],
                           provenance=["cre:capa_links", "cre:failure_modes"]))
    # R04 recovery time of terminal 002 incidents; unresolved are censored
    dur, censored = [], 0
    for i in inc:
        end = [h["at"] for h in hist if h["incident_id"] == i["incident_id"] and h["to_state"] in
               ("RESOLVED", "REQUIRES_OFFLINE_ATTENTION")]
        if end:
            from datetime import datetime
            f = "%Y-%m-%dT%H:%M:%S.%fZ"
            dur.append((datetime.strptime(end[-1], f) - datetime.strptime(i["created_at"], f)).total_seconds())
        else:
            censored += 1
    out.append(measurement("CRE-R04-p50", "supervisor-incidents", start, now, None, len(dur), policy=policy,
                           unit="seconds", binomial=False, value=statistics.median(dur) if dur else None,
                           status="MEASURED" if dur else "NOT_COMPUTABLE",
                           notes=[f"n={len(dur)} terminal incidents, {censored} censored (unresolved)"] +
                                 (["p95 not computable below 20 incidents"] if len(dur) < 20 else []),
                           provenance=["supervisor:incident_history"]))
    # R05 CAPA effectiveness: completed observation windows only
    done = [c for c in capas if c["state"] in ("EFFECTIVE", "REOPENED") and c["root_cause_status"] in ("VERIFIED",
                                                                                                      "HYPOTHESIS")]
    eff = sum(c["state"] == "EFFECTIVE" for c in done)
    out.append(measurement("CRE-R05", "capa", start, now, eff if done else None, len(done) or None, policy=policy,
                           status=None if done else "NOT_COMPUTABLE",
                           notes=[f"CAPAs still observing: {sum(c['state'] == 'EFFECTIVENESS_OBSERVING' for c in capas)}",
                                  "REOPENED counts as a completed, ineffective window"],
                           provenance=["cre:capa"]))
    # R06 candidate rejection / rollback rate
    out.append(measurement("CRE-R06", "promotion-candidates", start, now,
                           sum(d == "REJECTED" for d in decisions) + rollbacks if decisions or rollbacks else None,
                           (len(decisions) + rollbacks) or None, policy=policy,
                           notes=[f"decisions {dict((d, decisions.count(d)) for d in set(decisions))}",
                                  f"rollbacks {rollbacks}"], provenance=["cre:promotion_decisions", "cre:rollbacks"]))
    # R07 cost per accepted (READY) package; zero READY => NOT_APPLICABLE
    ready = sum(a["package_status"] == "READY" for a in atts)
    meter = state_dir() / "llm-gateway" / "usage-cloud-deepseek.jsonl"
    cloud = [cloud_tokens(a, meter) for a in atts if a["cohort"]["provider"] != "ollama"]
    est = [t for t in cloud if t["status"] == "ESTIMATED"]
    out.append(measurement("CRE-R07", "all-orders", start, now, None, ready or None, policy=policy, unit="USD/package",
                           binomial=False, status="NOT_APPLICABLE" if not ready else "ESTIMATED",
                           notes=[f"READY packages: {ready}",
                                  f"cloud attempts with estimated usage: {len(est)}/{len(cloud)}, total "
                                  f"${sum(t['usd'] for t in est):.2f} (ESTIMATED, time-window attribution)",
                                  "local-model compute cost UNKNOWN (no energy/compute meter)"],
                           provenance=["llm-gateway:usage-cloud-deepseek.jsonl"]))
    # R08 escaped / late-detected defects: found >= 2 phases after the owning phase
    defects = [o for o in store.observations() if o["error_code"].startswith("DEFECT:")]
    late = 0
    for o in defects:
        owner, det = o["operation"].split("/detected-")
        if det.startswith("SWE.") and owner.startswith("SWE.") and int(det[-1]) - int(owner[-1]) >= 2:
            late += 1
    out.append(measurement("CRE-R08", "defect-register", start, now, late if defects else None, len(defects) or None,
                           policy=policy, status=None if defects else "NOT_COMPUTABLE",
                           assumptions=["origin = the defect's target (owning) phase as routed by the gate"],
                           provenance=["cre:observations:DEFECT"]))
    out.extend(reused_kpis(policy, start, now))
    return {"schema": "forge-c/cre-metrics/1.0", "formula_version": FORMULA_VERSION, "computed_at": now,
            "policy_sha256": policy.sha256, "attempts": len(atts),
            "input_digest": sha256_bytes(canonical_json([{k: a[k] for k in ("attempt_id", "completed", "first_inspection",
                                                                               "author_visits")} for a in atts])),
            "measurements": out}


def reused_kpis(policy: Policy, start: str, now: str) -> list[dict]:
    """K16/K17 from the 003 KPI snapshot, verbatim (CRE-FR-017): reported, never recomputed or redefined here."""
    snap = REPO_ROOT / "evidence/v0.4/kpi/pilot-snapshot.json"
    out = []
    try:
        vals = json.loads(snap.read_text()).get("metric_values") or []
    except (OSError, ValueError):
        vals = []
    for kid in ("K16", "K17"):
        v = next((x for x in vals if kid in (x.get("kpi_id"), x.get("id"), x.get("metric_id"))), None)
        if v is None:
            out.append(measurement(kid, "kpi-003-reused", start, now, None, None, policy=policy,
                                   status="UNKNOWN", provenance=[str(snap.relative_to(REPO_ROOT))], binomial=False))
            continue
        num, den = v.get("numerator"), v.get("denominator")
        out.append(measurement(kid, "kpi-003-reused", start, now, num if isinstance(num, int) else None,
                               den if isinstance(den, int) else None, policy=policy, binomial=False,
                               value=v.get("value") if isinstance(v.get("value"), (int, float)) else None,
                               status="MEASURED" if isinstance(v.get("value"), (int, float)) else "NOT_COMPUTABLE",
                               notes=[f"003 status {v.get('status')}: {str(v.get('explanation', ''))[:120]}"],
                               provenance=[f"{snap.relative_to(REPO_ROOT)}#{kid}"]))
    return out


class IncrementalR09:
    """CRE-T033: streaming aggregation; equals the batch result for the same attempt set in any order of arrival."""

    def __init__(self):
        self.seen: dict[str, dict] = {}

    def add(self, a: dict) -> None:
        self.seen[a["attempt_id"]] = a  # idempotent per attempt id (duplicates, redelivery)

    def counts(self) -> dict[str, tuple[int, int]]:
        out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for a in self.seen.values():
            out[a["cohort_key"]][0] += int(a["completed"])
            out[a["cohort_key"]][1] += 1
        return {k: (v[0], v[1]) for k, v in out.items()}


def growth_report(policy: Policy, atts: list[dict], cohort: dict, split_revision: str,
                  normalization: dict | None = None) -> dict:
    """CRE-T034: pre/post comparison inside ONE cohort around a factory revision; refuses invalid pooling."""
    from .capa import is_ancestor

    members = [a for a in atts if not comparable(a["cohort"], cohort, normalization)]
    others = [a for a in atts if comparable(a["cohort"], cohort, normalization)]
    pre = [a for a in members if is_ancestor(split_revision, a["revision"]) is False]
    post = [a for a in members if is_ancestor(split_revision, a["revision"]) is True]
    unknown = [a for a in members if is_ancestor(split_revision, a["revision"]) is None]
    conf = float(policy.get("statistics.confidence_level"))

    def side(xs):
        k, n = sum(a["completed"] for a in xs), len(xs)
        return {"n": n, "completed": k, "rate": round(k / n, 4) if n else None, "wilson": wilson(k, n, conf)}

    p, q = side(pre), side(post)
    if not p["n"] or not q["n"]:
        verdict = "NOT_COMPUTABLE"
    elif p["wilson"][1] < q["wilson"][0]:
        verdict = "IMPROVEMENT_SUPPORTED"
    elif q["wilson"][1] < p["wilson"][0]:
        verdict = "DEGRADATION_SUPPORTED"
    else:
        verdict = "NO_SIGNIFICANT_DIFFERENCE"
    return {"cohort": cohort, "split_revision": split_revision, "pre": p, "post": q, "verdict": verdict,
            "excluded_other_cohorts": len(others), "excluded_unknown_revision": len(unknown),
            "assumptions": ["non-overlapping Wilson intervals as a conservative criterion",
                            "attempts treated as independent although revisions and prompts changed between them"]}


def p_chart(policy: Policy, samples: list[tuple[str, int, int]], calibration: dict | None) -> dict:
    """CRE-T032: measurement-only p-chart over (subgroup_id, defects, n). No frozen calibration => INSUFFICIENT_BASELINE."""
    min_n = int(policy.get("statistics.min_samples_for_descriptive_charts"))
    if not policy.get("statistics.p_chart_enabled_after_calibration") or not calibration:
        return {"status": "INSUFFICIENT_BASELINE", "reason": "no frozen calibration window (policy: measurement-only)",
                "signals": []}
    if calibration.get("samples", 0) < min_n or not calibration.get("frozen_at"):
        return {"status": "INSUFFICIENT_BASELINE", "reason": f"calibration has {calibration.get('samples')} < {min_n}",
                "signals": []}
    pbar = calibration["pbar"]
    signals, rows = [], []
    for sid, d, n in samples:
        sigma = math.sqrt(pbar * (1 - pbar) / n) if n else 0
        ucl, lcl = min(1.0, pbar + 3 * sigma), max(0.0, pbar - 3 * sigma)
        p = d / n if n else None
        rows.append({"subgroup": sid, "p": p, "ucl": ucl, "lcl": lcl})
        if p is not None and (p > ucl or p < lcl):
            signals.append(sid)
    return {"status": "MEASURED", "pbar": pbar, "calibration": calibration, "rows": rows, "signals": signals}


def ewma(policy: Policy, values: list[float], calibration: dict | None) -> dict:
    if not policy.get("statistics.ewma_enabled_after_calibration") or not calibration:
        return {"status": "INSUFFICIENT_BASELINE", "reason": "no frozen calibration window (policy: measurement-only)"}
    lam = float(policy.get("statistics.ewma_lambda"))
    mu, sd = calibration["mean"], calibration["sd"]
    z, rows, signals = mu, [], []
    for i, x in enumerate(values, 1):
        z = lam * x + (1 - lam) * z
        lim = 3 * sd * math.sqrt(lam / (2 - lam) * (1 - (1 - lam) ** (2 * i)))
        rows.append({"i": i, "ewma": z, "ucl": mu + lim, "lcl": mu - lim})
        if not (mu - lim <= z <= mu + lim):
            signals.append(i)
    return {"status": "MEASURED", "lambda": lam, "rows": rows, "signals": signals}


def emit_spc_signals(store: CREStore, policy: Policy, chart: str, signals: list) -> int:
    """Diagnostic only (AT-033): an event, never a repair dispatch, gate or threshold change."""
    n = 0
    for s in signals:
        n += E.record(store, E.build("cre.spc_signal", f"{chart}|{s}", {"chart": chart, "subgroup": str(s),
                                                                      "action": "DIAGNOSTIC_ONLY"},
                                     policy_sha256=policy.sha256, correlation_id=f"spc:{chart}"))
    return n


def main(argv: list[str] | None = None) -> int:
    from .policy import load

    pol = load()
    rep = compute(CREStore(), pol)
    out = REPO_ROOT / "evidence/cre/metrics"
    out.mkdir(parents=True, exist_ok=True)
    (out / "reliability-metrics-latest.json").write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    for m in rep["measurements"]:
        if m["metric_id"].startswith(("CRE-R01", "CRE-R09", "CRE-R03", "CRE-R05", "CRE-R06", "CRE-R07", "CRE-R08",
                                      "CRE-R04", "K1")):
            ci = f"[{m['ci_lower']:.3f}, {m['ci_upper']:.3f}]" if m["ci_lower"] is not None else ""
            print(f"{m['metric_id']:12s} {m['cohort_key'][:60]:60s} {m['status']:15s} "
                  f"{m['numerator']}/{m['denominator']} {m['value']} {ci}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
