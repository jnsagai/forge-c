"""EASA M5: mutation campaign (AT-044/047/075), measured coverage incl. MC/DC (AT-042/043/045), RM-derived oracles
(AT-040/041) on a small synthetic driver built with the real toolchain."""
import shutil

import pytest
from forge_factory.assurance import coverage, mutation, oracle_gen
from tests_easa_rm import idx_from

needs_cc = pytest.mark.skipif(not (shutil.which("gcc") and shutil.which("clang") and shutil.which("llvm-cov")),
                              reason="toolchain not installed")
LL = """#include <stdint.h>
#define LL_RCC_REG_COUNT 1024U
extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];
#define LL_RCC_CR_OFFSET 0x000U
#define LL_RCC_SR_OFFSET 0x004U
#define LL_RCC_CR_HSION_MSK 0x00000008U
#define LL_RCC_CR_HSEON_MSK 0x00000010U
#define LL_RCC_SR_HSIRDY_MSK 0x00000008U
static inline void LL_RCC_HSI_Enable(void)
{
  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSION_MSK;
}

static inline void LL_RCC_HSI_Disable(void)
{
  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] &= ~LL_RCC_CR_HSION_MSK;
}

static inline uint32_t LL_RCC_HSI_IsReady(void)
{
  return ((ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] & LL_RCC_SR_HSIRDY_MSK) != 0U) ? 1U : 0U;
}
"""
UT = """#include <stdio.h>
#include "stm32n6xx_ll_rcc.h"
volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];
static int failures;
#define CHECK(id, c) do { if (c) { printf("%s PASS\\n", id); } else { printf("%s FAIL\\n", id); failures++; } } while (0)
int main(void)
{
    LL_RCC_HSI_Enable();
    CHECK("UT-001", (ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) != 0U);
    LL_RCC_HSI_Disable();
    CHECK("UT-002", (ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) == 0U);
    ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] = LL_RCC_SR_HSIRDY_MSK;
    CHECK("UT-003", (LL_RCC_HSI_IsReady() == 1U) && (ll_rcc_regs[0] == 0U || 1));
    return failures ? 1 : 0;
}
"""


@pytest.fixture
def sw(tmp_path):
    d = tmp_path / "sw"
    (d / "ll").mkdir(parents=True)
    (d / "ll/stm32n6xx_ll_rcc.h").write_text(LL)
    (d / "tests").mkdir()
    (d / "tests/test_rcc.c").write_text(UT)
    return d


@needs_cc
def test_at044_campaign_populations_ids_and_shared_oracle_survivors(sw):
    used = {"LL_RCC_HSI_Enable", "LL_RCC_HSI_Disable", "LL_RCC_HSI_IsReady"}
    c = mutation.run_campaign(sw, "ll/stm32n6xx_ll_rcc.h", [sw / "tests/test_rcc.c"], used_symbols=used)
    r = c["record"]
    assert c["schema_issues"] == [] and mutation.validate_campaign(r) == []
    assert r["killed"] > 0 and r["survived"] > 0 and len(r["mutant_refs"]) == len(set(r["mutant_refs"]))
    surv = {m["original"] for m in c["mutants"] if m["outcome"] == "SURVIVED"}
    assert "#define LL_RCC_CR_HSION_MSK 0x00000008U" in surv          # the test shares the macro: oracle cannot see it
    eq = [m for m in c["mutants"] if m["outcome"] == "EQUIVALENT"]
    assert all("HSEON" in m["original"] for m in eq) and eq              # only the truly unreferenced definition
    again = mutation.run_campaign(sw, "ll/stm32n6xx_ll_rcc.h", [sw / "tests/test_rcc.c"], used_symbols=used)
    assert again["record"]["mutant_refs"] == r["mutant_refs"]            # deterministic ids


def test_at075_score_without_mutant_ids_rejected():
    rec = {"campaign_id": "MC-x", "code_hash": "c" * 64, "operator_set": ["x"], "eligible": 10, "killed": 9, "survived": 1,
           "equivalent": 0, "invalid": 0, "mutant_refs": [], "tool_version": "t", "result": "MEASURED"}
    assert "MUTATION_SCORE_WITHOUT_MUTANT_IDS" in mutation.validate_campaign(rec)
    assert "SCORE_FIELD_NOT_ALLOWED:score" in mutation.validate_campaign({**rec, "score": 0.9})
    bad = {**rec, "mutant_refs": ["MUT-1", "MUT-2"]}
    assert "MUTANT_POPULATION_MISMATCH:10!=2" in mutation.validate_campaign(bad)


def test_at047_survivor_blocks_adequacy_until_human_review():
    camp = {"mutants": [{"id": "MUT-a", "outcome": "KILLED"}, {"id": "MUT-b", "outcome": "SURVIVED"}]}
    c = mutation.adequacy_claim(camp)
    assert c["status"] == "UNSUPPORTED" and c["survivors_open"] == ["MUT-b"] and c["killed_provenance"] == ["MUT-a"]
    assert mutation.adequacy_claim(camp, {"MUT-b": "agent-swe4"})["status"] == "UNSUPPORTED"
    assert mutation.adequacy_claim(camp, {"MUT-b": "j.doe"})["status"] == "SUPPORTED"


@needs_cc
def test_at045_mcdc_measured_or_not_supported_never_fabricated(sw, tmp_path):
    src = tmp_path / "f.c"
    src.write_text('#include "stm32n6xx_ll_rcc.h"\nint f(int a, int b) { return (a && b) ? 1 : 0; }\n')
    t = tmp_path / "t.c"
    t.write_text('#include <stdio.h>\n#include "stm32n6xx_ll_rcc.h"\nvolatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];\n'
                 "int f(int, int);\nint main(void) { printf(\"%d\\n\", f(1, 1) + f(0, 1)); return 0; }\n")
    r = coverage.measure([src], t, [sw / "ll"])
    k = {x["kind"]: x for x in r["records"]}
    assert k["STATEMENT"]["status"] == "MEASURED" and k["BRANCH"]["status"] == "MEASURED"
    assert k["MCDC"]["status"] == "MEASURED" and k["MCDC"]["covered"] < k["MCDC"]["total"]   # b never independent
    no = coverage.measure([src], t, [sw / "ll"], mcdc=False)
    m = {x["kind"]: x for x in no["records"]}["MCDC"]
    assert m["status"] == "NOT_SUPPORTED" and m["covered"] is None and m["total"] is None and m["schema_issues"] == []


def test_at043_statement_only_is_missing_branch_evidence():
    st = {"kind": "STATEMENT", "status": "MEASURED", "covered": 10, "total": 10}
    assert coverage.missing_branch_evidence([st]) == ["BRANCH_EVIDENCE_MISSING"]
    br = {"kind": "BRANCH", "status": "NOT_COMPUTABLE", "covered": 4}
    assert coverage.missing_branch_evidence([st, br]) == ["BRANCH_EVIDENCE_MISSING", "FABRICATED_BRANCH_NUMBER"]


def test_at042_stub_and_unexecuted_api():
    test_text = "hal_status_t HAL_RCC_HSI_Enable(uint32_t t)\n{\n    return HAL_OK;\n}\nint main(void) { return 0; }\n"
    f = coverage.api_execution({"HAL_RCC_HSI_Disable": 0}, ["HAL_RCC_HSI_Enable", "HAL_RCC_HSI_Disable"], test_text)
    assert f == ["STUB_SHADOWS_API:HAL_RCC_HSI_Enable", "API_NOT_EXECUTED:HAL_RCC_HSI_Disable"]


REQS = """- **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION.
- **SWR-002** When the HSI disable is requested, the RCC driver shall clear RCC_CR.HSION.
"""
ARCH = "| SWR | Function |\n|---|---|\n| SWR-001 | LL_RCC_HSI_Enable |\n| SWR-002 | LL_RCC_HSI_Disable |\n"


@needs_cc
def test_at040_rm_derived_oracle_independent_and_catches_wrong_bit(sw, tmp_path):
    idx = idx_from(tmp_path)
    cases, notes = oracle_gen.derive(REQS, ARCH, LL, idx)
    assert [(c["swr"], c["function"], c["mask"]) for c in cases] == [("SWR-001", "LL_RCC_HSI_Enable", 8),
                                                                     ("SWR-002", "LL_RCC_HSI_Disable", 8)] and notes == []
    ws = tmp_path / "WO" / "workspace"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQS)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
    shutil.copytree(tmp_path / "sections", ws / "inputs/sections/RM0486")
    ok = oracle_gen.run(ws, [sw / "ll"], [], "stm32n6xx_ll_rcc.h")
    assert ok["status"] == "PASS" and ok["provenance"]["independence_status"] == "INDEPENDENT"
    assert len(ok["provenance"]["source_digests"]) >= 2                # requirements + RM section of RCC_CR
    (sw / "ll/stm32n6xx_ll_rcc.h").write_text(LL.replace("#define LL_RCC_CR_HSION_MSK 0x00000008U",
                                                         "#define LL_RCC_CR_HSION_MSK 0x00000010U"))
    bad = oracle_gen.run(ws, [sw / "ll"], [], "stm32n6xx_ll_rcc.h")
    assert bad["status"] == "FAIL" and {r[3] for r in bad["results"]} == {"FAIL"}
