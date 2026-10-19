"""EASA wiring found by the first end-to-end pilot (r122): live inspection records, SWR resource budgets against
measured results, fidelity labels of SWE.5/6 reports, requirement-derived negative/boundary arguments."""
import json

from forge_factory.assurance import observe
from forge_factory.assurance import verifiers as V

REQS = ("- **SWR-001** When the HSE enable is requested, the RCC driver shall set RCC_CR.HSEON.\n"
        "- **SWR-023** The RCC LL driver shall use no more than 4096 bytes of code and constant data.\n"
        "- **SWR-024** The RCC LL driver shall use no more than 64 bytes of static RAM.\n"
        "- **SWR-025** The RCC LL driver shall use at most 128 bytes of stack per call.\n")


def _ws(tmp_path, layer="LL"):
    ws = tmp_path / "WO" / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": layer}))
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQS)
    (ws / "evidence").mkdir()
    return ws


def _results(ws, *recs):
    with (ws / "evidence/tool-results.jsonl").open("a") as f:
        for op, res in recs:
            f.write(json.dumps({"op": op, "phase": "SWE.3", "result": res}) + "\n")


def test_live_inspection_record_is_the_latest_ins_file(tmp_path):
    ws = _ws(tmp_path)
    d = ws / "inspection/SWE.4"
    d.mkdir(parents=True)
    (d / "INS-SWE.4-009.json").write_text(json.dumps({"verdict": "FAIL"}))
    (d / "INS-SWE.4-010.json").write_text(json.dumps({"verdict": "PASS"}))
    assert observe.evidence_map(ws, "SWE.4")["INDEPENDENT_INSPECTION"][0]["status"] == "PASS"   # 010 > 009


def test_resource_budgets_from_swrs_against_measured_results(tmp_path):
    ws = _ws(tmp_path)
    assert V.budgets_from_requirements(ws)[0] == {"flash_bytes": 4096, "static_ram_bytes": 64, "stack_bytes": 128}
    assert V.v_resource_budgets(ws)["status"] == "NOT_SUPPORTED"                      # nothing measured: never PASS
    _results(ws, ("measure_elf", {"status": "PASS", "metrics": {"flash_bytes": 300, "ram_bytes": 0}}),
             ("stack_usage", {"status": "PASS", "metrics": {"max_frame_bytes": 16}}))
    assert V.v_resource_budgets(ws)["status"] == "PASS"
    _results(ws, ("measure_elf", {"status": "PASS", "metrics": {"flash_bytes": 5000, "ram_bytes": 0}}))
    r = V.v_resource_budgets(ws)
    assert r["status"] == "FAIL" and "BUDGET_EXCEEDED:flash_bytes:5000>4096:SWR-023" in r["findings"]


def test_fidelity_label_and_escalation(tmp_path):
    ws = _ws(tmp_path)
    assert V.v_fidelity(ws, "SWE.5")["status"] == "NOT_SUPPORTED"
    _results(ws, ("run_renode", {"status": "PASS"}))
    rep = ws / "workproducts/SWE.5/integration_verification_report.md"
    rep.parent.mkdir(parents=True)
    rep.write_text("All integration tests passed.\n")
    assert V.v_fidelity(ws, "SWE.5")["findings"][0].startswith("FIDELITY_LABEL_MISSING")
    rep.write_text("Executed on the Renode behavioural model. Not verified on silicon; HIL is not available.\n")
    assert V.v_fidelity(ws, "SWE.5")["status"] == "PASS"
    rep.write_text("Executed on Renode. The oscillator start-up was verified on the real silicon board.\n")
    r = V.v_fidelity(ws, "SWE.5")
    assert r["status"] == "FAIL" and any(x.startswith("FIDELITY_ESCALATION:HIL") for x in r["findings"])


def test_negative_boundary_cases_hal_and_ll(tmp_path):
    assert V.v_negative_boundary(_ws(tmp_path))["status"] == "NOT_APPLICABLE"
    ws = _ws(tmp_path / "h", "HAL")
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        REQS + "- **SWR-014** When an invalid parameter is passed, the RCC HAL driver shall return HAL_ERROR without any "
               "register write; a timeout argument of 0 or greater than HAL_RCC_TIMEOUT_VALUE is invalid.\n")
    (ws / "software/hal").mkdir(parents=True)
    (ws / "software/hal/stm32n6xx_hal_rcc.h").write_text("hal_status_t HAL_RCC_HSE_Enable(uint32_t timeout);\n")
    from tests_easa_rm import CCR, CR, CSR, SR

    sec = ws / "inputs/sections/RM0486"
    sec.mkdir(parents=True)
    for name, text in (("cr.md", CR), ("sr.md", SR), ("csr.md", CSR), ("ccr.md", CCR)):
        (sec / name).write_text(text)
    t = ws / "software/tests/unit/test_rcc.c"
    t.parent.mkdir(parents=True)
    t.write_text("HAL_RCC_HSE_Enable(0U); HAL_RCC_HSE_Enable(HAL_RCC_TIMEOUT_VALUE + 1U); HAL_RCC_HSE_Enable(1U);\n")
    r = V.v_negative_boundary(ws)
    assert r["status"] == "FAIL" and r["findings"][0] == "BOUNDARY_NOT_EXERCISED:HAL_RCC_HSE_Enable(HAL_RCC_TIMEOUT_VALUE)"
    t.write_text(t.read_text() + "HAL_RCC_HSE_Enable(HAL_RCC_TIMEOUT_VALUE);\n")
    assert V.v_negative_boundary(ws)["status"] == "PASS"
