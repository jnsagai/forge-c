"""Feature 020 test fixtures: synthetic brownfield modules (no private input, no vendor code).

`ser`: a serial module with two components (HAL_SER: ser_hal.c/.h, LL_SER: ser_ll.h), as the UART pilot has HAL_UART
and LL_USART. `tmr`: a second, different module (one LL component) that the same code must prepare (SC-009).
The inputs live under tests/fixtures/f020 (inside the repository, as prepare requires); the work order is written to a
temporary example directory."""
from __future__ import annotations

import copy
import json
from pathlib import Path

FIX = Path(__file__).parent / "fixtures/f020"
REL = "factory/python/tests/fixtures/f020"  # repository-relative: the delivery source resolves the same in every tree
TEMPLATE = "swe1-functional-v1"

SER_HAL = ["HAL_SER_Init", "HAL_SER_DeInit", "HAL_SER_MspInit", "HAL_SER_Transmit", "HAL_SER_Receive",
           "HAL_SER_TxCpltCallback", "HAL_SER_GetState", "HAL_SER_EnableLoop"]
SER_LL = ["LL_SER_Enable", "LL_SER_Disable", "LL_SER_IsEnabled", "LL_SER_SetBaud", "LL_SER_TransmitData",
          "LL_SER_ReceiveData", "LL_SER_IsActiveFlag_TXE", "LL_SER_IsActiveFlag_ORE", "LL_SER_ClearFlag_ORE",
          "LL_SER_EnableLoop", "LL_SER_IsEnabledLoop"]
SER_OUT = ["HAL_SER_EnableLoop", "LL_SER_EnableLoop", "LL_SER_IsEnabledLoop"]
TMR_LL = ["LL_TMR_Enable", "LL_TMR_Disable", "LL_TMR_SetPeriod", "LL_TMR_GetCounter", "LL_TMR_IsActiveFlag_UPD",
          "LL_TMR_ClearFlag_UPD", "LL_TMR_EnableOnePulse"]


def _inputs(*items: tuple[str, str]) -> list[dict]:
    return [{"path": str((FIX / p).resolve()), "role": r} for p, r in items]


def _common(driver: str, names: list[str], layer: str) -> dict:
    return {
        "schema": "forge-c/work-order-spec/0.4",
        "driver": driver,
        "target": {"part_number": "SYNTH-MCU (feature 020 fixture)", "core": "Arm Cortex-M55",
                   "silicon_revision": "UNSPECIFIED", "source_documents": ["RM9999 Rev 2", "DS9999 Rev 1"],
                   "hsi_contract": "RM9999 Rev 2 (synthetic fixture)",
                   "safety_allocation": "OUT_OF_SCOPE: QM test fixture, no safety allocation"},
        "system_names": names,
        "budgets": {"flash_bytes": 4096, "static_ram_bytes": 64, "stack_bytes": 128, "status": "test fixture"},
        "guideline": "inputs/hal_guideline.md (synthetic fixture)",
        "layer": layer,
    }


def ser_spec(functional: bool = True) -> dict:
    spec = _common("Synthetic SER module (HAL + LL), feature 020 test fixture", ["SER driver", "SER HAL driver",
                                                                               "SER LL driver"], "LL+HAL")
    spec["scope"] = ["SER module: the HAL and LL services of the synthetic serial interface",
                     "Out of scope: loopback mode"]
    spec["inputs"] = _inputs(("module_ser/inputs/DS9999-rev1-datasheet.md", "datasheet"),
                             ("module_ser/inputs/RM9999-rev2-ch42-ser.md", "reference_manual_ser_chapter"),
                             ("module_ser/inputs/RM9999-rev2-memory-map-ser.md", "reference_manual_memory_map"),
                             ("module_ser/inputs/ser_device.h", "cmsis_device_header"),
                             ("module_ser/inputs/inputs-manifest.json", "conversion_provenance"),
                             ("module_ser/inputs/hal_guideline.md", "development_guideline"))
    spec["delivery"] = {
        "code_mode": "FROZEN", "origin": "synthetic feature 020 test fixture", "licence": "Apache-2.0",
        "licence_allows_modification": True, "source": f"{REL}/module_ser/delivery",
        "files": [{"from": "ser_hal.c", "to": "software/hal/ser_hal.c"},
                  {"from": "ser_hal.h", "to": "software/hal/ser_hal.h"},
                  {"from": "ser_ll.h", "to": "software/ll/ser_ll.h"}],
        "scope": {"functions": list(SER_HAL)}, "build": {"style": "forge"}}
    if functional:
        spec["swe1"] = {"level": "functional", "template": TEMPLATE}
        spec["module"] = {"name": "SER", "components": [
            {"id": "HAL_SER", "layer": "HAL", "files": ["software/hal/ser_hal.c", "software/hal/ser_hal.h"],
             "uses": []},
            {"id": "LL_SER", "layer": "LL", "files": ["software/ll/ser_ll.h"], "uses": []}]}
        spec["scope_rule"] = {
            "in": [{"group": "initialisation", "functions": ["HAL_SER_Init", "HAL_SER_DeInit", "HAL_SER_MspInit"],
                    "rm_features": ["42.1"]},
                   {"group": "blocking transfer", "functions": ["HAL_SER_Transmit", "HAL_SER_Receive",
                                                                "HAL_SER_TxCpltCallback"],
                    "rm_features": ["42.3.1", "42.3.2"]},
                   {"group": "state", "functions": ["HAL_SER_GetState"]},
                   {"group": "ll configuration", "functions": ["LL_SER_Enable", "LL_SER_Disable", "LL_SER_IsEnabled",
                                                               "LL_SER_SetBaud"]},
                   {"group": "ll data and flags", "functions": ["LL_SER_TransmitData", "LL_SER_ReceiveData",
                                                                "LL_SER_IsActiveFlag_*", "LL_SER_ClearFlag_*"]}],
            "out": [{"group": "loopback", "functions": ["HAL_SER_EnableLoop", "LL_SER_*Loop"],
                     "rm_features": ["42.3.5"]}],
            "not_delivered": [{"capability": "separate configuration getters",
                               "note": "the reference process has getters per setting; the delivery has none"}]}
    return spec


def tmr_spec() -> dict:
    spec = _common("Synthetic TMR module (LL), feature 020 test fixture", ["TMR driver", "TMR LL driver"], "LL")
    spec["scope"] = ["TMR module: the LL services of the synthetic timer", "Out of scope: one-pulse mode"]
    spec["inputs"] = _inputs(("module_ser/inputs/DS9999-rev1-datasheet.md", "datasheet"),
                             ("module_tmr/inputs/RM9999-rev2-ch43-tmr.md", "reference_manual_tmr_chapter"),
                             ("module_ser/inputs/RM9999-rev2-memory-map-ser.md", "reference_manual_memory_map"),
                             ("module_ser/inputs/inputs-manifest.json", "conversion_provenance"),
                             ("module_ser/inputs/hal_guideline.md", "development_guideline"))
    spec["delivery"] = {
        "code_mode": "FROZEN", "origin": "synthetic feature 020 test fixture", "licence": "Apache-2.0",
        "licence_allows_modification": True, "source": f"{REL}/module_tmr/delivery",
        "files": [{"from": "tmr_ll.h", "to": "software/ll/tmr_ll.h"}],
        "scope": {"functions": list(TMR_LL)}, "build": {"style": "forge"}}
    spec["swe1"] = {"level": "functional", "template": TEMPLATE}
    spec["module"] = {"name": "TMR", "components": [
        {"id": "LL_TMR", "layer": "LL", "files": ["software/ll/tmr_ll.h"], "uses": []}]}
    spec["scope_rule"] = {
        "in": [{"group": "counter", "functions": ["LL_TMR_Enable", "LL_TMR_Disable", "LL_TMR_SetPeriod",
                                                  "LL_TMR_GetCounter"], "rm_features": ["43.3.1"]},
               {"group": "flags", "functions": ["LL_TMR_*Flag_UPD"]}],
        "out": [{"group": "one-pulse", "functions": ["LL_TMR_EnableOnePulse"], "rm_features": ["43.3.4"]}],
        "not_delivered": []}
    return spec


def example(tmp: Path, spec: dict | None = None, *, mutate=None, name: str = "ex") -> Path:
    """A temporary example directory holding the (optionally mutated) work order."""
    spec = copy.deepcopy(ser_spec() if spec is None else spec)
    if mutate:
        mutate(spec)
    ex = Path(tmp) / name
    ex.mkdir(parents=True, exist_ok=True)
    (ex / "workorder.json").write_text(json.dumps(spec, indent=1))
    return ex


VOLATILE = ("created_at", "input_baseline_commit", "factory_revision", "tool_versions")


def normalized_manifest(man: dict) -> dict:
    """The prepared manifest without its time-, commit- and path-dependent values (for byte-identity goldens)."""
    m = copy.deepcopy(man)
    for k in VOLATILE:
        if k in m:
            m[k] = "<volatile>"
    if isinstance(m.get("delivery_intake"), dict):
        m["delivery_intake"]["store"] = "<volatile>"
    if isinstance(m.get("resume_identity"), dict):  # the factory assets / tool runtime part changes with every commit
        m["resume_identity"] = {k: m["resume_identity"][k] for k in ("schema", "contract_sha256", "configuration",
                                                                     "input_files") if k in m["resume_identity"]}
    return m
