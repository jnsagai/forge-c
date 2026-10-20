"""CAPA-053 (h001): the SWE.3 implementation check and the evidence server's allocation map took the API prefix of the
default (RCC) profile: a HAL work order on IWDG found no allocated HAL_IWDG_ function (NO_ALLOCATED_HAL_FUNCTIONS_IN_SWE2)
and SWE.3 exhausted its rework budget; the authors filed it as factory defects DEF-001/DEF-002."""
import json

from forge_factory.inspection.implementation import allocated_functions
from forge_factory.mcp.servers.evidence import _allocation_map

ARCH = ("# Software architecture\n## Requirement allocation table\n| SWR | SWC | Function | Note |\n| --- | --- | --- | --- |\n"
        "| SWR-002 | SWC_HAL | HAL_IWDG_Init | start, configure, wait, refresh |\n"
        "| SWR-005 | SWC_HAL | HAL_IWDG_Refresh | refresh key |\n"
        "| SWR-009 | SWC_HAL | HAL_IWDG_Init | bound HAL_IWDG_TIMEOUT_VALUE |\n")


def _ws(tmp_path, manifest):
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "workproducts/SWE.2").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
    return tmp_path


def test_capa053_hal_allocation_uses_the_work_order_peripheral(tmp_path):
    ws = _ws(tmp_path, {"layer": "HAL", "peripheral": "iwdg"})
    assert allocated_functions(ws) == ["HAL_IWDG_Init", "HAL_IWDG_Refresh"]
    assert _allocation_map(ws) == {"SWR-002": ["HAL_IWDG_Init"], "SWR-005": ["HAL_IWDG_Refresh"],
                                   "SWR-009": ["HAL_IWDG_Init"]}


def test_capa053_rcc_unchanged(tmp_path):
    ws = _ws(tmp_path, {"layer": "HAL"})
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(ARCH.replace("IWDG", "RCC"))
    assert allocated_functions(ws) == ["HAL_RCC_Init", "HAL_RCC_Refresh"]
