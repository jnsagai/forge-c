"""LRTX-T018 (LRTX-FR-013): after a failed cycle, go straight back to the inspector - without re-running authorship -
only when the phase's newest baseline is valid and was never inspected (e.g. the inspector timed out or recorded
nothing) and nothing addressed to the author is pending. Exit 0 = inspect again, exit 1 = the author (existing path).

    python -m forge_factory.lrtx.reinspect --phase SWE.n --workspace .

The route gate has already counted the failed cycle; this decision never resets or adds budget.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FROZEN = ("FROZEN", "FROZEN_BY_EVIDENCE", "FROZEN_BY_TOOL_EVIDENCE")


def decide(ws: Path, phase: str) -> tuple[bool, str]:
    from ..inspection.engine import Store

    ws = Path(ws)
    st = Store(ws)
    bl = st.latest_baseline(phase)
    if bl is None:
        return False, "no baseline"
    stale = st.stale_reason(phase, bl)
    if stale:
        return False, f"baseline not valid: {stale}"
    ins = sorted((ws / "inspection" / phase).glob("INS-*.json")) if (ws / "inspection" / phase).is_dir() else []
    if any(json.loads(p.read_text()).get("baseline_id") == bl["baseline_id"] for p in ins):
        return False, "the baseline was inspected: findings go to the author"
    for p in sorted((ws / ".forge-run/defects").glob("DEF-*.json")) if (ws / ".forge-run/defects").is_dir() else []:
        d = json.loads(p.read_text())
        if d.get("target_phase") == phase and d.get("status") in ("OPEN", "IN_FIX"):
            return False, f"defect {d.get('id')} addressed to {phase}"
    log = ws / ".forge-run/gates/gate-log.jsonl"
    author = [json.loads(x) for x in (log.read_text().splitlines() if log.is_file() else [])]
    author = [d for d in author if d.get("phase") == phase and d.get("step") == "author"]
    if not author or author[-1].get("result") not in FROZEN or author[-1].get("baseline_id") != bl["baseline_id"]:
        return False, "the last author gate did not freeze the current baseline"
    return True, f"{bl['baseline_id']} valid and not inspected: inspect again without authorship"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase", required=True)
    ap.add_argument("--workspace", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    ok, why = decide(a.workspace.resolve(), a.phase)
    from ..inspection.gate import _state

    _state(a.workspace.resolve(), a.phase, {"step": "reinspect_direct", "result": "INSPECT" if ok
                                                             else "AUTHOR", "reason": why})
    print(json.dumps({"reinspect_direct": ok, "reason": why}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
