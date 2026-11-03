"""CAPA-121: the SWE.3 design-level bound of the simulation performance budget, by static analysis.

A work order with a `simulation_performance` allocation has requirements "complete each measured call within N
executed target instructions / M microseconds of virtual time in the pinned Renode simulation"; SWE.6 verifies them by
the Renode entry/return measurement of the `forge_measure_<function>` wrappers (simulation_performance.py). The
detailed design has to show how the bound is met (SWE3-03 "timing ... bounded"), by analysis, before verification.

For a header-only LL the factory computes that bound deterministically: the measurement unit SWE.6 measures
(layer.ll_measure_unit) is compiled with the pinned cross compiler at the target-cm55-gcc release flags and each
wrapper is disassembled. A wrapper whose code is straight-line (no branch, call, loop, table branch, low-overhead loop,
write to pc or wait, one final return) executes each of its instructions at most once per call, so its static
instruction count up to and including the return is an upper bound of the executed instructions. Anything else is
refused as NOT_BOUNDED with the reason; no bound is guessed. The virtual time follows from the instruction count at the
budget's MIPS (Renode's instruction-time model); no hardware WCET is claimed, and the SWE.6 measurement stays the
verification of the requirement.

Owner 2026-11-03: the SWE.3 author gate renders the bound for every author path (structured and native, LL and HAL;
a HAL order bounds its public functions compiled from the HAL source) and an OVER_BUDGET or NOT_BOUNDED result is a
rework finding naming the function, the count and the budget; it is not left to the inspector.

Coordinator 2026-11-03 (owner-delegated timing decision), so that a budgeted HAL order is not STUCK at SWE.3:
(b) a function whose branches all jump forward inside it (no backward branch, loop instruction, call, table branch,
    wait or pc write other than a return) is BOUNDED_STATIC by its instruction count up to the final return: each
    instruction executes at most once per call;
(c) every other function (calls, loops, time-bounded waits) is MEASURED_IN_SIMULATION at SWE.3 by the factory itself,
    with the SWE.6 machinery: the same wrappers/functions, pinned Renode, platform and peripheral model, the budget's
    MIPS, no injected interrupts or bus stalls, on the frozen SWE.2 call-contract cases (nominal path on the default
    model scenario, the never-ready cases on the model's never_ready scenario = timeout path). The measured bound is the
    maximum over the exercised paths only. Only when the measurement is impossible is the function NOT_BOUNDED.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

from .common import sha256_bytes, sha256_file

SCHEMA = "forge-c/swe3-call-bound/2"
EVIDENCE = "workproducts/SWE.3/static_timing_bound.json"
PROFILE = "target-cm55-gcc"
_COND = r"(?:eq|ne|cs|hs|cc|lo|mi|pl|vs|vc|hi|ls|ge|lt|gt|le|al)?"
CONTROL = re.compile(r"^(?:b(?:l|lx|x|xns|lxns)?" + _COND + r"|bf(?:x|l|lx|csel)?|cbn?z|tb[bh]|le|letp|lctp|wls|wlstp|"
                     r"dls|dlstp|svc|bkpt|udf|wfi|wfe)(?:\.[nw])?$")
DATA = re.compile(r"^\.(?:word|short|hword|byte|inst(?:\.[nw])?)$")
LINE = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{4,8} ?)+)\s*\t(\S+)\s*(.*)$")


def _writes_pc(mnemonic: str, operands: str) -> bool:
    ops = operands.split(";", 1)[0].replace(" ", "").lower()
    if mnemonic.startswith(("pop", "ldm")):
        return bool(re.search(r"[{,]pc[},]", ops))
    return ops.startswith("pc,") or ops == "pc"


_BRANCH = re.compile(r"^(?:b" + _COND + r"|cbn?z)(?:\.[nw])?$")
_TARGET = re.compile(r"\b([0-9a-f]+) <")


def _is_return(mn: str, op: str) -> bool:
    """An unconditional return (bx lr, pop {..., pc})."""
    return (mn in ("bx", "bx.n") and op.split(";")[0].strip() == "lr") or (mn in ("pop", "pop.w") and _writes_pc(mn, op))


def _is_cond_return(mn: str, op: str) -> bool:
    base = mn.split(".")[0]
    return ((re.fullmatch(r"bx" + _COND, base) is not None and op.split(";")[0].strip() == "lr")
            or (re.fullmatch(r"pop" + _COND, base) is not None and _writes_pc(mn, op)))


def analyse(listing: str, symbols: list[str]) -> dict[str, dict]:
    """Per symbol of an `objdump -d` listing: the static instruction bound of an acyclic function, or the reason it has
    none. Straight-line code and code whose branches all jump forward inside the function execute each instruction at
    most once, so the instructions up to the final unconditional return bound the executed ones. Data (literal pools)
    is not code; padding after that return is unreachable."""
    blocks: dict[str, list[tuple[int, str, str]]] = {}
    cur = None
    for line in listing.splitlines():
        label = re.fullmatch(r"[0-9a-fA-F]+ <([^>]+)>:", line.strip())
        if label:
            cur = label[1] if label[1] in symbols else None
            if cur is not None:
                blocks[cur] = []
            continue
        m = LINE.match(line)
        if cur is not None and m and not DATA.match(m[3]):
            blocks[cur].append((int(m[1], 16), m[3].lower(), m[4]))
    out = {}
    for name in symbols:
        ins = blocks.get(name)
        if not ins:
            out[name] = {"status": "NOT_BOUNDED", "reason": "SYMBOL_NOT_IN_DISASSEMBLY"}
            continue
        index = {a: k for k, (a, _m, _o) in enumerate(ins)}
        bad, targets, branches = [], [], 0
        for addr, mn, op in ins:
            text = f"{mn} {op.split(';')[0].strip()}".strip()
            if _is_return(mn, op) or _is_cond_return(mn, op):
                branches += not _is_return(mn, op)
            elif _BRANCH.match(mn):
                tm = _TARGET.search(op)
                to = int(tm[1], 16) if tm else None
                if to is None or to not in index:
                    bad.append(f"BRANCH_OUTSIDE_FUNCTION:{text}")
                elif to <= addr:
                    bad.append(f"BACKWARD_BRANCH:{text}")
                else:
                    targets.append(index[to])
                    branches += 1
            elif CONTROL.match(mn) or _writes_pc(mn, op):
                bad.append(f"CALL_LOOP_OR_WAIT:{text}")
            if bad and len(bad) >= 4:
                break
        reach = max(targets, default=0)
        end = next((k for k in range(reach, len(ins)) if _is_return(ins[k][1], ins[k][2])), None)
        tail = [mn for _a, mn, _o in ins[end + 1:]] if end is not None else []
        if bad:
            reason = "NO_STATIC_BOUND:" + "; ".join(bad[:4])
        elif end is None:
            reason = "NO_FINAL_RETURN"
        elif any(not mn.startswith("nop") for mn in tail):
            reason = "CODE_AFTER_RETURN:" + "; ".join(tail[:4])
        else:
            out[name] = {"status": "BOUNDED", "bound": "BOUNDED_STATIC", "static_instructions": end + 1,
                         "method": "STATIC_FORWARD_BRANCHES" if branches else "STATIC_STRAIGHT_LINE",
                         "listing_sha256": sha256_bytes("\n".join(f"{a:x} {b} {c}".strip() for a, b, c in ins).encode())}
            continue
        out[name] = {"status": "NOT_BOUNDED", "reason": reason[:200]}
    return out


def applies(ws: Path) -> bool:
    """A greenfield LL or HAL work order with a simulation performance allocation (CAPA-121; owner 2026-11-03: the
    native SWE.3 path, HAL included, gets the same factory-rendered bound)."""
    from . import layer
    from .brownfield import is_brownfield, manifest_of
    from .simulation_performance import selected

    ws = Path(ws)
    return bool(layer.layer_of(ws) in ("LL", "HAL") and selected(ws) and not is_brownfield(manifest_of(ws)))


def _target(ws: Path, kind: str) -> tuple[str | None, str, list[str], str]:
    """(C text to compile, its name, function names, symbol prefix): LL = the generated measurement unit of the
    header-only LL (the forge_measure_<function> wrappers SWE.6 measures); HAL = the HAL source itself (SWE.6 measures
    the public HAL functions directly)."""
    from . import layer

    if kind == "LL":
        hdr = ws / layer.ll_header(ws)
        unit = layer.ll_measure_unit(hdr.read_text(), ws) if hdr.is_file() else None
        return unit, "forge_ll_measure.c", list(dict.fromkeys(re.findall(r"\bforge_measure_(\w+)\(", unit or ""))), \
            "forge_measure_"
    src = ws / layer.hal_c(ws)
    names = re.findall(r"^[A-Za-z_][\w \t*]*?\b(" + re.escape(layer.api_prefix("HAL", ws)) + r"\w+)\s*\([^;{]*\)\s*\{",
                       src.read_text(), re.M) if src.is_file() else []
    return (src.read_text() if src.is_file() else None), src.name, list(dict.fromkeys(names)), ""


TICK_STUB = ("uint32_t HAL_GetTick(void)\n{\n    static uint32_t forge_tick = 0U;\n    forge_tick++;\n"
             "    return forge_tick;\n}\n")
TICK_NOTE = ("HAL_GetTick is a factory stub returning a counter that advances by 1 per call (the convention of the "
             "factory target tests); the timeout path length depends on it, not on a real system time base")


def _plan(symbols: list[str], disassembly: str, mips: int) -> dict:
    """Entry and caller-return hooks of the measured symbols (the SWE.6 hook format simulation_performance.report
    reads), for the functions this SWE.3 measurement covers."""
    starts, ends = {}, {n: set() for n in symbols}
    for line in disassembly.splitlines():
        label = re.fullmatch(r"([0-9a-fA-F]+) <([^>]+)>:", line)
        if label and label[2] in symbols:
            starts[label[2]] = int(label[1], 16)
        call = re.match(r"^\s*([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{4}\s+)+)bl\s+[0-9a-fA-F]+ <([^>]+)>", line)
        if call and call[3] in symbols:
            ends[call[3]].add(int(call[1], 16) + len(re.findall(r"[0-9a-fA-F]{4}", call[2])) * 2)
    missing = [n for n in symbols if n not in starts or not ends[n]]
    if missing:
        raise ValueError("MEASUREMENT_DIRECT_CALL_MISSING:" + ",".join(missing)[:120])
    coords = [(n, "BEGIN", starts[n]) for n in symbols] + [(n, "END", a) for n in symbols for a in sorted(ends[n])]
    commands = [f"cpu PerformanceInMips {mips}"] + [
        f'cpu AddHook {a:#x} "print \'FORGE_PERF|{n}|{k}|\'+str(self.ExecutedInstructions)+\'|\''
        '+str(self.GetMachine().ElapsedVirtualTime.TimeElapsed.Ticks)"' for n, k, a in coords]
    return {"symbols": symbols, "hooks": coords, "commands": commands, "disassembly_sha256": sha256_bytes(disassembly.encode())}


def _cases(ws: Path, fns: list[str]) -> tuple[dict[str, list], dict[str, list]]:
    """The frozen SWE.2 call-contract cases of each function: (nominal, timeout path). A timeout case is one whose SWE.1
    effect is never-ready or expects HAL_TIMEOUT; it runs on the model's never_ready scenario, as the factory target
    tests do."""
    calls = json.loads((ws / "workproducts/SWE.2/api_calls.json").read_text()).get("calls") or {}
    eff_p = ws / "workproducts/SWE.1/register_effects.json"
    never = {e.get("case") for e in (json.loads(eff_p.read_text()).get("effects") or [] if eff_p.is_file() else [])
             if e.get("ready") == "never" or e.get("status") == "HAL_TIMEOUT"}  # the model's never_ready scenario
    nominal: dict[str, list] = {f: [] for f in fns}
    timeout: dict[str, list] = {f: [] for f in fns}
    for case in sorted(calls):
        c = calls[case]
        if isinstance(c, dict) and c.get("function") in nominal and isinstance(c.get("args"), list):
            (timeout if case in never else nominal)[c["function"]].append({"case": case, **c})
    return nominal, timeout


_MAX_MS = re.compile(r"\bat most\s+(?:[A-Za-z_][A-Za-z0-9_]*\s*=\s*)?(\d+)\s*(?:U\s*)?(?:ms|milliseconds?)\b", re.I)
NO_MAX = "NO_MAX_TIMEOUT: no maximum timeout argument stated in the frozen SWE.1 requirements or the work-order scope"


def max_timeout(ws: Path) -> tuple[int | None, str]:
    """Coordinator 2026-11-03: a measured bound covers the worst case the API permits, so the call contract's {timeout}
    argument is the MAXIMUM the frozen inputs state: an 'at most N ms' of a frozen SWE.1 requirement about the timeout
    (preferred), else of the work-order scope. (None, reason) when none or conflicting values are stated."""
    from .inspection.swtrace import swr_texts

    found: dict[int, str] = {}
    for sid, text in sorted(swr_texts(ws).items()):
        if re.search(r"timeout", text, re.I):
            for m in _MAX_MS.finditer(text):
                found.setdefault(int(m[1]), f"{sid}: '{m[0]}'")
    if not found:
        try:
            scope = json.loads((Path(ws) / ".forge-run/manifest.json").read_text()).get("scope") or []
        except (OSError, ValueError):
            scope = []
        for k, item in enumerate(scope if isinstance(scope, list) else []):
            if isinstance(item, str) and re.search(r"timeout", item, re.I):
                for m in _MAX_MS.finditer(item):
                    found.setdefault(int(m[1]), f"work-order scope item {k + 1}: '{m[0]}'")
    if len(found) > 1:
        return None, "CONFLICTING_MAX_TIMEOUT: " + "; ".join(f"{v} ({src})" for v, src in sorted(found.items()))
    if not found:
        return None, NO_MAX
    (value, src), = found.items()
    return value, src


def measure(ws: Path, kind: str, fns: list[str], budget: dict) -> tuple[dict[str, dict], dict]:
    """MEASURED_IN_SIMULATION at SWE.3 (factory, not the author): per function the maximum executed instructions and
    virtual time over the exercised call-contract cases, or NOT_BOUNDED with the reason the measurement is impossible."""
    from . import layer
    from . import simulation_performance as performance
    from .assurance.register_contract import call_text
    from .mcp.sdk import run_argv
    from .mcp.servers import sim

    ws = Path(ws)
    pr = layer.profile(ws)
    env = {"simulator": f"Renode {sim.RENODE_VERSION} portable", "adapter": sim.ADAPTER_ID,
           "measurement_profile": sim.measurement_profile(ws), "performance_mips": budget["performance_mips"],
           "conditions": "cpu PerformanceInMips at the budget's MIPS; no injected interrupts or bus stalls (the "
                         "factory platform and model unchanged)",
           "platform_sha256": sha256_file(sim.SIM_DIR / pr["sim"]["platform"]),
           "model_sha256": sha256_file(sim.SIM_DIR / pr["sim"]["model"]), "cflags": list(sim.CFLAGS),
           "timeout_argument": None}

    def refuse(reason: str) -> tuple[dict[str, dict], dict]:
        return {f: {"status": "NOT_BOUNDED", "reason": reason[:200]} for f in fns}, env

    renode = sim.renode_bin()
    if renode is None:
        return refuse("MEASUREMENT_UNAVAILABLE:RENODE_NOT_INSTALLED")
    if not shutil.which("arm-none-eabi-gcc") or not shutil.which("arm-none-eabi-objdump"):
        return refuse("MEASUREMENT_UNAVAILABLE:ARM_TOOLCHAIN_MISSING")
    try:
        nominal, timeout = _cases(ws, fns)
    except (OSError, ValueError) as exc:
        return refuse(f"MEASUREMENT_NO_CALL_CONTRACT:{type(exc).__name__}")
    out: dict[str, dict] = {}
    for f in fns:
        if not nominal[f] and not timeout[f]:
            out[f] = {"status": "NOT_BOUNDED", "reason": "MEASUREMENT_NO_SWE2_CALL_CASE"}
    tmax, tsrc = None, ""
    if any("{timeout}" in a for f in fns for c in nominal[f] + timeout[f] for a in c["args"]):
        tmax, tsrc = max_timeout(ws)
        if tmax is None:
            for f in fns:
                if f not in out and any("{timeout}" in a for c in nominal[f] + timeout[f] for a in c["args"]):
                    out[f] = {"status": "NOT_BOUNDED", "reason": tsrc}
        else:
            env["timeout_argument"] = (f"{tmax}U = the maximum the frozen inputs allow ({tsrc}), for every measured "
                                       "case with the {timeout} placeholder; the 10U oracle convention stays for the "
                                       "functional tests only")
            env["max_timeout_ticks"] = tmax
    todo = [f for f in fns if f not in out]
    prefix = "forge_measure_" if kind == "LL" else ""
    samples: dict[str, list] = {f: [] for f in todo}
    paths: dict[str, dict] = {f: {"nominal": [c["case"] for c in nominal[f]],
                                  "timeout": [c["case"] for c in timeout[f]]} for f in todo}
    failure: dict[str, str] = {}
    srcs_text = "".join(p.read_text(errors="replace") for d in ("software/hal", "software/src", "software/ll")
                        for p in sorted((ws / d).glob("*.[ch]")))
    stub = "HAL_GetTick" in srcs_text and not re.search(r"\bHAL_GetTick\s*\(\s*void\s*\)\s*\{", srcs_text)
    if stub:
        env["time_base"] = TICK_NOTE + (f"; the maximum timeout of {tmax} ms corresponds to {tmax} ticks ({tmax} "
                                        "HAL_GetTick calls after the start tick)" if tmax is not None else "")
    with tempfile.TemporaryDirectory(prefix="forge-swe3-timing-") as td:
        wd = Path(td)
        try:
            unit = performance.prepare(ws, wd)
        except ValueError as exc:
            return refuse(f"MEASUREMENT_WRAPPERS_UNAVAILABLE:{exc}")
        seen: set[str] = set()
        srcs = [str(p) for d in ("software/hal", "software/src") for p in sorted((ws / d).glob("*.c"))
                if not (p.name in seen or seen.add(p.name))]
        from .brownfield.cmsis import target_flags
        from .delivery_first import include_flags

        incs = [f"-I{ws / d}" for d in ("software/hal", "software/ll", "software/include") if (ws / d).is_dir()]
        incs += target_flags(ws) + include_flags(ws) + layer.instance_flags(ws, host=False) + [f"-I{wd}"]
        api = Path(layer.api_header(kind, ws)).name
        for scenario, group in (("default", nominal), ("never_ready", timeout)):
            run = [f for f in todo if group[f] and f not in failure]
            if not run:
                continue
            body = [f"    (void){call_text({**c, 'function': prefix + c['function']}, f'{tmax}U')}; /* {c['case']} */"
                    for f in run for c in group[f]]
            drv = wd / f"forge_swe3_timing_{scenario}.c"
            drv.write_text("\n".join(["#include <stdint.h>", '#include "forge_target_test.h"', f'#include "{api}"',
                                      '#include "forge_performance_calls.h"', "FORGE_MAILBOX_DEFINE;",
                                      TICK_STUB if stub else "", "int main(void)", "{", "    FORGE_TEST_BEGIN();",
                                      *body, "    FORGE_TEST_END();", "    return 0;", "}", ""]))
            elf = wd / f"forge_swe3_timing_{scenario}.elf"
            b = run_argv(["arm-none-eabi-gcc", *sim.CFLAGS, *incs, f"-I{sim.SIM_DIR}", "-T",
                          str(sim.linker_script(ws, wd)), str(sim.SIM_DIR / "startup.c"), str(drv), *srcs, str(unit),
                          "-o", str(elf)], wd, 180, {"arm-none-eabi-gcc"})
            if b.exit_code:
                err = next((ln for ln in b.stderr.decode(errors="replace").splitlines() if "error" in ln), "")
                failure.update({f: f"MEASUREMENT_BUILD_FAILED:{scenario}:{err.split(td)[-1][-140:]}" for f in run})
                continue
            listing = run_argv(["arm-none-eabi-objdump", "-d", str(elf)], wd, 60, {"arm-none-eabi-objdump"})
            try:
                plan = _plan([prefix + f for f in run], listing.stdout.decode(errors="replace"),
                             budget["performance_mips"])
            except ValueError as exc:
                failure.update({f: f"{exc}:{scenario}" for f in run})
                continue
            env[f"{scenario}_driver_sha256"] = sha256_file(drv)
            env[f"{scenario}_elf_sha256"] = sha256_file(elf)
            res, _raw = sim.run_image(renode, elf, scenario, wd, ws, measurement=plan)
            perf = (res or {}).get("performance")
            if res is None or not res["magic_ok"] or not res["done"] or perf is None:
                failure.update({f: f"MEASUREMENT_NO_RESULT:{scenario}" for f in run})
                continue
            for f in run:
                sym = prefix + f
                bad = [i for i in perf["issues"] if i.endswith(":" + sym) and not i.startswith("CALL_BUDGET_EXCEEDED")]
                bad += [i for i in perf["issues"] if ":" not in i]
                if bad or not perf["samples"].get(sym):
                    failure[f] = f"MEASUREMENT_INCOMPLETE:{scenario}:{(bad or ['NO_COMPLETED_CALL'])[0]}"
                else:
                    samples[f] += [{**s, "scenario": scenario} for s in perf["samples"][sym]]
    limit_ns = budget["microseconds_per_call"] * 1000
    for f in todo:
        if f in failure:
            out[f] = {"status": "NOT_BOUNDED", "reason": failure[f][:200]}
            continue
        n = max(s["instructions"] for s in samples[f])
        ns = max(s["virtual_nanoseconds"] for s in samples[f])
        exercised = {"nominal": paths[f]["nominal"],
                     "timeout": paths[f]["timeout"] or "not exercised: no timeout case in the SWE.2 call contract"}
        out[f] = {"bound": "MEASURED_IN_SIMULATION", "method": "MEASURED_IN_SIMULATION", "measured_instructions": n,
                  "measured_virtual_ns": ns, "samples": samples[f], "paths": exercised,
                  "status": "WITHIN_BUDGET" if n <= budget["instructions_per_call"] and ns <= limit_ns else "OVER_BUDGET"}
    return out, env


def bound(ws: Path) -> dict | None:
    """The static per-call bound record of every scoped function (None when the work order has no such budget)."""
    from . import layer
    from .mcp.servers import build as B
    from .simulation_performance import selected, symbols

    ws = Path(ws)
    if not applies(ws):
        return None
    kind = layer.layer_of(ws)
    budget = selected(ws)
    prof = B.PROFILES[PROFILE]
    api = layer.api_header(kind, ws)
    text, cname, names, prefix = _target(ws, kind)
    try:  # bound exactly the functions SWE.6 measures
        measured = [s.removeprefix("forge_measure_") for s in symbols(ws)]
    except (OSError, ValueError, KeyError) as exc:
        measured = [f"<{str(exc)[:80]}>"]
    measured_how = ("the forge_measure_<function> wrapper SWE.6 measures" if kind == "LL" else
                    "each public HAL function SWE.6 measures, compiled from its source")
    rec = {"schema": SCHEMA, "layer": kind, "profile": PROFILE, "compiler": prof["cc"], "flags": list(prof["flags"]),
           "header": api, "header_sha256": sha256_file(ws / api) if (ws / api).is_file() else None,
           "budget": {k: budget[k] for k in ("instructions_per_call", "microseconds_per_call", "performance_mips")},
           "method": f"per function: BOUNDED_STATIC = static instruction count of {measured_how} when its code is "
                     "acyclic (straight-line or forward branches only; each instruction executes at most once per call; "
                     "virtual time = instructions x 1000 / MIPS ns, Renode instruction-time model); otherwise "
                     "MEASURED_IN_SIMULATION = maximum executed instructions and virtual time of the function over the "
                     "frozen SWE.2 call-contract cases in the pinned Renode simulation (nominal path; timeout path where "
                     "the model forces it); NOT_BOUNDED only when the measurement is impossible",
           "verification": "SWE.6 Renode measurement (Simulation Performance Should Meet Budget)",
           "hardware_wcet": "NOT_CLAIMED", "functions": {}}
    if kind == "HAL":
        rec.update(source=layer.hal_c(ws), source_sha256=sha256_file(ws / layer.hal_c(ws)) if text else None)
    missing = [t for t in (prof["cc"], prof["objdump"]) if not shutil.which(t)]
    if text is None or missing or sorted(names) != sorted(measured):
        rec.update(status="NOT_BOUNDED", issues=[f"TOOL_MISSING:{t}" for t in missing] or (
            [f"NO_{kind}_FUNCTIONS"] if text is None else
            [f"MEASURED_SCOPE_MISMATCH:{','.join(sorted(measured))[:160]}"]))
        return rec
    from .mcp.sdk import tool_version

    rec["compiler_version"] = tool_version(prof["cc"])
    if kind == "LL":
        rec["measurement_unit_sha256"] = sha256_bytes(text.encode())
    with tempfile.TemporaryDirectory(prefix="forge-static-timing-") as td:
        src, obj = Path(td) / cname, Path(td) / (Path(cname).stem + ".o")
        src.write_text(text)
        cc = subprocess.run([prof["cc"], *prof["flags"], *B.includes(SimpleNamespace(workspace=ws), PROFILE), "-c",
                             str(src), "-o", str(obj)], capture_output=True, text=True, cwd=td, timeout=120)
        if cc.returncode:
            rec.update(status="NOT_BOUNDED", issues=["COMPILE_FAILED:" + cc.stderr.strip()[-200:]])
            return rec
        dis = subprocess.run([prof["objdump"], "-d", str(obj)], capture_output=True, text=True, cwd=td, timeout=60)
        rec["object_sha256"] = sha256_file(obj)
    if dis.returncode:
        rec.update(status="NOT_BOUNDED", issues=["DISASSEMBLY_FAILED"])
        return rec
    limit_ns = budget["microseconds_per_call"] * 1000
    unbounded = {}
    for name, r in analyse(dis.stdout, [prefix + n for n in names]).items():
        fn = name.removeprefix(prefix)
        if r["status"] == "BOUNDED":
            n = r["static_instructions"]
            ns = -(-n * 1000 // budget["performance_mips"])
            r = {**r, "virtual_ns_bound": ns,
                 "status": "WITHIN_BUDGET" if n <= budget["instructions_per_call"] and ns <= limit_ns else "OVER_BUDGET"}
        else:
            unbounded[fn] = r["reason"]
        rec["functions"][fn] = r
    if unbounded:  # (c): no static bound -> the factory measures them in the pinned simulation at SWE.3
        got, env = measure(ws, kind, list(unbounded), budget)
        rec["measurement"] = env
        for fn, r in got.items():
            rec["functions"][fn] = {**r, "static_reason": unbounded[fn]}
    states = {r["status"] for r in rec["functions"].values()}
    rec["status"] = ("OVER_BUDGET" if "OVER_BUDGET" in states else "NOT_BOUNDED" if "NOT_BOUNDED" in states
                     else "WITHIN_BUDGET")
    return rec


def _value(r: dict) -> tuple[int, int, str]:
    if "static_instructions" in r:
        return r["static_instructions"], r["virtual_ns_bound"], "static bound"
    return r["measured_instructions"], r["measured_virtual_ns"], "measured"


def findings(rec: dict | None, swrs: list[str]) -> list[str]:
    """Owner 2026-11-03: an over-budget or unbounded result fails the SWE.3 author gate and goes back to the code rework,
    one precise finding per function; function, count and budget come first (compact replies keep 120 chars)."""
    if rec is None or rec["status"] == "WITHIN_BUDGET":
        return []
    b = rec["budget"]
    lim = f"budget {b['instructions_per_call']} instr/{b['microseconds_per_call']} us per call"
    tail = (f" at {b['performance_mips']} MIPS in the pinned Renode simulation"
            + (f" ({', '.join(swrs)})" if swrs else "") + "; SWE.6 measurement remains the verification")
    out = [f"STATIC_TIMING_NOT_BOUNDED: no bound for the {lim}: {i}{tail}" for i in rec.get("issues") or []]
    for fn, r in rec["functions"].items():
        if r["status"] == "OVER_BUDGET":
            n, ns, how = _value(r)
            out.append(f"STATIC_TIMING_OVER_BUDGET: {fn}: {how} {n} instr/{ns} ns exceeds the {lim}{tail}; reduce the "
                       f"code of {fn}")
        elif r["status"] == "NOT_BOUNDED":
            up = ("; this is an upstream gap: report_defect kind REQUIREMENT (SWE.1) to state the maximum timeout"
                  if r["reason"].startswith(("NO_MAX_TIMEOUT", "CONFLICTING_MAX_TIMEOUT")) else "")
            out.append(f"STATIC_TIMING_NOT_BOUNDED: {fn}: no bound for the {lim}: {r['reason']}"
                       + (f" (no static bound: {r['static_reason']})" if r.get("static_reason") else "") + tail + up)
    return out


METHOD_TEXT = {"STATIC_STRAIGHT_LINE": "static (straight-line)", "STATIC_FORWARD_BRANCHES": "static (forward branches)",
               "MEASURED_IN_SIMULATION": "measured in simulation"}


def design_section(rec: dict, swrs: list[str]) -> list[str]:
    """The detailed-design section rendered exactly from the record."""
    b = rec["budget"]
    out = [SECTION, "",
           f"Requirements {', '.join(swrs) or '(simulation performance budget)'}: at most {b['instructions_per_call']} "
           f"executed target instructions and {b['microseconds_per_call']} microseconds of virtual time per measured "
           f"call at {b['performance_mips']} MIPS. Design-level bound computed by the factory from "
           f"{rec.get('compiler_version') or rec['compiler']} at the {rec['profile']} flags "
           f"({' '.join(rec['flags'])}) on {rec['header']} (sha256 {str(rec['header_sha256'])[:16]}): {rec['method']}. "
           f"Evidence: {EVIDENCE}. Verification of the requirements: {rec['verification']}; hardware WCET is not "
           "claimed.", ""]
    if m := rec.get("measurement"):
        out += [f"Measurement at SWE.3: {m['measurement_profile']}; {m['conditions']}. A measured bound covers only the "
                "paths listed; it is not a bound for unexercised inputs."
                + (f" Timeout argument: {m['timeout_argument']}." if m.get("timeout_argument") else "")
                + (f" {m['time_base']}." if m.get("time_base") else ""), ""]
    out += [f"Overall: {rec['status']}.", ""]
    if rec.get("issues"):
        out += [f"- no bound: {', '.join(rec['issues'])}", ""]
        return out
    out += ["| Function | Method | Bound (instructions) | Virtual time (ns) | Result | Paths |",
            "| --- | --- | --- | --- | --- | --- |"]
    for fn, r in rec["functions"].items():
        if r["status"] == "NOT_BOUNDED":
            out.append(f"| {fn} | - | - | - | NOT_BOUNDED ({r['reason']}) | - |")
            continue
        n, ns, _how = _value(r)
        p = r.get("paths")
        paths = "every path (acyclic code)"
        if p:
            to = ", ".join(p["timeout"]) if isinstance(p["timeout"], list) else p["timeout"]
            paths = f"nominal: {', '.join(p['nominal']) or 'none'}; timeout: {to}"
        out.append(f"| {fn} | {METHOD_TEXT[r['method']]} | {n} | {ns} | {r['status']} | {paths} |")
    return out + [""]


def performance_swrs(ws: Path, reqs: dict[str, str]) -> list[str]:
    """The SWR ids of the work order's generated simulation performance requirements (exact statement match)."""
    from .lrtx.swe1 import budget_requirements, system_name

    want = {r["statement"] for r in budget_requirements(ws, system_name(ws)) if r["upstream"] == "WO-SIMULATION-PERFORMANCE"}
    return sorted(s for s, t in reqs.items() if t.strip() in want)


def render(rec: dict) -> str:
    return json.dumps(rec, indent=1, sort_keys=True) + "\n"


SECTION = "## Timing bound (static analysis and measurement)"
DESIGN = "workproducts/SWE.3/detailed_design.md"


def with_section(design: str, section: list[str]) -> str:
    """The design text with the factory-rendered timing section replacing an earlier one (else appended)."""
    text = "\n".join(section).rstrip("\n") + "\n"
    m = re.search(r"^## Timing bound\b[^\n]*\n.*?(?=^## |\Z)", design, re.M | re.S)
    if m:
        return design[:m.start()] + text + ("\n" if design[m.end():] else "") + design[m.end():]
    return design.rstrip("\n") + "\n\n" + text


def swrs_of(ws: Path, reqs: dict[str, str] | None = None) -> list[str]:
    try:
        if reqs is None:
            from .inspection.swtrace import swr_texts

            reqs = swr_texts(ws)
        return performance_swrs(ws, reqs)
    except (OSError, ValueError, KeyError):
        return []


def gate(ws: Path) -> list[str]:
    """SWE.3 author gate, every author path (structured and native, LL and HAL): render the bound into the detailed
    design and the frozen evidence file, deterministically, and return its findings (none for an order without the
    budget). A missing detailed design is left to the presence gate."""
    ws = Path(ws)
    rec = bound(ws)
    if rec is None:
        return []
    swrs = swrs_of(ws)
    dd = ws / DESIGN
    if dd.is_file():
        new = with_section(dd.read_text(), design_section(rec, swrs))
        if new != dd.read_text():
            dd.write_text(new)
    ev = ws / EVIDENCE
    if not ev.is_file() or ev.read_text() != render(rec):
        ev.parent.mkdir(parents=True, exist_ok=True)
        ev.write_text(render(rec))
    return findings(rec, swrs)
