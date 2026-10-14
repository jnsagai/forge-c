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


def _state(ws: Path, phase: str, payload: dict) -> None:
    d = ws / ".forge-run" / "gates"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "gate-log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": utc_now(), "phase": phase, **payload}, sort_keys=True) + "\n")


def step_author(store: Store, phase: str, text: str) -> int:
    res = parse(text)
    if not res.ok or res.status != "PASS":
        _state(store.workspace, phase, {"step": "author", "result": "REJECTED", "errors": res.errors,
                                        "status": res.status, "issues": res.issues})
        return 1
    try:
        bl = store.freeze(phase, f"swe{phase[-1]}-author")
    except InspectionError as exc:
        _state(store.workspace, phase, {"step": "author", "result": "FREEZE_FAILED", "error": str(exc)})
        return 1
    _state(store.workspace, phase, {"step": "author", "result": "FROZEN", "baseline_id": bl["baseline_id"]})
    print(json.dumps({"baseline_id": bl["baseline_id"], "baseline_hash": bl["baseline_hash"]}))
    return 0


def step_inspect(store: Store, phase: str, text: str) -> int:
    res = parse(text)
    g = store.gate(phase)
    _state(store.workspace, phase, {"step": "inspect", "agent_status": res.status, "agent_ok": res.ok,
                                    "gate": g})
    print(json.dumps(g))
    # The agent's own PASS is never sufficient: the recorded, deterministic gate decision rules.
    return 0 if g["decision"] == "PASS" else 1


def step_route(store: Store, phase: str) -> int:
    g = store.gate(phase)
    _state(store.workspace, phase, {"step": "route", "gate": g})
    if g["decision"] == "BLOCKED":
        emit("workflow", "WARN", f"{phase} rework budget exhausted -> BLOCKED", phase=phase)
        return 1
    return 0


def step_verify(store: Store, phase: str, check: str) -> int:
    if check == "hal_guideline":
        from .guideline import check_workspace

        rep = check_workspace(store.workspace)
        out = store.workspace / "verification" / "static" / "hal_guideline_conformance.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(pretty_json(rep))
        _state(store.workspace, phase, {"step": "verify", "check": check, "verdict": rep["verdict"],
                                        "violations": len(rep["violations"])})
        emit("workflow", "INFO" if rep["verdict"] == "PASS" else "WARN",
             f"{phase} HAL guideline verification {rep['verdict']} violations={len(rep['violations'])}", phase=phase)
        print(json.dumps({"verdict": rep["verdict"], "violations": len(rep["violations"]),
                          "report": "verification/static/hal_guideline_conformance.json"}))
        return 0 if rep["verdict"] == "PASS" else 1
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
