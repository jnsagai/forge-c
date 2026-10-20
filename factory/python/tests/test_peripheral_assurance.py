"""Feature 009 PG-T018: the observe-only assurance verifiers are peripheral-generic. On an IWDG work order they measure
the IWDG identities (LL header, unit test, compile unit, register prefix and block, simulator model) or say why they
cannot - never a vacuous PASS from an absent RCC file. RCC behaviour is unchanged (historical patterns and texts).

i003 (the first IWDG run) showed the gaps: mutation/API-execution NOT_RUN ('no unit test': test_rcc.c), the oracle
NOT_SUPPORTED (stm32n6xx_ll_rcc.h not found), register semantics and concurrency PASS on an empty RCC header, 'the LL
API takes no parameters' for LL_IWDG_SetPrescaler(uint32_t), and 'behavioural RCC model' for the IWDG model."""
import json
import re
import shutil

import pytest
from forge_factory import workorder as WO
from forge_factory.assurance import hardware, mutation, oracle_gen, swe3, swe12
from forge_factory.assurance import target as T
from forge_factory.assurance import verifiers as V
from forge_factory.common import REPO_ROOT
from forge_factory.layer import ll_tu_text

EX = REPO_ROOT / "examples/0009a-iwdg-ll"
I003_HEADER = REPO_ROOT / "evidence/v0.4/runs/PG-T012/i003/stm32n6xx_ll_iwdg.h"  # the i003 generated LL (evidence)
UNIT = """#include <stdio.h>
#include "stm32n6xx_ll_iwdg.h"
volatile uint32_t ll_iwdg_regs[LL_IWDG_REG_COUNT];
static int fails;
#define CHECK(id, c) do { if (c) { printf("%s PASS\\n", id); } else { printf("%s FAIL\\n", id); fails++; } } while (0)
int main(void)
{
    LL_IWDG_Enable();
    CHECK("UT-001", ll_iwdg_regs[0] == 0xCCCCU);
    LL_IWDG_ReloadCounter();
    CHECK("UT-002", ll_iwdg_regs[0] == 0xAAAAU);
    LL_IWDG_EnableWriteAccess();
    CHECK("UT-003", ll_iwdg_regs[0] == 0x5555U);
    LL_IWDG_DisableWriteAccess();
    CHECK("UT-004", ll_iwdg_regs[0] == 0x0000U);
    ll_iwdg_regs[1] = 0xFFFFFFF0U;
    LL_IWDG_SetPrescaler(5U);
    CHECK("UT-005", ll_iwdg_regs[1] == 0xFFFFFFF5U);
    ll_iwdg_regs[2] = 0xFFFFF000U;
    LL_IWDG_SetReloadCounter(0xABCU);
    CHECK("UT-006", ll_iwdg_regs[2] == 0xFFFFFABCU);
    ll_iwdg_regs[3] = 0x1U;
    CHECK("UT-007", (LL_IWDG_IsActiveFlag_PVU() == 1U) && (LL_IWDG_IsActiveFlag_RVU() == 0U));
    ll_iwdg_regs[3] = 0x2U;
    CHECK("UT-008", (LL_IWDG_IsActiveFlag_RVU() == 1U) && (LL_IWDG_IsActiveFlag_PVU() == 0U));
    ll_iwdg_regs[3] = 0x100U;
    CHECK("UT-009", LL_IWDG_IsActive() == 1U);
    ll_iwdg_regs[3] = 0x0U;
    CHECK("UT-010", (LL_IWDG_IsActive() == 0U) && (LL_IWDG_IsActiveFlag_PVU() == 0U));
    return fails ? 1 : 0;
}
"""


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    w, man = WO.prepare(EX, "WO-IWDG-AS-1")
    assert man["peripheral"] == "iwdg"
    (w / "software/ll").mkdir(parents=True, exist_ok=True)
    shutil.copy(I003_HEADER, w / "software/ll/stm32n6xx_ll_iwdg.h")
    (w / "software/src").mkdir(parents=True, exist_ok=True)
    (w / "software/src/stm32n6xx_ll_iwdg.c").write_text(ll_tu_text(w))
    (w / "software/tests/unit").mkdir(parents=True, exist_ok=True)
    (w / "software/tests/unit/test_iwdg.c").write_text(UNIT)
    return w


# ---- RCC: the historical patterns and texts are unchanged ----------------------------------------------------------
def test_rcc_patterns_and_texts_unchanged(tmp_path):
    assert hardware.DEFINE.pattern == r"^\s*#\s*define\s+(LL_RCC_\w+)\s+\(?\s*(0x[0-9A-Fa-f]+|\d+)U?L?\s*\)?"
    assert hardware.WRITE.pattern == r"ll_rcc_regs\s*\[\s*([^\]]+?)\s*\]\s*(\|=|&=|=)(?!=)\s*([^;]+);"
    assert hardware.prefix_of_index({}) == "RCC" and hardware.block_of("RCC") == "ll_rcc_regs"
    assert mutation.ops_for("RCC") is mutation.OPS and mutation.ops_for() is mutation.OPS
    st = T.fault_injection_status(tmp_path, [])  # no manifest: RCC
    assert st["clock_failure / clock security"] == "NOT_SUPPORTED: behavioural RCC model has no clock tree"
    assert T.limitations(tmp_path, "")[0] == ("Renode behavioural RCC model is not silicon, not HIL; no clock-tree "
                                              "timing, security filtering or interrupts")
    assert T.fidelity_record("r", "RENODE", "STM32N657X0", "v", [], [])["observed_peripherals"] == ["RCC"]
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    assert V.v_negative_boundary(tmp_path)["findings"] == ["NOT_APPLICABLE:the LL API takes no parameters"]


# ---- IWDG: measured on the IWDG identities ---------------------------------------------------------------------------
def test_iwdg_register_semantics_are_measured_not_vacuous(ws):
    r = V.v_register_semantics(ws)
    assert r["status"] == "PASS" and r["findings"] == []
    hdr = (ws / "software/ll/stm32n6xx_ll_iwdg.h").read_text()
    idx = V._idx(ws)
    assert hardware.prefix_of_index(idx) == "IWDG" and len(hardware.define_rx("IWDG").findall(hdr)) >= 20
    assert hardware.check_defines(hdr.replace("LL_IWDG_SR_RVU_MSK 0x00000002U", "LL_IWDG_SR_RVU_MSK 0x00000004U"),
                                  idx) == ["DEFINE_MISMATCH:LL_IWDG_SR_RVU_MSK:0x4!=0x2"]
    bad = hdr.replace("ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = LL_IWDG_KEY_ENABLE;",
                      "ll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U] = LL_IWDG_SR_PVU_MSK;")
    assert any(f.startswith("RO_REGISTER_WRITE:IWDG_SR") for f in hardware.check_writes(bad, bad, idx, "ll_iwdg_regs"))
    (ws / "software/ll/stm32n6xx_ll_iwdg.h").write_text(hdr.replace("LL_IWDG_SR_RVU_MSK 0x00000002U",
                                                                    "LL_IWDG_SR_RVU_MSK 0x00000004U"))
    assert V.v_register_semantics(ws)["status"] == "FAIL"


def test_iwdg_missing_header_is_not_a_pass(ws):
    (ws / "software/ll/stm32n6xx_ll_iwdg.h").unlink()
    r = V.v_register_semantics(ws)
    assert r["status"] == "NOT_SUPPORTED" and "stm32n6xx_ll_iwdg.h" in r["findings"][0]


def test_iwdg_unit_test_verifiers_run(ws):
    a = V.v_api_execution(ws)
    assert a["status"] in ("PASS", "NOT_SUPPORTED")  # NOT_SUPPORTED only where clang/llvm-cov are missing
    if a["status"] == "PASS":
        assert a["findings"] == []
    m = V.v_mutation(ws)
    assert m["status"] in ("PASS", "FAIL") and m["campaign"]["eligible"] > 0
    ops = mutation.ops_for("IWDG")
    assert not {n for n, _, _ in ops} & mutation.RCC_ONLY and not any("RCC" in rx for _, rx, _ in ops)
    assert all(m["op"] not in mutation.RCC_ONLY for m in mutation.mutants((ws / "software/ll/stm32n6xx_ll_iwdg.h")
                                                                          .read_text(), "IWDG"))


def test_iwdg_ll_boundary_is_not_claimed_not_applicable(ws):
    r = V.v_negative_boundary(ws)
    assert r["status"] == "NOT_SUPPORTED" and "LIMITATION" in r["findings"][0]


def test_iwdg_oracle_finds_the_api_header(ws):
    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.2").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** When the early wake-up interrupt enable is requested, the IWDG LL driver shall set "
        "IWDG_EWCR.EWIE.\n")
    (ws / "workproducts/SWE.2/software_architecture.md").write_text("| SWR-001 | LL_IWDG_EnableIT_EWI |\n")
    h = ws / "software/ll/stm32n6xx_ll_iwdg.h"
    h.write_text(h.read_text().replace(
        "#endif /* STM32N6XX_LL_IWDG_H */", "#define LL_IWDG_EWCR_OFFSET 0x014U\n#define LL_IWDG_EWCR_EWIE_MSK 0x00008000U\n"
        "static inline void LL_IWDG_EnableIT_EWI(void)\n{\n    ll_iwdg_regs[LL_IWDG_EWCR_OFFSET / 4U] |= "
        "LL_IWDG_EWCR_EWIE_MSK;\n}\n#endif /* STM32N6XX_LL_IWDG_H */", 1))
    r = V.v_oracle(ws)  # the sentence-parsing oracle on IWDG names (RM: EWIE is bit 15 of IWDG_EWCR at 0x14)
    assert r["status"] == "PASS" and r["cases"] == 1


def test_oracle_derive_uses_the_prefix():
    idx = {"IWDG_EWCR": {"offset": 0x14, "fields": {"EWIE": {"msb": 15, "lsb": 15}}}}
    req = "- **SWR-001** When the early wake-up interrupt enable is requested, the IWDG LL driver shall set IWDG_EWCR.EWIE."
    arch, hdr = "| SWR-001 | LL_IWDG_EnableIT_EWI |", "static inline void LL_IWDG_EnableIT_EWI(void) {"
    cases, _ = oracle_gen.derive(req, arch, hdr, idx, "IWDG")
    assert [(c["function"], c["word"], c["mask"]) for c in cases] == [("LL_IWDG_EnableIT_EWI", 5, 0x8000)]
    assert oracle_gen.derive(req, arch, hdr, idx) == ([], [])  # RCC default: IWDG text is not RCC


def test_iwdg_model_texts(ws):
    st = T.fault_injection_status(ws, [])
    assert st["clock_failure / clock security"] == "NOT_SUPPORTED: behavioural IWDG model has no clock tree"
    lim = T.limitations(ws, (REPO_ROOT / "factory/sim/stm32n6/iwdg_model.py").read_text())
    assert lim[0].startswith("Renode behavioural IWDG model") and not any("RCC" in x for x in lim)
    assert any(x.startswith("SIMULATOR_MODEL_NOT_COMPARABLE:no RM comparison rule for the IWDG model") for x in lim)
    assert T.integration_categories({"t.c": "LL_IWDG_Enable();"}, set(), "IWDG")["categories"]["interface"]


def test_iwdg_loop_bound_check_sees_iwdg_polls(ws):
    hdr = (ws / "software/ll/stm32n6xx_ll_iwdg.h").read_text()
    code = {"hal.c": "int HAL_IWDG_Init(void)\n{\n    while (LL_IWDG_IsActiveFlag_PVU() != 0U)\n    {\n    }\n"
                     "    return 0;\n}\n"}
    f = swe3.invariant_findings(code, hdr, V._idx(ws), True, "ll_iwdg_regs", "IsReady|IsEnabled|IsActive")
    assert f == ["LOOP_UNBOUNDED:HAL_IWDG_Init@hal.c"]
    assert swe3.invariant_findings(code, hdr, V._idx(ws), True) == []  # the RCC default does not know IsActive


def test_bare_plantuml_declaration_is_declared(ws):
    (ws / "workproducts/SWE.2").mkdir(parents=True, exist_ok=True)
    (ws / swe12.STATIC).write_text("@startuml\nactor Caller\ncomponent \"LL\" as SWC_LL\nCaller --> SWC_LL : IF-01\n"
                                   "@enduml\n")
    assert not any("UNDECLARED_ENDPOINT" in f for f in swe12.check_architecture(ws)["major_findings"])
    (ws / swe12.STATIC).write_text("@startuml\ncomponent \"LL\" as SWC_LL\nGhost --> SWC_LL : IF-01\n@enduml\n")
    assert "ARCH_UNDECLARED_ENDPOINT:Ghost" in swe12.check_architecture(ws)["major_findings"]


@pytest.mark.parametrize("text,escalated", [
    ("Renode checks key protection and update status, rather than proving those effects on silicon.", False),
    ("The watchdog behaviour was verified on silicon rather than in simulation.", True),
    ("Integration ran on the host and on Renode.", False)])
def test_fidelity_rather_than(ws, text, escalated):
    (ws / "workproducts/SWE.5").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.5/integration_verification_report.md").write_text(text + "\n")
    (ws / "evidence").mkdir(exist_ok=True)
    (ws / "evidence/tool-results.jsonl").write_text(json.dumps({"op": "run_renode", "result": {"status": "PASS"}}) + "\n")
    r = V.v_fidelity(ws, "SWE.5")
    assert any(f.startswith("CLAIM_TEXT") for f in r["findings"]) is escalated


def test_no_rcc_identifier_in_iwdg_verifier_reports(ws):
    for fn in (V.v_register_semantics, V.v_negative_boundary, V.v_fault_injection):
        assert not re.search(r"RCC|rcc", json.dumps(fn(ws))), fn.__name__
