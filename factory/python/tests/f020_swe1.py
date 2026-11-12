"""Feature 020 US2 test helpers: a prepared functional-level SER workspace whose governance package passed, and
scripted functional SWE.1 author answers (never a real model).

Task plan of the SER fixture (one task per scope-rule service group in inventory order, then state behaviour, then the
HAL design constraints of the guideline input): g_initialisation, g_blocking_transfer, g_state, g_ll_configuration,
g_ll_data_and_flags, state_behaviour, design_constraints. Input register: IN-01 datasheet, IN-02 RM chapter (sections
42.x), IN-03 memory map, IN-04 CMSIS header, IN-05 guideline, IN-06..IN-08 the delivered code (under analysis)."""
from __future__ import annotations

import copy
import json

from f020_fixtures import example, ser_spec
from forge_factory import workorder as WO
from forge_factory.lrtx import structured as S

MODEL = "fake-model:q8"
TASKS = ["requirements:g_initialisation", "requirements:g_blocking_transfer", "requirements:g_state",
         "requirements:g_ll_configuration", "requirements:g_ll_data_and_flags", "requirements:state_behaviour",
         "requirements:design_constraints"]


def req(key: str, statement: str, *, title: str | None = None, typ: str = "functional", origin: str = "use_case",
        links: list | None = None, ucs: tuple = (), method: str = "test", level: str = "component",
        pre: str = "none") -> dict:
    return {"key": key, "title": title or key.replace("_", " "), "statement": statement, "type": typ,
            "precondition": pre, "origin_group": origin, "links": list(links or []), "use_cases": list(ucs),
            "verification_method": method, "test_level": level}


def trace(input_id: str, locator: str) -> dict:
    return {"kind": "trace", "input_id": input_id, "locator": locator}


def derive(input_id: str, locator: str, rationale: str) -> dict:
    return {"kind": "derive", "input_id": input_id, "locator": locator, "rationale": rationale}


def answers() -> dict[str, dict]:
    """A valid answer per task of the SER fixture."""
    a = {
        "requirements:g_initialisation": [
            req("init_applies_settings", "When HAL_SER_Init is called with a valid handle, the SER HAL driver shall "
                "enable the interface with the settings of the handle.", links=[trace("IN-02", "42.1")],
                ucs=("UC-01",)),
            req("deinit_releases", "When HAL_SER_DeInit is called with a valid handle, the SER HAL driver shall "
                "return the interface to its state before initialisation.",
                links=[derive("IN-02", "42.1", "de-initialisation undoes the initialisation the introduction "
                              "describes")], ucs=("UC-01",)),
            req("init_calls_platform_hook", "When HAL_SER_Init is called, the SER HAL driver shall call "
                "HAL_SER_MspInit before it enables the interface.", origin="awaiting_traceability", ucs=("UC-01",))],
        "requirements:g_blocking_transfer": [
            req("transmit_blocking", "When HAL_SER_Transmit is called with a valid handle, data and size, the SER HAL "
                "driver shall send the data and return HAL_OK after the last data item was accepted.",
                links=[trace("IN-02", "42.3.1")], ucs=("UC-02",)),
            req("receive_blocking", "When HAL_SER_Receive is called with a valid handle, buffer and size, the SER HAL "
                "driver shall store the received data in the buffer and return HAL_OK.",
                links=[trace("IN-02", "42.3.2")], ucs=("UC-02",)),
            req("tx_complete_callback", "When a transmission started by HAL_SER_Transmit completes, the SER HAL "
                "driver shall call HAL_SER_TxCpltCallback.", links=[trace("IN-02", "42.3.1")], ucs=("UC-02",))],
        "requirements:g_state": [
            req("get_state", "When HAL_SER_GetState is called, the SER HAL driver shall return the current state of "
                "the handle.", links=[trace("IN-05", "1.1")], ucs=("UC-02",))],
        "requirements:g_ll_configuration": [
            req("ll_enable", "When LL_SER_Enable is called, the SER LL driver shall enable the interface.",
                links=[trace("IN-02", "42.7.1")], ucs=("UC-03",), level="unit"),
            req("ll_disable", "When LL_SER_Disable is called, the SER LL driver shall disable the interface.",
                links=[trace("IN-02", "42.7.1")], ucs=("UC-03",), level="unit"),
            req("ll_is_enabled", "When LL_SER_IsEnabled is called, the SER LL driver shall return 1 when the "
                "interface is enabled and 0 otherwise.", links=[trace("IN-02", "42.7.1")], ucs=("UC-03",),
                level="unit"),
            req("ll_set_baud", "When LL_SER_SetBaud is called with a divider value, the SER LL driver shall program "
                "the baud rate divider of the interface with that value.", origin="out_of_context",
                links=[trace("IN-02", "42.7.2")], level="unit")],
        "requirements:g_ll_data_and_flags": [
            req("ll_transmit_data", "When LL_SER_TransmitData is called with a data value, the SER LL driver shall "
                "hand the value to the transmitter.", links=[trace("IN-02", "42.3.1")], ucs=("UC-03",), level="unit"),
            req("ll_receive_data", "When LL_SER_ReceiveData is called, the SER LL driver shall return the last "
                "received data value.", links=[trace("IN-02", "42.3.2")], ucs=("UC-03",), level="unit"),
            req("ll_tx_empty_flag", "When LL_SER_IsActiveFlag_TXE is called, the SER LL driver shall return 1 when "
                "the transmitter is ready for new data and 0 otherwise.", links=[trace("IN-02", "42.3.1")],
                ucs=("UC-03",), level="unit"),
            req("ll_overrun_flag", "When LL_SER_IsActiveFlag_ORE is called, the SER LL driver shall return 1 when an "
                "overrun was detected and 0 otherwise.", links=[trace("IN-02", "42.3.2")], ucs=("UC-03",),
                level="unit"),
            req("ll_clear_overrun", "When LL_SER_ClearFlag_ORE is called, the SER LL driver shall clear the overrun "
                "indication.", links=[trace("IN-02", "42.3.2")], ucs=("UC-03",), level="unit")],
        "requirements:state_behaviour": [
            req("busy_refusal", "If a transfer service is called while a transfer of the same handle is ongoing, "
                "then the SER HAL driver shall return HAL_BUSY and leave the ongoing transfer unchanged.",
                origin="state_behaviour", ucs=("UC-02",),
                links=[derive("IN-05", "1.1", "the handle holds the state, so a busy handle refuses a second "
                              "transfer")]),
            req("invalid_parameter", "If a service is called with an invalid parameter, then the SER HAL driver "
                "shall return HAL_ERROR without starting the operation.", origin="state_behaviour",
                links=[derive("IN-05", "1.1", "parameter validity is part of the handle-based service contract")])],
        "requirements:design_constraints": [
            req("no_dynamic_memory", "The SER HAL driver shall not allocate memory dynamically.",
                typ="design_constraint", origin="hal_design_constraint", links=[trace("IN-05", "1.2")],
                method="inspection", level="not_testable"),
            req("handle_based_services", "The SER HAL driver shall take a handle that holds the instance and its state "
                "in every service.", typ="design_constraint", origin="hal_design_constraint",
                links=[trace("IN-05", "1.1")], method="inspection", level="not_testable")],
    }
    return {t: {"requirements": r, "open_points": []} for t, r in a.items()}


def scripted(by_task: dict, calls: list):
    """S.call stand-in: the answer for the packet's task (a list is consumed one answer per call, the last repeats)."""
    seen: dict[str, int] = {}

    def call(p, **_k):
        calls.append(p)
        a = by_task[p["task"]]
        if isinstance(a, list):
            n = seen.get(p["task"], 0)
            seen[p["task"]] = n + 1
            a = a[min(n, len(a) - 1)]
        doc = copy.deepcopy(a(p) if callable(a) else a)
        return {"doc": doc, "errors": S.validate(doc, p["output_schema"]),
                "usage": {"prompt_tokens": 900, "completion_tokens": 300}, "wall_ms": 1.0, "finish_reason": "stop"}
    return call


def prepared(tmp_path, monkeypatch, spec: dict | None = None, wo: str = "WO-F020-F1"):
    """A prepared functional SER workspace (binding with the author and governance nodes) whose governance passed."""
    from forge_factory.governance import package as GP
    from forge_factory.workflow.builder import binding_for, build
    from test_f020_governance_package import answer as governance_answer

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    w, _m = WO.prepare(example(tmp_path, spec or ser_spec(), name=wo), wo)
    _g, nodes = build(wo, layer="LL+HAL", trace=True, brownfield="FROZEN", stop_after="SWE.1")
    nodes = {**nodes, "swe1_governance": dict(nodes["swe1_author"])}
    binding_for(wo, str(w), nodes).dump(w / ".forge-run/binding.json")
    calls: list = []
    monkeypatch.setattr(S, "call", scripted({"governance": governance_answer()}, calls))
    assert GP.visit(w, MODEL)["status"] == "PASS"
    return w


def author(ws, monkeypatch, by_task: dict | None = None) -> tuple[dict, list]:
    from forge_factory.lrtx import swe1_functional as F

    calls: list = []
    monkeypatch.setattr(S, "call", scripted(by_task or answers(), calls))
    return F.visit(ws, MODEL), calls


def manifest(ws) -> dict:
    return json.loads((ws / ".forge-run/manifest.json").read_text())
