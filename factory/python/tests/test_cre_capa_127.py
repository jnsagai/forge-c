"""CAPA-127: SWE.5/SWE.6 of a no-wait HAL (CRC) ask for no timeout target file, never_ready scenario or timeout paths,
and the SWE.5 BOUNDARY_INTEGRATION category is decided per profile (RCC pattern kept; a time-base HAL's timeout
constant; a no-wait HAL's count of 0 or field limits from the register contract)."""
import json
import re

import pytest
from forge_factory import layer
from forge_factory.assurance import register_contract as RC
from forge_factory.assurance import target as T
from forge_factory.assurance import verifiers
from forge_factory.workflow import builder

MISSING = "INTEGRATION_CATEGORY_MISSING:boundary"
CRC_IDX = {"CRC_CR": {"offset": 8, "fields": {"POLYSIZE": {"msb": 4, "lsb": 3}, "RESET": {"msb": 0, "lsb": 0}}},
           "CRC_POL": {"offset": 20, "fields": {"POL": {"msb": 31, "lsb": 0}}}}
CRC_EFFECTS = [{"case": "SIZE", "swr": "SWR-003", "register": "CRC_CR", "field": "POLYSIZE", "op": "write", "value": 0},
               {"case": "POL", "swr": "SWR-001", "register": "CRC_POL", "field": "POL", "op": "write", "value": "0x1"},
               {"case": "RST", "swr": "SWR-006", "register": "CRC_CR", "field": "RESET", "op": "write", "value": 1},
               {"case": "BAD", "swr": "SWR-013", "op": "no_write", "status": "HAL_ERROR"}]


def _prompt(pid, node, lyr="HAL"):
    dot = builder.build("WO-CAPA-127", chunk_lines=150, layer=lyr, trace=True, isolation=True, peripheral=pid)[0]
    return re.search(rf'  {node} \[.*?prompt="((?:\\.|[^"\\])*)"', dot, re.S).group(1)


@pytest.mark.parametrize("lyr", ["HAL", "LL+HAL"])
def test_no_wait_hal_swe5_swe6_prompts_have_no_timeout_tests(lyr):
    s5, s6 = _prompt("crc", "swe5_author", lyr), _prompt("crc", "swe6_test_author", lyr)
    for p in (s5, s6):
        assert not re.search(r"_timeout\.c|never_ready|timeout paths|timeout behaviour", p)
    assert "write the software/tests/target/test_*.c files of the target-test step yourself" in s5
    assert "(error paths, measured sizes)" in s5


def test_waiting_hal_and_crc_ll_keep_their_swe5_swe6_prompts(monkeypatch):
    iwdg5 = _prompt("iwdg", "swe5_author")
    assert "test_iwdg_target_timeout.c" in iwdg5 and "(timeout paths, measured sizes)" in iwdg5
    assert "scenario=never_ready" in _prompt("iwdg", "swe6_test_author")
    ll = builder.build("WO-CAPA-127", chunk_lines=150, layer="LL", trace=True, peripheral="crc")[0]
    monkeypatch.setattr(layer, "hal_waits_of", lambda p: True)
    assert builder.build("WO-CAPA-127", chunk_lines=150, layer="LL", trace=True, peripheral="crc")[0] == ll


def _ws(tmp_path, pid, text, lyr="HAL", effects=None, name="t"):
    ws = tmp_path / f"{pid}-{lyr}-{name}"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"peripheral": pid, "layer": lyr}))
    (ws / "software/tests/integration").mkdir(parents=True)
    (ws / f"software/tests/integration/test_{pid}_integration.c").write_text(text)
    if effects is not None:
        (ws / "workproducts/SWE.1").mkdir(parents=True)
        (ws / RC.EFFECTS).write_text(json.dumps({"schema": "forge-c/register-effects/1", "effects": effects}))
    return ws


def _missing(ws):
    return MISSING in verifiers.v_integration(ws)["findings"]


def test_boundary_rule_per_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(RC, "_rm_index", lambda ws: CRC_IDX)
    rcc = T.boundary_rule(_ws(tmp_path, "rcc", ""))
    assert rcc["timeout_const"] is None and not rcc["zero_count"]  # RCC: the RCC pattern only
    iw = T.boundary_rule(_ws(tmp_path, "iwdg", ""))
    assert iw["timeout_const"] and not iw["zero_count"] and iw["field_limits"] == []
    crc = T.boundary_rule(_ws(tmp_path, "crc", "", effects=CRC_EFFECTS))
    assert crc["zero_count"] and crc["field_limits"] == [3, 4]  # 2-bit POLYSIZE; 1-bit RESET and 32-bit POL give none
    ll = T.boundary_rule(_ws(tmp_path, "crc", "", lyr="LL", effects=CRC_EFFECTS))
    assert not ll["zero_count"] and ll["field_limits"] == []  # an LL work order keeps the RCC pattern


@pytest.mark.parametrize("pid,text,missing", [
    ("rcc", "st = HAL_RCC_HSI_Enable(1001U);", False),
    ("rcc", "st = HAL_RCC_HSI_Enable(HAL_RCC_TIMEOUT_VALUE + 1U);", False),
    ("rcc", "st = HAL_RCC_HSI_Enable(10U);", True),
    ("rcc", "st = HAL_RCC_HSI_Enable(HAL_RCC_TIMEOUT_MS + 1U);", True),  # not a time-base HAL: no new rule
    ("iwdg", "st = HAL_IWDG_Init(&cfg, HAL_IWDG_TIMEOUT_MS + 1U);", False),
    ("iwdg", "timeout = HAL_IWDG_TIMEOUT_MS + 1U;\nst = HAL_IWDG_Init(&cfg, timeout);", False),
    ("iwdg", "st = HAL_IWDG_Init(&cfg, HAL_IWDG_TIMEOUT_MS);", False),  # the maximum, like RCC's 1000
    ("iwdg", "st = HAL_IWDG_Init(&cfg, 10U); /* HAL_IWDG_TIMEOUT_MS + 1U */", True),  # comments do not count
    ("iwdg", "st = HAL_IWDG_Init(&cfg, 10U);", True),
    ("crc", "st = HAL_CRC_Calculate(words, 0U, &crc);", False),
    ("crc", "st = HAL_CRC_Init(&(const hal_crc_config_t){ .polynomial_size = 4U });", False),
    ("crc", "bad.polynomial_size = 3U;\nst = HAL_CRC_Init(&bad);", False),
    ("crc", "st = HAL_CRC_Calculate(words, 2U, &crc);\nTCHECK(3, st == HAL_OK); TCHECK(4, crc == 1U);", True),
    ("crc", "st = HAL_CRC_Calculate(words, 1U, &crc);\nCHECK(\"IT-04\", st == HAL_OK);", True),
])
def test_boundary_category(tmp_path, monkeypatch, pid, text, missing):
    monkeypatch.setattr(RC, "_rm_index", lambda ws: CRC_IDX)
    assert _missing(_ws(tmp_path, pid, text, effects=CRC_EFFECTS if pid == "crc" else None)) is missing


def test_no_rule_keeps_the_rcc_pattern():
    assert "boundary" in T.integration_categories({"t.c": "HAL_IWDG_Init(&c, HAL_IWDG_TIMEOUT_MS + 1U);"}, set(),
                                                  "IWDG")["missing"]
    assert T.boundary_present("HAL_X(0U);") and not T.boundary_present("HAL_CRC_Calculate(w, 0U, &c);")
