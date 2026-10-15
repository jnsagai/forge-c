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
    arch = D.report(ws, detected_phase="SWE.6", reported_by="r", kind="ARCHITECTURE", summary="timeout-only API "
                    "cannot express an invalid parameter", requirement_ids=["SWR-014"], test_files=[], evidence_refs=[])
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
