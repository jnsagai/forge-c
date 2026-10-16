"""CRE-T005..T010 (Monitor + Analyze) — deterministic import of failure observations, classification, fingerprints,
cross-run recurrence. Model-free and read-only on its sources.

Sources per work-order attempt (workspace .forge-run):
  * gate log: author rejections (deterministic gate issues + contract errors; agent-reported issues are kept as
    `AGENT_REPORTED`), route BLOCKED, governor budget stops;
  * inspection records created by THIS attempt (carried-over records of a resumed run are skipped) - one observation
    per failed checklist item;
  * defect register: CODE/ARCHITECTURE/REQUIREMENT defects found downstream (escaped defects) and REJECTED blames;
  * package: final READY/BLOCKED outcome; gaps the owner deferred are recorded with disposition OWNER_DEFERRED.
Supervisor incidents (002 store) become INFRASTRUCTURE observations.

Units (ADR-CRE-005): order_id = the driver order, attempt_id = the work-order run; retries never create orders.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from ..common import REPO_ROOT, sha256_bytes, state_dir
from ..events.redact import redact_text
from ..kpi.sources import order_of
from . import events as E
from .store import CREStore
from .taxonomy import CLASSIFIER_VERSION, classify, fingerprint

FACTORY_MAJOR = "forge-factory-0"
GATE_SCHEMA = "gate-log-0.4"


def _ts_ok(ts: str | None, since: str) -> bool:
    return bool(ts) and ts >= since


def estimated_factory_revision(created_at: str) -> dict:
    """Historical attempts did not record the factory revision: the last commit before launch (ESTIMATED)."""
    try:
        c = subprocess.run(["git", "rev-list", "-1", f"--before={created_at}", "--all"], cwd=REPO_ROOT,
                           capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        c = ""
    return {"commit": c or "UNKNOWN", "basis": "ESTIMATED_LAST_COMMIT_BEFORE_LAUNCH"}


def attempt_context(ws: Path) -> dict | None:
    m_path = ws / ".forge-run/manifest.json"
    try:
        m = json.loads(m_path.read_text())
    except (OSError, ValueError):
        return None
    try:
        prof = json.loads((ws / ".forge-run/model-profile.json").read_text())
    except (OSError, ValueError):
        prof = {}
    attempt = m.get("work_order") or ws.parent.name
    rev = m.get("factory_revision") or estimated_factory_revision(m.get("created_at", ""))
    target = m.get("target") or {}
    driver = re.sub(r"[^A-Z0-9]+", "_", str(m.get("driver", "UNKNOWN")).upper()).strip("_")[:40]
    model = prof.get("default") or "qwen3:8b"
    cohort = {"driver_class": driver, "target": str(target.get("core", "UNKNOWN")),
              "model": model, "code_model": (prof.get("code_nodes") or {}).get("model") if isinstance(
                  prof.get("code_nodes"), dict) else (prof.get("code_nodes") or "-"),
              "provider": prof.get("provider") or "ollama",
              "mode": "RESUMED" if m.get("resumed_from") else "FULL"}
    fabro_run = ""
    try:
        fabro_run = (ws / ".forge-run/fabro_run_id").read_text().strip()
    except OSError:
        pass
    return {"attempt_id": attempt, "order_id": order_of(attempt, m), "created_at": m.get("created_at", ""),
            "factory_revision": rev, "cohort": cohort, "cohort_key": "|".join(f"{k}={v}" for k, v in cohort.items()),
            "run_id": fabro_run or None,
            "deferred_safety": str(target.get("safety_allocation", "")).startswith("OUT_OF_SCOPE")}


def _obs(ctx: dict, *, raw: str, component: str, phase: str | None, step: str, ts: str, outcome: str,
         source_ref: str, line: bytes, source_kind: str, disposition: str = "ACTIVE") -> dict:
    c = classify(raw)
    operation = f"{phase or '-'}/{step}"
    fp = fingerprint(c.failure_class, component, c.error_code, operation, FACTORY_MAJOR, GATE_SCHEMA)
    # the classification is part of the identity: a rule change yields a new record and retracts the old one
    key = f"{ctx['attempt_id']}|{source_ref}|{sha256_bytes(str(raw).encode())}|{c.failure_class}|{c.error_code}"
    return {"obs_id": E.event_id("cre.failure_observed", key), "obs_key": key, "fingerprint": fp,
            "failure_class": c.failure_class,
            "category": c.category, "component": component, "error_code": c.error_code, "operation": operation,
            "order_id": ctx["order_id"], "attempt_id": ctx["attempt_id"], "run_id": ctx["run_id"], "phase": phase,
            "ts_utc": ts, "disposition": disposition, "outcome": outcome, "cohort": ctx["cohort_key"],
            "factory_version": (ctx["factory_revision"].get("commit") or "UNKNOWN")[:12],
            "source_ref": source_ref, "evidence_sha256": sha256_bytes(line),
            "excerpt": redact_text(str(raw))[0][:200], "route": c.route, "rule": c.rule, "source_kind": source_kind,
            "factory_revision_basis": ctx["factory_revision"].get("basis", "UNKNOWN")}


def from_workspace(ws: Path) -> list[dict]:
    ctx = attempt_context(ws)
    if ctx is None:
        return []
    since, out = ctx["created_at"], []
    rel = f"workorders/{ctx['attempt_id']}/workspace"
    log = ws / ".forge-run/gates/gate-log.jsonl"
    for n, raw_line in enumerate(log.read_bytes().splitlines() if log.is_file() else [], 1):
        try:
            r = json.loads(raw_line)
        except ValueError:
            continue
        ts, phase, step = r.get("ts", ""), r.get("phase"), r.get("step")
        if not _ts_ok(ts, since):
            continue
        g = r.get("gate") or {}
        res = g.get("decision") or r.get("result") or r.get("status")
        src = f"{rel}/.forge-run/gates/gate-log.jsonl#{n}"
        if step == "author" and res in ("REJECTED", "FREEZE_FAILED"):
            deterministic = r.get("status") == "INCOMPLETE" or res == "FREEZE_FAILED"
            items = [(i, "GATE") for i in (r.get("errors") or [])] + ([(r["error"], "GATE")] if r.get("error") else [])
            items += [(i, "GATE" if deterministic else "AGENT_REPORTED") for i in (r.get("issues") or [])]
            seen: set[str] = set()  # the gate echoes contract errors into `issues`: one observation, GATE wins
            for raw, kind in items:
                if str(raw) in seen:
                    continue
                seen.add(str(raw))
                out.append(_obs(ctx, raw=str(raw), component="gate", phase=phase, step="author", ts=ts,
                                outcome="REWORK", source_ref=src, line=raw_line, source_kind=kind))
        elif step == "route" and res == "BLOCKED":
            out.append(_obs(ctx, raw=f"REWORK_BUDGET_EXHAUSTED {g.get('reason', '')}", component="gate", phase=phase,
                            step="route", ts=ts, outcome="BLOCKED", source_ref=src, line=raw_line, source_kind="GATE"))
        elif step == "governor" and res:
            out.append(_obs(ctx, raw=str(res), component="governor", phase=phase, step="governor", ts=ts,
                            outcome="BLOCKED", source_ref=src, line=raw_line, source_kind="GATE"))
    for ins in sorted((ws / "inspection").glob("SWE.*/INS-*.json")):
        try:
            d = json.loads(ins.read_bytes())
        except ValueError:
            continue
        if not _ts_ok(d.get("recorded_at"), since) or d.get("verdict") == "PASS":
            continue  # carried over from a resumed source run, or passing
        for item, v in sorted((d.get("items") or {}).items()):
            if (v or {}).get("verdict") == "FAIL":
                out.append(_obs(ctx, raw=f"INSPECTION_FAIL:{item}", component="inspection", phase=d.get("phase"),
                                step="inspect", ts=d["recorded_at"], outcome="REWORK",
                                source_ref=f"{rel}/{ins.relative_to(ws).as_posix()}#{item}",
                                line=json.dumps(v, sort_keys=True).encode(), source_kind=(v or {}).get("source", "INSPECTOR")
                                if (v or {}).get("source") == "deterministic" else "INSPECTOR"))
    for f in sorted((ws / ".forge-run/defects").glob("DEF-*.json")):
        try:
            d = json.loads(f.read_bytes())
        except ValueError:
            continue
        first = (d.get("history") or [{}])[0]
        if d.get("kind") not in ("CODE", "ARCHITECTURE", "REQUIREMENT") or not _ts_ok(first.get("ts"), since):
            continue
        raw = f"DEFECT_REJECTED:{d['kind']}" if d.get("status") == "REJECTED" else f"DEFECT:{d['kind']}"
        out.append(_obs(ctx, raw=raw, component="defect-register", phase=d.get("target_phase"),
                        step=f"detected-{d.get('detected_phase')}", ts=first["ts"], outcome="UPSTREAM",
                        source_ref=f"{rel}/.forge-run/defects/{f.name}", line=f.read_bytes(), source_kind="GATE"))
    pkg = ws / ".forge-run/package.json"
    if pkg.is_file():
        p = json.loads(pkg.read_bytes())
        gaps = p.get("gaps") or []
        deferred = [g for g in gaps if ctx["deferred_safety"] and re.match(r"missing_or_empty_file:safety/", g)]
        ts = p.get("finalized_at") or since
        src = f"{rel}/.forge-run/package.json"
        stopped = any(o["outcome"] == "BLOCKED" for o in out)  # a blocked phase/budget stop ends the run by design
        if "run_not_completed:INCOMPLETE" in gaps and not stopped:  # otherwise: orchestration (killed/aborted run)
            out.append(_obs(ctx, raw="PACKAGE_GAP:run_not_completed", component="fabro", phase=None, step="run",
                            ts=ts, outcome="BLOCKED", source_ref=src + "#run_not_completed", line=pkg.read_bytes(),
                            source_kind="GATE"))
        status = p.get("package_status", "UNKNOWN")
        only_deferred = status == "BLOCKED" and gaps and set(gaps) == set(deferred)
        for g in deferred:
            out.append(_obs(ctx, raw="PACKAGE_GAP:owner_deferred_document", component="release", phase=None,
                            step="package", ts=ts, outcome="INFO", source_ref=f"{src}#{g}", line=g.encode(),
                            source_kind="GATE", disposition="OWNER_DEFERRED"))
        if status == "BLOCKED" and not only_deferred:
            out.append(_obs(ctx, raw="PACKAGE_GAP:package_blocked", component="release", phase=None, step="package",
                            ts=ts, outcome="BLOCKED", source_ref=src + "#status", line=pkg.read_bytes(),
                            source_kind="GATE"))
    return out


def attempt_exposures(workspaces: list[Path] | None = None) -> list[dict]:
    """Which operations (phase/step) each attempt exercised, with its factory revision: the exposure base for CAPA
    effectiveness (an attempt that never reached a phase is not evidence that a fix there works)."""
    wss = workspaces if workspaces is not None else sorted((state_dir() / "workorders").glob("*/workspace"))
    out = []
    for ws in wss:
        ctx = attempt_context(ws)
        if ctx is None:
            continue
        ops = set()
        log = ws / ".forge-run/gates/gate-log.jsonl"
        for raw in log.read_text().splitlines() if log.is_file() else []:
            try:
                r = json.loads(raw)
            except ValueError:
                continue
            if _ts_ok(r.get("ts"), ctx["created_at"]) and r.get("phase") and r.get("step"):
                ops.add(f"{r['phase']}/{r['step']}")
        out.append({"attempt_id": ctx["attempt_id"], "started": ctx["created_at"],
                    "revision": ctx["factory_revision"].get("commit", "UNKNOWN"),
                    "revision_basis": ctx["factory_revision"].get("basis", "UNKNOWN"), "operations": sorted(ops),
                    "cohort": ctx["cohort_key"]})
    return sorted(out, key=lambda x: x["started"])


def from_incidents(path: Path | None = None) -> list[dict]:
    """002 supervisor incidents -> INFRASTRUCTURE observations (the incident itself stays the 002 record)."""
    from ..supervisor.store import IncidentStore

    p = path or state_dir() / "supervisor" / "incidents.sqlite3"
    if not p.is_file():
        return []
    st = IncidentStore(p)
    out = []
    for inc in st.all():
        ctx = {"attempt_id": inc.get("run_id") or "supervisor", "order_id": None, "run_id": inc.get("run_id"),
               "cohort_key": "supervisor|component=" + inc["component"], "created_at": inc["created_at"],
               "factory_revision": {"commit": "UNKNOWN", "basis": "NOT_RECORDED"}}
        o = _obs(ctx, raw=f"{inc['fault_type']} {inc.get('last_error') or ''}", component=f"supervisor:{inc['component']}",
                 phase=None, step="probe", ts=inc["created_at"], outcome=inc["state"],
                 source_ref=f"incidents.sqlite3#{inc['incident_id']}", line=json.dumps(inc, sort_keys=True).encode(),
                 source_kind="SUPERVISOR")
        o["incident_id"] = inc["incident_id"]
        out.append(o)
    return out


def ingest(store: CREStore, policy_sha256: str, workspaces: list[Path] | None = None, incidents: bool = True,
           mirror: bool = True) -> dict:
    """Record observations (idempotent) and their typed events; returns counts of new vs already-known records."""
    wss = workspaces if workspaces is not None else sorted((state_dir() / "workorders").glob("*/workspace"))
    obs = [o for ws in wss for o in from_workspace(ws)] + (from_incidents() if incidents else [])
    new = 0
    current = {o["obs_id"] for o in obs}
    scanned = {c["attempt_id"] for c in (attempt_context(ws) for ws in wss) if c}
    retracted = 0
    for o in store.observations():  # rule changes: observations the current importer no longer produces
        from_supervisor = str(o["component"]).startswith("supervisor:")
        rescanned = incidents if from_supervisor else o["attempt_id"] in scanned
        if rescanned and o["obs_id"] not in current:
            retracted += store.retract_observation(o["obs_id"], f"superseded by {CLASSIFIER_VERSION}: not produced "
                                                   "by the current importer", CLASSIFIER_VERSION)
    for o in sorted(obs, key=lambda x: (x["ts_utc"], x["obs_id"])):
        payload = {k: o[k] for k in ("failure_class", "category", "error_code", "operation", "component", "outcome",
                                     "disposition", "cohort", "route", "excerpt", "source_kind", "factory_version",
                                     "factory_revision_basis")}
        ev = E.build("cre.failure_observed", o["obs_key"], payload,
                     policy_sha256=policy_sha256, correlation_id=o["attempt_id"] or "cre", ts_utc=o["ts_utc"],
                     evidence_refs=[o["source_ref"]], evidence_sha256=o["evidence_sha256"],
                     data_status="OBSERVED", run_id=o.get("run_id"), work_order=o["attempt_id"],
                     order_id=o["order_id"], incident_id=o.get("incident_id"), fingerprint=o["fingerprint"],
                     phase=o["phase"],
                     source_type="AGENT_HYPOTHESIS" if o["source_kind"] == "AGENT_REPORTED" else "DETERMINISTIC_TOOL")
        if store.insert_observation(o):
            new += 1
            E.record(store, ev, mirror=mirror)
    return {"observations": len(obs), "new": new, "attempts": len(wss), "retracted": retracted}


def reduce(store: CREStore) -> list[dict]:
    """Pure projection: failure modes from the append-only observations (replay-equal by construction)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for o in store.observations():
        groups[o["fingerprint"]].append(o)
    rows = []
    for fp, os_ in sorted(groups.items()):
        active = [o for o in os_ if o["disposition"] == "ACTIVE"]
        attempts = {o["attempt_id"] for o in active}
        orders = {o["order_id"] for o in active if o["order_id"]}
        first = os_[0]
        rows.append({"fingerprint": fp, "failure_class": first["failure_class"], "category": first["category"],
                     "component": first["component"], "error_code": first["error_code"],
                     "operation": first["operation"], "first_seen": min(o["ts_utc"] for o in os_),
                     "last_seen": max(o["ts_utc"] for o in os_), "occurrences": len(active),
                     "distinct_attempts": len(attempts), "distinct_orders": len(orders),
                     "recurring": int(len(attempts) >= 2),
                     "significant": int(len(attempts) >= 2 or any(o["outcome"] == "BLOCKED" for o in active)),
                     "data_quality": "OBSERVED" if active else "OWNER_DEFERRED_ONLY"})
    store.replace_failure_modes(rows)
    return store.failure_modes()


def main(argv: list[str] | None = None) -> int:
    from .policy import load

    pol = load()
    store = CREStore()
    stats = ingest(store, pol.sha256)
    modes = reduce(store)
    rec = [m for m in modes if m["recurring"]]
    print(f"CRE ingest: {stats}; failure modes {len(modes)}, recurring {len(rec)}, significant "
          f"{sum(m['significant'] for m in modes)}")
    for m in rec[:15]:
        print(f"  {m['distinct_attempts']:3d} attempts {m['occurrences']:4d} obs  {m['failure_class'][:15]:15s} "
              f"{m['operation']:22s} {m['error_code'][:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
