"""T060: build, static analysis, unit tests and coverage on a tiny C project (tools may be missing: NOT_RUN)."""
from __future__ import annotations

import json
import shutil

import pytest

from forge_hi import code_gates, gates
from forge_hi.io import sha256_file
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


def test_verification_gate_runs_host_cases_and_never_passes_unexecuted_ones(tmp_path):
    """T068: integration, qualification and system tests were specified but nothing executed them."""
    from forge_hi import code_gates
    from hi_helpers import make_project, write
    root = tmp_path / "p"
    make_project(root, stages=("sys-req", "sw-req", "sw-integ"))
    write(root / "include/a.h", "int add(int a, int b);\n")
    write(root / "src/a.c", '#include "a.h"\nint add(int a, int b) { return a + b; }\n')
    prog = ('#include <stdio.h>\n#include "a.h"\nint main(void) { int ok = add(1, 2) == %d;\n'
            ' printf("HI-TEST ITC-SUP-001 %%s\\n", ok ? "PASS" : "FAIL sum"); return ok ? 0 : 1; }\n')
    write(root / "hi/sw-integ/host/test_a.c", prog % 3)

    def spec(*kinds):
        write(root / "hi/sw-integ/test-spec.json", {"items": [
            {"id": f"ITC-SUP-{n:03d}", "automation": {"kind": k, "file": "x"}} for n, k in enumerate(kinds, 1)]})

    def verdicts():
        return {r["test_id"]: r["verdict"] for r in json.loads((root / "hi/sw-integ/results.json").read_text())["results"]}

    import json
    spec("host-unit")
    assert code_gates.verification(root, "sw-integ")["verdict"] == "PASS"
    spec("host-unit", "simulator", "manual")
    res = code_gates.verification(root, "sw-integ")
    assert res["verdict"] == "NOT_RUN" and "2 of 3" in res["not_run_reason"]
    assert verdicts() == {"ITC-SUP-001": "PASS", "ITC-SUP-002": "NOT_RUN", "ITC-SUP-003": "NOT_RUN"}
    spec("host-unit", "host-unit")
    assert [i["code"] for i in code_gates.verification(root, "sw-integ")["issues"]] == ["VT-NOT-RUN"]
    write(root / "hi/sw-integ/host/test_a.c", prog % 4)
    spec("host-unit")
    assert [i["code"] for i in code_gates.verification(root, "sw-integ")["issues"]] == ["VT-FAIL"]
    spec()
    (root / "hi/sw-integ/host/test_a.c").unlink()
    assert code_gates.verification(root, "sw-integ")["verdict"] == "NOT_RUN"    # no cases is not a pass


def test_verification_gate_runs_simulator_programs_with_the_project_command(tmp_path):
    import json
    from forge_hi import code_gates
    from hi_helpers import make_project, write
    root = tmp_path / "p"
    make_project(root, stages=("sys-req", "sw-req", "sys-qual"))
    write(root / "hi/sys-qual/test-spec.json", {"items": [
        {"id": "SQT-SUP-001", "automation": {"kind": "simulator", "file": "hi/sys-qual/sim/test_a.c"}}]})
    write(root / "hi/sys-qual/sim/test_a.c", "int x;\n")
    assert code_gates.verification(root, "sys-qual")["verdict"] == "NOT_RUN"       # no simulator configured

    def configure(script):
        write(root / "sim.sh", script)
        p = json.loads((root / ".hi/project.json").read_text())
        p["simulator"] = {"command": ["sh", "sim.sh", "{program}"], "timeout_s": 5}
        write(root / ".hi/project.json", p)
        res = code_gates.verification(root, "sys-qual")
        return res["verdict"], [i["code"] for i in res["issues"]]

    assert configure('echo "HI-TEST SQT-SUP-001 PASS"\n') == ("PASS", [])
    assert configure('echo "HI-TEST SQT-SUP-001 FAIL late"; echo "HI-TEST SQT-SUP-001 PASS"\n') == ("FAIL", ["VT-FAIL"])
    assert configure("exit 3\n") == ("FAIL", ["VT-SIM", "VT-NOT-RUN"])
    assert configure("true\n") == ("FAIL", ["VT-NOT-RUN"])
    assert configure("sleep 30\n") == ("FAIL", ["VT-TIMEOUT", "VT-NOT-RUN"])


USER = '#include "clamp.h"\n#include "hal_pin.h"\n\nint clamp(int v, int lo, int hi)\n{\n    hal_pin_set(v);\n' \
       '    return (v < lo) ? lo : ((v > hi) ? hi : v);\n}\n'
PIN_H = "#ifndef HAL_PIN_H\n#define HAL_PIN_H\nvoid hal_pin_set(int v);\nint hal_pin_get(void);\n#endif\n"
PIN_C = ('#include "hal_pin.h"\n\nstatic int held = 0;\n\nvoid hal_pin_set(int v)\n{\n    held = v;\n}\n\n'
         'int hal_pin_get(void)\n{\n    return held;\n}\n')


def design(decisions):
    return {"schema": "forge-c-hi/design@1", "items": [], "decisions": decisions, "open_points": []}


@pytest.mark.skipif(not HAVE_CC, reason="gcc not installed")
def test_a_function_nobody_defines_fails_the_build_gate(tmp_project):
    # full-V attempt 3: design wrote only headers for seven drivers and deferred their code to a test stage
    c_project(tmp_project, src=USER)
    write(tmp_project / "include/hal_pin.h", PIN_H)
    res = code_gates.build(tmp_project)
    assert [(i["code"], i["target_id"]) for i in res["issues"]] == [("BUILD-UNDEFINED", "hal_pin_set")]
    dp = tmp_project / "hi/sw-design/design.json"
    outside = {"id": "DEC-1", "text": "x", "external": ["hal_pin_set"]}
    write(dp, design([outside]))                                         # nobody is named: still an issue
    assert code_gates.build(tmp_project)["verdict"] == "FAIL"
    write(dp, design([{**outside, "provided_by": "a later stage"}]))
    assert code_gates.build(tmp_project)["verdict"] == "FAIL"
    write(dp, design([{**outside, "provided_by": "CON-SUP-001"}]))
    assert code_gates.build(tmp_project)["verdict"] == "PASS"
    write(dp, design([]))
    write(tmp_project / "src/hal_pin.c", PIN_C)
    assert code_gates.build(tmp_project)["verdict"] == "PASS"


@pytest.mark.skipif(not HAVE_CC, reason="gcc not installed")
def test_a_program_may_replace_a_driver_or_use_the_real_one(tmp_project):
    fake = TEST_ALL.replace("int main(void)", "static int last = 0;\nvoid hal_pin_set(int v);\nint hal_pin_get(void);\n"
                            "void hal_pin_set(int v)\n{\n    last = v + 100;\n}\nint hal_pin_get(void)\n{\n"
                            "    return last;\n}\n\nint main(void)").replace(
        'clamp(50, 0, 10) == 10', 'clamp(50, 0, 10) == 10 && hal_pin_get() == 150')
    real = ('#include <stdio.h>\n#include "hal_pin.h"\n\nint main(void)\n{\n    hal_pin_set(7);\n'
            '    printf("HI-TEST UTC-PIN-001 %s\\n", hal_pin_get() == 7 ? "PASS" : "FAIL");\n    return 0;\n}\n')
    c_project(tmp_project, src=USER, test=fake, ids=("UTC-CLAMP-001", "UTC-CLAMP-002", "UTC-CLAMP-003", "UTC-PIN-001"))
    write(tmp_project / "include/hal_pin.h", PIN_H)
    write(tmp_project / "src/hal_pin.c", PIN_C)
    write(tmp_project / "tests/test_pin.c", real)
    res, _ = code_gates.unit_test(tmp_project)
    assert res["verdict"] == "PASS", res["issues"]


@pytest.mark.skipif(not (HAVE_CC and HAVE_GCOVR), reason="gcc or gcovr not installed")
def test_a_source_no_test_links_counts_as_not_covered(tmp_project):
    c_project(tmp_project)
    write(tmp_project / "include/hal_pin.h", PIN_H)
    write(tmp_project / "src/hal_pin.c", PIN_C)
    res = code_gates.coverage(tmp_project)
    cov = json.loads((tmp_project / "hi/unit-verif/coverage.json").read_text())
    assert cov["measured"]["statement"] < 100 and res["verdict"] == "FAIL", (cov, res)


SEAM = ('#include "clamp.h"\n#if defined(CLAMP_TEST)\nint clamp_inject;\nstatic int injected(void) { return clamp_inject; }\n'
        '#else\nstatic int injected(void) { return 0; }\n#endif\n\nint clamp(int v, int lo, int hi)\n{\n'
        '    (void)hi;\n    if ((v < lo) || injected()) {\n        return lo;\n    }\n    return v;\n}\n')
SEAM_TEST = ('#include <stdio.h>\n#include "clamp.h"\n\n#if defined(CLAMP_TEST)\nextern int clamp_inject;\n#endif\n\n'
             'int main(void)\n{\n    int ok = (clamp(-1, 0, 9) == 0) && (clamp(5, 0, 9) == 5);\n'
             '#if defined(CLAMP_TEST)\n    clamp_inject = 1;\n    ok = ok && (clamp(5, 0, 9) == 0);\n#endif\n'
             '    printf("HI-TEST UTC-CLAMP-001 %s\\n", ok ? "PASS" : "FAIL");\n    return ok ? 0 : 1;\n}\n')


@pytest.mark.skipif(not (HAVE_CC and HAVE_GCOVR), reason="gcc or gcovr not installed")
def test_a_coverage_gap_names_the_file_and_the_lines(tmp_project):
    partial = TEST_ALL.replace('    check("UTC-CLAMP-002", clamp(50, 0, 10) == 10);\n', "")
    c_project(tmp_project, test=partial, ids=("UTC-CLAMP-001", "UTC-CLAMP-003"))
    gap = [i for i in code_gates.coverage(tmp_project)["issues"] if i["code"] == "COV-GAP"]
    assert [i["target_id"] for i in gap] == ["src/clamp.c"]
    assert "lines never run: 9" in gap[0]["message"] and "line 8 (1 of 2)" in gap[0]["message"]


@pytest.mark.skipif(not (HAVE_CC and HAVE_GCOVR), reason="gcc or gcovr not installed")
def test_tests_are_built_with_the_test_defines_and_the_product_without(tmp_project):
    c_project(tmp_project, src=SEAM, test=SEAM_TEST, ids=("UTC-CLAMP-001",))
    assert code_gates.unit_test(tmp_project)[0]["verdict"] == "PASS"
    gap = [i for i in code_gates.coverage(tmp_project)["issues"] if i["code"] == "COV-GAP"]
    assert "lines never run" not in gap[0]["message"] and "branches never taken" in gap[0]["message"]   # the seam
    p = tmp_project / ".hi/project.json"
    project = json.loads(p.read_text())
    p.write_text(json.dumps({**project, "test_defines": ["CLAMP_TEST"]}))
    res = code_gates.coverage(tmp_project)
    assert res["verdict"] == "PASS", res["issues"]
    assert json.loads((tmp_project / "hi/unit-verif/coverage.json").read_text())["test_defines"] == ["CLAMP_TEST"]
    assert code_gates.build(tmp_project)["verdict"] == "PASS"
    write(tmp_project / "src/clamp.c", SEAM.replace("int clamp_inject;", "int clamp_inject"))   # broken in the test build only
    issue, = code_gates.build(tmp_project)["issues"]
    assert issue["code"] == "BUILD-ERROR" and issue["message"].startswith("-DCLAMP_TEST")
    write(tmp_project / "src/clamp.c", SEAM.replace("{ return 0; }", "{ return nobody(); }").replace(
        "#else", "#else\nint nobody(void);"))                                                  # and in the product only
    assert [i["code"] for i in code_gates.build(tmp_project)["issues"]] == ["BUILD-UNDEFINED"]


@pytest.mark.skipif(not (HAVE_CC and HAVE_GCOVR), reason="gcc or gcovr not installed")
def test_unit_evidence_keeps_the_logs_the_build_and_the_coverage_per_file(tmp_project):
    c_project(tmp_project)
    write(tmp_project / "hi/unit-verif/gates/logs/test_gone.log", "HI-TEST UTC-OLD-001 PASS\n")
    assert code_gates.coverage(tmp_project)["verdict"] == "PASS"
    assert code_gates.unit_test(tmp_project)[0]["verdict"] == "PASS"
    doc = json.loads((tmp_project / "hi/unit-verif/results.json").read_text())
    assert [f["path"] for f in doc["build"]["files"]] == ["include/clamp.h", "src/clamp.c", "tests/test_clamp.c"]
    assert "gcc" in doc["build"]["compiler"].lower() and "-std=c11" in doc["build"]["flags"]
    logs = list((tmp_project / "hi/unit-verif/gates/logs").iterdir())
    assert [p.name for p in logs] == ["test_clamp.log"]                 # nothing of an earlier run stays
    assert "HI-TEST UTC-CLAMP-001 PASS" in logs[0].read_text() and logs[0].read_text().endswith("exit 0\n")
    for r in doc["results"]:
        for e in r["evidence"]:
            assert sha256_file(tmp_project / e["path"]) == e["sha256"]
        assert [e["path"] for e in r["evidence"]] == ["tests/test_clamp.c", "hi/unit-verif/gates/logs/test_clamp.log"]
    f, = json.loads((tmp_project / "hi/unit-verif/coverage.json").read_text())["files"]
    assert f["path"] == "src/clamp.c" and f["sha256"] == sha256_file(tmp_project / "src/clamp.c")
    assert (f["statements_not_run"], f["branches_not_taken"], f["lines_not_run"]) == (0, 0, [])
    assert f["branches"] == 4 and f["decision_lines"] == [5, 8]
