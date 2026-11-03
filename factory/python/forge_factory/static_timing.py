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

SCHEMA = "forge-c/static-call-bound/1"
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


def analyse(listing: str, symbols: list[str]) -> dict[str, dict]:
    """Per symbol of an `objdump -d` listing: the static instruction bound of a straight-line function, or the reason
    it has none. Data (literal pools) is not code; padding after the single final return is unreachable."""
    blocks: dict[str, list[tuple[str, str]]] = {}
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
            blocks[cur].append((m[3].lower(), m[4]))
    out = {}
    for name in symbols:
        ins = blocks.get(name)
        if not ins:
            out[name] = {"status": "NOT_BOUNDED", "reason": "SYMBOL_NOT_IN_DISASSEMBLY"}
            continue
        ret = next((k for k, (mn, op) in enumerate(ins) if (mn.split(".")[0] == "bx" and op.split(";")[0].strip() == "lr")
                    or (mn.startswith("pop") and _writes_pc(mn, op))), None)
        before = ins[:ret] if ret is not None else ins
        bad = [f"{mn} {op.split(';')[0].strip()}".strip() for mn, op in before
               if CONTROL.match(mn) or _writes_pc(mn, op)]
        tail = [mn for mn, _op in ins[ret + 1:]] if ret is not None else []
        if ret is None:
            reason = "NO_FINAL_RETURN"
        elif bad:
            reason = "NOT_STRAIGHT_LINE:" + "; ".join(bad[:4])
        elif any(not mn.startswith("nop") for mn in tail):
            reason = "CODE_AFTER_RETURN:" + "; ".join(tail[:4])
        else:
            out[name] = {"status": "BOUNDED", "static_instructions": ret + 1,
                         "listing_sha256": sha256_bytes("\n".join(f"{a} {b}".strip() for a, b in ins).encode())}
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
    measured_how = ("the straight-line forge_measure_<function> wrapper SWE.6 measures" if kind == "LL" else
                    "each public HAL function SWE.6 measures, compiled from its source")
    rec = {"schema": SCHEMA, "layer": kind, "profile": PROFILE, "compiler": prof["cc"], "flags": list(prof["flags"]),
           "header": api, "header_sha256": sha256_file(ws / api) if (ws / api).is_file() else None,
           "budget": {k: budget[k] for k in ("instructions_per_call", "microseconds_per_call", "performance_mips")},
           "method": f"static instruction count of {measured_how}; straight-line code only (each instruction executes "
                     "at most once per call); virtual time = instructions x 1000 / MIPS ns (Renode instruction-time "
                     "model); refused (NOT_BOUNDED) for any branch, call, loop or wait",
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
    for name, r in analyse(dis.stdout, [prefix + n for n in names]).items():
        fn = name.removeprefix(prefix)
        if r["status"] == "BOUNDED":
            n = r["static_instructions"]
            ns = -(-n * 1000 // budget["performance_mips"])
            r = {**r, "virtual_ns_bound": ns,
                 "status": "WITHIN_BUDGET" if n <= budget["instructions_per_call"] and ns <= limit_ns else "OVER_BUDGET"}
        rec["functions"][fn] = r
    states = {r["status"] for r in rec["functions"].values()}
    rec["status"] = ("OVER_BUDGET" if "OVER_BUDGET" in states else "NOT_BOUNDED" if "NOT_BOUNDED" in states
                     else "WITHIN_BUDGET")
    return rec


def findings(rec: dict | None, swrs: list[str]) -> list[str]:
    """Owner 2026-11-03: an over-budget or unbounded static result fails the SWE.3 author gate and goes back to the code
    rework, one precise finding per function; function, count and budget come first (compact replies keep 120 chars)."""
    if rec is None or rec["status"] == "WITHIN_BUDGET":
        return []
    b = rec["budget"]
    lim = f"budget {b['instructions_per_call']} instr/{b['microseconds_per_call']} us per call"
    tail = (f" at {b['performance_mips']} MIPS in the pinned Renode simulation"
            + (f" ({', '.join(swrs)})" if swrs else "") + "; SWE.6 measurement remains the verification")
    out = [f"STATIC_TIMING_NOT_BOUNDED: no static bound for the {lim}: {i}{tail}" for i in rec.get("issues") or []]
    for fn, r in rec["functions"].items():
        if r["status"] == "OVER_BUDGET":
            out.append(f"STATIC_TIMING_OVER_BUDGET: {fn}: static bound {r['static_instructions']} instr/"
                       f"{r['virtual_ns_bound']} ns exceeds the {lim}{tail}; reduce the code of {fn}")
        elif r["status"] == "NOT_BOUNDED":
            how = (f"write {fn} without branches, calls, loops or waits" if rec.get("layer", "LL") == "LL" else
                   "the factory computes no static bound for HAL code with branches, calls or waits")
            out.append(f"STATIC_TIMING_NOT_BOUNDED: {fn}: no static bound for the {lim}: {r['reason']} (not "
                       f"straight-line code){tail}; {how}")
    return out


def design_section(rec: dict, swrs: list[str]) -> list[str]:
    """The detailed-design section rendered exactly from the record."""
    b = rec["budget"]
    out = ["## Timing bound (static analysis)", "",
           f"Requirements {', '.join(swrs) or '(simulation performance budget)'}: at most {b['instructions_per_call']} "
           f"executed target instructions and {b['microseconds_per_call']} microseconds of virtual time per measured "
           f"call at {b['performance_mips']} MIPS. Design-level bound computed by the factory from "
           f"{rec.get('compiler_version') or rec['compiler']} at the {rec['profile']} flags "
           f"({' '.join(rec['flags'])}) on {rec['header']} (sha256 {str(rec['header_sha256'])[:16]}): {rec['method']}. "
           f"Evidence: {EVIDENCE}. Verification of the requirements: {rec['verification']}; hardware WCET is not "
           "claimed.", "", f"Overall: {rec['status']}.", ""]
    if rec.get("issues"):
        out += [f"- no static bound: {', '.join(rec['issues'])}", ""]
        return out
    out += ["| Function | Static bound (instructions) | Derived virtual time (ns) | Result |", "| --- | --- | --- | --- |"]
    for fn, r in rec["functions"].items():
        if "static_instructions" in r:
            out.append(f"| {fn} | {r['static_instructions']} | {r['virtual_ns_bound']} | {r['status']} |")
        else:
            out.append(f"| {fn} | - | - | NOT_BOUNDED ({r['reason']}) |")
    return out + [""]


def performance_swrs(ws: Path, reqs: dict[str, str]) -> list[str]:
    """The SWR ids of the work order's generated simulation performance requirements (exact statement match)."""
    from .lrtx.swe1 import budget_requirements, system_name

    want = {r["statement"] for r in budget_requirements(ws, system_name(ws)) if r["upstream"] == "WO-SIMULATION-PERFORMANCE"}
    return sorted(s for s, t in reqs.items() if t.strip() in want)


def render(rec: dict) -> str:
    return json.dumps(rec, indent=1, sort_keys=True) + "\n"


SECTION = "## Timing bound (static analysis)"
DESIGN = "workproducts/SWE.3/detailed_design.md"


def with_section(design: str, section: list[str]) -> str:
    """The design text with the factory-rendered timing section replacing an earlier one (else appended)."""
    text = "\n".join(section).rstrip("\n") + "\n"
    m = re.search(r"^" + re.escape(SECTION) + r"[^\n]*\n.*?(?=^## |\Z)", design, re.M | re.S)
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
