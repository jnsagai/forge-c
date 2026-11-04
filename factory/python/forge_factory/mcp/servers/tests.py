"""T014 — forge-tests-mcp: host unit/integration tests + LLVM source-based coverage incl. MC/DC.

Each `software/tests/<level>/test_*.c` is linked with the driver sources into its own host executable
(`-DFORGE_HOST_TEST=1`, register blocks are provided by the test via the driver's host hook), run with a
timeout, and counted PASS (exit 0) / FAIL. Coverage uses LLVM 19 `-fcoverage-mcdc`; raw .profraw and
merged .profdata are preserved by artifact ref. Host results are explicitly NOT target evidence.
Unity/CMock are not vendored on this host: tests are self-checking C programs (documented gap).
Owner decision 2026-11-03: requirement-based unit tests are GoogleTest TESTs (`software/tests/unit/test_*.cpp`, pinned
GoogleTest/GoogleMock 1.11.0, forge_factory.gtest_toolchain) against the C driver: the driver C sources stay compiled by
clang as C with the same coverage flags and are linked with the C++ test; each TEST(<unit>, UT_nnn) result of the
gtest XML is reported as a 'UT-nnn PASS|FAIL' line, the result form Matrix 4 and the report read.
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

ALLOW = {"clang", "clang++", "gcc", "llvm-profdata", "llvm-cov", "gcovr"}
GTEST_TEST = re.compile(r"^[ \t]*TEST(?:_F)?\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)", re.M)
GTEST_EXE_SUFFIX = ".gtest"
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
# Consume comments and literals before scanning code, so example text is not a
# second assertion. The CHECK alternative owns its complete first argument.
CHECK_ID_TOKEN = re.compile(
    r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
    r'\bCHECK\s*\(\s*"(?P<check_id>[^"\\\r\n]+)"\s*,', re.S)


PROGRESS_DIR = ".forge-run/tool-progress"


def progress_path(ws: Path, phase: str | None, op: str) -> Path:
    return Path(ws) / PROGRESS_DIR / f"{phase or 'none'}-{op}.json"


def write_progress(ws: Path, phase: str | None, op: str, unit: str, total: int | None, done: int, passed: int = 0,
                   failed: int = 0, running: bool = True) -> None:
    """Owner 2026-11-01: the factory floor shows how many tests a running tool has to run and how many already ran.
    Display only (the tool result stays the evidence); a write failure never affects the tool."""
    import time

    p = progress_path(ws, phase, op)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        old = json.loads(p.read_text()) if p.is_file() else {}
        started = old.get("started") if old.get("running") else time.time()
        rec = {"schema": "forge-c/tool-progress/1", "op": op, "phase": phase, "unit": unit, "total": total,
               "done": done, "passed": passed, "failed": failed, "running": running, "started": started or time.time(),
               "updated": time.time()}
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(rec))
        tmp.replace(p)
    except OSError:
        pass


def gtest_ids(paths: list[Path]) -> dict[str, int]:
    """UT id (or suite.name) -> number of TESTs declaring it across the GoogleTest files (comments ignored)."""
    seen: dict[str, int] = {}
    for p in paths:
        code = re.sub(r"/\*.*?\*/|//[^\n]*", "", p.read_text(errors="replace"), flags=re.S)
        for suite, name in GTEST_TEST.findall(code):
            k = _gtest_id(suite, name)
            seen[k] = seen.get(k, 0) + 1
    return seen


def _gtest_id(suite: str, name: str) -> str:
    return name.replace("_", "-") if re.fullmatch(r"UT_\d{3}", name) else f"{suite}.{name}"


def gtest_results(xml: Path) -> list[dict]:
    """[{id, status PASS|FAIL|SKIPPED, message}] of a --gtest_output=xml report (written by the local test run)."""
    import xml.etree.ElementTree as ET  # noqa: N817

    out = []
    try:
        root = ET.parse(xml).getroot()  # noqa: S314 - written by the sandboxed local test executable
    except (ET.ParseError, OSError):
        return out
    for tc in root.iter("testcase"):
        fail = tc.find("failure")
        skipped = tc.find("skipped") is not None or tc.get("result") == "skipped" or tc.get("status") == "notrun"
        msg = " ".join((fail.get("message") or fail.text or "").split()) if fail is not None else ""
        out.append({"id": _gtest_id(tc.get("classname") or "", tc.get("name") or ""),
                    "status": "FAIL" if fail is not None else "SKIPPED" if skipped else "PASS", "message": msg})
    return out


def check_ids(paths: list[Path]) -> dict[str, int]:
    """Count complete static assertion identities across the selected test files.

    A suffix is part of an ID: UT-001 and UT-001-RESULT are distinct, but two
    UT-001-RESULT assertions are ambiguous. This is lexical metadata validation,
    not proof that a predicate ran or that a runtime loop covers its scope.
    """
    seen: dict[str, int] = {}
    for path in paths:
        for token in CHECK_ID_TOKEN.finditer(path.read_text(errors="replace")):
            identity = token.group("check_id")
            if identity is not None:
                seen[identity] = seen.get(identity, 0) + 1
    return seen


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
    from ...workflow import unit_target_observation as observation
    from ...workflow import unit_target_timing as timing
    from ...workflow import unit_target_wwdg_timing as wwdg_timing

    tdir = ctx.workspace / "software" / "tests" / level
    tests = sorted(tdir.glob("test_*.c")) if tdir.is_dir() else []
    if level == "unit" and tdir.is_dir():  # owner 2026-11-03: GoogleTest requirement-based unit tests
        tests = sorted(tests + sorted(tdir.glob("test_*.cpp")))
    target_adapters = [(name, adapter, ctx.workspace / adapter.DECLARATION)
                       for name, adapter in (("timing", timing), ("observation", observation), ("wwdg_timing", wwdg_timing))
                       if level == "unit" and ((ctx.workspace / adapter.DECLARATION).exists()
                           or adapter is wwdg_timing and wwdg_timing.selected(ctx.workspace))]
    if not tests and not target_adapters:
        return result(ctx, "BLOCKED", f"no {level} tests", issues=[f"NO_TESTS:software/tests/{level}"], tool="clang",
                      metrics={"verification_executed": False})
    srcs = [str(p) for d in SOURCE_DIRS for p in sorted((ctx.workspace / d).glob("*.c"))
            if (ctx.workspace / d).is_dir()]
    from ...workflow.ll_fake import FAKE_DIR, fake_header, internal_calls, modified, reviewed_change
    from ...workflow.scaffold import unit_test

    fake = level == "unit" and (ctx.workspace / FAKE_DIR).is_dir()  # CAPA-038: the LL test double wins the include
    from ...brownfield.cmsis import host_flags
    from ...delivery_first import include_flags

    # feature 008 (ST pilot): a CMSIS delivery compiles on the host against the generated host device directory
    from ...layer import instance_flags

    # instance mode: the pinned device header as a system header (the test build below defines FORGE_HOST_BUILD)
    incs = (host_flags(ctx.workspace) + include_flags(ctx.workspace) + instance_flags(ctx.workspace, host=False)
            + [f"-I{ctx.workspace / d}" for d in ([FAKE_DIR] if fake else []) + INCLUDE_DIRS
               + [f"software/tests/{level}"] if (ctx.workspace / d).is_dir()])
    from ...workflow import ll_call_arguments
    from ...workflow.provided_ll_unit import selected as real_ll_selected

    try:
        if fake and modified(ctx.workspace):
            return result(ctx, "FAIL", "generated LL test double was modified", issues=[
                f"GENERATED_TEST_DOUBLE_MODIFIED:{fake_header(ctx.workspace)} (generated from the provided LL header; "
                f"restore it - write the test cases in {unit_test(ctx.workspace)} only)"], tool="clang")
        effective_change = fake and reviewed_change(ctx.workspace) is not None
        real_ll_tests, argument_history_tests = set(), set()
        for t in tests if level == "unit" else []:
            if ll_call_arguments.selected(ctx.workspace, t):
                argument_history_tests.add(t)
            elif real_ll_selected(ctx.workspace, t):
                real_ll_tests.add(t)
    except ValueError as exc:
        return result(ctx, "FAIL", "invalid provided LL unit backend", issues=[str(exc)], tool="clang",
                      metrics={"verification_executed": False})
    effective_fake_tests = {t for t in tests if effective_change and t not in real_ll_tests
                            and t not in argument_history_tests}
    internal = [f"LL_FAKE_INTERNAL_CALL:{t.name}:{n} (internal to the generated LL bodies; preset state with "
                "ll_fake_set_state(query_fn, value), script flags with ll_fake_return_from)"
                for t in tests if fake and t not in real_ll_tests for n in internal_calls(t.read_text(errors="replace"))]
    if internal:
        return result(ctx, "FAIL", "unit test calls LL test-double internals", issues=internal[:10], tool="clang")
    bdir = ctx.workspace / "build" / f"tests-{level}"
    if bdir.exists():
        shutil.rmtree(bdir)
    bdir.mkdir(parents=True)
    log, passed, failed, issues, ms = b"", 0, 0, [], 0.0
    asserted: list[Path] = []  # runtime (not build) failures - ADR-0008 test-integrity record
    pop = "run_unit" if level == "unit" else "run_integration"
    per_file = {t: (len(gtest_ids([t])) if t.suffix == ".cpp" else len(check_ids([t]))) or 1
                for t in tests}  # tests = check ids / gtest TESTs (one executable may hold many)
    target_total = 0
    for name, adapter, _declaration in target_adapters:
        try:
            target_total += (len(adapter.expected_tests(ctx.workspace)) if name in ("observation", "wwdg_timing")
                             else len(adapter.declaration(ctx.workspace)["cases"]))
        except (OSError, ValueError, KeyError, TypeError):
            pass  # run() reports the precise refusal; invalid declarations never supply progress or results.
    total = sum(per_file.values()) + target_total
    gt = None
    if any(t.suffix == ".cpp" for t in tests):
        from ...gtest_toolchain import GtestToolchainError, load

        try:
            gt = load()
        except GtestToolchainError as exc:
            return result(ctx, "BLOCKED", "pinned GoogleTest toolchain unavailable", issues=[str(exc)[:200]],
                          tool="clang++", metrics={"verification_executed": False})
    n_done = n_pass = n_fail = 0
    write_progress(ctx.workspace, ctx.phase, pop, "tests", total, 0)
    for t in tests:
        exe = bdir / t.stem
        real_ll = t in real_ll_tests
        if real_ll_tests or argument_history_tests or effective_fake_tests:
            backend = ("provided-ll-ram-v1" if real_ll else
                       "ll-call-arguments-v1" if t in argument_history_tests else
                       "reviewed-ll-fake-v1" if t in effective_fake_tests else "default")
            log += f"# unit_backend {t.name} {backend}\n".encode()
        test_incs = [i for i in incs if i != f"-I{ctx.workspace / FAKE_DIR}"] if real_ll else incs
        if t in effective_fake_tests:
            from ...workflow.ll_effective_fake import generate

            private = generate(ctx.workspace, bdir / (t.stem + ".ll-effective-fake"))
            test_incs = [f"-I{private}", *test_incs]
        if t.suffix == ".cpp":
            exe = bdir / (t.stem + GTEST_EXE_SUFFIX)
            b, blog = _build_gtest(ctx, t, exe, bdir, test_incs, srcs, coverage, fake and not real_ll, gt,
                                   real_ll=real_ll, argument_history=t in argument_history_tests)
        else:
            argv = ["clang", "-std=c11", "-O0", "-g", "-Wall", "-Wextra", "-DFORGE_HOST_TEST=1", "-DFORGE_HOST_BUILD=1",
                    *(COV_FLAGS if coverage else []), *test_incs, str(t), *srcs, "-o", str(exe)]
            b = run_argv(argv, bdir, 180, ALLOW)
            blog = b"$ " + " ".join(argv).encode() + b"\n" + b.stdout + b.stderr
        log += blog
        if b.exit_code != 0:
            n_done, n_fail = n_done + per_file[t], n_fail + per_file[t]
            write_progress(ctx.workspace, ctx.phase, pop, "tests", total, n_done, n_pass, n_fail)
            failed += 1
            issues.append(f"BUILD_FAIL:{t.name}")
            # the agent cannot fix what it cannot see; r76: link errors named only 'linker command failed'
            issues += _diag(b.stderr, ctx.workspace, (": error:", ": fatal error:", "undefined reference",  # CAPA-132
                                                      "multiple definition"), 12)
            continue
        gx = bdir / f"{exe.name}.xml"
        r = run_argv([str(exe), *([f"--gtest_output=xml:{gx}"] if t.suffix == ".cpp" else [])], bdir, 60,
                     ALLOW | {exe.name},
                     env_extra={"LLVM_PROFILE_FILE": str(bdir / f"{exe.name}.profraw")} if coverage else None)
        ms += r.duration_ms
        log += f"$ {exe.name} -> exit {r.exit_code}\n".encode() + r.stdout + r.stderr  # full raw output kept by ref
        gres = gtest_results(gx) if t.suffix == ".cpp" else []
        if t.suffix == ".cpp":  # one 'UT-nnn PASS|FAIL' line per TEST (the result form Matrix 4 and reports read)
            log += b"# gtest results\n" + "".join(f"{g['id']} {'PASS' if g['status'] == 'PASS' else 'FAIL'}\n"
                                                    for g in gres).encode()
            if r.exit_code == 0 and (not gres or any(g["status"] != "PASS" for g in gres)):
                import dataclasses

                r = dataclasses.replace(r, exit_code=1)  # a skipped or missing TEST never passes
        n_done += per_file[t]
        n_pass, n_fail = (n_pass + per_file[t], n_fail) if r.exit_code == 0 else (n_pass, n_fail + per_file[t])
        write_progress(ctx.workspace, ctx.phase, pop, "tests", total, n_done, n_pass, n_fail)
        if r.exit_code == 0:
            passed += 1
        else:
            failed += 1
            asserted.append(t)
            issues.append(f"TEST_FAIL:{t.name}:exit{r.exit_code}" + (":TIMEOUT" if r.timed_out else ""))
            if t.suffix == ".cpp":
                issues += [f"GTEST_FAIL:{t.name}#{g['id']}:" + (g["message"] or g["status"])[:200]
                           for g in gres if g["status"] != "PASS"][:12] or ["GTEST_NO_RESULTS (no TEST ran)"]
                continue
            exprs = _host_check_exprs(t, r.stdout)
            issues += exprs or _diag(r.stdout + r.stderr, ctx.workspace, ("FAIL",), 12)
    target_metrics, target_refs, target_tests, target_summaries = {}, [], [], []
    integrity_files = list(tests)
    for name, adapter, declaration in target_adapters:
        fragment = adapter.run(ctx)
        if fragment is None:
            failed += 1
            issues.append(f"TARGET_DECLARATION_CHANGED_DURING_EXECUTION:{declaration.name}")
            continue
        if declaration.is_file():
            integrity_files.append(declaration)
        measured = fragment["tests"]
        target_tests += measured
        successes = sum(t["status"] == "PASS" for t in measured)
        failures = sum(t["status"] != "PASS" for t in measured)
        target_metrics.update({**fragment["metrics"], f"{name}_environment": fragment["environment"],
                               f"{name}_ut_passed": successes, f"{name}_ut_failed": failures,
                               "silicon_verified": False})
        target_refs += fragment["artifact_refs"]
        target_summaries.append(f"; Renode {name} UT: {successes} passed, {failures} failed")
        n_done += len(measured)
        n_pass += successes
        n_fail += failures
        log += f"# typed target-simulation {name} results\n".encode() + fragment["raw_log"]
        issues += fragment["issues"]
        if failures:
            asserted.append(declaration)
        if fragment["status"] != "PASS":
            failed += 1
    # CAPA-022 (r86): UT-015/016 were used by two test functions; an id must name exactly one check (trace and
    # report cite ids), so duplicates fail the run deterministically instead of being found by the inspector
    seen = check_ids([t for t in tests if t.suffix == ".c"])
    for k, v in gtest_ids([t for t in tests if t.suffix == ".cpp"]).items():
        seen[k] = seen.get(k, 0) + v
    for test in target_tests:
        seen[test["id"]] = seen.get(test["id"], 0) + 1
    dups = sorted(k for k, v in seen.items() if v > 1)
    if dups:
        failed += 1
        issues += [f"DUPLICATE_TEST_ID:{d}:used by {seen[d]} checks - give each check its own id; preserve predicates "
                   "and order, use a unique suffix, do not combine checks" for d in dups[:10]]
    (bdir / "results.json").write_text(json.dumps({"level": level, "passed": passed, "failed": failed,
        **({"backends": {t.name: "provided-ll-ram-v1" if t in real_ll_tests else
                        "ll-call-arguments-v1" if t in argument_history_tests else
                        "reviewed-ll-fake-v1" if t in effective_fake_tests else "default" for t in tests}}
           if real_ll_tests or argument_history_tests or effective_fake_tests else {})}))
    write_progress(ctx.workspace, ctx.phase, pop, "tests", total, n_done, n_pass, n_fail, running=False)
    op = "run_unit" if level == "unit" else "run_integration"
    record_integrity(ctx.workspace, ctx.phase, op, "PASS" if failed == 0 else "FAIL",
                     integrity(ctx.workspace, integrity_files, asserted))
    undeclared = undeclared_test_changes(ctx.workspace, ctx.phase, op) if failed == 0 else []
    issues = undeclared + issues
    argument_refs = [ctx.store(path.read_bytes(), "json") for t in sorted(argument_history_tests)
                     if (path := bdir / (t.stem + ".ll-call-arguments") / "binding.json").is_file()]
    effective_refs = [ctx.store(path.read_bytes(), "json") for t in sorted(effective_fake_tests)
                      if (path := bdir / (t.stem + ".ll-effective-fake") / "binding.json").is_file()]
    return result(ctx, "PASS" if failed == 0 and not undeclared else "FAIL",
                  f"{level}: {passed} passed, {failed} failed (HOST)"
                  + "".join(target_summaries)
                  + ("; undeclared test change - declare it" if undeclared else ""),
                  [ctx.store(log), *target_refs, *argument_refs, *effective_refs], issues,
                  {"passed": passed, "failed": failed, "executables": len(tests),
                                             "environment": "host", "target_evidence": False, **target_metrics},
                  "clang+self-checking tests", tool_version("clang"), 0 if failed == 0 else 1, ms, None, log)


def _generated_ll_unit(p: Path) -> bool:
    try:
        head = p.read_text(errors="replace")[:400]
    except OSError:
        return False
    return "Compile unit GENERATED by forge_factory (ADR-0009)" in head and "contains no driver logic" in head


def _build_gtest(ctx: ToolContext, t: Path, exe: Path, bdir: Path, incs: list[str], srcs: list[str], coverage: bool,
                 fake: bool, gt: dict, *, real_ll: bool = False, argument_history: bool = False):
    """The driver C sources compiled as C (same flags as the C harness), the GoogleTest file as C++17, linked with the
    pinned gtest/gmock. With the generated LL test double (CAPA-038) its state is defined once in a generated C unit."""
    cov = COV_FLAGS if coverage else []
    log, objs = b"", []
    if argument_history:
        from ...workflow.ll_call_arguments import generate

        private = generate(ctx.workspace, bdir / (t.stem + ".ll-call-arguments"))
        incs = [f"-I{private}", *incs]
    # the GENERATED compile unit of a header-only LL (ADR-0009: it only includes the header, no driver logic) is not
    # linked: the test unit includes the header itself, and the unit's unused static inline copies made llvm-cov count
    # a header line as missed (L6 IWDG: 48/49 lines with every region covered) - like the mutation campaign skips it
    c_units = [x for x in srcs if not _generated_ll_unit(Path(x))]
    from ...brownfield.cmsis_gtest import generate as cmsis_gtest

    if real_ll:
        from ...workflow.provided_ll_unit import generate

        abi = generate(ctx.workspace, bdir / t.stem)
    else:
        abi = cmsis_gtest(ctx.workspace, bdir)
    if abi:
        c_units.append(str(abi[1]))
    if fake:
        from ...workflow.ll_fake import fake_header

        impl = bdir / "forge_ll_fake_impl.c"
        impl.write_text("/* GENERATED by forge-tests-mcp: defines the LL test double state once (CAPA-038). */\n"
                        f"#define LL_FAKE_IMPLEMENTATION\n#include \"{Path(fake_header(ctx.workspace)).name}\"\n")
        c_units.append(str(impl))
    for i, src in enumerate(c_units):
        o = bdir / f"{t.stem}.c{i}.o"
        argv = ["clang", "-std=c11", "-O0", "-g", "-Wall", "-Wextra", "-DFORGE_HOST_TEST=1", "-DFORGE_HOST_BUILD=1",
                *cov, *incs, "-c", src, "-o", str(o)]
        b = run_argv(argv, bdir, 180, ALLOW)
        log += b"$ " + " ".join(argv).encode() + b"\n" + b.stdout + b.stderr
        if b.exit_code != 0:
            return b, log
        objs.append(str(o))
    o = bdir / f"{t.stem}.cpp.o"
    argv = ["clang++", "-std=c++17", "-O0", "-g", "-Wall", "-Wextra", "-DFORGE_HOST_TEST=1", "-DFORGE_HOST_BUILD=1",
            *gt["cxx_flags"], *cov, *(["-I", str(abi[0])] if abi else []), *incs,
            "-isystem", gt["include"], "-c", str(t), "-o", str(o)]
    b = run_argv(argv, bdir, 240, ALLOW, mem_mb=4096)
    log += b"$ " + " ".join(argv).encode() + b"\n" + b.stdout + b.stderr
    if b.exit_code != 0:
        return b, log
    main = str(Path(gt["gtest"]).with_name("libgtest_main.a"))
    argv = ["clang++", *gt["cxx_flags"], *cov, str(o), *objs, gt["gmock"], gt["gtest"], main, "-lpthread",
            "-o", str(exe)]
    b = run_argv(argv, bdir, 180, ALLOW, mem_mb=4096)
    log += b"$ " + " ".join(argv).encode() + b"\n" + b.stdout + b.stderr
    return b, log


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
    exes = [p for p in sorted(bdir.glob("test_*")) if p.is_file() and p.suffix in ("", GTEST_EXE_SUFFIX)] \
        if bdir.is_dir() else []
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
    gaps = coverage_gaps(ctx.workspace, prof, objs, srcs, bdir,
                         scope_functions=set(scope.get("scope_names") or []) if scope else None)
    if scope is not None:
        scope.pop("scope_names", None)
    if gaps is not None:  # owner 2026-11-03 (D): each uncovered line/branch/condition, for the closure tasks
        # the full list is a content-addressed artifact (metrics are scalar); first in the metrics, so the result-size
        # bound (sdk.result drops the metrics tail) never removes them
        refs.append(ctx.store(json.dumps({"schema": "forge-c/coverage-gaps/1", "gaps": gaps}, indent=1).encode(),
                              "json"))
        metrics = {"uncovered_count": len(gaps), "uncovered_artifact": refs[-1], **metrics}
    if scope is not None:  # CAPA-060 (b006): a delivery's headers hold far more than the scope (ST: 28k lines, 1.2%)
        metrics.update(scope)
        summary = (f"scope ({scope['scope_functions']} delivered functions): functions {scope['scope_function_pct']}% "
                   f"regions {scope['scope_region_pct']}% branches {scope['scope_branch_pct']}% (host); whole delivered "
                   f"files line {metrics['line_pct']}%")
    issues = [f"COVERAGE_GAP:{g['kind']}:{g['file']}:{g['line']}:{g['function'] or '-'}:{g['missing']}:"
              f"{g['text'][:60]}" for g in (gaps or [])][:12]
    return result(ctx, "PASS", summary + (f"; {len(gaps)} uncovered item(s)" if gaps else ""), refs, issues, metrics,
                  "llvm-cov", tool_version("llvm-cov"), r.exit_code, r.duration_ms + rep.duration_ms, a.model_dump(),
                  r.stdout)


def coverage_gaps(ws: Path, prof: Path, objs: list[str], srcs: list[str], bdir: Path,
                  scope_functions: set[str] | None = None) -> list[dict] | None:
    """Owner 2026-11-03 (D): every uncovered line, branch outcome and MC/DC condition of the measured driver sources,
    with its location, the enclosing function, the decision text and what is missing. Instances of one region in
    several binaries/units (a header-only LL is compiled in its C unit and in the test) are merged: a branch outcome
    or condition counts as covered when any instance covers it. None when llvm-cov output is unreadable."""
    from ...common import sha256_bytes
    from ...gtest_toolchain import c_name

    j = run_argv(["llvm-cov", "export", f"-instr-profile={prof}", *objs, *srcs], bdir, 120, ALLOW)
    lc = run_argv(["llvm-cov", "export", "-format=lcov", f"-instr-profile={prof}", *objs, *srcs], bdir, 120, ALLOW)
    try:
        data = json.loads(j.stdout)["data"][0]
    except (ValueError, KeyError, IndexError):
        return None
    root = Path(ws).resolve()

    def rel(f: str) -> str:
        try:
            return Path(f).resolve().relative_to(root).as_posix()
        except ValueError:
            return Path(f).name

    spans: dict[str, list[tuple[int, int, str]]] = {}
    for fn in data.get("functions", []):
        regs, files = fn.get("regions") or [], fn.get("filenames") or []
        if regs and files:
            r0 = regs[0]
            spans.setdefault(rel(files[r0[5]] if len(r0) > 5 and r0[5] < len(files) else files[0]), []).append(
                (r0[0], r0[2], c_name(fn["name"])))

    def func(f: str, line: int) -> str | None:
        hit = [(b - a, n) for a, b, n in spans.get(f, []) if a <= line <= b]
        return min(hit)[1] if hit else None

    texts: dict[str, list[str]] = {}

    def snippet(f: str, l1: int, c1: int, l2: int, c2: int) -> str:
        if f not in texts:
            p = root / f
            texts[f] = p.read_text(errors="replace").splitlines() if p.is_file() else []
        ls = texts[f][l1 - 1:l2]
        if not ls:
            return ""
        if len(ls) == 1:
            return ls[0][c1 - 1:c2 - 1].strip()
        return " ".join([ls[0][c1 - 1:].strip(), *[x.strip() for x in ls[1:-1]], ls[-1][:c2 - 1].strip()])

    gaps = []
    branches: dict[tuple, list[int]] = {}
    mcdc: dict[tuple, list[bool]] = {}
    for fobj in data.get("files", []):
        f = rel(fobj["filename"])
        for b in fobj.get("branches", []):
            k = (f, b[0], b[1], b[2], b[3])
            t = branches.setdefault(k, [0, 0])
            t[0], t[1] = t[0] + int(b[4]), t[1] + int(b[5])
        for m in fobj.get("mcdc_records", []):
            conds = next((x for x in m if isinstance(x, list)), [])
            k = (f, m[0], m[1], m[2], m[3])
            old = mcdc.setdefault(k, [False] * len(conds))
            mcdc[k] = [a or bool(b) for a, b in zip(old, conds, strict=False)] if old else list(map(bool, conds))
    for (f, l1, c1, l2, c2), (t, fa) in sorted(branches.items()):
        if t and fa:
            continue
        missing = "never evaluated" if not (t or fa) else "true outcome never taken" if not t else \
            "false outcome never taken"
        gaps.append({"kind": "branch", "file": f, "line": l1, "col": c1, "function": func(f, l1),
                     "text": snippet(f, l1, c1, l2, c2), "missing": missing})
    for (f, l1, c1, l2, c2), conds in sorted(mcdc.items()):
        miss = [i + 1 for i, ok in enumerate(conds) if not ok]
        if miss:
            gaps.append({"kind": "mcdc", "file": f, "line": l1, "col": c1, "function": func(f, l1),
                         "text": snippet(f, l1, c1, l2, c2),
                         "missing": f"independent effect of condition(s) {', '.join(map(str, miss))} of "
                                    f"{len(conds)} not shown"})
    cur = None
    for ln in lc.stdout.decode(errors="replace").splitlines():
        if ln.startswith("SF:"):
            cur = rel(ln[3:])
        elif ln.startswith("DA:") and cur is not None:
            n, c = ln[3:].split(",")[:2]
            if c.strip() == "0":
                line = int(n)
                gaps.append({"kind": "line", "file": cur, "line": line, "col": 1, "function": func(cur, line),
                             "text": snippet(cur, line, 1, line, 10**6), "missing": "line never executed"})
    if scope_functions is not None:
        gaps = [g for g in gaps if g["function"] in scope_functions]
    for g in gaps:
        g["id"] = "GAP-" + sha256_bytes(f"{g['kind']}|{g['file']}|{g['line']}|{g['col']}|{g['missing']}".encode())[:10]
        g["text"] = g["text"][:160]
    return gaps


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
    from ...gtest_toolchain import c_name

    for f in fns:  # one entry per test binary/TU: keep the most executed instance of each scope function
        n = c_name(f["name"])  # a static inline function of a GoogleTest (C++) unit is mangled
        if n in names and (n not in best or f["count"] > best[n]["count"]):
            best[n] = f
    regions = [rg for f in best.values() for rg in f.get("regions", []) if len(rg) > 7 and rg[7] == 0]
    branches = [b for f in best.values() for b in f.get("branches", [])]

    def pct(hit: int, n: int) -> float | None:
        return round(100.0 * hit / n, 2) if n else None

    return {"scope_functions": len(names), "scope_function_pct": pct(sum(f["count"] > 0 for f in best.values()), len(names)),
            "scope_region_pct": pct(sum(rg[4] > 0 for rg in regions), len(regions)),
            "scope_branch_pct": pct(sum((b[4] > 0) + (b[5] > 0) for b in branches), 2 * len(branches)),
            "scope_not_executed": sorted(names - {n for n, f in best.items() if f["count"] > 0}),
            "scope_names": sorted(names)}


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
                      tool="robotframework", metrics={"verification_executed": False})
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
    prog = progress_path(ctx.workspace, ctx.phase, "run_robot")
    write_progress(ctx.workspace, ctx.phase, "run_robot", "tests", None, 0)  # the listener writes the suite's total
    r = run_argv([py, "-I", "-m", "robot", "--pythonpath", str(REPO_ROOT / "factory/sim/stm32n6"), "--pythonpath",
                  str(REPO_ROOT / "factory/python"), "--outputdir", str(out), "--consolecolors", "off",
                  "--listener", f"forge_robot_progress.Progress:{prog}",
                  "--console", "dotted", *[str(s) for s in suites]], ctx.workspace, 570, {os.path.basename(py)},
                 env_extra=env, mem_mb=65536, fsize_mb=512)
    xml = out / "output.xml"
    if not xml.is_file():
        write_progress(ctx.workspace, ctx.phase, "run_robot", "tests", None, 0, running=False)
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
    npass = sum(1 for x in tests if x["status"] == "PASS")
    write_progress(ctx.workspace, ctx.phase, "run_robot", "tests", len(tests), len(tests), npass, len(tests) - npass,
                   running=False)
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
    Operation("run_unit", RunIn, run_unit, "Build+run software/tests/unit/test_*.c (self-checking C) and "
              "test_*.cpp (GoogleTest) on host (coverage optional)."),
    Operation("run_integration", RunIn, run_integration, "Build+run integration (or software-level) host tests."),
    Operation("run_robot", RobotIn, run_robot,
              "SWE.6: run Robot Framework requirement tests (software/tests/software/*.robot) on the Renode model."),
    Operation("llvm_coverage", CovIn, llvm_coverage, "LLVM line/branch/MC/DC coverage summary; raw data by ref."),
    Operation("gcov_coverage", CovIn, gcov_coverage, "gcov/gcovr coverage (disabled in this pilot)."),
]

if __name__ == "__main__":
    build_server("forge-tests-mcp", OPERATIONS).run("stdio")
