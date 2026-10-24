"""Shared visit machinery of the local profile's structured authors (feature 010): checkpointed tasks with localized
repair and a visit-wide call budget, role-scoped writes, rework findings since the last visit, and the compact reply
the unchanged author gate reads. Phase-specific task sets live in swe1.py / swe2.py."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ..common import pretty_json, utc_now
from . import structured as S


def _ckpt(ws: Path, phase: str, task: str) -> Path:
    return Path(ws) / ".forge-run/lrtx" / phase / "packets" / (task.replace(":", "__") + ".json")


class Continue(Exception):  # noqa: N818 - control flow: the visit's time box is used up, resume in a new node
    """Fabro 0.362 ends a command node with no activity for 1800 s (probes 2026-10-21; stdout does not count). A visit
    therefore stops before a model call that could cross its time box and continues in the next node execution."""


def open_visit(ws: Path, phase: str, resume: bool, findings_fn, max_calls: int, time_budget_s: float | None) -> tuple[
        dict, list[str]]:
    """The visit's shared budget (LRTX-FR-014). A resumed node execution continues the same visit: same call count,
    same rework findings; a new visit starts from the findings addressed to the phase since the last finished visit."""
    sp = Path(ws) / ".forge-run/lrtx" / phase / "visit-state.json"
    st = json.loads(sp.read_text()) if sp.is_file() else None
    if not (resume and st and st.get("open")):
        # a visit that ended FAILED before anything could be assembled leaves no gate finding of its own (the presence
        # gate rejects first): its issues are carried into the next visit so that it repairs instead of repeating
        log = Path(ws) / ".forge-run/lrtx" / phase / "visits.jsonl"
        done = [json.loads(x) for x in (log.read_text().splitlines() if log.is_file() else []) if x.strip()]
        done = [d for d in done if d.get("status") != "CONTINUE"]
        carried = list(done[-1].get("issues") or []) if done and done[-1].get("status") == "FAILED" else []
        st = {"open": True, "started_at": utc_now(), "calls": 0, "continuations": 0,
              "findings": list(dict.fromkeys(findings_fn() + carried))}
    else:
        st["continuations"] = st.get("continuations", 0) + 1
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(pretty_json(st))
    budget = {"calls": st["calls"], "max_calls": max_calls, "state": str(sp),
              "deadline": time.monotonic() + time_budget_s if time_budget_s else None}
    return budget, st["findings"]


def _save_calls(budget: dict) -> None:
    if budget.get("state"):
        sp = Path(budget["state"])
        st = json.loads(sp.read_text())
        st["calls"] = budget["calls"]
        sp.write_text(pretty_json(st))


def close_visit(budget: dict | None) -> None:
    if budget and budget.get("state") and Path(budget["state"]).is_file():
        sp = Path(budget["state"])
        st = json.loads(sp.read_text())
        st.update(open=False, closed_at=utc_now(), calls=budget["calls"])
        sp.write_text(pretty_json(st))


def last_finished(ws: Path, phase: str, log: str = "visits.jsonl") -> str:
    """Time of the last visit that ended (CONTINUE records are part of an open visit)."""
    p = Path(ws) / ".forge-run/lrtx" / phase / log
    done = [json.loads(x) for x in (p.read_text().splitlines() if p.is_file() else []) if x.strip()]
    done = [d for d in done if d.get("status") != "CONTINUE"]
    return done[-1]["at"] if done else ""


def run_task(ws: Path, phase: str, task: str, build, check, budget: dict, findings: list[str] | None = None,
             max_repairs: int = 2) -> dict:
    """Build -> call -> validate -> localized repair, with checkpoint reuse. `build(findings, previous)` returns the
    packet; `check(doc)` returns findings. Every call is counted in `budget` (shared by the whole visit, LRTX-FR-014).
    A VALID checkpoint is reused while the task's base inputs (packet without findings) are unchanged; findings start
    a localized repair of the checkpointed answer instead of a fresh authorship (LRTX-FR-013)."""
    ck = _ckpt(ws, phase, task)
    prev = json.loads(ck.read_text()) if ck.is_file() else None
    base = build(None, None)
    if prev and not findings and prev.get("base_hash") == base["input_hash"] and prev.get("status") == "VALID":
        return {**prev, "reused": True}
    if prev and not findings and prev.get("base_hash") == base["input_hash"] and prev.get("doc") is not None:
        findings = prev.get("errors") or None  # an INVALID checkpoint on unchanged inputs: repair it, not restart
    start = prev["doc"] if (prev and findings and prev.get("doc") is not None) else None
    p = build(findings, start) if start is not None else base
    attempts, doc, errs = [], start, list(findings or [])
    limit = max_repairs + 1
    n = -1
    while n + 1 < limit:
        n += 1
        if budget["calls"] >= budget["max_calls"]:
            errs = (errs or []) + ["VISIT_CALL_BUDGET_EXHAUSTED"]
            break
        if budget.get("deadline") and time.monotonic() > budget["deadline"]:
            if attempts:  # keep the progress of this task: the next node execution repairs from here
                ck.parent.mkdir(parents=True, exist_ok=True)
                ck.write_text(pretty_json({"task": task, "status": "INVALID", "doc": doc if doc is not None else
                                           start, "errors": errs, "base_hash": base["input_hash"],
                                           "attempts": attempts, "at": utc_now(), "reused": False}))
            raise Continue(task)
        budget["calls"] += 1
        if "schema_mode" not in budget:  # LRTX-T012: the probed mode of the served model, recorded once per visit
            budget["schema_mode"], budget["schema_mode_basis"] = S.schema_mode_for(p["model"])
        from ..brownfield.resume import remaining_seconds

        remaining = remaining_seconds(ws)
        r = S.call(p, schema_mode=budget["schema_mode"], **({"timeout": min(3600, remaining)} if remaining else {}))
        errs = r["errors"] or check(r["doc"])
        if not errs and start is not None and findings and r["doc"] == start:
            # lrtxq1 (2026-10-21): an unchanged answer to the findings re-froze the inspected baseline and spent two
            # rework cycles in seconds; the answer must address them or record why one does not apply
            errs = ["LRTX_FINDING_NOT_ADDRESSED: the answer is identical to the one these findings rejected - change "
                    "the requirements so they address the findings, or, if a finding does not apply, state why in "
                    "open_points (it is rendered into the requirements document for the inspector)"]
        attempts.append({"n": n, "input_hash": p["input_hash"], "accounting": p["accounting"], "usage": r["usage"],
                         "wall_ms": r["wall_ms"], "finish_reason": r["finish_reason"], "errors": errs[:20],
                         "schema_mode": budget["schema_mode"], "schema_mode_basis": budget.get("schema_mode_basis")})
        budget.setdefault("log", []).append({"task": task, **attempts[-1]})
        _save_calls(budget)
        # one line per model call: Fabro's stall watchdog ends a command node that shows no activity for 1800 s
        print(json.dumps({"lrtx_progress": task, "attempt": n, "errors": len(errs), "wall_ms": r["wall_ms"]}),
              flush=True)
        if r["doc"] is not None and not r["errors"]:
            doc = r["doc"]
        if not errs:
            break
        # bounded extension (at most 2 extra repairs, inside the visit's shared budget) while the answer improves
        if n + 1 == limit and limit < max_repairs + 3 and len(attempts) > 1 and \
                len(attempts[-1]["errors"]) < len(attempts[-2]["errors"]):
            limit += 1
        p = build(errs[:12], r["doc"]) if r["doc"] is not None and not r["errors"] else p
    rec = {"task": task, "status": "VALID" if doc is not None and not errs else "INVALID", "doc": doc,
           "errors": errs, "base_hash": base["input_hash"], "attempts": attempts, "at": utc_now(), "reused": False}
    ck.parent.mkdir(parents=True, exist_ok=True)
    ck.write_text(pretty_json(rec))
    return rec


def write_scoped(ws: Path, files: dict[str, str], node: str) -> None:
    """Every write is decided by the same role authorization the Fabro policy hook applies to the author node."""
    from ..policy.authz import Authorizer, Binding

    auth = Authorizer(Binding.load(Path(ws) / ".forge-run/binding.json"))
    for rel, text in files.items():
        d = auth.decide(node, "write_file", {"path": rel, "content": ""})
        if not d.allow:
            raise PermissionError(f"LRTX_WRITE_REFUSED:{rel}:{d.code}")
        p = Path(ws) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def rework_findings(ws: Path, phase: str, since: str) -> list[str]:
    """Findings addressed to the phase since the last visit: author-gate rejections, failed inspection items and the
    phase's defects in fix. Text only; mapping to tasks happens through the SWR ids they name."""
    ws = Path(ws)
    out: list[str] = []
    log = ws / ".forge-run/gates/gate-log.jsonl"
    for line in log.read_text().splitlines() if log.is_file() else []:
        d = json.loads(line)
        if d.get("phase") == phase and d.get("ts", "") > since and d.get("result") in ("REJECTED", "FAIL", "REWORK"):
            out += [str(i).removeprefix("LRTX_TASK_INVALID:") for i in d.get("issues") or []]
    ins = sorted((ws / "inspection" / phase).glob("INS-*.json")) if (ws / "inspection" / phase).is_dir() else []
    if ins:
        d = json.loads(ins[-1].read_text())
        if d.get("recorded_at", "") > since and d.get("verdict") != "PASS":
            out += [f"{f.get('id')}: {f.get('detail', '')}" for f in d.get("findings") or []]
            if d.get("stale_reason"):
                out.append(f"inspection stale: {d['stale_reason']}")
    for p in sorted((ws / ".forge-run/defects").glob("DEF-*.json")) if (ws / ".forge-run/defects").is_dir() else []:
        d = json.loads(p.read_text())
        if d.get("target_phase") == phase and d.get("status") == "IN_FIX":
            out.append(f"defect {d.get('id')} ({', '.join(d.get('requirement_ids') or [])}): {d.get('summary', '')} "
                       f"{d.get('requirement_quote', '')}".strip())
    return out


def route_findings(findings: list[str], amap: dict | None, default: str) -> dict[str, list[str]]:
    """Task -> findings: by the SWR ids or effect case ids a finding names; anything unmapped goes to every task whose
    requirements it might concern is unknown, so it is attached to the cross-cutting task and reported."""
    out: dict[str, list[str]] = {}
    for f in findings:
        tasks = set(re.findall(r"\b(requirements:[A-Za-z0-9_]+)", f))  # a visit's own findings name their task
        for swr in re.findall(r"SWR-\d{3}", f):
            if amap and swr in amap["swr"]:
                t = amap["swr"][swr]
                tasks.add(t["task"])
                f = f.replace(swr, f"{swr} [{t['key']}]")
        for case, swr in (amap or {}).get("case", {}).items():
            if re.search(rf"\b{re.escape(case)}\b", f) and swr in (amap or {}).get("swr", {}):
                tasks.add(amap["swr"][swr]["task"])
        for t in tasks or {default}:
            if t != "budgets":
                out.setdefault(t, []).append(f)
    return out


def reply(ws: Path, phase: str, status: str, issues: list[str], budget: dict | None = None,
          artifacts: list[str] | None = None) -> dict:
    """The compact author reply the unchanged author gate reads (agent-output contract), plus the visit record."""
    doc = {"status": status, "artifacts": artifacts or [], "issues": [i[:300] for i in issues[:20]],
           "next_action": "next" if status == "PASS" else "rework"}
    S.record(ws, f"{phase}/reply.json", doc)
    if status != "CONTINUE":
        close_visit(budget)
    calls = (budget or {}).get("log", [])
    visit_rec = {"at": utc_now(), "status": status, "calls": (budget or {}).get("calls", 0),
                 "max_calls": (budget or {}).get("max_calls"), "issues": doc["issues"][:10],
                 "prompt_tokens": [((c.get("usage") or {}).get("prompt_tokens"), c["accounting"]["estimated_prompt_tokens"])
                                   for c in calls]}
    p = Path(ws) / ".forge-run/lrtx" / phase / "visits.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(visit_rec, sort_keys=True) + "\n")
    return doc
