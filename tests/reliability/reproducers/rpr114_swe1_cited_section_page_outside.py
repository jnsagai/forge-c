"""RPR-114 (Fabro run WO-F014-SWE1-CRCL-20261102-L12, local line, Omniverse2, 2026-11-02): full CRC LL SWE.1. SWR-006
(LL_CRC_SetOutputDataReverseMode, CRC_CR task, section pages 1173-1174) cites RM0486 26.4.3 in its text but took
source page 1175, the first page of 26.4.6 (register map). The author gate accepted the page (the task-section check
allows two pages of slack), the assembly traced the requirement by page to RM0486-26.4.6, and the cross-inspection
failed SWE1-01 and SWE1-05 (the text cites 26.4.3, the trace row names 26.4.6); the author never got a finding.

Scenario: the real swe1.validate_group author check of a CRC_CR register task with the incident's requirement, against
an RM section index of ch.26 registers (section numbers, titles, start pages and page anchors only, in Forge-C wording;
no vendor text) written under TMPDIR. Manifest and peripheral profile are stubbed.
Symptom: the author check reports no finding for a source page outside the section the statement cites."""
import sys
import tempfile
from pathlib import Path

SIG = "a SWE.1 requirement citing an RM section with a source page outside that section passes the author check"
SECTIONS = {  # number: (title, start page, further page anchors)
    "26.4": ("CRC registers", 1172, []),
    "26.4.1": ("CRC data register (CRC_DR)", 1172, []),
    "26.4.2": ("CRC independent data register (CRC_IDR)", 1172, [1173]),
    "26.4.3": ("CRC control register (CRC_CR)", 1173, [1174]),
    "26.4.4": ("CRC initial value (CRC_INIT)", 1174, []),
    "26.4.5": ("CRC polynomial (CRC_POL)", 1174, [1175]),
    "26.4.6": ("CRC register map", 1175, []),
}
STATEMENT = ("When LL_CRC_SetOutputDataReverseMode is called with a requested output reversal mode, the CRC LL driver "
             "shall set both CRC_CR.REV_OUT (bits 8:7) and CRC_CR.RTYPE_OUT (bit 10) from one mode value, per RM0486 "
             "26.4.3, and preserve every other CRC_CR field.")


def workspace(root: Path) -> None:
    rows = []
    for num, (title, page, more) in SECTIONS.items():
        rel = f"inputs/sections/RM0486/{num}_{title.replace(' ', '_').replace('(', '').replace(')', '')}.md"
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(f"<!-- source: RM0486 section {num} starting p.{page} -->\n# {num} {title}\n"
                                + "".join(f'<a id="p-{p}"></a>\n' for p in more))
        rows.append(f"{num} | {title} | p.{page} | {rel}")
    (root / "inputs/index.md").write_text("\n".join(rows) + "\n")


def main() -> int:
    from forge_factory import layer
    from forge_factory.lrtx import swe1

    layer.profile = lambda _ws=None: {"id": "crc", "register_prefix": "CRC", "rm": {"doc": "RM0486"}}
    swe1._manifest = lambda _ws: {"scope": ["Implement LL_CRC_SetOutputDataReverseMode (CRC_CR.REV_OUT, "
                                            "CRC_CR.RTYPE_OUT)."]}
    sysname = "CRC LL driver"
    req = {"key": "set_output_reverse", "statement": STATEMENT, "source_page": 1175,
           "verification": "Host unit test calls the function for each mode; passes when CRC_CR.REV_OUT and "
           "CRC_CR.RTYPE_OUT hold the mode's bits.", "verified_by": "host_unit_test",
           "effects": [{"case": "REV_OUT_BYTE", "register": "CRC_CR", "field": "REV_OUT", "op": "write", "value": "0x1"},
                       {"case": "RTYPE_OUT_BIT", "register": "CRC_CR", "field": "RTYPE_OUT", "op": "set", "value": ""}]}
    doc = {"requirements": [req], "not_covered": [], "open_points": []}
    group = {"id": "CRC_CR", "register": "CRC_CR", "section": "26.4.3", "pages": [1173, 1174],
             "fields": {"REV_OUT": {"msb": 8, "lsb": 7, "access": ["rw"]},
                        "RTYPE_OUT": {"msb": 10, "lsb": 10, "access": ["rw"]}}}
    idx = {"CRC_CR": {"fields": dict(group["fields"])}}
    with tempfile.TemporaryDirectory() as td:
        workspace(Path(td))
        try:
            found = swe1.validate_group(Path(td), doc, group, sysname, idx)
        except Exception as exc:  # noqa: BLE001
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{type(exc).__name__}:{str(exc)[:120]}")
            return 2
    if not isinstance(found, list):
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the author check returned no finding list")
        return 2
    page = [f for f in found if "source_page 1175" in f and "26.4.3" in f]
    if not page:
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
