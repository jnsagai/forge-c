"""KPI-T002/T003 — deterministic conversion of immutable factory records into typed KPI source events.

Work-order lifecycle semantics (KPI-T003):
* `order_id` = the driver order (unique production unit); `attempt_id` = one workspace/run of that order.
  Restarts named `<order>-rN` are attempts of the same order (retries never create new units).
* admitted = manifest `created_at` of the attempt; closed/sealed = finalizer `finalized_at` (UTC).
* initial inspection = the first inspection record of a phase across ALL attempts of the order (append-only
  records => immutable; rework/reinspection can never rewrite it).
* event IDs are content-addressed (`kse-` + sha256 of type+key) => replays and duplicates are idempotent.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..common import canonical_json, schema_errors, sha256_file, state_dir
from ..inspection.engine import PHASES

SCHEMA_PATH = "../../003-manufacturing-kpis/contracts/kpi-source-event.schema.json"


def order_of(attempt_id: str, manifest: dict) -> str:
    return manifest.get("order_id") or re.sub(r"-r\d+(-aborted)?$", "", attempt_id)


def ev(type_: str, key: str, ts: str, order: str, attempt: str, payload: dict, evidence: list[str] | None = None,
       phase: str | None = None, source_kind: str = "record", source_ref: str = "") -> dict:
    eid = "kse-" + hashlib.sha256(f"{type_}|{key}".encode()).hexdigest()[:32]
    out = {"schema": "forge-c/kpi-source-event/0.5", "event_id": eid, "ts_utc": ts, "type": type_, "order_id": order,
           "attempt_id": attempt, "payload": payload, "evidence_refs": evidence or [],
           "source": {"kind": source_kind, "ref": source_ref[:512]}}
    if phase:
        out["phase"] = phase
    return out


def validate_event(e: dict) -> list[str]:
    from jsonschema import Draft202012Validator, FormatChecker

    from ..common import KPI_CONTRACTS_DIR

    schema = json.loads((KPI_CONTRACTS_DIR / "kpi-source-event.schema.json").read_text())
    return [x.message for x in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(e)]


def _norm_ts(ts: str) -> str:
    return ts if ts.endswith("Z") else ts.replace("+00:00", "Z")


def from_workspace(ws: Path, archive_root: Path | None = None, fabro_usage: dict | None = None,
                   fabro_stage_events: list[dict] | None = None) -> list[dict]:
    """All KPI source events for one attempt workspace (deterministic for identical records)."""
    attempt = ws.parent.name
    mpath = ws / ".forge-run/manifest.json"
    if not mpath.is_file():
        return []
    man = json.loads(mpath.read_text())
    if "created_at" not in man:  # KPI-FR-001: no admission timestamp => not a valid work order for KPIs
        return []
    order = order_of(attempt, man)
    out: list[dict] = []
    tgt = man.get("target", {})
    cls = {"driver_type": (man.get("driver") or "unknown").split()[1].lower() if len((man.get("driver") or "").split()) > 1
           else "unknown", "target_mcu": tgt.get("part_number", "UNSPECIFIED"), "compiler": "arm-none-eabi-gcc-10.3",
           "optimization": "-Os", "safety_profile": "ASIL_B_candidate", "complexity": man.get("complexity", "UNCLASSIFIED")}
    out.append(ev("work_order.admitted", attempt, _norm_ts(man["created_at"]), order, attempt,
                  {"class": cls, "budgets": man.get("budgets", {})}, [f"{attempt}/.forge-run/manifest.json"],
                  source_ref=str(mpath)))
    # inspections (append-only) and findings
    for p in PHASES:
        d = ws / "inspection" / p
        for f in sorted(d.glob("INS-*.json")) if d.is_dir() else []:
            r = json.loads(f.read_text())
            ref = f"sha256:{sha256_file(f)}"
            out.append(ev("inspection.completed", f"{attempt}|{r['inspection_id']}", _norm_ts(r["recorded_at"]), order,
                          attempt, {"inspection_id": r["inspection_id"], "verdict": r["verdict"],
                                    "baseline_hash": r["baseline_hash"], "stale": bool(r.get("stale_reason")),
                                    "findings_major": sum(1 for x in r["findings"] if x["severity"] in ("major", "critical")),
                                    "findings_total": len(r["findings"])}, [ref], p, "inspection_record", str(f)))
            for fd in r["findings"]:
                out.append(ev("finding.recorded", f"{attempt}|{r['inspection_id']}|{fd['id']}", _norm_ts(r["recorded_at"]),
                              order, attempt, {"finding_id": fd["id"], "severity": fd["severity"], "detected_phase": p,
                                               "origin_phase": None}, [ref], p, "inspection_record", str(f)))
    # deterministic gates (incl. SWE3-07 verification node, governor)
    gl = ws / ".forge-run/gates/gate-log.jsonl"
    if gl.is_file():
        for i, line in enumerate(gl.read_text().splitlines()):
            g = json.loads(line)
            out.append(ev("quality_gate.evaluated", f"{attempt}|gate|{i}", _norm_ts(g["ts"]), order, attempt,
                          {"step": g.get("step"), "result": g.get("result") or g.get("verdict") or
                           (g.get("gate") or {}).get("decision"), "check": g.get("check")},
                          [f"{attempt}/.forge-run/gates/gate-log.jsonl#{i}"], g.get("phase"), "gate_log", str(gl)))
    # tool results -> footprint / misra / coverage / static
    tr = ws / "evidence/tool-results.jsonl"
    if tr.is_file():
        for i, line in enumerate(tr.read_text().splitlines()):
            r = json.loads(line)
            res, key = r["result"], f"{attempt}|tool|{i}"
            refs = list(res.get("artifact_refs", []))[:3]
            ts = _norm_ts(r.get("ts_utc", man["created_at"]))
            if r["op"] in ("measure_elf", "stack_usage") and "target" in res.get("summary", ""):
                out.append(ev("firmware.footprint_measured", key, ts, order, attempt, {"op": r["op"], "status": res["status"],
                              "metrics": res.get("metrics", {})}, refs, r.get("phase"), "tool_result", str(tr)))
            elif r["op"] == "cppcheck":
                out.append(ev("misra.rule_assessed", key, ts, order, attempt, {"status": res["status"],
                              "rules_violated": sorted({x.split(":")[0][6:] for x in res.get("issues", [])
                                                        if x.startswith("MISRA-")}),
                              "metrics": res.get("metrics", {})}, refs, r.get("phase"), "tool_result", str(tr)))
            elif r["op"] in ("llvm_coverage", "run_unit", "run_integration", "clang_analyze", "validate_trace"):
                out.append(ev("quality_gate.evaluated", key, ts, order, attempt, {"step": "tool", "check": r["op"],
                              "result": res["status"], "metrics": res.get("metrics", {})}, refs, r.get("phase"),
                              "tool_result", str(tr)))
    # requirements + traceability (semantic link validation)
    req, trc = ws / "workproducts/SWE.1/software_requirements.md", ws / "traceability/requirements_to_tests.csv"
    if req.is_file():
        import csv
        import io

        reqs = sorted(set(re.findall(r"\*\*(SWR-[A-Z0-9_.-]+)\*\*", req.read_text())))
        rows = list(csv.DictReader(io.StringIO(trc.read_text()))) if trc.is_file() else []
        unit_ok = any('"op": "run_unit"' in x and '"status": "PASS"' in x
                      for x in (tr.read_text().splitlines() if tr.is_file() else []))
        for row in rows:
            rid, tid, tf = (row.get("requirement_id") or "").strip(), (row.get("test_id") or "").strip(), \
                (row.get("test_file") or "").strip()
            tpath = ws / tf if tf and ".." not in tf else None
            valid = bool(rid in reqs and tid and tpath and tpath.is_file() and tid in tpath.read_text(errors="replace"))
            out.append(ev("traceability.link_verified", f"{attempt}|link|{rid}|{tid}", _norm_ts(man["created_at"]), order,
                          attempt, {"requirement_id": rid, "test_id": tid, "semantically_valid": valid},
                          [f"{attempt}/traceability/requirements_to_tests.csv"], "SWE.6", "traceability", str(trc)))
        for rid in reqs:
            verified = unit_ok and any((r.get("requirement_id") or "").strip() == rid
                                       and (ws / (r.get("test_file") or "x")).is_file() for r in rows)
            out.append(ev("requirements.verification_recorded", f"{attempt}|req|{rid}", _norm_ts(man["created_at"]), order,
                          attempt, {"requirement_id": rid, "verified": verified}, [f"{attempt}/{req.relative_to(ws)}"],
                          "SWE.6", "requirements", str(req)))
    # package / close
    pkg = ws / ".forge-run/package.json"
    if pkg.is_file():
        p = json.loads(pkg.read_text())
        out.append(ev("package.sealed", f"{attempt}|pkg", _norm_ts(p["finalized_at"]), order, attempt,
                      {"package_status": p["package_status"], "gap_count": p["gap_count"], "gaps": p.get("gaps", [])[:60],
                       "archive_sha256": p["archive_sha256"], "scope": p.get("scope")}, [p["archive_ref"]],
                      source_kind="package", source_ref=p["archive"]))
        out.append(ev("work_order.closed", f"{attempt}|closed", _norm_ts(p["finalized_at"]), order, attempt,
                      {"outcome": p["package_status"]}, [p["archive_ref"]], source_kind="package", source_ref=p["archive"]))
    # usage (provider-reported) and stage segments
    if fabro_usage is not None:
        for s in fabro_usage.get("stages", []):
            if not s.get("model"):  # deterministic command stages consume no model tokens
                continue
            t = s["usage"]["tokens"]
            started = s.get("started_at", man["created_at"])[:26].rstrip("Z") + "Z"
            out.append(ev("agent.usage_recorded", f"{attempt}|usage|{s['stage']['id']}", _norm_ts(started),
                          order, attempt, {"stage": s["stage"]["id"], "model": s["model"]["model_id"],
                                           "tokens_new": int(t.get("input", 0)) + int(t.get("output", 0)),
                                           "cache_read": int(t.get("cache_read", 0)), "basis": "reported",
                                           "wall_ms": (s.get("timing") or {}).get("wall_time_ms")},
                          source_kind="fabro_usage", source_ref=attempt))
    for se in fabro_stage_events or []:
        typ = "stage.started" if se["event"] == "stage.started" else "stage.completed"
        out.append(ev(typ, f"{attempt}|fabro|{se['id']}", _norm_ts(se["ts"]), order, attempt,
                      {"node": se.get("node_id"), "outcome": "failed" if se["event"] == "stage.failed" else "ok"},
                      phase=_phase_of(se.get("node_id")), source_kind="fabro_event", source_ref=se["id"]))
    return out


def _phase_of(node: str | None) -> str | None:
    m = re.match(r"^swe(\d)_", node or "")
    return f"SWE.{m.group(1)}" if m else None


def from_incidents() -> list[dict]:
    from ..supervisor.store import IncidentStore

    st = IncidentStore()
    out = []
    for inc in st.all(1000):
        hist = st.history(inc["incident_id"])
        out.append(ev("incident.detected", inc["incident_id"], _norm_ts(inc["created_at"]), "factory", "factory",
                      {"fingerprint": inc["fingerprint"], "component": inc["component"], "fault_type": inc["fault_type"],
                       "recoverable": inc["recoverable"]}, [f"incident:{inc['incident_id']}"], source_kind="incident_ledger",
                      source_ref=inc["incident_id"]))
        term = [h for h in hist if h["to_state"] in ("RESOLVED", "REQUIRES_OFFLINE_ATTENTION")]
        if term:
            promoted = any(a["status"] == "PROMOTED" for a in st.attempts(inc["incident_id"]))
            out.append(ev("incident.resolved", f"{inc['incident_id']}|term", _norm_ts(term[-1]["at"]), "factory", "factory",
                          {"fingerprint": inc["fingerprint"], "terminal_state": term[-1]["to_state"],
                           "auto_restored": term[-1]["to_state"] == "RESOLVED" and promoted,
                           "recoverable": inc["recoverable"], "detected_at": inc["created_at"]},
                          [f"incident:{inc['incident_id']}"], source_kind="incident_ledger", source_ref=inc["incident_id"]))
        for a in st.attempts(inc["incident_id"]):
            if a["status"] in ("PROMOTED", "ROLLED_BACK", "FAILED"):
                out.append(ev("repair.completed", a["attempt_id"], _norm_ts(a.get("finished_at") or a["started_at"]),
                              "factory", "factory", {"status": a["status"], "incident_id": inc["incident_id"],
                                                     "tokens": a["token_usage"]}, [f"attempt:{a['attempt_id']}"],
                              source_kind="incident_ledger", source_ref=a["attempt_id"]))
    return out


def from_supervisor_events(path: Path | None = None) -> list[dict]:
    p = path or state_dir() / "events/factory-events.jsonl"
    out: list[dict] = []
    if not p.is_file():
        return out
    for line in p.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        m = re.match(r"^poll (\d+) (HEALTHY|DEGRADED|UNAVAILABLE|UNKNOWN)", e.get("message", ""))
        if e.get("channel") == "supervisor" and m:
            out.append(ev("supervisor.heartbeat", e["event_id"], _norm_ts(e["ts_utc"]), "factory", "factory",
                          {"status": m.group(2), "poll": int(m.group(1))}, [f"event:{e['event_id']}"],
                          source_kind="factory_event", source_ref=e["event_id"]))
    return out


def collect_all(include_fabro: bool = True) -> list[dict]:
    """Every KPI source event currently derivable (deduplicated, sorted by (ts, id))."""
    evs: list[dict] = []
    root = state_dir() / "workorders"
    for ws in sorted(root.glob("*/workspace")) if root.is_dir() else []:
        prof = ws / ".forge-run/model-profile.json"
        if prof.is_file() and not json.loads(prof.read_text()).get("local_only", True):
            continue  # user-authorized cloud benchmarks are reported separately, never in the production KPIs
        usage, stages = None, None
        rid = ws / ".forge-run/fabro_run_id"
        if include_fabro and rid.is_file():
            try:
                from ..fabro.client import FabroClient, load_token

                c = FabroClient(token=load_token(), timeout=10)
                usage = c.usage(rid.read_text().strip())
                stages = [e for e in c.iter_events(rid.read_text().strip())
                          if e["event"] in ("stage.started", "stage.completed", "stage.failed")]
            except Exception:  # noqa: BLE001 - unavailable usage stays UNKNOWN
                usage, stages = None, None
        evs += from_workspace(ws, fabro_usage=usage, fabro_stage_events=stages)
    evs += from_incidents() + from_supervisor_events()
    return dedup_sort(evs)


def dedup_sort(evs: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for e in evs:
        seen.setdefault(e["event_id"], e)
    return sorted(seen.values(), key=lambda e: (e["ts_utc"], e["event_id"]))


def event_set_digest(evs: list[dict]) -> str:
    h = hashlib.sha256()
    for e in dedup_sort(evs):
        h.update(e["event_id"].encode() + b"\0" + hashlib.sha256(canonical_json(e)).digest())
    return h.hexdigest()


def schema_ok(evs: list[dict]) -> list[str]:
    return [f"{e['event_id']}:{m}" for e in evs for m in validate_event(e)][:20] if evs else []


__all__ = ["collect_all", "dedup_sort", "event_set_digest", "from_workspace", "schema_errors"]
