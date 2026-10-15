"""SWE.2 deterministic architecture gate: agent-reply overwrite, SWR allocation, RM0486 register offsets."""
import json

import pytest
from forge_factory.inspection.architecture import check_architecture, is_agent_reply
from forge_factory.inspection.engine import InspectionError, Store

ARCH_MIN = ("# Architecture\n## Components\n- HAL, LL\n## Interfaces\n- HAL_RCC_HSI_Enable\n## Requirement allocation\n"
            "| SWR | Function |\n|---|---|\n| SWR-001 | HAL_RCC_HSI_SetConfig |\n## Register table\n"
            "| Name | Offset |\n|---|---|\n| RCC_CR | 0x0 |\n")  # synthetic minimum for other tests' fixtures
REPLY = '{"status":"PASS","artifacts":["workproducts/SWE.2/software_architecture.md"],"issues":[],"next_action":"next"}'
GOOD = """# Software Architecture
## Components
- LL header-only, HAL
## Interfaces
- HAL_RCC_HSI_Enable
## Requirement Allocation Table
| Requirement | Function |
|---|---|
| SWR-001 | `HAL_RCC_HSI_Enable` |
| SWR-002 | `HAL_RCC_HSI_Disable` |
## Register Table
| Name | Offset | Bits | Access | Page |
|---|---|---|---|---|
| RCC_CR | 0x0000 | 0 | RW | p.480 |
| RCC_AHB1ENR | 0x250 | 4 | RW | p.575 |
"""


@pytest.fixture()
def ws(tmp_path):
    (tmp_path / "workproducts/SWE.1").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.2").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.1/software_requirements.md").write_text("- **SWR-001** a\n- **SWR-002** b\n")
    sec = tmp_path / "inputs/sections/RM0486"
    sec.mkdir(parents=True)
    (sec / "14.10.1_RCC_CR.md").write_text("#### 14.10.1 RCC control register (RCC_CR)\n\n Address offset: 0x0\n")
    (sec / "14.10.79_RCC_AHB1ENR.md").write_text("#### 14.10.79 RCC AHB1 enable register (RCC_AHB1ENR)\n\n"
                                                 "  Address offset: 0x250\n")
    return tmp_path


def test_good_architecture_passes_with_offsets_cross_checked(ws):
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(GOOD)
    rep = check_architecture(ws)
    assert rep["verdict"] == "PASS" and rep["stats"]["registers_checked_against_rm"] == 2


def test_agent_reply_written_as_workproduct_fails_and_is_never_frozen(ws):
    assert is_agent_reply(REPLY) and not is_agent_reply('{"a": 1}') and not is_agent_reply(GOOD)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(REPLY)
    assert check_architecture(ws)["major_findings"] == ["SWE2:WORKPRODUCT_IS_AGENT_REPLY"]
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REPLY)
    with pytest.raises(InspectionError, match="WORKPRODUCT_IS_AGENT_REPLY"):
        Store(ws).freeze("SWE.1", "swe1-author")


def test_wrong_offset_missing_allocation_unknown_swr_and_missing_section(ws):
    bad = GOOD.replace("| SWR-002 |", "| SWR-009 |").replace("0x250", "0x0254").replace("## Interfaces", "## Misc")
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(bad)
    f = check_architecture(ws)["major_findings"]
    assert "SWE2:MISSING_SECTION:interfaces" in f and "SWE2:SWR_NOT_ALLOCATED:SWR-002" in f
    assert "SWE2:UNKNOWN_SWR:SWR-009" in f
    assert any(x.startswith("SWE2:REGISTER_OFFSET_MISMATCH:RCC_AHB1ENR") for x in f)


def test_swr_ranges_allocated_and_not_misread_as_ids(ws):
    from forge_factory.inspection.architecture import swr_ids

    assert swr_ids("| SWR-001..SWR-004 | f |") == {"SWR-001", "SWR-002", "SWR-003", "SWR-004"}
    assert swr_ids("SWR-010 to 012, SWR-020") == {"SWR-010", "SWR-011", "SWR-012", "SWR-020"}
    assert swr_ids("SWR-SAFE-01 and SWR-002") == {"SWR-SAFE-01", "SWR-002"}
    ranged = GOOD.replace("| SWR-001 | `HAL_RCC_HSI_Enable` |\n| SWR-002 | `HAL_RCC_HSI_Disable` |",
                          "| SWR-001..SWR-002 | `HAL_RCC_HSI_Enable`, `HAL_RCC_HSI_Disable` |")
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(ranged)
    assert check_architecture(ws)["verdict"] == "PASS", check_architecture(ws)


def test_inspection_records_deterministic_swe2_item(ws):
    (ws / "workproducts/SWE.1/software_requirements.md").write_text("- **SWR-001** a\n- **SWR-002** b\n")
    s = Store(ws)
    s.freeze("SWE.1", "swe1-author")
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(GOOD.replace("0x250", "0x254"))
    bl = s.freeze("SWE.2", "swe2-author")
    rec = s.record_inspection("SWE.2", "swe2-inspector", bl["baseline_id"], {})
    assert rec["items"]["SWE2-07"]["source"] == "deterministic" and rec["items"]["SWE2-07"]["verdict"] == "FAIL"
    assert rec["verdict"] == "FAIL"
    assert json.loads((ws / rec["items"]["SWE2-07"]["evidence_refs"][0]).read_text())["verdict"] == "FAIL"
