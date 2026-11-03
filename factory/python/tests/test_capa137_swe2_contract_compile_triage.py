"""CAPA-137 (WO-F014-SWE3-CRCHAL-20261103-L31B): SWE.2 compiled its call contract only in instance mode or for a
brownfield delivery, so a greenfield HAL (also on a provided ST LL) passed SWE.2 with `&crc` (nothing declares `crc`) and
SWE.3 was BLOCKED; the SWE.2 author then rejected the SWE.3 defect and the triage returned without re-checking. SWE.2 now
applies the identifier part of the SWE.3 compile check where it cannot compile (no interface header yet), and the triage
re-opens a rejected defect whose cited SWE.2 file still fails that check."""
import json
import shutil

import pytest
from forge_factory import workorder as WO
from forge_factory.assurance import register_contract as RC
from forge_factory.brownfield import cmsis
from forge_factory.inspection import defects, engine
from forge_factory.inspection import gate as G
from forge_factory.lrtx import swe2
from test_capa128_hal_on_st_ll import _iwdg_hal_example, _source_ll, env  # noqa: F401 (fixture)

ARCH = ("# Software architecture\n\n## Interface\n\n```c\ntypedef struct { uint32_t reload; } hal_iwdg_config_t;\n"
        "#define HAL_IWDG_WINDOW_OFF 0x0FFFU\nuint32_t HAL_IWDG_Init(const hal_iwdg_config_t *p_config);\n"
        "uint32_t HAL_IWDG_Read(uint32_t *p_value);\n```\n")


def _ws(env, name: str, args: list[str], cmsis_ll: bool = True, function: str = "HAL_IWDG_Read"):
    shutil.rmtree(env / "state/workorders/WO-LL-ST", ignore_errors=True)
    _source_ll(env / "state", cmsis_delivery=cmsis_ll)
    ws, _ = WO.prepare(_iwdg_hal_example(env), f"WO-HAL-{name}", "WO-LL-ST")
    for rel, d in {RC.EFFECTS: {"schema": "forge-c/register-effects/1",
                                "effects": [{"case": "C1", "swr": "SWR-001", "op": "no_write"}]},
                   RC.CALLS: {"schema": "forge-c/api-calls/1", "calls": {"C1": {"function": function, "args": args}}}}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(json.dumps(d))
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
    return ws


def test_an_undeclared_argument_of_a_hal_on_a_provided_st_ll_is_an_swe2_finding(env):
    ws = _ws(env, "BAD", ["&crc"])
    assert cmsis.provided_build(ws) is not None
    out = RC.swe2_compile_findings(ws, "HAL")
    assert len(out) == 1 and out[0].startswith(f"CONTRACT_CALL_DOES_NOT_COMPILE:{RC.CALLS}:'crc' undeclared in case C1")
    assert "&(uint32_t){0U}" in out[0]  # the finding says how a self-contained output argument looks
    assert any("'crc' undeclared" in f for f in swe2.self_check(ws))  # the lrtx SWE.2 self-check applies it too


@pytest.mark.parametrize("args", [
    ["&(uint32_t){0U}"],                                                       # compound literal output pointer
    ["&(const hal_iwdg_config_t){ .reload = HAL_IWDG_WINDOW_OFF }"],             # SWE.2 type + macro, designator
    ["(uint32_t *)NULL"], ["(uint32_t *)0", "sizeof(uint32_t)"],                 # C keywords and <stdint.h>/<stddef.h>
    ["(const char *)\"crc, value\""],                                           # identifiers inside a string literal
    ["(uint32_t)(uintptr_t)IWDG", "UINT32_MAX"],                                  # the provided device macro, a limit
])
def test_self_contained_arguments_are_not_findings(env, args):
    assert RC.check_args_declared(_ws(env, "OK", args)) == []


def test_a_greenfield_hal_is_checked_too(env):
    ws = _ws(env, "GF", ["&value"], cmsis_ll=False)
    assert cmsis.provided_build(ws) is None
    assert [f for f in RC.swe2_compile_findings(ws, "HAL") if "'value' undeclared" in f]


def test_instance_and_brownfield_work_orders_keep_their_compile(env, monkeypatch):
    seen = []
    monkeypatch.setattr(RC, "check_compiles", lambda ws, dirs, hdr: seen.append(hdr) or ["X"])
    ws = _ws(env, "INST", ["&value"])
    monkeypatch.setattr("forge_factory.layer.ll_instance", lambda w=None: {"api_contract": "api.h"})
    assert RC.swe2_compile_findings(ws, "LL") == ["X"] and seen == ["api.h"]
    monkeypatch.setattr("forge_factory.layer.ll_instance", lambda w=None: None)
    monkeypatch.setattr("forge_factory.brownfield.is_brownfield", lambda m: True)
    assert RC.swe2_compile_findings(ws, "HAL") == ["X"] and seen[-1].endswith(".h")


def _rejected(ws, cites: list[str]) -> None:
    rec = {"schema": "forge-c/defect/0.5", "id": "DEF-001", "kind": "ARCHITECTURE", "detected_phase": "SWE.3",
           "target_phase": "SWE.2", "reported_by": "swe3-author", "status": "REJECTED", "requirement_ids": ["SWR-001"],
           "summary": "the call contract does not compile", "evidence_refs": cites, "test_files": {},
           "history": [{"status": "OPEN"}, {"status": "IN_FIX", "loop": 1}, {"status": "REJECTED", "by": "swe2-author",
                                                                            "reason": "a SWE.3 harness fix"}]}
    defects._dir(ws).mkdir(parents=True, exist_ok=True)
    (defects._dir(ws) / "DEF-001.json").write_text(json.dumps(rec))
    (ws / defects.LOOPS).parent.mkdir(parents=True, exist_ok=True)
    (ws / defects.LOOPS).write_text(json.dumps({"ts": "t", "target": "SWE.2", "defects": ["DEF-001"]}) + "\n")


@pytest.fixture()
def intact(monkeypatch):
    monkeypatch.setattr(engine.Store, "latest_baseline", lambda self, ph: {"baseline_id": "BL-SWE.2-001", "frozen_at": "t"})
    monkeypatch.setattr(engine.Store, "stale_reason", lambda self, ph, bl: None)


def _triage_state(ws) -> dict:
    lines = (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()
    return [json.loads(x) for x in lines if '"step": "triage"' in x][-1]


def test_triage_reopens_a_rejected_defect_whose_cited_contract_still_does_not_compile(env, intact):
    ws = _ws(env, "TRI", ["&crc"])
    _rejected(ws, [RC.CALLS, ".forge-run/gates/gate-log.jsonl"])
    assert G.step_triage(engine.Store(ws), "SWE.2") == 0  # FIX: the owner's fix step
    st, rec = _triage_state(ws), json.loads((defects._dir(ws) / "DEF-001.json").read_text())
    assert st["result"] == "FIX" and st["overruled"] == ["DEF-001"]
    assert rec["status"] == "IN_FIX" and rec["history"][-1]["by"] == "triage-gate"
    assert rec["history"][-2]["reason"] == "a SWE.3 harness fix"  # the author's reason stays recorded


def test_triage_still_returns_when_the_cited_contract_compiles_or_is_not_cited(env, intact):
    ws = _ws(env, "RET", ["&(uint32_t){0U}"])
    _rejected(ws, [RC.CALLS])
    assert G.step_triage(engine.Store(ws), "SWE.2") == 1 and "overruled" not in _triage_state(ws)
    ws = _ws(env, "RET2", ["&crc"])
    _rejected(ws, ["workproducts/SWE.2/software_architecture.md"])  # cites another file: no deterministic finding on it
    assert G.step_triage(engine.Store(ws), "SWE.2") == 1
