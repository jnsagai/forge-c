"""CAPA-135 (WO-F014-SWE3-CRCHAL-20261103-L31): the SWE.2 call contract of a HAL on a provided ST (CMSIS) LL could never
compile - register_contract.check_compiles gave it neither the host device directory nor the forced host mapping nor
the defines of the provided LL (CAPA-128), so the ST LL header's #include "stm32n6xx.h" failed and SWE.3 was BLOCKED
STUCK. The contract now compiles with cmsis.host_flags; greenfield and brownfield compiles are unchanged."""
import json
import subprocess

from forge_factory import workorder as WO
from forge_factory.assurance import register_contract as RC
from forge_factory.brownfield import cmsis
from test_capa128_hal_on_st_ll import HAL_C, HAL_H, _iwdg_hal_example, _source_ll, env  # noqa: F401 (fixture)


def _hal(env, name: str, cmsis_ll: bool, function: str):
    import shutil

    shutil.rmtree(env / "state/workorders/WO-LL-ST", ignore_errors=True)
    _source_ll(env / "state", cmsis_delivery=cmsis_ll)
    ws, _ = WO.prepare(_iwdg_hal_example(env), f"WO-HAL-{name}", "WO-LL-ST")
    (ws / "software/hal").mkdir(parents=True, exist_ok=True)
    (ws / "software/hal/stm32n6xx_hal_iwdg.h").write_text(HAL_H)
    (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL_C)
    for rel, d in {RC.EFFECTS: {"schema": "forge-c/register-effects/1",
                                "effects": [{"case": "START", "swr": "SWR-001", "op": "no_write"}]},
                   RC.CALLS: {"calls": {"START": {"function": function, "args": []}}}}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(json.dumps(d))
    return ws


def _check(ws):
    return RC.check_compiles(ws, [ws / "software/hal", ws / "software/ll"], "stm32n6xx_hal_iwdg.h")


def _argv(ws, monkeypatch):
    seen = []
    real = subprocess.run

    def spy(argv, *a, **k):
        seen.append(list(argv))
        return real(argv, *a, **k)

    monkeypatch.setattr(RC.subprocess, "run", spy)
    _check(ws)
    return seen[-1]


def test_the_contract_of_a_hal_on_a_provided_st_ll_compiles_with_its_build_inputs(env, monkeypatch):
    ws = _hal(env, "ST", True, "HAL_IWDG_Start")
    assert cmsis.provided_build(ws) is not None and _check(ws) == []
    argv = _argv(ws, monkeypatch)
    hd = ws / cmsis.HOST_DIR
    assert argv[:2] == ["gcc", "-std=c11"] and ["-isystem", str(hd)] == argv[argv.index("-isystem"):][:2]
    assert ["-include", str(hd / "forge_host_device.h")] == argv[argv.index("-include"):][:2] and "-DSTM32N657xx" in argv


def test_a_wrong_call_on_a_provided_st_ll_is_still_reported(env):
    out = _check(_hal(env, "ST-WRONG", True, "HAL_IWDG_Nope"))
    assert out and all(f.startswith("CONTRACT_CALL_DOES_NOT_COMPILE:" + RC.CALLS) for f in out)
    assert any("HAL_IWDG_Nope" in f for f in out) and not any("stm32n6xx.h" in f for f in out)


def test_a_greenfield_hal_contract_compiles_as_before(env, monkeypatch):
    ws = _hal(env, "GF", False, "HAL_IWDG_Start")
    assert cmsis.provided_build(ws) is None
    argv = _argv(ws, monkeypatch)
    assert argv[:3] == ["gcc", "-std=c99", "-fsyntax-only"] and "-isystem" not in argv and "-include" not in argv

