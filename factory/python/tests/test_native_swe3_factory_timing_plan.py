"""The native author owns its outputs; the existing factory gate owns timing generation.

No model or simulation measurement is fabricated by these procedure/control tests.
"""
import json
import hashlib
import sys

import pytest
from forge_factory import static_timing
from forge_factory.acp import _split_attrs, statements
from forge_factory.inspection import gate
from forge_factory.peripheral import load
from forge_factory.workflow import builder


PERF = {"schema": "forge-c/simulation-performance-budget/1", "instructions_per_call": 2000,
        "microseconds_per_call": 1000, "performance_mips": 100,
        "test_source": "software/tests/target/test_performance.c"}
API = {"instance": "CRC", "functions": ["LL_CRC_ReadData32"],
       "calls": {"LL_CRC_ReadData32": "LL_CRC_ReadData32(CRC)"},
       "signatures": {"LL_CRC_ReadData32": "uint32_t LL_CRC_ReadData32(const CRC_TypeDef *instance)"}}


def graph(*, perf=True, provided=True, style="cmsis", layer="HAL"):
    manifest = {"purpose": "ASPICE_ONLY", "layer": layer,
                "provided": [{"work_order": "WO-PROVIDED"}] if provided else [],
                "provided_build": {"style": style}}
    if perf:
        manifest["simulation_performance"] = PERF
    sections = {k: f"inputs/sections/{k}.md" for k in load("crc")["rm"]["key_sections"]}
    dot, _ = builder.build("WO-SWE3-TIMING-CONTROL", layer=layer, peripheral="crc", trace=True,
                           uspec_gtest=True, assessment_manifest=manifest, sections=sections,
                           provided_api=API if provided else None)
    return dot


def prompt_map(dot):
    out = {}
    for _, _, _, name, attrs in statements(dot):
        values = [a.partition("=")[2] for a in _split_attrs(attrs) if a.startswith("prompt=")]
        if values:
            out[name] = json.loads(values[0], strict=False)  # DOT accepts the existing literal tabs in examples.
    return out


def test_only_the_native_swe3_author_gets_factory_measurement_ownership():
    prompts = prompt_map(graph())
    names = [name for name, text in prompts.items() if "SWE.3 FACTORY TIMING GATE" in text]
    assert names == ["swe3_author"]
    text = prompts["swe3_author"]
    assert "before it honors the author status" in text
    assert "static_timing_bound.json" in text and "frozen SWE.2 api_calls.json cases" in text
    assert "self-BLOCKED solely because no timing tool is exposed" in text
    assert "independent gate can still reject missing, unbounded or over-budget timing" in text
    assert "Never fabricate measurements, edit the factory timing record" in text
    assert "do not infer coverage for other input lengths" in text
    assert "SWE.6 still performs its separate requirement verification" in text


@pytest.mark.parametrize("options", [{"perf": False}, {"provided": False}, {"style": "other"}, {"layer": "LL"}])
def test_no_timing_ownership_instruction_outside_the_explicit_scope(options):
    assert "SWE.3 FACTORY TIMING GATE" not in graph(**options)


@pytest.mark.parametrize("options, exclude, expected", [
    ({"perf": False}, [], "c4d8ff3bf80d34aae0d28a1a9d6c33badffe5848f2fe1ee4a0c95097a092291a"),
    ({"provided": False}, [], "b19b67876214abbb9a93af35f5486681b866b93c7a5d98d04e81fa05d03c5d4d"),
    ({"style": "other"}, [], "cf06006ccec3e3c3a86c3b66a40fd11e702b9991ff666e8276a7ad235098bef8"),
    ({"layer": "LL"}, [], "dc131a9122aed865b0328ec6059300d13eb46211da2f33c7a502e03c5a9d3b02"),
    ({}, ["swe3_author"], "6ba1aef2b677d2601c4684ebbbbf44d4c654d06afb655dd2e06f230a2dfbecfe"),
])
def test_frozen_e014_graph_nodes_outside_the_two_intentional_author_changes(options, exclude, expected):
    # Values measured from a separate clean e014fd86 worktree, not generated from candidate expectations.
    dot = graph(**options).replace(builder._env(), "<ENV>").replace(sys.executable, "<PY>")
    unchanged = {name: attrs for _, _, _, name, attrs in statements(dot)
                 if name not in {"swe6_author", *exclude}}
    assert hashlib.sha256(json.dumps(unchanged, sort_keys=True).encode()).hexdigest() == expected


@pytest.mark.parametrize("status", ["PASS", "BLOCKED"])
def test_real_author_gate_invokes_timing_before_either_author_status(tmp_path, monkeypatch, status):
    # A sentinel at the real factory timing boundary proves call order without claiming a real measurement.
    # The unmodified static_timing tests independently exercise budget/measurement findings.
    ws = tmp_path / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL"}))
    store = type("TimingBoundaryStore", (), {"workspace": ws})()
    seen = []

    class TimingBoundaryReached(Exception):
        pass

    def observe(actual):
        seen.append(actual)
        raise TimingBoundaryReached

    monkeypatch.setattr(static_timing, "gate", observe)
    reply = json.dumps({"status": status, "artifacts": [], "issues": [], "next_action": "next"})
    with pytest.raises(TimingBoundaryReached):
        gate.step_author(store, "SWE.3", reply)
    assert seen == [ws]


@pytest.mark.parametrize("status, timing_issues, missing, accepted", [
    ("PASS", [], [], True),
    ("BLOCKED", [], [], False),
    ("PASS", ["STATIC_TIMING_OVER_BUDGET: control case"], [], False),
    ("BLOCKED", ["STATIC_TIMING_NOT_BOUNDED: control case"], [], False),
    ("PASS", [], ["workproducts/SWE.3/detailed_design.md"], False),
])
def test_author_reply_never_overrides_timing_or_required_output_rejection(
        tmp_path, monkeypatch, status, timing_issues, missing, accepted):
    # Controlled Store/timing edges, real step_author decision. No compiler/simulator result is claimed.
    ws = tmp_path / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL"}))

    class ControlStore:
        workspace = ws
        frozen = False

        def missing_outputs(self, phase):
            return list(missing)

        def latest_baseline(self, phase):
            return None

        def freeze(self, phase, role):
            self.frozen = True
            return {"baseline_id": "CONTROL-BASELINE", "baseline_hash": "control"}

    monkeypatch.setattr(static_timing, "gate", lambda actual: list(timing_issues))
    store = ControlStore()
    reply = json.dumps({"status": status, "artifacts": [], "issues": [], "next_action": "next"})
    result = gate.step_author(store, "SWE.3", reply)
    assert (result == 0) is accepted and store.frozen is accepted
    records = [json.loads(line) for line in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
    final = records[-1]
    assert final["result"] == ("FROZEN" if accepted else "REJECTED")
    if timing_issues:
        assert all(issue in final["issues"] for issue in timing_issues)
