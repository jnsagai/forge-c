"""Live floor (CR-T005, CR-T012, CR-T013; research R1-R3): work orders at their stations with an andon status.

Sources, all read-only: the work-order manifest, the append-only gate log (.forge-run/gates/gate-log.jsonl, read
incrementally), the finalized package record (.forge-run/package.json), the model profile, and the Fabro run of
units still in progress (lifecycle, current node and newest event time, read incrementally by event sequence).

Andon rules (R2), per unit, on the deterministic gate decisions only:
  BLOCKED  last decision of the current station is route BLOCKED / inspect BLOCKED / governor TOKEN_BUDGET_EXHAUSTED
  REWORK   last decision is route REWORK|UPSTREAM|REINSPECT or author REJECTED
  RUNNING  the unit is in progress and none of the above
  READY / BLOCKED at SHIPPING  from the sealed package record;  STOPPED  run ended without a package
A station shows the worst status of its current units (BLOCKED > REWORK > RUNNING), IDLE without units.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..common import state_dir
from ..inspection.engine import PHASES

SCHEMA = "forge-c/control-room-floor/0.1"
STATIONS = [*PHASES, "SHIPPING"]
BLOCK = {("route", "BLOCKED"), ("inspect", "BLOCKED"), ("governor", "TOKEN_BUDGET_EXHAUSTED")}
REWORK = {("route", "REWORK"), ("route", "UPSTREAM"), ("route", "REINSPECT"), ("author", "REJECTED"),
          ("inspect", "REWORK"), ("inspect", "REINSPECT")}
PASS = {("inspect", "PASS"), ("route", "PASS")}
RANK = {"BLOCKED": 3, "STOPPED": 3, "REWORK": 2, "RUNNING": 1}
RECENT_S = 24 * 3600
FINISHED_LIFECYCLES = {"succeeded", "failed", "cancelled", "canceled", "aborted"}


def _now() -> float:
    return time.time()


def _iso(t: float | None) -> str | None:
    return None if t is None else datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def decision(row: dict) -> tuple[str | None, str | None]:
    return row.get("step"), row.get("result") or (row.get("gate") or {}).get("decision")


WITH_OBJECT = {"REQUIRED_TOOL_NOT_PASS", "MISSING_REQUIRED_OUTPUT", "MISSING_REQUIRED_OUTPUTS"}


def code(issue: str) -> str:
    """Issue text -> loss code (Pareto/reason normalisation), dropping instance details:
    'CONTRACT_SWR_NOT_COVERED:SWR-005 (...)' -> 'CONTRACT_SWR_NOT_COVERED';
    'CODE:DOXYGEN_WARNING:file.h:14: ...' -> 'CODE:DOXYGEN_WARNING' (category + code);
    'REQUIRED_TOOL_NOT_PASS:run_unit:FAIL' -> 'REQUIRED_TOOL_NOT_PASS:run_unit' (the tool or output named)."""
    parts = str(issue).split(":")
    head = parts[0].split(" ", 1)[0]
    out = [head]
    if head in WITH_OBJECT and len(parts) > 1:
        out.append(parts[1].strip().split(" ", 1)[0].rsplit("/", 1)[-1])
    elif len(parts) > 1 and re.fullmatch(r"[A-Z][A-Z0-9_]+", parts[1].strip()):
        out.append(parts[1].strip())
    return ":".join(out)[:120]


def reason_of(row: dict) -> str | None:
    step, dec = decision(row)
    g = row.get("gate") or {}
    issues = row.get("issues") or row.get("errors") or []
    if g.get("reason"):
        text = str(g["reason"])
    elif issues:
        text = f"{step} {dec}: {code(issues[0])}"
    else:
        text = f"{step} {dec}" if dec else None
    return text[:300] if text else None


# ---------------------------------------------------------------------------------------------------- gate logs
@dataclass
class _Tail:
    size: int = 0
    mtime: float = 0.0
    offset: int = 0
    rows: list = field(default_factory=list)


class GateLogReader:
    """Incremental, de-duplicated reader of append-only gate logs (CR-T005). Re-reads from 0 if a file shrank."""

    def __init__(self) -> None:
        self._t: dict[Path, _Tail] = {}
        self._lock = threading.Lock()

    def rows(self, path: Path) -> list[dict]:
        try:
            st = path.stat()
        except OSError:
            return []
        with self._lock:
            t = self._t.get(path)
            if t is None or st.st_size < t.size:
                t = self._t[path] = _Tail()
            if st.st_size != t.size or st.st_mtime != t.mtime:
                with path.open("rb") as f:
                    f.seek(t.offset)
                    chunk = f.read(st.st_size - t.offset)
                end = chunk.rfind(b"\n") + 1  # a partial last line waits for its newline
                for raw in chunk[:end].splitlines():
                    try:
                        r = json.loads(raw)
                    except ValueError:
                        r = {"step": "unparseable"}
                    t.rows.append({**(r if isinstance(r, dict) else {"step": "unparseable"}), "_line": len(t.rows) + 1})
                t.offset += end
                # fully consumed: remember size/mtime; a pending partial line forces a re-check next time
                t.size, t.mtime = (st.st_size, st.st_mtime) if t.offset == st.st_size else (-1, -1.0)
            return list(t.rows)


# ---------------------------------------------------------------------------------------------------- Fabro runs
class RunProbe:
    """Lifecycle, current node and newest event time of in-progress runs; events are read incrementally."""

    def __init__(self, cache_s: float = 1.0) -> None:
        self.cache_s = cache_s
        self._c: dict[str, dict] = {}

    def status(self, ws: Path, run_id: str) -> dict:
        c = self._c.setdefault(run_id, {"seq": 0, "node": None, "last_ts": None, "lifecycle": "unknown", "t": 0.0,
                                        "open": {}})
        if _now() - c["t"] < self.cache_s and c["lifecycle"] != "unknown":
            return c
        try:
            from ..fabro.client import client_for_workspace

            cl = client_for_workspace(ws, timeout=3)
            run = cl.get_run(run_id)
            c["lifecycle"] = (((run.get("lifecycle") or {}).get("status") or {}).get("kind")) or "unknown"
            for e in cl.events(run_id, since_seq=c["seq"], limit=500):
                c["seq"] = max(c["seq"], int(e.get("seq") or 0))
                c["last_ts"] = e.get("ts") or c["last_ts"]
                if e.get("event") == "stage.started":
                    c["open"][e.get("node_id")] = e.get("ts")
                elif e.get("event") in ("stage.completed", "stage.failed"):
                    c["open"].pop(e.get("node_id"), None)
            c["node"] = max(c["open"], key=lambda k: c["open"][k] or "") if c["open"] else None
            c["error"] = None
        except Exception as exc:  # noqa: BLE001 - an unreachable run engine is shown, never guessed
            c["error"] = f"run engine unavailable: {type(exc).__name__}"
        c["t"] = _now()
        return c


# ---------------------------------------------------------------------------------------------------- units
def _json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _models(prof: dict | None) -> dict:
    p = prof or {}
    run_model = {"model": p.get("default"), "provider": p.get("provider")}
    a, i = p.get("acp_authors") or {}, p.get("acp_inspectors") or {}
    return {"authors": {"model": a.get("model"), "provider": a.get("provider")} if a else run_model,
            "inspectors": {"model": i.get("model"), "provider": i.get("provider")} if i else run_model}


def unit(ws: Path, rows: list[dict], now: float, run: dict | None) -> dict:
    """One production unit (data-model.md) from its records."""
    from ..kpi.sources import order_of

    wo = ws.parent.name
    man = _json(ws / ".forge-run/manifest.json") or {}
    pkg = _json(ws / ".forge-run/package.json")
    gl = f"{wo}/.forge-run/gates/gate-log.jsonl"
    by_phase: dict[str, list[dict]] = {p: [r for r in rows if r.get("phase") == p] for p in PHASES}
    passed = {p for p in PHASES if any(decision(r) in PASS for r in by_phase[p])}
    first_pass: dict[str, str | None] = {}
    for p in PHASES:
        ins = [r for r in by_phase[p] if r.get("step") == "inspect"]
        first_pass[p] = None if not ins else ("PASS" if decision(ins[0])[1] == "PASS" else "FAIL")
    rework = {p: sum(1 for r in by_phase[p] if r.get("step") == "route" and decision(r)[1] in
                     ("REWORK", "UPSTREAM", "REINSPECT")) for p in PHASES}
    started = [p for p in PHASES if by_phase[p]]
    last_started = started[-1] if started else None
    # current station: the first phase not passed up to the last phase with records (carried-over phases of a
    # resumed order have no rows but are behind the furthest phase => done); after a pass, the next phase
    station = PHASES[0]
    if last_started:
        if last_started in passed:
            nxt = PHASES.index(last_started) + 1
            station = PHASES[nxt] if nxt < len(PHASES) else "SHIPPING"
        else:
            station = last_started
    cur_rows = by_phase.get(station, []) if station in by_phase else []
    last = cur_rows[-1] if cur_rows else (rows[-1] if rows else None)
    status, reason, ev_rows = "RUNNING", None, cur_rows[-1:]
    blocked_rows = [r for r in rows if decision(r) in BLOCK]
    if pkg and pkg.get("package_status") in ("READY_FOR_OFFLINE_REVIEW", "READY", "BLOCKED"):
        station = "SHIPPING"
        status = "BLOCKED" if pkg["package_status"] == "BLOCKED" else "READY"
        if status == "BLOCKED" and blocked_rows:
            reason = f"{blocked_rows[-1].get('phase')}: {reason_of(blocked_rows[-1])}"
            ev_rows = blocked_rows[-1:]
        elif status == "BLOCKED":
            reason = f"package BLOCKED ({pkg.get('gap_count', 0)} gaps)"
    elif last is not None and decision(last) in BLOCK:
        status, reason, ev_rows = "BLOCKED", reason_of(last), [last]
    elif last is not None and decision(last) in REWORK:
        status, reason, ev_rows = "REWORK", reason_of(last), [last]
    life = (run or {}).get("lifecycle", "unknown")
    if not pkg and life in FINISHED_LIFECYCLES:
        status, reason = "STOPPED", f"run {life}, no package"
    admitted = _ts(man.get("created_at"))
    done_t = _ts((pkg or {}).get("finalized_at"))
    st_rows = by_phase.get(station) or []
    since = _ts(st_rows[0].get("ts")) if st_rows else (done_t if station == "SHIPPING" else None)
    if since is None and station != "SHIPPING":
        prev = [r for r in rows if r.get("phase") in PHASES[:max(PHASES.index(station), 0)]]
        since = _ts(prev[-1].get("ts")) if prev else admitted
    return {"work_order": wo, "order_id": order_of(wo, man),
            "class": {"layer": man.get("layer"), "driver": man.get("driver"),
                      "target_mcu": (man.get("target") or {}).get("part_number")},
            "admitted_at": man.get("created_at") or "", "station": station, "status": status,
            "station_since": _iso(since), "elapsed_s": max(0.0, round((done_t or now) - (admitted or now), 1)),
            "rework_cycles": rework, "first_pass": first_pass,
            "package": None if not pkg else {k: pkg.get(k) for k in ("package_status", "finalized_at",
                                                                      "archive_sha256", "gap_count")},
            "run": {"fabro_run_id": (run or {}).get("run_id"), "lifecycle": life, "current_node": (run or {}).get("node"),
                    "error": (run or {}).get("error")},
            "models": _models(_json(ws / ".forge-run/model-profile.json")), "reason": reason,
            "_evidence": [f"{gl}#L{r['_line']}" for r in ev_rows if "_line" in r],
            "_blocked_at": blocked_rows[-1].get("phase") if (status == "BLOCKED" and blocked_rows) else None,
            "_finished_t": done_t, "_last_t": max([t for t in [_ts(r.get("ts")) for r in rows[-1:]] if t] or [0.0])}


# ---------------------------------------------------------------------------------------------------- snapshot
class Floor:
    def __init__(self, root: Path | None = None, probe: RunProbe | None = None) -> None:
        self.root = root
        self.reader = GateLogReader()
        self.probe = probe or RunProbe()

    def _workspaces(self) -> list[Path]:
        root = self.root or state_dir() / "workorders"
        return sorted(root.glob("*/workspace")) if root.is_dir() else []

    def snapshot(self, cfg: dict, now: float | None = None, violations_open: int = 0) -> dict:
        now = _now() if now is None else now
        units, newest = [], []
        for ws in self._workspaces():
            gl = ws / ".forge-run/gates/gate-log.jsonl"
            pkg = ws / ".forge-run/package.json"
            try:  # cheap skip of old finished or abandoned orders before any parsing
                last_touch = max(p.stat().st_mtime for p in (gl, pkg, ws / ".forge-run/manifest.json") if p.exists())
            except ValueError:
                continue
            if now - last_touch > RECENT_S:
                continue
            run = None
            rid_f = ws / ".forge-run/fabro_run_id"
            if rid_f.is_file() and not pkg.exists():
                rid = rid_f.read_text().strip()
                run = {**self.probe.status(ws, rid), "run_id": rid}
                if run.get("last_ts"):
                    newest.append(_ts(run["last_ts"]) or 0.0)
            u = unit(ws, self.reader.rows(gl), now, run)
            newest.append(last_touch)
            units.append(u)
        stations = []
        for s in STATIONS:
            here = [u for u in units if u["station"] == s and u["status"] in ("RUNNING", "REWORK", "BLOCKED", "STOPPED")
                    and not (s == "SHIPPING" and u["package"])]
            worst = max(here, key=lambda u: (RANK[u["status"]], -(_ts(u["station_since"]) or now)), default=None)
            andon = "IDLE" if worst is None else ("BLOCKED" if worst["status"] in ("BLOCKED", "STOPPED")
                                                  else worst["status"])
            waits = [now - t for t in (_ts(u["station_since"]) for u in here) if t is not None]
            recent = [u for u in units if u.get("_blocked_at") == s or (s == "SHIPPING" and u["package"])]
            stations.append({"station_id": s, "andon": andon, "units": [u["work_order"] for u in here],
                             "oldest_wait_s": round(max(waits), 1) if waits else None,
                             "reason": worst["reason"] if worst and andon in ("BLOCKED", "REWORK") else None,
                             "evidence": worst["_evidence"] if worst else [],
                             "recent": [{"work_order": u["work_order"], "status": u["status"], "reason": u["reason"],
                                         "at": _iso(u["_finished_t"] or u["_last_t"])} for u in recent]})
        live = [u for u in units if not u["package"] and u["status"] != "STOPPED"]
        if violations_open:
            fs = "VIOLATION"
        elif any(u["status"] in ("BLOCKED", "STOPPED") and not u["package"] for u in units):
            fs = "STOPPED"
        elif any(u["status"] == "REWORK" for u in live):
            fs = "ATTENTION"
        elif live:
            fs = "PRODUCING"
        else:
            fs = "NO_WIP"
        age = round(max(0.0, now - max(newest)), 1) if newest else None  # clock skew never gives a negative age
        out_units = [{k: v for k, v in u.items() if not k.startswith("_")} for u in units]
        body = {"stations": stations, "units": out_units, "factory_status": fs, "violations_open": violations_open}
        canon = json.dumps({**body,  # time passing alone (waits, elapsed) is not a floor change
                            "stations": [{k: v for k, v in s.items() if k != "oldest_wait_s"} for s in stations],
                            "units": [{k: v for k, v in u.items() if k != "elapsed_s"} for u in out_units]},
                           sort_keys=True)
        return {"schema": SCHEMA, "generated_at": _iso(now), "data_age_s": age,
                "stale": bool(live) and age is not None and age > cfg["staleness_s"],
                "content_hash": hashlib.sha256(canon.encode()).hexdigest(), **body}


_FLOOR: Floor | None = None


def shared() -> Floor:
    global _FLOOR
    if _FLOOR is None or os.environ.get("FORGE_CONTROLROOM_FRESH"):
        _FLOOR = Floor()
    return _FLOOR
