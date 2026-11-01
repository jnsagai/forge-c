"""Factory floor view of the structured runs (owner 2026-11-01: "lets commit and push it and use it from now on for new
runs"; feature 007 addendum specs/007-kpi-control-room/addendum-factory-floor.md).

Model-free and read-only, like progress_api (whose per-run task progress it reuses). From the work-order records it
derives what a plant manager reads:
  * shift KPIs: orders on the floor, completed / total, first-pass yield, rework cycles, stopped orders, model work;
  * halls (one per SWE process, plus shipping) with an andon state and their KPIs;
  * the cells of each hall (tool changer, author, freeze gate, inspection cell, inspection gate, rework router) with a
    state (working / rework / stopped / waiting / idle), the job, a progress counter, ETA, speed and counters;
  * the orders of the shift with their route and a one-line note.
Every number comes from recorded gate decisions, task packets and visit states; nothing is guessed. Model reasoning is
never read (the packets do not hold it).
"""
from __future__ import annotations

import glob
import json
import os
import time
from pathlib import Path

from .progress_api import STALE_S, _load, _ts, progress, state_root

PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")
HALL_NAMES = {"SWE.1": "Requirements", "SWE.2": "Architecture", "SWE.3": "Detailed design", "SWE.4": "Unit verification",
              "SWE.5": "Integration", "SWE.6": "Qualification", "SHIP": "Shipping"}


def shift_start(now: float, since: float | None = None) -> float:
    """The shift the KPIs count: from `since`, else from 00:00 UTC of the current day."""
    if since is not None:
        return since
    return now - (now % 86400)


def _gate_log(ws: Path) -> list[dict]:
    p = ws / ".forge-run/gates/gate-log.jsonl"
    out = []
    for x in (p.read_text().splitlines() if p.is_file() else []):
        try:
            out.append(json.loads(x))
        except ValueError:
            continue
    return out


def _result(e: dict) -> str | None:
    return e.get("result") or (e.get("gate") or {}).get("decision")


def _calls(ws: Path, phase: str) -> list[dict]:
    out = []
    for p in glob.glob(str(ws / ".forge-run/lrtx" / phase / "packets/*.json")):
        c = _load(Path(p))
        for a in (c or {}).get("attempts") or []:
            u = a.get("usage") or {}
            out.append({"at": c.get("at"), "out": u.get("completion_tokens") or 0, "s": (a.get("wall_ms") or 0) / 1000})
    return out


_FINISHED: dict[str, dict] = {}  # Fabro state of finished runs never changes


def _fabro_token() -> str | None:
    p = os.environ.get("FORGE_FLOOR_FABRO_ENV")  # the stack's server.env; the token never leaves this process
    try:
        for line in Path(p).read_text().splitlines() if p else []:
            if line.startswith("FABRO_DEV_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        return None
    return None


def fabro_stages(run_id: str | None, finished: bool) -> dict | None:
    """Read-only GET of the Fabro run state (stages with node, model, tokens, inference time). None when unavailable."""
    url = os.environ.get("FORGE_FLOOR_FABRO_URL")
    if not url or not run_id:
        return None
    if run_id in _FINISHED:
        return _FINISHED[run_id]
    import urllib.request

    req = urllib.request.Request(f"{url.rstrip('/')}/runs/{run_id}/state", headers={"Accept": "application/json"})
    tok = _fabro_token()
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=4) as r:
            stages = json.load(r).get("stages") or {}
    except Exception:  # noqa: BLE001 - the floor degrades to the recorded files
        return None
    if finished:
        _FINISHED[run_id] = stages
    return stages


def node_cell(node: str) -> str:
    """The floor cell a workflow node belongs to."""
    n = node.split("@")[0]
    if n.endswith("_serve"):
        return "tool"
    if "inspect_gate" in n:
        return "gate"
    if "author_gate" in n or "delivery_check" in n or "freeze" in n:
        return "freeze"
    if "inspector" in n:
        return "inspector"
    if "author" in n:
        return "author"
    return "router"


def native(stages: dict | None, now: float) -> dict:
    """Per phase: model work of the Fabro nodes (output tokens, inference seconds, model-node visits); the node at work."""
    out: dict = {"phases": {}, "node": None}
    for sid, st in (stages or {}).items():
        node = sid.split("@")[0]
        ph = f"SWE.{node[3]}" if node.startswith("swe") and node[3:4].isdigit() else None
        tokens = ((st.get("usage") or {}).get("tokens") or {}).get("output") or 0
        inf_ms = (st.get("timing") or {}).get("inference_time_ms") or st.get("live_inference_ms") or 0
        if ph:
            p = out["phases"].setdefault(ph, {"calls": 0, "out_tokens": 0, "model_s": 0})
            if st.get("model") or st.get("agent"):
                p["calls"] += 1
            p["out_tokens"] += tokens
            p["model_s"] += round(inf_ms / 1000)
        if st.get("state") == "running" and not node.endswith("_cont"):
            started = _ts(st.get("started_at"))
            out["node"] = {"node": node, "phase": ph, "cell": node_cell(node),
                           "model": (st.get("model") or {}).get("model_id"),
                           "elapsed_s": round(now - started) if started else None,
                           "tok_s": round(tokens / (inf_ms / 1000)) if inf_ms else None}
    return out


def station(now: float) -> dict:
    """The GPU station from the gateway's resource samples (every 10 s) and the model loaded by the last swap."""
    meter = state_root() / "llm-gateway/usage.jsonl"
    sample = None
    try:
        with meter.open("rb") as f:
            f.seek(max(0, meter.stat().st_size - 16384))
            for line in reversed(f.read().decode(errors="replace").splitlines()):
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if "sample" in rec:
                    sample = rec
                    break
    except OSError:
        pass
    model = None
    try:
        last = (state_root().parent / "run/model-swaps.jsonl").read_text().strip().splitlines()[-1]
        model = json.loads(last).get("to")
    except (OSError, IndexError, ValueError):
        pass
    if sample is None:
        return {"available": False, "model": model}
    g = (sample.get("sample") or {}).get("gpu") or {}
    age = round(now - (sample["sample"].get("ts") or 0))
    return {"available": age < 120, "age_s": age, "model": model, "util_pct": g.get("util_pct"), "power_w": g.get("power_w"),
            "temp_c": g.get("temp_c"), "mem_used_mib": g.get("mem_used_mib"), "mem_total_mib": g.get("mem_total_mib")}


def order(ws: Path, now: float | None = None) -> dict:
    """One work order as the floor sees it."""
    now = now or time.time()
    man = _load(ws / ".forge-run/manifest.json") or {}
    target = (man.get("phase_scope") or {}).get("stop_after") or "SWE.6"
    log = _gate_log(ws)
    pkg = _load(ws / ".forge-run/package.json")
    prog = progress(ws)
    phases = {}
    for ph in PHASES:
        L = [e for e in log if e.get("phase") == ph]
        calls = _calls(ws, ph)
        if not L and not calls:
            continue
        ins = [_result(e) for e in L if e.get("step") == "inspect" and _result(e) not in ("REINSPECT", None)]
        t = [x for x in (_ts(e.get("ts")) for e in L) if x]
        phases[ph] = {
            "inspections": ins, "passed": "PASS" in ins, "first_pass": bool(ins) and ins[0] == "PASS",
            "reworks": sum(1 for r in ins if r != "PASS"),  # failed inspections, each sent back for rework
            "frozen": sum(1 for e in L if e.get("step") == "author" and _result(e) == "FROZEN"),
            "rejected": sum(1 for e in L if e.get("step") == "author" and _result(e) == "REJECTED"),
            "blocked": next((str((e.get("gate") or {}).get("reason") or e.get("reason") or "")[:160]
                             for e in reversed(L) if _result(e) == "BLOCKED" and e.get("step") == "route"),
                            next((f"inspection failed ({(e.get('gate') or {}).get('reason')})" for e in reversed(L)
                                  if _result(e) == "BLOCKED"), None)),
            "last": max(t) if t else None,
            "calls": len(calls), "out_tokens": sum(c["out"] for c in calls), "model_s": round(sum(c["s"] for c in calls)),
            "carried": False,
        }
    created = _ts(man.get("created_at"))
    active = prog.get("active")
    rid = prog.get("fabro_run_id")
    nat = native(fabro_stages(rid, pkg is not None), now) if rid else {"phases": {}, "node": None}
    for ph, n in nat["phases"].items():  # native agent phases write no task packets: Fabro has their model work
        if ph in phases and phases[ph]["calls"] == 0:
            phases[ph].update(n)
        elif ph not in phases and n["calls"]:
            phases[ph] = {"inspections": [], "passed": False, "first_pass": False, "reworks": 0, "frozen": 0,
                          "rejected": 0, "blocked": None, "last": None, "carried": False, **n}
    phases = {ph: phases[ph] for ph in PHASES if ph in phases}
    node = nat["node"] if pkg is None else None  # structured progress stays primary; the node says where the order is
    worked = [ph for ph in PHASES if ph in phases and [e for e in log if e.get("phase") == ph]]
    at = active["phase"] if active else (node["phase"] if node and node["phase"] else
                                         worked[-1] if worked else list(phases)[-1] if phases else "SWE.1")
    resumed = (man.get("resumed_from") or {}).get("source_work_order")
    if resumed:  # phases carried over by --resume-from passed in the source order; not this order's work
        for ph in PHASES[:PHASES.index(at)]:
            if not [e for e in log if e.get("phase") == ph]:
                phases[ph] = {"inspections": [], "passed": True, "first_pass": False, "reworks": 0, "frozen": 0,
                              "rejected": 0, "blocked": None, "last": None, "calls": 0, "out_tokens": 0, "model_s": 0,
                              "carried": True}
        phases = {ph: phases[ph] for ph in PHASES if ph in phases}
    if pkg is not None:
        state = "DONE" if (phases.get(target) or {}).get("passed") else "STOPPED"
    elif active or node:
        state = "RUNNING"
    else:
        newest = max([p["last"] or 0 for p in phases.values()] + [created or 0])
        state = "STOPPED" if now - newest > STALE_S else "RUNNING"
    note = None
    if state == "STOPPED":
        note = next((p["blocked"] for p in reversed(list(phases.values())) if p["blocked"]), None) or \
            ("the node stopped before the phase finished" if prog.get("stopped_visit") else "ended before its target phase")
    elif state == "RUNNING" and active:
        note = active["text"]
    elif state == "RUNNING" and node:
        note = f"{at} {node['cell']} cell: node {node['node']} ({node['model'] or 'deterministic'})" + \
            (f", {node['elapsed_s'] // 60} min in this node" if node.get("elapsed_s") else "")
    elif state == "DONE":
        rw = sum(p["reworks"] for p in phases.values())
        note = "every phase at first inspection" if all(p["first_pass"] for p in phases.values() if p["inspections"]) \
            else f"{rw} rework cycle{'s' if rw != 1 else ''}"
    return {"wo": man.get("work_order") or ws.parent.name, "part": man.get("driver"), "target": target, "at": at,
            "state": state, "note": note, "created": created, "phases": phases, "active": active, "node": node,
            "resumed_from": resumed, "newest": max([p["last"] or 0 for p in phases.values()] + [created or 0])}


def _cells(phase: str, orders: list[dict]) -> list[dict]:
    """The hall's cells, their state now, and today's counters."""
    here = [o for o in orders if phase in o["phases"] and not o["phases"][phase]["carried"]]
    run = next((o for o in orders if o["state"] == "RUNNING" and o["at"] == phase), None)
    a = (run or {}).get("active") or {}
    stopped_recent = next((o for o in sorted(orders, key=lambda o: -(o["phases"].get(phase, {}).get("last") or 0))
                           if o["state"] == "STOPPED" and o["at"] == phase), None) if run is None else None
    agg = lambda k: sum(o["phases"][phase][k] for o in here)  # noqa: E731
    reworking = run is not None and any(o is run and o["phases"].get(phase, {}).get("reworks") for o in here)
    step = a.get("step")
    nd = (run or {}).get("node") if not a else None  # a native agent node at work (Fabro run state)
    at_cell = {"author": "author", "inspect": "inspector"}.get(step) if a else (nd or {}).get("cell")

    def state(cell: str) -> str:
        if run is None:
            return "stopped" if stopped_recent is not None and cell == "router" else "idle"
        if cell == at_cell:
            return "rework" if cell == "author" and reworking else "working"
        return "ready" if cell == "tool" else "waiting"
    job = None
    if run is not None:
        wo = run["wo"].replace("WO-F014-", "")
        if a.get("current"):
            job = f"{wo} · now {a['current']}"
        elif nd:
            job = f"{wo} · node {nd['node']}" + (f", {nd['elapsed_s'] // 60} min" if nd.get("elapsed_s") else "")
        else:
            job = wo
    prog = {"done": a.get("done"), "total": a.get("total"), "unit": a.get("unit"), "eta": a.get("eta_utc")} if a else None
    speed = None
    if nd and nd.get("tok_s"):
        speed = nd["tok_s"]
    elif run is not None:
        out = run["phases"].get(phase, {})
        if out.get("model_s"):
            speed = round(out["out_tokens"] / out["model_s"])
    short = lambda m: "Ornith 35B" if m and "ornith" in m.lower() else (m or "").split(":")[0].replace("qwen", "Qwen")  # noqa: E731
    author_tag = f"{short(nd['model'])}, native agent" if nd and nd["cell"] == "author" and nd.get("model") else "Ornith 35B, thinking on"
    insp_tag = f"{short(nd['model'])}, native agent" if nd and nd["cell"] == "inspector" and nd.get("model") else "Qwen3.8 27B"
    per_h = None
    if a.get("done") and a.get("elapsed_s"):
        per_h = round(a["done"] / (a["elapsed_s"] / 3600), 1)
    insp = [o for o in here if o["phases"][phase]["inspections"]]
    cells = [
        {"id": "tool", "name": "Tool changer", "tag": "loads Ornith or Qwen", "state": state("tool"),
         "what": "Loads the right model on the GPU before each cell (6-10 s per swap).", "counters": []},
        {"id": "author", "name": "Author cell", "tag": author_tag, "state": state("author"),
         "job": job if at_cell == "author" else None, "progress": prog if step == "author" else None,
         "speed": {"tok_s": speed, "per_h": per_h, "unit": a.get("unit")} if at_cell == "author" else None,
         "what": "Writes the work products, one task at a time.",
         "counters": [["calls", agg("calls")], ["output tokens", agg("out_tokens")], ["model hours", round(agg("model_s") / 3600, 1)]]},
        {"id": "freeze", "name": "Freeze gate", "tag": "deterministic check", "state": state("freeze"),
         "what": "Checks format, coverage and obligations, then freezes the baseline.",
         "counters": [["frozen", agg("frozen")], ["rejected", agg("rejected")]]},
        {"id": "inspector", "name": "Inspection cell", "tag": insp_tag, "state": state("inspector"),
         "job": job if at_cell == "inspector" else None, "progress": prog if step == "inspect" else None,
         "speed": {"tok_s": speed, "per_h": None, "unit": None} if at_cell == "inspector" and nd else None,
         "what": "Independent review of every checklist item against the frozen baseline.",
         "counters": [["orders inspected", len(insp)]]},
        {"id": "gate", "name": "Inspection gate", "tag": "deterministic check", "state": state("gate"),
         "what": "Records PASS or sends the findings back for rework.",
         "counters": [["first pass", f"{sum(1 for o in insp if o['phases'][phase]['first_pass'])}/{len(insp)}"],
                      ["reworks", agg("reworks")]]},
        {"id": "router", "name": "Rework router", "tag": "deterministic", "state": state("router"),
         "why": stopped_recent["note"] if stopped_recent is not None else None,
         "what": "Grants another repair cycle, or stops an order that is stuck.",
         "counters": [["repairs granted", agg("reworks")], ["stopped", sum(1 for o in here if o["state"] == "STOPPED"
                                                                             and o["at"] == phase)]]},
    ]
    return cells


def floor(now: float | None = None, since: float | None = None) -> dict:
    now = now or time.time()
    start = shift_start(now, since)
    orders = []
    for w in glob.glob(str(state_root() / "workorders/*/workspace")):
        ws = Path(w)
        marks = [ws / ".forge-run/gates/gate-log.jsonl", *map(Path, glob.glob(str(ws / ".forge-run/lrtx/*/visit-state.json")))]
        newest = max((os.path.getmtime(p) for p in marks if p.is_file()), default=0)
        if newest < start:
            continue
        try:
            orders.append(order(ws, now))
        except Exception as exc:  # noqa: BLE001 - one unreadable order never hides the floor
            orders.append({"wo": ws.parent.name, "state": "UNKNOWN", "note": f"{type(exc).__name__}", "phases": {},
                           "at": "SWE.1", "target": "SWE.1"})
    orders.sort(key=lambda o: o.get("created") or 0)
    halls = []
    for ph in PHASES:
        here = [o for o in orders if ph in o["phases"] and not o["phases"][ph]["carried"]]
        insp = [o for o in here if o["phases"][ph]["inspections"]]
        passed = [o for o in here if o["phases"][ph]["passed"]]
        running = [o for o in orders if o["state"] == "RUNNING" and o["at"] == ph]
        stopped = [o for o in here if o["state"] == "STOPPED" and o["at"] == ph]
        cyc = []
        for o in passed:
            prev = [o["phases"][p]["last"] for p in PHASES[:PHASES.index(ph)] if p in o["phases"] and o["phases"][p]["last"]]
            entry = max(prev) if prev else o.get("created")
            if entry and o["phases"][ph]["last"]:
                cyc.append((o["phases"][ph]["last"] - entry) / 60)
        last_stop = max([o["phases"][ph]["last"] or 0 for o in stopped] + [0])
        last_pass = max([o["phases"][ph]["last"] or 0 for o in passed] + [0])
        # the hall's andon: working while an order is in it, red when its newest outcome was a stop, else green/grey
        state = "working" if running else "stopped" if stopped and last_stop > last_pass else "done" if passed else "idle"
        halls.append({"id": ph, "name": HALL_NAMES[ph], "state": state, "entered": len(here), "passed": len(passed),
                      "inspected": len(insp), "first_pass": sum(1 for o in insp if o["phases"][ph]["first_pass"]),
                      "reworks": sum(o["phases"][ph]["reworks"] for o in here), "stopped": len(stopped),
                      "cycle_min": round(sum(cyc) / len(cyc)) if cyc else None,
                      "running": [o["wo"].replace("WO-F014-", "") for o in running],
                      "cells": _cells(ph, orders) if here else []})
    done = [o for o in orders if o["state"] == "DONE"]
    model_s = sum(p["model_s"] for o in orders for p in o["phases"].values())
    out_tokens = sum(p["out_tokens"] for o in orders for p in o["phases"].values())
    h1 = next(h for h in halls if h["id"] == "SWE.1")
    line = None
    for o in orders:
        if o["state"] == "RUNNING" and (o.get("node") or {}).get("tok_s"):
            line = o["node"]["tok_s"]
        elif o["state"] == "RUNNING" and o["phases"].get(o["at"], {}).get("model_s"):
            p = o["phases"][o["at"]]
            line = round(p["out_tokens"] / p["model_s"])
    halls.append({"id": "SHIP", "name": HALL_NAMES["SHIP"], "state": "idle", "entered": 0, "passed": 0, "inspected": 0,
                  "first_pass": 0, "reworks": 0, "stopped": 0, "cycle_min": None, "running": [], "cells": [],
                  "note": "Offline review candidates only; nothing is released."})
    return {"schema": "forge-c/factory-floor/1", "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "shift_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
            "kpis": {"on_floor": sum(1 for o in orders if o["state"] == "RUNNING"), "completed": len(done),
                     "orders": len(orders), "fpy_swe1": [h1["first_pass"], h1["inspected"]],
                     "reworks": sum(h["reworks"] for h in halls), "stopped": sum(1 for o in orders if o["state"] == "STOPPED"),
                     "model_hours": round(model_s / 3600, 1), "out_tokens": out_tokens, "line_tok_s": line,
                     "station": station(now)},
            "halls": halls,
            "orders": [{k: o.get(k) for k in ("wo", "part", "target", "at", "state", "note", "resumed_from")} |
                       {"route": {ph: ("carried" if v["carried"] else "ok" if v["passed"]
                                       else "run" if o["state"] == "RUNNING" and o["at"] == ph
                                       else "no" if o["state"] == "STOPPED" and o["at"] == ph else "—")
                                  for ph, v in o["phases"].items()}} for o in orders]}
