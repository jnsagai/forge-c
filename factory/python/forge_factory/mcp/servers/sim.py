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

import base64
import json
import os
import random
import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import Field

from ...common import REPO_ROOT, canonical_json, sha256_file
from ...inspection.defects import integrity, record_integrity, undeclared_test_changes
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
    roots = [os.environ.get("FORGE_DATA_ROOT")]
    if os.environ.get("FORGE_STATE_DIR"):  # MCP servers get FORGE_STATE_DIR (= <data root>/state), not FORGE_DATA_ROOT
        roots.append(str(Path(os.environ["FORGE_STATE_DIR"]).parent))
    for root in filter(None, roots):
        cand.append(str(Path(root) / "toolchains/renode/renode_1.17.0-portable/renode"))
    cand.append(shutil.which("renode") or "")
    return next((c for c in cand if c and Path(c).is_file()), None)


def build_image(ws: Path, test: Path, elf: Path) -> tuple[bool, bytes, list[str]]:
    """Build one RAM-resident Cortex-M55 test image (test source + driver sources + startup + linker script)."""
    # CAPA-048: a packaged workspace carries the HAL unit in software/hal AND in the flat software/src view; one
    # compile unit per file name (software/hal first), or the image links every function twice
    seen: set[str] = set()
    srcs = [str(p) for d in ("software/hal", "software/src") for p in sorted((ws / d).glob("*.c"))
            if not (p.name in seen or seen.add(p.name))]
    incs = [f"-I{ws / d}" for d in ("software/hal", "software/ll", "software/include", "software/tests/target",
                                     "software/tests/software") if (ws / d).is_dir()]
    from ...brownfield.cmsis import target_flags
    from ...delivery_first import include_flags

    incs += target_flags(ws) + include_flags(ws)  # pinned target adapter, explicit work-order selection
    from ... import simulation_performance as performance

    budget = performance.selected(ws)
    performance_inputs = None
    unit = None
    if budget and test == ws / budget["test_source"]:
        try:
            unit = performance.prepare(ws, elf.parent)
        except ValueError as exc:
            return False, str(exc).encode(), [str(exc)]
        srcs.append(str(unit))
        incs.append("-I" + str(elf.parent))
        performance_inputs = performance.inputs(ws)
    b = run_argv(["arm-none-eabi-gcc", *CFLAGS, *incs, f"-I{SIM_DIR}", "-T", str(linker_script(ws, elf.parent)),
                  str(SIM_DIR / "startup.c"), str(test), *srcs, "-o", str(elf)], elf.parent, 180, {"arm-none-eabi-gcc"})
    lines = b.stderr.decode(errors="replace").splitlines()
    # r68: a link failure only said "collect2: error: ld returned 1"; the cause is the undefined reference line
    errs = [ln.split(str(ws) + "/")[-1][:140] for ln in lines
            if ("undefined reference" in ln or "multiple definition" in ln or ": error:" in ln)
            and "collect2" not in ln][:8]
    if not errs:
        errs = [ln[:140] for ln in lines if "error" in ln][:4]
    if b.exit_code == 0 and performance_inputs:
        if performance.inputs(ws) != performance_inputs:
            return False, b.stdout + b.stderr, ["SIMULATION_PERFORMANCE_BUILD_INPUT_CHANGED"]
        elf.with_suffix(".performance-inputs.json").write_bytes(
            canonical_json({**performance_inputs, "elf_sha256": sha256_file(elf), "wrapper_sha256": sha256_file(unit)}))
    return b.exit_code == 0, b.stdout + b.stderr, errs


def linker_script(ws: Path | None, wd: Path) -> Path:
    """The platform linker script; feature 009: the register-block symbol of the work order's peripheral (RCC: the
    shared link.ld unchanged)."""
    from ...layer import profile

    pr = profile(ws)
    if pr["id"] == "rcc":
        return SIM_DIR / "link.ld"
    text = re.sub(r"^ll_rcc_regs = 0x56028000;.*$", f"{pr['ll']['register_block']} = {pr['base_address']};  "
                  f"/* {pr['register_prefix']} register block (RM0486 p.{pr.get('mm_page')}) */",
                  (SIM_DIR / "link.ld").read_text(), flags=re.M)
    out = wd / f"link_{pr['id']}.ld"
    out.write_text(text)
    return out


def run_image(renode: str, elf: Path, scenario: str, wd: Path, ws: Path | None = None) -> tuple[dict | None, bytes]:
    """Run an image on the Forge-C STM32N6 platform with the given model scenario; read the RAM mailbox. Feature 009:
    the peripheral model and platform come from the work order's profile (RCC by default)."""
    from ...layer import profile

    pr = profile(ws)
    stem = Path(pr["sim"]["model"]).stem
    model = wd / f"{stem}_{scenario}.py"
    model.write_text(re.sub(r'^SCENARIO = .*$', f'SCENARIO = "{scenario}"',
                            (SIM_DIR / pr["sim"]["model"]).read_text(), flags=re.M))
    repl = wd / f"platform_{scenario}.repl"
    repl.write_text((SIM_DIR / pr["sim"]["platform"]).read_text().replace(f"{pr['register_prefix']}_MODEL_PATH",
                                                                          str(model)))
    words = "\n".join(f"sysbus ReadDoubleWord {MAILBOX + 4 * k:#x}" for k in range(12))
    resc = wd / f"run_{elf.stem}.resc"
    from ... import simulation_performance as performance

    budget = performance.selected(ws) if ws is not None else None
    instrumentation = None
    extra = ""
    if budget and elf.stem in (Path(budget["test_source"]).stem, Path(budget["test_source"]).stem + "_default"):
        if scenario != "default":
            return None, b"SIMULATION_PERFORMANCE_PROFILE_REQUIRES_DEFAULT_SCENARIO"
        try:
            receipt = json.loads(elf.with_suffix(".performance-inputs.json").read_text())
            if (any(receipt[k] != v for k, v in performance.inputs(ws).items())
                    or receipt["elf_sha256"] != sha256_file(elf)):
                return None, b"SIMULATION_PERFORMANCE_BUILD_INPUT_CHANGED"
        except (OSError, ValueError, KeyError, TypeError):
            return None, b"SIMULATION_PERFORMANCE_BUILD_INPUT_UNAVAILABLE"
        listing = run_argv(["arm-none-eabi-objdump", "-d", str(elf)], wd, 30, {"arm-none-eabi-objdump"})
        if listing.exit_code:
            return None, b"SIMULATION_PERFORMANCE_DISASSEMBLY_FAILED\n" + listing.stdout + listing.stderr
        try:
            instrumentation = performance.plan(ws, listing.stdout.decode())
        except ValueError as exc:
            return None, str(exc).encode()
        extra = "\n".join(instrumentation["commands"]) + "\n"
        instrumentation.update(receipt)
        instrumentation["observer_sha256"] = sha256_file(Path(performance.__file__))
        instrumentation["source_files"] = performance.source_files(Path(ws))
        instrumentation["platform_sha256"] = sha256_file(repl)
        instrumentation["model_sha256"] = sha256_file(model)
    resc.write_text(f'mach create "stm32n6"\nmachine LoadPlatformDescription @{repl}\nsysbus LoadELF @{elf}\n'
                    f'cpu VectorTableOffset 0x34000000\n{extra}emulation RunFor "0.2"\n{words}\nquit\n')
    # .NET under the sandbox rlimits: no W^X double-mapping file (RLIMIT_FSIZE) and a bounded GC heap (RLIMIT_AS)
    env = {"DOTNET_EnableWriteXorExecute": "0", "DOTNET_GCHeapHardLimit": "0x60000000"}
    r = run_argv([renode, "--disable-gui", "--console", "--plain", "-e", f"include @{resc}"], wd, 170,
                 {os.path.basename(renode)}, env_extra=env, mem_mb=65536, fsize_mb=512)
    if instrumentation and (any(instrumentation[k] != v for k, v in performance.inputs(ws).items())
                            or instrumentation["elf_sha256"] != sha256_file(elf)):
        return None, r.stdout + r.stderr + b"\nSIMULATION_PERFORMANCE_EXECUTION_INPUT_CHANGED"
    vals = [int(x, 16) for x in re.findall(r"^(0x[0-9A-Fa-f]{8})\s*$", r.stdout.decode(errors="replace"), re.M)]
    if len(vals) < 4:
        return None, r.stdout + r.stderr
    observation = {"magic_ok": vals[0] == MAGIC, "passed": vals[1], "failed": vals[2], "done": vals[3] == 1,
                   "failed_ids": [v for v in vals[4:4 + min(vals[2], 8)]]}
    if instrumentation:
        observation["performance"] = performance.report(ws, instrumentation, r.stdout.decode(errors="replace"))
    return observation, r.stdout + r.stderr


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
    from ... import simulation_performance as performance

    budget = performance.selected(ctx.workspace)
    if budget and ctx.workspace / budget["test_source"] not in tests:
        return result(ctx, "BLOCKED", "declared simulation performance test is missing",
                      issues=["SIMULATION_PERFORMANCE_TEST_MISSING"], tool="renode")
    if not tests:
        return result(ctx, "BLOCKED", "no target tests", issues=["NO_TESTS:software/tests/target"], tool="renode")
    wd = ctx.workspace / "build" / "renode"
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    log, issues, per = b"", [], {}
    asserted: list[Path] = []
    passed = failed = 0
    for t in tests:
        scenario = "never_ready" if t.stem.endswith("_timeout") else "default"
        elf = wd / f"{t.stem}.elf"
        ok_build, blog, errs = build_image(ctx.workspace, t, elf)
        log += blog
        if not ok_build:
            issues.append(f"BUILD_FAIL:{t.name}")
            issues += errs
            failed += 1
            continue
        res, out = run_image(renode, elf, scenario, wd, ctx.workspace)
        log += out
        if res is None or not res["magic_ok"] or not res["done"]:
            issues.append(f"NO_RESULT:{t.name}:{scenario}")
            failed += 1
            continue
        per[t.name] = {**res, "scenario": scenario}
        if budget and t == ctx.workspace / budget["test_source"]:
            measurement = res.get("performance") or {}
            if measurement.get("status") != "PASS":
                issues.append("SIMULATION_PERFORMANCE_NOT_PASS:" + t.name)
                issues += measurement.get("issues", [])
        passed += res["passed"]
        failed += res["failed"]
        issues += [f"TARGET_FAIL:{t.name}:check {i}" for i in res["failed_ids"]]
        if res["failed"]:
            asserted.append(t)  # runtime check failures (not build errors) - ADR-0008 test-integrity record
        if res["passed"] == 0:
            issues.append(f"NO_CHECKS:{t.name}")
    ok = not issues and passed > 0
    record_integrity(ctx.workspace, ctx.phase, "run_renode", "PASS" if ok else "FAIL",
                     integrity(ctx.workspace, tests, asserted))
    undeclared = undeclared_test_changes(ctx.workspace, ctx.phase, "run_renode") if ok else []
    from ...layer import register_prefix

    pfx = register_prefix(ctx.workspace)  # feature 009 (i003 said "RCC model" for the IWDG model)
    log_ref = ctx.store(log)
    artifact_refs = [log_ref]
    performance_metrics = {}
    if budget:
        measured = per.get(Path(budget["test_source"]).name, {}).get("performance")
        if measured:
            elf = wd / (Path(budget["test_source"]).stem + ".elf")
            binary_ref = ctx.store(canonical_json({"schema": "forge-c/elf-evidence/1", "encoding": "base64",
                                                   "sha256": sha256_file(elf),
                                                   "data": base64.b64encode(elf.read_bytes()).decode("ascii")}), "json")
            artifact_refs.append(binary_ref)
            proof = {**measured, "raw_log_ref": log_ref, "elf_artifact_ref": binary_ref}
            proof_ref = ctx.store(canonical_json(proof), "json")
            artifact_refs.append(proof_ref)
            performance_metrics = {"simulation_performance_report": proof_ref}
    return result(ctx, "PASS" if ok and not undeclared else "FAIL", f"renode cortex-m55: {passed} checks passed, "
                  f"{failed} failed ({len(tests)} images; behavioural {pfx} model)"
                  + ("; undeclared test change - declare it" if undeclared else ""), artifact_refs,
                  (undeclared + issues)[:30],
                  {"passed": passed, "failed": failed, "images": per, "cpu": "cortex-m55",
                   "platform": f"forge-stm32n6-{pfx.lower()}-min (CPU+NVIC+AXISRAM+behavioural {pfx})",
                   "target_evidence": "simulated", "silicon_verified": False, **performance_metrics}, "renode",
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
