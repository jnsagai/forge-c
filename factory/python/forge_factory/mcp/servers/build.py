"""T012 — forge-build-mcp: compile/size/stack/disassembly over fixed, allowlisted toolchain profiles.

Callers choose a *profile* and validated macro names only; they can never pass raw compiler flags,
output paths or include dirs. Target profile `target-cm55-gcc` uses GNU Arm Embedded (Cortex-M55);
host profiles exist for unit testing. Missing toolchain -> UNAVAILABLE (never a fake PASS).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..sdk import Operation, ToolContext, ToolDenied, ToolInput, build_server, result, run_argv, tool_version

PROFILES: dict[str, dict] = {
    "host-clang": {"cc": "clang", "size": "llvm-size", "objdump": "llvm-objdump",
                   "flags": ["-std=c11", "-O2", "-g", "-DFORGE_HOST_BUILD=1"]},
    "host-gcc": {"cc": "gcc", "size": "size", "objdump": "objdump", "flags": ["-std=c11", "-O2", "-g",
                                                                             "-DFORGE_HOST_BUILD=1"]},
    "target-cm55-gcc": {"cc": "arm-none-eabi-gcc", "size": "arm-none-eabi-size", "objdump": "arm-none-eabi-objdump",
                        "flags": ["-std=c11", "-mcpu=cortex-m55", "-mthumb", "-mfloat-abi=hard", "-Os",
                                  "-ffunction-sections", "-fdata-sections", "-ffreestanding"]},
}
WARN = ["-Wall", "-Wextra", "-Werror", "-Wconversion", "-Wsign-conversion", "-Wshadow", "-Wcast-align",
        "-Wstrict-prototypes", "-Wmissing-prototypes", "-Wundef", "-pedantic"]
SOURCE_DIRS = ["software/hal", "software/src"]
INCLUDE_DIRS = ["software/hal", "software/ll", "software/include", "inputs/cmsis/include"]
ALLOW = {"clang", "gcc", "arm-none-eabi-gcc", "llvm-size", "size", "arm-none-eabi-size", "llvm-objdump", "objdump",
         "arm-none-eabi-objdump"}
Profile = Literal["host-clang", "host-gcc", "target-cm55-gcc"]
MACRO = re.compile(r"^[A-Z][A-Z0-9_]{1,40}(=[0-9A-Za-z_]{1,20})?$")


class ConfigureIn(ToolInput):
    profile: Profile = "target-cm55-gcc"


class CompileIn(ToolInput):
    profile: Profile = "target-cm55-gcc"
    defines: list[str] = Field(default_factory=list, max_length=10)


class ProfileIn(ToolInput):
    profile: Profile = "target-cm55-gcc"


class DisasmIn(ToolInput):
    profile: Profile = "target-cm55-gcc"
    symbol: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")


def out_dir(ctx: ToolContext, profile: str) -> Path:
    d = ctx.workspace / "build" / profile
    d.mkdir(parents=True, exist_ok=True)
    return d


def sources(ctx: ToolContext) -> list[Path]:
    out: list[Path] = []
    for d in SOURCE_DIRS:
        p = ctx.workspace / d
        if p.is_dir():
            out += sorted(x for x in p.glob("*.c") if not x.is_symlink())
    if not out:
        from ...delivery_first import selected

        cfg, _ = selected(ctx.workspace)
        if cfg and all(ctx.path(raw, must_exist=False).is_file() for raw in cfg["candidate_files"]):
            from ...development_demonstration import validate_inputs

            # Compile the declared build-only probe against the authored header.
            # It contains wrappers, never a substituted driver implementation.
            validate_inputs(ctx.workspace)
            out = [ctx.path(cfg["target_probe"], kind="file")]
    if not out:  # feature 008 (ST pilot): a header-only delivery gets a generated build-only unit (outside the delivery)
        from ...brownfield.cmsis import delivered_unit

        u = delivered_unit(ctx.workspace, ctx.workspace / "build" / "delivered")
        out = [u] if u else []
    return out


def includes(ctx: ToolContext, profile: str = "target-cm55-gcc") -> list[str]:
    from ...brownfield.cmsis import host_flags, target_flags
    from ...delivery_first import include_flags

    # feature 008 (ST pilot): a CMSIS delivery needs the vendor device headers (target) or the host device map (host)
    vendor = target_flags(ctx.workspace) if profile.startswith("target") else host_flags(ctx.workspace)
    return (vendor + include_flags(ctx.workspace)
            + [f"-I{ctx.workspace / d}" for d in INCLUDE_DIRS if (ctx.workspace / d).is_dir()])


def configure(ctx: ToolContext, a: ConfigureIn) -> dict:
    prof = PROFILES[a.profile]
    if not shutil.which(prof["cc"]):
        return result(ctx, "UNAVAILABLE", f"{prof['cc']} not installed", issues=[f"TOOL_MISSING:{prof['cc']}"],
                      tool=prof["cc"], version="unavailable", input_obj=a.model_dump())
    srcs = sources(ctx)
    ver = tool_version(prof["cc"])
    return result(ctx, "PASS" if srcs else "BLOCKED", f"profile {a.profile}: {len(srcs)} sources",
                  issues=[] if srcs else ["NO_SOURCES:software/hal|software/src"],
                  metrics={"sources": len(srcs), "include_dirs": len(includes(ctx))}, tool=prof["cc"], version=ver,
                  input_obj=a.model_dump())


def compile_(ctx: ToolContext, a: CompileIn) -> dict:
    prof = PROFILES[a.profile]
    for m in a.defines:
        if not MACRO.match(m):
            raise ToolDenied("DEFINE_NOT_ALLOWED", m[:40])
    if not shutil.which(prof["cc"]):
        return result(ctx, "UNAVAILABLE", f"{prof['cc']} not installed", issues=[f"TOOL_MISSING:{prof['cc']}"],
                      tool=prof["cc"], version="unavailable")
    od = out_dir(ctx, a.profile)
    log, issues, failed, total_ms = b"", [], 0, 0.0
    srcs = sources(ctx)
    if not srcs:
        return result(ctx, "BLOCKED", "no sources to compile", issues=["NO_SOURCES"], tool=prof["cc"])
    from ...layer import layer_of

    if layer_of(ctx.workspace) == "LL":
        inst = ll_instances(ctx, od)
        if inst is not None:
            srcs = [*srcs, inst]
    from ...brownfield import is_brownfield, manifest_of

    # CAPA-056 (b006): delivered code is frozen input - its warnings are recorded findings, not build failures
    delivered = is_brownfield(manifest_of(ctx.workspace))
    warn = [w for w in WARN if w != "-Werror"] if delivered else WARN
    for src in srcs:
        obj = od / (src.stem + ".o")
        argv = [prof["cc"], *prof["flags"], *warn, *[f"-D{m}" for m in a.defines], *includes(ctx, a.profile), "-fstack-usage",
                "-c", str(src), "-o", str(obj)]
        r = run_argv(argv, od, 180, ALLOW)
        total_ms += r.duration_ms
        log += b"$ " + " ".join(argv).encode() + b"\n" + r.stdout + r.stderr + b"\n"
        if r.exit_code != 0 or delivered:
            failed += r.exit_code != 0
            for line in (r.stderr.decode(errors="replace")).splitlines():
                if ": error:" in line or ": warning:" in line:
                    issues.append(line.split(str(ctx.workspace) + "/")[-1][:120])
    metrics: dict = {"units": len(srcs), "failed_units": failed}
    if not failed and a.profile == "target-cm55-gcc":
        # Relocatable driver image + link map for footprint evidence (NOT a firmware image: no startup/linker script).
        objs = [str(od / (s.stem + ".o")) for s in srcs]
        argv = [prof["cc"], *prof["flags"], "-nostdlib", "-r", f"-Wl,-Map={od / 'driver.map'}", "-o",
                str(od / "driver.elf"), *objs]
        r = run_argv(argv, od, 120, ALLOW)
        log += b"$ " + " ".join(argv).encode() + b"\n" + r.stdout + r.stderr
        metrics["relocatable_elf"] = r.exit_code == 0
        if r.exit_code != 0:
            failed += 1
            issues.append("LINK_RELOCATABLE_FAILED")
    ref = ctx.store(log)
    return result(ctx, "PASS" if not failed else "FAIL", f"{len(srcs) - failed}/{len(srcs)} units compiled ({a.profile})",
                  [ref], issues, metrics, prof["cc"], tool_version(prof["cc"]),
                  0 if not failed else 1, total_ms, a.model_dump(), log)


def ll_instances(ctx: ToolContext, od: Path) -> Path | None:
    """CAPA-013 (r83): the header-only LL compiles to nothing, so size and stack read 0 bytes / 0 functions. For LL
    work orders a measurement unit in the BUILD directory (never a product source) instantiates every LL access
    function once, non-inline, so measure_elf and stack_usage measure the real code."""
    from ...layer import ll_header

    hdr = ctx.workspace / ll_header(ctx.workspace)
    if not hdr.is_file():
        return None
    from ...layer import ll_measure_unit

    text = ll_measure_unit(hdr.read_text(errors="replace"), ctx.workspace)
    if text is None:
        return None
    p = od / "forge_ll_measure.c"
    p.write_text(text)
    return p


def objects(ctx: ToolContext, profile: str) -> list[Path]:
    return sorted((ctx.workspace / "build" / profile).glob("*.o"))


def measure_elf(ctx: ToolContext, a: ProfileIn) -> dict:
    prof = PROFILES[a.profile]
    objs = objects(ctx, a.profile)
    if not objs:
        return result(ctx, "BLOCKED", "no objects; compile first", issues=["NO_OBJECTS"], tool=prof["size"])
    r = run_argv([prof["size"], *[str(o) for o in objs]], ctx.workspace, 60, ALLOW)
    text = data = bss = 0
    for line in r.stdout.decode().splitlines()[1:]:
        cols = line.split()
        if len(cols) >= 3 and cols[0].isdigit():
            text, data, bss = text + int(cols[0]), data + int(cols[1]), bss + int(cols[2])
    ref = ctx.store(r.stdout + r.stderr)
    return result(ctx, "PASS" if r.exit_code == 0 else "FAIL", f"text={text} data={data} bss={bss} ({a.profile})",
                  [ref], [], {"flash_bytes": text + data, "ram_bytes": data + bss, "text": text, "data": data,
                              "bss": bss, "objects": len(objs), "scope": "object-level, not linked image"},
                  prof["size"], tool_version(prof["size"]), r.exit_code, r.duration_ms, a.model_dump(), r.stdout)


def stack_usage(ctx: ToolContext, a: ProfileIn) -> dict:
    sus = sorted((ctx.workspace / "build" / a.profile).glob("*.su"))
    if not sus:
        return result(ctx, "BLOCKED", "no .su files; compile first", issues=["NO_STACK_USAGE"], tool="-fstack-usage")
    rows, raw, issues = [], b"", []
    for su in sus:
        b = su.read_bytes()
        raw += b
        for line in b.decode(errors="replace").splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                rows.append((parts[0].rsplit(":", 1)[-1], int(parts[1]), parts[2]))
                if parts[2] != "static":
                    issues.append(f"NON_STATIC_STACK:{parts[0].rsplit(':', 1)[-1]}:{parts[2]}")
    worst = max(rows, key=lambda x: x[1]) if rows else ("-", 0, "")
    return result(ctx, "PASS" if not issues else "FAIL", f"max frame {worst[1]} B in {worst[0]} ({a.profile})",
                  [ctx.store(raw)], issues, {"functions": len(rows), "max_frame_bytes": worst[1],
                                             "scope": "per-function frames; call-graph worst case not computed"},
                  "gcc/clang -fstack-usage", "profile:" + a.profile, input_obj=a.model_dump())


def disassemble(ctx: ToolContext, a: DisasmIn) -> dict:
    prof = PROFILES[a.profile]
    objs = objects(ctx, a.profile)
    if not objs:
        return result(ctx, "BLOCKED", "no objects; compile first", issues=["NO_OBJECTS"], tool=prof["objdump"])
    r = run_argv([prof["objdump"], "-d", f"--disassemble={a.symbol}", *[str(o) for o in objs]], ctx.workspace, 60, ALLOW)
    lines = [ln for ln in r.stdout.decode(errors="replace").splitlines() if re.match(r"^\s+[0-9a-f]+:", ln)]
    return result(ctx, "PASS" if lines else "FAIL", f"{a.symbol}: {len(lines)} instructions",
                  [ctx.store(r.stdout)], [] if lines else [f"SYMBOL_NOT_FOUND:{a.symbol}"],
                  {"instructions": len(lines)}, prof["objdump"], tool_version(prof["objdump"]), r.exit_code,
                  r.duration_ms, a.model_dump(), r.stdout)


OPERATIONS = [
    Operation("configure", ConfigureIn, configure, "Check toolchain profile and list C sources (no flags accepted)."),
    Operation("compile", CompileIn, compile_, "Compile software/hal+src with a fixed strict profile; log by ref."),
    Operation("measure_elf", ProfileIn, measure_elf, "Object-level Flash/RAM size (text/data/bss)."),
    Operation("stack_usage", ProfileIn, stack_usage, "Per-function stack frames from -fstack-usage."),
    Operation("disassemble", DisasmIn, disassemble, "Disassemble one symbol; full listing by artifact ref."),
]

if __name__ == "__main__":
    build_server("forge-build-mcp", OPERATIONS).run("stdio")
