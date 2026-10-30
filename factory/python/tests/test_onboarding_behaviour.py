"""Feature 016 OB-T016: behaviour facts (time base, waits, undelivered externals, instance comparisons, file map and
framework modules) from the real ST inputs, and the unbounded-wait and missing-header cases."""
import shutil

import pytest

from forge_factory.brownfield.scope import Definition
from forge_factory.common import REPO_ROOT
from forge_factory.onboarding import behaviour as B
from forge_factory.onboarding import identity as I
from onboarding_util import example_copy, need_inputs


def _derive(example):
    ctx = I.context(example)
    facts, v = I.derive(ctx)
    style = next(f.value for f in facts if f.name == "driver_style")
    bf, asm, dmap = B.derive(ctx, v, style)
    return {f.name: f for f in bf}, asm, dmap


def test_usart_hal_time_base_kernel_clock_and_host_instance():
    need_inputs()
    f, asm, _ = _derive(REPO_ROOT / "examples/0012d-st-cube-usart-hal")
    assert f["time_base"].value == "HAL_GetTick" and f["framework_modules"].value == ["UART", "RCC"]
    ext = {e["symbol"]: e for e in f["undelivered_externals"].value}
    assert ext["HAL_GetTick"]["role"] == "time_base" and ext["HAL_RCCEx_GetPeriphCLKFreq"]["feeds"] == ["BRR"]
    assert [(a.symbol, a.affects) for a in asm] == [("HAL_RCCEx_GetPeriphCLKFreq", ["USART_BRR"])]
    assert f["host_instance"].value == "USART1" and "HAL_UART_TIMEOUT_VALUE" in f["timeout_constants"].value
    assert {w["bound"] for w in f["waits"].value} == {"time_base"}


@pytest.mark.parametrize("example,mods,host", [("0014d-st-cube-crc-hal", ["CRC"], "NONE"),
                                               ("0013d-st-cube-tim-hal", ["TIM", "DMA"], "TIM2"),
                                               ("0011d-st-cube-spi-hal", ["SPI", "DMA"], "SPI1"),
                                               ("0010d-st-cube-gpio-hal", ["GPIO"], "GPIOA")])
def test_hal_modules_and_host_instances(example, mods, host):
    need_inputs()
    f, asm, dmap = _derive(REPO_ROOT / "examples" / example)
    assert f["framework_modules"].value == mods and f["host_instance"].value == host and asm == []
    assert any(d.get("configure") == {"hal_modules": mods} for d in dmap["dependencies"])


def test_an_unbounded_hardware_poll_is_classified_unbounded():
    d = Definition("LL_X_WaitReady", "x.h", 10, "static_inline", ["USARTx"],
                   "\n  while ((USARTx->ISR & USART_ISR_TEACK) == 0U)\n  {\n  }\n")
    cfg = Definition("Cfg", "x.c", 20, "function", ["init"], "\n  while ((init->Pin >> pos) != 0U) { pos++; }\n")
    w = B.waits({"LL_X_WaitReady": d, "Cfg": cfg}, None).value
    assert w == [{"function": "LL_X_WaitReady", "file": "x.h", "line": 11, "bound": "unbounded"}]


def test_a_header_no_package_declares_is_a_missing_input(tmp_path, monkeypatch):
    need_inputs()
    ex = example_copy(tmp_path, "0012d-st-cube-usart-hal")
    ctx = I.context(ex)
    hal = ctx.packages[0]["root"]
    cut = tmp_path / "hal"
    shutil.copytree(hal / "Inc", cut / "Inc")
    shutil.copytree(hal / "Src", cut / "Src")
    for x in cut.rglob("*"):
        x.chmod(0o755 if x.is_dir() else 0o644)
    cut.chmod(0o755)
    (cut / "Inc/stm32n6xx_hal_rcc_ex.h").unlink()
    (cut / "Inc/stm32n6xx_hal_rcc.h").write_text("/* removed for the test */\n")
    ctx.source = cut
    ctx.packages[0] = {**ctx.packages[0], "root": cut, "include_root": cut / "Inc"}
    facts, v = I.derive(ctx)
    bf, dmap = B.file_map_and_modules(ctx, v["defs"], "HAL_STANDALONE")
    assert {f.name: f.status for f in bf} == {"file_map": "NOT_DERIVED", "framework_modules": "NOT_DERIVED"}
    assert "HAL_RCCEx_GetPeriphCLKFreq" in dmap["missing"]
