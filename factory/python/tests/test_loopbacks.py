"""ADR-0008 cross-phase loopbacks: defect register, upstream routing chain, verification with unchanged tests."""
import json
import os
import subprocess
import sys

import pytest
from forge_factory.inspection import defects as D
from forge_factory.inspection.engine import Store

REQS = ("- **SWR-013** If a ready flag is not set within the timeout, then the RCC driver shall return HAL_TIMEOUT.\n"
        "- **SWR-014** If a parameter is invalid, then the RCC driver shall return HAL_ERROR without any register "
        "write.\n")


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / ".ev"))
    for rel, txt in {"workproducts/SWE.1/software_requirements.md": REQS,
                     "software/hal/stm32n6xx_hal_rcc.c": "int x;\nint y;\n",
                     "software/tests/software/scn_invalid_param.c": "/* SWR-014 */\n"}.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(txt)
    return tmp_path


def tool(ws, phase, op, status, ts="2026-10-15T10:00:00Z"):
    p = ws / "evidence/tool-results.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"ts_utc": ts, "phase": phase, "op": op, "server": "forge-tests-mcp",
                            "result": {"status": status, "issues": [], "summary": op}}) + "\n")


def code_defect(ws, phase="SWE.6"):
    return D.report(ws, detected_phase=phase, reported_by="swe6-author", kind="CODE", summary="HAL has no parameter "
                    "validation: SWR-014 scenario fails", requirement_ids=["SWR-014"],
                    test_files=["software/tests/software/scn_invalid_param.c"], evidence_refs=[],
                    requirement_quote="shall return HAL_ERROR without any register\nwrite")


def gate(ws, phase, step, stdin=b""):
    return subprocess.run([sys.executable, "-m", "forge_factory.inspection.gate", "--workspace", str(ws), "--phase",
                           phase, "--step", step], input=stdin, capture_output=True, env={**os.environ})


def test_report_validation_is_deterministic(ws):
    with pytest.raises(D.DefectError, match="CODE_DEFECT_NEEDS_EVIDENCE"):
        code_defect(ws)  # no failing test run and no source location: blame-shifting refused
    tool(ws, "SWE.5", "run_renode", "FAIL")
    with pytest.raises(D.DefectError, match="REQUIREMENT_QUOTE_REQUIRED"):  # r62: code asked to contradict SWR-013
        D.report(ws, detected_phase="SWE.5", reported_by="swe5-author", kind="CODE", summary="hardware leaves the "
                 "enable bit set after a timeout; the driver must not clear it", requirement_ids=["SWR-013"],
                 test_files=["software/tests/software/scn_invalid_param.c"], evidence_refs=[],
                 requirement_quote="the driver shall leave the enable bit set after a timeout")
    with pytest.raises(D.DefectError, match="UNKNOWN_REQUIREMENT"):
        D.report(ws, detected_phase="SWE.6", reported_by="r", kind="ARCHITECTURE", summary="api cannot validate",
                 requirement_ids=["SWR-999"], test_files=[], evidence_refs=[])
    with pytest.raises(D.DefectError, match="TARGET_NOT_UPSTREAM"):
        D.report(ws, detected_phase="SWE.2", reported_by="r", kind="CODE", summary="code wrong here",
                 requirement_ids=["SWR-014"], test_files=[], evidence_refs=["software/hal/stm32n6xx_hal_rcc.c:2"])
    with pytest.raises(D.DefectError, match="TEST_FILE_NOT_FOUND"):
        D.report(ws, detected_phase="SWE.6", reported_by="r", kind="TEST", summary="expectation was wrong",
                 requirement_ids=["SWR-014"], test_files=["../../etc/passwd"], evidence_refs=[],
                 requirement_quote="without any register write")
    tool(ws, "SWE.6", "run_robot", "FAIL")
    rec = code_defect(ws)
    assert (rec["id"], rec["target_phase"], rec["status"]) == ("DEF-001", "SWE.3", "OPEN")
    assert list(rec["test_files"]) == ["software/tests/software/scn_invalid_param.c"]
    loc = D.report(ws, detected_phase="SWE.4", reported_by="swe4-inspector", kind="CODE", summary="missing check",
                   requirement_ids=["SWR-014"], test_files=[], evidence_refs=["software/hal/stm32n6xx_hal_rcc.c:2"],
                   requirement_quote="shall return HAL_ERROR without any register write")
    assert loc["target_phase"] == "SWE.3"  # an inspector may cite a source location instead of a failing run
    with pytest.raises(D.DefectError, match="REQUIREMENT_QUOTE_REQUIRED"):  # r70: invented quote, wrong blame
        D.report(ws, detected_phase="SWE.4", reported_by="swe4-author", kind="ARCHITECTURE", summary="API has no PLL "
                 "disable", requirement_ids=["SWR-013"], test_files=[], evidence_refs=[],
                 requirement_quote="SWR-013: PLL disable for every oscillator")
    arch = D.report(ws, detected_phase="SWE.6", reported_by="r", kind="ARCHITECTURE", summary="timeout-only API "
                    "cannot express an invalid parameter", requirement_ids=["SWR-014"], test_files=[], evidence_refs=[],
                    requirement_quote="If a parameter is invalid, then the RCC driver shall return HAL_ERROR")
    assert arch["target_phase"] == "SWE.2"
    inp = D.report(ws, detected_phase="SWE.1", reported_by="r", kind="INPUT", summary="RM sections contradict",
                   requirement_ids=[], test_files=[], evidence_refs=[])
    assert inp["status"] == "ESCALATED" and inp["target_phase"] is None
    t = D.report(ws, detected_phase="SWE.6", reported_by="r", kind="TEST", summary="wrong bit in expectation",
                 requirement_ids=["SWR-013"], test_files=["software/tests/software/scn_invalid_param.c"],
                 evidence_refs=[], requirement_quote="the RCC driver shall return HAL_TIMEOUT")
    assert t["status"] == "DECLARED" and t["target_phase"] == "SWE.6"
    assert sorted(D.gaps(ws)) == ["escalated_defect:DEF-004:INPUT", "open_defect:DEF-001:CODE:OPEN",
                                  "open_defect:DEF-002:CODE:OPEN", "open_defect:DEF-003:ARCHITECTURE:OPEN"]


def test_route_leaves_phase_and_chain_routes_to_owner_within_budget(ws):
    tool(ws, "SWE.6", "run_robot", "FAIL")
    code_defect(ws)
    r = gate(ws, "SWE.6", "route")
    assert r.returncode == 1 and b"UPSTREAM" in r.stdout and b"DEF-001->SWE.3" in r.stdout
    assert gate(ws, "SWE.1", "upstream").returncode != 0  # chain: earliest owner first, nothing for SWE.1
    assert gate(ws, "SWE.2", "upstream").returncode != 0
    assert gate(ws, "SWE.3", "upstream").returncode == 0  # -> swe3_fix_author
    assert D.all_defects(ws)[0]["status"] == "IN_FIX" and D.loops_used(ws) == 1
    assert D.open_from(ws, "SWE.6") == []  # claimed: the phase no longer leaves for it
    # second loop allowed, third refused (UPSTREAM_LOOP_BUDGET = 2) -> defect stays OPEN -> package gap
    tool(ws, "SWE.6", "run_robot", "FAIL", ts="2026-10-15T11:00:00Z")
    code_defect(ws)
    assert gate(ws, "SWE.3", "upstream").returncode == 0 and D.loops_used(ws) == 2
    code_defect(ws)
    assert gate(ws, "SWE.3", "upstream").returncode != 0
    assert "open_defect:DEF-003:CODE:OPEN" in D.gaps(ws)


def test_fix_verified_only_with_unchanged_tests_and_a_later_pass(ws):
    tool(ws, "SWE.6", "run_robot", "FAIL")
    code_defect(ws)
    D.take_upstream(ws, "SWE.3")
    assert D.mark_fixed(ws, "SWE.3", "BL-SWE.3-002") == ["DEF-001"]
    tool(ws, "SWE.6", "run_robot", "PASS", ts="2000-01-01T00:00:00Z")  # a PASS from before the fix never verifies
    assert D.verify_on_freeze(ws, "SWE.6") == [] and D.all_defects(ws)[0]["status"] == "FIXED"
    tool(ws, "SWE.6", "run_robot", "PASS", ts="2999-01-01T00:00:00Z")
    assert D.verify_on_freeze(ws, "SWE.6") == [] and D.all_defects(ws)[0]["status"] == "VERIFIED"
    assert D.gaps(ws) == []


def test_bent_test_after_fix_is_rejected_at_freeze(ws):
    tool(ws, "SWE.6", "run_robot", "FAIL")
    code_defect(ws)
    D.take_upstream(ws, "SWE.3")
    D.mark_fixed(ws, "SWE.3", "BL-SWE.3-002")
    (ws / "software/tests/software/scn_invalid_param.c").write_text("/* rewritten to pass */\n")
    tool(ws, "SWE.6", "run_robot", "PASS", ts="2999-01-01T00:00:00Z")
    assert D.verify_on_freeze(ws, "SWE.6") == ["DEFECT_TEST_CHANGED:DEF-001:software/tests/software/scn_invalid_param.c"]
    assert D.all_defects(ws)[0]["status"] == "FIXED"


def test_only_target_author_rejects_with_reason(ws):
    tool(ws, "SWE.6", "run_robot", "FAIL")
    code_defect(ws)
    with pytest.raises(D.DefectError, match="NOT_TARGET_AUTHOR"):
        D.reject(ws, "DEF-001", "swe6-author", "the test is fine really")
    with pytest.raises(D.DefectError, match="REASON_REQUIRED"):
        D.reject(ws, "DEF-001", "swe3-author", "no")
    rec = D.reject(ws, "DEF-001", "swe3-author", "scenario writes RCC_CR before the call; HAL is correct")
    assert rec["status"] == "REJECTED" and D.gaps(ws) == []


def test_stale_tool_pass_before_current_code_baseline_does_not_count(ws):
    (ws / "workproducts/SWE.3").mkdir(parents=True)
    (ws / "workproducts/SWE.3/detailed_design.md").write_text("# D\n")
    s = Store(ws)
    tool(ws, "SWE.4", "run_unit", "PASS", ts="2000-01-01T00:00:00Z")
    s.base.joinpath("SWE.3").mkdir(parents=True)
    s.base.joinpath("SWE.3/BL-SWE.3-001.json").write_text(json.dumps(
        {"baseline_id": "BL-SWE.3-001", "phase": "SWE.3", "baseline_hash": "x", "files": [], "upstream": {},
         "frozen_at": "2026-10-15T09:00:00Z", "author_role": "swe3-author"}))
    assert "REQUIRED_TOOL_STALE:run_unit:before BL-SWE.3-001" in s.missing_outputs("SWE.4")
    tool(ws, "SWE.4", "run_unit", "PASS", ts="2026-10-15T09:30:00Z")
    assert not [m for m in s.missing_outputs("SWE.4") if "run_unit" in m]


def test_mcp_report_defect_uses_node_phase_and_role(ws, monkeypatch):
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import evidence

    tool(ws, "SWE.6", "run_robot", "FAIL")
    for k, v in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_ROLE": "swe6-author",
                 "FORGE_PHASE": "SWE.6"}.items():
        monkeypatch.setenv(k, v)
    op = next(o for o in evidence.OPERATIONS if o.name == "report_defect")
    out = sdk.invoke("forge-evidence-mcp", op, {"kind": "CODE", "summary": "HAL lacks parameter validation (SWR-014)",
                                                "requirement_ids": "SWR-014",
                                                "test_files": "software/tests/software/scn_invalid_param.c",
                                                "requirement_quote": "without any register write"})
    assert out["status"] == "PASS" and "DEF-001 CODE -> SWE.3 OPEN" in out["summary"], out
    rec = D.all_defects(ws)[0]
    assert rec["reported_by"] == "swe6-author" and rec["detected_phase"] == "SWE.6"
    rej = next(o for o in evidence.OPERATIONS if o.name == "reject_defect")
    denied = sdk.invoke("forge-evidence-mcp", rej, {"defect_id": "DEF-001", "reason": "I do not like this defect"})
    assert denied["status"] != "PASS"  # swe6-author is not granted reject_defect (registry) / not the target author


def _run(ws, phase, op, status, ts, code, files, failed):
    p = ws / D.INTEGRITY_LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"ts_utc": ts, "phase": phase, "op": op, "status": status, "code_sha": code,
                            "files": files, "assert_failed": failed}) + "\n")


def test_bent_test_without_declaration_blocks_freeze_r60(ws):
    """r60: the SWR-014 scenario failed 4 checks, was rewritten into a different test and passed, code unchanged."""
    f = "software/tests/software/scn_invalid_param.c"
    _run(ws, "SWE.6", "run_robot", "FAIL", "2026-10-15T10:00:00Z", "C1", {f: "h1"}, [f])
    _run(ws, "SWE.6", "run_robot", "PASS", "2026-10-15T10:05:00Z", "C1", {f: "h2"}, [])
    assert D.bent_tests(ws, "SWE.6") == [f"TEST_CHANGED_AFTER_FAIL:{f}"]
    r = gate(ws, "SWE.6", "author", b'{"status":"PASS","artifacts":[],"issues":[],"next_action":"next"}')
    assert r.returncode != 0 and b"TEST_CHANGED_AFTER_FAIL" in r.stdout
    D.report(ws, detected_phase="SWE.6", reported_by="swe6-author", kind="TEST", summary="expected HAL_ERROR from a "
             "timeout-only API; scenario now drives SWR-014 through the invalid-timeout path", requirement_ids=["SWR-014"],
             test_files=[f], evidence_refs=[], requirement_quote="shall return HAL_ERROR without any register write")
    assert D.bent_tests(ws, "SWE.6") == []  # declared -> visible in the package for the inspector and the human


def test_test_change_after_code_fix_or_unchanged_test_is_not_bending(ws):
    f = "software/tests/unit/test_rcc.c"
    _run(ws, "SWE.4", "run_unit", "FAIL", "2026-10-15T10:00:00Z", "C1", {f: "h1"}, [f])
    _run(ws, "SWE.4", "run_unit", "PASS", "2026-10-15T11:00:00Z", "C2", {f: "h2"}, [])  # code changed (upstream fix)
    assert D.bent_tests(ws, "SWE.4") == []
    _run(ws, "SWE.5", "run_renode", "FAIL", "2026-10-15T10:00:00Z", "C1", {f: "h1"}, [f])
    _run(ws, "SWE.5", "run_renode", "PASS", "2026-10-15T11:00:00Z", "C1", {f: "h1"}, [])  # flaky/infra, test same
    assert D.bent_tests(ws, "SWE.5") == []


def test_test_tools_record_runtime_failures_not_build_errors(ws):
    out = D.integrity(ws, [ws / "software/tests/software/scn_invalid_param.c"], [])
    assert out["assert_failed"] == [] and "software/tests/software/scn_invalid_param.c" in out["files"]
    before = out["code_sha"]
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text("int x;\nint z;\n")
    assert D.code_hash(ws) != before


def test_regmap_regeneration_on_reentry_keeps_authored_ll_functions(tmp_path, monkeypatch):
    from forge_factory.inspection import regmap

    hdr = tmp_path / regmap.LL_HEADER
    hdr.parent.mkdir(parents=True)
    authored = "\nstatic inline void LL_RCC_HSI_Enable(void) { }\n\n"
    hdr.write_text(f"/* old defines */\n{regmap.FUNCTIONS_MARKER}{authored}#endif /* {regmap.GUARD} */\n")
    monkeypatch.setattr(regmap, "architecture_registers", lambda ws: ["RCC_CR"])  # isolate from SWE.2 inputs
    monkeypatch.setattr(regmap, "rm_registers", lambda ws: {"RCC_CR": {
        "name": "RCC_CR", "offset": 0, "fields": {"HSION": (3, 3)}, "source": "inputs/14.10.1_rcc_cr.md",
        "sha256": "x"}})
    assert regmap.generate(tmp_path)["status"] == "PASS"
    text = hdr.read_text()
    assert "LL_RCC_CR_HSION_MSK" in text and "/* old defines */" not in text
    assert text.count("LL_RCC_HSI_Enable") == 1 and text.rstrip().endswith(f"#endif /* {regmap.GUARD} */")


def test_agents_cannot_write_defect_register_or_integrity_evidence(tmp_path):
    from forge_factory.policy.authz import Authorizer, Binding

    a = Authorizer(Binding("b", str(tmp_path), {"a6": {"role": "swe6-author", "phase": "SWE.6"},
                                                "a3": {"role": "swe3-author", "phase": "SWE.3"}}))
    for node in ("a6", "a3"):
        for rel in (".forge-run/defects/DEF-001.json", "evidence/test-integrity.jsonl",
                    ".forge-run/gates/upstream-loops.jsonl"):
            assert not a.decide(node, "write_file", {"file_path": rel, "content": "x"}).allow, (node, rel)


def test_same_open_defect_reported_twice_is_one_defect_r66(ws):
    tool(ws, "SWE.6", "run_robot", "FAIL")
    a, b = code_defect(ws), code_defect(ws)
    assert a["id"] == b["id"] == "DEF-001" and len(D.all_defects(ws)) == 1


def test_carried_over_inspection_failures_do_not_consume_this_runs_budget_r66(ws):
    s = Store(ws)
    (ws / "inspection/SWE.5").mkdir(parents=True)
    (ws / "inspection/SWE.5/INS-SWE.5-001.json").write_text(json.dumps(
        {"verdict": "FAIL", "recorded_at": "2026-10-15T13:12:15Z", "baseline_hash": "x"}))  # from the source run
    (ws / ".forge-run").mkdir(exist_ok=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"created_at": "2026-10-15T16:58:08Z"}))
    assert s.gate("SWE.5")["failed_inspections"] == 0
    (ws / "inspection/SWE.5/INS-SWE.5-002.json").write_text(json.dumps(
        {"verdict": "FAIL", "recorded_at": "2026-10-15T17:10:00Z", "baseline_hash": "y"}))
    assert s.gate("SWE.5")["failed_inspections"] == 1


# ---- per-epoch rework budget and route-gate safety net (owner decisions 2026-10-15) ----------------------------
SCN_OK = "TCHECK(9, rc == HAL_ERROR);\n"
SUITE = "*** Test Cases ***\nSWR-014\n    [Tags]    SWR-014\n    Run Target Scenario    scn_invalid_param.c\n"


def _robot_run(ws, files, failed_checks, unobserved=(), status="FAIL"):
    """What run_robot records: tool result + integrity record (with snapshots of the files as they ran)."""
    for rel, txt in files.items():
        (ws / rel).write_text(txt)
    tool(ws, "SWE.6", "run_robot", status, ts=D.utc_now())
    paths = [ws / "software/tests/software/test_rcc_requirements.robot", ws / "software/tests/software/scn_invalid_param.c"]
    D.record_integrity(ws, "SWE.6", "run_robot", status, {**D.integrity(ws, paths, []), "failed_checks": failed_checks,
                                                          "build_failed": [], "unobserved": list(unobserved)})


def _check(expr, observes=("HAL_ERROR",), call=True, cid="9"):
    return {"requirements": ["SWR-014"], "scenario": "scn_invalid_param.c", "check": cid, "expr": expr,
            "observes": list(observes), "driver_call": call}


def test_upstream_loop_starts_a_fresh_rework_epoch(ws):
    for _ in range(2):
        assert gate(ws, "SWE.4", "route").returncode == 0
    assert gate(ws, "SWE.4", "route").returncode == 1  # 3rd failed cycle -> BLOCKED
    (ws / D.LOOPS).parent.mkdir(parents=True, exist_ok=True)
    (ws / D.LOOPS).write_text(json.dumps({"ts": D.utc_now(), "target": "SWE.3", "defects": ["DEF-001"]}) + "\n")
    assert Store(ws).budget_start() > "2026"
    for _ in range(2):  # after the upstream fix the downstream phase has its authored maximum again
        assert gate(ws, "SWE.4", "route").returncode == 0
    assert gate(ws, "SWE.4", "route").returncode == 1


def test_safety_net_files_code_defect_from_evidence_and_restores_the_failing_test_r69(ws):
    scn = "software/tests/software/scn_invalid_param.c"
    suite = "software/tests/software/test_rcc_requirements.robot"
    original = "rc = HAL_RCC_HSI_Enable(0U);\n" + SCN_OK
    _robot_run(ws, {suite: SUITE, scn: original},
               [_check("rc == HAL_ERROR with rc = HAL_RCC_HSI_Enable(0U)")])
    # r69: the author bent the check (no longer observes HAL_ERROR, requirement reported unobserved) and never reported
    _robot_run(ws, {scn: "TCHECK(12, (ll_rcc_regs[0] & LL_RCC_CR_HSEON_MSK) == 0U);\n"},
               [_check("(ll_rcc_regs[0] & LL_RCC_CR_HSEON_MSK) == 0U", (), False, "12")], unobserved=["SWR-014"])
    assert gate(ws, "SWE.6", "route").returncode == 0 and gate(ws, "SWE.6", "route").returncode == 0
    r = gate(ws, "SWE.6", "route")  # budget exhausted: the gate files the defect instead of BLOCKING
    assert r.returncode == 1 and b"UPSTREAM" in r.stdout and b"DEF-001->SWE.3" in r.stdout, r.stdout
    d = D.all_defects(ws)[0]
    assert (d["kind"], d["reported_by"], d["status"], d["requirement_ids"]) == ("CODE", "route-gate", "OPEN", ["SWR-014"])
    assert "rc == HAL_ERROR with rc = HAL_RCC_HSI_Enable(0U)" in d["summary"]
    assert (ws / scn).read_text() == original and d["auto_filed"]["restored_test_files"] == [scn]
    assert set(d["test_files"]) == {scn, suite}  # the fix is verified with exactly the test that failed
    assert D.verify_on_freeze(ws, "SWE.6") == []
    assert "open_defect:DEF-001:CODE:OPEN:gate-filed" in D.gaps(ws)
    # SWE.3 rejects it with a reason -> the same tests are never filed again
    D.take_upstream(ws, "SWE.3")
    D.reject(ws, "DEF-001", "swe3-author", "HAL_RCC_HSI_Enable has no invalid parameter; the scenario is wrong")
    assert D.auto_code_defect(ws, "SWE.6", "") is None and len(D.all_defects(ws)) == 1


def test_safety_net_never_blames_code_without_a_driver_check_that_observes_the_requirement(ws):
    scn = "software/tests/software/scn_invalid_param.c"
    suite = "software/tests/software/test_rcc_requirements.robot"
    base = {suite: SUITE, scn: SCN_OK}
    _robot_run(ws, base, [_check("rc == HAL_OK", observes=())])  # check does not test what SWR-014 names
    assert D.auto_code_defect(ws, "SWE.6", "") is None
    _robot_run(ws, base, [_check("(ll_rcc_regs[0] & 1U) == 0U", call=False)])  # no call into the driver
    assert D.auto_code_defect(ws, "SWE.6", "") is None
    _robot_run(ws, base, [_check("rc == HAL_ERROR"), _check("rc == HAL_OK", observes=(), cid="3")])  # mixed failures
    assert D.auto_code_defect(ws, "SWE.6", "") is None
    _robot_run(ws, base, [_check("rc == HAL_ERROR with rc = HAL_RCC_HSI_Enable(0U)")])
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text("int x;\nint fixed;\n")  # code changed since: rerun first
    assert D.auto_code_defect(ws, "SWE.6", "") is None
    for _ in range(3):
        r = gate(ws, "SWE.6", "route")
    assert r.returncode == 1 and b"BLOCKED" in (ws / ".forge-run/gates/gate-log.jsonl").read_bytes()
    assert D.all_defects(ws) == []


# ---- L12 triage: a fully rejected loop returns to the reporter without re-freezing upstream (r70) -------------
def _triage_setup(ws, monkeypatch, intact=True):
    from forge_factory.inspection import gate as G

    monkeypatch.setattr(Store, "latest_baseline", lambda self, p: {"baseline_id": "BL", "frozen_at": "x"})
    monkeypatch.setattr(Store, "stale_reason", lambda self, p, bl: None if intact else "BASELINE_CHANGED_AFTER_FREEZE")
    tool(ws, "SWE.6", "run_robot", "FAIL")
    code_defect(ws)
    assert D.take_upstream(ws, "SWE.3")
    return G


def test_triage_rejecting_every_defect_returns_to_the_reporting_phase(ws, monkeypatch):
    G = _triage_setup(ws, monkeypatch)
    assert G.step_triage(Store(ws), "SWE.3") == 0  # nothing rejected yet -> owner's fix step
    D.reject(ws, "DEF-001", "swe3-author", "SWR-014 as written is met; the scenario passes an allowed timeout")
    assert G.step_triage(Store(ws), "SWE.3") == 1  # -> return chain, nothing re-frozen upstream
    assert [G.step_return(Store(ws), f"SWE.{n}") for n in range(2, 7)] == [1, 1, 1, 1, 0]  # back to SWE.6


def test_triage_that_edited_the_owner_baseline_goes_through_the_fix_step(ws, monkeypatch):
    G = _triage_setup(ws, monkeypatch, intact=False)
    D.reject(ws, "DEF-001", "swe3-author", "SWR-014 as written is met; the scenario passes an allowed timeout")
    assert G.step_triage(Store(ws), "SWE.3") == 0  # the changed work product must be re-frozen and inspected
    assert G.step_return(Store(ws), "SWE.4") == 1


def test_partially_rejected_loop_is_fixed_by_the_owner(ws, monkeypatch):
    G = _triage_setup(ws, monkeypatch)
    tool(ws, "SWE.6", "run_robot", "FAIL", ts="2026-10-15T11:00:00Z")
    D.report(ws, detected_phase="SWE.6", reported_by="swe6-author", kind="CODE", summary="no HAL_TIMEOUT on wait",
             requirement_ids=["SWR-013"], test_files=["software/tests/software/scn_invalid_param.c"], evidence_refs=[],
             requirement_quote="the RCC driver shall return HAL_TIMEOUT")
    assert [d["id"] for d in D.take_upstream(ws, "SWE.3")] == ["DEF-002"]
    D.reject(ws, "DEF-002", "swe3-author", "HAL_TIMEOUT is returned; the scenario never waits")
    assert G.step_triage(Store(ws), "SWE.3") == 1  # latest loop (DEF-002) fully rejected
    assert D.all_defects(ws)[0]["status"] == "IN_FIX"  # the earlier loop's defect stays with the owner


# ---- L13 gate-declared adaptation of a test to an upstream fix (owner decision 2026-10-15, r71) ---------------
def _fixed_code_defect(ws):
    tool(ws, "SWE.6", "run_robot", "FAIL")
    code_defect(ws)
    D.take_upstream(ws, "SWE.3")
    D.mark_fixed(ws, "SWE.3", "BL-SWE.3-002")  # FIXED now, between the runs below


def test_test_adapted_after_an_upstream_fix_is_declared_by_the_gate_r71(ws):
    f = "software/tests/integration/test_rcc_integration.c"
    (ws / f).parent.mkdir(parents=True)
    (ws / f).write_text("/* IT-017 adapted */\n")
    _fixed_code_defect(ws)
    _run(ws, "SWE.5", "run_integration", "PASS", "2000-01-01T00:00:00Z", "C-old", {f: "h1"}, [])  # pre-fix code
    _run(ws, "SWE.5", "run_integration", "FAIL", D.utc_now(), "C-fix", {f: "h1"}, [f])  # same test fails
    _run(ws, "SWE.5", "run_integration", "PASS", D.utc_now(), "C-fix", {f: "h2"}, [])  # adapted
    assert D.bent_tests(ws, "SWE.5") == [f"TEST_CHANGED_AFTER_FAIL:{f}"]
    [rec] = D.declare_post_fix_adaptations(ws, "SWE.5")
    assert (rec["kind"], rec["status"], rec["reported_by"]) == ("TEST", "DECLARED", "route-gate")
    assert rec["gate_declared"]["fix_defect"] == "DEF-001" and rec["requirement_ids"] == ["SWR-014"]
    assert D.bent_tests(ws, "SWE.5") == [] and D.gaps(ws) == ["open_defect:DEF-001:CODE:FIXED"]
    assert any(x.startswith(f"{rec['id']} TEST DECLARED (SWE.5)") for x in D.review_items(ws))


def test_test_that_never_passed_before_the_fix_is_still_bending(ws):
    f = "software/tests/integration/test_rcc_integration.c"
    (ws / f).parent.mkdir(parents=True)
    (ws / f).write_text("/* rewritten */\n")
    _fixed_code_defect(ws)
    _run(ws, "SWE.5", "run_integration", "PASS", "2000-01-01T00:00:00Z", "C-old", {f: "h0"}, [])  # other content
    _run(ws, "SWE.5", "run_integration", "FAIL", D.utc_now(), "C-fix", {f: "h1"}, [f])
    _run(ws, "SWE.5", "run_integration", "PASS", D.utc_now(), "C-fix", {f: "h2"}, [])
    assert D.declare_post_fix_adaptations(ws, "SWE.5") == []
    assert D.bent_tests(ws, "SWE.5") == [f"TEST_CHANGED_AFTER_FAIL:{f}"]


# ---- L14 a TEST declaration covers later corrections on the same product code (owner decision 2026-10-16, r72) --
def _declare(ws, f):
    return D.report(ws, detected_phase="SWE.6", reported_by="swe6-author", kind="TEST", summary="SWR-014 scenario "
                    "drove a timeout, not an invalid parameter", requirement_ids=["SWR-014"], test_files=[f],
                    evidence_refs=[], requirement_quote="shall return HAL_ERROR without any register write")


def test_declaration_covers_later_corrections_while_the_code_is_unchanged_r72(ws):
    """r72: declared at 21:22, the scenario failed and was corrected six more times on the same code; 18/18 rejected."""
    f, c = "software/tests/software/scn_invalid_param.c", D.code_hash(ws)
    _run(ws, "SWE.6", "run_robot", "FAIL", "2026-10-15T10:00:00Z", c, {f: "h1"}, [f])
    rec = _declare(ws, f)
    assert rec["code_sha"] == c
    _run(ws, "SWE.6", "run_robot", "FAIL", D.utc_now(), c, {f: "h2"}, [f])  # failed again after the declaration
    _run(ws, "SWE.6", "run_robot", "FAIL", D.utc_now(), c, {f: "h3"}, [f])
    _run(ws, "SWE.6", "run_robot", "PASS", D.utc_now(), c, {f: "h4"}, [])
    assert D.bent_tests(ws, "SWE.6") == []


def test_declaration_does_not_cover_corrections_after_the_code_changed(ws):
    f, c = "software/tests/software/scn_invalid_param.c", D.code_hash(ws)
    _run(ws, "SWE.6", "run_robot", "FAIL", "2026-10-15T10:00:00Z", c, {f: "h1"}, [f])
    _declare(ws, f)
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text("int x;\nint z;\n")  # upstream fix after the declaration
    c2 = D.code_hash(ws)
    _run(ws, "SWE.6", "run_robot", "FAIL", D.utc_now(), c2, {f: "h2"}, [f])
    _run(ws, "SWE.6", "run_robot", "PASS", D.utc_now(), c2, {f: "h3"}, [])
    assert D.bent_tests(ws, "SWE.6") == [f"TEST_CHANGED_AFTER_FAIL:{f}"]
    _declare(ws, f)  # declared again against the fixed code
    assert D.bent_tests(ws, "SWE.6") == []


def test_legacy_declaration_without_code_hash_uses_the_preceding_run(ws):
    f = "software/tests/software/scn_invalid_param.c"
    _run(ws, "SWE.6", "run_robot", "FAIL", "2026-10-15T10:00:00Z", "C1", {f: "h1"}, [f])
    rec = _declare(ws, f)
    rec.pop("code_sha")
    (D._dir(ws) / f"{rec['id']}.json").write_text(json.dumps(rec))
    _run(ws, "SWE.6", "run_robot", "FAIL", D.utc_now(), "C1", {f: "h2"}, [f])
    _run(ws, "SWE.6", "run_robot", "PASS", D.utc_now(), "C1", {f: "h3"}, [])
    assert D.bent_tests(ws, "SWE.6") == []
