"""T042 — deterministic budget governor (turns, tokens) — never calls a model.

* Turn budget: the Fabro policy hook calls `count_tool_call` on every pre_tool_use; after the role's
  `max_turns` tool calls in one node visit, further calls are blocked (TURN_BUDGET_EXHAUSTED). A
  `stage_start` hook resets the per-visit counter.
* Token budget: `check_run` compares Fabro-*reported* per-stage token usage with the role's
  `max_stage_tokens`; on excess it records TOKEN_BUDGET_EXHAUSTED, writes a gate-log entry, and cancels the
  run so the finalizer packages BLOCKED (safe phase failure, never a false PASS). Missing usage => UNKNOWN.
"""
from __future__ import annotations

import fcntl
import json
from pathlib import Path
from typing import Any

from ..common import state_dir, utc_now
from ..events.emit import emit
from ..registry.agents import load_agents


def _state_file(binding_id: str) -> Path:
    d = state_dir() / "governor"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{binding_id}.json"


def _update(binding_id: str, fn: Any) -> Any:
    p = _state_file(binding_id)
    with open(p, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        raw = f.read()
        st = json.loads(raw) if raw.strip() else {}
        out = fn(st)
        f.seek(0)
        f.truncate()
        f.write(json.dumps(st))
        fcntl.flock(f, fcntl.LOCK_UN)
    return out


def reset_node(binding_id: str, run_id: str, node_id: str) -> None:
    def fn(st: dict) -> None:
        st[f"{run_id}:{node_id}"] = 0
    _update(binding_id, fn)


RESERVED_FOR_INSPECTORS = 4  # r63: inspectors ran out of calls before recording; the last calls are reserved
RESERVED_TOOLS = ("mcp__forge_evidence_mcp__check_inspection", "mcp__forge_evidence_mcp__report_defect")


SCALED_ROLES = ("swe3-author", "swe4-author", "swe5-author", "swe6-author")
REFERENCE_FUNCTIONS = 12  # the combined-driver allocation the authored 35-turn budget was set for (r70/r71)


TRACE_ROLES = ("swe2-author", "swe3-author", "swe4-author", "swe5-author")
TRACE_EXTRA_TURNS = 8
# CAPA-041 (r135/r136/r137): a phase re-entered to fix an upstream defect must re-read its context, fix the code AND
# re-validate the specs/designs/trace; all three HAL fix visits of SWE.3 ran out of turns. Extra turns apply only
# while a defect targeted at the author's phase is IN_FIX (an upstream loop), never on a first pass.
LOOP_EXTRA_TURNS = 15


def _in_fix_loop(workspace: str, role: str) -> bool:
    phase = {"swe1-author": "SWE.1", "swe2-author": "SWE.2", "swe3-author": "SWE.3"}.get(role)
    if not phase:
        return False
    try:
        from ..inspection.defects import all_defects

        return any(d.get("status") == "IN_FIX" and d.get("target_phase") == phase for d in all_defects(Path(workspace)))
    except Exception:  # noqa: BLE001 - advisory: the authored budget always applies
        return False


def turn_limit(role: str, workspace: str | None = None) -> int:
    """CAPA-015: authored max_turns, plus 1 turn per 2 allocated API functions above REFERENCE_FUNCTIONS for the
    code/test author roles (r81: SWE.3 needed 36 of 35 calls for a 16-function LL), capped at +25."""
    base = next((a.max_turns for a in load_agents()[0] if a.id == role), 20)
    if workspace and role in TRACE_ROLES:
        from ..layer import swtrace_enabled

        if swtrace_enabled(Path(workspace)):  # owner addendum 2026-10-17: unit specs, designs, trace tags
            base += TRACE_EXTRA_TURNS
    if workspace and _in_fix_loop(workspace, role):
        base += LOOP_EXTRA_TURNS
    if role not in SCALED_ROLES or not workspace:
        return base
    try:
        from ..inspection.implementation import allocated_functions

        n = len(allocated_functions(Path(workspace)))
    except Exception:  # noqa: BLE001 - scaling is advisory; the authored budget always applies
        return base
    return base + min(25, max(0, n - REFERENCE_FUNCTIONS) // 2)


def count_tool_call(binding_id: str, run_id: str, node_id: str, role: str,
                    tool: str = "", workspace: str | None = None) -> tuple[bool, int, int, bool]:
    """Returns (allowed, count_after, limit, reserved_denial). For inspector roles the last RESERVED_FOR_INSPECTORS
    calls of the authored budget are only usable for check_inspection/report_defect; a denied non-reserved call
    does not consume budget (the budget itself is unchanged)."""
    limit = turn_limit(role, workspace)

    def fn(st: dict) -> tuple[bool, int, int, bool]:
        k = f"{run_id}:{node_id}"
        cur = int(st.get(k, 0))
        if role.endswith("-inspector") and cur >= limit - RESERVED_FOR_INSPECTORS and tool not in RESERVED_TOOLS:
            return False, cur, limit, True
        st[k] = cur + 1
        return st[k] <= limit, st[k], limit, False
    return _update(binding_id, fn)


def check_run(run_id: str, nodes: dict, workspace: Path | None = None, client=None, cancel: bool = True) -> dict:
    from ..fabro.client import FabroClient, load_token

    if workspace is not None and (workspace / ".forge-run" / "model-profile.json").is_file():
        prof = json.loads((workspace / ".forge-run" / "model-profile.json").read_text())
        if str(prof.get("token_budget", "")).startswith("unlimited"):  # owner decision for local runs
            return {"run_id": run_id, "status": "TOKEN_BUDGET_DISABLED", "reason": prof["token_budget"],
                    "checked_at": utc_now()}
    c = client or FabroClient(token=load_token(), timeout=10)
    budgets = {a.id: a.max_stage_tokens for a in load_agents()[0]}
    try:
        usage = c.usage(run_id)
    except Exception as exc:  # noqa: BLE001
        return {"run_id": run_id, "status": "UNKNOWN", "reason": type(exc).__name__}
    per_node: dict[str, int] = {}
    cached: dict[str, int] = {}
    for s in usage.get("stages", []):
        node = s["stage"]["id"]
        t = s["usage"]["tokens"]
        # basis: newly processed tokens = uncached input + output (cache_read reported separately, ADR-0006)
        per_node[node] = per_node.get(node, 0) + int(t.get("input", 0)) + int(t.get("output", 0))
        cached[node] = cached.get(node, 0) + int(t.get("cache_read", 0))
    from ..workflow.builder import MAX_VISITS

    exceeded = []
    for node, used in per_node.items():
        role = (nodes.get(node) or {}).get("role")
        if role and used > budgets[role] * MAX_VISITS:  # budget is per visit; at most MAX_VISITS visits per node
            exceeded.append({"node": node, "role": role, "tokens": used, "budget_total": budgets[role] * MAX_VISITS})
    out = {"run_id": run_id, "status": "TOKEN_BUDGET_EXHAUSTED" if exceeded else "WITHIN_BUDGET",
           "per_node_tokens": per_node, "per_node_cache_read": cached, "exceeded": exceeded, "basis": "reported",
           "accounting": f"uncached_input+output per node across visits (cap = max_stage_tokens x {MAX_VISITS} visits)",
           "checked_at": utc_now()}
    if exceeded:
        emit("ai", "ERROR", f"TOKEN_BUDGET_EXHAUSTED run={run_id} nodes={','.join(e['node'] for e in exceeded)}",
             correlation_id=run_id, run_id=run_id)
        if workspace is not None:
            log = workspace / ".forge-run" / "gates" / "gate-log.jsonl"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a") as f:
                f.write(json.dumps({"ts": utc_now(), "step": "governor", "result": "TOKEN_BUDGET_EXHAUSTED",
                                    "exceeded": exceeded}) + "\n")
        if cancel:
            c.cancel(run_id)
    return out
