"""T014 — forge-tests-mcp: host unit/integration tests + LLVM source-based coverage incl. MC/DC.

Each `software/tests/<level>/test_*.c` is linked with the driver sources into its own host executable
(`-DFORGE_HOST_TEST=1`, register blocks are provided by the test via the driver's host hook), run with a
timeout, and counted PASS (exit 0) / FAIL. Coverage uses LLVM 19 `-fcoverage-mcdc`; raw .profraw and
merged .profdata are preserved by artifact ref. Host results are explicitly NOT target evidence.
Unity/CMock are not vendored on this host: tests are self-checking C programs (documented gap).
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Literal

from ...inspection.defects import integrity, record_integrity
from ..sdk import Operation, ToolContext, ToolInput, build_server, result, run_argv, tool_version
from .build import INCLUDE_DIRS, SOURCE_DIRS

ALLOW = {"clang", "gcc", "llvm-profdata", "llvm-cov", "gcovr"}
COV_FLAGS = ["-fprofile-instr-generate", "-fcoverage-mapping", "-fcoverage-mcdc"]


class RunIn(ToolInput):
    coverage: bool = True


class CovIn(ToolInput):
    level: Literal["unit", "integration", "software"] = "unit"


def _diag(raw: bytes, ws, markers: tuple[str, ...], limit: int) -> list[str]:
    """First diagnostic lines (compiler errors / failing test cases), workspace-relative and truncated."""
    out = []
    for line in raw.decode(errors="replace").splitlines():
        if any(m in line for m in markers):
            out.append(line.split(str(ws) + "/")[-1].strip()[:140])
            if len(out) >= limit:
                break
    return out


def _run_level(ctx: ToolContext, level: str, coverage: bool) -> dict:
    tdir = ctx.workspace / "software" / "tests" / level
    tests = sorted(tdir.glob("test_*.c")) if tdir.is_dir() else []
    if not tests:
        return result(ctx, "BLOCKED", f"no {level} tests", issues=[f"NO_TESTS:software/tests/{level}"], tool="clang")
    srcs = [str(p) for d in SOURCE_DIRS for p in sorted((ctx.workspace / d).glob("*.c"))
            if (ctx.workspace / d).is_dir()]
    incs = [f"-I{ctx.workspace / d}" for d in INCLUDE_DIRS + [f"software/tests/{level}"] if (ctx.workspace / d).is_dir()]
    bdir = ctx.workspace / "build" / f"tests-{level}"
    if bdir.exists():
        shutil.rmtree(bdir)
    bdir.mkdir(parents=True)
    log, passed, failed, issues, ms = b"", 0, 0, [], 0.0
    asserted: list[Path] = []  # runtime (not build) failures - ADR-0008 test-integrity record
    for t in tests:
        exe = bdir / t.stem
        argv = ["clang", "-std=c11", "-O0", "-g", "-Wall", "-Wextra", "-DFORGE_HOST_TEST=1", "-DFORGE_HOST_BUILD=1",
                *(COV_FLAGS if coverage else []), *incs, str(t), *srcs, "-o", str(exe)]
        b = run_argv(argv, bdir, 180, ALLOW)
        log += b"$ " + " ".join(argv).encode() + b"\n" + b.stdout + b.stderr
        if b.exit_code != 0:
            failed += 1
            issues.append(f"BUILD_FAIL:{t.name}")
            issues += _diag(b.stderr, ctx.workspace, (": error:",), 12)  # the agent cannot fix what it cannot see
            continue
        r = run_argv([str(exe)], bdir, 60, ALLOW | {exe.name},
                     env_extra={"LLVM_PROFILE_FILE": str(bdir / f"{t.stem}.profraw")} if coverage else None)
        ms += r.duration_ms
        log += f"$ {exe.name} -> exit {r.exit_code}\n".encode() + r.stdout + r.stderr  # full raw output kept by ref
        if r.exit_code == 0:
            passed += 1
        else:
            failed += 1
            asserted.append(t)
            issues.append(f"TEST_FAIL:{t.name}:exit{r.exit_code}" + (":TIMEOUT" if r.timed_out else ""))
            issues += _diag(r.stdout + r.stderr, ctx.workspace, ("FAIL",), 12)
    (bdir / "results.json").write_text(json.dumps({"level": level, "passed": passed, "failed": failed}))
    record_integrity(ctx.workspace, ctx.phase, "run_unit" if level == "unit" else "run_integration",
                     "PASS" if failed == 0 else "FAIL", integrity(ctx.workspace, tests, asserted))
    return result(ctx, "PASS" if failed == 0 else "FAIL", f"{level}: {passed} passed, {failed} failed (HOST)",
                  [ctx.store(log)], issues, {"passed": passed, "failed": failed, "executables": len(tests),
                                             "environment": "host", "target_evidence": False},
                  "clang+self-checking tests", tool_version("clang"), 0 if failed == 0 else 1, ms, None, log)


def run_unit(ctx: ToolContext, a: RunIn) -> dict:
    return _run_level(ctx, "unit", a.coverage)


def run_integration(ctx: ToolContext, a: RunIn) -> dict:
    out = _run_level(ctx, "integration", a.coverage)
    if out["status"] == "BLOCKED":
        alt = _run_level(ctx, "software", a.coverage)
        if alt["status"] != "BLOCKED":
            return alt
    return out


def llvm_coverage(ctx: ToolContext, a: CovIn) -> dict:
    bdir = ctx.workspace / "build" / f"tests-{a.level}"
    raws = sorted(bdir.glob("*.profraw")) if bdir.is_dir() else []
    exes = [p for p in sorted(bdir.glob("test_*")) if p.is_file() and p.suffix == ""] if bdir.is_dir() else []
    if not raws or not exes:
        return result(ctx, "BLOCKED", "no coverage data; run tests with coverage", issues=["NO_PROFRAW"],
                      tool="llvm-cov")
    prof = bdir / "merged.profdata"
    m = run_argv(["llvm-profdata", "merge", "-sparse", *map(str, raws), "-o", str(prof)], bdir, 60, ALLOW)
    if m.exit_code != 0:
        return result(ctx, "FAIL", "llvm-profdata merge failed", [ctx.store(m.stderr)], ["PROFDATA_MERGE_FAILED"],
                      tool="llvm-profdata")
    srcs = [str(p) for d in SOURCE_DIRS for p in sorted((ctx.workspace / d).glob("*.c")) if (ctx.workspace / d).is_dir()]
    objs = [str(exes[0])] + [x for e in exes[1:] for x in ("-object", str(e))]
    r = run_argv(["llvm-cov", "export", "-summary-only", f"-instr-profile={prof}", *objs, *srcs], bdir, 60, ALLOW)
    rep = run_argv(["llvm-cov", "report", "-show-mcdc-summary", f"-instr-profile={prof}", *objs, *srcs], bdir, 60, ALLOW)
    try:
        totals = json.loads(r.stdout)["data"][0]["totals"]
    except (ValueError, KeyError, IndexError):
        return result(ctx, "FAIL", "coverage export unparseable", [ctx.store(r.stdout + r.stderr)], ["COV_PARSE"],
                      tool="llvm-cov")

    def pct(k: str) -> float | None:
        v = totals.get(k)
        return round(float(v["percent"]), 2) if v and v.get("count") else None

    metrics = {"line_pct": pct("lines"), "branch_pct": pct("branches"), "function_pct": pct("functions"),
               "region_pct": pct("regions"), "mcdc_pct": pct("mcdc"), "environment": "host",
               "target_evidence": False}
    refs = [ctx.store(r.stdout, "json"), ctx.store(rep.stdout + rep.stderr), ctx.store(prof.read_bytes(), "profdata")]
    return result(ctx, "PASS", f"line {metrics['line_pct']}% branch {metrics['branch_pct']}% "
                  f"MC/DC {metrics['mcdc_pct']}% (host)", refs, [], metrics, "llvm-cov", tool_version("llvm-cov"),
                  r.exit_code, r.duration_ms + rep.duration_ms, a.model_dump(), r.stdout)


def gcov_coverage(ctx: ToolContext, a: CovIn) -> dict:
    return result(ctx, "UNSUPPORTED", "gcov path not configured for this pilot; use llvm_coverage",
                  issues=["OPTIONAL_OP_DISABLED:gcov_coverage"], tool="gcovr", version=tool_version("gcovr"))


class RobotIn(ToolInput):
    pass


def run_robot(ctx: ToolContext, a: RobotIn) -> dict:
    """SWE.6 requirement-based tests: Robot Framework suites (software/tests/software/*.robot) using the ForgeTarget
    keyword library on the Renode STM32N6 model. PASS only if every test passes and every SWE.1 requirement is the
    tag of at least one passing test."""
    import os
    import sys
    import xml.etree.ElementTree as ET  # noqa: N817

    from ...common import REPO_ROOT
    from ...inspection.architecture import SWR

    suites = sorted((ctx.workspace / "software/tests/software").glob("*.robot"))
    if not suites:
        return result(ctx, "BLOCKED", "no Robot suites", issues=["NO_TESTS:software/tests/software/*.robot"],
                      tool="robotframework")
    from .robot_policy import check_suite

    policy = [i for s in suites for i in check_suite(s)]
    if policy:  # r57: a suite is code - only the factory keyword library may run (no Process/OperatingSystem/eval)
        return result(ctx, "FAIL", f"robot suite rejected by policy ({len(policy)} issues): use only Library "
                      "ForgeTarget and its keywords", issues=policy[:30], tool="robotframework")
    out = ctx.workspace / "build" / "robot"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    py = sys.executable
    env = {"DOTNET_EnableWriteXorExecute": "0", "DOTNET_GCHeapHardLimit": "0x60000000",
           **{k: os.environ[k] for k in ("FORGE_STATE_DIR", "FORGE_DATA_ROOT") if os.environ.get(k)}}
    # -I: isolated mode, so modules in the (agent-written) workspace cannot shadow stdlib/robot/ForgeTarget imports
    r = run_argv([py, "-I", "-m", "robot", "--pythonpath", str(REPO_ROOT / "factory/sim/stm32n6"), "--pythonpath",
                  str(REPO_ROOT / "factory/python"), "--outputdir", str(out), "--consolecolors", "off",
                  "--console", "dotted", *[str(s) for s in suites]], ctx.workspace, 570, {os.path.basename(py)},
                 env_extra=env, mem_mb=65536, fsize_mb=512)
    xml = out / "output.xml"
    if not xml.is_file():
        return result(ctx, "FAIL", "robot produced no output.xml", [ctx.store(r.stdout + r.stderr)],
                      ["ROBOT_NO_OUTPUT"], tool="robotframework", exit_code=r.exit_code)
    tests, issues, covered = [], [], set()
    for t in ET.parse(xml).getroot().iter("test"):  # noqa: S314 - output.xml written by the local robot run
        tags = [x.text or "" for x in t.findall("./tags/tag")] or [x.text or "" for x in t.findall("./tag")]
        st = t.find("status")
        status = st.get("status") if st is not None else "FAIL"
        tests.append({"name": t.get("name"), "tags": tags, "status": status})
        if status == "PASS":
            covered |= {g for g in tags if SWR.fullmatch(g)}
        else:
            msg = (st.text or "").strip().replace("\n", " ")[:120] if st is not None else ""
            issues.append(f"ROBOT_FAIL:{t.get('name')}:{msg}")
    req = ctx.workspace / "workproducts/SWE.1/software_requirements.md"
    reqs = sorted(set(re.findall(r"\*\*(SWR-[A-Z0-9_.-]+)\*\*", req.read_text()))) if req.is_file() else []
    issues += [f"UNCOVERED_REQUIREMENT:{x}" for x in reqs if x not in covered]
    passed = sum(1 for t in tests if t["status"] == "PASS")
    sdir = ctx.workspace / "software/tests/software"
    from ...inspection.ears import extract
    from .robot_policy import unobserved_requirements

    texts = {r.req_id: r.text for r in extract(req.read_text(errors="replace"))} if req.is_file() else {}
    unobserved = [i for s in suites for i in unobserved_requirements(s, sdir, texts)]
    issues = unobserved + issues  # a passing test that never checks what its requirement demands verifies nothing
    covered -= {i.split(":")[1] for i in unobserved}
    ok = bool(tests) and passed == len(tests) and not unobserved \
        and not [i for i in issues if i.startswith("UNCOVERED")]
    scn = sorted(sdir.glob("*.c"))
    asserted = sorted({sdir / m for i in issues if i.startswith("ROBOT_FAIL:") and "build failed" not in i
                       for m in re.findall(r"\b([\w-]+\.c) \[", i)})  # failing checks, not build errors
    record_integrity(ctx.workspace, ctx.phase, "run_robot", "PASS" if ok else "FAIL",
                     integrity(ctx.workspace, [*suites, *scn], asserted))
    return result(ctx, "PASS" if ok else "FAIL",
                  f"robot: {passed}/{len(tests)} tests passed; {len(covered & set(reqs))}/{len(reqs)} requirements "
                  "verified (Renode STM32N6 model + host measurements)",
                  [ctx.store(xml.read_bytes(), "xml")], issues[:30],
                  {"tests": len(tests), "passed": passed, "failed": len(tests) - passed, "requirements": len(reqs),
                   "requirements_verified": len(covered & set(reqs)), "environment": "robotframework 6.1 + renode "
                   "1.17.0 (simulated cortex-m55)", "silicon_verified": False},
                  "robotframework", tool_version(py, ("-m", "robot", "--version")), r.exit_code, r.duration_ms,
                  a.model_dump(), r.stdout + r.stderr)


OPERATIONS = [
    Operation("run_unit", RunIn, run_unit, "Build+run software/tests/unit/test_*.c on host (coverage optional)."),
    Operation("run_integration", RunIn, run_integration, "Build+run integration (or software-level) host tests."),
    Operation("run_robot", RobotIn, run_robot,
              "SWE.6: run Robot Framework requirement tests (software/tests/software/*.robot) on the Renode model."),
    Operation("llvm_coverage", CovIn, llvm_coverage, "LLVM line/branch/MC/DC coverage summary; raw data by ref."),
    Operation("gcov_coverage", CovIn, gcov_coverage, "gcov/gcovr coverage (disabled in this pilot)."),
]

if __name__ == "__main__":
    build_server("forge-tests-mcp", OPERATIONS).run("stdio")
