"""KPI-T005..T010 — model-free, replay-safe KPI engine (K01–K20) producing schema-valid snapshots.

Rules: deterministic (same event set + window + policy + catalog => byte-identical snapshot); no model calls;
missing inputs => UNKNOWN / NOT_APPLICABLE / NOT_COMPUTABLE / INSUFFICIENT_* with explanation, never a guessed 0;
safety/process KPIs (K20) are counted hard violations, never weighted; no KPI changes package status.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import yaml

from ..common import CONFIG_DIR, KPI_CONTRACTS_DIR, canonical_json, schema_errors, sha256_bytes
from .sources import dedup_sort, event_set_digest

ENGINE_VERSION = "kpi-engine-0.5.0"
PHASES = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]
LOW_SAMPLE = 5


def ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def catalog() -> dict:
    return json.loads((KPI_CONTRACTS_DIR / "kpi-catalog.json").read_text())


def policy() -> dict:
    return yaml.safe_load((CONFIG_DIR / "kpi-policy.yaml").read_text())


def formula_version() -> str:
    h = hashlib.sha256(canonical_json({"engine": ENGINE_VERSION, "catalog": catalog(), "policy": policy()})).hexdigest()
    return f"{ENGINE_VERSION}+{h[:16]}"


def quantile(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 3)


def mv(mid: str, status: str, value: float | None, unit: str, n: int, refs: list[str], num: float | None = None,
       den: float | None = None, filters: dict | None = None, evidence: list[str] | None = None, expl: str = "") -> dict:
    out = {"metric_id": mid, "status": status, "value": None if value is None else round(float(value), 6), "unit": unit,
           "sample_count": int(n), "numerator": num, "denominator": den, "filters": filters or {},
           "source_event_refs": sorted(set(refs))[:200], "evidence_refs": sorted(set(evidence or []))[:50]}
    if expl:
        out["explanation"] = expl[:600]
    return out


def ratio(mid: str, num: float, den: float, unit: str, refs: list[str], filters: dict | None = None,
          evidence: list[str] | None = None, zero_den: str = "NOT_APPLICABLE", expl: str = "",
          n: int | None = None) -> dict:
    if not den:
        return mv(mid, zero_den, None, unit, 0, refs, num, den, filters, evidence, expl or "denominator is zero")
    n = int(den) if n is None else n  # sample = units observed (orders/segments), not seconds
    st = "MEASURED" if n >= LOW_SAMPLE else "INSUFFICIENT_SAMPLE"
    return mv(mid, st, num / den, unit, n, refs, num, den, filters, evidence,
              expl or ("low sample: no SLO/benchmark claim" if st == "INSUFFICIENT_SAMPLE" else ""))


class Engine:
    def __init__(self, events: list[dict], window_start: str, window_end: str, baselines: dict | None = None):
        self.all = dedup_sort(events)
        self.ws, self.we = window_start, window_end
        self.ev = [e for e in self.all if window_start <= e["ts_utc"] <= window_end]
        self.baselines = baselines or {}

    def of(self, *types: str, src: list[dict] | None = None) -> list[dict]:
        return [e for e in (src if src is not None else self.ev) if e["type"] in types]

    # --- order model ---------------------------------------------------------------------------------
    def orders(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for e in self.of("work_order.admitted", src=self.all):
            o = out.setdefault(e["order_id"], {"admitted": e["ts_utc"], "attempts": [], "refs": []})
            o["admitted"] = min(o["admitted"], e["ts_utc"])
            o["attempts"].append(e["attempt_id"])
            o["refs"].append(e["event_id"])
            if e["ts_utc"] >= o.get("latest_admitted", ""):
                o["latest_admitted"], o["latest_attempt"] = e["ts_utc"], e["attempt_id"]
        for e in self.of("package.sealed", src=self.all):
            po = out.get(e["order_id"])
            if po is None:
                continue
            o = po
            if (o.get("sealed") is None or e["ts_utc"] >= o["sealed"]):
                o.update({"sealed": e["ts_utc"], "status": e["payload"]["package_status"], "pkg_ref": e["event_id"],
                          "evidence": e["evidence_refs"], "gaps": e["payload"].get("gaps", [])})
        for o in out.values():  # a newer attempt after the last seal re-opens the order (retry, not a new unit)
            if o.get("sealed") and o["latest_admitted"] > o["sealed"]:
                o["sealed"] = None
        return out

    def latest_attempt_events(self, *types: str) -> list[dict]:
        latest = {o["latest_attempt"] for o in self.orders().values()}
        return [e for e in self.of(*types) if e["attempt_id"] in latest]

    def initial_inspections(self) -> dict[tuple[str, str], dict]:
        first: dict[tuple[str, str], dict] = {}
        for e in self.of("inspection.completed", src=self.all):
            k = (e["order_id"], e["phase"])
            if k not in first:  # sorted by ts: first-ever inspection of the phase for this order
                first[k] = e
        return first

    # --- metrics --------------------------------------------------------------------------------------
    def k01(self) -> dict:
        orders = self.orders()
        intervals = []
        for o in orders.values():
            a, b = ts(o["admitted"]), ts(o.get("sealed") or self.we)
            a, b = max(a, ts(self.ws)), min(b, ts(self.we))
            if b > a:
                intervals.append((a, b))
        if not intervals:
            return mv("K01", "NOT_APPLICABLE", None, "ratio", 0, [], None, None, {}, None,
                      "no admitted work in window: availability is N/A, not 0 (AC-K09)")
        hb = sorted((ts(e["ts_utc"]), e["payload"]["status"], e["event_id"]) for e in self.of("supervisor.heartbeat"))
        eligible = healthy = 0.0
        refs = []
        for a, b in intervals:
            eligible += b - a
            for i, (t, st_, eid) in enumerate(hb):
                t2 = hb[i + 1][0] if i + 1 < len(hb) else t + 120
                t2 = min(t2, t + 180)  # a missing heartbeat beyond 3 min is unknown telemetry, not healthy
                lo, hi = max(a, t), min(b, t2)
                if hi > lo and st_ == "HEALTHY":
                    healthy += hi - lo
                    refs.append(eid)
        if not hb:
            return mv("K01", "UNKNOWN", None, "ratio", 0, [], None, round(eligible, 1), {}, None,
                      "no supervisor heartbeats in window")
        return ratio("K01", round(healthy, 1), round(eligible, 1), "ratio", refs[:200], n=len(intervals), expl=
                     "eligible = admitted-work seconds; unobserved telemetry counted as not healthy")

    def k02(self) -> list[dict]:
        first = self.initial_inspections()
        rows = []
        for p in PHASES:
            ins = [e for (o, ph), e in first.items() if ph == p and self.ws <= e["ts_utc"] <= self.we]
            passed = [e for e in ins if e["payload"]["verdict"] == "PASS"]
            rows.append(ratio("K02", len(passed), len(ins), "ratio", [e["event_id"] for e in ins], {"phase": p},
                              [r for e in ins for r in e["evidence_refs"]]))
        return rows

    def closed_orders(self) -> dict[str, dict]:
        return {k: o for k, o in self.orders().items() if o.get("sealed") and self.ws <= o["sealed"] <= self.we}

    def k03_k19q(self) -> tuple[dict, dict]:
        first = self.initial_inspections()
        closed = self.closed_orders()
        rty_ok, q_ok, refs = 0, 0, []
        for oid, o in closed.items():
            fp = all(first.get((oid, p)) and first[(oid, p)]["payload"]["verdict"] == "PASS" for p in PHASES)
            gates_first = not any(e["order_id"] == oid and e["payload"].get("result") in ("REJECTED", "FAIL")
                                  for e in self.of("quality_gate.evaluated", src=self.all))
            rty_ok += int(fp and gates_first)
            q_ok += int(fp and gates_first and o["status"] == "READY_FOR_OFFLINE_REVIEW")
            refs.append(o["pkg_ref"])
        k03 = ratio("K03", rty_ok, len(closed), "ratio", refs, {"basis": "unique closed orders"},
                    expl="all six initial inspections and gates first try; BLOCKED orders fail")
        q = {"num": q_ok, "den": len(closed), "refs": refs}
        return k03, q

    def k04(self) -> list[dict]:
        closed = self.closed_orders()
        ready = [o for o in closed.values() if o["status"] == "READY_FOR_OFFLINE_REVIEW"]
        blocked = [o for o in closed.values() if o["status"] == "BLOCKED"]
        return [mv("K04", "MEASURED", len(ready), "packages_per_window", len(closed), [o["pkg_ref"] for o in ready],
                   len(ready), None, {"status": "READY_FOR_OFFLINE_REVIEW"}),
                mv("K04", "MEASURED", len(blocked), "packages_per_window", len(closed), [o["pkg_ref"] for o in blocked],
                   len(blocked), None, {"status": "BLOCKED"}, None, "BLOCKED shown separately; not yield")]

    def k05(self) -> list[dict]:
        rows = []
        for status in ("READY_FOR_OFFLINE_REVIEW", "BLOCKED"):
            os_ = [o for o in self.closed_orders().values() if o["status"] == status]
            d = [ts(o["sealed"]) - ts(o["admitted"]) for o in os_]
            for q, name in ((0.5, "p50"), (0.95, "p95")):
                val = quantile(d, q)
                st = "NOT_APPLICABLE" if not d else ("INSUFFICIENT_SAMPLE" if len(d) < LOW_SAMPLE else "MEASURED")
                rows.append(mv("K05", st, val, "seconds", len(d), [o["pkg_ref"] for o in os_], None, None,
                               {"status": status, "quantile": name}))
        return rows

    def segments(self) -> list[dict]:
        """Active station segments from Fabro stage events: (order, attempt, phase, node, visit, seconds)."""
        st: dict[tuple, str] = {}
        segs: list[dict] = []
        visits: dict[tuple, int] = {}
        for e in self.of("stage.started", "stage.completed", "stage.failed"):
            node = e["payload"].get("node") or ""
            if not e.get("phase") or "gate" in node or "route" in node or "verify" in node:
                continue
            k = (e["attempt_id"], node)
            if e["type"] == "stage.started":
                st[k] = e["ts_utc"]
            elif k in st:
                visits[k] = visits.get(k, 0) + 1
                segs.append({"order": e["order_id"], "phase": e["phase"], "node": node, "visit": visits[k],
                             "seconds": ts(e["ts_utc"]) - ts(st.pop(k)), "ref": e["event_id"]})
        return segs

    def k06_k07(self) -> list[dict]:
        segs = self.segments()
        rows = []
        for p in PHASES:
            ss = [s for s in segs if s["phase"] == p]
            per_visit = [s["seconds"] for s in ss]
            for q, name in ((0.5, "p50"), (0.95, "p95")):
                st = "NOT_APPLICABLE" if not ss else ("INSUFFICIENT_SAMPLE" if len(ss) < LOW_SAMPLE else "MEASURED")
                rows.append(mv("K06", st, quantile(per_visit, q), "seconds", len(ss), [s["ref"] for s in ss], None, None,
                               {"phase": p, "quantile": name}))
        total = sum(s["seconds"] for s in segs)
        rework = sum(s["seconds"] for s in segs if s["visit"] > 1)
        rows.append(ratio("K07", round(rework, 1), round(total, 1), "ratio", [s["ref"] for s in segs if s["visit"] > 1],
                          n=len(segs),
                          expl="correction + reinspection visits (visit > 1); infrastructure repair excluded"))
        return rows

    def k08(self) -> dict:
        f = self.of("finding.recorded")
        with_origin = [e for e in f if e["payload"].get("origin_phase")]
        if not with_origin:
            return mv("K08", "UNKNOWN", None, "ratio", len(f), [e["event_id"] for e in f], None, None, {}, None,
                      f"{len(f)} findings recorded; no adjudicated origin phase -> leakage UNKNOWN (not 0)")
        leaked = [e for e in with_origin if PHASES.index(e["phase"]) > PHASES.index(e["payload"]["origin_phase"])]
        return ratio("K08", len(leaked), len(with_origin), "ratio", [e["event_id"] for e in with_origin])

    def k09(self) -> dict:
        pol = json.loads((Path(__file__).resolve().parents[4] / "factory/release-manager/policies/"
                          "release-package-policy-v0.4.json").read_text())
        slots = len(pol["required_files"]) + len(pol["required_quality_checks"]) + len(pol["required_patterns"])
        closed = self.closed_orders()
        if not closed:
            return mv("K09", "NOT_APPLICABLE", None, "ratio", 0, [], None, None, {}, None, "no sealed package in window")
        num = den = 0
        refs = []
        for o in closed.values():
            missing = sum(1 for g in o["gaps"] if g.startswith(("missing_or_empty_file:", "failed_or_missing_quality_check:",
                                                                  "missing_required_pattern:")))
            num += max(0, slots - missing)
            den += slots
            refs.append(o["pkg_ref"])
        return ratio("K09", num, den, "ratio", refs, {"policy": pol["schema"]},
                     expl="validated = policy slot present AND quality check true (file existence alone is not enough)")

    def k10_k11(self) -> list[dict]:
        rv = self.latest_attempt_events("requirements.verification_recorded")
        tl = self.latest_attempt_events("traceability.link_verified")
        return [ratio("K10", sum(1 for e in rv if e["payload"]["verified"]), len(rv), "ratio", [e["event_id"] for e in rv],
                      zero_den="NOT_APPLICABLE"),
                ratio("K11", sum(1 for e in tl if e["payload"]["semantically_valid"]), len(tl), "ratio",
                      [e["event_id"] for e in tl], zero_den="NOT_APPLICABLE",
                      expl="link valid only if requirement exists, test file exists and contains the test id")]

    def k12(self) -> dict:
        m = self.of("misra.rule_assessed")
        if not m:
            return mv("K12", "NOT_APPLICABLE", None, "ratio", 0, [], None, None, {}, None, "no Cppcheck/MISRA run in window")
        from ..mcp.servers.analysis import MISRA_RULES
        supported = misra_addon_rules()
        assessed = len(set(supported) & set(MISRA_RULES))
        return mv("K12", "MEASURED", assessed / len(MISRA_RULES), "ratio", len(m), [e["event_id"] for e in m], assessed,
                  len(MISRA_RULES), {"ruleset": "MISRA C:2012 main rules (numbers only)"}, None,
                  f"{len(MISRA_RULES) - assessed} rules not checked by the Cppcheck addon; compliance NOT claimed")

    def k13(self) -> list[dict]:
        cov = [e for e in self.of("quality_gate.evaluated") if e["payload"].get("check") == "llvm_coverage"
               and e["payload"].get("result") == "PASS"]
        rows = []
        for measure, key in (("statement/line", "line_pct"), ("branch", "branch_pct"), ("mcdc", "mcdc_pct")):
            if not cov:
                rows.append(mv("K13", "NOT_APPLICABLE", None, "percent", 0, [], None, None, {"measure": measure}))
                continue
            last = cov[-1]
            v = last["payload"]["metrics"].get(key)
            rows.append(mv("K13", "MEASURED" if v is not None else "UNKNOWN", v, "percent", 1, [last["event_id"]], None,
                           None, {"measure": measure, "environment": "host"}, last["evidence_refs"],
                           "host LLVM instrumentation; not target evidence"))
        return rows

    def k14(self) -> list[dict]:
        fp = self.of("firmware.footprint_measured")
        adm = {e["attempt_id"]: e["payload"].get("budgets", {}) for e in self.of("work_order.admitted", src=self.all)}
        rows = []
        for measure, op, key, bkey in (("flash_bytes", "measure_elf", "flash_bytes", "flash_bytes"),
                                       ("static_ram_bytes", "measure_elf", "ram_bytes", "static_ram_bytes"),
                                       ("stack_bytes", "stack_usage", "max_frame_bytes", "stack_bytes")):
            cand = [e for e in fp if e["payload"]["op"] == op and e["payload"]["metrics"].get(key) is not None]
            if not cand:
                rows.append(mv("K14", "UNKNOWN", None, "bytes", 0, [], None, None, {"measure": measure}, None,
                               "no target footprint measurement"))
                continue
            e = cand[-1]
            v, budget = e["payload"]["metrics"][key], adm.get(e["attempt_id"], {}).get(bkey)
            rows.append(mv("K14", "MEASURED", v, "bytes", 1, [e["event_id"]], v, budget,
                           {"measure": measure, "target": "cortex-m55 (object-level)"}, e["evidence_refs"],
                           f"budget {budget} B, headroom {None if budget is None else budget - v} B; estimation: object-level"))
        rows.append(mv("K14", "NOT_COMPUTABLE", None, "cycles", 0, [], None, None, {"measure": "cycles"}, None,
                       "no cycle/WCET measurement available (no target/simulator)"))
        return rows

    def k15(self) -> dict:
        use = self.of("agent.usage_recorded")
        ready = [o for o in self.closed_orders().values() if o["status"] == "READY_FOR_OFFLINE_REVIEW"]
        total = sum(e["payload"]["tokens_new"] for e in use)
        if not ready:
            return mv("K15", "NOT_APPLICABLE", None, "tokens_per_package", len(use), [e["event_id"] for e in use], total, 0,
                      {"basis": "reported"}, None, f"{total} reported tokens across attempts; 0 READY packages -> N/A")
        if not use:
            return mv("K15", "UNKNOWN", None, "tokens_per_package", 0, [], None, len(ready), {}, None, "usage unavailable")
        return mv("K15", "MEASURED", total / len(ready), "tokens_per_package", len(use), [e["event_id"] for e in use], total,
                  len(ready), {"basis": "reported"})

    def k16_k17(self) -> list[dict]:
        term = [e for e in self.of("incident.resolved") if e["payload"]["recoverable"]]
        rest = [e for e in term if e["payload"]["auto_restored"]]
        mttr = [ts(e["ts_utc"]) - ts(e["payload"]["detected_at"]) for e in rest]
        rows = [ratio("K16", len(rest), len(term), "ratio", [e["event_id"] for e in term],
                      expl=f"MTTR p50={quantile(mttr, .5)} s p95={quantile(mttr, .95)} s; dedup by fingerprint")]
        window_s = 7 * 86400
        resolved = [e for e in self.of("incident.resolved", src=self.all) if e["payload"]["terminal_state"] == "RESOLVED"]
        observable = [e for e in resolved if ts(e["ts_utc"]) + window_s <= ts(self.we)]
        if not observable:
            rows.append(mv("K17", "NOT_COMPUTABLE", None, "ratio", len(resolved), [e["event_id"] for e in resolved], None,
                           None, {"window_days": 7}, None, "no resolved fingerprint has a complete 7-day observation window"))
        else:
            det = self.of("incident.detected", src=self.all)
            rec = [e for e in observable if any(d["payload"]["fingerprint"] == e["payload"]["fingerprint"]
                                                and ts(e["ts_utc"]) < ts(d["ts_utc"]) <= ts(e["ts_utc"]) + window_s for d in det)]
            rows.append(ratio("K17", len(rec), len(observable), "ratio", [e["event_id"] for e in observable],
                              {"window_days": 7}, expl="no claim that lessons prevented recurrence"))
        return rows

    def k18(self) -> dict:
        orders = self.orders()
        wip = [o for o in orders.values() if ts(o["admitted"]) <= ts(self.we) and
               (not o.get("sealed") or ts(o["sealed"]) > ts(self.we))]
        ages = [ts(self.we) - ts(o["admitted"]) for o in wip]
        return mv("K18", "MEASURED", len(wip), "count", len(wip), [r for o in wip for r in o["refs"]], len(wip), None,
                  {"at": self.we}, None, f"ages p50={quantile(ages, .5)} s" if ages else "")

    def k19(self, k01: dict, q: dict) -> dict:
        if k01["value"] is None:
            return mv("K19", "NOT_COMPUTABLE", None, "ratio", 0, [], None, None, {}, None, "availability not computable")
        if not self.baselines.get("frozen"):
            return mv("K19", "NOT_COMPUTABLE", None, "ratio", q["den"], q["refs"], None, None,
                      {"A": k01["value"], "P": None, "Q": (q["num"] / q["den"]) if q["den"] else None}, None,
                      "no frozen calibrated per-class reference baseline (INSUFFICIENT_BASELINE); SFOEE suppressed")
        return mv("K19", "NOT_COMPUTABLE", None, "ratio", 0, [], None, None, {}, None, "performance factor not implemented")

    def k20(self) -> dict:
        refs, viol = [], 0
        first = self.initial_inspections()
        for oid, o in self.closed_orders().items():
            if o["status"] == "READY_FOR_OFFLINE_REVIEW":
                missing = [p for p in PHASES if (oid, p) not in first]
                viol += len(missing)  # READY without a recorded inspection = skipped mandatory inspection
                if any(g.startswith("failed_or_missing_quality_check") for g in o["gaps"]):
                    viol += 1  # bypassed gate
                refs.append(o["pkg_ref"])
        for e in self.of("package.sealed"):
            if (e["payload"].get("scope") or "") != "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED" or \
                    "APPROVED" in json.dumps(e["payload"]).replace("NOT_SAFETY_APPROVED", ""):
                viol += 1  # fabricated approval assertion
                refs.append(e["event_id"])
        return mv("K20", "MEASURED", viol, "count", len(self.of("package.sealed")), refs, viol, None, {}, None,
                  "hard zero-tolerance count, never weighted or offset by other KPIs")

    def compute(self) -> list[dict]:
        k01 = self.k01()
        k03, q = self.k03_k19q()
        rows = [k01, *self.k02(), k03, *self.k04(), *self.k05(), *self.k06_k07(), self.k08(), self.k09(), *self.k10_k11(),
                self.k12(), *self.k13(), *self.k14(), self.k15(), *self.k16_k17(), self.k18(), self.k19(k01, q), self.k20()]
        return rows


_MISRA_CACHE: list[str] | None = None


def misra_addon_rules() -> list[str]:
    """Rules the installed Cppcheck MISRA addon implements (parsed from its source; deterministic)."""
    global _MISRA_CACHE
    if _MISRA_CACHE is None:
        import re

        from ..mcp.servers.analysis import MISRA_ADDON
        try:
            src = Path(MISRA_ADDON).read_text()
            _MISRA_CACHE = sorted({f"{a}.{b}" for a, b in re.findall(r"def misra_(\d+)_(\d+)\(", src)})
        except OSError:
            _MISRA_CACHE = []
    return _MISRA_CACHE


def snapshot(events: list[dict], window_start: str, window_end: str, release_status: str = "IN_PROGRESS",
             baselines: dict | None = None) -> dict:
    eng = Engine(events, window_start, window_end, baselines)
    digest = event_set_digest(eng.ev)
    fv = formula_version()
    cat_hash = sha256_bytes(canonical_json(catalog()))
    snap = {"snapshot_id": "kpi-" + hashlib.sha256(f"{fv}|{window_start}|{window_end}|{digest}|{release_status}".encode()
                                                   ).hexdigest()[:24],
            "formula_version": fv, "window_start": window_start, "window_end": window_end,
            "metric_values": eng.compute(), "event_set_digest": digest, "release_status": release_status,
            "source_catalog_hash": cat_hash}
    errs = schema_errors_kpi(snap)
    if errs:
        raise ValueError(f"kpi snapshot schema violation: {errs[:3]}")
    return snap


def schema_errors_kpi(snap: dict) -> list[str]:
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads((KPI_CONTRACTS_DIR / "kpi-snapshot.schema.json").read_text())
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(snap)]


def serialize(snap: dict) -> bytes:
    """Checksum-ready canonical serialization (sorted keys, no whitespace variance)."""
    return canonical_json(snap) + b"\n"


__all__ = ["snapshot", "serialize", "formula_version", "schema_errors", "Engine"]


def learning_metrics(path=None):
    """Separate learning facts, usage and benefit; missing records are UNKNOWN, never zero benefit."""
    import sqlite3
    from ..common import state_dir
    path = path or state_dir() / 'knowledge/lessons.sqlite3'
    if not path.is_file():
        return {'status':'UNKNOWN','benefit_status':'UNKNOWN'}
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='job_experience'").fetchone():
            return {'status':'UNKNOWN','benefit_status':'UNKNOWN'}
        total=c.execute('SELECT COUNT(*) FROM job_experience').fetchone()[0]
        dispositions=dict(c.execute('SELECT state,COUNT(*) FROM learning_dispositions GROUP BY state'))
        transfers=dict(c.execute('SELECT kind,COUNT(*) FROM lesson_transfers GROUP BY kind'))
    return {'status':'RECORDED','experience_count':total,'dispositions':dispositions,'transfers':transfers,
            'benefit_status':'UNKNOWN' if not transfers.get('BENEFIT') else 'MEASURED_COMPARISONS_REQUIRE_REVIEW',
            'scope':'all recorded experience; separate from product quality'}
