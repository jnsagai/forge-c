"""CHANGE (owner 2026-11-03 "go with other small HAL than RCC"): the WWDG profile gets its own HAL prompt texts. The
WWDG HAL has no wait (RM0486 ch.60: activation and refresh are WWDG_CR writes, the configuration a WWDG_CFR write, and
WWDG_SR holds only the early wake-up flag), so - like CRC - it gets no HAL_TIMEOUT path, timeout requirement or timeout
target file, and the CAPA-127 boundary rule uses its field limits. Without these texts CAPA-124 fell back to the RCC
'waits' default for WWDG."""
import json
import re

import pytest
from forge_factory import layer, peripheral
from forge_factory.assurance import register_contract as RC
from forge_factory.assurance import target as T
from forge_factory.common import REPO_ROOT
from forge_factory.inspection.views import check_views
from forge_factory.workflow import builder

RM = REPO_ROOT / "examples/0016-wwdg-st/inputs/RM0486-rev4-ch60-wwdg.md"
LL_EXAMPLE = REPO_ROOT / "examples/0016c-st-cube-wwdg/workorder.json"
HAL_KEYS = ("hal_requirement_example", "hal_reset_example", "hal_failure_responses", "hal_api", "hal_dynamic_view",
            "hal_wait_rule", "hal_example", "hal_wait_rest", "hal_contract_rule", "hal_ut_example", "hal_ut_rule",
            "hal_integration", "hal_effect_example", "hal_args_example", "hal_target_tests")
WWDG_IDX = {"WWDG_CR": {"offset": 0, "fields": {"WDGA": {"msb": 7, "lsb": 7}, "T": {"msb": 6, "lsb": 0}}},
            "WWDG_CFR": {"offset": 4, "fields": {"WDGTB": {"msb": 13, "lsb": 11}, "EWI": {"msb": 9, "lsb": 9},
                                                  "W": {"msb": 6, "lsb": 0}}},
            "WWDG_SR": {"offset": 8, "fields": {"EWIF": {"msb": 0, "lsb": 0}}}}
WWDG_EFFECTS = [
    {"case": "INIT_PRESCALER", "swr": "SWR-001", "register": "WWDG_CFR", "field": "WDGTB", "op": "write", "value": 3},
    {"case": "INIT_WINDOW", "swr": "SWR-002", "register": "WWDG_CFR", "field": "W", "op": "write", "value": "0x50"},
    {"case": "INIT_COUNTER", "swr": "SWR-003", "register": "WWDG_CR", "field": "T", "op": "write", "value": "0x7F"},
    {"case": "INIT_ACTIVATE", "swr": "SWR-004", "register": "WWDG_CR", "field": "WDGA", "op": "set"},
    {"case": "CLEAR_FLAG", "swr": "SWR-008", "register": "WWDG_SR", "field": "EWIF", "op": "write", "value": 0},
    {"case": "BAD_WINDOW", "swr": "SWR-010", "op": "no_write", "status": "HAL_ERROR"}]


def _dot(pid, lyr="HAL", **kw):
    return builder.build("WO-WWDG-HAL", chunk_lines=150, layer=lyr, trace=True, isolation=True, peripheral=pid, **kw)[0]


def _prompt(dot, node):
    return re.search(rf'  {node} \[.*?prompt="((?:\\.|[^"\\])*)"', dot, re.S).group(1)


def _ws(tmp, lyr="HAL", effects=None, name="t"):
    ws = tmp / f"wwdg-{lyr}-{name}"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"peripheral": "wwdg", "layer": lyr}))
    if effects is not None:
        (ws / "workproducts/SWE.1").mkdir(parents=True)
        (ws / RC.EFFECTS).write_text(json.dumps({"schema": "forge-c/register-effects/1", "effects": effects}))
    return ws


def test_the_wwdg_profile_states_every_hal_text_and_no_wait():
    p = peripheral.load("wwdg")
    t = p["prompt"]
    assert all(k in t for k in HAL_KEYS), [k for k in HAL_KEYS if k not in t]
    assert not p["hal"].get("time_base")
    assert not any("HAL_TIMEOUT" in t[k] for k in layer.HAL_WAIT_TEXTS)
    assert layer.hal_waits_of(p) is False
    assert "returns without waiting on a WWDG flag" in t["hal_failure_responses"]
    for name in ("HAL_WWDG_Init", "HAL_WWDG_Refresh", "HAL_WWDG_GetEarlyWakeupFlag", "HAL_WWDG_ClearEarlyWakeupFlag"):
        assert name in t["hal_api"] and name in t["hal_dynamic_view"], name
    assert not any(re.search(r"\bRCC(?:\b|_)|\bIWDG\b|\bCRC_", t[k]) for k in HAL_KEYS)


def test_the_hal_calls_only_the_delivered_st_ll_functions():
    """The HAL is built on the provided 0016c LL (ST CubeN6 stm32n6xx_ll_wwdg.h, delivery scope of 12 functions)."""
    t = peripheral.load("wwdg")["prompt"]
    scope = set(json.loads(LL_EXAMPLE.read_text())["delivery"]["scope"]["functions"])
    used = set(re.findall(r"\bLL_WWDG_[A-Za-z_]+(?=\s*\()", t["hal_example"] + t["hal_ut_example"]))
    used |= {f"LL_{m}" for m in re.findall(r"\bLL_FAKE_LL_(WWDG_\w+)", t["hal_ut_example"])}
    assert used and used <= scope, used - scope
    order = [t["hal_example"].index(f"{f}(WWDG") for f in ("LL_WWDG_ClearFlag_EWKUP", "LL_WWDG_EnableIT_EWKUP",
                                                           "LL_WWDG_SetCounter", "LL_WWDG_Enable")]
    assert order == sorted(order)  # flag clear before EWI (RM0486 60.5), counter with T6 before WDGA (60.4.4)


@pytest.mark.skipif(not RM.is_file(), reason="RM0486 ch.60 conversion is a git-ignored local input (hash manifest tracked)")
def test_the_rm_supports_the_no_wait_decision_and_the_parameter_ranges():
    """The factory RM parser on the converted chapter: WWDG_SR has only EWIF (no update/busy/ready flag), WDGA and EWI
    are set-only, WDGTB is 3 bits (prescaler <= 7), W and T are 7 bits (window/counter <= 0x7F)."""
    from forge_factory.assurance.hardware import parse_section

    text = RM.read_text()
    regs = {}
    for part in re.split(r"(?m)^(?=#{2,4} \d)", text):
        r = parse_section(part, "WWDG")
        if r:
            regs[r["name"]] = {f: (d["msb"] - d["lsb"] + 1, d.get("access")) for f, d in r["fields"].items()}
    assert regs["WWDG_SR"] == {"EWIF": (1, ["rc_w0"])}
    assert regs["WWDG_CR"] == {"WDGA": (1, ["rs"]), "T": (7, ["rw"])}
    assert regs["WWDG_CFR"] == {"WDGTB": (3, ["rw"]), "EWI": (1, ["rs"]), "W": (7, ["rw"])}
    flat = " ".join(text.split())
    assert "lower than or equal to the window register value, and greater than 0x3F" in flat  # p.2997: refresh window
    assert "always write 1 in the T6 bit" in flat  # p.2997
    assert "counting down even if the watchdog is disabled" in flat  # p.2997


@pytest.mark.parametrize("lyr", ["HAL", "LL+HAL"])
@pytest.mark.parametrize("gtest", [False, True])
def test_wwdg_hal_prompts_have_no_timeout_bound_or_timeout_tests(lyr, gtest):
    dot = _dot("wwdg", lyr, uspec_gtest=gtest)
    s1, s2, s3 = (_prompt(dot, n) for n in ("swe1_author", "swe2_author", "swe3_hal_author"))
    for p in (s1, s2, s3):
        assert "TIMEOUT_VALUE" not in p and "polling iterations" not in p
    assert "returns without waiting on a WWDG flag" in s1
    assert "No HAL_WWDG_ function waits" in s3 and "LL_WWDG_SetCounter(WWDG, p_config->counter);" in s3
    assert "Error handling and timing" in s2 and "Timeouts and error handling" not in s2
    for p in (_prompt(dot, "swe5_author"), _prompt(dot, "swe6_test_author")):
        assert not re.search(r"_timeout\.c|never_ready|timeout paths|timeout behaviour", p)
    assert "test_wwdg_target_errors.c" in _prompt(dot, "swe5_inspect_gate")  # hal_target_tests, as for CRC


@pytest.mark.parametrize("gtest", [False, True])
def test_no_wwdg_hal_text_reaches_the_ll_graph(gtest):
    ll = builder.build("WO-WWDG-LL", chunk_lines=150, layer="LL", trace=True, peripheral="wwdg", uspec_gtest=gtest)[0]
    t = peripheral.load("wwdg")["prompt"]
    assert not any(t[k][:60].replace('"', '\\"') in ll for k in HAL_KEYS)


def test_no_timeout_path_required_in_the_wwdg_hal_views(tmp_path):
    ws = _ws(tmp_path)
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    fns = ["HAL_WWDG_Init", "HAL_WWDG_Refresh"]
    rows = "".join(f"| SWR-00{i} | {f} |\n" for i, f in enumerate(fns, 1))
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "# Software architecture\n\n## Requirement allocation table\n\n| SWR | Function |\n|---|---|\n" + rows)
    (ws / "workproducts/SWE.2/architecture_static.puml").write_text(
        "@startuml\ncomponent stm32n6xx_hal_wwdg\ncomponent stm32n6xx_ll_wwdg\nstm32n6xx_hal_wwdg --> stm32n6xx_ll_wwdg\n"
        "@enduml\n")
    calls = "".join(f"Caller -> HAL : {f}()\nHAL --> Caller : HAL_OK\n" for f in fns)
    (ws / "workproducts/SWE.2/architecture_dynamic.puml").write_text(
        f"@startuml\nparticipant Caller\nparticipant HAL\n{calls}HAL --> Caller : HAL_ERROR\n@enduml\n")
    r = check_views(ws)
    assert r["stats"]["timeout_path_required"] is False
    assert "VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH" not in r["major_findings"]


def test_wwdg_hal_boundary_rule_uses_the_field_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(RC, "_rm_index", lambda ws: WWDG_IDX)
    rule = T.boundary_rule(_ws(tmp_path, effects=WWDG_EFFECTS))
    assert rule["timeout_const"] is None and rule["zero_count"]
    assert rule["field_limits"] == [7, 8, 127, 128]  # 3-bit WDGTB, 7-bit W and T; 1-bit WDGA/EWIF give none
    ll = T.boundary_rule(_ws(tmp_path, lyr="LL", effects=WWDG_EFFECTS, name="ll"))
    assert not ll["zero_count"] and ll["field_limits"] == []
    t = peripheral.load("wwdg")["prompt"]
    assert all(v in t["hal_args_example"] for v in ("8U", "0x80U"))  # the invalid cases hit those limits
