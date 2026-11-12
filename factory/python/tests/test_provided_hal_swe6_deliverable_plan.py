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
    ({"provided_api": None}, "16edc0adfed5fcc4215d4fd4ee7da1260da14d8d307ead0af0626ec7ed9f0374"),
    ({"layer": "LL", "provided_api": None}, "07371d4cbea1af2d0d7e4f4c1b79cb194a9d3cc399c6cd86da2cd0aa81c6db5c"),
    ({"trace": False}, "491d9d590aa21aa55ae39b26724d77c3b0cd5eb139ae391e40353234b70d0ec2"),
    ({"uspec_gtest": False}, "2e80ef2e72754cc2577ec5339d807a725d32a9b052f05643561f07f68a3e239b"),
    ({"stop_after": "SWE.5"}, "0a397e5aa7289eae04607ecc28d97db3500075cc1f7f35a5644fdb1c1e0b94f3"),
])
def test_outside_scope_graphs_are_byte_identical_to_frozen_baseline(options, expected):
    dot = graph(**options)
    assert hashlib.sha256(dot.encode()).hexdigest() == expected
    assert "SWE.6 DELIVERABLE PLAN" not in dot


@pytest.mark.parametrize("peripheral, expected", [
    ("crc", "11327a4b130edb0114d2e0f75bd87348cf7b416531bd0372dc2d0cb12852d39f"),
    ("wwdg", "674dde10de3ba8ce8f955788be7ff08a23702313a21c9e1d55221b6390d1c8d4"),
])
def test_every_other_node_keeps_its_frozen_instructions_and_limits(peripheral, expected):
    dot = graph(peripheral)
    stable = {name: attrs for _, _, _, name, attrs in statements(dot) if name != "swe6_author"}
    assert hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest() == expected
    attrs = next(a for _, _, _, name, a in statements(dot) if name == "swe6_author")
    assert 'max_visits=18' in attrs and 'timeout="1500s"' in attrs
