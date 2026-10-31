"""Feature 008 US2 - requirements written without the code (FR-007) and conformance of the delivered code to them
(FR-008, SC-002): the five seeded mismatch kinds each give the right finding; an unmodified delivery gives none."""
import json

import pytest
from brownfield_fixtures import HEADER, MUTANTS, add_contract, example_copy, pass_swe1, scope_for
from forge_factory import workorder as WO
from forge_factory.brownfield import conformance as C
from forge_factory.brownfield.inject import inject
from forge_factory.policy.authz import Authorizer, Binding


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    return tmp_path


def _prepared(tmp_path, wo, header=HEADER, scope=None):
    mutate = (lambda s: s["delivery"]["scope"].update(functions=scope)) if scope else None
    return WO.prepare(example_copy(tmp_path, header=header, mutate=mutate, name=wo), wo)


def test_inject_refuses_before_swe1_passes(tmp_path):
    ws, _ = _prepared(tmp_path, "WO-I-1")
    r = inject(ws)
    assert r["status"] == "REFUSED" and any(i.startswith("SWE1_NOT_PASSED") for i in r["issues"])
    assert not (ws / "software/ll/stm32n6xx_ll_rcc.h").exists()


def test_inject_after_swe1_records_the_frozen_baseline(tmp_path, monkeypatch):
    ws, man = _prepared(tmp_path, "WO-I-2")
    pass_swe1(monkeypatch)
    r = inject(ws)
    assert r["status"] == "INJECTED" and r["swe1_baseline_id"] == "BL-SWE.1-001"
    h = ws / "software/ll/stm32n6xx_ll_rcc.h"
    assert h.read_text() == HEADER and h.stat().st_mode & 0o222 == 0
    rec = json.loads((ws / ".forge-run/delivery/injection.json").read_text())
    assert rec["swe1_baseline_hash"] == "h" * 64 and {f["path"] for f in rec["files"]} == {d["path"] for d in man["delivered"]}
    assert (ws / ".forge-run/delivery/scope.json").is_file()
    assert inject(ws)["status"] == "ALREADY_INJECTED"


def test_inject_refuses_a_tampered_store(tmp_path, monkeypatch):
    from forge_factory.brownfield import delivery as D

    ws, _ = _prepared(tmp_path, "WO-I-3")
    f = D.store_dir("WO-I-3") / "files/software/ll/stm32n6xx_ll_rcc.h"
    f.chmod(0o644)
    f.write_text(HEADER + "/* tampered */\n")
    pass_swe1(monkeypatch)
    assert "DELIVERY_STORE_MISMATCH:software/ll/stm32n6xx_ll_rcc.h" in inject(ws)["issues"]


def _auth(ws, node, role, phase):
    return Authorizer(Binding("WO", str(ws), {node: {"role": role, "phase": phase}}))


def test_requirement_authors_cannot_read_delivered_code(tmp_path, monkeypatch):
    ws, _ = _prepared(tmp_path, "WO-I-4")
    pass_swe1(monkeypatch)
    inject(ws)
    swe1 = _auth(ws, "swe1_author", "swe1-author", "SWE.1")
    d = swe1.decide("swe1_author", "read_file", {"path": "software/ll/stm32n6xx_ll_rcc.h"})
    assert not d.allow and d.code == "DELIVERED_CODE_HIDDEN_FROM_REQUIREMENTS"
    for tool, root in (("grep", "."), ("glob", "software"), ("list_dir", "software/ll")):
        assert not swe1.decide("swe1_author", tool, {"path": root}).allow, (tool, root)
    assert not swe1.decide("swe1_author", "read_file", {"path": ".forge-run/delivery/scope.json"}).allow
    assert swe1.decide("swe1_author", "read_file", {"path": "inputs/index.md"}).allow
    assert swe1.decide("swe1_author", "glob", {"path": "inputs/sections"}).allow
    swe2 = _auth(ws, "swe2_author", "swe2-author", "SWE.2")
    assert swe2.decide("swe2_author", "read_file", {"path": "software/ll/stm32n6xx_ll_rcc.h"}).allow


def _conformance(tmp_path, wo, header, scope):
    ws, _ = _prepared(tmp_path, wo, header, scope)
    add_contract(ws)
    from forge_factory.inspection import engine

    real = engine.Store.gate, engine.Store.latest_baseline
    engine.Store.gate = lambda self, ph: {"decision": "PASS"}
    engine.Store.latest_baseline = lambda self, ph: {"baseline_id": "BL-SWE.1-001", "baseline_hash": "h" * 64}
    try:
        assert inject(ws)["status"] == "INJECTED"
    finally:
        engine.Store.gate, engine.Store.latest_baseline = real
    return C.check(ws, "SWE.3")


def test_unmodified_delivery_is_conformant(tmp_path):
    r = _conformance(tmp_path, "WO-C-0", HEADER, None)
    assert r["status"] == "CONFORMANT" and r["findings"] == []


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_each_seeded_mismatch_gives_its_finding_kind(tmp_path, name):
    mutate, change, kind, fn = MUTANTS[name]
    r = _conformance(tmp_path, f"WO-C-{name}", mutate(HEADER), scope_for(change) if change else None)
    assert r["status"] == "FINDINGS"
    kinds = {(f["kind"], f["function"]) for f in r["findings"]}
    assert (kind, fn) in kinds, kinds
    assert {k for k, _ in kinds} == {kind}  # exactly the expected kind of finding (SC-002)
    rec = json.loads((tmp_path / "state/workorders" / f"WO-C-{name}" / "workspace/.forge-run/delivery/"
                      "conformance.json").read_text())
    assert rec["schema"] == "forge-c/conformance/0.1" and all(f["status"] == "OPEN" for f in rec["findings"])


def test_api_call_none_is_no_code_and_not_a_contract_error(tmp_path):
    from forge_factory.assurance import register_contract as RC

    ws, _ = _prepared(tmp_path, "WO-C-N")
    add_contract(ws)
    calls = json.loads((ws / "workproducts/SWE.2/api_calls.json").read_text())
    calls["calls"]["HSE_READY_QUERY"] = {"function": "NONE", "args": []}
    (ws / "workproducts/SWE.2/api_calls.json").write_text(json.dumps(calls))
    assert not any("HSE_READY_QUERY" in x for x in RC.check_calls(ws))
    assert all(c["case"] != "HSE_READY_QUERY" for c in RC.cases(ws)[0])


def test_bound_arguments_select_the_branch_that_writes():
    """F015 USART-R4 a3 (CF-005..CF-012): ST LL_USART_SetBaudRate writes BRR only in its last two branches; with an
    invalid prescaler or a zero baud rate bound, the extractor still reported the BRR writes of every branch."""
    from forge_factory.brownfield import scope as S

    body = """{
  uint32_t brrtemp;
  if (PrescalerValue > LL_USART_PRESCALER_DIV256)
  {
  }
  else if (BaudRate == 0U)
  {
  }
  else if (OverSampling == LL_USART_OVERSAMPLING_8)
  {
    brrtemp = 1U;
    USARTx->BRR = brrtemp;
  }
  else
  {
    USARTx->BRR = (uint16_t)(BaudRate);
  }
}"""
    d = S.Definition("LL_USART_SetBaudRate", "f.h", 1, "static_inline",
                     ["USARTx", "PeriphClk", "PrescalerValue", "OverSampling", "BaudRate"], body)
    macros = {"LL_USART_PRESCALER_DIV256": "0x0000000BU", "LL_USART_OVERSAMPLING_8": "(0x1UL << 15U)"}

    def brr(*args):
        return [e.text for e in S.register_effects(d, macros, "cmsis", list(args), prefix="USART") if e.op != "read"]
    assert brr("USART1", "64000000U", "12U", "0U", "115200U") == []                      # invalid prescaler
    assert brr("USART1", "64000000U", "0U", "0U", "0U") == []                            # zero baud rate
    assert brr("USART1", "64000000U", "0U", "LL_USART_OVERSAMPLING_8", "9600U") == ["(USART1)->BRR = brrtemp;"]
    assert len(brr("USART1", "64000000U", "0U", "0U", "9600U")) == 1                     # oversampling 16
    assert len(brr("USART1", "64000000U", "Prescaler", "0U", "9600U")) == 2              # undecidable: all branches


TIM_R4 = __import__("forge_factory.common", fromlist=["state_dir"]).state_dir() / \
    "workorders/WO-AFO-c36be5a7c46d0b55-a1/workspace"  # resolved at import, like the AFO tests' real workspaces


def test_a_whole_register_write_meets_the_rm_fields_it_specifies(tmp_path):
    """F015 BENCH-TIM-ST-R4 (CF-001..CF-003, LL_TIM_SetCounter / SWR-012): ST writes TIM_CNT whole (WRITE_REG); the
    requirement states CNT[30:0] = 99 and bit 31 (UIFCPY_CNT, CNT[31] while UIFREMAP = 0) set for 0x80000063. The check
    took CMSIS TIM_CNT_CNT_Msk (the whole register) for the RM's CNT[30:0], refused a plain write as a 'set', and
    called the fully specified write an overwrite of other bits. A value without bit 31 still contradicts."""
    import json
    import shutil

    from forge_factory.brownfield import conformance

    src = TIM_R4
    if not src.is_dir():
        pytest.skip("BENCH-TIM-ST-R4 workspace not on this host")
    ws = tmp_path / "ws"
    shutil.copytree(src, ws, ignore=shutil.ignore_patterns("build", "acp"), symlinks=True)
    open_ = lambda: [f for f in conformance.check(ws, "SWE.3", write=False)["findings"]  # noqa: E731
                     if f["status"] == "OPEN"]
    assert open_() == []
    calls = ws / "workproducts/SWE.2/api_calls.json"
    d = json.loads(calls.read_text())
    d["calls"]["SET_COUNTER_HIGH_1"]["args"] = ["TIM2", "0x00000063U"]   # bit 31 not written
    calls.write_text(json.dumps(d))
    assert [(f["kind"], f["function"]) for f in open_()] == [("CONTRADICTION", "LL_TIM_SetCounter")]
