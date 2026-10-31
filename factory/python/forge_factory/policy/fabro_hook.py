"""Fabro `pre_tool_use` command hook entrypoint (host side, blocking, fail-closed).

Fabro pipes the hook context JSON on stdin (ADR-0002). Exit 0 + {"decision":"proceed"} allows;
exit 2 + {"decision":"block"} denies. ANY error -> block (command hooks fail closed in Fabro).
Usage in run config:  script = "<venv>/bin/python -m forge_factory.policy.fabro_hook --binding <file>"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..events.emit import emit
from .authz import Authorizer, Binding, Decision


def handle(ctx: dict, binding: Binding) -> Decision:
    from ..brownfield.resume import ResumeRefused, remaining_seconds
    from .governor import count_tool_call, reset_node

    try:
        remaining_seconds(Path(binding.workspace))
    except ResumeRefused as exc:
        return Decision(False, "RESUME_BUDGET_REFUSED", str(exc))

    if ctx.get("event") == "stage_start":
        reset_node(binding.binding_id, str(ctx.get("run_id")), str(ctx.get("node_id")))
        return Decision(True, "STAGE_START_RESET", str(ctx.get("node_id")))
    if ctx.get("event") != "pre_tool_use":
        return Decision(True, "NOT_A_TOOL_EVENT", str(ctx.get("event")))
    d = Authorizer(binding).decide(ctx.get("node_id"), str(ctx.get("tool_name", "")), ctx.get("tool_input"))
    if d.allow and d.role:
        import uuid

        from ..afo.durable import Refused
        from ..afo.tool_accounting import charge

        try:
            charge(Path(binding.workspace), str(ctx.get("tool_call_id") or "hook-" + uuid.uuid4().hex))
        except Refused as exc:
            return Decision(False, exc.code, "shared mission tool allowance refused", d.role, d.op)
        ok, n, limit, reserved = count_tool_call(
            binding.binding_id,
            str(ctx.get("run_id")),
            str(ctx.get("node_id")),
            d.role,
            str(ctx.get("tool_name", "")),
            binding.workspace,
        )
        if reserved:
            return Decision(
                False,
                "INSPECTION_CALLS_RESERVED",
                f"{n}/{limit} tool calls used: the remaining calls are "
                "reserved - call check_inspection now with a verdict for EVERY item (and report_defect for "
                "upstream findings)",
                d.role,
                d.op,
            )
        if not ok:
            return Decision(False, "TURN_BUDGET_EXHAUSTED", f"{n}>{limit} tool calls; reply BLOCKED now", d.role, d.op)
    return d


def audit(ctx: dict, d: Decision, binding_id: str) -> None:
    if d.code == "STAGE_START_RESET":
        return
    common = {
        "run_id": ctx.get("run_id"),
        "phase": None,
        "agent_id": d.role,
        "tool_id": d.op or ctx.get("tool_name"),
        "workflow_id": ctx.get("workflow_name"),
    }
    msg = f"{'ALLOW' if d.allow else 'DENY'} {ctx.get('tool_name')} role={d.role} {d.code}"
    if d.allow:
        emit("audit", "INFO", msg, correlation_id=ctx.get("run_id") or binding_id, **common)
    else:
        emit("security", "WARN", msg, correlation_id=ctx.get("run_id") or binding_id, **common)
        emit("audit", "WARN", msg, correlation_id=ctx.get("run_id") or binding_id, **common)


def main(argv: list[str] | None = None) -> int:
    try:
        ap = argparse.ArgumentParser()
        ap.add_argument("--binding", required=True, type=Path)
        a = ap.parse_args(argv)
        binding = Binding.load(a.binding)
        raw = sys.stdin.read()
        ctx = json.loads(raw)
        if not isinstance(ctx, dict):
            raise ValueError("context not an object")
        d = handle(ctx, binding)
        if d.allow and str(ctx.get("tool_name", "")).startswith("mcp__"):
            from ..mcp.sdk import issue_ticket

            node = binding.nodes.get(ctx.get("node_id") or "", {})
            issue_ticket(
                binding.binding_id,
                ctx["tool_name"],
                ctx.get("tool_input") or {},
                d.role or "",
                ctx.get("node_id") or "",
                node.get("phase"),
                binding.workspace,
            )
        try:
            audit(ctx, d, binding.binding_id)
        except Exception:  # noqa: BLE001 - audit failure must not open the gate
            if d.allow:
                d = Decision(False, "AUDIT_WRITE_FAILED", "cannot record audit event", d.role, d.op)
        print(d.hook_json())
        return 0 if d.allow else 2
    except BaseException as exc:  # noqa: BLE001 - fail closed on anything
        print(json.dumps({"decision": "block", "reason": f"FORGE_POLICY:HOOK_ERROR:{type(exc).__name__}"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
