"""CAPA-055 (PG-T018 finding): the SWE.1 source check read only the first RM page of a source line and required every
named field to be on it - i003 SWR-013 (RM0486 p.2989; p.2990; p.2991: RVU on p.2990, ONF on p.2991) and RCC r164
SWR-001/002/007 (p.480; p.482: HSIRDY on p.482) were flagged although they cite the right pages. A field now counts
when it appears on ANY page the requirement cites (all sources, lists and ranges); a field on none is still flagged."""
from forge_factory.assurance import swe12
from test_easa_m3_m4 import REQS, _ws, sections  # noqa: F401 - pytest fixture

TWO = ("# Software requirements\n- **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION "
       "and report RCC_SR.HSIRDY.\n  - Source: {src}\n")


def _src(sections, src):  # noqa: F811
    return [x for x in swe12.check_requirements(_ws(sections, TWO.format(src=src)))["major_findings"] if "SOURCE" in x]


def test_capa055_field_on_any_cited_page(sections):  # noqa: F811
    assert _src(sections, "RM0486 p.480; RM0486 p.482") == []   # r164 shape: HSIRDY is on the second page
    assert _src(sections, "RM0486 p.480-482") == []             # a range
    assert _src(sections, "RM0486 pp. 480, 482") == []          # a list


def test_capa055_field_on_no_cited_page_still_flagged(sections):  # noqa: F811
    assert _src(sections, "RM0486 p.482") == ["REQ_SOURCE_MISMATCH:SWR-001:HSION not on p.482"]
    assert "REQ_SOURCE_MISMATCH:SWR-001:HSION not on p.482" in swe12.check_requirements(
        _ws(sections, REQS.replace("RM0486 p.480", "RM0486 p.482")))["major_findings"]
    assert _src(sections, "RM0486 p.9999") == ["REQ_SOURCE_PAGE_NOT_IN_INPUTS:SWR-001:p.9999"]


def test_capa055_cited_pages_parser():
    assert swe12.cited_pages("RM0486 p.2989; RM0486 p.2990; RM0486 p.2991") == [2989, 2990, 2991]
    assert swe12.cited_pages("RM0486 p.2989-2991") == [2989, 2990, 2991]
    assert swe12.cited_pages("RM0486 pp. 480–482") == [480, 481, 482]
    assert swe12.cited_pages("work-order HAL scope.") == []
