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

PHASES = {"SWE.1": "swe1", "SWE.2": "swe2"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["author", "inspect"])
    ap.add_argument("--phase", required=True, choices=[f"SWE.{i}" for i in range(1, 7)])
    ap.add_argument("--workspace", type=Path, default=Path("."))
    ap.add_argument("--model", required=True)
    a = ap.parse_args(argv)
    ws = a.workspace.resolve()
    if a.step == "author" and a.phase not in PHASES:
        ap.error(f"no structured author for {a.phase}")
    from importlib import import_module

    if a.step == "inspect":
        from . import review as mod

        (ws / ".forge-run/lrtx" / a.phase / "inspect-reply.json").unlink(missing_ok=True)
        try:
            rep = mod.visit(ws, a.phase, a.model)
        except Exception as exc:  # noqa: BLE001 - no inspection recorded; the inspect gate decides (fails)
            rep = mod._reply(ws, a.phase, "FAILED", [f"LRTX_RUNNER_ERROR:{type(exc).__name__}:{str(exc)[:200]}"])
        print(json.dumps(rep))
        return 0
    mod = import_module(f"forge_factory.lrtx.{PHASES[a.phase]}")
    stale = ws / ".forge-run/lrtx" / a.phase / "reply.json"
    stale.unlink(missing_ok=True)  # the gate must never read the reply of an earlier visit
    try:
        rep = mod.visit(ws, a.model)
    except Exception as exc:  # noqa: BLE001 - recorded as the author's FAILED reply; the gate rejects it
        rep = mod.reply(ws, "FAILED", [f"LRTX_RUNNER_ERROR:{type(exc).__name__}:{str(exc)[:200]}"])
    print(json.dumps(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
