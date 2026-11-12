"""Feature 020 T027 (US2, FR-002, FR-007..FR-012): the UART module order `0012u-st-cube-uart-module` prepares.

The git-ignored inputs are materialised from the line's content-addressed inputs cache exactly as the line launcher
does (`afo/line_launcher.needed_inputs` / `input_hashes`, sha256-verified, as /mnt/data/forge-c/model-service/
matinputs.py), into a temporary copy of the example tree (`workorder.REPO_ROOT` points at that copy for the
inputs-inside-the-repository rule); nothing is written into the worktree. Skipped cleanly when the inputs cache or the
vendor delivery or the target compiler (delivery build check) is unavailable.

Prepared with no model: the governance inventory classifies every delivered public function (HAL: the functions the
delivered UART HAL headers declare; LL: every inline function of the delivered LL header) by the order's scope rule,
the in-scope lists match FR-009 / the FR-010 rule (applied here independently, by name), every FR-011 feature is
delivered-out-of-scope, the not-delivered list is FR-012's, the input register holds the FR-002 inputs and the
delivered code only as implementation under analysis; no INPUT_GAP.

The second test builds, for the real order under the owner-lane profile, the governance packet and every functional
author packet (governance answered by a scripted stand-in derived from the inventory - never a model) and checks each
against the packet bound of `lrtx/structured.packet` (PACKET_TOO_LARGE: estimated prompt tokens + output reserve <=
the profile's context) and against the practical input bound BOUND_TOKENS (decision log D24); the sizes are printed
(pytest -s) and recorded in the decision log."""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import jsonschema
import pytest
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT, sha256_file

EX = "0012u-st-cube-uart-module"
WO_ID = "WO-F020-UART-T027"
OWNER_PROFILE = "local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104"
BOUND_TOKENS = 100_000  # D24: practical author input bound (CAPA-242/243 saw CAPABILITY_LIMIT refusals at ~115k)
INV_SCHEMA = REPO_ROOT / "specs/020-usart-benchmark-pilot/contracts/governance-inventory.schema.json"

HAL_IN = {f"HAL_UART_{n}" for n in (
    "Init", "DeInit", "MspInit", "MspDeInit", "Transmit", "Receive", "Transmit_IT", "Receive_IT", "IRQHandler",
    "Transmit_DMA", "Receive_DMA", "Abort", "AbortTransmit", "AbortReceive", "Abort_IT", "AbortTransmit_IT",
    "AbortReceive_IT", "RegisterCallback", "UnRegisterCallback", "TxCpltCallback", "TxHalfCpltCallback",
    "RxCpltCallback", "RxHalfCpltCallback", "ErrorCallback", "AbortCpltCallback", "AbortTransmitCpltCallback",
    "AbortReceiveCpltCallback", "GetState", "GetError")} | {f"HAL_UARTEx_{n}" for n in (
        "EnableFifoMode", "DisableFifoMode", "SetTxFifoThreshold", "SetRxFifoThreshold")}  # FR-009
# FR-010, applied by name: configuration, enable/disable, FIFO, DMA request enable, transmit/receive/error interrupt
# enable and status, the matching flags and flag clears, data transmit/receive
LL_RULE = [r"(Enable|Disable|IsEnabled)", r"(Set|Get)(TransferDirection|Parity|DataWidth|StopBitsLength|OverSampling|"
           r"BaudRate|Prescaler)", r"(Enable|Disable)Direction(Rx|Tx)", r"Config(Character|AsyncMode)",
           r".*FIFO.*", r".*_(TXFT|RXFT|TXFE|RXFF)", r"Request(Rx|Tx)DataFlush", r"(Enable|Disable|IsEnabled)DMAReq_(RX|TX)",
           r"(Enable|Disable|IsEnabled)IT_(TXE_TXFNF|TC|RXNE_RXFNE|PE|ERROR)",
           r"(IsActiveFlag|ClearFlag)_(PE|FE|NE|ORE|TC|TXE_TXFNF|RXNE_RXFNE)", r"IsActiveFlag_(TEACK|REACK)",
           r"(Transmit|Receive)Data(8|9)"]
FR011_HAL = {"half-duplex": "HAL_HalfDuplex_", "LIN": "HAL_LIN_", "multiprocessor": "HAL_MultiProcessor",
             "RS-485": "HAL_RS485Ex_", "receive-to-idle": "HAL_UARTEx_ReceiveToIdle", "receive event callback":
             "HAL_UARTEx_RxEventCallback", "receiver timeout": "ReceiverTimeout", "DMA pause/resume/stop": "HAL_UART_DMA",
             "stop-mode wake-up": "StopMode"}
FR011_LL = {"LIN": "LIN", "smartcard": "Smartcard", "IrDA": "Irda", "auto-baud": "AutoBaud", "wake-up": "WKUP",
            "RS-485 driver enable": "DEMode"}
FR002 = {"RM0486-rev4-ch65-usart.md", "RM0486-rev4-memory-map-excerpt-usart.md", "RM0486-rev4-vector-table.md",
         "DS14791-rev9-stm32n6x5-x7-datasheet.md", "hal_driver_guideline.md", "stm32n657xx.h"}
DELIVERED = {"software/hal/stm32n6xx_hal_uart.c", "software/hal/stm32n6xx_hal_uart.h",
             "software/hal/stm32n6xx_hal_uart_ex.c", "software/hal/stm32n6xx_hal_uart_ex.h",
             "software/ll/stm32n6xx_ll_usart.h"}


class _Tree:
    """The working tree as a line_launcher reader (the launcher reads a git revision; this test reads the files)."""

    def read(self, path: str) -> bytes | None:
        p = REPO_ROOT / path
        return p.read_bytes() if p.is_file() else None

    def tracked(self, path: str) -> bool:
        return False  # every input is taken from the cache when a tracked manifest records its sha256

    def names(self, prefix: str) -> list[str]:
        return [str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / prefix).rglob("*") if p.is_file()]


def _mirror(tmp: Path) -> Path:
    from forge_factory.afo import line_launcher as LL

    cache = LL.LineConfig.from_env().inputs_cache
    if cache is None or not Path(cache).is_dir():
        pytest.skip("line inputs cache unavailable")
    spec = json.loads((REPO_ROOT / "examples" / EX / "workorder.json").read_text())
    src = os.path.expandvars(spec["delivery"]["source"])
    if not Path(src).is_dir():
        pytest.skip("vendor delivery source unavailable")
    if shutil.which("arm-none-eabi-gcc") is None:  # the delivery intake's build check of a cmsis delivery
        pytest.skip("arm-none-eabi-gcc not on PATH (delivery build check)")
    reader, root = _Tree(), tmp / "repo"
    idx = LL.input_hashes(reader)
    for rel in LL.needed_inputs(reader, EX):
        h = idx.get(rel)
        if h is None:
            if not (REPO_ROOT / rel).is_file():
                pytest.skip(f"input {rel} neither tracked nor in a manifest")
            got = REPO_ROOT / rel
        else:
            got = Path(cache) / "sha256" / h
            if not got.is_file() or sha256_file(got) != h:
                pytest.skip(f"input {rel} not in the inputs cache")
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(got, dst)
        assert h is None or sha256_file(dst) == h
    ex = root / "examples" / EX
    ex.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / "examples" / EX / "workorder.json", ex / "workorder.json")
    return ex


@pytest.fixture()
def uart(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path / "lrtx"))
    ex = _mirror(tmp_path)
    monkeypatch.setattr(WO, "REPO_ROOT", ex.parents[1])
    ws, man = WO.prepare(ex, WO_ID)
    monkeypatch.setattr(WO, "REPO_ROOT", REPO_ROOT)
    return ws, man, json.loads((REPO_ROOT / "examples" / EX / "workorder.json").read_text())


def _public(ws) -> tuple[set[str], set[str]]:
    """Delivered public API from the delivered files: HAL functions the delivered HAL headers declare, LL inline."""
    from forge_factory.brownfield import delivery as BD
    from forge_factory.brownfield import scope as S

    files = BD.stored(WO_ID)
    hdr = "".join(files[p].decode(errors="replace") for p in files if p.startswith("software/hal/") and p.endswith(".h"))
    hal = {d.name for p in files if p.startswith("software/hal/") and p.endswith(".c")
           for d in S.index(files[p].decode(errors="replace"), p) if re.search(rf"\b{d.name}\s*\(", hdr)}
    ll = {d.name for d in S.index(files["software/ll/stm32n6xx_ll_usart.h"].decode(errors="replace"), "ll")
          if d.kind == "static_inline"}
    return hal, ll


def test_the_uart_module_order_prepares_and_classifies_every_delivered_public_function(uart):
    ws, man, spec = uart
    assert man["swe1_level"] == "functional" and "register_contract" not in man
    inv = json.loads((ws / "inputs/governance-inventory.json").read_text())
    jsonschema.Draft202012Validator(json.loads(INV_SCHEMA.read_text())).validate(inv)
    assert inv["module"] == "UART"
    hal, ll = _public(ws)
    api = {a["function"]: a for a in inv["api"]}
    assert set(api) == hal | ll and len(ll) == 249  # every delivered public function, nothing else
    assert all(a["scope_class"] in ("in", "out") and a["scope_group"] for a in api.values())
    assert {f for f in hal if api[f]["component"] == "HAL_UART"} == hal
    assert {f for f in ll if api[f]["component"] == "LL_USART"} == ll
    hal_in = {f for f in hal if api[f]["scope_class"] == "in"}
    assert hal_in == HAL_IN  # FR-009
    ll_in = {f for f in ll if api[f]["scope_class"] == "in"}
    by_rule = {f for f in ll if any(re.fullmatch(r, f.removeprefix("LL_USART_")) for r in LL_RULE)}
    assert ll_in == by_rule  # FR-010: the list is the rule's, not a hand pick
    out = {f for f, a in api.items() if a["scope_class"] == "out"}
    assert out == (hal | ll) - HAL_IN - by_rule  # FR-011: everything else delivered is out of scope
    for feature, token in FR011_HAL.items():
        assert any(token in f for f in out & hal), feature
    for feature, token in FR011_LL.items():
        assert any(token in f for f in out & ll), feature
    assert inv["not_delivered"] == spec["scope_rule"]["not_delivered"]
    assert {n["capability"] for n in inv["not_delivered"]} == {  # FR-012 (spec edge cases)
        "separate configuration setters and getters in the HAL component", "DMA channel linking services",
        "loopback or self-test mode"}
    new = json.dumps({k: spec[k] for k in ("scope", "scope_rule", "module", "driver", "layer_note")}).lower()
    assert "benchmark" not in new  # generic wording (target and budgets are 0012d's, which name feature 015's set)
    regs = {r["name"]: r for r in inv["inputs"]}
    assert FR002 <= {n for n, r in regs.items() if r["role"] == "requirement_source"}  # FR-002
    assert regs["stm32n657xx.h"]["revision"] == "cmsis-device-n6 v1.4.0"
    assert {n for n, r in regs.items() if r["role"] == "implementation_under_analysis"} >= DELIVERED  # FR-003
    assert not any(n.endswith("manifest.json") for n in regs)
    assert {s["section"] for s in regs["RM0486-rev4-vector-table.md"]["sections"]} >= {"24.1.2"}
    feats = {f["feature"]: f["scope_class"] for f in inv["rm_features"]}
    assert feats["65.5.6"] == feats["65.7"] == feats["24.1.2"] == "in" and feats["65.5.14"] == "out"
    comps = {c["id"]: c for c in spec["module"]["components"]}
    assert set(comps) == {"HAL_UART", "LL_USART"} and all(c["uses"] == [] for c in comps.values())  # FR-007/FR-008


def _governance_answer(inv: dict, spec: dict) -> dict:
    """A scripted governance answer (no model): one use case per in-scope service group of the scope rule."""
    api = {}
    for a in inv["api"]:
        if a["scope_class"] == "in":
            api.setdefault(a["scope_group"], []).append(a["function"])
    feats = {g["group"]: g.get("rm_features") or [] for g in spec["scope_rule"]["in"]}
    ucs = [{"use_case_id": f"UC-{n:02d}", "title": g, "actor_id": "A-01" if not g.startswith("ll ") else "A-02",
            "goal": f"use the {g} services", "functions": fns, "rm_features": feats.get(g, [])}
           for n, (g, fns) in enumerate(api.items(), 1)]
    return {"actors": [{"actor_id": "A-01", "name": "application software (HAL)", "description": "calls the HAL"},
                       {"actor_id": "A-02", "name": "application software (LL)", "description": "calls the LL"}],
            "use_cases": ucs, "assumptions": [{"assumption_id": "AS-01", "text": "one instance per handle"}],
            "open_points": []}


def test_real_module_packets_fit_the_packet_bound(uart, monkeypatch):
    from forge_factory.afo.owner_supervised_development import RUN_MODEL
    from forge_factory.governance import inventory as GI
    from forge_factory.governance import package as GP
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import swe1_functional as F
    from forge_factory.lrtx.runner import _call  # the runner's step context: the packet bound is the profile's
    from forge_factory.workflow.builder import binding_for, build

    ws, _man, spec = uart
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    m["local_profile"] = {"id": OWNER_PROFILE}  # the owner lane's profile: its context is the packet bound
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m, indent=1))
    _g, nodes = build(WO_ID, layer="LL+HAL", trace=True, brownfield="FROZEN", stop_after="SWE.1")
    binding_for(WO_ID, str(ws), {**nodes, "swe1_governance": dict(nodes["swe1_author"])}).dump(
        ws / ".forge-run/binding.json")
    sizes = {}

    def rec(p):
        a = p["accounting"]
        assert a["fits"] is not False
        sizes[p["task"]] = {"tokens": a["estimated_prompt_tokens"], "reserve": a["output_reserve"],
                            "context": a["context_tokens"], "chars": a["serialized_chars"]}
        return p

    inv = GI.load(ws)
    rec(_call(ws, GP.packet, ws, RUN_MODEL))
    answer = _governance_answer(inv, spec)

    def call(p, **_k):
        return {"doc": answer, "errors": S.validate(answer, p["output_schema"]), "usage": None, "wall_ms": 1.0,
                "finish_reason": "stop"}
    monkeypatch.setattr(S, "call", call)
    assert _call(ws, GP.visit, ws, RUN_MODEL)["status"] == "PASS"
    ctx = F.context(ws)
    plan = F.plan(ws)
    assert [t["kind"] for t in plan].count("group") == len(spec["scope_rule"]["in"])
    for t in plan:
        rec(_call(ws, F.task_packet, ws, t, RUN_MODEL, ctx=ctx))
    print("\nF020_PACKET_SIZES " + json.dumps({k: {x: v[x] for x in ("tokens", "reserve", "context", "chars")}
                                               for k, v in sizes.items()}, sort_keys=True))
    over = {k: v["tokens"] for k, v in sizes.items() if v["tokens"] + v["reserve"] > BOUND_TOKENS}
    assert not over, f"packets over the {BOUND_TOKENS}-token input bound (D24): {over}"
