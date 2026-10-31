"""Delivery-first scenario guidance follows the frozen API, without imposing a register layout."""
# ruff: noqa: F811 - imported pytest fixture uses its conventional parameter name
import re

import pytest
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import sim, tests
from forge_factory.workflow import robot_scaffold
from forge_factory.workflow.builder import build
from test_delivery_first import prepared  # noqa: F401 - shared isolated fixture


def test_robot_author_has_no_unprovided_register_array_instructions(prepared):
    ws, man = prepared
    graph, _ = build(man["work_order"], layer="LL", peripheral="crc", sections={
        "26.4.2": "inputs/sections/RM0486/26.4.2_CRC_independent_data_register_CRC_IDR.md"},
        operation_scope=man["operation_scope"], assessment_manifest=man,
        execution_policy=man["development_execution"])
    prompt = re.search(r'swe6_test_author \[[^\n]*prompt="((?:\\.|[^"\\])*)"', graph)[1]
    assert "ll_crc_regs[" not in prompt
    assert "LL_CRC_<REG>_OFFSET" not in prompt
    assert "Register access follows " + man["delivery_first"]["contract"] in prompt
    assert "FORGE_MAILBOX_DEFINE" in prompt and "TCHECK" in prompt
    assert "Run Target Scenario" in prompt


def test_robot_scaffold_points_to_declared_layout_in_delivery_mode(prepared):
    ws, man = prepared
    text = robot_scaffold.header(ws)
    assert "ll_crc_regs[" not in text
    assert man["delivery_first"]["contract"] in text
    assert "Library    ForgeTarget" in text and "Simulation Performance Should Meet Budget" in text


def test_default_robot_header_keeps_existing_register_access_contract():
    assert robot_scaffold.header() == robot_scaffold.HEADER


@pytest.mark.parametrize("fault", ["none", "read", "flash"])
def test_real_robot_uses_the_declared_typed_api_and_preserves_failure(prepared, monkeypatch, fault):
    """Deliberate local C fixture, not Qwen output or full-scope product qualification."""
    from test_delivery_first import candidate

    ws, _ = prepared
    candidate(ws)
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** When called, the CRC driver shall write the supplied 32-bit IDR value.\n"
        "- **SWR-002** When called, the CRC driver shall return the current 32-bit IDR value.\n"
        "- **SWR-003** The CRC driver shall occupy at most 4096 bytes of flash.\n")
    target = ws / "software/tests/software"
    target.mkdir(parents=True)
    code = ('#include "stm32n6xx_ll_crc.h"\n#include "forge_target_test.h"\nFORGE_MAILBOX_DEFINE;\n'
            'int main(void) {\n CRC_TypeDef *crc = (CRC_TypeDef *)0x56024C00U;\n FORGE_TEST_BEGIN();\n'
            ' LL_CRC_Write_IDR(crc, 0x12345678U);\n TCHECK(1, crc->IDR == 0x12345678U);\n'
            ' crc->IDR = 0x87654321U;\n TCHECK(2, LL_CRC_Read_IDR(crc) == EXPECTED);\n'
            ' FORGE_TEST_END();\n return 0;\n}\n')
    (target / "scn_typed.c").write_text(code.replace("EXPECTED", "0U" if fault == "read" else "0x87654321U"))
    (target / "test_crc_requirements.robot").write_text(
        "*** Settings ***\nLibrary    ForgeTarget\n\n*** Test Cases ***\n"
        "SWR-001\n    [Tags]    SWR-001\n    Run Target Scenario    scn_typed.c\n    Target Check Should Pass    1\n"
        "SWR-002\n    [Tags]    SWR-002\n    Run Target Scenario    scn_typed.c\n    Target Check Should Pass    2\n"
        "SWR-003\n    [Tags]    SWR-003\n    Driver Flash Size Should Be At Most    "
        + ("1" if fault == "flash" else "4096") + "\n")
    for key, value in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_ROLE": "swe6-author",
                       "FORGE_PHASE": "SWE.6"}.items():
        monkeypatch.setenv(key, value)
    assert sim.renode_bin() is not None
    out = sdk.invoke("forge-tests-mcp", next(o for o in tests.OPERATIONS if o.name == "run_robot"), {})
    assert out["status"] == ("PASS" if fault == "none" else "FAIL"), out
    assert out["metrics"]["requirements_verified"] == (3 if fault == "none" else 2), out
    if fault == "flash":
        assert any("driver flash" in i and "exceeds 1 B" in i for i in out["issues"]), out
