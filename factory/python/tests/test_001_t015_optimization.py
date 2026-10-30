"""SPEC-001 T-015: footprint + per-call instruction-count collectors (Renode, cycle proxy per OD-2026-10-19-05), a
baseline comparator and a Pareto report; read-only on packages, deterministic counts, honest NOT_COMPARABLE."""
import json
import shutil
import zipfile

import pytest
from forge_factory import optimization as O
from forge_factory.mcp.servers import sim
from test_easa_register_contract import CALLS, EFFECTS, HAL_C, HAL_H, LL

needs_target = pytest.mark.skipif(not (sim.renode_bin() and shutil.which("arm-none-eabi-gcc")),
                                  reason="Renode or GNU Arm not installed")


def _pkg(tmp_path, name, hal_c=HAL_C, flash=600, frame=8, contract=True, flat_copy=False):
    p = tmp_path / f"{name}-review.zip"
    files = {"software/ll/stm32n6xx_ll_rcc.h": LL, "software/hal/stm32n6xx_hal_rcc.h": HAL_H,
             "software/hal/stm32n6xx_hal_rcc.c": hal_c,
             **({"software/src/stm32n6xx_hal_rcc.c": hal_c} if flat_copy else {}),  # real packages: flat view too
             "verification/footprint/memory_stack_summary.json": json.dumps(
                 {"flash_bytes": flash, "ram_bytes": 0, "max_frame_bytes": frame, "scope": "object-level"})}
    if contract:
        files.update({O.EFFECTS: json.dumps(EFFECTS), O.CALLS: json.dumps(CALLS)})
    with zipfile.ZipFile(p, "w") as z:
        for k, v in files.items():
            z.writestr("evidence/" + k, v)
    return p


def test_comparator_and_pareto_on_given_measurements():
    a = {"package": "a", "flash_bytes": 600, "ram_bytes": 0, "max_frame_bytes": 8,
         "instructions": {"X": {"instructions": 40}, "Y": {"instructions": 10}}}
    b = {"package": "b", "flash_bytes": 560, "ram_bytes": 0, "max_frame_bytes": 8,
         "instructions": {"X": {"instructions": 52}, "Y": {"instructions": 10}, "Z": {"instructions": 3}}}
    c = {"package": "c", "flash_bytes": 640, "ram_bytes": 0, "max_frame_bytes": 16,
         "instructions": {"X": {"instructions": 60}, "Y": {"instructions": 12}}}
    r = O.compare(a, b)
    assert r["common_cases"] == ["X", "Y"] and r["overall"] == "TRADE_OFF"
    assert r["metrics"]["flash_bytes"]["verdict"] == "BETTER" and r["metrics"]["instructions_common"]["delta"] == 12
    assert O.compare(a, c)["overall"] == "DOMINATED"
    assert O.pareto([a, b, c])["pareto_front"] == ["a", "b"]
    assert O.compare(a, {**b, "instructions": {}})["metrics"]["instructions_common"]["verdict"] == "NOT_COMPARABLE"


def test_package_without_register_contract_reports_it_and_stays_unchanged(tmp_path):
    m = O.collect(_pkg(tmp_path, "old", contract=False))
    assert m["instructions_status"].startswith("NO_REGISTER_CONTRACT") and m["flash_bytes"] == 600
    assert m["archive_unchanged"]


@needs_target
def test_renode_counts_per_call_are_deterministic_and_see_a_slower_driver(tmp_path):
    fast = O.collect(_pkg(tmp_path, "fast"))
    assert fast["instructions_status"] == "MEASURED" and fast["archive_unchanged"], fast
    assert all(v["status"] == "OK" and v["instructions"] > 0 for v in fast["instructions"].values()), fast
    slow_c = HAL_C.replace("    LL_RCC_HSE_Enable();\n", "    for (count = 0U; count < 50U; count++) { __asm volatile(\"nop\"); }\n"
                                                             "    count = 0U;\n    LL_RCC_HSE_Enable();\n")
    (tmp_path / "s").mkdir()
    slow = O.collect(_pkg(tmp_path / "s", "slow", hal_c=slow_c))
    assert slow["instructions_status"] == "MEASURED", slow
    assert slow["instructions"]["HSE_ENABLE"]["instructions"] > fast["instructions"]["HSE_ENABLE"]["instructions"]
    assert O.compare(fast, slow)["metrics"]["instructions_common"]["verdict"] == "WORSE"


@needs_target
def test_capa048_real_package_layout_with_the_flat_src_copy_links_once(tmp_path):
    """CAPA-048 (batch d376c70, HAL r161-r164): sealed packages carry the HAL unit in software/hal AND software/src;
    the benchmark image linked both (multiple definition) and every case was BASE_BUILD_FAIL while the status said
    MEASURED."""
    m = O.collect(_pkg(tmp_path, "flat", flat_copy=True))
    assert m["instructions_status"] == "MEASURED", m
    assert all(v["status"] == "OK" and v["instructions"] > 0 for v in m["instructions"].values()), m
    # F015-T065: target images link with --gc-sections, so an unreferenced broken function would be discarded; the
    # undefined reference sits in a HAL function the benchmark runs (as slow_c above edits the same line)
    bad = "int undefined_symbol(void);\n" + HAL_C.replace("    LL_RCC_HSE_Enable();\n",
                                                          "    LL_RCC_HSE_Enable();\n    (void)undefined_symbol();\n", 1)
    (tmp_path / "b").mkdir()
    n = O.collect(_pkg(tmp_path / "b", "broken", hal_c=bad))
    assert n["instructions_status"].startswith("NOT_MEASURED:"), n                  # no number -> never MEASURED
