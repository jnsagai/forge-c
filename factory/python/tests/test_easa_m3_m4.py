"""EASA M3 (SWE.1/SWE.2 stronger validation) and M4 hardware semantics: independent RM index, register-write checks,
simulator fidelity, requirement quality/source/contradictions, trace round trip, owner freeze, architecture graph."""
import json

import pytest
from forge_factory.assurance import hardware as H
from forge_factory.assurance import impact, swe12
from forge_factory.assurance.store import AssuranceStore
from forge_factory.common import state_dir

COLS = (" 15      14       13     12      11     10      9       8       7      6       5      4       3       2      1        0")
CR = f"""<!-- source: RM0486 section 14.10.1 starting p.479 -->
#### 14.10.1 RCC control register (RCC_CR)
```text
                Address offset: 0x0
                Reset value: 0x0000 0008
 31      30       29     28      27     26      25      24      23     22     21      20      19     18      17       16
 Res.   Res.     Res.    Res.   Res.   Res.    Res.    Res.   Res.    Res.   Res.    Res.    Res.   Res.    Res.     Res.
{COLS}
                                                                                     HSE     HSI
                                                                                     ON      ON
                                                                                     rw      rw
<!-- source: RM0486 p.480 -->
             Bit 4 HSEON: HSE oscillator enable
             Bit 3 HSION: HSI oscillator enable
```
"""
SR = f"""<!-- source: RM0486 section 14.10.2 starting p.481 -->
#### 14.10.2 RCC status register (RCC_SR)
```text
               Address offset: 0x4
               Reset value: 0x0000 0000
{COLS}
                                                                                     HSE     HSI
                                                                                     RDY     RDY
                                                                                      r       r
<!-- source: RM0486 p.482 -->
               Bit 4 HSERDY: HSE clock ready flag
               Bit 3 HSIRDY: HSI clock ready flag
```
"""
CSR = f"""#### 14.10.128 RCC control set register (RCC_CSR)
```text
               Address offset: 0x800
               Reset value: 0x0000 0000
{COLS}
                                                                                     HSEO    HSION
                                                                                      w       w
               Bit 4 HSEONS: HSE enable
               Bit 3 HSIONS: HSI enable
```
"""
CCR = CSR.replace("set register (RCC_CSR)", "clear register (RCC_CCR)").replace("0x800", "0x1000").replace("ONS:", "ONC:")
HDR = """#define LL_RCC_CR_OFFSET 0x000U
#define LL_RCC_SR_OFFSET 0x004U
#define LL_RCC_CR_HSION_MSK 0x00000008U
#define LL_RCC_CR_HSEON_MSK 0x00000010U
#define LL_RCC_SR_HSIRDY_MSK 0x00000008U
#define LL_RCC_CR_FOO_MSK 0x00000080U
static inline void LL_RCC_HSI_Enable(void)
{
  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSION_MSK;
}

static inline void LL_RCC_HSE_Enable(void)
{
  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSEON_MSK;
}
"""


@pytest.fixture
def sections(tmp_path):
    d = tmp_path / "WO" / "workspace" / "inputs/sections/RM0486"
    d.mkdir(parents=True)
    for name, t in (("14.10.1_RCC_CR.md", CR), ("14.10.2_RCC_SR.md", SR), ("14.10.128_RCC_CSR.md", CSR),
                    ("14.10.185_RCC_CCR.md", CCR)):
        (d / name).write_text(t)
    return d


# ---- M4 hardware semantics (T033 / AT-038 / AT-084) ----------------------------------------------------------------
def test_independent_index_access_reserved_and_aliases(sections):
    idx = H.index(sections)
    assert idx["RCC_SR"]["read_only"] and not idx["RCC_CR"]["read_only"]
    assert idx["RCC_CR"]["fields"]["HSION"]["access"] == ["rw"] and idx["RCC_CR"]["reset"] == 0x8
    assert idx["RCC_CR"]["reserved_mask"] == 0xFFFFFFE7
    assert H.set_clear_aliases(idx)["RCC_CR"] == ("RCC_CSR", "RCC_CCR")


def test_at038_write_to_read_only_status_register_is_found(sections):
    idx = H.index(sections)
    bad = HDR + "static inline void X(void)\n{\n  ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] = LL_RCC_SR_HSIRDY_MSK;\n}\n"
    f = H.check_writes(bad, HDR, idx)
    assert any(x.startswith("RO_REGISTER_WRITE:RCC_SR") for x in f)
    assert sum(x.startswith("NON_ATOMIC_RMW:RCC_CR") for x in f) == 2       # CSR/CCR exist in the RM


def test_reserved_unknown_field_and_unknown_register(sections):
    idx = H.index(sections)
    code = ("void a(void)\n{\n  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] = LL_RCC_CR_FOO_MSK;\n}\n"
            "void b(void)\n{\n  ll_rcc_regs[0x40U / 4U] = 1U;\n}\n"
            "void c(void)\n{\n  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] = 0x80U;\n}\n")
    f = H.check_writes(code, HDR, idx)
    assert "UNKNOWN_FIELD:LL_RCC_CR_FOO_MSK:for RCC_CR:line 3" in f
    assert any(x.startswith("RESERVED_BIT_WRITE:RCC_CR:0x00000080:line 3") for x in f)
    assert any(x.startswith("UNKNOWN_REGISTER:offset 0x40") for x in f)
    assert any(x.startswith("RESERVED_BIT_WRITE:RCC_CR:0x00000080:line 11") for x in f)


def test_at084_simulator_mismatch_and_errata_unknown(sections):
    idx = H.index(sections)
    ok_model = "READY_MASK = 0x00000018\nregs = {}\nrequest.Value = regs.get(off, 0)\n0x800 set 0x1000 clear\n"
    f = H.simulator_mismatches(ok_model, idx)
    assert f == ["SIMULATOR_MISMATCH:RCC_CR reset value model 0x0 != RM 0x00000008"]
    wrong = ok_model.replace("0x00000018", "0x0000001C")
    assert "SIMULATOR_MISMATCH:RCC_SR ready mask model 0x1C != RM 0x18" in H.simulator_mismatches(wrong, idx)
    assert H.errata_status(sections.parents[2])["status"] == "UNKNOWN"


@pytest.mark.skipif(not (state_dir() / "workorders/WO-0002A-STM32N6-RCC-LL-r108/workspace/inputs/sections/RM0486").is_dir(),
                    reason="baselined RM sections not on this host")
def test_real_rm_index_matches_independent_audit():
    idx = H.index(state_dir() / "workorders/WO-0002A-STM32N6-RCC-LL-r108/workspace/inputs/sections/RM0486")
    assert idx["RCC_SR"]["read_only"] and idx["RCC_AHB1ENR"]["offset"] == 0x250 and idx["RCC_AHB1RSTR"]["offset"] == 0x210
    assert idx["RCC_CR"]["reset"] == 0x8 and idx["RCC_CR"]["reserved_mask"] == 0xFFFFF0E0
    model = (state_dir().parent / "factory/sim/stm32n6/rcc_model.py")
    from forge_factory.common import REPO_ROOT

    f = H.simulator_mismatches((REPO_ROOT / "factory/sim/stm32n6/rcc_model.py").read_text(), idx)
    assert "SIMULATOR_MISMATCH:RCC_CR reset value model 0x0 != RM 0x00000008" in f and model is not None


# ---- M3 SWE.1 (T024..T027 / AT-024..AT-027 / AT-031) ------------------------------------------------------------
REQS = """# Software requirements
- **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION.
  - Source: RM0486 p.480
- **SWR-002** The RCC driver shall bound every oscillator ready wait to HAL_RCC_TIMEOUT_VALUE = 1000 polling iterations.
  - Source: owner decision 2026-10-16
"""


def _ws(sections, reqs=REQS, trace="requirement_id,test_id,test_file\nSWR-001,UT-001,t.c\nSWR-002,UT-002,t.c\n"):
    ws = sections.parents[2]
    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(reqs)
    (ws / "traceability").mkdir(exist_ok=True)
    (ws / "traceability/requirements_to_tests.csv").write_text(trace)
    return ws


def test_at024_source_anchored_requirements(sections):
    ws = _ws(sections)
    assert swe12.check_requirements(ws)["major_findings"] == []
    ws = _ws(sections, REQS.replace("RM0486 p.480", "RM0486 p.482"))
    assert "REQ_SOURCE_MISMATCH:SWR-001:HSION not on p.482" in swe12.check_requirements(ws)["major_findings"]


def test_at025_quality_no_source_assumption_untestable_unbounded(sections):
    bad = REQS + ("- **SWR-003** When the HSE enable is requested, the RCC driver shall wait until it is ready, as needed.\n"
                  "- **SWR-004** The RCC driver shall be robust.\n  - Source: owner\n")
    f = swe12.check_requirements(_ws(sections, bad))["major_findings"]
    assert {"REQ_NO_SOURCE:SWR-003", "REQ_SILENT_ASSUMPTION:SWR-003:as needed", "REQ_UNBOUNDED_TIME:SWR-003",
            "REQ_NOT_TESTABLE:SWR-004"} <= set(f)


def test_at031_contradiction_and_invented_register(sections):
    bad = REQS + ("- **SWR-003** The RCC driver shall bound every wait to HAL_RCC_TIMEOUT_VALUE = 500 polling iterations.\n"
                  "  - Source: owner\n"
                  "- **SWR-004** When the HSI enable is requested, the RCC driver shall clear RCC_CR.HSION.\n"
                  "  - Source: RM0486 p.480\n"
                  "- **SWR-005** When the PLL9 enable is requested, the RCC driver shall set RCC_PLL9CR.PLL9ON.\n"
                  "  - Source: RM0486 p.480\n")
    f = swe12.check_requirements(_ws(sections, bad))["major_findings"]
    assert "REQ_CONTRADICTION:SWR-002,SWR-003:HAL_RCC_TIMEOUT_VALUE=1000!=500" in f
    assert "REQ_CONTRADICTION:SWR-001,SWR-004:RCC_CR.HSION set and cleared on the same trigger" in f
    assert "REQ_UNKNOWN_REGISTER:SWR-005:RCC_PLL9CR" in f


def test_at026_trace_round_trip_and_change_invalidates_dependents(sections, tmp_path):
    ws = _ws(sections, trace="requirement_id,test_id,test_file\nSWR-001,UT-001,t.c\nSWR-009,UT-009,t.c\n")
    f = swe12.trace_round_trip(ws)["major_findings"]
    assert f == ["TRACE_REQ_WITHOUT_TEST:SWR-002", "TRACE_TEST_FOR_UNKNOWN_REQ:UT-009->SWR-009"]
    s = AssuranceStore(tmp_path / "db.sqlite3")
    g = impact.ImpactGraph()
    g.add("req:SWR-001", swe12.requirements_digest(ws))
    g.add("trace:SWR-001->UT-001", "t1", ["req:SWR-001"])
    g.add("unit-test:UT-001", "u1", ["trace:SWR-001->UT-001"])
    g.add("claim:SWR-001", "c1", ["unit-test:UT-001"])
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQS.replace("shall set", "shall toggle"))
    assert g.change("req:SWR-001", swe12.requirements_digest(ws), store=s) == ["claim:SWR-001", "trace:SWR-001->UT-001",
                                                                              "unit-test:UT-001"]


def test_at027_owner_freeze_human_only_and_goes_stale(sections, tmp_path):
    ws = _ws(sections)
    s = AssuranceStore(tmp_path / "db.sqlite3")
    with pytest.raises(PermissionError):
        swe12.owner_freeze(s, ws, "agent-swe1", citations_checked=True)
    with pytest.raises(ValueError):
        swe12.owner_freeze(s, ws, "j.doe", citations_checked=False)
    assert swe12.owner_freeze_status(s, ws) == "NOT_FROZEN"
    swe12.owner_freeze(s, ws, "j.doe", citations_checked=True)
    assert swe12.owner_freeze_status(s, ws) == "FROZEN"
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQS + "- **SWR-003** filled in silently\n")
    assert swe12.owner_freeze_status(s, ws) == "STALE_FREEZE"


# ---- M3 SWE.2 (T028..T031 / AT-028..AT-031) ---------------------------------------------------------------------
STATIC = """@startuml
component "RCC_HAL\\nstm32n6xx_hal_rcc" <<SWC>> as SWC_HAL
component "RCC_LL\\nstm32n6xx_ll_rcc" <<SWC>> as SWC_LL
component "RCC registers" as RCC
SWC_HAL --> SWC_LL : IF-01 accessors
SWC_LL --> RCC : IF-02 registers
@enduml
"""
DYN = "@startuml\nparticipant Caller\nparticipant stm32n6xx_hal_rcc\nparticipant stm32n6xx_ll_rcc\nparticipant RCC\n@enduml\n"


def _arch(ws, static=STATIC, dyn=DYN, md="## Components\n## Shared resources and interrupts\nNo interrupt context; "
          "callers serialize access (owner: application).\n"):
    d = ws / "workproducts/SWE.2"
    d.mkdir(parents=True, exist_ok=True)
    (d / "architecture_static.puml").write_text(static)
    (d / "architecture_dynamic.puml").write_text(dyn)
    (d / "software_architecture.md").write_text(md)
    (ws / "software/ll").mkdir(parents=True, exist_ok=True)
    (ws / "software/ll/stm32n6xx_ll_rcc.h").write_text(HDR)
    (ws / ".forge-run").mkdir(exist_ok=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL"}))
    return ws


def test_at028_structural_invariants(sections):
    ws = _arch(sections.parents[2])
    assert swe12.check_architecture(ws)["major_findings"] == []
    ws = _arch(ws, STATIC + "SWC_LL --> SWC_HAL : IF-03 callback\nSWC_HAL --> GHOST : IF-04 x\n")
    f = swe12.check_architecture(ws)["major_findings"]
    assert "ARCH_UNDECLARED_ENDPOINT:GHOST" in f and any(x.startswith("ARCH_CYCLE:") for x in f)


def test_at029_shared_resource_and_irq_owner_and_view_consistency(sections):
    ws = _arch(sections.parents[2], md="## Components\nIRQ handler RCC_IRQHandler clears flags.\n")
    f = swe12.check_architecture(ws)["major_findings"]
    assert "ARCH_SHARED_RESOURCE_UNOWNED:RCC_CR written by LL_RCC_HSE_Enable, LL_RCC_HSI_Enable" not in f  # IRQ text present
    assert "ARCH_IRQ_OWNER_MISSING" in f
    ws = _arch(ws, md="## Components\nHAL and LL only.\n")
    assert "ARCH_SHARED_RESOURCE_UNOWNED:RCC_CR written by LL_RCC_HSE_Enable, LL_RCC_HSI_Enable" in \
        swe12.check_architecture(ws)["major_findings"]
    ws = _arch(ws, dyn=DYN.replace("participant RCC\n", "participant RCC\nparticipant stm32n6xx_dma\n"))
    assert "ARCH_VIEW_INCONSISTENT:dynamic participant stm32n6xx_dma not in static view" in \
        swe12.check_architecture(ws)["major_findings"]


def test_layer_bypass_hal_writing_registers(sections):
    ws = _arch(sections.parents[2])
    (ws / "software/hal").mkdir(parents=True, exist_ok=True)
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text("void f(void){ ll_rcc_regs[0] = 1U; }\n")
    assert "ARCH_LAYER_BYPASS:stm32n6xx_hal_rcc.c accesses registers directly" in swe12.check_architecture(ws)["major_findings"]
