"""RPR-089 (Fabro runs WO-F014-SWE2-CRCK-20261101-01 -> WO-F014-SWE3-CRCK-20261101-01, Omniverse2, 2026-11-01): the
brownfield CRC IDR SWE.2 froze a call contract (workproducts/SWE.2/api_calls.json) whose calls pass the undeclared
identifier CRC_Instance; nothing at SWE.2 compiled it. SWE.3 (which may not edit SWE.2 files) was rejected three times
with CONTRACT_CALL_DOES_NOT_COMPILE until the route stopped it as STUCK (about 4.3 h of author time).

Scenario: a brownfield (delivered ST code, CMSIS build) CRC IDR workspace at SWE.2 with that call contract, through the
real SWE.2 author gate. Symptom: the SWE.2 author gate records no CONTRACT_CALL_DOES_NOT_COMPILE finding."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "a brownfield SWE.2 call contract that does not compile against the delivered header passes the SWE.2 author gate"
ST = "inputs/st/stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc/stm32n6xx_ll_crc.h"
DEV = "inputs/st/cmsis-device-n6-v1.4.0/src/cmsis-device-n6-1.4.0/Include"
CORE = "inputs/st/stm32cuben6-v1.4.0-cmsis-core/src"
VENDOR = [(DEV, "stm32n6xx.h"), (DEV, "stm32n657xx.h"), (DEV, "system_stm32n6xx.h"), (CORE, "core_cm55.h"),
          (CORE, "cmsis_version.h"), (CORE, "cmsis_compiler.h"), (CORE, "cmsis_gcc.h"), (CORE, "m-profile/cmsis_gcc_m.h"),
          (CORE, "m-profile/armv8m_mpu.h"), (CORE, "m-profile/armv8m_pmu.h"), (CORE, "m-profile/armv7m_cachel1.h")]


def main() -> int:
    data = Path(os.environ.get("FORGE_DATA_ROOT", "/nonexistent"))
    if not (data / ST).is_file() or shutil.which("arm-none-eabi-gcc") is None:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:pinned ST sources or arm-none-eabi-gcc not available")
        return 2
    from forge_factory.inspection import gate
    from forge_factory.inspection.engine import Store
    from forge_factory.layer import REGISTER_CONTRACT
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO-RPR089/workspace"
        os.environ["FORGE_STATE_DIR"] = str(Path(td) / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(Path(td) / "state/events")
        (ws / ".forge-run/gates").mkdir(parents=True)
        (ws / ".forge-run/manifest.json").write_text(json.dumps({
            "work_order": "WO-RPR089", "layer": "LL", "peripheral": "crc", "register_contract": REGISTER_CONTRACT,
            "delivery": {"code_mode": "FROZEN", "build": {"style": "cmsis", "defines": ["STM32N657xx"], "secure": True},
                         "files": [{"from": "Inc/stm32n6xx_ll_crc.h", "to": "software/ll/stm32n6xx_ll_crc.h"}],
                         "scope": {"functions": ["LL_CRC_Write_IDR", "LL_CRC_Read_IDR"]}},
            "delivered": [{"path": "software/ll/stm32n6xx_ll_crc.h", "role": "delivered_code"}]}))
        (ws / "software/ll").mkdir(parents=True)
        shutil.copyfile(data / ST, ws / "software/ll/stm32n6xx_ll_crc.h")
        for src, rel in VENDOR:
            (ws / "inputs/vendor/include" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(data / src / rel, ws / "inputs/vendor/include" / rel)
        sec = ws / "inputs/sections/RM0486"
        sec.mkdir(parents=True)  # register facts only (offset, reset, field bits), in Forge-C wording
        (sec / "26.4.2_CRC_independent_data_register_CRC_IDR.md").write_text(
            "# 26.4.2 CRC independent data register (CRC_IDR)\n\nAddress offset: 0x04\n\nReset value: 0x0000 0000\n\n"
            "Bits 31:0 IDR[31:0]: 32-bit general-purpose data, not changed by the CRC calculation.\n")
        (ws / "workproducts/SWE.1").mkdir(parents=True)
        (ws / "workproducts/SWE.1/register_effects.json").write_text(json.dumps({"schema": "forge-c/register-effects/1", "effects": [
            {"case": "CRC_IDR_IDR_WRITE", "swr": "SWR-001", "register": "CRC_IDR", "field": "IDR", "op": "write", "value": "0xA5A5A5A5"},
            {"case": "CRC_IDR_IDR_READ", "swr": "SWR-002", "register": "CRC_IDR", "field": "IDR", "op": "no_write"}]}))
        (ws / "workproducts/SWE.2").mkdir(parents=True)
        (ws / "workproducts/SWE.2/api_calls.json").write_text(json.dumps({"schema": "forge-c/api-calls/1", "calls": {
            "CRC_IDR_IDR_WRITE": {"function": "LL_CRC_Write_IDR", "args": ["CRC_Instance", "0xA5A5A5A5U"]},
            "CRC_IDR_IDR_READ": {"function": "LL_CRC_Read_IDR", "args": ["CRC_Instance"]}}}))
        reply = json.dumps({"status": "PASS", "artifacts": [], "issues": [], "next_action": "next"})
        try:
            gate.step_author(Store(ws), "SWE.2", reply)
        except SystemExit:
            pass
        log = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines() if x.strip()]
        author = [e for e in log if e.get("step") == "author" and e.get("phase") == "SWE.2"]
        if not author:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the SWE.2 author gate recorded nothing")
            return 2
        issues = author[-1].get("issues") or []
    if any(str(i).startswith("CONTRACT_CALL_DOES_NOT_COMPILE") for i in issues):
        print("SYMPTOM_ABSENT")
        return 0
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
