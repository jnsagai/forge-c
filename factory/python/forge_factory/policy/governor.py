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


def count_tool_call(binding_id: str, run_id: str, node_id: str, role: str) -> tuple[bool, int, int]:
    """Returns (allowed, count_after, limit)."""
    limit = next((a.max_turns for a in load_agents()[0] if a.id == role), 20)

    def fn(st: dict) -> tuple[bool, int, int]:
        k = f"{run_id}:{node_id}"
        st[k] = int(st.get(k, 0)) + 1
        return st[k] <= limit, st[k], limit
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
    exceeded = []
    for node, used in per_node.items():
        role = (nodes.get(node) or {}).get("role")
        if role and used > budgets[role] * 4:  # budget is per visit; MAX_VISITS (4) visits per node
            exceeded.append({"node": node, "role": role, "tokens": used, "budget_total": budgets[role] * 4})
    out = {"run_id": run_id, "status": "TOKEN_BUDGET_EXHAUSTED" if exceeded else "WITHIN_BUDGET",
           "per_node_tokens": per_node, "per_node_cache_read": cached, "exceeded": exceeded, "basis": "reported",
           "accounting": "uncached_input+output per node across visits (cap = max_stage_tokens x 4 visits)",
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
