"""T015 — forge-sim-mcp: Renode / HwSim adapters with explicit availability and deterministic fault plans.

Renode and an STM32N6 HwSim model are NOT installed on this host: run_renode/run_hwsim return
UNSUPPORTED with a SAFETY_GAP issue (target behaviour unverified) instead of emulating results.
`inject_fault` writes a deterministic, seeded register-fault plan (`verification/integration/fault_plan.json`)
that host integration tests may consume through the driver's host register hook; it never touches hardware.
"""
from __future__ import annotations

import json
import random
import shutil
from typing import Literal

from pydantic import Field

from ..sdk import Operation, ToolContext, ToolInput, build_server, result


class SimIn(ToolInput):
    scenario: str = Field(default="default", pattern=r"^[a-z0-9_-]{1,40}$")


class FaultIn(ToolInput):
    register_name: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,30}$")
    fault: Literal["stuck_at_0", "stuck_at_1", "never_ready", "bit_flip"]
    bit: int = Field(ge=0, le=31)
    seed: int = Field(default=1, ge=0, le=2**31)


def run_renode(ctx: ToolContext, a: SimIn) -> dict:
    if shutil.which("renode"):
        return result(ctx, "UNSUPPORTED", "renode present but no validated STM32N6 platform model",
                      issues=["NO_VALIDATED_PLATFORM:stm32n6"], tool="renode")
    return result(ctx, "UNSUPPORTED", "Renode not installed; target simulation disabled",
                  issues=["TOOL_MISSING:renode", "SAFETY_GAP:target_behaviour_unverified"], tool="renode",
                  version="unavailable")


def run_hwsim(ctx: ToolContext, a: SimIn) -> dict:
    return result(ctx, "UNSUPPORTED", "No STM32N6 RCC HwSim model available; disabled",
                  issues=["TOOL_MISSING:hwsim", "SAFETY_GAP:target_behaviour_unverified"], tool="hwsim",
                  version="unavailable")


def inject_fault(ctx: ToolContext, a: FaultIn) -> dict:
    p = ctx.workspace / "verification" / "integration" / "fault_plan.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    plan: dict = json.loads(p.read_text()) if p.is_file() else {"schema": "forge-c/fault-plan/0.4", "faults": []}
    rng = random.Random(a.seed)  # noqa: S311 - deterministic test planning, not security
    entry = {**a.model_dump(), "trigger_after_reads": rng.randint(1, 8), "environment": "host-register-model"}
    plan["faults"].append(entry)
    data = json.dumps(plan, indent=2, sort_keys=True).encode()
    p.write_bytes(data)
    return result(ctx, "PASS", f"fault {a.fault} on {a.register_name}[{a.bit}] planned (host model only)",
                  [ctx.store(data, "json")], [], {"faults_planned": len(plan["faults"]), "target_evidence": False},
                  "forge-fault-planner", input_obj=a.model_dump())


OPERATIONS = [
    Operation("run_renode", SimIn, run_renode, "Renode target simulation (disabled: not installed)."),
    Operation("run_hwsim", SimIn, run_hwsim, "HwSim device model (disabled: no model)."),
    Operation("inject_fault", FaultIn, inject_fault, "Plan a deterministic register fault for host tests."),
]

if __name__ == "__main__":
    build_server("forge-sim-mcp", OPERATIONS).run("stdio")
