"""Code-stage gates: build, static-analysis (sw-design) and unit-test, coverage (unit-verif).

Conventions (stated in the hi-sw-design and hi-unit-verif skills):

- sources `src/**/*.c`, headers `include/`, no `main()` in `src/`;
- unit tests `tests/**/test_*.c`, each a program with `main()`, compiled with every source file, printing one line per
  test case: `HI-TEST <UTC-id> PASS` or `HI-TEST <UTC-id> FAIL <reason>`;
- the compiler is `$CC` or `gcc`, with `-std=c11 -Wall -Wextra -Werror -pedantic`; static analysis is cppcheck;
  coverage is gcov through gcovr.

A missing tool gives NOT_RUN with the reason. Coverage is compared with the profile's targets for the level; an MC/DC
target cannot be measured by these tools and is NOT_RUN when the level requires it.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import __version__, gate_result
from .config import effective_rigor, load_project, stages
from .io import read_json, sha256_file, write_json
from .provenance import utc_now

CFLAGS = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic"]
HI_TEST = re.compile(r"^HI-TEST[ \t]+(\S+)[ \t]+(PASS|FAIL)\b[ \t]*([^\n]*)$", re.M)
RESULTS = Path("hi") / "unit-verif" / "results.json"
RUN_TIMEOUT = 120


def _common(root: Path) -> tuple[dict, dict]:
    rigor = effective_rigor(load_project(root))
    return rigor, {"profile": rigor["profile"], "integrity_level": rigor["level"], "root": Path(root)}


def cc() -> str | None:
    return shutil.which(os.environ.get("CC", "gcc"))


def sources(root: Path) -> list[Path]:
    return sorted(p for p in (Path(root) / "src").rglob("*.c")) if (Path(root) / "src").is_dir() else []


def test_programs(root: Path) -> list[Path]:
    return sorted((Path(root) / "tests").rglob("test_*.c")) if (Path(root) / "tests").is_dir() else []


def _tool(name: str) -> dict:
    return {"name": f"forge-c-hi {name}", "version": __version__}


def _run(cmd: list[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def build(root: Path, *, write: bool = True) -> dict:
    root = Path(root)
    _, common = _common(root)
    srcs = sources(root)
    compiler = cc()
    if compiler is None:
        res = gate_result.result("build", [], not_run_reason="no C compiler ($CC or gcc) found", **common)
    elif not srcs:
        res = gate_result.result("build", [gate_result.issue("BUILD-NO-SOURCES", "no src/**/*.c files")], **common)
    else:
        issues = []
        with tempfile.TemporaryDirectory() as tmp:
            for n, src in enumerate(srcs):
                r = _run([compiler, *CFLAGS, "-Iinclude", "-c", str(src.relative_to(root)), "-o",
                          str(Path(tmp) / f"{n}.o")], root)
                if r.returncode != 0:
                    first = next((l for l in r.stderr.splitlines() if "error" in l), r.stderr.strip()[:200])
                    issues.append(gate_result.issue("BUILD-ERROR", first[:280], src.relative_to(root).as_posix()))
            mains = [s for s in srcs if re.search(r"\bint\s+main\s*\(", s.read_text(errors="replace"))]
            issues += [gate_result.issue("BUILD-MAIN-IN-SRC", "src/ must not define main(); tests provide it",
                                         s.relative_to(root).as_posix()) for s in mains]
        res = gate_result.result("build", issues, evidence=srcs, tool=_tool(f"build ({Path(compiler).name})"), **common)
    if write:
        gate_result.write(root, "sw-design", res)
    return res


def static_analysis(root: Path, *, write: bool = True) -> dict:
    root = Path(root)
    _, common = _common(root)
    tool = shutil.which("cppcheck")
    if tool is None:
        res = gate_result.result("static-analysis", [], not_run_reason="cppcheck is not installed", **common)
    elif not sources(root):
        res = gate_result.result("static-analysis", [gate_result.issue("SA-NO-SOURCES", "no src/**/*.c files")], **common)
    else:
        r = _run([tool, "--enable=warning,style,performance,portability", "--std=c11", "--inline-suppr",
                  "--suppress=missingIncludeSystem", "--error-exitcode=1", "--quiet",
                  "--template={file}:{line}: {severity} {id}: {message}", "-Iinclude", "src"], root)
        issues = [gate_result.issue("SA-" + (m.group(3) or "finding"), m.group(0)[:280], m.group(1))
                  for m in re.finditer(r"^(\S+?):(\d+): \w+ (\w+): .*$", r.stderr, re.M)]
        if r.returncode != 0 and not issues:
            issues.append(gate_result.issue("SA-ERROR", r.stderr.strip()[:280] or f"cppcheck exit {r.returncode}"))
        res = gate_result.result("static-analysis", issues, evidence=sources(root), tool=_tool("static-analysis (cppcheck)"),
                                 exit_code=r.returncode, **common)
    if write:
        gate_result.write(root, "sw-design", res)
    return res


def _spec_cases(root: Path) -> list[dict]:
    p = Path(root) / stages()["unit-verif"]["outputs"][0]
    if not p.is_file():
        return []
    return [i for i in read_json(p).get("items", []) if (i.get("automation") or {}).get("kind") == "host-unit"]


def run_unit_tests(root: Path, *, coverage: bool, programs: list[Path] | None = None,
                   include: list[str] | None = None) -> tuple[dict[str, dict], list[dict], Path | None]:
    """Compile and run every test program. Returns per-case results, issues, and the build dir (coverage)."""
    root = Path(root)
    compiler = cc()
    out: dict[str, dict] = {}
    issues: list[dict] = []
    bdir = Path(tempfile.mkdtemp(prefix="hi-unit-"))
    extra = ["--coverage", "-O0", "-g"] if coverage else []
    for t in (test_programs(root) if programs is None else programs):
        exe = bdir / t.stem
        rel = t.relative_to(root).as_posix()
        r = _run([compiler, *CFLAGS, *extra, "-Iinclude", "-Itests",
                  *[f"-I{i}" for i in include or []], rel,
                  *[s.relative_to(root).as_posix() for s in sources(root)], "-o", str(exe)], root)
        if r.returncode != 0:
            issues.append(gate_result.issue("UT-BUILD", f"{rel}: {r.stderr.strip()[:240]}", rel))
            continue
        try:
            run = subprocess.run([str(exe)], cwd=root, capture_output=True, text=True, timeout=RUN_TIMEOUT)
        except subprocess.TimeoutExpired:
            issues.append(gate_result.issue("UT-TIMEOUT", f"{rel} did not finish in {RUN_TIMEOUT} s", rel))
            continue
        cases = HI_TEST.findall(run.stdout)
        for cid, verdict, why in cases:
            out[cid] = {"test_id": cid, "verdict": verdict, "message": (why or rel)[:300],
                        "evidence": [{"path": rel, "sha256": sha256_file(t)}]}
        if run.returncode != 0 and not any(v == "FAIL" for _, v, _ in cases):
            issues.append(gate_result.issue("UT-EXIT", f"{rel} exited {run.returncode} without a FAIL line", rel))
    return out, issues, bdir


def unit_test(root: Path, *, write: bool = True, coverage: bool = False) -> tuple[dict, Path | None]:
    root = Path(root)
    _, common = _common(root)
    spec = _spec_cases(root)
    if cc() is None:
        res = gate_result.result("unit-test", [], not_run_reason="no C compiler ($CC or gcc) found", **common)
        if write:
            gate_result.write(root, "unit-verif", res)
        return res, None
    if not test_programs(root):
        res = gate_result.result("unit-test", [gate_result.issue("UT-NO-TESTS", "no tests/**/test_*.c programs")], **common)
        if write:
            gate_result.write(root, "unit-verif", res)
        return res, None
    results, issues, bdir = run_unit_tests(root, coverage=coverage)
    for cid, r in sorted(results.items()):
        if r["verdict"] == "FAIL":
            issues.append(gate_result.issue("UT-FAIL", f"{cid}: {r['message']}", cid))
    for case in spec:
        if case["id"] not in results:
            results[case["id"]] = {"test_id": case["id"], "verdict": "NOT_RUN",
                                   "message": "no HI-TEST line was printed for this case"}
            issues.append(gate_result.issue("UT-NOT-RUN", f"{case['id']} printed no result", case["id"]))
    unknown = sorted(set(results) - {c["id"] for c in spec})
    issues += [gate_result.issue("UT-UNSPECIFIED", f"{u} is not a host-unit case in the test specification", u)
               for u in unknown]
    vr = {"schema": "forge-c-hi/verification-result@1", "stage": "unit-verif", "tool": _tool("unit-test"),
          "results": [results[k] for k in sorted(results)], "created_utc": utc_now()}
    write_json(root / RESULTS, vr)
    res = gate_result.result("unit-test", issues, evidence=[root / RESULTS] + test_programs(root),
                             tool=_tool(f"unit-test ({Path(cc()).name})"), **common)
    if write:
        gate_result.write(root, "unit-verif", res)
    if not coverage:
        shutil.rmtree(bdir, ignore_errors=True)
        bdir = None
    return res, bdir


def coverage(root: Path, *, write: bool = True) -> dict:
    root = Path(root)
    rigor, common = _common(root)
    targets = rigor.get("coverage") or {}
    gcovr = shutil.which("gcovr")
    if not any(v is not None for v in targets.values()):
        res = gate_result.result("coverage", [], not_run_reason="no coverage target at this level", **common)
    elif gcovr is None or cc() is None:
        res = gate_result.result("coverage", [], not_run_reason="gcovr or the C compiler is not installed", **common)
    else:
        ut, bdir = unit_test(root, write=False, coverage=True)
        if bdir is None:
            res = gate_result.result("coverage", [gate_result.issue("COV-NO-TESTS", "no unit tests to measure")], **common)
        else:
            r = _run([gcovr, "--root", str(root), "--filter", str(root / "src"), "--object-directory", str(bdir),
                      "--json-summary", "-", str(bdir)], root)
            shutil.rmtree(bdir, ignore_errors=True)
            try:
                summ = json.loads(r.stdout)
            except ValueError:
                res = gate_result.result("coverage", [gate_result.issue("COV-TOOL", r.stderr.strip()[:280])], **common)
            else:
                measured = {"statement": summ.get("line_percent"), "branch": summ.get("branch_percent")}
                issues = []
                for kind in ("statement", "branch"):
                    want = targets.get(kind)
                    if want is not None and (measured[kind] is None or measured[kind] + 1e-9 < want):
                        issues.append(gate_result.issue(
                            f"COV-{kind.upper()}", f"{kind} coverage {measured[kind]}% is below the target {want}%"))
                cov_file = write_json(root / "hi" / "unit-verif" / "coverage.json",
                                      {"schema": "forge-c-hi/coverage@1", "measured": measured, "targets": targets,
                                       "tool": "gcovr", "created_utc": utc_now()})
                if targets.get("mcdc") is not None and not issues:
                    res = gate_result.result("coverage", [], not_run_reason=(
                        f"MC/DC {targets['mcdc']}% is required at this level and gcov/gcovr cannot measure it"), **common)
                    res["evidence"] = [{"path": cov_file.relative_to(root).as_posix(), "sha256": sha256_file(cov_file)}]
                else:
                    res = gate_result.result("coverage", issues, evidence=[cov_file], tool=_tool("coverage (gcovr)"),
                                             **common)
    if write:
        gate_result.write(root, "unit-verif", res)
    return res


def verification(root: Path, stage: str, *, write: bool = True) -> dict:
    """The `verification` gate of sw-integ, sw-qual, sys-integ and sys-qual (T068): the host programs
    ``hi/<stage>/host/test_*.c`` are compiled with the real sources and run. A simulator or manual case has no runner
    in this package: it is NOT_RUN, so the gate is NOT_RUN at best and the package cannot be sealed READY on tests that
    were only specified."""
    root = Path(root)
    _, common = _common(root)
    spec_file = root / stages()[stage]["outputs"][0]
    if cc() is None or not spec_file.is_file():
        res = gate_result.result("verification", [], not_run_reason=(
            "no C compiler ($CC or gcc) found" if cc() is None else f"{spec_file.name} does not exist"), **common)
        if write:
            gate_result.write(root, stage, res)
        return res
    cases = [i for i in read_json(spec_file).get("items", []) if isinstance(i, dict)]
    host = {c["id"] for c in cases if (c.get("automation") or {}).get("kind") == "host-unit"}
    hdir = root / "hi" / stage / "host"
    results, issues, bdir = run_unit_tests(root, coverage=False, programs=sorted(hdir.glob("test_*.c")),
                                           include=[f"hi/{stage}/host"])
    if bdir is not None:
        shutil.rmtree(bdir, ignore_errors=True)
    for cid, r in sorted(results.items()):
        if r["verdict"] == "FAIL":
            issues.append(gate_result.issue("VT-FAIL", f"{cid}: {r['message']}", cid))
        if cid not in host:
            issues.append(gate_result.issue("VT-UNSPECIFIED", f"{cid} is not a host-unit case in the specification", cid))
    not_run = []
    for c in cases:
        if c["id"] in results:
            continue
        kind = (c.get("automation") or {}).get("kind") or "none"
        if c["id"] in host:
            issues.append(gate_result.issue("VT-NOT-RUN", f"{c['id']} printed no result", c["id"]))
        else:
            not_run.append(c["id"])
        results[c["id"]] = {"test_id": c["id"], "verdict": "NOT_RUN", "message": f"not executed (automation: {kind})"}
    vr = write_json(root / "hi" / stage / "results.json", {
        "schema": "forge-c-hi/verification-result@1", "stage": stage, "tool": _tool("verification"),
        "results": [results[k] for k in sorted(results)], "created_utc": utc_now()}) if write else None
    if not issues and (not_run or not cases):
        res = gate_result.result("verification", [], not_run_reason=(
            f"{len(not_run)} of {len(cases)} cases were not executed (no runner for simulator or manual cases): "
            + ", ".join(not_run[:8]))[:300], **common)
    else:
        res = gate_result.result("verification", issues, evidence=[vr] if vr else [], tool=_tool("verification"), **common)
    if write:
        gate_result.write(root, stage, res)
    return res
