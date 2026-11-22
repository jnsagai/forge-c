#!/usr/bin/env python3
"""Factory-floor line for forge-c-hi conductor runs (feature 023): read-only, model-free.

Serves /floor.json (schema forge-c/factory-floor/1, the shape the :8788 floor page renders), /supervisor.json and
/health from the conductor's own records in one or more project folders:

    .hi/project.json        stages (halls), role bindings (cell tags)
    .hi/runs/*/events.jsonl one run = one order; role calls, gates, findings, rework, stage outcomes
    .hi/active-role.json    the role at work right now (cleared by the conductor when the role ends)
    hi/<stage>/requirements.json, hi/<stage>/inspection/*.json   counts only (items, open points, findings)

It never writes, never calls a model, and never shows prompt or reply text.

    python3 tools/hi_floor_line.py --port 32412 --project SUP=/path/to/project [--project ...]

The two-line floor relays it as a line with a `url` (FORGE_FLOOR_LINES).
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

STAGE_NAMES = {
    "sys-req": "System requirements", "sys-arch": "System architecture", "sw-req": "Software requirements",
    "sw-arch": "Software architecture", "sw-design": "Detailed design and units", "unit-verif": "Unit verification",
    "sw-integ": "Software integration test", "sw-qual": "Software qualification test",
    "sys-verif": "System verification",
}
MODEL_NAMES = {"sonnet": "Claude Sonnet", "opus": "Claude Opus", "fable": "Claude Fable", "haiku": "Claude Haiku"}
REWORK = ("blocking", "major")
STALE_S = 600  # no role at work and no event for this long: the conductor is gone (between roles it pauses seconds)


def hall_id(stage: str) -> str:
    return stage.upper().replace("-", ".")  # the page's hash navigation maps "#sys-req" to "SYS.REQ"


def _read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def _events(p: Path) -> list[dict]:
    out = []
    try:
        for line in p.read_text().splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e, dict):
                out.append(e)
    except OSError:
        pass
    return out


def _ts(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _hhmm(t: float) -> str:
    return time.strftime("%H:%M", time.gmtime(t))


def model_label(binding: dict) -> str:
    m = binding.get("model")
    if m:
        return MODEL_NAMES.get(m, m)
    fam = binding.get("model_family") or "?"
    return f"{fam} (account default)"


def _findings(root: Path, stage: str, name: str) -> list[dict]:
    d = _read_json(root / "hi" / stage / "inspection" / f"{name}.json", {})
    f = d.get("findings") if isinstance(d, dict) else d
    return [x for x in (f or []) if isinstance(x, dict)]


class Run:
    """One conductor run (= one order on the floor)."""

    def __init__(self, tag: str, root: Path, run_id: str, events: list[dict], active: dict | None, now: float):
        self.tag, self.root, self.run_id, self.ev = tag, root, run_id, events
        self.active = active if active and active.get("run_id") == run_id else None
        self.started = _ts(events[0].get("ts")) if events else None
        self.last = _ts(events[-1].get("ts")) if events else None
        self.ends = {e["stage"]: e for e in events if e.get("step") == "stage-end"}
        self.stages = [e["stage"] for e in events if e.get("step") == "stage-start"]
        finished = any(e.get("step") in ("run-end", "summary") for e in events)
        if self.active:
            self.state = "RUNNING"
        elif any(e.get("outcome") == "BLOCKED" for e in self.ends.values()):
            self.state = "BLOCKED"
        elif finished or (self.stages and all(s in self.ends for s in self.stages) and self.last
                          and now - self.last > 60):
            self.state = "DONE"
        elif self.last and now - self.last > STALE_S:
            self.state = "STOPPED"  # interrupted by the operator or a crash: no outcome was recorded
        else:
            self.state = "RUNNING"  # between two role calls
        self.at = self.stages[-1] if self.stages else None

    def stage_events(self, stage: str) -> list[dict]:
        return [e for e in self.ev if e.get("stage") == stage]

    @property
    def wo(self) -> str:
        return f"HI-{self.tag}-{self.run_id}"


def load_runs(projects: list[tuple[str, Path]], now: float) -> list[Run]:
    runs = []
    for tag, root in projects:
        active = _read_json(root / ".hi" / "active-role.json")
        for f in sorted((root / ".hi" / "runs").glob("*/events.jsonl")):
            ev = _events(f)
            if ev:
                runs.append(Run(tag, root, f.parent.name, ev, active, now))
    runs.sort(key=lambda r: r.started or 0)
    return runs


def _roles(ev: list[dict], role: str, phase: str | None = None) -> list[dict]:
    return [e for e in ev if e.get("step") == "role" and e.get("role") == role
            and (phase is None or e.get("phase") == phase)]


def _phase_now(ev: list[dict]) -> tuple[str, int]:
    """(phase, round) the stage is in: the newest inspection decides (item or set); before one, the newest role."""
    for e in reversed(ev):
        if e.get("step") == "findings":
            return e.get("phase", "item"), int(e.get("round") or 0)
    for e in reversed(ev):
        if e.get("step") == "role":
            return e.get("phase", "create"), int(e.get("round") or 0)
    return "create", 0


def _typical(ev: list[dict], role: str, phase: str) -> float | None:
    d = [e.get("duration_s") for e in _roles(ev, role, phase) if isinstance(e.get("duration_s"), (int, float))]
    return statistics.median(d) if d else None


def _estimate_bar(elapsed: float, typical: float | None, n: int, now: float) -> dict:
    bar = {"kind": "estimate", "elapsed_s": round(elapsed), "typical_s": round(typical) if typical else None,
           "n": n, "pct": None}
    if typical:
        bar["pct"] = min(100, round(elapsed / typical * 100))
        if elapsed < typical:
            bar["eta_at"] = int(now + typical - elapsed)
            bar["eta"] = _hhmm(bar["eta_at"])
        else:
            bar["over"] = True
    return bar


def cells(run: Run | None, stage: str, bindings: dict, now: float) -> list[dict]:
    ev = run.stage_events(stage) if run else []
    root = run.root if run else None
    act = run.active if run and run.active and run.active.get("stage") == stage else None
    phase, rnd = _phase_now(ev)
    end = run.ends.get(stage) if run else None
    authors, inspectors = _roles(ev, "author"), _roles(ev, "inspector")
    gates = [e for e in ev if e.get("step") == "gate"]
    fnd = [e for e in ev if e.get("step") == "findings"]
    a_b, i_b = bindings.get("author", {}), bindings.get("inspector", {})
    wp = _read_json(root / "hi" / stage / "requirements.json", {}) if root else {}
    wp = wp if isinstance(wp, dict) else {}
    ops = [o for o in (wp.get("open_points") or []) if isinstance(o, dict)]
    carried = _findings(root, stage, "findings") if root else []
    waiting = {(f.get("target_id"), f.get("checklist_item")) for f in carried
               if f.get("blocked_by") and f.get("status") in (None, "open", "carried")}
    act_for = (now - _ts(act["set_utc"])) if act and _ts(act.get("set_utc")) else 0

    # Author cell
    a_state, a_job, a_bar = ("done" if end else "waiting" if ev else "idle"), None, None
    if act and act.get("role") == "author":
        a_state = "working" if phase in ("create", "update") or not authors else "rework"
        if phase == "item" and rnd:
            flagged = {f.get("target_id") for f in _findings(root, stage, f"item-r{rnd}")
                       if f.get("severity") in REWORK and not f.get("blocked_by")}
            done = len([e for e in _roles(ev, "author", "rework") if int(e.get("round") or 0) == rnd])
            total = max(len(flagged), done + 1)
            a_bar = {"kind": "measured", "done": done, "total": total, "unit": f"items reworked (round {rnd})",
                     "sub": "one item per call"}
            a_job = f"rework round {rnd} · item {done + 1} of {total}"
        else:
            key = {"set": "rework-set", "item": "rework"}.get(phase, phase)
            a_job = {"rework-set": "set rework: one call for the set findings", "rework": "rework",
                     "create": "writing the work product", "update": "updating after changed inputs",
                     "fix-gates": "fixing gate issues"}.get(key, key)
            a_bar = _estimate_bar(act_for, _typical(ev, "author", key), len(_roles(ev, "author", key)), now)
    a_hours = sum(e.get("duration_s") or 0 for e in authors) / 3600
    author = {
        "id": "author", "name": "Author cell", "tag": f"{model_label(a_b)} · {a_b.get('harness', '?')}",
        "state": a_state, "job": a_job, "bar": a_bar or {"kind": "idle"}, "progress": None, "speed": None,
        "what": "Writes the work product from the inputs, then reworks each flagged item on its own.",
        "counters": [["calls", len(authors)], ["items", len(wp.get("items") or [])],
                     ["model hours", round(a_hours, 1)]],
    }

    # Gate cell (deterministic)
    g = gates[-1] if gates else None
    gate = {
        "id": "gate", "name": "Gate cell", "tag": "deterministic · no model",
        "state": "done" if g and g.get("verdict") == "PASS" else "rework" if g else "idle", "job": None,
        "bar": {"kind": "tools", "round": len(gates),
                "steps": [{"label": k, "status": "passed" if v == "PASS" else "failed" if v == "FAIL" else "pending"}
                          for k, v in sorted((g or {}).get("gates", {}).items())]} if g else {"kind": "idle"},
        "what": "Schema, wording rules, trace links, write scope and independence: checked by code after every write.",
        "counters": [["runs", len(gates)], ["failed", sum(1 for x in gates if x.get("verdict") != "PASS")]],
    }

    # Inspection cell
    i_state, i_job, i_bar = ("done" if end else "waiting" if ev else "idle"), None, None
    if act and act.get("role") == "inspector":
        i_state = "working"
        nxt_phase = "set" if any(e.get("step") == "rework-limit" for e in ev) and phase == "item" else phase
        nxt_phase = nxt_phase if nxt_phase in ("item", "set") else "item"
        i_job = f"{nxt_phase} inspection"
        i_bar = _estimate_bar(act_for, _typical(ev, "inspector", nxt_phase), len(_roles(ev, "inspector", nxt_phase)), now)
    inspector = {
        "id": "inspector", "name": "Inspection cell", "tag": f"{model_label(i_b)} · {i_b.get('harness', '?')} · read-only",
        "state": i_state, "job": i_job, "bar": i_bar or {"kind": "idle"}, "progress": None, "speed": None,
        "what": "Independent model family judges each item, then the whole set, against the checklists.",
        "counters": [["calls", len(inspectors)], ["findings raised", sum(int(e.get("findings") or 0) for e in fnd)],
                     ["model hours", round(sum(e.get("duration_s") or 0 for e in inspectors) / 3600, 1)]],
    }

    # Rework router
    reworks = _roles(ev, "author", "rework") + _roles(ev, "author", "rework-set")
    lim = [e for e in ev if e.get("step") == "rework-limit"]
    last_f = fnd[-1] if fnd else None
    router = {
        "id": "router", "name": "Rework router", "tag": "deterministic",
        "state": "stopped" if end and end.get("outcome") == "BLOCKED" else "done" if end else "waiting" if fnd else "idle",
        "job": None,
        "bar": {"kind": "step", "step": "stopped" if end and end.get("outcome") == "BLOCKED" else "passed" if end
                else "rework" if last_f and last_f.get("findings") else "passed",
                "decision": (end or {}).get("outcome") or (f"{last_f.get('findings')} findings, {last_f.get('phase')} "
                                                           f"round {last_f.get('round')}" if last_f else None)}
        if (end or last_f) else {"kind": "idle"},
        "why": (end or {}).get("reason"),
        "what": "Sends each flagged item back alone; after the rework limit the findings are carried, not hidden.",
        "counters": [["reworks granted", len(reworks)], ["carried at limit", len(lim[-1].get("flagged") or []) if lim else 0],
                     ["waiting on a decision", len(waiting)]],
    }

    # Decision desk: open points only a person can close
    blocking = [o for o in ops if o.get("blocks") or o.get("blocking")]
    desk = {
        "id": "desk", "name": "Decision desk", "tag": "product owner · human",
        "state": "waiting" if blocking else "done" if ev else "idle", "job": None,
        "bar": {"kind": "waiting", "for": "product-owner decisions" if blocking else None} if ev else {"kind": "idle"},
        "what": "Values the inputs do not give become open points; the package never guesses them.",
        "counters": [["open points", len(ops)], ["blocking", len(blocking)]],
    }
    return [author, gate, inspector, router, desk]


def floor(projects: list[tuple[str, Path]], now: float | None = None) -> dict:
    now = time.time() if now is None else now
    runs = load_runs(projects, now)
    cfg = {}
    for tag, root in projects:
        cfg[tag] = _read_json(root / ".hi" / "project.json", {}) or {}
    stage_order: list[str] = []
    for c in cfg.values():
        for s in c.get("stages") or []:
            if s not in stage_order:
                stage_order.append(s)
    for r in runs:
        for s in r.stages:
            if s not in stage_order:
                stage_order.append(s)
    live = [r for r in runs if r.state == "RUNNING"]
    halls = []
    fpy = {}
    for s in stage_order:
        entered = [r for r in runs if s in r.stages]
        passed = [r for r in entered if (r.ends.get(s) or {}).get("outcome", "").startswith("ACCEPTED")]
        inspected, first = 0, 0
        for r in entered:
            f1 = [e for e in r.stage_events(s) if e.get("step") == "findings" and e.get("phase") == "item"
                  and int(e.get("round") or 0) == 1]
            if f1:
                inspected += 1
                if not _findings(r.root, s, "item-r1") or not any(
                        f.get("severity") in REWORK for f in _findings(r.root, s, "item-r1")):
                    first += 1
        cyc = [(_ts(r.ends[s]["ts"]) - _ts(r.stage_events(s)[0]["ts"])) / 60 for r in passed
               if _ts(r.ends[s].get("ts")) and _ts(r.stage_events(s)[0].get("ts"))]
        running = [r for r in live if r.at == s]
        shown = running[-1] if running else (entered[-1] if entered else None)
        bindings = (cfg.get(shown.tag) if shown else next(iter(cfg.values()), {})) or {}
        fpy[hall_id(s)] = [first, inspected]
        halls.append({
            "id": hall_id(s), "name": STAGE_NAMES.get(s, s), "state": "working" if running else
            "history" if entered else "idle",
            "entered": len(entered), "passed": len(passed), "inspected": inspected, "first_pass": first,
            "reworks": sum(len(_roles(r.stage_events(s), "author", "rework"))
                           + len(_roles(r.stage_events(s), "author", "rework-set")) for r in entered),
            "stopped": sum(1 for r in entered if (r.ends.get(s) or {}).get("outcome") == "BLOCKED"
                           or (r.state == "STOPPED" and r.at == s)),
            "cycle_min": round(statistics.mean(cyc)) if cyc else None,
            "running": [r.wo for r in running],
            "cells": cells(shown, s, bindings.get("roles") or {}, now) if shown else [],
            "note": None if shown else "No run has reached this stage yet.",
        })
    orders = []
    for r in runs:
        route = {}
        for s in (cfg.get(r.tag, {}).get("stages") or r.stages):
            o = (r.ends.get(s) or {}).get("outcome")
            route[hall_id(s)] = ("ok" if o and o.startswith("ACCEPTED") else "no" if o == "BLOCKED"
                                 else "no" if r.state == "STOPPED" and r.at == s
                                 else "run" if r.state == "RUNNING" and r.at == s else "pending")
        note = ""
        if r.state == "RUNNING" and r.active:
            note = f"{r.active.get('role')} at work in {r.active.get('stage')} since {(r.active.get('set_utc') or '')[11:16]} UTC"
        elif r.state == "BLOCKED":
            b = next(e for e in r.ends.values() if e.get("outcome") == "BLOCKED")
            note = f"BLOCKED in {b.get('stage')}: {b.get('reason', '')}"
        elif r.state == "STOPPED":
            note = f"stopped by the operator in {r.at} (no outcome recorded)"
        elif r.state == "DONE":
            note = ", ".join(f"{s}: {e.get('outcome')}" for s, e in r.ends.items())
        c = cfg.get(r.tag, {})
        orders.append({
            "wo": r.wo, "part": f"{c.get('project_id', r.tag)} · {c.get('profile', '?')} {c.get('integrity_level', '')}",
            "target": hall_id((c.get("stages") or r.stages or ["?"])[-1]), "at": hall_id(r.at) if r.at else None,
            "state": {"BLOCKED": "STOPPED"}.get(r.state, r.state), "note": note, "resumed_from": None, "eta": None,
            "route": route,
        })
    roles = next((c.get("roles") for c in (cfg.get(live[-1].tag) if live else None, *cfg.values()) if c and c.get("roles")), {})
    hours = sum(e.get("duration_s") or 0 for r in runs for e in r.ev if e.get("step") == "role") / 3600
    day = time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(now))
    return {
        "schema": "forge-c/factory-floor/1", "updated_at": _iso(now),
        "supervisor": {"available": False, "reason": "NO_SUPERVISOR_ON_THIS_LINE"},
        "monitor": {"available": False, "reason": "SOURCE_MONITOR_NOT_REPORTED"},
        "owner_lane": {"available": False, "reason": "NO_LINE_QUEUE"},
        "cre": {"available": False}, "deployer": {"available": False, "reason": "NO_DEPLOYER_ON_THIS_FLOOR"},
        "shift_start": day,
        "kpis": {
            "on_floor": len(live), "completed": sum(1 for r in runs if r.state == "DONE"), "orders": len(runs),
            "fpy_swe1": next(iter(fpy.values()), [0, 0]), "fpy_by_hall": fpy,
            "reworks": sum(h["reworks"] for h in halls), "stopped": sum(1 for r in runs if r.state in ("BLOCKED", "STOPPED")),
            "model_hours": round(hours, 1), "out_tokens": 0, "line_tok_s": None,
            "station": {"kind": "cloud_api", "available": True, "models": [], "cost_today_usd": 0,
                        "account_models": {role: model_label(b) for role, b in (roles or {}).items()}},
        },
        "halls": halls, "focus": None, "orders": orders,
    }


def make_handler(projects: list[tuple[str, Path]]):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API
            u = urlparse(self.path)
            if u.path == "/floor.json":
                body = floor(projects)
            elif u.path == "/supervisor.json":
                body = {"available": False, "reason": "NO_SUPERVISOR_ON_THIS_LINE"}
            elif u.path == "/health":
                body = {"status": "ok", "projects": [t for t, _ in projects]}
            else:
                self.send_error(404)
                return
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):  # quiet
            pass

    _ = parse_qs  # query parameters (line, order, since) are accepted and ignored
    return Handler


def parse_projects(values: list[str]) -> list[tuple[str, Path]]:
    out = []
    for v in values:
        tag, _, path = v.partition("=")
        if not path or not tag.replace("_", "").isalnum():
            raise SystemExit(f"--project expects TAG=PATH, got {v!r}")
        out.append((tag.upper(), Path(path).resolve()))
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=32412)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--project", action="append", required=True, help="TAG=PATH of a forge-c-hi project")
    ap.add_argument("--once", action="store_true", help="print floor.json once and exit")
    a = ap.parse_args(argv)
    projects = parse_projects(a.project)
    if a.once:
        print(json.dumps(floor(projects), indent=1, ensure_ascii=False))
        return
    ThreadingHTTPServer((a.host, a.port), make_handler(projects)).serve_forever()


if __name__ == "__main__":
    main()
