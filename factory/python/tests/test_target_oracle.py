"""F011-T034 (SWE.5/SWE.6): the SafeC register-image oracle on the Renode STM32N6 target model with Cortex-M55 code.

Cases come from the reference derivation on real RM0486 facts (RCC_AHB1ENR, RCC_SR); the LL code is built for the
target and runs on the Forge-C platform. A plain read-write register (AHB1ENR) holds every initial image and each
case passes; model-driven ready flags (RCC_SR) cannot be set, so their cases are NOT_SETTABLE, never passed; a
wrong-bit mutant fails on its own cases only.
"""
from __future__ import annotations

import shutil

import pytest
from forge_factory.assurance import target_oracle
from forge_factory.mcp.servers import sim
from forge_factory.safec_bridge import contract as K
from forge_factory.safec_bridge import oracle as O
from test_safec_bridge_m2 import RM_RCC, _rm_domain

FN = {"ADC-ON": "LL_RCC_EnableADC12", "ADC-OFF": "LL_RCC_DisableADC12", "HSI-RDY": "LL_RCC_IsReadyHSI"}
INTENTS = [
    {"intent_id": "ADC-ON", "source_fact_ids": ["F-RCC_AHB1ENR-ADC12EN"], "register": "RCC_AHB1ENR",
     "field": "ADC12EN", "action": "set_field"},
    {"intent_id": "ADC-OFF", "source_fact_ids": ["F-RCC_AHB1ENR-ADC12EN"], "register": "RCC_AHB1ENR",
     "field": "ADC12EN", "action": "clear_field"},
    {"intent_id": "HSI-RDY", "source_fact_ids": ["F-RCC_SR-HSIRDY"], "register": "RCC_SR", "field": "HSIRDY",
     "action": "read_field"},
]


def _header(ops, block: str, wrong_bit: bool = False) -> str:
    lines = ["#include <stdint.h>"]
    for op in ops:
        w, mask = int(op["offset"], 16) // 4, int(op["field_mask"], 16)
        if wrong_bit and op["intent_id"] == "ADC-ON":
            mask >>= 1  # GPDMA1EN, the neighbouring field
        fn = FN[op["intent_id"]]
        if op["write_kind"] == "none":
            lines.append(f"static inline uint32_t {fn}(void) {{ return (({block}[{w}U] & 0x{mask:08X}U) == "
                         f"0x{mask:08X}U) ? 1U : 0U; }}")
        elif op["action"] == "set_field":
            lines.append(f"static inline void {fn}(void) {{ {block}[{w}U] |= 0x{mask:08X}U; }}")
        else:
            lines.append(f"static inline void {fn}(void) {{ {block}[{w}U] &= ~0x{mask:08X}U; }}")
    return "\n".join(lines) + "\n"


@pytest.mark.skipif(sim.renode_bin() is None or shutil.which("arm-none-eabi-gcc") is None,
                    reason="Renode or the GNU Arm toolchain not installed")
@pytest.mark.skipif(not RM_RCC.is_file(), reason="owner RM0486 inputs not in this checkout")
def test_register_oracle_on_the_renode_target(tmp_path):
    doc, _raw = _rm_domain(tmp_path, RM_RCC, "RCC", {"RCC_AHB1ENR", "RCC_SR"})
    ops = [K.reference_operation(doc, i) for i in INTENTS]
    cases = []
    for c in O.reference_cases(doc, ops):
        op = next(o for o in ops if o["intent_id"] == c["intent_id"])
        cases.append({"swr": f"SWR-{c['intent_id']}", "case": f"{c['intent_id']}@{c['initial']}",
                      "register": c["register"], "function": FN[c["intent_id"]], "args": [],
                      "word": int(c["offset"], 16) // 4, "initial": int(c["initial"], 16),
                      "after": int(c["expected_after"], 16),
                      "ret": None if c["expected_return"] is None else int(c["expected_return"]),
                      "mask": int(op["field_mask"], 16)})
    renode = sim.renode_bin()

    def run(name, wrong_bit=False):
        d = tmp_path / name
        d.mkdir()
        (d / "ll_test.h").write_text(_header(ops, "ll_rcc_regs", wrong_bit))
        ws = tmp_path / f"ws-{name}"
        ws.mkdir()
        return target_oracle.execute(ws, cases, [d], "ll_test.h", renode)

    good = run("ok")
    by = {}
    for r in good["cases"]:
        by.setdefault(r["case"].split("@")[0], set()).add(r["status"])
    assert by["ADC-ON"] == {"PASS"} and by["ADC-OFF"] == {"PASS"}, good["cases"]
    assert by["HSI-RDY"] == {"NOT_SETTABLE"}, good["cases"]  # ready flags are driven by the model
    assert good["status"] == "PASS" and good["counts"]["FAIL"] == 0 and good["environment"] == "RENODE"
    bad = run("mut", wrong_bit=True)
    failed = {r["case"].split("@")[0] for r in bad["cases"] if r["status"] == "FAIL"}
    assert bad["status"] == "FAIL" and failed == {"ADC-ON"}, bad["cases"]
