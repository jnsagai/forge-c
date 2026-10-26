"""Deterministic Fabro command-node gates for the SWE author/inspector loops (T009/T047).

Invoked by generated workflows with the agent's final response on stdin (`stdin_source`):

  gate --step author  --phase SWE.n : parse compact result; freeze baseline; exit 0 -> inspector
  gate --step inspect --phase SWE.n : parse compact result; require recorded inspection of the
                                       current baseline; exit 0 only on PASS
  gate --step route   --phase SWE.n : exit 0 -> rework (author), exit 1 -> BLOCKED finalizer
  gate --step verify  --phase SWE.3 --check hal_guideline : deterministic verification node

Exit codes map to Fabro outcomes (0 succeeded / non-zero failed) and conditional edges. Agents can
never route themselves (routing keys are rejected by the T008 parser).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path

from ..common import pretty_json, utc_now
from ..contracts.agent_output import parse
from ..events.emit import emit
from .engine import InspectionError, Store


def fail_code(ws: Path, phase: str, step: str) -> int:
    """Distinct non-zero exit per failed attempt (Fabro 0.362 trips its cycle breaker on identical signatures;
    the deterministic route gate is the authoritative loop bound)."""
    log = ws / ".forge-run" / "gates" / "gate-log.jsonl"
    n = 0
    if log.is_file():
        n = sum(1 for x in log.read_text().splitlines() if f'"phase": "{phase}"' in x and f'"step": "{step}"' in x)
    return 10 + min(n, 200)


def _state(ws: Path, phase: str, payload: dict) -> None:
    d = ws / ".forge-run" / "gates"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "gate-log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": utc_now(), "phase": phase, **payload}, sort_keys=True) + "\n")


def _last_gate_ts(ws: Path, phase: str) -> str:
    log = ws / ".forge-run" / "gates" / "gate-log.jsonl"
    ts = ""
    if log.is_file():
        for x in log.read_text().splitlines():
            if f'"phase": "{phase}"' in x:
                ts = json.loads(x).get("ts", ts)
    return ts


# A prose reply that says it did not finish is honoured as a failure (never frozen on evidence alone).
FAILURE_SIGNAL = re.compile(r"\b(BLOCKED|REWORK|TURN_BUDGET\w*|turn budget|could ?n[o']t|cannot|unable to|incomplete|"
                            r"not (?:yet )?(?:done|complete|completed|finished|written))\b", re.I)


def _trailing_contract(text: str):
    """A prose reply that ENDS with a valid compact contract object (e.g. 'Done.\n{"status":"PASS",...}')."""
    i = text.rfind("\n{")
    i = i + 1 if i >= 0 else text.find("{")
    if i < 0:
        return None
    tail = parse(text[i:].strip())
    return tail if tail.ok else None


def _unaddressed_defects(store: Store, phase: str) -> list[str]:
    """r73: the SWE.3 fix author replied in prose without changing a file; the gate re-froze the SAME baseline, the
    unchanged inspection passed and DEF-002 became FIXED with nothing fixed. An IN_FIX defect of this phase needs a
    changed work product (fixed) or reject_defect with a reason (REJECTED) before the phase is frozen again."""
    from . import defects

    bl = store.latest_baseline(phase)
    if bl is None or store.current_hash(phase) != bl["baseline_hash"]:
        return []
    out = []
    for d in defects.all_defects(store.workspace):
        if d["status"] == "IN_FIX" and d["target_phase"] == phase:
            taken = next((h["ts"] for h in reversed(d["history"]) if h["status"] == "IN_FIX"), "")
            if bl["frozen_at"] <= taken:
                out.append(f"DEFECT_NOT_ADDRESSED:{d['id']}: no {phase} file changed since the defect was handed "
                           "to you; fix it, or reject_defect with the reason it is not a defect")
    return out


def _structured_task_issues(store: Store, res) -> list[str]:
    """Feature 010 (explicit local profile only): a structured author visit that failed before anything could be
    assembled reports its deterministic task validation issues; they join the rejection record so that the STUCK
    signature and the progress rule compare real progress instead of the same presence failure every time. Work
    orders without a local profile never reach this (their rejection records are unchanged)."""
    try:
        if not json.loads((store.workspace / ".forge-run/manifest.json").read_text()).get("local_profile"):
            return []
    except (OSError, ValueError):
        return []
    if not (res.ok and res.status == "FAILED"):
        return []
    return [f"LRTX_TASK_INVALID:{str(i)[:200]}" for i in res.issues]


def step_author(store: Store, phase: str, text: str) -> int:
    res = parse(text)
    prose_violation = None
    if not res.ok:
        tail = _trailing_contract(text)
        if tail is not None:  # contract violation is recorded, the contract object itself is honoured
            prose_violation, res = res.errors, tail
    generated: list[str] = []
    if phase == "SWE.1" and (store.workspace / "workproducts/SWE.1/software_requirements.md").is_file():
        from .reqif_export import export as reqif_export  # deterministic ReqIF, part of the frozen baseline

        rq = reqif_export(store.workspace)
        generated += [f"REQIF:{i}" for i in rq["issues"]]
        from .test_mapping import startup_on_host  # CAPA-059: startup invariants are target-observed (Robot)

        generated += startup_on_host(store.workspace)
    if phase == "SWE.2" and (store.workspace / "workproducts/SWE.2/architecture_static.puml").is_file():
        from .views import check_views  # PlantUML views: syntax/content checked and SVGs rendered before freeze

        generated += check_views(store.workspace, render=True)["major_findings"]
    from ..layer import swtrace_enabled

    if phase != "SWE.1" and swtrace_enabled(store.workspace):  # owner addendum 2026-10-17: trace relations of this phase
        from .swtrace import check_phase

        generated += check_phase(store.workspace, phase)["major_findings"]
    from ..layer import layer_of, register_contract_enabled

    if register_contract_enabled(store.workspace):  # owner decision 2026-10-19 (B): the oracle's register contract
        from ..assurance import register_contract as RC

        lay = layer_of(store.workspace)
        if phase == "SWE.1":
            generated += RC.check_effects(store.workspace, "LL" if lay == "LL" else "HAL")
        elif phase == "SWE.2":
            generated += RC.check_calls(store.workspace)
        elif phase == "SWE.3":
            from ..layer import hal_h, ll_header

            hdr = Path(ll_header(store.workspace) if lay == "LL" else hal_h(store.workspace)).name  # feature 009
            generated += RC.check_compiles(store.workspace, [store.workspace / "software/hal",
                                                             store.workspace / "software/ll"], hdr)
    from ..assurance.scope import workspace_scope_findings  # CAPA-044: stated safety level = owner scope

    generated += workspace_scope_findings(store.workspace, phase)
    missing = store.missing_outputs(phase) if os.environ.get("FORGE_GATE_PRESENCE", "1") == "1" else []
    missing += generated
    missing += _structured_task_issues(store, res)
    from . import defects  # ADR-0008: a fixed upstream defect is verified with the SAME, unchanged tests

    missing += defects.verify_on_freeze(store.workspace, phase)
    missing += _unaddressed_defects(store, phase)
    if phase in ("SWE.4", "SWE.5", "SWE.6"):  # L4 anti-bending: a test edited until it passes must be declared
        try:  # L13: adaptation to an upstream fix (test passed before the fix) is declared by the gate
            for d in defects.declare_post_fix_adaptations(store.workspace, phase):
                _state(store.workspace, phase, {"step": "test_declaration", "result": "GATE_DECLARED",
                                                "defect": d["id"], "fix": d["gate_declared"]["fix_defect"]})
        except defects.DefectError as exc:
            _state(store.workspace, phase, {"step": "test_declaration", "result": "REFUSED", "error": str(exc)[:200]})
        missing += [f"{i} (restore the test and report_defect the upstream fault, or declare the correction with "
                    "report_defect kind TEST)" for i in defects.bent_tests(store.workspace, phase)]
    if missing:  # deterministic presence gate: nothing is frozen while required outputs/tool passes are missing
        _state(store.workspace, phase, {"step": "author", "result": "REJECTED", "status": "INCOMPLETE",
                                        "issues": missing[:20]})
        print(json.dumps({"rejected": "MISSING_REQUIRED_OUTPUTS", "issues": missing[:10]}))
        return fail_code(store.workspace, phase, "author")
    if res.ok and res.status != "PASS":  # the author itself reports it could not complete: honour it (rework)
        _state(store.workspace, phase, {"step": "author", "result": "REJECTED", "status": res.status,
                                        "issues": res.issues})
        return fail_code(store.workspace, phase, "author")
    if not res.ok:
        # Agent messages are never evidence. An empty/prose reply is a recorded contract violation; progress then
        # depends ONLY on deterministic evidence: a baseline frozen during this stage that still matches the files.
        bl = store.latest_baseline(phase)
        fresh = bl is not None and bl["frozen_at"] > _last_gate_ts(store.workspace, phase) \
            and store.stale_reason(phase, bl) is None
        if not fresh and text.strip() and not FAILURE_SIGNAL.search(text):
            # ADR-0008 L10 (owner decision 2026-10-15): a non-empty reply in the wrong FORMAT does not cost a rework
            # cycle when the deterministic presence gate above already passed (all outputs present, required tools
            # PASS, no stale/bent tests). The baseline is frozen and the independent inspection decides; the
            # violation stays recorded. A reply that signals failure, or an empty reply (dead session), is rejected.
            try:
                bl = store.freeze(phase, f"swe{phase[-1]}-author")
            except InspectionError as exc:
                _state(store.workspace, phase, {"step": "author", "result": "FREEZE_FAILED", "error": str(exc)})
                return fail_code(store.workspace, phase, "author")
            _state(store.workspace, phase, {"step": "author", "result": "FROZEN_BY_EVIDENCE",
                                            "baseline_id": bl["baseline_id"],
                                            "finding": "AGENT_OUTPUT_CONTRACT_VIOLATION", "errors": res.errors})
            print(json.dumps({"baseline_id": bl["baseline_id"], "agent_output": "CONTRACT_VIOLATION_RECORDED"}))
            return 0
        if not fresh or bl is None:
            _state(store.workspace, phase, {"step": "author", "result": "REJECTED", "errors": res.errors,
                                            "status": res.status, "issues": res.issues})
            return fail_code(store.workspace, phase, "author")
        _state(store.workspace, phase, {"step": "author", "result": "FROZEN_BY_TOOL_EVIDENCE",
                                        "baseline_id": bl["baseline_id"],
                                        "finding": "AGENT_OUTPUT_CONTRACT_VIOLATION", "errors": res.errors})
        print(json.dumps({"baseline_id": bl["baseline_id"], "agent_output": "CONTRACT_VIOLATION_RECORDED"}))
        return 0
    try:
        bl = store.freeze(phase, f"swe{phase[-1]}-author")
    except InspectionError as exc:
        _state(store.workspace, phase, {"step": "author", "result": "FREEZE_FAILED", "error": str(exc)})
        return fail_code(store.workspace, phase, "author")
    _state(store.workspace, phase, {"step": "author", "result": "FROZEN", "baseline_id": bl["baseline_id"]}
           | ({"finding": "AGENT_OUTPUT_CONTRACT_VIOLATION", "errors": prose_violation} if prose_violation else {}))
    print(json.dumps({"baseline_id": bl["baseline_id"], "baseline_hash": bl["baseline_hash"]}))
    return 0


def step_inspect(store: Store, phase: str, text: str) -> int:
    res = parse(text)
    g = store.gate(phase)
    _state(store.workspace, phase, {"step": "inspect", "agent_status": res.status, "agent_ok": res.ok,
                                    "gate": g})
    print(json.dumps(g))
    from ..assurance import observe  # EASA-T022: observe-only assurance gate; never changes this decision

    observe.phase(store.workspace, phase, g)
    # The agent's own PASS is never sufficient: the recorded, deterministic gate decision rules.
    if g["decision"] == "PASS":
        from . import defects

        bl = store.latest_baseline(phase)
        fixed = defects.mark_fixed(store.workspace, phase, bl["baseline_id"] if bl else "")
        if fixed:
            _state(store.workspace, phase, {"step": "defects", "result": "FIXED", "defects": fixed})
    return 0 if g["decision"] == "PASS" else fail_code(store.workspace, phase, "inspect")




def _epoch_lines(ws: Path, phase: str, since: str) -> list[str]:
    log = ws / ".forge-run" / "gates" / "gate-log.jsonl"
    if not log.is_file():
        return []
    return [x for x in log.read_text().splitlines()
            if f'"phase": "{phase}"' in x and json.loads(x).get("ts", "") >= since]


def _count(ws: Path, phase: str, step: str, since: str = "") -> int:
    return sum(1 for x in _epoch_lines(ws, phase, since) if f'"step": "{step}"' in x)


def author_rejections(ws: Path, phase: str, since: str = "") -> int:
    return sum(1 for x in _epoch_lines(ws, phase, since) if '"step": "author"' in x and '"REJECTED"' in x)


def _rejection_signature(line: str) -> tuple | None:
    """Deterministic gate codes of an author rejection (None when it holds agent-output or free-text issues)."""
    d = json.loads(line)
    iss = [str(x) for x in (d.get("issues") or d.get("errors") or [])]
    codes = tuple(sorted(i for i in iss if re.match(r"^[A-Z][A-Z0-9_]+(:|$)", i) and not i.startswith("AGENT_OUTPUT")))
    return codes if codes and len(codes) == len(iss) else None


def stuck_signature(ws: Path, phase: str, since: str = "") -> tuple | None:
    """CAPA-014: the last two author attempts of this epoch were rejected with the identical deterministic codes.
    Over all recorded runs (r10-r82) this never recovered on the next cycle (0 of 14), so the remaining cycle is
    not spent: the phase stops early (the L11 safety net still runs) and the failure goes to the CAPA process."""
    rows = [x for x in _epoch_lines(ws, phase, since) if '"step": "author"' in x]
    if len(rows) < 2 or '"REJECTED"' not in rows[-1] or '"REJECTED"' not in rows[-2]:
        return None
    a, b = _rejection_signature(rows[-2]), _rejection_signature(rows[-1])
    return b if a is not None and a == b else None


EXTENSION_POLICY = "config/factory/rework-policy.yaml"
_ITEM = re.compile(r"\b[A-Z][A-Z0-9]{1,7}(?:-[A-Z0-9]+)*-\d+\b")  # UT-007, SWR-006, USPEC-HAL-09-01, DEF-004


def extra_cycles() -> int:
    """Owner decision 2026-10-18 (rework-policy.yaml): extra failed cycles allowed while a phase progresses; 0 when
    the policy is absent or unreadable (fail closed to the authored checklist maximum)."""
    from ..common import REPO_ROOT, load_yaml

    try:
        return max(0, min(5, int(load_yaml(REPO_ROOT / EXTENSION_POLICY)["progress_extension"]["max_extra_cycles"])))
    except (OSError, KeyError, TypeError, ValueError):
        return 0


def _issue_key(s: str) -> str:
    """An author-gate issue without line/column numbers (a warning that only moved is the same issue)."""
    return re.sub(r":\d+(?=:|$)", "", s)


def failed_cycles(store: Store, phase: str, since: str) -> list[dict]:
    """The phase's failed cycles of this epoch in time order: author gate rejections (issues without line numbers)
    and failed inspections (check id with the item ids its finding names), as multisets."""
    from collections import Counter

    cyc = []
    for x in _epoch_lines(store.workspace, phase, since):
        d = json.loads(x)
        if d.get("step") == "author" and d.get("result") == "REJECTED":
            iss = [_issue_key(str(i)) for i in (d.get("issues") or d.get("errors") or [])]
            cyc.append({"ts": d.get("ts", ""), "kind": "author", "items": Counter(iss), "n": len(iss)})
    for i in store.inspections(phase):
        if i.get("verdict") != "PASS" and i.get("recorded_at", "") >= since:
            fs = [f for f in i.get("findings") or [] if isinstance(f, dict)]
            keys = [str(f.get("id") or f.get("check_id") or "?") + "@" + ",".join(
                sorted(set(_ITEM.findall(str(f.get("detail") or ""))))) for f in fs]
            cyc.append({"ts": i.get("recorded_at", ""), "kind": "inspect", "items": Counter(keys), "n": len(keys)})
    return sorted(cyc, key=lambda c: c["ts"])


def progressing(store: Store, phase: str, since: str) -> dict:
    """Owner progress rule (rework-policy.yaml): the last failed cycle improved on the one before it."""
    cyc = failed_cycles(store, phase, since)
    if len(cyc) < 2:
        return {"progress": False, "why": "fewer than two failed cycles"}
    a, b = cyc[-2], cyc[-1]
    if a["kind"] == "author" and b["kind"] == "inspect":
        return {"progress": True, "why": "deterministic gates passed; reached inspection"}
    if a["kind"] != b["kind"]:
        return {"progress": False, "why": "regressed from inspection to an author gate rejection"}
    gone = sorted((a["items"] - b["items"]).elements())
    if gone and b["n"] <= a["n"]:
        return {"progress": True, "why": f"{len(gone)} item(s) resolved, {a['n']} -> {b['n']} findings",
                "resolved": gone[:6]}
    return {"progress": False, "why": f"no item resolved or findings grew ({a['n']} -> {b['n']})"}


def advisory_enabled(ws: Path) -> bool:
    """Owner decision 2026-10-26 ("Advisory + calibrate"): with the local profile's structured.advisory_continue, a
    phase whose whole bounded ladder is exhausted continues with its unresolved findings registered for the end-of-run
    human review instead of stopping the run. Without the flag nothing changes."""
    from ..lrtx.swe2 import _structured_flag

    return _structured_flag(ws, "advisory_continue")


def recovery_state(ws: Path, phase: str) -> dict:
    """The diagnosis-repair rung (DA-FR-054). Under AFO (an attempt id or a durable binding in the run) a phase first
    BLOCKs, so AFO recovery diagnoses and repairs it; only an attempt AFO launched after recovery for this phase was
    exhausted may continue in advisory mode. A plain local run has no recovery path: UNAVAILABLE."""
    m = ws / ".forge-run" / "manifest.json"
    afo = (json.loads(m.read_text()) if m.is_file() else {}).get("afo") or {}
    if not afo and not (ws / ".forge-run" / "durable-binding.json").is_file():
        return {"state": "UNAVAILABLE"}
    done = (afo.get("recovery_exhausted") or {}).get(phase)
    return {"state": "EXHAUSTED", **done} if done else {"state": "PENDING"}


def advisory_record(store: Store, phase: str, since: str, g: dict, cycles: int, budget: int, extension, stuck) -> Path:
    """The gap register entry: what stayed unresolved and every attempt the ladder made (a gap without its attempt
    record is not a gap). Appended per continuation to .forge-run/advisory/<phase>.jsonl."""
    last = next((i for i in reversed(store.inspections(phase)) if i.get("verdict") != "PASS"
                 and i.get("recorded_at", "") >= since), None)
    rejected = [json.loads(x) for x in _epoch_lines(store.workspace, phase, since)
                if '"step": "author"' in x and '"REJECTED"' in x]
    bl = store.latest_baseline(phase) or {}
    rec = {
        "schema": "forge-c/advisory-gap/1",
        "at": utc_now(),
        "phase": phase,
        "baseline_id": bl.get("baseline_id"),
        "baseline_hash": bl.get("baseline_hash"),
        "gate": {k: g.get(k) for k in ("decision", "reason", "failed_inspections", "max_rework_cycles")},
        "unresolved_findings": [{k: f.get(k) for k in ("id", "severity", "detail")}
                                for f in (last or {}).get("findings") or [] if isinstance(f, dict)][:50],
        "inspection_ref": (last or {}).get("inspection_id"),
        "author_issues": [str(i)[:300] for i in ((rejected[-1].get("issues") or rejected[-1].get("errors") or [])
                                                 if rejected else [])][:20],
        "attempts": {
            "failed_cycles": cycles,
            "budget": budget,
            "progress_extension": extension,
            "stuck_signature": list(stuck) if stuck else None,
            "history": [{"ts": c["ts"], "kind": c["kind"], "findings": c["n"]}
                        for c in failed_cycles(store, phase, since)],
        },
    }
    rec["attempts"]["ladder"] = _ladder(store, phase, cycles, budget, extension, stuck)
    out = store.workspace / ".forge-run" / "advisory" / f"{phase}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return out


def capa_rung(ws: Path, phase: str) -> dict:
    """The CAPA rung (DA-FR-054, KI-014-004): the CRE fingerprints of this phase's failures in this attempt and the CAPAs
    linked to them, so a gap names a CAPA that already describes (or fixes) its cause; an unreadable store says so."""
    try:
        from ..reliability.capa import CapaRegistry
        from ..reliability.observe import from_workspace
        from ..reliability.policy import load
        from ..reliability.store import CREStore

        fps = sorted({o["fingerprint"] for o in from_workspace(ws) if o.get("phase") == phase})
        reg = CapaRegistry(CREStore(), load())
        linked = [{"capa_id": c["capa_id"], "state": c["state"]} for c in reg.all()
                  if set(reg.links(c["capa_id"], "FINGERPRINT")) & set(fps)]
    except Exception as exc:  # noqa: BLE001 - the register records an unreadable store instead of failing the gate
        return {"rung": "capa_retrieval", "status": "UNKNOWN", "reason": type(exc).__name__}
    return {"rung": "capa_retrieval", "status": "MATCHED" if linked else "NONE_MATCHING", "capas": linked[:10],
            "fingerprints": fps[:10]}


def _ladder(store: Store, phase: str, cycles: int, budget: int, extension, stuck) -> list[dict]:
    """Every rung of the escalation ladder (owner 2026-10-26: gaps only after best effort) with what it did, so a gap
    never implies a rung that did not run. A rung that is not integrated yet says so."""
    m = store.workspace / ".forge-run" / "manifest.json"
    run_id = (json.loads(m.read_text()) if m.is_file() else {}).get("work_order")
    try:
        from ..knowledge.store import LessonStore

        lessons = LessonStore().exposures(run_id, phase) if run_id else []
        lesson_rung = {"rung": "validated_lessons", "status": "EXPOSED" if lessons else "NONE_QUALIFIED",
                       "lesson_ids": lessons[:20]}
    except Exception as exc:  # noqa: BLE001 - the register records an unreadable store instead of failing the gate
        lesson_rung = {"rung": "validated_lessons", "status": "UNKNOWN", "reason": type(exc).__name__}
    ext = (extension or {}) if isinstance(extension, dict) else {}
    return [
        {"rung": "rework_with_findings", "status": "RAN", "failed_cycles": cycles, "budget": budget},
        {"rung": "progress_extension", "status": ("GRANTED" if ext.get("progress") else "REFUSED") if ext
         else "NOT_EVALUATED"},
        lesson_rung,
        capa_rung(store.workspace, phase),
        {"rung": "diagnosis_repair", **{("status" if k == "state" else k): v
                                         for k, v in recovery_state(store.workspace, phase).items()}},
        {"rung": "stall_detection", "status": "STUCK" if stuck else "BUDGET_EXHAUSTED"},
    ]


def step_route(store: Store, phase: str) -> int:
    g = store.gate(phase)
    # rework budget counts failed inspections AND rejected author attempts (both are failed production cycles)
    # The route node is reached ONLY after a failed author/verify/inspection stage (including agent-session failures
    # where no gate could run), so each route invocation is one failed cycle.
    since = store.budget_start()  # per-epoch budget: an upstream loop gives every phase its authored maximum again
    prior_routes = _count(store.workspace, phase, "route", since)
    cycles = max(g["failed_inspections"] + author_rejections(store.workspace, phase, since), prior_routes + 1)
    # The authored maximum applies; Fabro's identical-signature breaker no longer fires because every failed gate
    # execution prints a distinct cycle marker (ADR-0005 #5, verified with a model-free loop probe).
    budget = int(g["max_rework_cycles"])
    stuck = stuck_signature(store.workspace, phase, since) if g["decision"] != "PASS" else None
    exhausted = cycles >= budget or stuck is not None
    extension = None
    if exhausted and stuck is None and g["decision"] != "PASS" and cycles < budget + extra_cycles():
        # owner decision 2026-10-18: one more cycle at a time, only while the phase measurably progresses
        extension = {"cycle": cycles - budget + 1, "of": extra_cycles(), **progressing(store, phase, since)}
        exhausted = not extension["progress"]
    from . import defects

    up = defects.open_from(store.workspace, phase)
    if not up and g["decision"] != "PASS" and exhausted:
        # ADR-0008 L11 safety net: about to BLOCK with nothing reported - file the CODE defect this phase's own
        # recorded test evidence proves (the author edited a correct failing check instead of reporting it, r67-r69)
        try:
            auto = defects.auto_code_defect(store.workspace, phase, store.run_started())
        except defects.DefectError as exc:
            _state(store.workspace, phase, {"step": "auto_defect", "result": "REFUSED", "error": str(exc)[:200]})
        else:
            if auto is not None:
                _state(store.workspace, phase, {"step": "auto_defect", "result": "FILED", "defect": auto["id"],
                                                "restored": auto.get("auto_filed", {}).get("restored_test_files", [])})
                emit("workflow", "WARN", f"{phase} route gate filed {auto['id']} (CODE, {', '.join(auto['requirement_ids'])}) "
                     "from recorded test evidence", phase=phase)
                up = defects.open_from(store.workspace, phase)
    if up:  # ADR-0008: the fault is upstream - do not burn this phase's rework cycles on code it cannot change
        g = {**g, "decision": "UPSTREAM", "reason": "open upstream defects: " + ", ".join(
            f"{d['id']}->{d['target_phase']}" for d in up)}
        _state(store.workspace, phase, {"step": "route", "gate": g})
        emit("workflow", "WARN", f"{phase} {g['reason']}", phase=phase)
        print(json.dumps(g))
        return 1
    if g["decision"] != "PASS" and exhausted:
        g = {**g, "decision": "BLOCKED", "reason": f"rework budget exhausted ({cycles} failed cycles)" if stuck is None
             else f"STUCK: identical deterministic rejection twice ({', '.join(stuck)[:120]}); stopped early"}
        if advisory_enabled(store.workspace) and store.latest_baseline(phase) and \
                recovery_state(store.workspace, phase)["state"] != "PENDING":
            # the ladder is exhausted (budget, progress extensions, stall detection) and nothing is upstream: register
            # the gap with its attempt record and continue; a phase without a frozen baseline cannot feed the next one
            ref = advisory_record(store, phase, since, g, cycles, budget, extension, stuck)
            g = {**g, "decision": "ADVISORY_CONTINUE", "reason": f"{g['reason']}; registered for human review",
                 "advisory_ref": str(ref.relative_to(store.workspace))}
    elif g["decision"] == "BLOCKED" and extension is not None and extension["progress"]:
        # CAPA-068 (RPR-072): Store.gate blocks at the checklist maximum of failed INSPECTIONS; a granted progress
        # extension (same bounded rule: cycles < budget + extra) is one more rework cycle, as for author rejections
        g = {**g, "decision": "REWORK", "reason": f"{g['reason']} (progress extension {extension['cycle']}/"
                                                  f"{extension['of']})"}
    if extension is not None:
        g = {**g, "progress_extension": extension}
    _state(store.workspace, phase, {"step": "route", "gate": g})
    if extension is not None and extension["progress"]:
        emit("workflow", "INFO", f"{phase} progress extension {extension['cycle']}/{extension['of']}: "
             f"{extension['why']}", phase=phase)
    if g["decision"] == "BLOCKED":
        emit("workflow", "WARN", f"{phase} rework budget exhausted -> BLOCKED", phase=phase)
        return 1
    if g["decision"] == "ADVISORY_CONTINUE":
        emit("workflow", "WARN", f"{phase} ladder exhausted -> ADVISORY_CONTINUE (gap registered)", phase=phase)
        return 1  # the failure path's advisory node continues the run
    return 0


def step_advisory(store: Store, phase: str) -> int:
    """Advisory node on the route's failure path: exit 0 (continue to the next phase) only right after this phase's
    route recorded ADVISORY_CONTINUE; otherwise 1, the existing upstream/finalize chain."""
    routes = [json.loads(x) for x in _epoch_lines(store.workspace, phase, store.budget_start()) if '"step": "route"' in x]
    return 0 if routes and routes[-1].get("gate", {}).get("decision") == "ADVISORY_CONTINUE" else 1


def step_upstream(store: Store, target: str) -> int:
    """Shared chain node `upstream_sweN` (ADR-0008): exit 0 routes the run to the owner of `target` when an OPEN
    defect targets it and the run's upstream-loop budget remains; otherwise fall through (next target / finalize)."""
    from . import defects

    taken = defects.take_upstream(store.workspace, target)
    _state(store.workspace, target, {"step": "upstream", "result": "LOOP" if taken else "NONE",
                                     "defects": [d["id"] for d in taken], "loops_used": defects.loops_used(
                                         store.workspace), "loop_budget": defects.UPSTREAM_LOOP_BUDGET})
    if taken:
        emit("workflow", "WARN", f"upstream loop to {target}: {', '.join(d['id'] for d in taken)}", phase=target)
    print(json.dumps({"target": target, "defects": [d["id"] for d in taken]}))
    return 0 if taken else 1


def step_triage(store: Store, target: str) -> int:
    """`swe{k}_triage_gate` (ADR-0008 L12): exit 0 -> the owner's fix step (some defect accepted, or the triage left
    the owner's baseline changed); exit 1 -> return chain: every defect was rejected, nothing is re-frozen."""
    from . import defects

    back = defects.rejected_loop_return(store.workspace)
    bl = store.latest_baseline(target)
    intact = bl is not None and store.stale_reason(target, bl) is None
    decision = "RETURN" if back and intact else "FIX"
    _state(store.workspace, target, {"step": "triage", "result": decision, "return_to": back if decision == "RETURN"
                                     else None, "baseline_intact": intact})
    if decision == "RETURN":
        emit("workflow", "WARN", f"{target} rejected every routed defect: returning to {back} without a cascade",
             phase=target)
    print(json.dumps({"target": target, "decision": decision, "return_to": back}))
    return 1 if decision == "RETURN" else 0


def step_return(store: Store, phase: str) -> int:
    """Return chain node `return_sweN`: exit 0 routes back to phase N's rework entry when the latest loop was
    rejected in full and N reported it; otherwise fall through (next phase / finalize)."""
    from . import defects

    back = defects.rejected_loop_return(store.workspace)
    if back == phase:
        _state(store.workspace, phase, {"step": "return", "result": "RESUME"})
    print(json.dumps({"phase": phase, "resume": back == phase}))
    return 0 if back == phase else 1


def step_verify(store: Store, phase: str, check: str) -> int:
    if check in ("delivery_inject", "delivery_check", "delivery"):  # feature 008 brownfield nodes
        from ..brownfield import gates as BG

        return BG.run(store, phase, check, _state, fail_code)
    if check == "hal_guideline":
        from .guideline import check_workspace
        from .implementation import check_implementation
        from .regmap import check_regmap

        rep = check_workspace(store.workspace)
        reg = check_regmap(store.workspace)  # register definitions vs RM0486 inputs (SWE3-08)
        imp = check_implementation(store.workspace)  # allocated design really implemented (SWE3-09)
        out = store.workspace / "verification" / "static" / "hal_guideline_conformance.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(pretty_json(rep))
        (out.parent / "register_map_conformance.json").write_text(pretty_json(reg))
        (out.parent / "implementation_completeness.json").write_text(pretty_json(imp))
        from .misra_matrix import build as misra_matrix

        misra_matrix(store.workspace)  # coverage record (not compliance) for the release policy
        verdict = "PASS" if rep["verdict"] == reg["verdict"] == imp["verdict"] == "PASS" else "FAIL"
        _state(store.workspace, phase, {"step": "verify", "check": check, "verdict": verdict,
                                        "violations": len(rep["violations"]),
                                        "register_map_findings": len(reg["major_findings"]),
                                        "implementation_findings": len(imp["major_findings"])})
        emit("workflow", "INFO" if verdict == "PASS" else "WARN",
             f"{phase} HAL guideline verification {rep['verdict']} violations={len(rep['violations'])}; "
             f"register map {reg['verdict']}; implementation {imp['verdict']}", phase=phase)
        print(json.dumps({"verdict": verdict, "violations": len(rep["violations"]),
                          "register_map_findings": reg["major_findings"][:10],
                          "implementation_findings": imp["major_findings"][:10],
                          "report": "verification/static/hal_guideline_conformance.json"}))
        return 0 if verdict == "PASS" else fail_code(store.workspace, phase, "verify")
    print(json.dumps({"error": f"unknown check {check}"}))
    return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", type=Path, default=Path("."))
    ap.add_argument("--phase", required=True, choices=[f"SWE.{i}" for i in range(1, 7)])
    ap.add_argument("--step", required=True, choices=["author", "inspect", "route", "verify", "upstream", "triage",
                                                      "return", "advisory"])
    ap.add_argument("--check", default="")
    a = ap.parse_args(argv)
    store = Store(a.workspace.resolve())
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _run_step(store, a)
    # r56: Fabro keeps only the first ~200 characters of the output in its failure signature, so the marker that
    # makes each failed execution distinct must come FIRST (a trailing marker was cut off on long outputs).
    if rc != 0:
        print(cycle_marker(store.workspace))
    sys.stdout.write(buf.getvalue())
    return rc


def _run_step(store: Store, a: argparse.Namespace) -> int:
    try:
        if a.step == "author":
            rc = step_author(store, a.phase, sys.stdin.read())
        elif a.step == "inspect":
            rc = step_inspect(store, a.phase, sys.stdin.read())
        elif a.step == "route":
            rc = step_route(store, a.phase)
        elif a.step == "upstream":
            rc = step_upstream(store, a.phase)
        elif a.step == "advisory":
            rc = step_advisory(store, a.phase)
        elif a.step == "triage":
            rc = step_triage(store, a.phase)
        elif a.step == "return":
            rc = step_return(store, a.phase)
        else:
            rc = step_verify(store, a.phase, a.check)
    except Exception as exc:  # noqa: BLE001 - any gate error is a failed (never passed) gate
        print(json.dumps({"gate_error": type(exc).__name__, "detail": str(exc)[:200]}))
        rc = 3
    return rc


def cycle_marker(ws: Path) -> str:
    """Distinct, digit-free text per failed gate execution. Fabro 0.362's deterministic failure-cycle breaker
    hashes node|category|output with digits normalised and kills the run at the 3rd identical signature; our
    rework loop is bounded by the route gate (authored maximum), so each cycle must not look identical."""
    log = ws / ".forge-run" / "gates" / "gate-log.jsonl"
    n = len(log.read_text().splitlines()) if log.is_file() else 0
    return "gate execution " + "".join(chr(ord("a") + int(d)) for d in str(n))


if __name__ == "__main__":
    raise SystemExit(main())
