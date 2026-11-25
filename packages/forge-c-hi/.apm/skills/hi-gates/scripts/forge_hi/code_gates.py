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


def _identify(root: Path, paths) -> list[dict]:
    return [{"path": p.relative_to(root).as_posix(), "sha256": sha256_file(p)} for p in sorted(set(paths)) if p.is_file()]


def _fresh_logs(root: Path, stage: str) -> Path:
    """Directory of the test programs' output, emptied: a log of an earlier run never stands beside new results."""
    d = Path(root) / "hi" / stage / "gates" / "logs"       # the author cannot write there
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    return d


def _log(root: Path, logs: Path | None, name: str, text: str) -> list[dict]:
    if logs is None:
        return []
    (logs / f"{name}.log").write_text(text)
    return _identify(root, [logs / f"{name}.log"])


def _build_record(root: Path, *dirs: str, simulator: dict | None = None) -> dict:
    """What the results were produced from: compiler, flags, and every source, header, fake and test file by hash."""
    version = _run([cc(), "--version"], root).stdout.splitlines()
    files = [p for d in ("src", "include", *dirs) for p in (root / d).rglob("*") if p.suffix != ".pyc"]
    return {"compiler": version[0] if version else "unknown", "flags": [*CFLAGS, *test_flags(root)],
            **({"simulator": simulator["command"]} if simulator else {}), "files": _identify(root, files)}


def _tool(name: str) -> dict:
    return {"name": f"forge-c-hi {name}", "version": __version__}


def _run(cmd: list[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


# standard C library functions a unit may call without defining them
LIBC = {"memcpy", "memset", "memcmp", "memmove", "strlen", "strcmp", "strncmp", "strncpy", "strcpy", "strchr", "strnlen",
        "abs", "labs", "abort"}


def undefined_functions(root: Path, objects: list[Path]) -> list[str]:
    """Symbols the sources use and none of them defines, without the standard library, linker symbols (leading
    underscore) and the functions a design decision says come from outside (`external`, `provided_by`)."""
    nm = shutil.which(os.environ.get("NM", "nm"))
    if nm is None or not objects:
        return []
    defined, used = set(), set()
    for line in _run([nm, "-P", *map(str, objects)], root).stdout.splitlines():
        f = line.split()
        if len(f) >= 2 and not f[0].endswith(":"):
            (used if f[1] in "UwV" else defined if f[1].isupper() else set()).add(f[0])
    rigor_project = load_project(root)
    links = {ln.get("project_path") for ln in rigor_project.get("links", [])}
    outside: set[str] = set()
    wp = root / stages()["sw-design"]["outputs"][0]
    for d in (read_json(wp).get("decisions", []) if wp.is_file() else []):
        if isinstance(d, dict) and (d.get("provided_by") in links or
                                    re.match(r"^CON-[A-Z0-9_]+-\d{3}$", str(d.get("provided_by", "")))):
            outside |= set(d.get("external") or [])
    return sorted(u for u in used - defined - outside - LIBC if not u.startswith("_"))


def test_flags(root: Path) -> list[str]:
    """-D flags of the project's test build (`test_defines`). The tests are built with them; the product is not."""
    return [f"-D{d}" for d in load_project(root).get("test_defines") or []]


def uncovered(files: list[dict]) -> list[dict]:
    """One issue per source file with statements or branches no test takes, so that the author knows where to look."""
    out = []
    for f in files:
        rows = [x for x in f.get("lines", []) if not x.get("gcovr/noncode")]
        lines = [x["line_number"] for x in rows if x["count"] == 0]
        # a line that is never reached is named once, not again for its branches
        branches = [(x["line_number"], sum(b["count"] == 0 for b in x.get("branches", [])), len(x.get("branches", [])))
                    for x in rows if x["count"] > 0]
        parts = []
        if lines:
            parts.append("lines never run: " + ", ".join(map(str, lines)))
        if any(n for _, n, _ in branches):
            parts.append("branches never taken: " + ", ".join(f"line {ln} ({n} of {m})" for ln, n, m in branches if n))
        if parts:
            out.append(gate_result.issue("COV-GAP", f"{f['file']}: {'; '.join(parts)}"[:280], f["file"]))
    return out


def coverage_by_file(root: Path, files: list[dict]) -> list[dict]:
    """The measurement per source file: counts, and every line that has an untaken statement or branch."""
    out = []
    for f in files:
        rows = [x for x in f.get("lines", []) if not x.get("gcovr/noncode")]
        br = [(x["line_number"], b["count"]) for x in rows for b in x.get("branches", [])]
        out.append({"path": f["file"], "sha256": sha256_file(root / f["file"]),
                    "statements": len(rows), "statements_not_run": sum(x["count"] == 0 for x in rows),
                    "branches": len(br), "branches_not_taken": sum(n == 0 for _, n in br),
                    "lines_not_run": [x["line_number"] for x in rows if x["count"] == 0],
                    "lines_with_branches_not_taken": sorted({ln for ln, n in br if n == 0}),
                    "decision_lines": sorted({ln for ln, _ in br})})
    return out


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
            # the product build, and the test build when the project has one
            for variant in [[]] + ([test_flags(root)] if test_flags(root) else []):
                if issues:
                    break
                for n, src in enumerate(srcs):
                    r = _run([compiler, *CFLAGS, *variant, "-Iinclude", "-c", str(src.relative_to(root)), "-o",
                              str(Path(tmp) / f"{n}.o")], root)
                    if r.returncode != 0:
                        first = next((l for l in r.stderr.splitlines() if "error" in l), r.stderr.strip()[:200])
                        issues.append(gate_result.issue("BUILD-ERROR", " ".join([*variant, first])[:280],
                                                        src.relative_to(root).as_posix()))
                missing = [] if issues else undefined_functions(root, sorted(Path(tmp).glob("*.o")))
                issues += [gate_result.issue(
                    "BUILD-UNDEFINED", f"{u} is used and no file in src/ defines it; write it, or name it in a decision's "
                    "`external` with `provided_by` a linked project or the CON id that says who provides it", u)
                    for u in missing]
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
                   include: list[str] | None = None, logs: Path | None = None) -> tuple[dict[str, dict], list[dict], Path | None]:
    """Compile and run every test program. Returns per-case results, issues, and the build dir (coverage)."""
    root = Path(root)
    compiler = cc()
    out: dict[str, dict] = {}
    issues: list[dict] = []
    bdir = Path(tempfile.mkdtemp(prefix="hi-unit-"))
    extra = test_flags(root) + (["--coverage", "-O0", "-g"] if coverage else [])
    # the sources go into a library, so that a program which defines every function of a driver (a fake) links without
    # the real one, while the other units and the drivers under test are the real ones
    objs, broken = [], []
    for n, s in enumerate(sources(root)):
        obj = bdir / f"{n:03d}-{s.stem}.o"
        r = _run([compiler, *CFLAGS, *extra, "-Iinclude", "-c", s.relative_to(root).as_posix(), "-o", str(obj)], root)
        if r.returncode == 0:
            objs.append(str(obj))
        else:
            broken.append(s)
            issues.append(gate_result.issue("UT-BUILD", f"{s.relative_to(root).as_posix()}: {r.stderr.strip()[:240]}",
                                            s.relative_to(root).as_posix()))
    lib = bdir / "libsrc.a"
    if broken:
        return out, issues, bdir
    if objs:
        ar = _run([shutil.which("ar") or "ar", "rcs", str(lib), *objs], root)
        if ar.returncode != 0:
            issues.append(gate_result.issue("UT-BUILD", f"ar: {ar.stderr.strip()[:240]}"))
            return out, issues, bdir
    for t in (test_programs(root) if programs is None else programs):
        exe = bdir / t.stem
        rel = t.relative_to(root).as_posix()
        r = _run([compiler, *CFLAGS, *extra, "-Iinclude", "-Itests",
                  *[f"-I{i}" for i in include or []], rel,
                  *([str(lib)] if objs else []), "-o", str(exe)], root)
        if r.returncode != 0:
            issues.append(gate_result.issue("UT-BUILD", f"{rel}: {r.stderr.strip()[:240]}", rel))
            continue
        try:
            run = subprocess.run([str(exe)], cwd=root, capture_output=True, text=True, timeout=RUN_TIMEOUT)
        except subprocess.TimeoutExpired:
            issues.append(gate_result.issue("UT-TIMEOUT", f"{rel} did not finish in {RUN_TIMEOUT} s", rel))
            continue
        cases = HI_TEST.findall(run.stdout)
        kept = _log(root, logs, t.stem, f"{run.stdout}{run.stderr}exit {run.returncode}\n")
        for cid, verdict, why in cases:
            out[cid] = {"test_id": cid, "verdict": verdict, "message": (why or rel)[:300],
                        "evidence": [{"path": rel, "sha256": sha256_file(t)}, *kept]}
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
    # only the gate's own run writes evidence: the instrumented run of the coverage gate must not replace the files
    # whose hashes the unit-test verdict has recorded
    results, issues, bdir = run_unit_tests(root, coverage=coverage,
                                           logs=_fresh_logs(root, "unit-verif") if write else None)
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
          "results": [results[k] for k in sorted(results)], "build": _build_record(root, "tests"),
          "created_utc": utc_now()}
    if write:
        write_json(root / RESULTS, vr)
    res = gate_result.result("unit-test", issues, evidence=([root / RESULTS] if write else []) + test_programs(root),
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
                      "--json-summary", "-", "--json", str(bdir / "lines.json"), str(bdir)], root)
            gaps = json.loads((bdir / "lines.json").read_text())["files"] if (bdir / "lines.json").is_file() else []
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
                issues += uncovered(gaps) if issues else []
                if ut["verdict"] != "PASS":
                    issues.append(gate_result.issue(
                        "COV-UNIT-TEST", "the unit tests do not pass in the run that measured the coverage: "
                        + ", ".join(sorted({str(i.get("target_id") or i["code"]) for i in ut["issues"]}))[:200]))
                cov_file = write_json(root / "hi" / "unit-verif" / "coverage.json",
                                      {"schema": "forge-c-hi/coverage@1", "measured": measured, "targets": targets,
                                       "files": coverage_by_file(root, gaps),
                                       "tool": "gcovr", "test_defines": load_project(root).get("test_defines") or [],
                                       "created_utc": utc_now()})
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


def _run_simulator(root: Path, stage: str, simulator: dict, logs: Path | None = None) -> tuple[dict[str, dict], list[dict]]:
    out: dict[str, dict] = {}
    issues: list[dict] = []
    limit = int(simulator.get("timeout_s", 600))
    for t in sorted((root / "hi" / stage / "sim").glob("test_*.c")):
        rel = t.relative_to(root).as_posix()
        argv = [a.replace("{program}", rel) for a in simulator["command"]]
        try:
            r = subprocess.run(argv, cwd=root, capture_output=True, text=True, errors="replace", timeout=limit,
                               env=dict(os.environ, HI_TEST_CFLAGS=" ".join(test_flags(root)),
                                        **{k: str(v) for k, v in (simulator.get("env") or {}).items()}))
        except subprocess.TimeoutExpired:
            issues.append(gate_result.issue("VT-TIMEOUT", f"{rel} did not finish in {limit} s", rel))
            continue
        except OSError as exc:
            issues.append(gate_result.issue("VT-SIM", f"{rel}: the simulator command cannot run: {exc}"[:280], rel))
            continue
        if r.returncode != 0:
            issues.append(gate_result.issue("VT-SIM", f"{rel}: exit {r.returncode}: {r.stderr.strip()[-240:]}", rel))
            continue
        kept = _log(root, logs, f"sim-{t.stem}", r.stdout.replace("\r", "") + "exit 0\n")
        for cid, verdict, why in HI_TEST.findall(r.stdout.replace("\r", "")):
            if out.get(cid, {}).get("verdict") != "FAIL":   # a later PASS never hides a FAIL of the same case
                out[cid] = {"test_id": cid, "verdict": verdict, "message": (why or rel)[:300],
                            "evidence": [{"path": rel, "sha256": sha256_file(t)}, *kept]}
    return out, issues


def verification(root: Path, stage: str, *, write: bool = True, keep: Path | None = None) -> dict:
    """The `verification` gate of sw-integ, sw-qual, sys-integ and sys-qual (T068): the host programs
    ``hi/<stage>/host/test_*.c`` are compiled with the real sources and run. The simulator programs
    ``hi/<stage>/sim/test_*.c`` are run with the project's `simulator.command`, which prints the same HI-TEST lines.
    A manual case, or a simulator case without that command, is NOT_RUN, so the gate is NOT_RUN at best and the
    package cannot be sealed READY on tests that were only specified. With ``write=False`` nothing of the stage's
    evidence changes; the output logs then go to the directory ``keep``, if given."""
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
    logs = _fresh_logs(root, stage) if write else keep
    results, issues, bdir = run_unit_tests(root, coverage=False, programs=sorted(hdir.glob("test_*.c")),
                                           include=[f"hi/{stage}/host"], logs=logs)
    if bdir is not None:
        shutil.rmtree(bdir, ignore_errors=True)
    for cid in sorted(set(results) - host):
        issues.append(gate_result.issue("VT-UNSPECIFIED", f"{cid} is not a host-unit case in the specification", cid))
    simulator = load_project(root).get("simulator") or {}
    if simulator.get("command"):
        sim = {c["id"] for c in cases if (c.get("automation") or {}).get("kind") == "simulator"}
        got, sim_issues = _run_simulator(root, stage, simulator, logs)
        issues += sim_issues
        for cid in sorted(set(got) - sim):
            issues.append(gate_result.issue("VT-UNSPECIFIED", f"{cid} is not a simulator case in the specification", cid))
        for cid, r in got.items():
            if cid not in results:
                results[cid] = r
        for c in cases:     # full-V attempt 3 pass 35: 36 of 44 test cases were declared manual, with a platform at hand
            if (c.get("method") == "test" and (c.get("automation") or {}).get("kind") not in ("host-unit", "simulator")
                    and len(str((c.get("attributes") or {}).get("manual_reason") or "").strip()) < 20):
                issues.append(gate_result.issue(
                    "VT-MANUAL", f"{c['id']}: a case of method test is executed. Write its program, or state in "
                    "attributes.manual_reason what the platform cannot stimulate or observe for it", c["id"]))
        host = host | sim            # an executable case that prints no result is an issue, not a gap
    for cid, r in sorted(results.items()):
        if r["verdict"] == "FAIL":
            issues.append(gate_result.issue("VT-FAIL", f"{cid}: {r['message']}", cid))
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
        "results": [results[k] for k in sorted(results)],
        "build": _build_record(root, f"hi/{stage}/host", f"hi/{stage}/sim", "sim", simulator=simulator
                               if simulator.get("command") else None),
        "created_utc": utc_now()}) if write else None
    if not issues and (not_run or not cases):
        res = gate_result.result("verification", [], not_run_reason=(
            f"{len(not_run)} of {len(cases)} cases were not executed (no runner for simulator or manual cases): "
            + ", ".join(not_run[:8]))[:300], **common)
    else:
        res = gate_result.result("verification", issues, evidence=[vr] if vr else [], tool=_tool("verification"), **common)
    if write:
        gate_result.write(root, stage, res)
    return res
