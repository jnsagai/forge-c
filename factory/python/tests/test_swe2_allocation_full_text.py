"""CAPA-106 (run WO-F014-CMP-SWE2-OBL-20261102-01): the SWE.2 requirement allocation table cut component-level
constraint requirements at 120 characters (the instruction/time budgets of SWR-012/SWR-013 vanished)."""
from forge_factory.lrtx import swe2


def test_a_cell_keeps_the_whole_requirement_and_cannot_split_the_row():
    req = ("When a scoped API is measured in the pinned Renode profile at 100 MIPS without injected interrupts or bus "
           "stalls, the CRC LL driver shall complete each measured call within 64 executed target instructions.")
    assert swe2._cell(req) == req and len(req) > 120
    assert swe2._cell("a | b\nc") == "a \\| b c"
