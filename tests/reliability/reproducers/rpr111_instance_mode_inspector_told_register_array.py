"""RPR-111 (Fabro run WO-F014-CMP-SWE2-OBL-20261102-06, cloud comparison line, loop10, 2026-11-02): CRC IDR 0014i in
instance mode (caller-supplied CRC_TypeDef *CRCx). The SWE.2 inspector instructions carried the fixed ADR-0009 note
("the driver uses only the extern volatile uint32_t ll_<p>_regs array"), so the inspector failed the correct
caller-instance architecture on SWE2-02/04/06 three times: BLOCKED STUCK SAME_ITEM_FAILED_3X.

Scenario: the real lrtx.review inspector notes for SWE.2 of an LL work order whose operation scope declares a
caller-supplied instance (the instance declaration and the CRC profile are stubbed; no file is read or written).
Symptom: the notes demand the register-block array instead of the declared instance."""
import sys
import tempfile
from pathlib import Path

SIG = "an instance-mode SWE.2 inspector is told the extern register-block array is the required register access"
INST = {"parameter": "CRCx", "macro": "CRC", "type_name": "CRC_TypeDef", "device_header": "forge_crc_device.h",
        "host_object": "forge_host_crc"}


def main() -> int:
    from forge_factory import layer
    from forge_factory.lrtx import review

    layer.ll_instance = lambda _ws=None: dict(INST)
    real_profile = layer.profile
    layer.profile = lambda _ws=None: {**real_profile(None), "id": "crc", "register_prefix": "CRC",
                                      "ll": {**real_profile(None)["ll"], "register_block": "ll_crc_regs"}}
    review.profile = layer.profile
    with tempfile.TemporaryDirectory() as td:
        try:
            notes = " ".join(review._notes(Path(td), "SWE.2", "SWE2-02"))
        except Exception as exc:  # noqa: BLE001
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{type(exc).__name__}:{str(exc)[:120]}")
            return 2
    if "extern volatile uint32_t" in notes:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if "CRC_TypeDef *CRCx" in notes:
        print("SYMPTOM_ABSENT")
        return 0
    print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no register-access note in the SWE.2 inspector notes")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
