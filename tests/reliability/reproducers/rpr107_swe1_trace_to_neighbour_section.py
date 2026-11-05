"""RPR-107 (Fabro run WO-F014-CMP-SWE1-IWDG-20261102-02, cloud comparison line, loop10, 2026-11-02): IWDG LL greenfield
SWE.1. The deterministic SWE.1 assembly traced the IWDG_KR requirements (task section RM0486 59.7.1, p.2989) to
RM0486-59.7.2 in traceability/upstream_gaps.md, because 59.7.1 and 59.7.2 both start on p.2989 and the page lookup
takes the last section starting on or before the page. The inspector rejected SWE1-01/SWE1-05 three times; the author
cannot change the assembled trace, so the order stopped BLOCKED STUCK (SAME_ITEM_FAILED_3X).

Scenario: the real swe1.assemble trace mapping for an IWDG_KR register task with one requirement on p.2989, against
the RM0486 ch.59 register section index (section numbers, titles and pages only). Manifest, system name and profile
are stubbed and the assembly stops right after the requirement rows are traced (rendering is not part of the symptom).
Symptom: the KR requirement's upstream is not RM0486-59.7.1."""
import sys
import tempfile
from pathlib import Path

SIG = "a register task's requirement on a page shared by two RM sections traces to the neighbour section"
INDEX = """59.7 | IWDG registers | p.2988 | inputs/sections/RM0486/59.7_IWDG_registers.md
59.7.1 | IWDG key register (IWDG_KR) | p.2989 | inputs/sections/RM0486/59.7.1_IWDG_key_register_IWDG_KR.md
59.7.2 | IWDG prescaler register (IWDG_PR) | p.2989 | inputs/sections/RM0486/59.7.2_IWDG_prescaler_register_IWDG_PR.md
59.7.3 | IWDG reload register (IWDG_RLR) | p.2990 | inputs/sections/RM0486/59.7.3_IWDG_reload_register_IWDG_RLR.md
59.7.4 | IWDG status register (IWDG_SR) | p.2990 | inputs/sections/RM0486/59.7.4_IWDG_status_register_IWDG_SR.md
"""


class Reached(Exception):
    pass


def main() -> int:
    from forge_factory import layer
    from forge_factory.lrtx import swe1

    swe1._manifest = lambda _ws: {}
    swe1.system_name = lambda _ws: "IWDG LL driver"
    layer.profile = lambda _ws: {"id": "iwdg"}

    def stop(*_a, **_k):
        raise Reached()

    swe1.budget_requirements = stop
    req = {"key": "start", "statement": "When LL_IWDG_Enable is called, the IWDG LL driver shall write 0x0000CCCC to "
           "IWDG_KR.KEY.", "source_page": 2989, "verified_by": "host_unit_test", "effects": [], "verification": "passes"}
    group = {"id": "IWDG_KR", "register": "IWDG_KR", "section": "59.7.1", "pages": [2989]}
    rec = {"task": "requirements:IWDG_KR", "doc": {"requirements": [req], "open_points": [], "not_covered": []}}
    cross = {"task": "requirements:crosscutting", "doc": {"requirements": [], "open_points": [], "not_covered": []}}
    inv = {"registers": [{"section": "59.7.1"}], "items": {}}
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "inputs").mkdir()
        (Path(td) / "inputs/index.md").write_text(INDEX)
        try:
            swe1.assemble(Path(td), inv, [(group, rec)], cross)
        except Reached as exc:
            tb = exc.__traceback__
            rows = None
            while tb is not None:
                if tb.tb_frame.f_code.co_name == "assemble":
                    rows = tb.tb_frame.f_locals.get("rows")
                tb = tb.tb_next
        else:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:assembly did not reach the budget requirements")
            return 2
    if not rows:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no traced requirement row")
        return 2
    if rows[0].get("upstream") != "RM0486-59.7.1":
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
