"""Opt-in instruction/virtual-time measurements in the existing Renode path; no silicon timing claims."""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

from .afo.durable import digest
from .common import sha256_file

FIELD = "simulation_performance"
SCHEMA = "forge-c/simulation-performance-budget/1"
TEST = "software/tests/target/test_performance.c"


def validate(value):
    if (not isinstance(value, dict) or set(value) != {"schema", "instructions_per_call", "microseconds_per_call",
                                                   "performance_mips", "test_source"}
            or value.get("schema") != SCHEMA or value.get("test_source") != TEST
            or any(type(value.get(k)) is not int or not 1 <= value[k] <= limit
                   for k, limit in (("instructions_per_call", 100_000_000), ("microseconds_per_call", 1_000_000),
                                    ("performance_mips", 1_000_000)))):
        raise ValueError("SIMULATION_PERFORMANCE_BUDGET_INVALID")
    return value


def selected(ws):
    path = Path(ws) / ".forge-run/manifest.json"
    if not path.is_file():
        return None
    manifest = json.loads(path.read_text())
    return validate(manifest[FIELD]) if FIELD in manifest else None


def _authored_scope(ws):
    """Reuse the driver profile and C index; unsupported APIs refuse rather than disappear from coverage."""
    from . import layer
    from .brownfield.scope import FUNC_HEAD, _blank_directives, _skip_if0, index, strip_comments

    ws = Path(ws)
    kind = layer.layer_of(ws)
    if kind not in ("LL", "HAL"):
        raise ValueError("SIMULATION_PERFORMANCE_AUTHORED_SCOPE_LAYER_UNSUPPORTED")
    header = layer.api_header(kind, ws)
    text = (ws / header).read_text()
    prefix = layer.api_prefix(kind, ws)
    definitions = [d for d in index(text, header) if d.name.startswith(prefix)]
    code = _blank_directives(_skip_if0(strip_comments(text)))
    declaration_rx = re.compile(FUNC_HEAD.pattern.removesuffix(r"\{") + ";")
    declarations = [m for m in declaration_rx.finditer(code) if m["name"].startswith(prefix)]
    candidates = set(re.findall(r"\b(" + re.escape(prefix) + r"\w+)\s*\(", code))
    if kind == "LL":
        names = [d.name for d in definitions if d.kind == "static_inline"]
        valid = not declarations and all(d.kind == "static_inline" for d in definitions)
    else:
        names = [m["name"] for m in declarations]
        source = layer.hal_c(ws)
        impl = _blank_directives(_skip_if0(strip_comments((ws / source).read_text())))
        implemented = [m["name"] for m in FUNC_HEAD.finditer(impl)
                       if not re.search(r"\bstatic\b", m["quals"])]
        valid = (not definitions and all(not re.search(r"\bstatic\b", m["quals"]) for m in declarations)
                 and all(implemented.count(name) == 1 for name in names))
    if not valid or not names or len(names) != len(set(names)) or set(names) != candidates:
        raise ValueError("SIMULATION_PERFORMANCE_AUTHORED_SCOPE_UNSUPPORTED_OR_INCOMPLETE")
    return kind, names, text


def _delivered(ws):
    from .brownfield import is_brownfield, manifest_of

    return is_brownfield(manifest_of(Path(ws)))


def symbols(ws):
    if _delivered(ws):
        scope = json.loads((Path(ws) / ".forge-run/delivery/scope.json").read_text())
        names = ["forge_measure_" + f["name"] for f in scope.get("functions", [])]
    else:
        kind, public, _ = _authored_scope(ws)
        names = [("forge_measure_" if kind == "LL" else "") + name for name in public]
    if not names or len(names) != len(set(names)) or any(not re.fullmatch(r"[A-Za-z_]\w{0,150}", n) for n in names):
        raise ValueError("SIMULATION_PERFORMANCE_SCOPE_UNMEASURED")
    return names


def source_files(ws):
    return {p.relative_to(ws).as_posix(): sha256_file(p)
            for name in ("software/ll", "software/hal", "software/src", "software/include", "inputs/vendor/include")
            for p in sorted((Path(ws) / name).rglob("*")) if p.is_file() and p.suffix in (".c", ".h")}


def inputs(ws):
    return {"source_files": source_files(ws), "test_source_sha256": sha256_file(Path(ws) / selected(ws)["test_source"]),
            "budget_sha256": digest(selected(ws))}


def prepare(ws, output):
    from .brownfield.cmsis import delivered_unit

    ws, output = Path(ws), Path(output)
    if _delivered(ws):
        unit = delivered_unit(ws, output)
    else:
        from . import layer

        kind, _, text = _authored_scope(ws)
        content = (layer.ll_measure_unit(text, ws) if kind == "LL" else
                   f'#include "{Path(layer.hal_h(ws)).name}"\n')
        if not content:
            raise ValueError("SIMULATION_PERFORMANCE_WRAPPERS_UNAVAILABLE")
        unit = output / "forge_authored_performance.c"
        unit.write_text(content)
    if unit is None:
        raise ValueError("SIMULATION_PERFORMANCE_WRAPPERS_UNAVAILABLE")
    text = unit.read_text()
    declarations = [ln for ln in text.splitlines() if ln.startswith("#include") or
                    re.fullmatch(r"[^{}]+forge_measure_\w+\([^{}]*\);", ln)]
    for name in (n for n in symbols(ws) if n.startswith("forge_measure_")):
        if not any(re.search(r"\b" + re.escape(name) + r"\(", line) for line in declarations):
            raise ValueError("SIMULATION_PERFORMANCE_WRAPPER_MISSING:" + name)
    header = output / "forge_performance_calls.h"
    header.write_text("/* Generated measurement declarations; driver sources remain unchanged. */\n" +
                      "\n".join(declarations) + "\n")
    return unit


def plan(ws, disassembly):
    """Direct entry and actual caller-return PCs, without estimating the return instruction's cost."""
    wanted = symbols(ws)
    starts, ends = {}, {name: set() for name in wanted}
    for line in disassembly.splitlines():
        label = re.fullmatch(r"([0-9a-fA-F]+) <([^>]+)>:", line)
        if label and label[2] in wanted:
            starts[label[2]] = int(label[1], 16)
        call = re.match(r"^\s*([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{4}\s+)+)bl\s+[0-9a-fA-F]+ <([^>]+)>", line)
        if call and call[3] in wanted:
            ends[call[3]].add(int(call[1], 16) + len(re.findall(r"[0-9a-fA-F]{4}", call[2])) * 2)
    if set(starts) != set(wanted) or any(not ends[name] for name in wanted):
        raise ValueError("SIMULATION_PERFORMANCE_DIRECT_CALL_COVERAGE_MISSING")
    coordinates = [(name, "BEGIN", starts[name]) for name in wanted] + [
        (name, "END", address) for name in wanted for address in sorted(ends[name])]
    if len({address for _, _, address in coordinates}) != len(coordinates):
        raise ValueError("SIMULATION_PERFORMANCE_HOOK_OVERLAP")
    commands = [f'cpu PerformanceInMips {selected(ws)["performance_mips"]}']
    for name, kind, address in coordinates:
        hook = (f"print 'FORGE_PERF|{name}|{kind}|'+str(self.ExecutedInstructions)+'|'"
                "+str(self.GetMachine().ElapsedVirtualTime.TimeElapsed.Ticks)")
        commands.append(f'cpu AddHook {address:#x} "{hook}"')
    return {"symbols": wanted, "hooks": coordinates, "commands": commands,
            "disassembly_sha256": digest(disassembly), "budget_sha256": digest(selected(ws))}


def report(ws, instrumentation, log):
    budget = selected(ws)
    pending, samples, issues = {}, {name: [] for name in instrumentation["symbols"]}, []
    rx = re.compile(r"^FORGE_PERF\|([A-Za-z_]\w*)\|(BEGIN|END)\|(\d+)\|(\d+)\s*$", re.M)
    for name, kind, count, nanos in rx.findall(log):
        if name not in samples:
            issues.append("UNKNOWN_SYMBOL:" + name)
            continue
        count, nanos = int(count), int(nanos)
        if kind == "BEGIN":
            if pending:  # Nested/recursive cases need a separately qualified observer.
                issues.append("OVERLAPPING_CALLS:" + name)
            pending[name] = (count, nanos)
        elif name not in pending:
            issues.append("ORPHAN_RETURN:" + name)
        else:
            before, start = pending.pop(name)
            if count <= before or nanos < start:
                issues.append("NONMONOTONIC_MEASUREMENT:" + name)
                continue
            if (nanos - start + 1) * budget["performance_mips"] < (count - before) * 1000:
                issues.append("VIRTUAL_CLOCK_ACCOUNTING_MISMATCH:" + name)
                continue
            samples[name].append({"instructions": count - before, "virtual_nanoseconds": nanos - start})
    if pending:
        issues.append("INCOMPLETE_CALL")
    for name, values in samples.items():
        if not values:
            issues.append("NO_COMPLETED_CALL:" + name)
        elif any(v["instructions"] > budget["instructions_per_call"] or
                 v["virtual_nanoseconds"] > budget["microseconds_per_call"] * 1000 for v in values):
            issues.append("CALL_BUDGET_EXCEEDED:" + name)
    return {"schema": "forge-c/simulation-call-performance/1", "status": "FAIL" if issues else "PASS",
            "budget_sha256": digest(budget), "performance_mips": budget["performance_mips"],
            "samples": samples, "issues": issues, "hardware_wcet": "NOT_MEASURED",
            "scope": "observed complete calls in the pinned Renode instruction/time model; not silicon timing",
            "measurement_plan": {k: v for k, v in instrumentation.items() if k != "commands"}}


def verify_result(ws, result):
    """Recompute CPU/time checks from the normal tool's sealed raw evidence, not a model's status assertion."""
    ws = Path(ws)

    def artifact(ref, kind):
        if ref not in result.get("artifact_refs", []) or not re.fullmatch(r"artifact:sha256:[0-9a-f]{64}", ref or ""):
            raise ValueError("SIMULATION_PERFORMANCE_ARTIFACT_UNBOUND")
        path = ws / "evidence/raw" / (ref.split(":")[-1] + "." + kind)
        if path.is_symlink() or not path.is_file() or sha256_file(path) != ref.split(":")[-1]:
            raise ValueError("SIMULATION_PERFORMANCE_ARTIFACT_CHANGED")
        return path.read_text()

    proof_ref = result.get("metrics", {}).get("simulation_performance_report")
    proof = json.loads(artifact(proof_ref, "json"))
    plan = proof["measurement_plan"]
    binary = json.loads(artifact(proof["elf_artifact_ref"], "json"))
    if (binary.get("schema") != "forge-c/elf-evidence/1" or binary.get("encoding") != "base64"
            or binary.get("sha256") != plan["elf_sha256"]
            or hashlib.sha256(base64.b64decode(binary["data"], validate=True)).hexdigest() != plan["elf_sha256"]):
        raise ValueError("SIMULATION_PERFORMANCE_ELF_CHANGED")
    if (set(plan["symbols"]) != set(symbols(ws))
            or plan["budget_sha256"] != digest(selected(ws))
            or plan["source_files"] != source_files(ws)
            or plan["observer_sha256"] != sha256_file(Path(__file__))
            or plan["test_source_sha256"] != sha256_file(ws / selected(ws)["test_source"])):
        raise ValueError("SIMULATION_PERFORMANCE_INPUT_CHANGED")
    recomputed = report(ws, plan, artifact(proof["raw_log_ref"], "log"))
    if any(recomputed[k] != proof[k] for k in ("status", "budget_sha256", "samples", "issues")):
        raise ValueError("SIMULATION_PERFORMANCE_RESULT_CHANGED")
    return recomputed
