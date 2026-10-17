"""EASA-T032/T034..T039 — SWE.3 defensive-code assurance with real analyzers and honest coverage.

* coding policy: the Table 1 / Table 6 working-index methods are mapped to concrete, executable checks (clang
  warnings, clang analyzer, clang-tidy, cppcheck + MISRA addon subset, deterministic rules); a method without an
  executable check is CONTROLLED_REVIEW, never PASS by default;
* MISRA inventory: the rules the installed cppcheck addon actually implements versus the rules of MISRA C:2012
  (compliance is NEVER claimed); deviations only from an approved deviation record, never from code comments;
* seeded-defect probes: each analyzer is run on a fixture with a known defect; a miss is a recorded COVERAGE_GAP;
* concurrency/timeout/reentrancy invariants (shared-register races, unbounded polling loops, mutable static state);
* resource evidence tagged MEASURED / ESTIMATED / UNKNOWN per environment;
* formal proof adapter: CBMC when installed (bounded, assumptions recorded), otherwise NOT_SUPPORTED.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..common import data_root
from . import hardware

MISRA_ADDON = Path("/usr/lib/x86_64-linux-gnu/cppcheck/addons/misra.py")
POLICY = {  # method id -> executable checks (tool:check) ; empty = controlled review only
    "ISO6-T01-1A": ["clang-tidy:readability-function-cognitive-complexity"],
    "ISO6-T01-1B": ["cppcheck:misra-addon-subset", "rule:no-goto-malloc-recursion-vla"],
    "ISO6-T01-1C": ["clang:-Wconversion -Wsign-conversion"],
    "ISO6-T01-1F": [],
    "ISO6-T01-1G": ["guideline:hal_guideline_conformance"],
    "ISO6-T01-1H": ["guideline:hal_guideline_conformance"],
    "ISO6-T06-1A": ["cppcheck:misra-15.5"],
    "ISO6-T06-1B": ["rule:no-dynamic-memory"],
    "ISO6-T06-1C": ["clang:-Wuninitialized", "clang-analyzer:core.uninitialized"],
    "ISO6-T06-1D": ["guideline:hal_guideline_conformance"],
    "ISO6-T06-1F": ["clang-analyzer:core.NullDereference", "cppcheck:misra-18.4"],
    "ISO6-T06-1G": ["clang:-Wconversion"],
    "ISO6-T06-1H": ["cppcheck:misra-13.5", "rule:no-mutable-static-state"],
    "ISO6-T06-1I": ["cppcheck:misra-15.1", "rule:no-goto-malloc-recursion-vla"],
}


def coding_policy(catalog: dict) -> list[dict]:
    out = []
    for m in catalog["methods"]:
        if m["table"] not in (1, 6):
            continue
        checks = POLICY.get(m["method_id"], [])
        out.append({"method_id": m["method_id"], "paraphrase": m["paraphrase"], "checks": checks,
                    "resolution": "EXECUTABLE" if checks else "CONTROLLED_REVIEW",
                    "misra_compliance": "NOT_CLAIMED"})
    return out


# ---- MISRA inventory and deviation control -------------------------------------------------------------------------
def misra_inventory(standard_rules: list[str]) -> dict:
    """Rules the installed addon implements (from its source) vs the standard body; compliance never claimed."""
    if not MISRA_ADDON.is_file():
        return {"status": "NOT_SUPPORTED", "reason": "cppcheck MISRA addon not installed", "implemented": [],
                "unsupported": sorted(standard_rules), "misra_compliance": "NOT_CLAIMED"}
    src = MISRA_ADDON.read_text(errors="replace")
    impl = sorted({f"{a}.{b}" for a, b in re.findall(r"def misra_(\d+)_(\d+)\(", src)},
                  key=lambda r: tuple(int(x) for x in r.split(".")))
    std = sorted(set(standard_rules), key=lambda r: tuple(int(x) for x in re.findall(r"\d+", r)))
    covered = [r for r in std if r in impl]
    return {"status": "MEASURED", "tool": "cppcheck MISRA addon", "implemented_in_addon": len(impl),
            "standard_rules": len(std), "covered": len(covered), "unsupported": [r for r in std if r not in impl],
            "coverage_note": "rules implemented by the addon; decidability, configuration and directive coverage "
                             "are NOT assessed - manual review required for the rest",
            "misra_compliance": "NOT_CLAIMED"}


SUPPRESS = re.compile(r"(cppcheck-suppress|NOLINT|misra-c2012-\d+\.\d+.*deviat|#pragma\s+(GCC|clang)\s+diagnostic\s+ignored)")


def deviation_findings(code: dict[str, str], deviations: list[dict]) -> list[str]:
    """A suppression in code must match an approved deviation record (rule, file, rationale, human approver)."""
    from .policy import _human

    f = []
    approved = {(d.get("rule"), d.get("file")) for d in deviations
                if d.get("rationale") and len(str(d["rationale"])) >= 20 and _human(d.get("approved_by"))}
    for d in deviations:
        if not _human(d.get("approved_by")):
            f.append(f"DEVIATION_NOT_HUMAN_APPROVED:{d.get('rule')}")
    for path, text in code.items():
        for i, line in enumerate(text.splitlines(), 1):
            m = SUPPRESS.search(line)
            if m:
                rule = (re.search(r"misra-c2012-(\d+\.\d+)", line) or re.search(r"(\d+\.\d+)", line))
                key = (rule.group(1) if rule else None, Path(path).name)
                if key not in approved:
                    f.append(f"UNAPPROVED_SUPPRESSION:{Path(path).name}:{i}")
    return f


# ---- seeded-defect probes with real analyzers -------------------------------------------------------------------
PROBES = {  # name -> (source, {analyzer: signature that counts as detection})
    "uninitialized_use": ("int f(int c)\n{\n    int x;\n    if (c > 0) { x = 1; }\n    return x;\n}\n",
                          {"clang-analyzer": "core.uninitialized", "clang-warn": "uninitialized"}),
    "null_dereference": ("#include <stddef.h>\nint g(int *p)\n{\n    int *q = NULL;\n    if (p == NULL) { return *q; }\n"
                         "    return *p;\n}\n", {"clang-analyzer": "core.NullDereference"}),
    "implicit_narrowing": ("#include <stdint.h>\nuint8_t h(uint32_t v)\n{\n    uint8_t r = v;\n    return r;\n}\n",
                           {"clang-warn": "loses integer precision"}),
    "goto_use": ("int k(int a)\n{\n    if (a) { goto out; }\n    a = 2;\nout:\n    return a;\n}\n",
                 {"cppcheck-misra": "misra-c2012-15.1", "rule": "FORBIDDEN:goto"}),
    "dynamic_memory": ("#include <stdlib.h>\nint *m(void)\n{\n    return malloc(4);\n}\n",
                       {"cppcheck-misra": "misra-c2012-21.3", "rule": "FORBIDDEN:malloc"}),
}


def _run(argv: list[str], cwd: Path) -> tuple[int, str]:
    r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=180)
    return r.returncode, r.stdout + r.stderr


def analyze_file(path: Path) -> dict[str, list[str]]:
    """Run the real analyzers on one C file; returns findings per analyzer (empty list = nothing found)."""
    out: dict[str, list[str]] = {}
    d = path.parent
    if shutil.which("clang"):
        _, t = _run(["clang", "--analyze", "-std=c11", "-Xanalyzer", "-analyzer-output=text", "-o", "/dev/null",
                     str(path)], d)
        out["clang-analyzer"] = [ln.split(": warning: ")[1][:100] for ln in t.splitlines() if ": warning: " in ln]
        _, t = _run(["clang", "-fsyntax-only", "-std=c11", "-Wall", "-Wextra", "-Wconversion", "-Wsign-conversion",
                     "-Wuninitialized", "-Wsometimes-uninitialized", str(path)], d)
        out["clang-warn"] = [ln.split(": warning: ")[1][:100] for ln in t.splitlines() if ": warning: " in ln]
    if shutil.which("cppcheck") and MISRA_ADDON.is_file():
        _, t = _run(["cppcheck", "--std=c11", "--enable=warning,style", f"--addon={MISRA_ADDON}",
                     "--template={id}:{line}", str(path)], d)
        out["cppcheck-misra"] = [ln for ln in t.splitlines() if re.match(r"^[\w.-]+:\d+", ln)
                                 and not ln.startswith(("missingInclude", "checkersReport"))]
    text = path.read_text()
    out["rule"] = [f"FORBIDDEN:{w}" for w in ("malloc", "calloc", "realloc", "free", "goto") if re.search(rf"\b{w}\b", text)]
    return out


def seeded_probe_campaign() -> list[dict]:
    """T034/T039: every probe must be caught by at least one expected analyzer; a miss is a COVERAGE_GAP."""
    rows = []
    with tempfile.TemporaryDirectory() as td:
        for name, (src, expected) in PROBES.items():
            p = Path(td) / f"{name}.c"
            p.write_text(src)
            found = analyze_file(p)
            caught = [a for a, sig in expected.items() if any(sig in x for x in found.get(a, []))]
            missed = [a for a in expected if a not in caught]
            rows.append({"probe": name, "expected": expected, "caught_by": caught, "missed_by": missed,
                         "status": "CAUGHT" if caught else "COVERAGE_GAP",
                         "details": {a: found.get(a, [])[:4] for a in expected}})
    return rows


# ---- concurrency / timeout / reentrancy (T035 / T036 / AT-036) -----------------------------------------------
LOOP = re.compile(r"\b(while|for)\s*\((.*?)\)\s*\{", re.S)


def invariant_findings(code: dict[str, str], header_defs: str, idx: dict[str, dict], mitigation_stated: bool) -> list[str]:
    f = []
    rmw_by_reg: dict[str, set[str]] = {}
    for path, text in code.items():
        for fm in re.finditer(r"^[A-Za-z_][\w\s\*]*?\b(\w+)\s*\([^;{)]*\)\s*\{(.*?)^\}", text, re.S | re.M):
            body = fm.group(2)
            for w in hardware.check_writes(body, header_defs, idx):
                if w.startswith("NON_ATOMIC_RMW:"):
                    rmw_by_reg.setdefault(w.split(":")[1], set()).add(fm.group(1))
            for lm in LOOP.finditer(body):
                cond = lm.group(2)
                if re.search(r"IsReady|IsEnabled|ll_rcc_regs", cond) and not re.search(r"(<|<=)\s*\w+", cond):
                    f.append(f"LOOP_UNBOUNDED:{fm.group(1)}@{Path(path).name}")
        for m in re.finditer(r"^\s*static\s+(?!inline|const|hal_status_t|void|uint32_t\s+\w+\s*\()[\w\s]+\b(\w+)\s*(=[^;]*)?;",
                             text, re.M):
            f.append(f"REENTRANCY_STATE:{m.group(1)}@{Path(path).name}")
    for reg, fns in sorted(rmw_by_reg.items()):
        if len(fns) > 1 and not mitigation_stated:
            f.append(f"SHARED_REGISTER_RACE_UNMITIGATED:{reg}:{','.join(sorted(fns))}")
    return f


# ---- resources (T037) ------------------------------------------------------------------------------------------
def resource_evidence(tool_results: dict[str, dict | None], budgets: dict[str, int]) -> list[dict]:
    """tool_results: {'measure_elf': result|None, 'stack_usage': result|None} (latest MCP results)."""
    out = []
    me, su = tool_results.get("measure_elf"), tool_results.get("stack_usage")
    for metric, res, key in (("flash_bytes", me, "flash_bytes"), ("static_ram_bytes", me, "ram_bytes"),
                             ("stack_bytes", su, "max_frame_bytes")):
        val = ((res or {}).get("metrics") or {}).get(key)
        prov = "MEASURED" if res and res.get("status") == "PASS" and val is not None else "UNKNOWN"
        out.append({"metric": metric, "value": val if prov == "MEASURED" else None, "provenance": prov,
                    "environment": "target-cm55-gcc object-level (not a linked image)" if prov == "MEASURED" else None,
                    "budget": budgets.get(metric), "within_budget": (val <= budgets[metric]) if prov == "MEASURED"
                    and budgets.get(metric) is not None else None,
                    "note": "stack = largest single frame (stack_usage); call-chain depth estimated separately"
                    if metric == "stack_bytes" else None})
    out.append({"metric": "execution_time", "value": None, "provenance": "UNKNOWN", "environment": None,
                "budget": budgets.get("execution_time"), "within_budget": None,
                "note": "no cycle-accurate model or target trace: timing is not measured"})
    return out


# ---- formal proof adapter (T038) ------------------------------------------------------------------------------
def cbmc_bin() -> str | None:
    cand = sorted((data_root() / "toolchains").glob("cbmc*/**/bin/cbmc"))
    return str(cand[0]) if cand else shutil.which("cbmc")


def bounded_proof(harness: Path, includes: list[Path], unwind: int = 1001, function: str = "harness") -> dict:
    exe = cbmc_bin()
    if exe is None:
        return {"status": "NOT_SUPPORTED", "tool": "cbmc", "reason": "CBMC is not installed on this host",
                "assumptions": [], "claims": []}
    argv = [exe, str(harness), "--function", function, "--unwind", str(unwind), "--unwinding-assertions",
            "--bounds-check", "--pointer-check", "--signed-overflow-check", "--unsigned-overflow-check"]
    for i in includes:
        argv += ["-I", str(i)]
    r = subprocess.run(argv, capture_output=True, text=True, timeout=900)
    ver = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    ok = r.returncode == 0 and "VERIFICATION SUCCESSFUL" in r.stdout
    return {"status": "PASS" if ok else ("FAIL" if "VERIFICATION FAILED" in r.stdout else "ERROR"), "tool": "cbmc",
            "version": ver, "argv": argv, "exit_code": r.returncode,
            "assumptions": [f"loops unwound to {unwind} (unwinding assertions on)", "registers modelled as plain "
                            "nondeterministic memory (no hardware side effects)", "single-threaded, no interrupts"],
            "claims": re.findall(r"\[(\S+)\] .*?: (SUCCESS|FAILURE)", r.stdout)[:50],
            "scope": "bounded model of the C semantics, NOT physical hardware behaviour"}


def fabricated_calls(code: str, header: str, prefix: str = "LL_RCC_") -> list[str]:
    """AT-039: calls to driver API functions that the (provided) header does not define - an invented API."""
    defined = set(re.findall(rf"\b({prefix}\w+)\s*\([^;{{]*\)\s*\{{", header))
    called = set(re.findall(rf"\b({prefix}\w+)\s*\(", code)) - set(re.findall(rf"\b({prefix}\w+)\s*\([^;{{]*\)\s*\{{", code))
    return [f"FABRICATED_API:{c}" for c in sorted(called - defined)]
