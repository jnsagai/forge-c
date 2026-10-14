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
    if ctx.get("event") != "pre_tool_use":
        return Decision(True, "NOT_A_TOOL_EVENT", str(ctx.get("event")))
    return Authorizer(binding).decide(ctx.get("node_id"), str(ctx.get("tool_name", "")), ctx.get("tool_input"))


def audit(ctx: dict, d: Decision, binding_id: str) -> None:
    common = {"run_id": ctx.get("run_id"), "phase": None, "agent_id": d.role, "tool_id": d.op or ctx.get("tool_name"),
              "workflow_id": ctx.get("workflow_name")}
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
