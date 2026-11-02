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


_ENDED: dict[str, str] = {}  # a run Fabro reports as ended never runs again


def fabro_lifecycle(run_id: str | None) -> str | None:
    """Fabro's run status ('running', 'succeeded', 'failed:cancelled', ...); None when unavailable."""
    url = os.environ.get("FORGE_FLOOR_FABRO_URL")
    if not url or not run_id:
        return None
    if run_id in _ENDED:
        return _ENDED[run_id]
    import urllib.request

    req = urllib.request.Request(f"{url.rstrip('/')}/runs/{run_id}", headers={"Accept": "application/json"})
    tok = _fabro_token()
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=4) as r:
            st = (json.load(r).get("lifecycle") or {}).get("status") or {}
    except Exception:  # noqa: BLE001
        return None
    kind = st.get("kind") if isinstance(st, dict) else st
    status = f"{kind}:{st.get('reason')}" if isinstance(st, dict) and st.get("reason") else str(kind)
    if kind in ("succeeded", "failed", "cancelled", "canceled", "aborted"):
        _ENDED[run_id] = status
    return status


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


def cloud_station(now: float) -> dict | None:
    """Owner 2026-11-02 ("instead of gpu monitor i want to have a tokens and api cost monitor for both claude and
    openai"): the cloud line's API station from the bridge's per-call meter (state/cloud-bridge/calls.jsonl; no prompt
    or answer is in it): per model, today (UTC) and the last hour - calls, tokens, cost when the profile prices it."""
    meter = state_root() / "cloud-bridge/calls.jsonl"
    if not meter.is_file():
        return None
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    hour_ago = now - 3600
    models: dict[str, dict] = {}
    # owner 2026-11-02 ("apply them"): display rates for a model the bridge does not price (gpt-6.1-sol, from public
    # pricing pages, unverified) - FORGE_FLOOR_API_PRICES {model: {input, cached, output, source}} USD per 1M tokens
    try:
        rates = json.loads(os.environ.get("FORGE_FLOOR_API_PRICES") or "{}")
    except ValueError:
        rates = {}
    for line in meter.read_text(errors="replace").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        t = _ts(r.get("ts")) or 0
        if not str(r.get("ts", "")).startswith(day) or not r.get("model"):
            continue
        m = models.setdefault(r["model"], {"model": r["model"], "backend": r.get("backend"), "last_ts": 0,
                                           "today": _api_zero(), "hour": _api_zero(), "priced": False})
        u = dict(r.get("usage") or {})
        rate = rates.get(r["model"])
        if u.get("cost_usd") is None and rate and u:
            cached = int(u.get("cached_prompt_tokens") or 0)
            u["cost_usd"] = ((int(u.get("prompt_tokens") or 0) - cached) * rate.get("input", 0) + cached * rate.get("cached", 0)
                             + int(u.get("completion_tokens") or 0) * rate.get("output", 0)) / 1e6
            m["price_source"] = rate.get("source", "floor display rate")
        m["priced"] = m["priced"] or u.get("cost_usd") is not None
        m["last_ts"] = max(m["last_ts"], t)
        for k in (["today", "hour"] if t >= hour_ago else ["today"]):
            a = m[k]
            a["calls"] += 1
            a["failed"] += 0 if r.get("ok") else 1
            for f, key in (("prompt", "prompt_tokens"), ("completion", "completion_tokens"), ("reasoning", "reasoning_tokens"),
                           ("cached", "cached_prompt_tokens"), ("cached", "cache_read_tokens")):
                a[f] += int(u.get(key) or 0)
            a["cost_usd"] = round(a["cost_usd"] + float(u.get("cost_usd") or 0), 4)
    for m in models.values():
        m["last_s"] = round(now - m.pop("last_ts")) if m.get("last_ts") else None
    return {"kind": "cloud_api", "available": True, "models": sorted(models.values(), key=lambda x: x["model"]),
            "cost_today_usd": round(sum(m["today"]["cost_usd"] for m in models.values()), 2)}


def _api_zero() -> dict:
    return {"calls": 0, "failed": 0, "prompt": 0, "completion": 0, "reasoning": 0, "cached": 0, "cost_usd": 0.0}


def station(now: float) -> dict:
    """The GPU station from the gateway's resource samples (every 10 s) and the model loaded by the last swap; on the
    cloud comparison line (a cloud-bridge meter exists) the API station instead."""
    cloud = cloud_station(now)
    if cloud is not None:
        return cloud
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


HISTORY_S = 7 * 86400
_HISTORY: dict = {"at": 0.0, "typical": {}, "refs": {}}


def _median(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2


def history(now: float) -> dict:
    """Typical durations of the workflow nodes and the work-product count of each phase, from the finished runs of the
    last 7 days (Fabro node visits, read-only; cached, recomputed at most every 10 minutes)."""
    if now - _HISTORY["at"] < 600:
        return _HISTORY
    durs: dict[str, list[float]] = {}
    refs: dict[tuple, tuple] = {}
    for w in glob.glob(str(state_root() / "workorders/*/workspace")):
        ws = Path(w)
        pkg, rid = ws / ".forge-run/package.json", ws / ".forge-run/fabro_run_id"
        try:
            if not pkg.is_file() or os.path.getmtime(pkg) < now - HISTORY_S:
                continue
        except OSError:
            continue
        for sid, st in (fabro_stages(rid.read_text().strip() if rid.is_file() else None, True) or {}).items():
            ms = (st.get("timing") or {}).get("wall_time_ms")
            if st.get("state") == "succeeded" and ms:
                durs.setdefault(sid.split("@")[0], []).append(ms / 1000)
        driver = (_load(ws / ".forge-run/manifest.json") or {}).get("driver")
        log = _gate_log(ws)
        for ph in PHASES:
            if not any(e.get("phase") == ph and e.get("step") == "inspect" and _result(e) == "PASS" for e in log):
                continue
            bls = sorted(glob.glob(str(ws / "configuration/baselines" / ph / "BL-*.json")))
            bl = _load(Path(bls[-1])) if bls else None
            if bl and bl.get("files"):
                t = os.path.getmtime(bls[-1])
                if t > refs.get((driver, ph), (0, 0))[0]:
                    refs[(driver, ph)] = (t, len(bl["files"]))
    _HISTORY.update(at=now, typical={n: {"s": round(_median(v)), "n": len(v)} for n, v in durs.items()},
                    refs={k: v[1] for k, v in refs.items()})
    return _HISTORY


# The deterministic tool checks the structured author runs after its tasks, per phase (journaled tool calls,
# evidence/tool-results.jsonl). Owner 2026-11-01: "the tools phase should be a node and a cell right?" -> a cell now.
TOOLS = {"SWE.3": [("forge-build-mcp", "compile", "target build"), ("forge-build-mcp", "compile", "host build"),
                   ("forge-docs-mcp", "validate_artifact", "design and code rules"),
                   ("forge-analysis-mcp", "cppcheck", "static analysis")],
         "SWE.4": [("forge-tests-mcp", "run_unit", "unit tests"), ("forge-tests-mcp", "llvm_coverage", "coverage")],
         "SWE.5": [("forge-tests-mcp", "run_integration", "integration tests"), ("forge-sim-mcp", "run_renode", "target tests (Renode)")],
         "SWE.6": [("forge-tests-mcp", "run_robot", "target tests (Renode)")]}


def tool_progress(ws: Path, phase: str) -> dict[str, dict]:
    """Owner 2026-11-01: how many tests the phase's test tools have to run and how many already ran (written by the
    tools while they run: .forge-run/tool-progress/<phase>-<op>.json). Display only."""
    out = {}
    for f in glob.glob(str(ws / ".forge-run/tool-progress" / f"{phase}-*.json")):
        rec = _load(Path(f)) or {}
        if rec.get("op"):
            out[rec["op"]] = {k: rec.get(k) for k in ("unit", "total", "done", "passed", "failed", "running", "updated")}
    return out


def tool_rounds(ws: Path, phase: str) -> list[list[dict]]:
    """The phase author's tool runs, grouped into rounds (a round starts at the phase's first tool)."""
    want = TOOLS.get(phase) or []
    if not want:
        return []
    keys = {(s_, o) for s_, o, _l in want}
    rounds: list[list[dict]] = []
    p = ws / "evidence/tool-results.jsonl"
    for line in (p.read_text().splitlines() if p.is_file() else []):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("phase") != phase or not str(r.get("role") or "").endswith("-author") or \
                (r.get("server"), r.get("op")) not in keys:
            continue
        res = r.get("result") or {}
        label = next(lab for s_, o, lab in want if (s_, o) == (r["server"], r["op"]))
        if r["op"] == "compile":
            label = "target build" if "relocatable_elf" in (res.get("metrics") or {}) else "host build"
        if label == want[0][2] or not rounds:
            rounds.append([])
        rounds[-1].append({"tool": label, "status": res.get("status"), "at": _ts(r.get("ts_utc"))})
    return rounds


def _work_products(ws: Path, phase: str) -> int:
    try:
        from ..inspection.engine import Store

        return len(Store(ws).files_of(phase))
    except Exception:  # noqa: BLE001
        return 0


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
            "last_author": next((_result(e) for e in reversed(L) if e.get("step") == "author"), None),
            "last_inspect": next((_result(e) for e in reversed(L) if e.get("step") == "inspect"
                                  and _result(e) != "REINSPECT"), None),
            "last_route": next((_result(e) for e in reversed(L) if e.get("step") == "route"), None),
        }
    created = _ts(man.get("created_at"))
    active = prog.get("active")
    rid = prog.get("fabro_run_id")
    life = fabro_lifecycle(rid) if pkg is None and rid else None
    ended = bool(life) and life.split(":")[0] in ("succeeded", "failed", "cancelled", "canceled", "aborted")
    nat = native(fabro_stages(rid, pkg is not None or ended), now) if rid else {"phases": {}, "node": None}
    for ph, n in nat["phases"].items():  # native agent phases write no task packets: Fabro has their model work
        if ph in phases and phases[ph]["calls"] == 0:
            phases[ph].update(n)
        elif ph not in phases and n["calls"]:
            phases[ph] = {"inspections": [], "passed": False, "first_pass": False, "reworks": 0, "frozen": 0,
                          "rejected": 0, "blocked": None, "last": None, "carried": False, "last_author": None,
                          "last_inspect": None, "last_route": None, **n}
    phases = {ph: phases[ph] for ph in PHASES if ph in phases}
    # structured progress stays primary; the node says where the order is. A run Fabro reports as ended has no node
    # at work, even when its last stage was left 'running' (a cancelled node)
    node = nat["node"] if pkg is None and not ended else None
    if ended:
        active = None
    worked = [ph for ph in PHASES if ph in phases and [e for e in log if e.get("phase") == ph]]
    at = active["phase"] if active else (node["phase"] if node and node["phase"] else
                                         worked[-1] if worked else list(phases)[-1] if phases else "SWE.1")
    resumed = (man.get("resumed_from") or {}).get("source_work_order")
    if resumed:  # phases carried over by --resume-from passed in the source order; not this order's work
        for ph in PHASES[:PHASES.index(at)]:
            if not [e for e in log if e.get("phase") == ph]:
                phases[ph] = {"inspections": [], "passed": True, "first_pass": False, "reworks": 0, "frozen": 0,
                              "rejected": 0, "blocked": None, "last": None, "calls": 0, "out_tokens": 0, "model_s": 0,
                              "carried": True, "last_author": None, "last_inspect": None, "last_route": None}
        phases = {ph: phases[ph] for ph in PHASES if ph in phases}
    if pkg is not None:
        state = "DONE" if (phases.get(target) or {}).get("passed") else "STOPPED"
    elif ended:
        state = "STOPPED"
    elif active or node:
        state = "RUNNING"
    else:
        newest = max([p["last"] or 0 for p in phases.values()] + [created or 0])
        state = "STOPPED" if now - newest > STALE_S else "RUNNING"
    note = None
    if state == "STOPPED":
        note = next((p["blocked"] for p in reversed(list(phases.values())) if p["blocked"]), None) or \
            (f"Fabro run ended ({life.replace(':', ', ')}) before its target phase" if ended else
             "the node stopped before the phase finished" if prog.get("stopped_visit") else "ended before its target phase")
    elif state == "RUNNING" and active:
        note = active["text"]
    elif state == "RUNNING" and node:
        note = f"{at} {node['cell']} cell: node {node['node']} ({node['model'] or 'deterministic'})" + \
            (f", {node['elapsed_s'] // 60} min in this node" if node.get("elapsed_s") else "")
    elif state == "DONE":
        rw = sum(p["reworks"] for p in phases.values())
        note = "every phase at first inspection" if all(p["first_pass"] for p in phases.values() if p["inspections"]) \
            else f"{rw} rework cycle{'s' if rw != 1 else ''}"
    wp = {"have": _work_products(ws, at), "phase": at} if state == "RUNNING" else None
    tools = {ph: tool_rounds(ws, ph) for ph in TOOLS if ph in phases}
    tool_prog = {ph: tool_progress(ws, ph) for ph in TOOLS if ph in phases}
    newest_task = max([_ts((_load(Path(f)) or {}).get("at")) or 0
                       for f in glob.glob(str(ws / ".forge-run/lrtx" / at / "packets/*.json"))] + [0])
    return {"wo": man.get("work_order") or ws.parent.name, "part": man.get("driver"), "target": target, "at": at,
            "state": state, "note": note, "created": created, "phases": phases, "active": active, "node": node, "wp": wp,
            "tools": tools, "progress": tool_prog, "newest_task": newest_task,
            "resumed_from": resumed, "newest": max([p["last"] or 0 for p in phases.values()] + [created or 0])}


STEP = {"FROZEN": "passed", "PASS": "passed", "INJECTED": "passed", "UNCHANGED": "passed", "REJECTED": "rejected",
        "REWORK": "rejected", "BLOCKED": "stopped"}
WAIT_FOR = {"tool": None, "author": "the tool changer", "freeze": "the author cell", "inspector": "the freeze gate",
            "gate": "the inspection cell", "router": "the inspection gate"}


def _tool_cell(phase: str, run: dict | None, here: list[dict], a: dict) -> dict | None:
    """The tool station: the phase's deterministic tool runs (last round per tool: passed / failed / pending)."""
    want = TOOLS.get(phase)
    if not want:
        return None
    rounds = (run or {}).get("tools", {}).get(phase) or []
    last = rounds[-1] if rounds else []
    labels = [lab for _s, _o, lab in want]
    state, why = "idle", None
    if run is not None:
        failed = [t for t in last if t["status"] not in ("PASS", None)]
        tools_newer = bool(last) and max(t["at"] or 0 for t in last) >= (run.get("newest_task") or 0)
        if a.get("checking") and (not last or tools_newer or not failed):
            state = "working"
        elif failed:
            state = "rework"
            why = "found " + ", ".join(t["tool"] for t in failed) + " issues; the author repairs them"
        else:
            state = "waiting"
    seen = {t["tool"]: t["status"] for t in last}
    steps = [{"label": lab, "status": "passed" if seen.get(lab) == "PASS" else "failed" if lab in seen else "pending"}
             for lab in labels]
    prog = (run or {}).get("progress", {}).get(phase) or {}
    tests = None
    for (_s, op, lab), st in zip(want, steps):
        pr = prog.get(op)
        if pr and pr.get("total") is not None:
            st["tests"] = {k: pr.get(k) for k in ("done", "total", "passed", "failed", "unit")}
            if pr.get("running") or tests is None or (pr.get("updated") or 0) > (tests.get("updated") or 0):
                tests = {"label": lab, **st["tests"], "running": bool(pr.get("running")), "updated": pr.get("updated")}
                if pr.get("running"):
                    break
        elif pr and pr.get("running"):
            tests = {"label": lab, "done": 0, "total": None, "unit": pr.get("unit"), "running": True}
            break
    allr = [t for o in here for r in (o.get("tools") or {}).get(phase, []) for t in r]
    return {"id": "tools", "name": "Tool station", "tag": "qualified tools, deterministic", "state": state,
            "bar": {"kind": "tools", "steps": steps, "round": len(rounds), "tests": tests} if run is not None
            else {"kind": "idle"},
            "why": why, "what": "Builds and checks the work products: " + ", ".join(labels) + ".",
            "counters": [["tool runs", len(allr)], ["failed", sum(1 for t in allr if t["status"] not in ("PASS", None))]]}


def _bar(cell: str, run: dict | None, a: dict, nd: dict | None, at_cell: str | None, phase: str, now: float) -> dict:
    """The cell's bar: measured task progress, a time estimate against the node's typical duration, a step of a
    deterministic check, or waiting/idle. Every bar says which kind it is."""
    if run is None:
        return {"kind": "idle"}
    if a and cell == at_cell and a.get("total"):
        return {"kind": "measured", "done": a.get("done"), "total": a.get("total"), "unit": a.get("unit"),
                "eta": a.get("eta_utc"), "sub": "running the tool checks (build, static analysis)" if a.get("checking") else None}
    if nd and cell == at_cell:
        if cell in ("freeze", "gate", "router"):
            return {"kind": "step", "step": "checking", "node": nd["node"]}
        typ = history(now)["typical"].get(nd["node"])
        el = nd.get("elapsed_s") or 0
        bar = {"kind": "estimate", "elapsed_s": el, "node": nd["node"]}
        if typ and typ["s"]:
            bar.update(pct=min(95, round(el / typ["s"] * 100)), typical_s=typ["s"], n=typ["n"], over=el > typ["s"])
        if cell == "author" and run.get("wp"):
            ref = history(now)["refs"].get((run.get("part"), phase))
            bar["work_products"] = {"have": run["wp"]["have"], "expect": ref}
        return bar
    p = run["phases"].get(phase) or {}
    last = {"freeze": p.get("last_author"), "gate": p.get("last_inspect"), "router": p.get("last_route")}.get(cell)
    if last in STEP:  # the router's REWORK is a repair it granted, not a rejection
        return {"kind": "step", "step": "rework" if cell == "router" and last == "REWORK" else STEP[last], "decision": last}
    return {"kind": "waiting", "for": "the tool station" if cell == "freeze" and phase in TOOLS else WAIT_FOR.get(cell)}


def _cells(phase: str, orders: list[dict], now: float | None = None) -> list[dict]:
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
        elif a.get("checking"):
            job = f"{wo} · all {a.get('total')} tasks valid, tool checks"
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
    now = now or time.time()
    bar = lambda cell: _bar(cell, run, a, nd, at_cell, phase, now)  # noqa: E731
    cells = [
        {"id": "tool", "bar": bar("tool"), "name": "Tool changer", "tag": "loads Ornith or Qwen", "state": state("tool"),
         "what": "Loads the right model on the GPU before each cell (6-10 s per swap).", "counters": []},
        {"id": "author", "bar": bar("author"), "name": "Author cell", "tag": author_tag, "state": state("author"),
         "job": job if at_cell == "author" else None, "progress": prog if step == "author" else None,
         "speed": {"tok_s": speed, "per_h": per_h, "unit": a.get("unit")} if at_cell == "author" else None,
         "what": "Writes the work products, one task at a time.",
         "counters": [["calls", agg("calls")], ["output tokens", agg("out_tokens")], ["model hours", round(agg("model_s") / 3600, 1)]]},
        {"id": "freeze", "bar": bar("freeze"), "name": "Freeze gate", "tag": "deterministic check", "state": state("freeze"),
         "what": "Checks format, coverage and obligations, then freezes the baseline.",
         "counters": [["frozen", agg("frozen")], ["rejected", agg("rejected")]]},
        {"id": "inspector", "bar": bar("inspector"), "name": "Inspection cell", "tag": insp_tag, "state": state("inspector"),
         "job": job if at_cell == "inspector" else None, "progress": prog if step == "inspect" else None,
         "speed": {"tok_s": speed, "per_h": None, "unit": None} if at_cell == "inspector" and nd else None,
         "what": "Independent review of every checklist item against the frozen baseline.",
         "counters": [["orders inspected", len(insp)]]},
        {"id": "gate", "bar": bar("gate"), "name": "Inspection gate", "tag": "deterministic check", "state": state("gate"),
         "what": "Records PASS or sends the findings back for rework.",
         "counters": [["first pass", f"{sum(1 for o in insp if o['phases'][phase]['first_pass'])}/{len(insp)}"],
                      ["reworks", agg("reworks")]]},
        {"id": "router", "bar": bar("router"), "name": "Rework router", "tag": "deterministic", "state": state("router"),
         "why": stopped_recent["note"] if stopped_recent is not None else None,
         "what": "Grants another repair cycle, or stops an order that is stuck.",
         "counters": [["repairs granted", agg("reworks")], ["stopped", sum(1 for o in here if o["state"] == "STOPPED"
                                                                             and o["at"] == phase)]]},
    ]
    tc = _tool_cell(phase, run, here, a)
    if tc is not None:
        cells.insert(2, tc)  # between the author cell and the freeze gate
    return cells


def _focus_state(o: dict, ph: str) -> str:
    """A hall's state for one order: out of its route, carried over, working, done, stopped or pending."""
    route = PHASES[:PHASES.index(o["target"]) + 1] if o.get("target") in PHASES else list(PHASES)
    if ph not in route:
        return "out"
    p = o["phases"].get(ph)
    if p and p.get("carried"):
        return "carried"
    if o["state"] == "RUNNING" and o["at"] == ph:
        return "working"
    if p and p.get("passed"):
        return "done"
    if o["state"] == "STOPPED" and o["at"] == ph:
        return "stopped"
    return "pending"


def floor(now: float | None = None, since: float | None = None, focus: str | None = None) -> dict:
    """The shift (every order since `since`, default 00:00 UTC), or with `focus` (a work order id or its suffix) the
    halls and cells of that one order; shift KPIs and the order list are always the whole shift."""
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
    sel = next((o for o in orders if focus and (o["wo"] == focus or o["wo"].endswith(focus))), None)
    scope = [sel] if sel else orders
    halls = []
    for ph in PHASES:
        here = [o for o in scope if ph in o["phases"] and not o["phases"][ph]["carried"]]
        insp = [o for o in here if o["phases"][ph]["inspections"]]
        passed = [o for o in here if o["phases"][ph]["passed"]]
        running = [o for o in scope if o["state"] == "RUNNING" and o["at"] == ph]
        stopped = [o for o in here if o["state"] == "STOPPED" and o["at"] == ph]
        cyc = []
        for o in passed:
            prev = [o["phases"][p]["last"] for p in PHASES[:PHASES.index(ph)] if p in o["phases"] and o["phases"][p]["last"]]
            entry = max(prev) if prev else o.get("created")
            if entry and o["phases"][ph]["last"]:
                cyc.append((o["phases"][ph]["last"] - entry) / 60)
        # owner 2026-11-01 ("Shift view + order focus"): in the shift view a hall lights up only while an order is in it;
        # what happened earlier is history, not a light. In the order focus, the hall shows that order's state in it.
        if sel:
            state = _focus_state(sel, ph)
        else:
            state = "working" if running else "history" if passed or stopped else "idle"
        halls.append({"id": ph, "name": HALL_NAMES[ph], "state": state, "entered": len(here), "passed": len(passed),
                      "inspected": len(insp), "first_pass": sum(1 for o in insp if o["phases"][ph]["first_pass"]),
                      "reworks": sum(o["phases"][ph]["reworks"] for o in here), "stopped": len(stopped),
                      "cycle_min": round(sum(cyc) / len(cyc)) if cyc else None,
                      "running": [o["wo"].replace("WO-F014-", "") for o in running],
                      "cells": _cells(ph, scope, now) if here and state != "out" else []})
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
    ship = ("pending" if sel.get("target") == "SWE.6" else "out") if sel else "idle"
    halls.append({"id": "SHIP", "name": HALL_NAMES["SHIP"], "state": ship, "entered": 0, "passed": 0, "inspected": 0,
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
            "focus": None if sel is None else {
                "wo": sel["wo"], "part": sel.get("part"), "target": sel.get("target"), "state": sel["state"],
                "at": sel["at"], "note": sel.get("note"), "resumed_from": sel.get("resumed_from"),
                "phases_passed": sum(1 for p in sel["phases"].values() if p["passed"]),
                "phases_in_route": len(PHASES[:PHASES.index(sel["target"]) + 1]) if sel.get("target") in PHASES else 6,
                "reworks": sum(p["reworks"] for p in sel["phases"].values()),
                "model_hours": round(sum(p["model_s"] for p in sel["phases"].values()) / 3600, 1),
                "out_tokens": sum(p["out_tokens"] for p in sel["phases"].values()),
                "elapsed_min": round((now - sel["created"]) / 60) if sel.get("created") and sel["state"] == "RUNNING" else None},
            "orders": [{k: o.get(k) for k in ("wo", "part", "target", "at", "state", "note", "resumed_from")} |
                       {"route": {ph: ("carried" if v["carried"] else "ok" if v["passed"]
                                       else "run" if o["state"] == "RUNNING" and o["at"] == ph
                                       else "no" if o["state"] == "STOPPED" and o["at"] == ph else "—")
                                  for ph, v in o["phases"].items()}} for o in orders]}
