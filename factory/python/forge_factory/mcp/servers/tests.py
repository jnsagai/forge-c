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

from ...inspection.defects import integrity, record_integrity, undeclared_test_changes
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


def _with_setter(expr: str, src_before: str) -> str:
    """r68: 'st == HAL_ERROR' -> 'st == HAL_ERROR with st = HAL_RCC_HSI_Enable(0U)' (last assignment before)."""
    v = re.match(r"\(?\s*([a-z_]\w*)\s*[=!<>]", expr)
    code = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', src_before)  # r76: never a 'st=%u' inside a printf format
    setter = re.findall(rf"\b{v.group(1)}\s*=\s*([^;=][^;]*);", code) if v else []
    return f"{expr} with {v.group(1)} = {' '.join(setter[-1].split())}" if setter else expr


HOST_CHECK = re.compile(r'\bCHECK\(\s*"([^"]+)"\s*,(.*?)\)\s*;', re.S)


def _host_check_exprs(test: Path, out: bytes, limit: int = 8) -> list[str]:
    """r74: run_integration said only 'IT-001 FAIL'; the SWE.5 author rewrote the test model three times blind.
    Name the failed check's expression and the call that set its variable, like run_robot's CHECK_EXPR."""
    ids = re.findall(r"^\s*(\S+) FAIL\b", out.decode(errors="replace"), re.M)
    src = test.read_text(errors="replace")
    exprs = []
    for cid in dict.fromkeys(ids):
        m = next((m for m in HOST_CHECK.finditer(src) if m.group(1) == cid), None)
        if m:
            exprs.append(f"CHECK_EXPR:{test.name}#{cid}:" + _with_setter(" ".join(m.group(2).split()),
                                                                         src[:m.start()])[:110])
        if len(exprs) >= limit:
            break
    return exprs


def _run_level(ctx: ToolContext, level: str, coverage: bool) -> dict:
    tdir = ctx.workspace / "software" / "tests" / level
    tests = sorted(tdir.glob("test_*.c")) if tdir.is_dir() else []
    if not tests:
        return result(ctx, "BLOCKED", f"no {level} tests", issues=[f"NO_TESTS:software/tests/{level}"], tool="clang")
    srcs = [str(p) for d in SOURCE_DIRS for p in sorted((ctx.workspace / d).glob("*.c"))
            if (ctx.workspace / d).is_dir()]
    from ...workflow.ll_fake import FAKE_DIR, fake_header, internal_calls, modified
    from ...workflow.scaffold import unit_test

    fake = level == "unit" and (ctx.workspace / FAKE_DIR).is_dir()  # CAPA-038: the LL test double wins the include
    from ...brownfield.cmsis import host_flags
    from ...delivery_first import include_flags

    # feature 008 (ST pilot): a CMSIS delivery compiles on the host against the generated host device directory
    incs = (host_flags(ctx.workspace) + include_flags(ctx.workspace)
            + [f"-I{ctx.workspace / d}" for d in ([FAKE_DIR] if fake else []) + INCLUDE_DIRS
               + [f"software/tests/{level}"] if (ctx.workspace / d).is_dir()])
    if fake and modified(ctx.workspace):
        return result(ctx, "FAIL", "generated LL test double was modified", issues=[
            f"GENERATED_TEST_DOUBLE_MODIFIED:{fake_header(ctx.workspace)} (generated from the provided LL header; "
            f"restore it - write the test cases in {unit_test(ctx.workspace)} only)"], tool="clang")
    internal = [f"LL_FAKE_INTERNAL_CALL:{t.name}:{n} (internal to the generated LL bodies; preset state with "
                "ll_fake_set_state(query_fn, value), script flags with ll_fake_return_from)"
                for t in tests if fake for n in internal_calls(t.read_text(errors="replace"))]
    if internal:
        return result(ctx, "FAIL", "unit test calls LL test-double internals", issues=internal[:10], tool="clang")
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
            # the agent cannot fix what it cannot see; r76: link errors named only 'linker command failed'
            issues += _diag(b.stderr, ctx.workspace, (": error:", "undefined reference", "multiple definition"), 12)
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
            exprs = _host_check_exprs(t, r.stdout)
            issues += exprs or _diag(r.stdout + r.stderr, ctx.workspace, ("FAIL",), 12)
    # CAPA-022 (r86): UT-015/016 were used by two test functions; an id must name exactly one check (trace and
    # report cite ids), so duplicates fail the run deterministically instead of being found by the inspector
    seen: dict[str, int] = {}
    for t in tests:
        code = re.sub(r"/\*.*?\*/|//[^\n]*", "", t.read_text(errors="replace"), flags=re.S)
        for cid in re.findall(r'\bCHECK\s*\(\s*"([A-Z]+-\d+)"', code):
            seen[cid] = seen.get(cid, 0) + 1
    dups = sorted(k for k, v in seen.items() if v > 1)
    if dups:
        failed += 1
        issues += [f"DUPLICATE_TEST_ID:{d}:used by {seen[d]} checks - give each check its own id" for d in dups[:10]]
    (bdir / "results.json").write_text(json.dumps({"level": level, "passed": passed, "failed": failed}))
    op = "run_unit" if level == "unit" else "run_integration"
    record_integrity(ctx.workspace, ctx.phase, op, "PASS" if failed == 0 else "FAIL",
                     integrity(ctx.workspace, tests, asserted))
    undeclared = undeclared_test_changes(ctx.workspace, ctx.phase, op) if failed == 0 else []
    issues = undeclared + issues
    return result(ctx, "PASS" if failed == 0 and not undeclared else "FAIL",
                  f"{level}: {passed} passed, {failed} failed (HOST)"
                  + ("; undeclared test change - declare it" if undeclared else ""),
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
    from ...layer import layer_of, ll_header

    if layer_of(ctx.workspace) == "LL" and (ctx.workspace / ll_header(ctx.workspace)).is_file():  # ADR-0009
        srcs.append(str(ctx.workspace / ll_header(ctx.workspace)))
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
    summary = f"line {metrics['line_pct']}% branch {metrics['branch_pct']}% MC/DC {metrics['mcdc_pct']}% (host)"
    scope = _scope_coverage(ctx, prof, objs, srcs)
    if scope is not None:  # CAPA-060 (b006): a delivery's headers hold far more than the scope (ST: 28k lines, 1.2%)
        metrics.update(scope)
        summary = (f"scope ({scope['scope_functions']} delivered functions): functions {scope['scope_function_pct']}% "
                   f"regions {scope['scope_region_pct']}% branches {scope['scope_branch_pct']}% (host); whole delivered "
                   f"files line {metrics['line_pct']}%")
    return result(ctx, "PASS", summary, refs, [], metrics, "llvm-cov", tool_version("llvm-cov"),
                  r.exit_code, r.duration_ms + rep.duration_ms, a.model_dump(), r.stdout)


def _scope_coverage(ctx: ToolContext, prof: Path, objs: list[str], srcs: list[str]) -> dict | None:
    """CAPA-060: coverage of the delivered scope functions only (from llvm-cov's per-function export); None when the
    work order has no delivery scope."""
    from ...brownfield import DELIVERY_DIR, is_brownfield, manifest_of

    sp = ctx.workspace / DELIVERY_DIR / "scope.json"
    if not (is_brownfield(manifest_of(ctx.workspace)) and sp.is_file()):
        return None
    names = {f["name"] for f in json.loads(sp.read_text()).get("functions", [])}
    r = run_argv(["llvm-cov", "export", f"-instr-profile={prof}", *objs, *srcs], prof.parent, 120, ALLOW)
    try:
        fns = json.loads(r.stdout)["data"][0]["functions"]
    except (ValueError, KeyError, IndexError):
        return None
    best: dict[str, dict] = {}
    for f in fns:  # one entry per test binary/TU: keep the most executed instance of each scope function
        n = f["name"].split(":")[-1]
        if n in names and (n not in best or f["count"] > best[n]["count"]):
            best[n] = f
    regions = [rg for f in best.values() for rg in f.get("regions", []) if len(rg) > 7 and rg[7] == 0]
    branches = [b for f in best.values() for b in f.get("branches", [])]

    def pct(hit: int, n: int) -> float | None:
        return round(100.0 * hit / n, 2) if n else None

    return {"scope_functions": len(names), "scope_function_pct": pct(sum(f["count"] > 0 for f in best.values()), len(names)),
            "scope_region_pct": pct(sum(rg[4] > 0 for rg in regions), len(regions)),
            "scope_branch_pct": pct(sum((b[4] > 0) + (b[5] > 0) for b in branches), 2 * len(branches)),
            "scope_not_executed": sorted(names - {n for n, f in best.items() if f["count"] > 0})}


def gcov_coverage(ctx: ToolContext, a: CovIn) -> dict:
    return result(ctx, "UNSUPPORTED", "gcov path not configured for this pilot; use llvm_coverage",
                  issues=["OPTIONAL_OP_DISABLED:gcov_coverage"], tool="gcovr", version=tool_version("gcovr"))


class RobotIn(ToolInput):
    pass


def _compact_build_error(err: str) -> str:
    """'x.c:15:53: error: 'A' undeclared (first use ...); did you mean 'A_MSK'?' -> "15: 'A' undeclared; did you
    mean 'A_MSK'" so the fix fits in one capped issue line."""
    u = re.search(r"undefined reference to [`'](\w+)'", err)
    if u:  # link error: name the missing symbol (r68)
        return f"link: undefined reference to '{u.group(1)}' (not provided by the driver or forge_target_test.h)"
    m = re.search(r":(\d+):\d+: error: (.*)", err)
    if not m:
        return " ".join(err.split())[:100]
    text = re.split(r"\s+\d+ \|", m.group(2))[0]  # drop gcc's source excerpt
    hint = re.search(r"did you mean '[^']+'", text)
    text = re.sub(r"\s*\(first use[^)]*\)|;?\s*did you mean '[^']+'\??", "", text).strip()
    return f"{m.group(1)}: {text}" + (f"; {hint.group(0)}" if hint else "")


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
    builds: dict[str, str] = {}  # r67: one compact BUILD_FAIL per scenario, gcc's "did you mean" kept
    failing: list[tuple[list[str], str]] = []  # (SWR tags, failure text) of runtime failures
    for t in ET.parse(xml).getroot().iter("test"):  # noqa: S314 - output.xml written by the local robot run
        tags = [x.text or "" for x in t.findall("./tags/tag")] or [x.text or "" for x in t.findall("./tag")]
        st = t.find("status")
        status = st.get("status") if st is not None else "FAIL"
        tests.append({"name": t.get("name"), "tags": tags, "status": status})
        if status == "PASS":
            covered |= {g for g in tags if SWR.fullmatch(g)}
        else:
            full = (st.text or "").strip().replace("\n", " ") if st is not None else ""
            b = re.match(r"build failed for ([\w-]+\.c): (.*)", full)
            if b:
                builds.setdefault(b.group(1), _compact_build_error(b.group(2)))
                issues.append(f"ROBOT_FAIL:{t.get('name').split()[0]}:build failed ({b.group(1)})")
            else:
                issues.append(f"ROBOT_FAIL:{t.get('name')}:{full[:120]}")
                failing.append(([g for g in tags if SWR.fullmatch(g)], full))
    req = ctx.workspace / "workproducts/SWE.1/software_requirements.md"
    reqs = sorted(set(re.findall(r"\*\*(SWR-[A-Z0-9_.-]+)\*\*", req.read_text()))) if req.is_file() else []
    issues += [f"UNCOVERED_REQUIREMENT:{x}" for x in reqs if x not in covered]
    passed = sum(1 for t in tests if t["status"] == "PASS")
    sdir = ctx.workspace / "software/tests/software"
    from ...inspection.ears import extract
    from .robot_policy import unobserved_requirements

    texts = {r.req_id: r.text for r in extract(req.read_text(errors="replace"))} if req.is_file() else {}
    unobserved = [i for s in suites for i in unobserved_requirements(s, sdir, texts)
                  if not any(f" in {b}" in i for b in builds)]  # a scenario that does not build is fixed first
    if unobserved == [x for x in unobserved if x.startswith("HOW_TO_OBSERVE")]:
        unobserved = []
    from ...layer import profile
    from .robot_policy import DRIVER_CALL, TCHECK, required_tokens

    _pr = profile(ctx.workspace)  # feature 009: the work order's driver prefixes (RCC by default)
    if _pr["id"] != "rcc":
        DRIVER_CALL = re.compile(rf"\b(?:{re.escape(_pr['hal']['function_prefix'])}|"  # noqa: N806
                                 rf"{re.escape(_pr['ll']['function_prefix'])})\w+\s*\(")
    exprs = []  # r64: authors spent their budget reading files to learn what a failed check tested - say it here
    failed_checks = []  # ADR-0008 L11: structured copy for the route gate's safety net (test-integrity record)
    for reqs_, full in failing:
        for cid, scn in re.findall(r"check (\d+) failed in ([\w-]+\.c)", full):
            f = sdir / scn
            src = f.read_text(errors="replace") if f.is_file() else ""
            m = next((m for m in TCHECK.finditer(src) if m.group(1).strip() == cid), None)
            cond = expr = ""
            if m:
                cond = " ".join(m.group(2).split())
                expr = _with_setter(cond, src[:m.start()])
                exprs.append(f"CHECK_EXPR:{scn}#{cid}:" + expr[:100])
            named = {t for r_ in reqs_ for ts in required_tokens(texts.get(r_, ""), _pr["register_prefix"],
                                                                 _pr["ll"]["function_prefix"]) for t in ts}
            failed_checks.append({"requirements": reqs_, "scenario": scn, "check": cid, "expr": expr[:200],
                                  "observes": sorted(t for t in named if t in cond),
                                  "driver_call": bool(DRIVER_CALL.search(expr))})
    # most fundamental first (the result is capped): build errors, failed checks with their expressions, then
    # requirements the passing checks never observe, then the per-test/coverage lines
    build_issues = [f"BUILD_FAIL:{k}:{v}" for k, v in sorted(builds.items())]
    fails = [i for i in issues if i.startswith("ROBOT_FAIL:") and "build failed (" not in i]
    rest = [i for i in issues if i not in fails]
    issues = build_issues + fails + exprs + unobserved + rest
    covered -= {i.split(":")[1] for i in unobserved if i.startswith("REQUIREMENT_NOT_OBSERVED:")}
    ok = bool(tests) and passed == len(tests) and not unobserved \
        and not [i for i in issues if i.startswith("UNCOVERED")]
    scn = sorted(sdir.glob("*.c"))
    asserted = sorted({sdir / m for i in issues if i.startswith("ROBOT_FAIL:") and "build failed" not in i
                       for m in re.findall(r"\b([\w-]+\.c) \[", i)})  # failing checks, not build errors
    record_integrity(ctx.workspace, ctx.phase, "run_robot", "PASS" if ok else "FAIL",
                     {**integrity(ctx.workspace, [*suites, *scn], asserted), "failed_checks": failed_checks,
                      "build_failed": sorted(builds), "unobserved": sorted(
                          {i.split(":")[1] for i in unobserved if i.startswith("REQUIREMENT_NOT_OBSERVED:")})})
    undeclared = undeclared_test_changes(ctx.workspace, ctx.phase, "run_robot") if ok else []
    from ...afo.durable import digest
    from ...simulation_performance import selected

    performance = selected(ctx.workspace)
    contract = {"simulation_performance_contract": json.dumps({
        **performance, "budget_sha256": digest(performance),
        "scope": "DECLARED_INPUT_CONTRACT_NOT_A_MEASUREMENT"}, separators=(",", ":"))} if performance else {}
    return result(ctx, "PASS" if ok and not undeclared else "FAIL",
                  f"robot: {passed}/{len(tests)} tests passed; {len(covered & set(reqs))}/{len(reqs)} requirements "
                  "verified (Renode STM32N6 model + host measurements)"
                  + ("; undeclared test change - declare it" if undeclared else ""),
                  [ctx.store(xml.read_bytes(), "xml")], (undeclared + issues)[:30],
                  {"tests": len(tests), "passed": passed, "failed": len(tests) - passed, "requirements": len(reqs),
                   "requirements_verified": len(covered & set(reqs)), "environment": "robotframework 6.1 + renode "
                   "1.17.0 (simulated cortex-m55)", "silicon_verified": False, **contract},
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
