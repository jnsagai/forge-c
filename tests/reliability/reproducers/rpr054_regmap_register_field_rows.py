"""RPR-054 (LL r166): the SWE.2 register table named its rows register.field (RCC_CR.HSION); the register map
generator read only bare RCC_ names, BLOCKED with NO_REGISTERS_FROM_SWE2_TABLE and wrote no LL compile unit."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "register map generator finds no register in register.field table rows"
RM_CR = ("#### 14.10.1 RCC control register (RCC_CR)\n                Address offset: 0x0\n"
         "                Reset value: 0x0000 0008\n             Bit 4 HSEON: HSE oscillator enable\n"
         "             Bit 3 HSION: HSI oscillator enable\n")
ARCH = ("# A\n## Register table\n| Name | Offset | Bit position(s) | Access | RM0486 page |\n| --- | --- | --- | --- | --- |\n"
        "| RCC_CR.HSION | 0x000 | 3 | read/write | p.480 |\n| RCC_CR.HSEON | 0x000 | 4 | read/write | p.480 |\n")


def main() -> int:
    from forge_factory.inspection.regmap import generate
    from forge_factory.layer import LL_TU

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "inputs/sections/RM0486").mkdir(parents=True)
        (ws / "inputs/sections/RM0486/14.10.1_RCC_CR.md").write_text(RM_CR)
        (ws / "workproducts/SWE.2").mkdir(parents=True)
        (ws / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
        (ws / ".forge-run").mkdir()
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
        res = generate(ws)
        if res.get("status") != "PASS" or not (ws / LL_TU).is_file():
            print(f"SYMPTOM_PRESENT:{SIG}")
            return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
