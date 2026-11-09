"""Feature 018: two-phase SWE.1 inspection, phase 1 - each requirement inspected and reworked on its own.

Owner 2026-11-09: "for the inspection, i want the inspector and rework be divided in 2 phases, one in which the
inspection and rework cycle will be done requirement per requirement without modifying others, and after that
inspector and rework phase for the complete set", following docs/SWE1-REQUIREMENTS-QUALITY-GUIDELINE.md.

Phase 1 runs between the SWE.1 author and its freeze gate (graph nodes swe1_iq_inspect -> swe1_iq_check ->
swe1_iq_rework -> swe1_iq_inspect ...):
  iq-inspect  the inspector judges every requirement whose current content has no verdict, alone, against IQ-01..12
  iq-check    exit 0 while a requirement needs rework (BLOCKING/CORRECTABLE, author-made, rounds left)
  iq-rework   the author rewrites only a flagged requirement; code splices it into its task answer, so every other
              requirement stays byte-identical (swe1.replace_requirement)
A requirement that still has findings when its rounds are used, whose rework makes no change or is invalid, or that
the factory generates (budgets) is carried to the set phase (owner decision 2026-11-09). Phase 1 never blocks SWE.1
and records no inspection: the route gate's rework cycles are untouched. No prompt or reasoning is stored.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from ..common import REPO_ROOT, canonical_json, sha256_bytes, sha256_file, utc_now
from . import structured as S
from . import visit as V

CHECKLIST = "config/factory/swe1-requirements-quality.yaml"  # not under the protected factory/checklists/** (CRE)
INSPECT = "SWE.1/phase1"  # visit state and verdict checkpoints of the inspector step
REWORK = "SWE.1/phase1-rework"  # visit state and answer checkpoints of the author step
STATE = "SWE.1/phase1/state.json"
SUMMARY = "SWE.1/phase1/summary.json"
VERDICTS = "SWE.1/phase1/verdicts.jsonl"
REWORKS = "SWE.1/phase1/reworks.jsonl"
MAX_CALLS = 1_000_000  # owner 2026-11-09: limits very high; rounds per requirement bound the phase
# The live trial profile's file is checksum-bound into guardian history, so it is switched on here (code-side pin).
PINNED_PROFILES = frozenset({"local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104"})


def enabled(profile: dict | None) -> bool:
    """The two-phase inspection is on for a profile that asks for it, or for a pinned profile."""
    if not profile:
        return False
    return bool((profile.get("structured") or {}).get("two_phase_inspection")) or profile.get("id") in PINNED_PROFILES


def quality_checklist(root: Path | None = None) -> dict:
    """The versioned IQ/SQ criteria, refused when they no longer match the pinned guideline."""
    root = Path(root or REPO_ROOT)
    doc = yaml.safe_load((root / CHECKLIST).read_text())
    if doc.get("schema") != "forge-c/swe1-quality-checklist/1":
        raise ValueError("QUALITY_CHECKLIST_SCHEMA")
    if sha256_file(root / doc["guideline"]["path"]) != doc["guideline"]["sha256"]:
        raise ValueError("QUALITY_GUIDELINE_CHANGED")
    if [i["id"] for i in doc["individual"]] != [f"IQ-{n:02d}" for n in range(1, 13)] or \
            [i["id"] for i in doc["set"]] != [f"SQ-{n:02d}" for n in range(1, 11)]:
        raise ValueError("QUALITY_CHECKLIST_IDS")
    return doc


def verdict_schema(swr: str) -> dict:
    """contracts/individual-verdict.schema.json for one requirement."""
    return {"type": "object", "additionalProperties": False, "required": ["requirement_id", "findings"],
            "properties": {"requirement_id": {"type": "string", "enum": [swr]},
                           "findings": {"type": "array", "maxItems": 24, "items": {
                               "type": "object", "additionalProperties": False,
                               "required": ["quality_id", "severity", "evidence", "required_action",
                                            "input_uncertainty"],
                               "properties": {
                                   "quality_id": {"type": "string", "enum": [f"IQ-{n:02d}" for n in range(1, 13)]},
                                   "severity": {"type": "string", "enum": ["BLOCKING", "CORRECTABLE", "EDITORIAL", "N/A"]},
                                   "evidence": {"type": "string", "minLength": 1, "maxLength": 400},
                                   "required_action": {"type": "string", "maxLength": 300},
                                   "input_uncertainty": {"type": "boolean"}}}}}}


def needs_rework(finding: dict, cl: dict | None = None) -> bool:
    sev = (cl or {}).get("rework_severities") or ["BLOCKING", "CORRECTABLE"]
    return finding.get("severity") in sev and not finding.get("input_uncertainty")


def finding_text(f: dict) -> str:
    return f"{f['quality_id']} ({f['severity']}): {f['evidence']} -> {f.get('required_action') or 'resolve'}"


# ---- the set under inspection ---------------------------------------------------------------------------------------
def requirements(ws: Path) -> list[dict]:
    """Every requirement of the assembled set: swr, task, key, obj, sha (canonical object), generated (budgets)."""
    from . import swe1

    ws = Path(ws)
    amap = json.loads((ws / ".forge-run/lrtx/SWE.1/assembly.json").read_text())
    docs: dict[str, dict] = {}
    budget = None
    out = []
    for swr, ref in amap["swr"].items():
        task, key = ref["task"], ref["key"]
        if task in V.NOT_AUTHORED:
            if budget is None:
                budget = {r["key"]: r for r in swe1.budget_requirements(ws, swe1.system_name(ws))}
            obj, generated = budget.get(key), True
        else:
            if task not in docs:
                docs[task] = json.loads(V._ckpt(ws, "SWE.1", task).read_text())["doc"]
            obj, generated = next((r for r in docs[task]["requirements"] if r["key"] == key), None), False
        if obj is None:
            raise ValueError(f"PHASE1_REQUIREMENT_MISSING:{swr}:{task}:{key}")
        out.append({"swr": swr, "task": task, "key": key, "obj": obj, "generated": generated,
                    "sha": sha256_bytes(canonical_json(obj)), "siblings": [r for r in (docs.get(task) or {}).get(
                        "requirements", []) if r["key"] != key]})
    return out


def _tk(ref: dict) -> str:
    return f"{ref['task']}|{ref['key']}"


def _author_passed(ws: Path) -> bool:
    p = Path(ws) / ".forge-run/lrtx/SWE.1/reply.json"
    return p.is_file() and json.loads(p.read_text()).get("status") == "PASS"


def _state(ws: Path) -> dict:
    """Per-requirement rounds of the current author result (epoch = the author's last finished visit): a new author
    visit (set rework) starts new rounds; verdicts stay keyed by requirement content and are never repeated."""
    p = Path(ws) / ".forge-run/lrtx" / STATE
    epoch = V.last_finished(ws, "SWE.1")
    st = json.loads(p.read_text()) if p.is_file() else None
    if not st or st.get("epoch") != epoch:
        st = {"schema": "forge-c/swe1-phase1-state/1", "epoch": epoch, "keys": {}}
    return st


def _save_state(ws: Path, st: dict) -> None:
    S.record(ws, STATE, st)


def _lines(ws: Path, rel: str) -> list[dict]:
    p = Path(ws) / ".forge-run/lrtx" / rel
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []


def _append(ws: Path, rel: str, rec: dict) -> None:
    p = Path(ws) / ".forge-run/lrtx" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def verdicts(ws: Path) -> dict[tuple[str, str], dict]:
    """(task|key, content sha) -> the verdict of that requirement content (the latest recorded)."""
    return {(v["tk"], v["sha"]): v for v in _lines(ws, VERDICTS)}


def reply(ws: Path, step: str, status: str, issues: list[str]) -> dict:
    doc = {"status": status, "artifacts": [], "issues": [i[:V.ISSUE_MAX] for i in issues[:20]],
           "next_action": "next" if status != "CONTINUE" else "continue"}
    S.record(ws, f"SWE.1/{step}-reply.json", doc)
    return doc


# ---- packets -------------------------------------------------------------------------------------------------------
def _contexts(ws: Path) -> dict[str, list[dict]]:
    """task -> the reference-manual sources its requirements cite (register section; functional chapter)."""
    from . import swe1

    ws = Path(ws)
    out: dict[str, list[dict]] = {}
    try:
        for g in swe1.groups(swe1.inventory(ws)):
            out[f"requirements:{g['id']}"] = [S.source(ws, g["file"])]
    except (ValueError, OSError, KeyError):  # judged from its own text and the scope when no source loads
        out = {}
    secs = swe1._section_files(ws) if (ws / "inputs/index.md").is_file() else {}
    from ..layer import profile

    try:
        chapter = str(profile(ws)["rm"]["chapter"])
        func = [n for n, s in secs.items() if n.startswith(chapter + ".") and "functional" in s["title"].lower()]
        out["requirements:crosscutting"] = [S.source(ws, secs[n]["file"], max_chars=swe1.FUNCTIONAL_SOURCE_MAX_CHARS)
                                            for n in func[:1]]
    except Exception:  # noqa: BLE001
        out.setdefault("requirements:crosscutting", [])
    return out


def _scope_text(ws: Path) -> str:
    m = json.loads((Path(ws) / ".forge-run/manifest.json").read_text())
    return " | ".join(m.get("scope") or [])


# WO-F014-SWE1-WWDGL-20261109-L44E (SWR-017): the register-field convention made the inspector ask a cross-cutting
# requirement to name WWDG_SR.EWIF; the consistency rule then refused the rework (a cross-cutting requirement may not act
# on a register a register task covers), so the requirement could never converge.
CROSSCUT_CONVENTION = ("this is a cross-cutting requirement (reset/startup behaviour, failure handling, rules for all "
                       "functions): it states a rule over the driver and must NOT name a register field that a register "
                       "task covers - never ask it to name one.")


def iq_packet(ws: Path, ref: dict, model: str, sources: list[dict], findings=None, previous=None) -> dict:
    from ..workflow import prompts
    from . import review as R
    from . import swe1

    cl = quality_checklist()
    sysname = swe1.system_name(ws)
    instr = (f"Judge ONE software requirement of the {sysname} on its own against the individual quality criteria "
             "IQ-01..IQ-12 (Forge-C SWE.1 requirements quality guideline). The requirement is the CURRENT ARTIFACT "
             f"'requirement' ({ref['swr']}); the CURRENT ARTIFACT 'task_requirements' lists the other requirements of "
             "the same author task as read-only context for IQ-09 consistency - never judge them. Judge the "
             "statement, its source_page citation, its verification and its effects against the provided reference-"
             "manual source and the work-order scope. Report a finding only for a real defect of this requirement: "
             "quality_id, severity (BLOCKING: unsupported or invented behaviour, contradiction, unverifiable mandatory "
             "behaviour, missing critical source; CORRECTABLE: resolvable from the provided inputs, e.g. imprecision, "
             "combined obligations, ambiguous term; EDITORIAL: no technical change; N/A: the property does not apply, "
             "give the reason), evidence quoting the requirement or the source, required_action, and "
             "input_uncertainty true when the defect is a missing or contradictory input rather than the author's. "
             "A requirement without defects has an empty findings list. Project conventions (not defects): EARS with "
             f"exactly one 'shall' and the subject 'the {sysname}'; source_page is the RM0486 page of the cited fact; "
             + (CROSSCUT_CONVENTION if ref["task"] == "requirements:crosscutting" else
                "requirements of a header-only LL driver name register fields as REGISTER.FIELD.")
             + " Work-order scope: " + _scope_text(ws))
    if R.out_of_context(ws):
        instr += " " + prompts.OUT_OF_CONTEXT_NOTE
    art = [{"path": "lrtx:requirement", "text": json.dumps(ref["obj"], indent=1, sort_keys=True)},
           {"path": "lrtx:task_requirements",
            "text": "\n".join(f"- [{r['key']}] {r['statement']}" for r in ref["siblings"]) or "(none)"}]
    for a in art:
        a["sha256"] = sha256_bytes(a["text"].encode())
    crit = [f"{i['id']} {i['property']}: {i['criterion']}" for i in cl["individual"]]
    return S.packet(phase="SWE.1", task=f"iq:{ref['task']}:{ref['key']}", role="swe1-inspector", instructions=instr,
                    sources=sources, artifacts=art, criteria=crit, output_schema=verdict_schema(ref["swr"]),
                    model=model, findings=findings, previous=previous, output_reserve=4096,
                    assessment_workspace=Path(ws), sampling=R.inspector_sampling(ws, model))


def validate_iq(doc: dict, ref: dict) -> list[str]:
    out = []
    if doc.get("requirement_id") != ref["swr"]:
        out.append(f"requirement_id must be {ref['swr']}")
    for i, f in enumerate(doc.get("findings") or []):
        if f.get("severity") == "N/A" and not str(f.get("evidence") or "").strip():
            out.append(f"findings[{i}]: N/A needs the reason in evidence")
        if needs_rework(f) and not str(f.get("required_action") or "").strip():
            out.append(f"findings[{i}]: a {f['severity']} finding states the required_action")
    return out


def rework_packet(ws: Path, ref: dict, model: str, sources: list[dict], fixes: list[str], findings=None,
                  previous=None) -> dict:
    from . import swe1

    sysname = swe1.system_name(ws)
    req = swe1._req_schema(ws)
    obl = swe1.owner_obligations(ws)
    if obl is not None:
        ids = [o["id"] for o in obl["obligations"]]
        req = {**req, "required": req["required"] + ["obligations"],
               "properties": {**req["properties"], "obligations": {"type": "array", "items": {"type": "string",
                                                                                               "enum": ids}}}}
    schema = {"type": "object", "additionalProperties": False, "required": ["requirement"],
              "properties": {"requirement": req}}
    instr = (f"Rework ONE software requirement of the {sysname}: the CURRENT ARTIFACT 'requirement' (key "
             f"'{ref['key']}', task {ref['task']}). Resolve exactly the inspection findings below and nothing else; "
             f"keep the key '{ref['key']}'. Answer only this requirement as `requirement`; the other requirements of "
             "the task (CURRENT ARTIFACT 'task_requirements', read-only) stay as they are and are not part of your "
             "answer, so never move their content into this one. Each statement uses EARS (The/When/While/Where/"
             f"If..then), exactly one 'shall', the subject 'the {sysname}', and ends with a period; name fields as "
             "REGISTER.FIELD; source_page is the RM0486 page of the cited fact; verification states the test and its "
             "pass criterion ('... passes when ...'); " + swe1.effect_rule(ws) + " Author rules: " + swe1.REGISTER_RULES
             + (" " + CROSSCUT_CONVENTION.replace("never ask it to name one", "do not add one")
                if ref["task"] == "requirements:crosscutting" else "")
             + " INSPECTION FINDINGS TO RESOLVE: " + " | ".join(fixes) + " Work-order scope: " + _scope_text(ws))
    art = [{"path": "lrtx:requirement", "text": json.dumps(ref["obj"], indent=1, sort_keys=True)},
           {"path": "lrtx:task_requirements",
            "text": "\n".join(f"- [{r['key']}] {r['statement']}" for r in ref["siblings"]) or "(none)"}]
    for a in art:
        a["sha256"] = sha256_bytes(a["text"].encode())
    return S.packet(phase="SWE.1", task=f"iqfix:{ref['task']}:{ref['key']}", role="swe1-author", instructions=instr,
                    sources=sources, artifacts=art,
                    criteria=["only this requirement, same key", "every finding resolved", "EARS, one 'shall'"],
                    output_schema=schema, model=model, findings=findings, previous=previous)


# ---- steps ---------------------------------------------------------------------------------------------------------
def _budget(ws: Path, phase: str, resume: bool, time_budget_s: float | None) -> dict:
    budget, _ = V.open_visit(ws, phase, resume, lambda: [], MAX_CALLS, time_budget_s)
    return budget


def iq_inspect(ws: Path, model: str, resume: bool = False, time_budget_s: float | None = None) -> dict:
    """Judge every requirement whose current content has no verdict yet (one structured call each)."""
    ws = Path(ws)
    if not _author_passed(ws):
        return reply(ws, "iq-inspect", "PASS", ["PHASE1_SKIPPED: the SWE.1 author reply is not PASS"])
    st, refs, done = _state(ws), requirements(ws), verdicts(ws)
    srcs = _contexts(ws)
    budget = _budget(ws, INSPECT, resume, time_budget_s)
    issues = []
    try:
        for ref in refs:
            k = st["keys"].setdefault(_tk(ref), {"reworks": 0, "stopped": None})
            if k["stopped"] or (_tk(ref), ref["sha"]) in done:
                continue
            sources = srcs.get(ref["task"], [])
            rec = V.run_task(ws, INSPECT, f"iq:{ref['task']}:{ref['key']}:{ref['sha'][:12]}",
                             lambda fi, pr, ref=ref, sources=sources: iq_packet(ws, ref, model, sources, fi, pr),
                             lambda d, ref=ref: validate_iq(d, ref), budget)
            if rec["status"] == "VALID":
                fs = rec["doc"]["findings"]
                v = {"tk": _tk(ref), "swr": ref["swr"], "task": ref["task"], "key": ref["key"], "sha": ref["sha"],
                     "round": k["reworks"] + 1, "findings": fs, "passed": not any(needs_rework(f) for f in fs),
                     "at": utc_now()}
                _append(ws, VERDICTS, v)
                done[(v["tk"], v["sha"])] = v
            elif budget.get("outage"):
                break
            else:
                k["stopped"] = "VERDICT_INVALID"
                issues.append(f"{ref['swr']}: PHASE1_VERDICT_INVALID: {(rec.get('errors') or ['?'])[0]}"[:300])
    except V.Continue as c:
        _save_state(ws, st)
        return reply(ws, "iq-inspect", "CONTINUE", [f"time box used; the next node execution resumes at {c}"])
    _save_state(ws, st)
    V.close_visit(budget)
    summary(ws)
    if budget.get("outage"):
        return reply(ws, "iq-inspect", "FAILED", [f"PHASE1_OUTAGE: {str(budget['outage'])[:200]}"])
    return reply(ws, "iq-inspect", "PASS", issues)


def _latest(ws: Path, ref: dict, done: dict) -> dict | None:
    return done.get((_tk(ref), ref["sha"]))


def pending_rework(ws: Path) -> list[dict]:
    """Requirements whose current content failed its verdict, that the author made and that have rounds left."""
    ws = Path(ws)
    if not _author_passed(ws) or not (ws / ".forge-run/lrtx/SWE.1/assembly.json").is_file():
        return []
    st, done = _state(ws), verdicts(ws)
    rounds = int(quality_checklist()["phase1"]["rounds"])
    out = []
    for ref in requirements(ws):
        k = st["keys"].get(_tk(ref)) or {"reworks": 0, "stopped": None}
        v = _latest(ws, ref, done)
        if v and not v["passed"] and not k["stopped"] and not ref["generated"] and k["reworks"] < rounds:
            out.append({**ref, "verdict": v})
    return out


def iq_rework(ws: Path, model: str, resume: bool = False, time_budget_s: float | None = None) -> dict:
    """Rework each flagged requirement alone; code splices the answer in (swe1.replace_requirement)."""
    from . import swe1

    ws = Path(ws)
    if not _author_passed(ws):
        return reply(ws, "iq-rework", "PASS", ["PHASE1_SKIPPED: the SWE.1 author reply is not PASS"])
    st = _state(ws)
    todo = pending_rework(ws)
    srcs = _contexts(ws)
    budget = _budget(ws, REWORK, resume, time_budget_s)
    changed, issues = 0, []
    try:
        for ref in todo:
            k = st["keys"].setdefault(_tk(ref), {"reworks": 0, "stopped": None})
            fixes = [finding_text(f) for f in ref["verdict"]["findings"] if needs_rework(f)]
            sources = srcs.get(ref["task"], [])

            def check(d, ref=ref):
                errs, _state_ = swe1.splice(ws, ref["task"], ref["key"], (d or {}).get("requirement"))
                return errs
            rec = V.run_task(ws, REWORK, f"iqfix:{ref['task']}:{ref['key']}:{ref['sha'][:12]}",
                             lambda fi, pr, ref=ref, fixes=fixes, sources=sources:
                             rework_packet(ws, ref, model, sources, fixes, fi, pr), check, budget)
            if rec["status"] != "VALID" and budget.get("outage"):
                break
            k["reworks"] += 1
            entry = {"tk": _tk(ref), "swr": ref["swr"], "round": k["reworks"], "before": ref["sha"], "at": utc_now()}
            if rec["status"] != "VALID":
                k["stopped"] = "REWORK_INVALID"
                _append(ws, REWORKS, {**entry, "status": "INVALID", "errors": (rec.get("errors") or [])[:5]})
                continue
            new = rec["doc"]["requirement"]
            after = sha256_bytes(canonical_json(new))
            if after == ref["sha"]:
                k["stopped"] = "NO_CHANGE"
                _append(ws, REWORKS, {**entry, "status": "UNCHANGED", "after": after})
                continue
            try:
                swe1.replace_requirement(ws, ref["task"], ref["key"], new)
            except ValueError as exc:
                k["stopped"] = str(exc).split(":", 1)[0]
                _append(ws, REWORKS, {**entry, "status": "REFUSED", "after": after, "errors": [str(exc)[:300]]})
                continue
            changed += 1
            _append(ws, REWORKS, {**entry, "status": "CHANGED", "after": after})
            _save_state(ws, st)
    except V.Continue as c:
        _save_state(ws, st)
        return reply(ws, "iq-rework", "CONTINUE", [f"time box used; the next node execution resumes at {c}"])
    _save_state(ws, st)
    V.close_visit(budget)
    summary(ws)
    if budget.get("outage"):
        return reply(ws, "iq-rework", "FAILED", [f"PHASE1_OUTAGE: {str(budget['outage'])[:200]}"])
    return reply(ws, "iq-rework", "PASS", issues + [f"PHASE1_REWORKED:{changed}"])


def iq_check(ws: Path) -> int:
    """0 = a requirement needs rework (the graph goes to iq-rework), 1 = phase 1 is done (the freeze gate)."""
    ws = Path(ws)
    p = ws / ".forge-run/lrtx/SWE.1/iq-inspect-reply.json"
    status = json.loads(p.read_text()).get("status") if p.is_file() else "MISSING"
    if status != "PASS":
        return 1  # skipped, outage or failed: phase 1 ends; its findings are what was recorded
    try:
        return 0 if pending_rework(ws) else 1
    except (ValueError, OSError, KeyError):
        return 1


def summary(ws: Path) -> dict:
    """phase1/summary.json: the input of the set phase (carried findings) and the owner's view (US3)."""
    ws = Path(ws)
    cl = quality_checklist()
    st, done = _state(ws), verdicts(ws)
    refs = requirements(ws)
    rows, carried = [], []
    for ref in refs:
        k = st["keys"].get(_tk(ref)) or {"reworks": 0, "stopped": None}
        v = _latest(ws, ref, done)
        open_fs = [f for f in (v or {}).get("findings", []) if needs_rework(f, cl)]
        state = "PENDING" if v is None else ("PASSED" if v["passed"] else (
            "REWORK" if not k["stopped"] and not ref["generated"] and k["reworks"] < cl["phase1"]["rounds"]
            else "CARRIED"))
        rows.append({"swr": ref["swr"], "task": ref["task"], "key": ref["key"], "state": state,
                     "reworks": k["reworks"], "stopped": k["stopped"], "open": len(open_fs)})
        if state == "CARRIED":
            carried += [{"requirement_id": ref["swr"], **f} for f in open_fs]
    out = {"schema": "forge-c/swe1-phase1-summary/1", "at": utc_now(), "epoch": st["epoch"],
           "guideline_sha256": cl["guideline"]["sha256"], "rounds": cl["phase1"]["rounds"],
           "requirements": len(refs), "passed": sum(r["state"] == "PASSED" for r in rows),
           "carried": sum(r["state"] == "CARRIED" for r in rows), "pending": sum(r["state"] == "PENDING" for r in rows),
           "rework": sum(r["state"] == "REWORK" for r in rows), "rows": rows, "carried_findings": carried}
    S.record(ws, SUMMARY, out)
    report(ws)
    return out


REPORT = "SWE.1/quality-report.md"


def report(ws: Path) -> str:
    """Feature 018 US3: the owner's view of both phases - per requirement (phase 1) and per criterion (phase 2).
    Findings and counts only; no prompt or model reasoning."""
    ws = Path(ws)
    base = ws / ".forge-run/lrtx"
    p1 = json.loads((base / SUMMARY).read_text()) if (base / SUMMARY).is_file() else None
    p2p = base / "SWE.1/phase2/set-quality.json"
    p2 = json.loads(p2p.read_text()) if p2p.is_file() else None
    lines = ["# SWE.1 quality inspection (two phases)", ""]
    if p1 and "rows" in p1:
        lines += ["## Phase 1 - each requirement on its own (IQ-01..IQ-12)", "",
                  f"Requirements {p1['requirements']}: passed {p1['passed']}, carried {p1['carried']}, "
                  f"rework pending {p1['rework']}, not judged {p1['pending']} (rounds per requirement: {p1['rounds']}).",
                  "", "| SWR | Task | State | Reworks | Open findings | Stop |", "| --- | --- | --- | --- | --- | --- |"]
        lines += [f"| {r['swr']} | {r['task']} | {r['state']} | {r['reworks']} | {r['open']} | {r['stopped'] or ''} |"
                  for r in p1["rows"]]
        if p1["carried_findings"]:
            lines += ["", "Carried to the set phase:", ""]
            lines += [f"- {f['requirement_id']} {f['quality_id']} {f['severity']}: {f['evidence']}"
                      for f in p1["carried_findings"]]
        lines.append("")
    if p2:
        lines += ["## Phase 2 - the complete set (SQ-01..SQ-10; the gate is SWE1-01..08)", "",
                  f"Baseline {p2['baseline_id']}.", "", "| Criterion | Findings | To checklist item |",
                  "| --- | --- | --- |"]
        from .review import SQ_ITEMS

        for sq, fs in sorted(p2["findings"].items()):
            lines.append(f"| {sq} | {len(fs)} ({', '.join(sorted({f['severity'] for f in fs})) or 'none'}) | "
                         f"{SQ_ITEMS.get(sq, '')} |")
        lines += [f"- {u}" for u in p2.get("unjudged") or []]
        lines.append("")
    text = "\n".join(lines) + "\n"
    out = base / REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return text
