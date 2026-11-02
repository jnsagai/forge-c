"""CAPA-102 / CAPA-103 (run WO-F014-SWE5-IWDG-20261101-L5): visit status notes are not routed to test tasks, and a test
indexing the register block by a byte offset is rejected before it runs."""
from forge_factory.lrtx import visit as V


def test_status_notes_are_not_repair_findings():
    fs = ["run_integration: TEST_FAIL:test_iwdg_integration.c:exit1", "defect filed: DEF-001",
          "defect filed: REFUSED:REQUIREMENT_QUOTE_REQUIRED", "time box used; the next node execution resumes at file:target"]
    assert V.routable(fs) == ["run_integration: TEST_FAIL:test_iwdg_integration.c:exit1"]


def test_a_byte_offset_index_is_rejected_and_the_word_index_is_accepted():
    bad = "CHECK(\"IT-001-B\", (ll_iwdg_regs[LL_IWDG_PR_OFFSET] & LL_IWDG_PR_PR_MSK) == 5U);"
    assert V.offset_index_errors(bad, "ll_iwdg_regs", "IWDG") == [
        "ll_iwdg_regs[LL_IWDG_PR_OFFSET] indexes the register block by a byte offset: use "
        "ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U]"]
    good = "x = ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U]; /* not ll_iwdg_regs[LL_IWDG_SR_OFFSET] */"
    assert V.offset_index_errors(good, "ll_iwdg_regs", "IWDG") == []
