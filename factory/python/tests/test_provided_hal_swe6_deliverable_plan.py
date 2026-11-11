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
    ({"trace": False}, "c0ca1574c79e13482a74214c89c4eb5b80bebc324ddb451a8e9b9dda0fea587a"),
    ({"uspec_gtest": False}, "2c7de660d51213870d2fc96ab79630508cdc837064ac8ca23482fc81613ff41f"),
    ({"stop_after": "SWE.5"}, "f9ff707defeed3a38e4305c5b5b74e94d853faab54d5e5a5ef66962eb7e573d1"),
])
def test_outside_scope_graphs_are_byte_identical_to_frozen_baseline(options, expected):
    dot = graph(**options)
    assert hashlib.sha256(dot.encode()).hexdigest() == expected
    assert "SWE.6 DELIVERABLE PLAN" not in dot


@pytest.mark.parametrize("peripheral, expected", [
    ("crc", "dacc0d47bf4b461c048038811126adaa454bd6d6e4582bf0d22ba55f83e02316"),
    ("wwdg", "cf84f11ee1e2c4fe53cb998feb21ae29cb7a73d1f3b552572a766a35395df67a"),
])
def test_every_other_node_keeps_its_frozen_instructions_and_limits(peripheral, expected):
    dot = graph(peripheral)
    stable = {name: attrs for _, _, _, name, attrs in statements(dot) if name != "swe6_author"}
    assert hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest() == expected
    attrs = next(a for _, _, _, name, a in statements(dot) if name == "swe6_author")
    assert 'max_visits=18' in attrs and 'timeout="1500s"' in attrs
