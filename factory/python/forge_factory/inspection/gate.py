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
    if phase == "SWE.2" and (store.workspace / "workproducts/SWE.2/architecture_static.puml").is_file():
        from .views import check_views  # PlantUML views: syntax/content checked and SVGs rendered before freeze

        generated += check_views(store.workspace, render=True)["major_findings"]
    missing = store.missing_outputs(phase) if os.environ.get("FORGE_GATE_PRESENCE", "1") == "1" else []
    missing += generated
    from . import defects  # ADR-0008: a fixed upstream defect is verified with the SAME, unchanged tests

    missing += defects.verify_on_freeze(store.workspace, phase)
    if phase in ("SWE.4", "SWE.5", "SWE.6"):  # L4 anti-bending: a test edited until it passes must be declared
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
    from . import defects

    up = defects.open_from(store.workspace, phase)
    if not up and g["decision"] != "PASS" and cycles >= budget:
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
    if g["decision"] != "PASS" and cycles >= budget:
        g = {**g, "decision": "BLOCKED", "reason": f"rework budget exhausted ({cycles} failed cycles)"}
    _state(store.workspace, phase, {"step": "route", "gate": g})
    if g["decision"] == "BLOCKED":
        emit("workflow", "WARN", f"{phase} rework budget exhausted -> BLOCKED", phase=phase)
        return 1
    return 0


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
                                                      "return"])
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
