"""T013 — forge-analysis-mcp: Clang Static Analyzer, Cppcheck (+ MISRA C:2012 addon SUBSET), clang-tidy.

MISRA: Cppcheck's addon checks a subset of rules and, without the licensed rule texts, reports rule
numbers only. Results always state `misra_compliance: NOT_CLAIMED` and the rules *not* covered by the
tool. CBMC and Frama-C are not installed on this host -> UNAVAILABLE (disabled, never emulated).
"""
from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET

from ..sdk import Operation, ToolContext, ToolInput, build_server, result, run_argv, tool_version
from .build import INCLUDE_DIRS, SOURCE_DIRS

ALLOW = {"cppcheck", "clang", "clang-tidy", "python3"}
MISRA_ADDON = "/usr/lib/x86_64-linux-gnu/cppcheck/addons/misra.py"
# MISRA C:2012 rules (main body) used only for coverage accounting by rule number; no rule text bundled.
MISRA_RULES = [f"{a}.{b}" for a, n in [(1, 4), (2, 7), (3, 2), (4, 2), (5, 9), (6, 2), (7, 4), (8, 14), (9, 5),
                                       (10, 8), (11, 9), (12, 5), (13, 6), (14, 4), (15, 7), (16, 7), (17, 8),
                                       (18, 8), (19, 2), (20, 14), (21, 21), (22, 10)] for b in range(1, n + 1)]


class AnalyzeIn(ToolInput):
    pass


def srcs(ctx: ToolContext) -> list[str]:
    out = []
    for d in SOURCE_DIRS + ["software/ll"]:
        p = ctx.workspace / d
        if p.is_dir():
            out += [str(x) for x in sorted(p.glob("*.[ch]"))]
    return out


def incs(ctx: ToolContext) -> list[str]:
    return [f"-I{ctx.workspace / d}" for d in INCLUDE_DIRS if (ctx.workspace / d).is_dir()]


def cppcheck(ctx: ToolContext, a: AnalyzeIn) -> dict:
    if not shutil.which("cppcheck"):
        return result(ctx, "UNAVAILABLE", "cppcheck not installed", issues=["TOOL_MISSING:cppcheck"], tool="cppcheck")
    files = srcs(ctx)
    if not files:
        return result(ctx, "BLOCKED", "no sources", issues=["NO_SOURCES"], tool="cppcheck")
    # No --inline-suppr: a suppression comment written by an AI agent is a self-granted MISRA deviation and is ignored.
    argv = ["cppcheck", "--xml", "--xml-version=2", "--enable=warning,style,performance,portability",
            "--std=c11", "--error-exitcode=0", f"--addon={MISRA_ADDON}", *incs(ctx), *files]
    r = run_argv(argv, ctx.workspace, 170, ALLOW, mem_mb=4096)
    issues, misra_hits, general = [], set(), 0
    try:
        root = ET.fromstring(r.stderr.decode(errors="replace"))  # noqa: S314 - local cppcheck output, not external input
        for err in root.iter("error"):
            eid = err.get("id", "")
            loc = err.find("location")
            where = f"{(loc.get('file') or '').split('/')[-1]}:{loc.get('line')}" if loc is not None else "-"
            m = re.match(r"misra-c2012-(\d+\.\d+)", eid)
            if m:
                misra_hits.add(m.group(1))
                issues.append(f"MISRA-{m.group(1)}:{where}")
            elif eid not in ("missingIncludeSystem", "missingInclude", "unmatchedSuppression", "checkersReport"):
                general += 1
                issues.append(f"{err.get('severity')}:{eid}:{where}")
    except ET.ParseError:
        issues.append("CPPCHECK_OUTPUT_UNPARSEABLE")
    ref = ctx.store(r.stdout + r.stderr, "xml")
    findings = len(issues)
    return result(ctx, "PASS" if findings == 0 and r.exit_code == 0 else "FAIL",
                  f"cppcheck: {general} general, {len(misra_hits)} MISRA rules hit (subset only)", [ref], issues,
                  {"general_findings": general, "misra_rules_violated": len(misra_hits),
                   "misra_rules_in_standard_body": len(MISRA_RULES), "misra_compliance": "NOT_CLAIMED",
                   "misra_coverage_note": "addon subset; undecidable/manual rules require human review"},
                  "cppcheck", tool_version("cppcheck"), r.exit_code, r.duration_ms, a.model_dump(), r.stderr)


def clang_analyze(ctx: ToolContext, a: AnalyzeIn) -> dict:
    files = [f for f in srcs(ctx) if f.endswith(".c")]
    if not files:
        return result(ctx, "BLOCKED", "no C sources", issues=["NO_SOURCES"], tool="clang")
    log, issues, ms = b"", [], 0.0
    for f in files:
        r = run_argv(["clang", "--analyze", "-std=c11", "-DFORGE_HOST_BUILD=1", *incs(ctx), "-Xanalyzer",
                      "-analyzer-output=text", "-o", "/dev/null", f], ctx.workspace, 120, ALLOW)
        ms += r.duration_ms
        log += r.stdout + r.stderr
        for line in r.stderr.decode(errors="replace").splitlines():
            if ": warning:" in line or ": error:" in line:
                issues.append(line.split("/")[-1][:120])
    return result(ctx, "PASS" if not issues else "FAIL", f"clang analyzer: {len(issues)} diagnostics",
                  [ctx.store(log)], issues, {"files": len(files), "diagnostics": len(issues)}, "clang --analyze",
                  tool_version("clang"), 0, ms, a.model_dump(), log)


def clang_tidy(ctx: ToolContext, a: AnalyzeIn) -> dict:
    if not shutil.which("clang-tidy"):
        return result(ctx, "UNAVAILABLE", "clang-tidy not installed", issues=["TOOL_MISSING:clang-tidy"],
                      tool="clang-tidy")
    files = [f for f in srcs(ctx) if f.endswith(".c")]
    checks = "-*,bugprone-*,cert-*,clang-analyzer-*,misc-*,readability-braces-around-statements,-misc-include-cleaner"
    r = run_argv(["clang-tidy", f"--checks={checks}", "--quiet", *files, "--", "-std=c11", "-DFORGE_HOST_BUILD=1",
                  *incs(ctx)], ctx.workspace, 170, ALLOW, mem_mb=4096)
    issues = [ln.split("/")[-1][:120] for ln in r.stdout.decode(errors="replace").splitlines()
              if ": warning:" in ln or ": error:" in ln]
    return result(ctx, "PASS" if not issues and r.exit_code == 0 else "FAIL", f"clang-tidy: {len(issues)} findings",
                  [ctx.store(r.stdout + r.stderr)], issues, {"findings": len(issues)}, "clang-tidy",
                  tool_version("clang-tidy"), r.exit_code, r.duration_ms, a.model_dump(), r.stdout)


def unavailable(name: str):
    def h(ctx: ToolContext, a: AnalyzeIn) -> dict:
        return result(ctx, "UNAVAILABLE", f"{name} not installed on this host; operation disabled",
                      issues=[f"TOOL_MISSING:{name}", "SAFETY_GAP:formal_verification_not_performed"], tool=name,
                      version="unavailable")
    return h


OPERATIONS = [
    Operation("cppcheck", AnalyzeIn, cppcheck, "Cppcheck + MISRA C:2012 addon subset (compliance never claimed)."),
    Operation("clang_analyze", AnalyzeIn, clang_analyze, "Clang Static Analyzer over driver sources."),
    Operation("clang_tidy", AnalyzeIn, clang_tidy, "clang-tidy bugprone/cert/analyzer checks."),
    Operation("cbmc_verify", AnalyzeIn, unavailable("cbmc"), "CBMC bounded model checking (disabled: not installed)."),
    Operation("frama_check", AnalyzeIn, unavailable("frama-c"), "Frama-C (disabled: not installed)."),
]

if __name__ == "__main__":
    build_server("forge-analysis-mcp", OPERATIONS).run("stdio")
