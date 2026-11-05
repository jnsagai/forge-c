"""Prospective native SWE.6 planning; frozen e014fd86 controls outside that one author prompt.

These controls qualify procedure order and isolation, not unmeasured LLM success or efficiency.
The actual D attempt is retained in the external OPS evidence index.
"""
import hashlib
import json
import sys

import pytest
from forge_factory.acp import _split_attrs, statements
from forge_factory.workflow import builder


def api(peripheral):
    inst = peripheral.upper()
    fn = f"LL_{inst}_ReadData32" if peripheral == "crc" else f"LL_{inst}_IsEnabled"
    return {"instance": inst, "functions": [fn], "calls": {fn: f"{fn}({inst})"},
            "signatures": {fn: f"uint32_t {fn}(const {inst}_TypeDef *instance)"}}


def graph(peripheral="crc", **kwargs):
    options = {"layer": "HAL", "trace": True, "uspec_gtest": True, "provided_api": api(peripheral)}
    options.update(kwargs)
    dot, _ = builder.build("WO-SWE6-PLAN-CONTROL", peripheral=peripheral, **options)
    return dot.replace(builder._env(), "<ENV>").replace(sys.executable, "<PY>")


def prompt(dot):
    attrs = next(a for _, _, _, name, a in statements(dot) if name == "swe6_author")
    return json.loads(next(a.partition("=")[2] for a in _split_attrs(attrs) if a.startswith("prompt=")))


@pytest.mark.parametrize("peripheral", ["crc", "wwdg"])
def test_first_evidence_precedes_discovery_and_the_report_remains_conditional(peripheral):
    text = prompt(graph(peripheral))
    assert text.index("Call use_skill") < text.index("Call mcp__forge_tests_mcp__run_robot FIRST")
    assert text.index("Call mcp__forge_tests_mcp__run_robot FIRST") < text.index("read_file .forge-run/manifest.json")
    assert text.index("Call mcp__forge_tests_mcp__run_robot FIRST") < text.index("If inspection/SWE.6/")
    assert "SWE.6 DELIVERABLE PLAN" in text
    assert "read each implicated scenario at most once" in text
    assert "Do not create C/Python verification helpers" in text
    assert "Reserve remaining tool calls for the actual edits" in text
    assert "When run_robot PASSes" in text
    assert "workproducts/SWE.6/software_verification_report.md" in text
    assert "never change, weaken or remove it" in text
    assert "report_defect" in text and "requirement_quote" in text
    assert "budget is exhausted" in text and "status BLOCKED" in text


@pytest.mark.parametrize("options, expected", [
    ({"provided_api": None}, "00623657880150f30a0d1217f5d21298c4ce697832b456b8753714bc0cfe1753"),
    ({"layer": "LL", "provided_api": None}, "06291556a9cfeb083e2ff39ab450830ac9e7336aef51ff89144cc081dca1b032"),
    ({"trace": False}, "85ac759a1d4c78333404db8ed9af35f160535fdaf0dbc5a593a34af3f469b0ef"),
    ({"uspec_gtest": False}, "f70e1a3b742166cf0c5af62e0111342a1123dcb8f343d25d98144ebb8f808e1d"),
    ({"stop_after": "SWE.5"}, "ddd4adc509f7f16566e87dd7951ea98c0daf6a10f076b20982bec226d8fc0316"),
])
def test_outside_scope_graphs_are_byte_identical_to_frozen_baseline(options, expected):
    dot = graph(**options)
    assert hashlib.sha256(dot.encode()).hexdigest() == expected
    assert "SWE.6 DELIVERABLE PLAN" not in dot


@pytest.mark.parametrize("peripheral, expected", [
    ("crc", "269c096007a4d509ff0a88e87c9089a2ad738829c5a9a8e215c0104799354f3d"),
    ("wwdg", "d31dad362b04ade37fda9e59e7d5f49c7b97a7f83a3d8d6aa6e879057f9e69c8"),
])
def test_every_other_node_keeps_its_frozen_instructions_and_limits(peripheral, expected):
    dot = graph(peripheral)
    stable = {name: attrs for _, _, _, name, attrs in statements(dot) if name != "swe6_author"}
    assert hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest() == expected
    attrs = next(a for _, _, _, name, a in statements(dot) if name == "swe6_author")
    assert 'max_visits=18' in attrs and 'timeout="1500s"' in attrs
