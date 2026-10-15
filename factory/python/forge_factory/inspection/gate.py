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
import json
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
    return 0 if g["decision"] == "PASS" else fail_code(store.workspace, phase, "inspect")


FABRO_SAFE_CYCLES = 2


def _count(ws: Path, phase: str, step: str) -> int:
    log = ws / ".forge-run" / "gates" / "gate-log.jsonl"
    if not log.is_file():
        return 0
    return sum(1 for x in log.read_text().splitlines() if f'"phase": "{phase}"' in x and f'"step": "{step}"' in x)


def author_rejections(ws: Path, phase: str) -> int:
    log = ws / ".forge-run" / "gates" / "gate-log.jsonl"
    if not log.is_file():
        return 0
    return sum(1 for x in log.read_text().splitlines()
               if f'"phase": "{phase}"' in x and '"step": "author"' in x and '"REJECTED"' in x)


def step_route(store: Store, phase: str) -> int:
    g = store.gate(phase)
    # rework budget counts failed inspections AND rejected author attempts (both are failed production cycles)
    # The route node is reached ONLY after a failed author/verify/inspection stage (including agent-session failures
    # where no gate could run), so each route invocation is one failed cycle.
    prior_routes = _count(store.workspace, phase, "route")
    cycles = max(g["failed_inspections"] + author_rejections(store.workspace, phase), prior_routes + 1)
    # Fabro 0.362 terminates a run at the 3rd identical deterministic failure signature (numbers normalised), which
    # would bypass the in-graph finalizer; block at 2 failed cycles (within the authored maximum of 3, ADR-0005).
    budget = min(int(g["max_rework_cycles"]), FABRO_SAFE_CYCLES)
    if g["decision"] != "PASS" and cycles >= budget:
        g = {**g, "decision": "BLOCKED", "reason": f"rework budget exhausted ({cycles} failed cycles)"}
    _state(store.workspace, phase, {"step": "route", "gate": g})
    if g["decision"] == "BLOCKED":
        emit("workflow", "WARN", f"{phase} rework budget exhausted -> BLOCKED", phase=phase)
        return 1
    return 0


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
    ap.add_argument("--step", required=True, choices=["author", "inspect", "route", "verify"])
    ap.add_argument("--check", default="")
    a = ap.parse_args(argv)
    store = Store(a.workspace.resolve())
    try:
        if a.step == "author":
            return step_author(store, a.phase, sys.stdin.read())
        if a.step == "inspect":
            return step_inspect(store, a.phase, sys.stdin.read())
        if a.step == "route":
            return step_route(store, a.phase)
        return step_verify(store, a.phase, a.check)
    except Exception as exc:  # noqa: BLE001 - any gate error is a failed (never passed) gate
        print(json.dumps({"gate_error": type(exc).__name__, "detail": str(exc)[:200]}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
