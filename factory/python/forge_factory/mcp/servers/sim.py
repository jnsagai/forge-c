"""T015 — forge-sim-mcp: Renode / HwSim adapters with explicit availability and deterministic fault plans.

run_renode (Renode 1.17.0, pinned portable build on the data volume) builds each
`software/tests/target/test_*.c` with the driver sources into a RAM-resident Cortex-M55 image
(factory/sim/stm32n6: startup, linker script, mailbox harness) and runs it on the Forge-C minimal STM32N6
platform: CPU + NVIC + AXISRAM + a *behavioural* RCC model at 0x56028000 (ready flags follow enable bits;
`*_timeout.c` tests run with the never-ready scenario). Results are read from the RAM mailbox. This is
simulated target evidence of the driver logic on the target ISA, not silicon verification.
run_hwsim stays UNSUPPORTED (no HwSim model).
`inject_fault` writes a deterministic, seeded register-fault plan (`verification/integration/fault_plan.json`)
that host integration tests may consume through the driver's host register hook; it never touches hardware.
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import Field

from ...common import REPO_ROOT
from ..sdk import Operation, ToolContext, ToolInput, build_server, result, run_argv, tool_version


class SimIn(ToolInput):
    scenario: str = Field(default="default", pattern=r"^[a-z0-9_-]{1,40}$")


class FaultIn(ToolInput):
    register_name: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,30}$")
    fault: Literal["stuck_at_0", "stuck_at_1", "never_ready", "bit_flip"]
    bit: int = Field(ge=0, le=31)
    seed: int = Field(default=1, ge=0, le=2**31)


SIM_DIR = REPO_ROOT / "factory" / "sim" / "stm32n6"
MAILBOX = 0x341F0000
MAGIC = 0xF0C6E5A1
CFLAGS = ["-mcpu=cortex-m55", "-mthumb", "-mfloat-abi=hard", "-std=c11", "-Os", "-ffreestanding", "-nostdlib",
          "-Wall", "-Wextra"]


def renode_bin() -> str | None:
    env = os.environ.get("FORGE_RENODE_BIN")
    cand = [env] if env else []
    root = os.environ.get("FORGE_DATA_ROOT")
    if root:
        cand.append(str(Path(root) / "toolchains/renode/renode_1.17.0-portable/renode"))
    cand.append(shutil.which("renode") or "")
    return next((c for c in cand if c and Path(c).is_file()), None)


def _run_image(ctx: ToolContext, renode: str, elf: Path, scenario: str, wd: Path) -> tuple[dict | None, bytes]:
    model = wd / f"rcc_model_{scenario}.py"
    model.write_text(re.sub(r'^SCENARIO = .*$', f'SCENARIO = "{scenario}"',
                            (SIM_DIR / "rcc_model.py").read_text(), flags=re.M))
    repl = wd / f"platform_{scenario}.repl"
    repl.write_text((SIM_DIR / "stm32n6_rcc.repl").read_text().replace("RCC_MODEL_PATH", str(model)))
    words = "\n".join(f"sysbus ReadDoubleWord {MAILBOX + 4 * k:#x}" for k in range(12))
    resc = wd / f"run_{elf.stem}.resc"
    resc.write_text(f'mach create "stm32n6"\nmachine LoadPlatformDescription @{repl}\nsysbus LoadELF @{elf}\n'
                    f'cpu VectorTableOffset 0x34000000\nemulation RunFor "0.2"\n{words}\nquit\n')
    # .NET under the sandbox rlimits: no W^X double-mapping file (RLIMIT_FSIZE) and a bounded GC heap (RLIMIT_AS)
    env = {"DOTNET_EnableWriteXorExecute": "0", "DOTNET_GCHeapHardLimit": "0x60000000"}
    r = run_argv([renode, "--disable-gui", "--console", "--plain", "-e", f"include @{resc}"], wd, 170,
                 {os.path.basename(renode)}, env_extra=env, mem_mb=65536, fsize_mb=512)
    vals = [int(x, 16) for x in re.findall(r"^(0x[0-9A-Fa-f]{8})\s*$", r.stdout.decode(errors="replace"), re.M)]
    if len(vals) < 4:
        return None, r.stdout + r.stderr
    return {"magic_ok": vals[0] == MAGIC, "passed": vals[1], "failed": vals[2], "done": vals[3] == 1,
            "failed_ids": [v for v in vals[4:4 + min(vals[2], 8)]]}, r.stdout + r.stderr


def run_renode(ctx: ToolContext, a: SimIn) -> dict:
    renode = renode_bin()
    if not renode:
        return result(ctx, "UNSUPPORTED", "Renode not installed; target simulation disabled",
                      issues=["TOOL_MISSING:renode", "SAFETY_GAP:target_behaviour_unverified"], tool="renode",
                      version="unavailable")
    if not shutil.which("arm-none-eabi-gcc"):
        return result(ctx, "UNAVAILABLE", "GNU Arm toolchain missing", issues=["TOOL_MISSING:arm-none-eabi-gcc"],
                      tool="renode")
    tests = sorted((ctx.workspace / "software/tests/target").glob("test_*.c"))
    if not tests:
        return result(ctx, "BLOCKED", "no target tests", issues=["NO_TESTS:software/tests/target"], tool="renode")
    srcs = [str(p) for d in ("software/hal", "software/src") for p in sorted((ctx.workspace / d).glob("*.c"))]
    incs = [f"-I{ctx.workspace / d}" for d in ("software/hal", "software/ll", "software/include",
                                                "software/tests/target") if (ctx.workspace / d).is_dir()]
    wd = ctx.workspace / "build" / "renode"
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    log, issues, per = b"", [], {}
    passed = failed = 0
    for t in tests:
        scenario = "never_ready" if t.stem.endswith("_timeout") else "default"
        elf = wd / f"{t.stem}.elf"
        b = run_argv(["arm-none-eabi-gcc", *CFLAGS, *incs, f"-I{SIM_DIR}", "-T", str(SIM_DIR / "link.ld"),
                      str(SIM_DIR / "startup.c"), str(t), *srcs, "-o", str(elf)], wd, 180, {"arm-none-eabi-gcc"})
        log += b.stdout + b.stderr
        if b.exit_code != 0:
            issues.append(f"BUILD_FAIL:{t.name}")
            issues += [ln.split(str(ctx.workspace) + "/")[-1][:140] for ln in b.stderr.decode(errors="replace")
                       .splitlines() if ": error:" in ln][:8]
            failed += 1
            continue
        res, out = _run_image(ctx, renode, elf, scenario, wd)
        log += out
        if res is None or not res["magic_ok"] or not res["done"]:
            issues.append(f"NO_RESULT:{t.name}:{scenario}")
            failed += 1
            continue
        per[t.name] = {**res, "scenario": scenario}
        passed += res["passed"]
        failed += res["failed"]
        issues += [f"TARGET_FAIL:{t.name}:check {i}" for i in res["failed_ids"]]
        if res["passed"] == 0:
            issues.append(f"NO_CHECKS:{t.name}")
    ok = not issues and passed > 0
    return result(ctx, "PASS" if ok else "FAIL", f"renode cortex-m55: {passed} checks passed, {failed} failed "
                  f"({len(tests)} images; behavioural RCC model)", [ctx.store(log)], issues[:30],
                  {"passed": passed, "failed": failed, "images": per, "cpu": "cortex-m55",
                   "platform": "forge-stm32n6-rcc-min (CPU+NVIC+AXISRAM+behavioural RCC)",
                   "target_evidence": "simulated", "silicon_verified": False}, "renode",
                  tool_version(renode), 0 if ok else 1, None, a.model_dump(), log)


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
    Operation("run_renode", SimIn, run_renode,
              "Build software/tests/target/test_*.c for Cortex-M55 and run them on the Renode STM32N6 RCC model."),
    Operation("run_hwsim", SimIn, run_hwsim, "HwSim device model (disabled: no model)."),
    Operation("inject_fault", FaultIn, inject_fault, "Plan a deterministic register fault for host tests."),
]

if __name__ == "__main__":
    build_server("forge-sim-mcp", OPERATIONS).run("stdio")
