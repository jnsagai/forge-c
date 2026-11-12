"""CAPA-107: a register task's requirement traces to the task's own RM section when its page is one of that section's
pages - several register sections can start on one page (IWDG_KR 59.7.1 / IWDG_PR 59.7.2 on p.2989, IWDG_RLR 59.7.3 /
IWDG_SR 59.7.4 on p.2990). A page outside the task's section still traces by page."""
from forge_factory.lrtx import swe1

INDEX = """59.4 | IWDG functional description | p.2980 | a.md
59.7.1 | IWDG key register (IWDG_KR) | p.2989 | b.md
59.7.2 | IWDG prescaler register (IWDG_PR) | p.2989 | c.md
59.7.3 | IWDG reload register (IWDG_RLR) | p.2990 | d.md
59.7.4 | IWDG status register (IWDG_SR) | p.2990 | e.md
"""


def test_a_shared_page_traces_to_the_task_section(tmp_path):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs/index.md").write_text(INDEX)
    kr = {"section": "59.7.1", "pages": [2989]}
    rlr = {"section": "59.7.3", "pages": [2990]}
    assert swe1._task_section(tmp_path, 2989, kr) == "59.7.1"
    assert swe1._task_section(tmp_path, 2990, rlr) == "59.7.3"
    assert swe1._page_section(tmp_path, 2989, "59.7.1") == "59.7.2"  # the page alone is ambiguous
    assert swe1._task_section(tmp_path, 2981, kr) == "59.4"  # outside the task's pages: by page
    assert swe1._task_section(tmp_path, None, kr) == "59.7.1"
    assert swe1._task_section(tmp_path, 2989, {"section": "59.7.1", "pages": []}) == "59.7.2"
