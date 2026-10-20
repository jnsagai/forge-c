"""RPR-059 (PG-T018 / i003 SWR-013, RCC r164 SWR-001): the SWE.1 source check read only the first RM page of a source
line and flagged a field that is on another page the requirement also cites (REQ_SOURCE_MISMATCH false positive)."""
import sys
import tempfile
from pathlib import Path

SIG = "field on a later cited page flagged as not on the source page"
CR = ("<!-- source: RM0486 section 14.10.1 starting p.479 -->\n#### 14.10.1 RCC control register (RCC_CR)\n"
      "<!-- source: RM0486 p.480 -->\n                Address offset: 0x0\n             Bit 3 HSION: HSI oscillator enable\n")
SR = ("<!-- source: RM0486 section 14.10.2 starting p.481 -->\n#### 14.10.2 RCC status register (RCC_SR)\n"
      "<!-- source: RM0486 p.482 -->\n                Address offset: 0x4\n             Bit 3 HSIRDY: HSI ready\n")
REQ = ("# Software requirements\n- **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION "
       "and report RCC_SR.HSIRDY.\n  - Source: RM0486 p.480; RM0486 p.482\n")


def main() -> int:
    from forge_factory.assurance import swe12

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        s = ws / "inputs/sections/RM0486"
        s.mkdir(parents=True)
        (s / "14.10.1_RCC_CR.md").write_text(CR)
        (s / "14.10.2_RCC_SR.md").write_text(SR)
        (ws / "workproducts/SWE.1").mkdir(parents=True)
        (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQ)
        found = [x for x in swe12.check_requirements(ws)["major_findings"] if x.startswith("REQ_SOURCE_MISMATCH")]
    if found:
        print(f"findings: {found}")
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
