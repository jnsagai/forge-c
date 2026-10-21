"""Shared visit machinery of the local profile's structured authors (feature 010): checkpointed tasks with localized
repair and a visit-wide call budget, role-scoped writes, rework findings since the last visit, and the compact reply
the unchanged author gate reads. Phase-specific task sets live in swe1.py / swe2.py."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import pretty_json, utc_now
from . import structured as S


def _ckpt(ws: Path, phase: str, task: str) -> Path:
    return Path(ws) / ".forge-run/lrtx" / phase / "packets" / (task.replace(":", "__") + ".json")


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
    for n in range(max_repairs + 1):
        if budget["calls"] >= budget["max_calls"]:
            errs = (errs or []) + ["VISIT_CALL_BUDGET_EXHAUSTED"]
            break
        budget["calls"] += 1
        r = S.call(p, schema_mode=budget.get("schema_mode", "json_schema"))
        errs = r["errors"] or check(r["doc"])
        attempts.append({"n": n, "input_hash": p["input_hash"], "accounting": p["accounting"], "usage": r["usage"],
                         "wall_ms": r["wall_ms"], "finish_reason": r["finish_reason"], "errors": errs[:20]})
        budget.setdefault("log", []).append({"task": task, **attempts[-1]})
        if r["doc"] is not None and not r["errors"]:
            doc = r["doc"]
        if not errs:
            break
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
            out += [str(i) for i in d.get("issues") or []]
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
        tasks = set()
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
