"""CAPA-051 (i003, OD-2026-10-20-03): acp.attach matched node statements line by line, so an author node whose prompt
holds real line breaks (swe4_test_author's unit-test example, swe3_hal_author's HAL example) was never moved to Codex
and ran on the Fabro run model (DeepSeek). The owner suspended DeepSeek: a run must leave no agent node on it."""
from pathlib import Path

import pytest
from forge_factory import acp
from forge_factory import workorder as W
from forge_factory.workflow.builder import build

SHAPES = [dict(layer="LL"), dict(layer="LL+HAL"), dict(layer="LL", peripheral="iwdg"),
          dict(layer="LL", brownfield="FROZEN"), dict(layer="LL+HAL", brownfield="FIX_ALLOWED")]


def _both(graph, nodes):
    g, a = acp.attach(graph, nodes, Path("/ws"))
    g, b = acp.attach(g, nodes, Path("/ws"), roles=acp.NON_AUTHOR_ROLES, agent="claude")
    return g, a, b


@pytest.mark.parametrize("kw", SHAPES)
def test_capa051_every_agent_node_leaves_the_run_model(kw):
    graph, nodes = build("WO-X", **kw)
    assert acp.native_agent_nodes(graph)  # before: every agent node is native
    g, a, b = _both(graph, nodes)
    assert acp.native_agent_nodes(g) == []
    assert "swe4_test_author" in a
    assert g.count("\n") == graph.count("\n")  # multi-line prompts keep their text
    if "HAL" in kw["layer"] and not kw.get("brownfield"):
        assert "swe3_hal_author" in a


def test_capa051_multiline_prompt_and_bracket_in_string():
    nodes = {"au": {"role": "swe4-author"}, "ins": {"role": "swe4-inspector"}}
    graph = ('digraph X {\n  au [label="A", model="m", prompt="x[0] = 1;\n} \\"]\\" done", max_visits=3]\n'
             '  ins [label="I", prompt="check"]\n  au -> ins\n}\n')
    g, a, b = _both(graph, nodes)
    assert (a, b) == (["au"], ["ins"]) and acp.native_agent_nodes(g) == []
    assert 'model="m"' not in g and 'prompt="x[0] = 1;\n} \\"]\\" done", max_visits=3]' in g
    assert g.endswith("  au -> ins\n}\n")


def test_capa051_single_line_statement_unchanged_apart_from_backend():
    nodes = {"au": {"role": "swe3-author"}}
    g, a = acp.attach('  au [label="A", model="m", prompt="p", timeout="9s"]\n', nodes, Path("/ws"))
    assert g == f'  au [backend="acp", acp.command="{acp.acp_command(Path("/ws"), "au")}", label="A", prompt="p", ' \
                'timeout="9s"]\n'


def test_capa051_suspended_provider_refused_without_acp():
    assert W.suspension("deepseek")["decision"] == "OD-2026-10-20-03"
    assert W.suspension("ollama") is None
    with pytest.raises(RuntimeError, match="MODEL_SUSPENDED:deepseek"):
        W.run(Path("/nonexistent"), "WO-X", model="deepseek-flash", provider="deepseek")
    with pytest.raises(RuntimeError, match="MODEL_SUSPENDED:deepseek"):
        W.run(Path("/nonexistent"), "WO-X", model="deepseek-flash", provider="deepseek", acp_authors="codex")


def test_capa051_suspension_file(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("schema_version: '1.0'\nsuspended:\n  - provider: x\n    decision: OD-1\n")
    assert W.suspension("x", p)["decision"] == "OD-1" and W.suspension("deepseek", p) is None
    assert W.suspension("x", tmp_path / "missing.yaml") is None
