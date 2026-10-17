"""EASA M4: coding policy, MISRA inventory/deviations, seeded analyzer probes, invariants, resources, formal adapter."""
import shutil

import pytest
from forge_factory.assurance import catalog, swe3
from tests_easa_rm import HDR, idx_from  # noqa: F401  (shared synthetic RM fixture)


def test_t032_policy_maps_table1_table6_without_misra_claim():
    pol = swe3.coding_policy(catalog.load())
    assert len(pol) == 14 and {p["method_id"][:8] for p in pol} == {"ISO6-T01", "ISO6-T06"}
    assert all(p["misra_compliance"] == "NOT_CLAIMED" for p in pol)
    assert [p["method_id"] for p in pol if p["resolution"] == "CONTROLLED_REVIEW"] == ["ISO6-T01-1F"]


def test_t036_misra_inventory_is_measured_and_partial():
    from forge_factory.mcp.servers.analysis import MISRA_RULES

    inv = swe3.misra_inventory(MISRA_RULES)
    if inv["status"] == "NOT_SUPPORTED":
        pytest.skip("cppcheck MISRA addon absent")
    assert inv["misra_compliance"] == "NOT_CLAIMED" and 0 < inv["covered"] < inv["standard_rules"]
    assert inv["covered"] + len(inv["unsupported"]) == inv["standard_rules"]


def test_t036_suppressions_need_human_approved_deviation():
    code = {"hal.c": "int a; /* cppcheck-suppress misra-c2012-15.5 */\n#pragma GCC diagnostic ignored \"-Wconversion\"\n"}
    f = swe3.deviation_findings(code, [])
    assert f == ["UNAPPROVED_SUPPRESSION:hal.c:1", "UNAPPROVED_SUPPRESSION:hal.c:2"]
    ok = [{"rule": "15.5", "file": "hal.c", "rationale": "early return keeps the timeout path readable",
           "approved_by": "j.doe"}]
    assert swe3.deviation_findings(code, ok) == ["UNAPPROVED_SUPPRESSION:hal.c:2"]
    assert "DEVIATION_NOT_HUMAN_APPROVED:15.5" in swe3.deviation_findings(code, [{**ok[0], "approved_by": "agent-swe3"}])


@pytest.mark.skipif(not (shutil.which("clang") and shutil.which("cppcheck")), reason="analyzers not installed")
def test_t034_t039_seeded_defects_caught_by_real_analyzers_and_gaps_recorded():
    rows = {r["probe"]: r for r in swe3.seeded_probe_campaign()}
    assert all(r["status"] == "CAUGHT" for r in rows.values())
    assert rows["uninitialized_use"]["caught_by"] == ["clang-analyzer", "clang-warn"]
    assert rows["null_dereference"]["caught_by"] == ["clang-analyzer"]
    assert "cppcheck-misra" in rows["goto_use"]["missed_by"]          # measured tool limitation, kept visible


def test_at039_fabricated_api():
    hdr = "static inline void LL_RCC_HSI_Enable(void)\n{\n}\n"
    code = "void f(void)\n{\n    LL_RCC_HSI_Enable();\n    LL_RCC_HSI_Calibrate();\n}\n"
    assert swe3.fabricated_calls(code, hdr) == ["FABRICATED_API:LL_RCC_HSI_Calibrate"]


def test_t035_at036_invariants_race_loop_reentrancy(tmp_path):
    idx = idx_from(tmp_path)
    code = {"hal.c": "static uint32_t calls;\n"
                     "void a(void)\n{\n    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSION_MSK;\n"
                     "    while (LL_RCC_HSI_IsReady() == 0U)\n    {\n    }\n}\n"
                     "void b(void)\n{\n    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSEON_MSK;\n"
                     "    for (i = 0U; (LL_RCC_HSE_IsReady() == 0U) && (i < 1000U); i++)\n    {\n    }\n}\n"}
    f = swe3.invariant_findings(code, HDR, idx, mitigation_stated=False)
    assert "SHARED_REGISTER_RACE_UNMITIGATED:RCC_CR:a,b" in f
    assert "LOOP_UNBOUNDED:a@hal.c" in f and not any(x.startswith("LOOP_UNBOUNDED:b") for x in f)
    assert "REENTRANCY_STATE:calls@hal.c" in f
    assert not any(x.startswith("SHARED_REGISTER_RACE") for x in swe3.invariant_findings(code, HDR, idx, True))


def test_t037_resources_tagged_measured_or_unknown():
    me = {"status": "PASS", "metrics": {"flash_bytes": 428, "ram_bytes": 0}}
    rows = {r["metric"]: r for r in swe3.resource_evidence({"measure_elf": me, "stack_usage": None},
                                                         {"flash_bytes": 4096, "static_ram_bytes": 64, "stack_bytes": 128})}
    assert rows["flash_bytes"]["provenance"] == "MEASURED" and rows["flash_bytes"]["within_budget"] is True
    assert rows["stack_bytes"]["provenance"] == "UNKNOWN" and rows["stack_bytes"]["value"] is None
    assert rows["execution_time"]["provenance"] == "UNKNOWN"


def test_t038_formal_adapter_reports_not_supported_without_cbmc(tmp_path, monkeypatch):
    monkeypatch.setattr(swe3, "cbmc_bin", lambda: None)
    r = swe3.bounded_proof(tmp_path / "h.c", [])
    assert r["status"] == "NOT_SUPPORTED" and r["claims"] == []
