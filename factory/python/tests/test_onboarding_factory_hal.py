"""Feature 016 OB-T066/OB-T067/OB-T069 (owner decisions 2026-11-11): the factory HAL on the factory's own LL
(driver style HAL_ON_LL) is onboarded from owner inputs and its LL lineage; its texts, scope and required operations
are generated (no hand text), pass the leftover check, and its budgets are owner-confirmed assumptions."""
import json
import shutil
import subprocess

import pytest
from forge_factory import onboarding as OB
from forge_factory.common import REPO_ROOT
from forge_factory.onboarding import approval as A
from forge_factory.onboarding import factory_hal as FH
from forge_factory.onboarding import leftovers as L
from forge_factory.onboarding.facts import value
from forge_factory.peripheral import load
from onboarding_util import factory_hal_example, need_inputs

HAL_KEYS = ("hal_requirement_example", "hal_reset_example", "hal_failure_responses", "hal_api", "hal_dynamic_view",
            "hal_wait_rule", "hal_example", "hal_wait_rest", "hal_contract_rule", "hal_ut_example", "hal_ut_rule",
            "hal_integration", "hal_effect_example", "hal_args_example", "hal_target_tests")


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    load.cache_clear()
    yield tmp_path
    load.cache_clear()


@pytest.mark.parametrize("pid", ["wwdg", "crc", "spi", "tim"])
def test_factory_hal_orders_derive_from_the_ll_lineage(pid, state):
    need_inputs()
    ex = factory_hal_example(state, pid)
    a = OB.derive(ex, ex.name, author_missing=False)
    assert a["status"] == "READY_FOR_OWNER" and a["driver_style"] == "HAL_ON_LL"
    assert value(a, "driver_style") == "HAL_ON_LL"
    assert not [g for g in a["gaps"] if g["kind"] in ("MISSING_INPUT", "NOT_DERIVED", "CONFLICT")], a["gaps"]
    assert value(a, "ll_api")["functions"] and value(a, "ll_lineage")["layer"] == "LL"
    assert any(i["role"] == "ll_lineage_work_order" for i in a["inputs"])
    assert [x["id"] for x in a["authored"]] == ["model"] and a["authored"][0]["status"] == "ACCEPTED"
    b = OB.derive(ex, ex.name, author_missing=False)
    assert b["sha256"] == a["sha256"]                                       # FR-006: deterministic


def test_a_changed_lineage_or_a_different_rm_input_changes_or_blocks(state):
    need_inputs()
    a = OB.derive(factory_hal_example(state / "a", "spi"), "K", author_missing=False)
    b = OB.derive(factory_hal_example(state / "b", "spi", ll_mutate=lambda s: s["delivery"]["scope"].update(
        note=s["delivery"]["scope"]["note"] + ".")), "K", author_missing=False)
    assert a["sha256"] != b["sha256"]                                       # the lineage work order is an input
    c = OB.derive(factory_hal_example(state / "c", "spi", replace_inputs={"RM0486-rev4-ch67-spi.md": lambda t: t + "\n"}),
                  "K2", author_missing=False)
    assert c["status"] == "BLOCKED"
    assert any(g["kind"] == "MISSING_INPUT" and g["ref"] == "ll_lineage_rm_chapter" for g in c["gaps"])


def test_an_invalid_or_missing_lineage_is_refused(state):
    ex = factory_hal_example(state, "spi", mutate=lambda s: s["onboarding"].update(ll_example="../0011l"))
    with pytest.raises(FH.FactoryHalError, match="ONBOARDING_LL_EXAMPLE_INVALID"):
        OB.derive(ex, "K", author_missing=False)
    ex2 = factory_hal_example(state / "x", "spi", mutate=lambda s: s["onboarding"].update(ll_example="0099z-none"))
    with pytest.raises(FH.FactoryHalError, match="ONBOARDING_LL_EXAMPLE_MISSING"):
        OB.derive(ex2, "K", author_missing=False)


def test_ll_api_kinds_and_register_effects(state):
    need_inputs()
    spi = OB.derive(factory_hal_example(state / "s", "spi"), "S", author_missing=False)
    f = {x["name"]: x for x in value(spi, "ll_api")["functions"]}
    assert f["LL_SPI_Enable"]["kind"] == "main_enable" and f["LL_SPI_IsEnabled"]["kind"] == "main_enable_query"
    assert f["LL_SPI_SetBaudRatePrescaler"]["kind"] == "setter"
    assert f["LL_SPI_SetBaudRatePrescaler"]["effects"] == [{"register": "SPI_CFG1", "fields": ["MBR", "BPASS"],
                                                           "op": "write", "value": "param"}]
    assert f["LL_SPI_IsActiveFlag_RXP"]["effects"] == [{"register": "SPI_SR", "fields": ["RXP"], "op": "read"}]
    assert f["LL_SPI_ClearFlag_EOT"]["effects"] == [{"register": "SPI_IFCR", "fields": ["EOTC"], "op": "set"}]
    assert f["LL_SPI_TransmitData8"]["kind"] == "write" and f["LL_SPI_ReceiveData8"]["kind"] == "read"
    tim = OB.derive(factory_hal_example(state / "t", "tim"), "T", author_missing=False)
    g = {x["name"]: x for x in value(tim, "ll_api")["functions"]}
    assert g["LL_TIM_EnableCounter"]["kind"] == "main_enable"                # sets TIM_CR1.CEN, bit 0 at offset 0
    assert g["LL_TIM_EnableARRPreload"]["kind"] == "toggle_enable"
    assert g["LL_TIM_ClearFlag_UPDATE"]["effects"] == [{"register": "TIM_SR", "fields": ["UIF"], "op": "write",
                                                        "value": 0}]          # rc_w0: written 0


@pytest.mark.parametrize("pid", ["wwdg", "crc", "spi", "tim"])
def test_generated_texts_are_complete_have_origins_and_no_leftover(pid, state):
    need_inputs()
    ex = factory_hal_example(state, pid)
    pkg = OB.derive(ex, ex.name, author_missing=False)
    prompt = pkg["texts"]["prompt"]
    assert set(HAL_KEYS) <= set(prompt) and {"swe1_cover", "ll_api", "target_model", "ut_example"} <= set(prompt)
    assert all(v["from"].split(":")[0] in ("template", "owner", "model") and v["text"]
               for g in pkg["texts"].values() for v in g.values())
    assert not any("HAL_TIMEOUT" in prompt[k]["text"] for k in ("hal_wait_rule", "hal_failure_responses",
                                                                "hal_dynamic_view"))  # no-wait HAL (CAPA-126 path)
    assert L.run(ex.name, ex) == []                                         # OB-T067 AC: 0 leftover findings
    from forge_factory.onboarding import identity, texts

    ctx, _hal, _m = FH.context(ex)
    assert json.loads(json.dumps(texts.generate(ctx, pkg))) == pkg["texts"]  # regenerated from the package alone


@pytest.mark.parametrize("planted,token", [("call LL_CRC_FeedData32(CRC) first", "LL_CRC_FeedData32"),
                                           ("check SPI_CFG1.NOSUCHFIELD", "SPI_CFG1.NOSUCHFIELD"),
                                           ("wait for the oscillator", "oscillator"),
                                           ("call HAL_SPI_Transmit", "HAL_SPI_Transmit")])
def test_planted_leftovers_in_a_factory_hal_are_caught(planted, token, state):
    need_inputs()
    ex = factory_hal_example(state, "spi")
    OB.derive(ex, ex.name, author_missing=False)
    root = OB.onboarding_dir(ex.name)
    pkg = json.loads((root / "onboarding/package.json").read_text())
    pkg["texts"]["prompt"]["hal_api"]["text"] += " " + planted
    pkg["sha256"] = OB.facts.canonical_hash(pkg)
    (root / "onboarding/package.json").write_text(json.dumps(pkg))
    assert any(x.endswith(":" + token) for x in L.run(ex.name, ex))


def test_the_derived_profile_names_the_instance_and_the_required_operations(state):
    need_inputs()
    from forge_factory.onboarding.profile import derived_profile

    conf = lambda p: {"assumption_confirmations": [{"id": a["id"], "value": 1} for a in p["assumptions"]]}  # noqa
    spi = OB.derive(factory_hal_example(state / "s", "spi"), "S", author_missing=False)
    prof = derived_profile(spi, conf(spi), "SPI HAL driver")
    assert prof["ll"]["header"] == "stm32n6xx_ll_spi.h" and prof["hal"]["header"] == "stm32n6xx_hal_spi.h"
    assert prof["hal"]["function_prefix"] == "HAL_SPI_" and prof["hal"]["host_instance"] == "SPI1"
    ops = prof["semantic_required_operations"]
    assert 1 <= len(ops) <= 32 and {"register": "SPI_CR1", "field": "SPE", "action": "set_field"} in ops
    assert "work_order" not in prof and set(HAL_KEYS) <= set(prof["prompt"])
    ww = OB.derive(factory_hal_example(state / "w", "wwdg"), "W", author_missing=False)
    assert "host_instance" not in derived_profile(ww, conf(ww))["hal"]     # WWDG: the instance is the prefix


def test_scope_and_budget_assumptions_and_the_owner_summary(state):
    need_inputs()
    spec = json.loads((REPO_ROOT / "examples/0011m-spi-hal/workorder.json").read_text())
    assert "scope" not in spec and "delivery" not in spec and "peripheral" not in spec  # owner inputs only
    assert not any(k.startswith("prompt") for k in spec)
    ex = factory_hal_example(state, "spi")
    pkg = OB.derive(ex, ex.name, author_missing=False)
    sc = pkg["texts"]["work_order"]["scope"]["text"]
    assert sc[0].startswith("HAL: hal_status_t API with HAL_SPI_ prefix") and "0011l-st-cube-spi-swe1-gen" in sc[0]
    assert any(s.startswith("Parameter checks before any register write") for s in sc)
    asm = {a["id"]: a for a in pkg["assumptions"]}
    assert set(asm) == {"ASM-BUDGET-FLASH", "ASM-BUDGET-RAM", "ASM-BUDGET-STACK", "ASM-SIM-PERF-INSTRUCTIONS",
                        "ASM-SIM-PERF-MICROSECONDS", "ASM-SIM-PERF-MIPS"}
    assert asm["ASM-BUDGET-FLASH"]["proposed_value"] == 4096 and asm["ASM-SIM-PERF-MIPS"]["proposed_value"] == 100
    root = OB.onboarding_dir(ex.name)
    page = A.summary(root).read_text()
    assert "## Generated work-order scope" in page and "hal_status_t HAL_SPI_Init(const hal_spi_config_t" in page
    tmpl = json.loads((root / A.TEMPLATE).read_text())
    assert {c["id"] for c in tmpl["assumption_confirmations"]} == set(asm)


@pytest.fixture
def signer(tmp_path):
    if not shutil.which("ssh-keygen"):
        pytest.skip("ssh-keygen not installed")
    key = tmp_path / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    allowed = tmp_path / "allowed"
    allowed.write_text(f"tester {key.with_suffix('.pub').read_text()}")
    return key, allowed


def _sign(root, key, drop=None):
    a = json.loads((root / A.TEMPLATE).read_text())
    a.update(approval_id="OA-2026-11-11-01", decided_by="tester", decided_on="2026-11-11")
    if drop:
        for c in a["assumption_confirmations"]:
            if c["id"] == drop:
                c["value"] = None
    (root / A.APPROVAL).write_text(json.dumps(a))
    (root / f"{A.APPROVAL}.sig").unlink(missing_ok=True)
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", A.NAMESPACE, str(root / A.APPROVAL)],
                   check=True)
    return a


def test_unconfirmed_budgets_are_refused_and_confirmed_ones_apply(state, signer):
    """A throwaway test key: the factory never signs an owner approval."""
    need_inputs()
    key, allowed = signer
    ex = factory_hal_example(state, "spi")
    pkg = OB.derive(ex, ex.name, author_missing=False)
    root = OB.onboarding_dir(ex.name)
    A.summary(root)
    _sign(root, key, drop="ASM-SIM-PERF-MIPS")
    assert A.verify(root, allowed)["code"] == "APPROVAL_INCOMPLETE:assumption"
    appr = _sign(root, key)
    assert A.verify(root, allowed)["code"] == "APPROVAL_OK"
    budgets, sim = FH.confirmed_budgets(json.loads((ex / "workorder.json").read_text()), pkg, appr)
    assert budgets["flash_bytes"] == 4096 and "OA-2026-11-11-01" in budgets["status"]
    assert sim == {"schema": FH.SIM_PERF_SCHEMA, "instructions_per_call": 2000, "microseconds_per_call": 1000,
                   "performance_mips": 100, "test_source": "software/tests/target/test_performance.c"}


HDR = ("__STATIC_INLINE void LL_SPI_Enable(SPI_TypeDef *SPIx)\n{\n  SET_BIT(SPIx->CR1, SPI_CR1_SPE);\n}\n"
       "__STATIC_INLINE uint32_t LL_SPI_IsEnabled(const SPI_TypeDef *SPIx)\n{\n  return 0U;\n}\n")


def test_the_provided_ll_instance_follows_the_profile_instance(monkeypatch):
    """SPI1 is an SPI_TypeDef: the provided-LL calls, register rule and host mapping use SPI1 with the SPI_ masks and
    forge_host_spi; a profile without host_instance (CRC, WWDG) keeps the exact old result."""
    from forge_factory.brownfield import cmsis
    from forge_factory.workflow import prompts as PR

    api = cmsis.instance_api(HDR, "SPI1")
    assert api["instance"] == "SPI1" and api["prefix"] == "SPI" and api["calls"]["LL_SPI_Enable"] == "LL_SPI_Enable(SPI1)"
    old = cmsis.instance_api(HDR.replace("SPI", "CRC"))
    assert old["instance"] == "CRC" and "prefix" not in old
    text = PR.provided_registers("self-checking host program exercising HAL+LL together; on HAL return values and "
                                 "ll_spi_regs[LL_SPI_<REG>_OFFSET / 4U] bits. No printf, no stdlib, no ll_spi_regs "
                                 "definition (the linker places it).", api)
    assert "SPI1-><REG> & the device header's SPI_<REG>_<FIELD>_Msk" in text
    assert "forge_host_spi;" in text and "forge_host_spi1" not in text and "SPI1_TypeDef" not in text
    monkeypatch.setattr("forge_factory.layer.profile", lambda ws: {"hal": {"host_instance": "SPI1"}})
    m = cmsis.provided_concrete(None, "SPI", "forge_host_spi")
    assert "#define SPI1 (&forge_host_spi)" in m and "#define SPI1_S (&forge_host_spi)" in m
    monkeypatch.setattr("forge_factory.layer.profile", lambda ws: {"hal": {}})
    assert cmsis.provided_concrete(None, "CRC", "forge_host_crc") == ""
