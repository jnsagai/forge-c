"""Compact progress view of a Fabro run (stages, tool calls, failures). Read-only; for operators."""
from __future__ import annotations

import argparse
import json

from .client import FabroClient, load_token, run_status


def summarize(run_id: str, tail: int = 40) -> list[str]:
    c = FabroClient(token=load_token(), timeout=15)
    lines = [f"run {run_id} status={run_status(c.get_run(run_id))}"]
    for e in c.iter_events(run_id):
        ev, p = e["event"], e.get("properties", {})
        if ev == "agent.tool.completed":
            d = p["event"]["ToolCallCompleted"]
            out = d["output"].replace("\n", " ")
            try:
                j = json.loads(d["output"])
                out = f"{j.get('status')} {j.get('summary', '')} {j.get('issues', [])[:2]}"
            except (ValueError, AttributeError):
                pass
            lines.append(f"  tool {e.get('node_id')}:{d['tool_name']} {d.get('error_kind') or ''} {out[:150]}")
        elif ev in ("stage.started", "stage.completed", "stage.failed", "run.completed", "run.failed", "agent.error"):
            detail = p.get("failure") or p.get("status") or p.get("event", {}).get("Error", {}).get("error", {}).get(
                "message", "") if isinstance(p, dict) else ""
            lines.append(f"{ev} {e.get('node_id') or ''} {str(detail)[:160]}")
    return lines[:1] + lines[-tail:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--tail", type=int, default=40)
    a = ap.parse_args()
    print("\n".join(summarize(a.run_id, a.tail)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
