"""CAPA-218 (TIM LL L43R, Omniverse2 owner lane, 2026-11-10): the TIM input index has no "functional description"
section (54.4 and 54.4.1 are absent; 54.4.2.. are present), so the cross-cutting packet carried no reference-manual source.
The author cited "RM0486 p.3", a page of no provided section; the assembly traced it to the first register section
(54.5.1). The set inspector failed SWE1-05 on that source/trace mismatch in four rounds, rework could not converge and the
order ended MODEL_CONVERGENCE after six phase reworks. The cross-cutting task now falls back to the owner scope's context
sections, and a cross-cutting source_page outside the provided sections is a finding at authoring time."""
import inspect

from forge_factory import layer
from forge_factory.lrtx import swe1

SECTIONS = {"54.3": ("TIM2/TIM3/TIM4/TIM5 implementation", 2626, []),
            "54.4.2": ("TIM2/TIM3/TIM4/TIM5 pins and internal signals", 2628, [2629, 2630]),
            "54.4.3": ("Time-base unit", 2631, [2632]),
            "54.5.1": ("TIMx control register 1 (TIMx_CR1)", 2704, [2705])}
ST = "While no LL function has been called after reset, the TIM LL driver shall not write any TIM register."


def _ws(tmp_path, monkeypatch, sections=SECTIONS):
    rows = []
    (tmp_path / "inputs").mkdir(exist_ok=True)
    for i, (num, (title, page, more)) in enumerate(sections.items()):
        rel = f"inputs/s{i}.md"
        (tmp_path / rel).write_text(f"<!-- source: RM0486 section {num} starting p.{page} -->\n"
                                    + "".join(f'<a id="p-{p}"></a>\n' for p in more))
        rows.append(f"{num} | {title} | p.{page} | {rel}")
    (tmp_path / "inputs/index.md").write_text("\n".join(rows) + "\n")
    monkeypatch.setattr(layer, "profile", lambda _ws=None: {"register_prefix": "TIM", "rm": {"doc": "RM0486",
                                                                                            "chapter": 54}})
    monkeypatch.setattr(swe1, "_manifest", lambda _ws: {"scope": ["TIM2 time base."]})
    monkeypatch.setattr(swe1, "inventory", lambda _ws: {"items": [], "context_sections": []})
    monkeypatch.setattr(swe1, "owner_obligations", lambda _ws: None)
    return tmp_path


def _doc(page):
    return {"requirements": [{"key": "startup_no_write", "statement": ST, "source_page": page,
                              "verification": "Target Robot test; passes when the access log shows no TIM write.",
                              "verified_by": "target_robot_test", "effects": []}],
            "not_covered": [], "open_points": []}


def test_a_crosscutting_page_outside_the_provided_sections_is_a_finding(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    found = [f for f in swe1.validate_group(ws, _doc(3), None, "TIM LL driver", {}) if "source_page" in f]
    assert len(found) == 1 and "source_page 3" in found[0] and "2626-2705" in found[0]
    for page in (2626, 2632, 2704, 2705):
        assert not [f for f in swe1.validate_group(ws, _doc(page), None, "TIM LL driver", {}) if "source_page" in f]


def test_without_an_index_there_is_no_page_finding(tmp_path, monkeypatch):
    monkeypatch.setattr(swe1, "_manifest", lambda _ws: {"scope": []})
    monkeypatch.setattr(layer, "profile", lambda _ws=None: {"register_prefix": "TIM", "rm": {"doc": "RM0486"}})
    assert swe1.crosscut_page_findings(tmp_path, _doc(3)["requirements"][0], {}) == []


def test_the_crosscutting_source_falls_back_to_the_scope_context_sections(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    monkeypatch.setattr(swe1, "inventory", lambda _ws: {"context_sections": ["54.4.2", "54.4.3", "54.9.9"]})
    assert swe1.crosscut_sections(ws) == ["54.4.2", "54.4.3"]  # indexed context sections only


def test_a_functional_description_section_stays_the_source(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch, {**SECTIONS, "54.4": ("TIM2/TIM3/TIM4/TIM5 functional description", 2627, [])})
    monkeypatch.setattr(swe1, "inventory", lambda _ws: (_ for _ in ()).throw(AssertionError("not needed")))
    assert swe1.crosscut_sections(ws) == ["54.4"]


def test_the_packet_uses_the_crosscutting_sections():
    src = inspect.getsource(swe1.crosscut_packet)
    assert "crosscut_sections(ws, secs)" in src
