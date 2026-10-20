"""Feature 009 (PG-T005/T007/T008): an IWDG work order records its profile; the register map is generated from
RM0486 chapter 59 with IWDG names only (no RCC identifier), including multi-bit fields."""
import json
import re

import pytest
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0009a-iwdg-ll"


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    w, man = WO.prepare(EX, "WO-IWDG-1")
    assert man["peripheral"] == "iwdg" and len(man["peripheral_profile_sha256"]) == 64
    return w


def test_unknown_key_section_is_refused(tmp_path, monkeypatch):
    import shutil

    from forge_factory import peripheral

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ex = tmp_path / "ex"
    shutil.copytree(EX, ex)
    spec = json.loads((ex / "workorder.json").read_text())
    for i in spec["inputs"]:
        i["path"] = str((EX / i["path"]).resolve())
    spec["peripheral"] = "rcc"  # RCC key sections are not in the IWDG inputs
    (ex / "workorder.json").write_text(json.dumps(spec))
    peripheral.load.cache_clear()
    with pytest.raises(ValueError, match="PERIPHERAL_KEY_SECTIONS_NOT_IN_INPUTS:rcc"):
        WO.prepare(ex, "WO-IWDG-2")


def test_iwdg_register_map_is_generated_with_iwdg_names_only(ws):
    from forge_factory.inspection import regmap

    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "## Register table\n\n| Register | Offset | Bits | Access | Source |\n|---|---|---|---|---|\n"
        "| IWDG_KR | 0x000 | 15:0 | w | RM0486 p.2989 |\n| IWDG_PR | 0x004 | 3:0 | rw | RM0486 p.2989 |\n"
        "| IWDG_RLR | 0x008 | 11:0 | rw | RM0486 p.2990 |\n| IWDG_SR | 0x00C | 8,1,0 | r | RM0486 p.2990 |\n")
    r = regmap.generate(ws)
    assert r["status"] == "PASS" and r["registers"] == 4
    h = (ws / "software/ll/stm32n6xx_ll_iwdg.h").read_text()
    assert "#define LL_IWDG_KR_KEY_MSK 0x0000FFFFU" in h and "#define LL_IWDG_RLR_RL_MSK 0x00000FFFU" in h
    assert "#define LL_IWDG_PR_PR_MSK 0x0000000FU" in h and "extern volatile uint32_t ll_iwdg_regs[LL_IWDG_REG_COUNT];" in h
    assert "0x56004800" in h and "STM32N6XX_LL_IWDG_H" in h
    assert not re.search(r"RCC|rcc", h)
    tu = (ws / "software/src/stm32n6xx_ll_iwdg.c").read_text()
    assert '#include "stm32n6xx_ll_iwdg.h"' in tu and "rcc" not in tu.lower()
    assert regmap.check_regmap(ws)["verdict"] == "PASS"


SWE2 = ("## Register table\n\n| Register | Offset | Bits | Access | Source |\n|---|---|---|---|---|\n"
        "| IWDG_KR | 0x000 | 15:0 | w | RM0486 p.2989 |\n| IWDG_PR | 0x004 | 3:0 | rw | RM0486 p.2989 |\n"
        "| IWDG_RLR | 0x008 | 11:0 | rw | RM0486 p.2990 |\n| IWDG_SR | 0x00C | 8,1,0 | r | RM0486 p.2990 |\n\n"
        "## Requirement allocation table\n\n| Requirement | Function | Note |\n|---|---|---|\n"
        "| SWR-001 | LL_IWDG_Enable | KR start key |\n| SWR-002 | LL_IWDG_SetPrescaler | PR value |\n")


def test_iwdg_harness_and_implementation_check(ws):
    from forge_factory.inspection import regmap
    from forge_factory.inspection.implementation import check_implementation
    from forge_factory.workflow.scaffold import scaffold

    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(SWE2)
    regmap.generate(ws)
    h = ws / "software/ll/stm32n6xx_ll_iwdg.h"
    h.write_text(h.read_text().replace(regmap.functions_marker(ws), regmap.functions_marker(ws) + "\n"
        "static inline void LL_IWDG_Enable(void)\n{\n    ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x0000CCCCU;\n}\n"
        "static inline void LL_IWDG_SetPrescaler(uint32_t prescaler)\n{\n"
        "    ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] = (prescaler & LL_IWDG_PR_PR_MSK);\n}\n"))
    r = check_implementation(ws)
    assert r["verdict"] == "PASS", r["major_findings"]  # LL functions with a value parameter are allowed for IWDG
    out = scaffold(ws)
    t = (ws / out["file"]).read_text()
    assert out["file"] == "software/tests/unit/test_iwdg.c"
    assert '#include "stm32n6xx_ll_iwdg.h"' in t and "volatile uint32_t ll_iwdg_regs[LL_IWDG_REG_COUNT];" in t
    assert "rcc" not in t.lower()


def test_iwdg_robot_suite_header_and_observation_tokens(ws):
    from forge_factory.mcp.servers.robot_policy import required_tokens
    from forge_factory.workflow import robot_scaffold as R

    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** When the IWDG start function is called, the IWDG LL driver shall write 0xCCCC to IWDG_KR.KEY.\n")
    out = R.scaffold(ws)
    text = (ws / out["file"]).read_text()
    assert out["file"] == "software/tests/software/test_iwdg_requirements.robot"
    assert "IWDG behavioural model: see iwdg_model.py" in text and "LL_IWDG_KR_KEY_MSK" in text
    assert "RCC" not in text and "rcc" not in text
    assert required_tokens("shall write 0xCCCC to IWDG_KR.KEY.", "IWDG", "LL_IWDG_")[1] == {"LL_IWDG_KR_KEY_MSK"}


def test_check_results_accept_the_colon_form(tmp_path):
    """i002: the SWE.5 author's CHECK printed 'IT-001: PASS'; swtrace saw no result line and SWE.5 blocked."""
    from forge_factory.inspection.swtrace import check_results

    log = tmp_path / "run.log"
    log.write_text("IT-001: PASS\nIT-002 PASS\nIT-003-a: FAIL\nIT-003-b PASS\n")
    assert check_results([log]) == {"IT-001": "PASS", "IT-002": "PASS", "IT-003": "FAIL"}
