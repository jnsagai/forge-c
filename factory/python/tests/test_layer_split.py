"""ADR-0009 (owner decision 2026-10-16): LL and HAL are built in separate work orders - LL first, then a HAL work
order on the PROVIDED, verified LL header."""
import json
import re

import pytest
from forge_factory import layer as LY
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT
from forge_factory.inspection import engine
from forge_factory.inspection.guideline import check_workspace
from forge_factory.inspection.implementation import check_implementation
from forge_factory.inspection.regmap import FUNCTIONS_MARKER
from forge_factory.workflow import prompts
from forge_factory.workflow import scaffold as SC
from forge_factory.workflow.builder import build

LL_EX, HAL_EX = REPO_ROOT / "examples/0002a-arm_55_rcc_ll", REPO_ROOT / "examples/0002b-arm_55_rcc_hal"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    yield tmp_path
    prompts.LAYER["layer"] = "LL+HAL"  # module state set by build(); never leak into other tests


def ws_with(tmp_path, layer, provided=()):
    ws = tmp_path / f"ws-{layer}"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": layer, "provided": list(provided)}))
    return ws


def test_examples_declare_the_layers():
    assert json.loads((LL_EX / "workorder.json").read_text())["layer"] == "LL"
    assert json.loads((HAL_EX / "workorder.json").read_text())["layer"] == "HAL"
    assert "layer" not in json.loads((REPO_ROOT / "examples/0002-arm_55_rcc_st/workorder.json").read_text())


@pytest.mark.parametrize("layer,present,absent", [
    ("LL", ["swe3_regmap", "swe3_ll_author", "swe3_fix_author"], ["swe3_hal_author"]),
    ("HAL", ["swe3_hal_author", "swe3_fix_author"], ["swe3_regmap", "swe3_ll_author"]),
    ("LL+HAL", ["swe3_regmap", "swe3_ll_author", "swe3_hal_author", "swe3_fix_author"], []),
])
def test_swe3_chain_depends_on_the_layer(layer, present, absent):
    dot, nodes = build("WO-L", layer=layer, chunk_lines=150)
    for n in present:
        assert re.search(rf"^\s+{n} \[", dot, re.M), n
    for n in absent:
        assert not re.search(rf"^\s+{n} \[", dot, re.M), n
    chain = [n for n in present]
    for x, y in zip(chain, chain[1:] + ["swe3_author"], strict=True):
        assert f"  {x} -> {y}" in dot
    if layer == "HAL":
        assert 'swe2_inspect_gate -> swe3_hal_author [condition="outcome=succeeded"]' in dot


def test_ll_prompts_never_ask_for_hal_work():
    build("WO-L", layer="LL", chunk_lines=150)
    texts = [prompts.author_prompt(p) for p in engine.PHASES] + [
        prompts.ll_author_prompt(), prompts.fix3_author_prompt(), prompts.unit_test_author_prompt(),
        prompts.target_test_author_prompt(), prompts.robot_test_author_prompt(), prompts.triage_prompt(3)]
    for t in texts:
        assert "stm32n6xx_hal_rcc" not in t
        assert "hal_status_t" not in t
    assert "RCC LL driver" in prompts.author_prompt("SWE.1")
    assert "LL_RCC_<Name>_IsReady" in prompts.author_prompt("SWE.2")
    assert '#include \\"stm32n6xx_ll_rcc.h\\"' in json.dumps(prompts.target_test_author_prompt())


def test_hal_prompts_build_on_the_provided_ll():
    build("WO-H", layer="HAL", chunk_lines=150)
    assert "PROVIDED LL header-only" in prompts.author_prompt("SWE.2")
    for t in (prompts.hal_author_prompt(), prompts.fix3_author_prompt()):
        assert "PROVIDED read-only" in t and "never write or edit it" in t
    build("WO-X", layer="LL+HAL", chunk_lines=150)  # legacy texts unchanged
    assert "PROVIDED" not in prompts.author_prompt("SWE.2")


def test_ll_scaffold_and_guideline_layout(tmp_path):
    ws = ws_with(tmp_path, "LL")
    SC.scaffold(ws)
    assert '#include "stm32n6xx_ll_rcc.h"' in (ws / SC.UNIT_TEST).read_text()
    (ws / "software/ll").mkdir(parents=True)
    (ws / LY.LL_HEADER).write_text("#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#endif /* STM32N6XX_LL_RCC_H */\n")
    rep = check_workspace(ws)
    assert not [v for v in rep["violations"] if v["rule"] == "GL-FILE-01" and "hal" in v["file"]]
    hal_ws = ws_with(tmp_path, "HAL")
    SC.scaffold(hal_ws)
    assert '#include "stm32n6xx_hal_rcc.h"' in (hal_ws / SC.UNIT_TEST).read_text()


ARCH = """# Software architecture
## Requirement allocation
| SWR | Function |
|---|---|
| SWR-001 | LL_RCC_HSI_Enable |
| SWR-002 | LL_RCC_HSI_IsReady |
"""


def test_ll_implementation_check(tmp_path):
    ws = ws_with(tmp_path, "LL")
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
    (ws / "software/ll").mkdir(parents=True)
    head = "#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n" \
           "extern volatile uint32_t ll_rcc_regs[1024U];\n"
    one = "static inline void LL_RCC_HSI_Enable(void)\n{\n    ll_rcc_regs[0U] |= 1U;\n}\n"
    two = "static inline uint32_t LL_RCC_HSI_IsReady(void)\n{\n    return ((ll_rcc_regs[1U] & 2U) != 0U) ? 1U : 0U;\n}\n"
    (ws / LY.LL_HEADER).write_text(head + one + "#endif /* STM32N6XX_LL_RCC_H */\n")
    r = check_implementation(ws)
    assert r["verdict"] == "FAIL" and "IMPL:NOT_DEFINED:LL_RCC_HSI_IsReady" in r["major_findings"]
    assert not any("HAL" in f for f in r["major_findings"])  # no HAL file is required in an LL work order
    (ws / LY.LL_HEADER).write_text(head + one + two + "#endif /* STM32N6XX_LL_RCC_H */\n")
    assert check_implementation(ws)["verdict"] == "PASS"
    (ws / LY.LL_HEADER).write_text(head + one + two.replace("static inline ", "") + "#endif\n")
    assert "IMPL:LL_NOT_STATIC_INLINE:LL_RCC_HSI_IsReady" in check_implementation(ws)["major_findings"]


def test_hal_work_order_detects_a_changed_provided_ll(tmp_path):
    from forge_factory.common import sha256_bytes

    data = b"#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#endif /* STM32N6XX_LL_RCC_H */\n"
    ws = ws_with(tmp_path, "HAL", [{"path": LY.LL_HEADER, "sha256": sha256_bytes(data)}])
    (ws / "software/ll").mkdir(parents=True)
    (ws / LY.LL_HEADER).write_bytes(data)
    assert "IMPL:PROVIDED_COMPONENT_CHANGED:" + LY.LL_HEADER not in check_implementation(ws)["major_findings"]
    (ws / LY.LL_HEADER).write_bytes(data + b"/* edited */\n")
    assert "IMPL:PROVIDED_COMPONENT_CHANGED:" + LY.LL_HEADER in check_implementation(ws)["major_findings"]


def _fake_ll_workorder(state, gates_pass=True, layer="LL"):
    src = state / "workorders/WO-LL-1/workspace"
    (src / "software/ll").mkdir(parents=True)
    (src / LY.LL_HEADER).write_text("/* verified LL */\n" + FUNCTIONS_MARKER + "\n")
    (src / ".forge-run").mkdir(parents=True)
    (src / ".forge-run/manifest.json").write_text(json.dumps({"layer": layer}))
    return src


def test_hal_prepare_requires_a_verified_ll(env, monkeypatch):
    with pytest.raises(ValueError, match="HAL_LAYER_NEEDS_PROVIDED_LL"):
        WO.prepare(HAL_EX, "WO-HAL-0")
    _fake_ll_workorder(env / "state")
    monkeypatch.setattr(engine.Store, "gate", lambda self, ph: {"decision": "FAIL" if ph == "SWE.6" else "PASS"})
    with pytest.raises(ValueError, match="PROVIDED_LL_NOT_VERIFIED:WO-LL-1:SWE.6"):
        WO.prepare(HAL_EX, "WO-HAL-1", "WO-LL-1")
    monkeypatch.setattr(engine.Store, "gate", lambda self, ph: {"decision": "PASS"})
    ws, man = WO.prepare(HAL_EX, "WO-HAL-2", "WO-LL-1")
    assert man["layer"] == "HAL" and man["provided"][0]["source_work_order"] == "WO-LL-1"
    hdr = ws / LY.LL_HEADER
    assert hdr.read_text().startswith("/* verified LL */") and (hdr.stat().st_mode & 0o222) == 0
    assert LY.layer_of(ws) == "HAL" and LY.provided(ws)[0]["sha256"] == man["provided"][0]["sha256"]


def test_hal_refuses_a_provided_header_from_a_non_ll_work_order(env, monkeypatch):
    _fake_ll_workorder(env / "state", layer="LL+HAL")
    monkeypatch.setattr(engine.Store, "gate", lambda self, ph: {"decision": "PASS"})
    with pytest.raises(ValueError, match="PROVIDED_LL_NOT_FROM_LL_WORK_ORDER"):
        WO.prepare(HAL_EX, "WO-HAL-3", "WO-LL-1")


def test_ll_prepare_records_the_layer(env):
    ws, man = WO.prepare(LL_EX, "WO-LL-P")
    assert man["layer"] == "LL" and man["provided"] == [] and LY.layer_of(ws) == "LL"


# ---- real tools on an LL-only workspace (no HAL sources) ---------------------------------------------------------
LL_H = """#ifndef STM32N6XX_LL_RCC_H
#define STM32N6XX_LL_RCC_H
#include <stdint.h>
#define LL_RCC_REG_COUNT 1024U
extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];
#define LL_RCC_CR_OFFSET 0x000U
#define LL_RCC_SR_OFFSET 0x004U
#define LL_RCC_CR_HSION_MSK 0x00000008U
#define LL_RCC_SR_HSIRDY_MSK 0x00000008U
static inline void LL_RCC_HSI_Enable(void)
{
    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSION_MSK;
}
static inline uint32_t LL_RCC_HSI_IsReady(void)
{
    return ((ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] & LL_RCC_SR_HSIRDY_MSK) != 0U) ? 1U : 0U;
}
#endif /* STM32N6XX_LL_RCC_H */
"""
LL_TARGET = ("#include \"stm32n6xx_ll_rcc.h\"\n#include \"forge_target_test.h\"\nFORGE_MAILBOX_DEFINE;\n"
             "int main(void)\n{\n    uint32_t n = 0U;\n    FORGE_TEST_BEGIN();\n    LL_RCC_HSI_Enable();\n"
             "    while ((LL_RCC_HSI_IsReady() == 0U) && (n < 1000U)) { n++; }\n"
             "    TCHECK(1, LL_RCC_HSI_IsReady() == {expect});\n"
             "    TCHECK(2, (ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) != 0U);\n"
             "    FORGE_TEST_END();\n    return 0;\n}\n")


def _ll_ws(tmp_path, monkeypatch, role, phase):
    import os

    ws = ws_with(tmp_path, "LL")
    for rel, txt in {LY.LL_HEADER: LL_H, LY.LL_TU: LY.LL_TU_TEXT}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt)
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")
    monkeypatch.setenv("FORGE_WORKSPACE", str(ws))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(ws / ".ev"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(ws / ".state"))
    monkeypatch.setitem(os.environ, "FORGE_ROLE", role)
    monkeypatch.setitem(os.environ, "FORGE_PHASE", phase)
    return ws


def _op(mod, name):
    return next(o for o in mod.OPERATIONS if o.name == name)


def test_ll_compiles_on_both_profiles_and_unit_tests_run(tmp_path, monkeypatch):
    import shutil

    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import build as B
    from forge_factory.mcp.servers import tests as T

    ws = _ll_ws(tmp_path, monkeypatch, "swe3-author", "SWE.3")
    profiles = ["host-clang"] + (["target-cm55-gcc"] if shutil.which("arm-none-eabi-gcc") else [])
    for prof in profiles:
        out = sdk.invoke("forge-build-mcp", _op(B, "compile"), {"profile": prof})
        assert out["status"] == "PASS", (prof, out)
    monkeypatch.setitem(__import__("os").environ, "FORGE_ROLE", "swe4-author")
    monkeypatch.setitem(__import__("os").environ, "FORGE_PHASE", "SWE.4")
    SC.scaffold(ws)
    ut = (ws / SC.UNIT_TEST).read_text()
    ut = ut.replace(SC.TEST_CASES_MARKER, "static void ut_hsi(void)\n{\n    ut_reset_regs();\n    LL_RCC_HSI_Enable();\n"
                    "    CHECK(\"UT-001\", (ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) != 0U);\n"
                    "    CHECK(\"UT-002\", LL_RCC_HSI_IsReady() == 0U);\n}\n" + SC.TEST_CASES_MARKER)
    (ws / SC.UNIT_TEST).write_text(ut.replace(SC.TEST_CALLS_MARKER, "ut_hsi();\n    " + SC.TEST_CALLS_MARKER))
    out = sdk.invoke("forge-tests-mcp", _op(T, "run_unit"), {"coverage": True})
    assert out["status"] == "PASS", out
    cov = sdk.invoke("forge-tests-mcp", _op(T, "llvm_coverage"), {"level": "unit"})
    assert cov["status"] == "PASS" and cov["metrics"]["line_pct"] == 100.0, cov  # header-only LL code is measured


def test_ll_runs_on_the_renode_target(tmp_path, monkeypatch):
    import shutil

    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import sim

    if not (sim.renode_bin() and shutil.which("arm-none-eabi-gcc")):
        pytest.skip("renode / GNU Arm not installed")
    ws = _ll_ws(tmp_path, monkeypatch, "swe5-author", "SWE.5")
    (ws / "software/tests/target").mkdir(parents=True)
    (ws / "software/tests/target/test_rcc_target.c").write_text(LL_TARGET.replace("{expect}", "1U"))
    (ws / "software/tests/target/test_rcc_target_timeout.c").write_text(LL_TARGET.replace("{expect}", "0U"))
    out = sdk.invoke("forge-sim-mcp", _op(sim, "run_renode"), {})
    assert out["status"] == "PASS", out
    assert out["metrics"]["passed"] == 4 and out["metrics"]["failed"] == 0
