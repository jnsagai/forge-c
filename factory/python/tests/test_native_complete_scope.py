"""Native model prompts must not narrow an owner's literal scope to catalog seeds."""
import json
import re

import pytest
from forge_factory import workorder
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import swe1
from forge_factory.lrtx.obligations import scope_sections
from forge_factory.workflow.builder import build


def prompts(graph):
    return dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', graph))


@pytest.mark.parametrize("layer,example", [("LL", "0002a-arm_55_rcc_ll"), ("HAL", "0002b-arm_55_rcc_hal")])
def test_real_owner_scope_reaches_author_and_inspector(tmp_path, monkeypatch, layer, example):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, manifest = workorder.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-COMPLETE-SCOPE", purpose="ASPICE_ONLY")
    # Builder-only test: a HAL execution still requires independently verified LL.
    manifest["scope"] = json.loads((REPO_ROOT / "examples" / example / "workorder.json").read_text())["scope"]
    sections = {key: value["file"] for key, value in swe1._section_files(ws).items()}
    graph, _ = build("WO-COMPLETE-SCOPE", layer=layer, peripheral=manifest.get("peripheral"), sections=sections, chunk_lines=150,
                     assessment_manifest=manifest)
    p = prompts(graph)
    selected = scope_sections(manifest["scope"], "RM0486", ["14.10.1", "14.10.2", "14.10.79", "14.10.64"])
    if layer == "LL":
        assert len(selected) == 25
    else:
        assert selected
    for section in selected:
        path = sections[section]
        assert path in p["swe1_author"] and path in p["swe2_author"]
    assert "12-26 requirements" not in p["swe1_author"]
    assert "8-15 requirements" not in p["swe1_author"]
    assert "enough atomic requirements to cover the full scope" in p["swe1_author"]
    for node in ("swe1_author", "swe1_inspector"):
        assert "Missing coverage is a finding" in p[node]
        assert "explicit simulation_performance allocation: at most 64" in p[node]
        assert "not a bound for unmeasured timeout paths or physical hardware WCET" in p[node]
    assert "Simulation Performance Should Meet Budget" in p["swe6_author"]
    # Native ACP and QM roles obtain their allowance from policy. The old prompt
    # invented a20-call stop even when the actual role had4096/10000 calls.
    assert "at most 20 tool calls" not in graph
    assert "Include every read/query requirement too" in p["swe1_author"]
    if layer == "LL":
        assert "queries return the specified value, not void" in p["swe1_author"]
        assert "LL functions return nothing" not in p["swe1_author"]


def test_missing_literal_section_refuses_before_native_submission():
    sections = {f"14.10.{n}": f"inputs/section-{n}.md" for n in [1, 2, 64, 79]}
    with pytest.raises(ValueError, match="WORKFLOW_SCOPE_SECTION_MISSING:14.10.90"):
        build("WO-MISSING-SCOPE", layer="LL", peripheral="rcc", sections=sections,
              assessment_manifest={"purpose": "ASPICE_ONLY", "scope": ["RM0486 section 14.10.90."]})


@pytest.mark.parametrize("layer", ["LL", "HAL"])
def test_non_rcc_scope_and_domain_rules_are_preserved(layer):
    sections = {f"59.7.{n}": f"inputs/section-59.7.{n}.md" for n in range(1, 6)}
    graph, _ = build("WO-IWDG-SCOPE", layer=layer, peripheral="iwdg", sections=sections,
                     assessment_manifest={"purpose": "ASPICE_ONLY", "scope": ["RM0486 sections 59.7.1–59.7.5."]})
    p = prompts(graph)
    assert "inputs/section-59.7.5.md" in p["swe1_author"]
    assert "IWDG" in p["swe1_author"] and "RCC_" not in p["swe1_author"]
    assert "write the start key" in p["swe1_author"] if layer == "LL" else "HAL_IWDG" in p["swe2_author"]
    assert "never invent a target cycle bound" in p["swe1_author"]


def test_scope_does_not_leak_into_the_next_legacy_build():
    sections = {f"59.7.{n}": f"inputs/section-{n}.md" for n in range(1, 5)}
    build("WO-PREVIOUS-SCOPE", layer="LL", peripheral="iwdg", sections=sections,
          assessment_manifest={"purpose": "ASPICE_ONLY", "scope": []})
    graph, _ = build("WO-LEGACY", layer="LL", peripheral="rcc")
    p = prompts(graph)
    assert "12-26 requirements" in p["swe1_author"] and "Missing coverage is a finding" not in graph
