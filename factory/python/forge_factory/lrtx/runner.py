"""Fabro command-node entry point of the local profile's structured authors (feature 010).

    python -m forge_factory.lrtx.runner author --phase SWE.1 --workspace . --model qwen3-coder:30b
    python -m forge_factory.lrtx.runner inspect --phase SWE.1 --workspace . --model qwen3-coder:30b

Runs one author visit (structured tasks through the profile's admission gateway), writes the compact agent-output
reply to .forge-run/lrtx/<phase>/reply.json for the unchanged author gate, and always exits 0 for model/content
outcomes (the gate decides and the route gate counts the rework). Exit 2 only for an infrastructure fault before any
reply could be written; the run's failure edges then route through the existing bounded rework path.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PHASES = {"SWE.1": "swe1", "SWE.2": "swe2", "SWE.3": "swe3", "SWE.4": "swe4", "SWE.5": "swe5", "SWE.6": "swe6"}


def author_module(ws: Path, step: str, phase: str) -> str:
    """Feature 011: a work order of a profile listing the phase in structured.semantic_phases (local-rtx-v2) uses the
    semantic author for it; every other work order keeps the feature 010 module (unchanged graphs and behaviour)."""
    man = ws / ".forge-run/manifest.json"
    prof_id = (json.loads(man.read_text()).get("local_profile") or {}).get("id") if man.is_file() else None
    if step == "author" and phase == "SWE.1" and prof_id:
        from .profile import load

        if phase in ((load(prof_id).get("structured") or {}).get("semantic_phases") or []):
            return "swe1_semantic"
    return PHASES[phase]


def inspector_module(ws: Path, phase: str) -> str:
    """Feature 011: a profile listing the phase in structured.semantic_inspect_phases (local-rtx-v2) inspects it with
    typed claims and deterministic adjudication; every other work order keeps the feature 010 inspector."""
    man = ws / ".forge-run/manifest.json"
    prof_id = (json.loads(man.read_text()).get("local_profile") or {}).get("id") if man.is_file() else None
    if prof_id:
        from .profile import load

        if phase in ((load(prof_id).get("structured") or {}).get("semantic_inspect_phases") or []):
            return "review_semantic"
    return "review"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["author", "code", "tests", "inspect", "continue-check"])
    ap.add_argument("--of", choices=["author", "code", "tests", "inspect"], default="author",
                    help="continue-check: which reply")
    ap.add_argument("--resume", action="store_true", help="continue the open visit after its time box")
    ap.add_argument("--time-budget", type=float, default=1200.0,
                    help="seconds of model work per node execution (Fabro ends a node silent for 1800 s)")
    ap.add_argument("--phase", required=True, choices=[f"SWE.{i}" for i in range(1, 7)])
    ap.add_argument("--workspace", type=Path, default=Path("."))
    ap.add_argument("--model", default="")
    a = ap.parse_args(argv)
    ws = a.workspace.resolve()
    if a.step in ("author", "code", "tests") and a.phase not in PHASES or \
            (a.step == "code" and a.phase != "SWE.3") or (a.step == "tests" and a.phase not in ("SWE.4", "SWE.5", "SWE.6")):
        ap.error(f"no structured author for {a.phase}")
    from importlib import import_module

    if a.step == "continue-check":  # exit 0 = the visit continues in the next node, 1 = the gate reads the reply
        f = ws / ".forge-run/lrtx" / a.phase / ("reply.json" if a.of == "author" else "inspect-reply.json")
        status = json.loads(f.read_text()).get("status") if f.is_file() else "MISSING"
        log = ws / ".forge-run/lrtx" / a.phase / "continue-checks.log"
        n = len(log.read_text().splitlines()) + 1 if log.is_file() else 1
        with log.open("a") as fh:
            fh.write(f"{status}\n")
        # distinct, digit-free text per execution: Fabro's failure-cycle breaker hashes node|output (ADR-0005 #5)
        print(f"continue check {''.join(chr(ord('a') + int(d)) for d in str(n))}: {status.lower()}")
        return 0 if status == "CONTINUE" else 1
    if not a.model:
        ap.error("--model is required")
    if a.step == "inspect":
        mod = import_module(f"forge_factory.lrtx.{inspector_module(ws, a.phase)}")

        (ws / ".forge-run/lrtx" / a.phase / "inspect-reply.json").unlink(missing_ok=True)
        try:
            rep = mod.visit(ws, a.phase, a.model, resume=a.resume, time_budget_s=a.time_budget)
        except Exception as exc:  # noqa: BLE001 - no inspection recorded; the inspect gate decides (fails)
            rep = mod._reply(ws, a.phase, "FAILED", [f"LRTX_RUNNER_ERROR:{type(exc).__name__}:{str(exc)[:200]}"])
        print(json.dumps(rep))
        return 0
    mod = import_module(f"forge_factory.lrtx.{author_module(ws, a.step, a.phase)}")
    stale = ws / ".forge-run/lrtx" / a.phase / "reply.json"
    stale.unlink(missing_ok=True)  # the gate must never read the reply of an earlier visit
    try:
        if a.step == "code":  # SWE.3: unit code tasks (the LL author and fix author nodes)
            rep = mod.visit_code(ws, a.model, resume=a.resume, time_budget_s=a.time_budget)
        elif a.step == "tests":  # SWE.4/SWE.5: test tasks (the unit-test / target-test author node)
            rep = mod.visit_tests(ws, a.model, resume=a.resume, time_budget_s=a.time_budget)
        elif a.phase == "SWE.3":  # SWE.3 design: rendered from the validated code tasks and the measured tools
            rep = mod.visit_design(ws, a.model)
        else:
            rep = mod.visit(ws, a.model, resume=a.resume, time_budget_s=a.time_budget)
    except Exception as exc:  # noqa: BLE001 - recorded as the author's FAILED reply; the gate rejects it
        rep = mod.reply(ws, "FAILED", [f"LRTX_RUNNER_ERROR:{type(exc).__name__}:{str(exc)[:200]}"])
    print(json.dumps(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
