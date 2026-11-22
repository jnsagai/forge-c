"""T060: build, static analysis, unit tests and coverage on a tiny C project (tools may be missing: NOT_RUN)."""
from __future__ import annotations

import json
import shutil

import pytest

from forge_hi import code_gates, gates
from hi_helpers import PROV, make_project, write

HAVE_CC = bool(shutil.which("gcc"))
HAVE_CPPCHECK = bool(shutil.which("cppcheck"))
HAVE_GCOVR = bool(shutil.which("gcovr"))

HDR = "#ifndef CLAMP_H\n#define CLAMP_H\nint clamp(int v, int lo, int hi);\n#endif\n"
SRC = ('#include "clamp.h"\n\nint clamp(int v, int lo, int hi)\n{\n    if (v < lo) {\n        return lo;\n    }\n'
       '    if (v > hi) {\n        return hi;\n    }\n    return v;\n}\n')
TEST_ALL = ('#include <stdio.h>\n#include "clamp.h"\n\nstatic int fails = 0;\n'
            'static void check(const char *id, int ok)\n{\n    printf("HI-TEST %s %s\\n", id, ok ? "PASS" : "FAIL");\n'
            '    if (!ok) {\n        fails++;\n    }\n}\n\nint main(void)\n{\n'
            '    check("UTC-CLAMP-001", clamp(-5, 0, 10) == 0);\n    check("UTC-CLAMP-002", clamp(50, 0, 10) == 10);\n'
            '    check("UTC-CLAMP-003", clamp(5, 0, 10) == 5);\n    return fails != 0;\n}\n')


def spec(*ids):
    return {"schema": "forge-c-hi/test-spec@1", "stage": "unit-verif", "baseline_id": "b", "status": "draft",
            "provenance": PROV, "open_points": [], "items": [
                {"id": i, "title": i, "objective": "Check the clamp unit.", "method": "test", "steps": ["call"],
                 "expected": ["value"], "sources": [{"kind": "upstream", "id": "SWU-CLAMP-001"}],
                 "automation": {"kind": "host-unit", "file": "tests/test_clamp.c"}, "status": "proposed"} for i in ids]}


def c_project(root, level="HI-2", test=TEST_ALL, src=SRC, ids=("UTC-CLAMP-001", "UTC-CLAMP-002", "UTC-CLAMP-003")):
    make_project(root, level=level, stages=("sw-design", "unit-verif"))
    write(root / "include/clamp.h", HDR)
    write(root / "src/clamp.c", src)
    write(root / "tests/test_clamp.c", test)
    write(root / "hi/unit-verif/test-spec.json", spec(*ids))
    return root


@pytest.mark.skipif(not HAVE_CC, reason="gcc not installed")
def test_build_pass_and_fail(tmp_project):
    c_project(tmp_project)
    assert code_gates.build(tmp_project)["verdict"] == "PASS"
    write(tmp_project / "src/clamp.c", SRC.replace("return v;", "return v\n"))
    res = code_gates.build(tmp_project)
    assert res["verdict"] == "FAIL" and res["issues"][0]["code"] == "BUILD-ERROR"
    write(tmp_project / "src/clamp.c", SRC + "int main(void) { return 0; }\n")
    assert any(i["code"] == "BUILD-MAIN-IN-SRC" for i in code_gates.build(tmp_project)["issues"])


@pytest.mark.skipif(not HAVE_CC, reason="gcc not installed")
def test_warnings_are_errors(tmp_project):
    c_project(tmp_project, src=SRC.replace("int clamp(int v, int lo, int hi)\n{", "int clamp(int v, int lo, int hi)\n{\n    int unused;"))
    assert code_gates.build(tmp_project)["verdict"] == "FAIL"


@pytest.mark.skipif(not HAVE_CPPCHECK, reason="cppcheck not installed")
def test_static_analysis(tmp_project):
    c_project(tmp_project)
    assert code_gates.static_analysis(tmp_project)["verdict"] == "PASS"
    write(tmp_project / "src/bad.c", "int bad(void)\n{\n    int a[2];\n    a[2] = 1;\n    return a[0];\n}\n")
    res = code_gates.static_analysis(tmp_project)
    assert res["verdict"] == "FAIL" and any("arrayIndexOutOfBounds" in i["code"] for i in res["issues"])


@pytest.mark.skipif(not HAVE_CC, reason="gcc not installed")
def test_unit_tests_results_and_not_run_cases(tmp_project):
    c_project(tmp_project, ids=("UTC-CLAMP-001", "UTC-CLAMP-002", "UTC-CLAMP-003", "UTC-CLAMP-004"))
    res, _ = code_gates.unit_test(tmp_project)
    assert res["verdict"] == "FAIL"
    codes = {(i["code"], i.get("target_id")) for i in res["issues"]}
    assert ("UT-NOT-RUN", "UTC-CLAMP-004") in codes
    vr = json.loads((tmp_project / "hi/unit-verif/results.json").read_text())
    verdicts = {r["test_id"]: r["verdict"] for r in vr["results"]}
    assert verdicts == {"UTC-CLAMP-001": "PASS", "UTC-CLAMP-002": "PASS", "UTC-CLAMP-003": "PASS",
                        "UTC-CLAMP-004": "NOT_RUN"}
    from forge_hi.config import schema
    from forge_hi.jsonschema_lite import validate
    assert validate(vr, schema("verification-result")) == []


@pytest.mark.skipif(not HAVE_CC, reason="gcc not installed")
def test_failing_case_fails_gate(tmp_project):
    c_project(tmp_project, src=SRC.replace("return hi;", "return lo;"))
    res, _ = code_gates.unit_test(tmp_project)
    assert ("UT-FAIL", "UTC-CLAMP-002") in {(i["code"], i.get("target_id")) for i in res["issues"]}


@pytest.mark.skipif(not (HAVE_CC and HAVE_GCOVR), reason="gcc or gcovr not installed")
def test_coverage_against_profile_targets(tmp_project):
    c_project(tmp_project, level="HI-2")  # generic HI-2: statement 100, branch 100
    res = code_gates.coverage(tmp_project)
    assert res["verdict"] == "PASS", res
    cov = json.loads((tmp_project / "hi/unit-verif/coverage.json").read_text())
    assert cov["measured"]["statement"] == 100.0
    partial = TEST_ALL.replace('    check("UTC-CLAMP-002", clamp(50, 0, 10) == 10);\n', "")
    c_project(tmp_project, level="HI-2", test=partial, ids=("UTC-CLAMP-001", "UTC-CLAMP-003"))
    res = code_gates.coverage(tmp_project)
    assert res["verdict"] == "FAIL" and {"COV-STATEMENT", "COV-BRANCH"} & {i["code"] for i in res["issues"]}


@pytest.mark.skipif(not (HAVE_CC and HAVE_GCOVR), reason="gcc or gcovr not installed")
def test_mcdc_required_is_not_run(tmp_project):
    c_project(tmp_project, level="HI-4")
    res = code_gates.coverage(tmp_project)
    assert res["verdict"] == "NOT_RUN" and "MC/DC" in res["not_run_reason"]


def test_missing_tools_are_not_run(tmp_project, monkeypatch):
    c_project(tmp_project)
    monkeypatch.setattr(code_gates.shutil, "which", lambda _: None)
    assert code_gates.build(tmp_project)["verdict"] == "NOT_RUN"
    assert code_gates.static_analysis(tmp_project)["verdict"] == "NOT_RUN"
    assert code_gates.unit_test(tmp_project)[0]["verdict"] == "NOT_RUN"
    assert code_gates.coverage(tmp_project)["verdict"] == "NOT_RUN"


@pytest.mark.skipif(not HAVE_CC, reason="gcc not installed")
def test_stage_gate_runs_code_gates(tmp_project):
    c_project(tmp_project, level="HI-2")
    summ = gates.gate_stage(tmp_project, "sw-design")
    assert summ["gates"]["build"] == "PASS"
    assert summ["gates"].get("static-analysis") in ("PASS", "NOT_RUN")
