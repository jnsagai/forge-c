"""Feature 008 US1 - brownfield intake: validated, fingerprinted, scoped and build-checked before any agent runs; the
delivery stays outside the workspace (FR-001..FR-006, FR-019)."""
import json

import pytest
from brownfield_fixtures import EX, HEADER, SCOPE, example_copy
from forge_factory import workorder as WO
from forge_factory.brownfield import delivery as D
from forge_factory.brownfield import scope as S
from forge_factory.common import sha256_bytes


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    return tmp_path


def test_example_delivery_is_valid_against_the_contract():
    assert D.validate(json.loads((EX / "workorder.json").read_text())["delivery"]) == []


def test_intake_accepts_fingerprints_scopes_and_keeps_the_code_out_of_the_workspace(tmp_path):
    ws, man = WO.prepare(example_copy(tmp_path), "WO-BF-1")
    assert man["code_mode"] == "FROZEN" and man["delivery_intake"] == {
        "status": "ACCEPTED", "build_check": "PASS", "store": str(D.store_dir("WO-BF-1"))}
    by = {d["path"]: d for d in man["delivered"]}
    assert by["software/ll/stm32n6xx_ll_rcc.h"]["sha256"] == sha256_bytes(HEADER.encode())
    assert {d["role"] for d in man["delivered"]} == {"delivered_code"}
    assert not (ws / "software").exists()  # FR-007: no delivered code before SWE.1 is frozen
    scope = json.loads((D.store_dir("WO-BF-1") / "scope.json").read_text())
    assert [f["name"] for f in scope["functions"]] == SCOPE and scope["excluded"] == []
    stored = D.stored("WO-BF-1")
    assert stored["software/ll/stm32n6xx_ll_rcc.h"] == HEADER.encode()
    assert all((D.store_dir("WO-BF-1") / "files" / p).stat().st_mode & 0o222 == 0 for p in stored)


@pytest.mark.parametrize("mutate, issue", [
    (lambda s: s["delivery"]["scope"]["functions"].append("LL_RCC_PLL1_Enable"),
     "DELIVERY_SCOPE_FUNCTION_NOT_FOUND:LL_RCC_PLL1_Enable"),
    (lambda s: s["delivery"].update(licence=" "), "DELIVERY_LICENCE_MISSING"),
    (lambda s: s["delivery"].update(origin="   "), "DELIVERY_ORIGIN_MISSING"),
    (lambda s: s["delivery"].update(code_mode="FIX_ALLOWED", licence_allows_modification=False),
     "DELIVERY_MODE_FORBIDDEN_BY_LICENCE:FIX_ALLOWED"),
    (lambda s: s["delivery"]["files"].append({"from": "../../workorder.json", "to": "software/src/x.c"}),
     "DELIVERY_FILE_MISSING_OR_OUTSIDE_SOURCE:../../workorder.json"),
    (lambda s: s["delivery"].pop("licence"), "DELIVERY_SPEC_INVALID"),
])
def test_intake_refusals_stop_before_any_workspace(tmp_path, mutate, issue):
    with pytest.raises(D.DeliveryBlocked) as exc:
        WO.prepare(example_copy(tmp_path, mutate=mutate), "WO-BF-2")
    assert issue in str(exc.value)
    rec = json.loads((D.store_dir("WO-BF-2") / "intake.json").read_text())
    assert rec["status"] == "BLOCKED" and any(i.startswith(issue) for i in rec["issues"])
    assert not (D.store_dir("WO-BF-2") / "files").exists()


def test_build_failure_blocks_with_the_build_evidence(tmp_path):
    with pytest.raises(D.DeliveryBlocked, match="DELIVERY_BUILD_FAIL"):
        WO.prepare(example_copy(tmp_path, header=HEADER.replace("#endif", "int broken(void) { return }\n#endif")),
                   "WO-BF-3")
    rec = json.loads((D.store_dir("WO-BF-3") / "intake.json").read_text())
    assert rec["build_check"]["status"] == "FAIL" and rec["build_check"]["exit_code"] != 0
    assert "error" in rec["build_check"]["log"]


def test_functions_outside_the_scope_are_listed_as_excluded(tmp_path):
    ex = example_copy(tmp_path, mutate=lambda s: s["delivery"]["scope"].update(functions=SCOPE[:4]))
    WO.prepare(ex, "WO-BF-4")
    scope = json.loads((D.store_dir("WO-BF-4") / "scope.json").read_text())
    assert len(scope["functions"]) == 4 and scope["excluded_count"] == 12 and "LL_RCC_ADC12_Enable" in scope["excluded"]


def test_greenfield_prepare_is_unchanged(tmp_path):
    from forge_factory.common import REPO_ROOT

    _ws, man = WO.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-GF-1")
    assert "delivery" not in man and "code_mode" not in man and "delivered" not in man


def test_intake_only_cli_and_blocked_cli(tmp_path, capsys):
    assert WO.main(["--example", str(example_copy(tmp_path)), "--wo", "WO-BF-5", "--intake-only"]) == 0
    assert json.loads(capsys.readouterr().out)["intake"]["status"] == "ACCEPTED"
    bad = example_copy(tmp_path, mutate=lambda s: s["delivery"].update(licence=""), name="bad")
    assert WO.main(["--example", str(bad), "--wo", "WO-BF-6", "--intake-only"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "BLOCKED" and out["stage"] == "delivery_intake"


def test_c_index_and_register_effects_both_styles():
    defs = {d.name: d for d in S.index(HEADER, "h")}
    assert len(defs) == 16 and defs["LL_RCC_HSI_Enable"].kind == "static_inline"
    mac = S.constant_macros([HEADER])
    eff = S.register_effects(defs["LL_RCC_GPDMA1_ReleaseReset"], mac, "forge", defs=defs)
    assert [(e.register, e.op, S.bits(e.mask)) for e in eff] == [("RCC_AHB1RSTR", "clear", [4])]
    cmsis = ("#define RCC_CSR_HSIONS_Pos (3U)\n#define RCC_CSR_HSIONS_Msk (0x1UL << RCC_CSR_HSIONS_Pos)\n"
             "#define RCC_CSR_HSIONS RCC_CSR_HSIONS_Msk\n#define RCC_AHB1ENR_GPDMA1EN (0x1UL << 4U)\n"
             "#define LL_AHB1_GRP1_PERIPH_GPDMA1 RCC_AHB1ENR_GPDMA1EN\n"
             "/* comment with fake(void) { } */\n#if 0\nvoid dead(void) { RCC->CR = 0U; }\n#endif\n"
             "__STATIC_INLINE void LL_RCC_HSI_Enable(void)\n{\n  WRITE_REG(RCC->CSR, RCC_CSR_HSIONS);\n}\n"
             "__STATIC_INLINE void LL_AHB1_GRP1_EnableClock(uint32_t Periphs)\n{\n  __IO uint32_t tmpreg;\n"
             "  WRITE_REG(RCC->AHB1ENSR, Periphs);\n  tmpreg = READ_REG(RCC->AHB1ENR);\n  (void)tmpreg;\n}\n")
    cd = {d.name: d for d in S.index(cmsis, "c")}
    assert set(cd) == {"LL_RCC_HSI_Enable", "LL_AHB1_GRP1_EnableClock"}
    cm = S.constant_macros([cmsis])
    e1 = S.register_effects(cd["LL_RCC_HSI_Enable"], cm, "cmsis")
    assert [(e.register, e.op, e.via, e.mask) for e in e1] == [("RCC_CR", "set", "RCC_CSR", 8)]
    e2 = S.register_effects(cd["LL_AHB1_GRP1_EnableClock"], cm, "cmsis", ["LL_AHB1_GRP1_PERIPH_GPDMA1"])
    assert [(e.register, e.op, e.via, e.mask) for e in e2 if e.op != "read"] == [("RCC_AHB1ENR", "set", "RCC_AHB1ENSR", 16)]
