"""Feature 020 T007 (SC-007, FR-013): register-level orders are unchanged by the functional SWE.1 level.

The golden `fixtures/f020/register_identity.json` was captured on forge-c-020-base (303b46ea, the deployed owner-lane
commit) with FORGE_GOLDEN_WRITE=1 and is compared byte for byte here:
  - the SWE.1 graphs the builder makes for register-level orders (native LL / HAL / LL+HAL brownfield, structured
    SWE.1 with the feature 018 two-phase inspection, all structured phases), with their node role bindings;
  - the role SKILL files the structured SWE.1 packets carry (swe1-author, swe1-inspector);
  - the SWE.1 author packets (prompt messages + input hash) and the feature 018 phase-1 packets of the IWDG LL order
    (scripted model, git-ignored owner inputs; skipped when they are absent);
  - the SWE.1 author gate's step list and decision on that order.

Identity guard suites (research R1/R2), run on both trees by the T024 regression with no new failure allowed:
test_builder_structured_refactor_golden, test_peripheral_rcc_equivalence, test_lrtx_compat,
test_lrtx_packet_identity, test_builder_stop_after, test_brownfield_stop_after_inject, test_f018_phase1,
test_f018_phase2, test_f018_quality_checklist, test_f018_line_product_graph, test_lrtx_swe1, test_lrtx_v2_swe1,
test_swe1_author_rules, test_f019_derived_campaign, test_f019_ladder_walk, test_owner_supervised_* and the reqif tests.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pytest
from f020_fixtures import FIX
from forge_factory.common import REPO_ROOT, canonical_json
from forge_factory.workflow import builder

GOLDEN = FIX / "register_identity.json"
ALL = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]
ST = {"model": "golden-model:q8", "author_model": "golden-author:q8", "inspector_model": "golden-inspector:q8",
      "timeout_s": 3600, "visit_time_s": 240}
GRAPHS = {
    "native-ll-swe1": dict(layer="LL", trace=True, stop_after="SWE.1"),
    "native-hal": dict(layer="HAL", trace=True, isolation=True),
    "native-llhal-frozen-cmsis-swe1": dict(layer="LL+HAL", trace=True, brownfield="FROZEN", delivery_style="cmsis",
                                           stop_after="SWE.1"),
    "structured-swe1-two-phase": dict(layer="LL", trace=True, peripheral="iwdg", stop_after="SWE.1",
                                      structured={**ST, "phases": ["SWE.1"], "inspect_phases": ["SWE.1"],
                                                  "two_phase_inspection": True}),
    "structured-swe1-two-phase-llhal-frozen": dict(layer="LL+HAL", trace=True, brownfield="FROZEN",
                                                   delivery_style="cmsis", stop_after="SWE.1",
                                                   structured={**ST, "phases": ["SWE.1"], "inspect_phases": ["SWE.1"],
                                                               "two_phase_inspection": True}),
    "structured-all": dict(layer="LL", trace=True, structured={**ST, "phases": ALL, "inspect_phases": ALL,
                                                               "reinspect": True}),
}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _graph(kw: dict) -> dict:
    g, nodes = builder.build("WO-F020-ID", chunk_lines=150, **kw)
    g = g.replace(builder._env(), "<ENV>").replace(sys.executable, "<PY>")
    g = g.replace(os.environ["FORGE_LRTX_ROOT"], "<LRTX>")  # the model-swap nodes name the per-test lrtx root
    return {"graph": _sha(g.encode()), "nodes": _sha(canonical_json(nodes))}


def _record(section: str, got: dict) -> None:
    data = json.loads(GOLDEN.read_text()) if GOLDEN.is_file() else {}
    if os.environ.get("FORGE_GOLDEN_WRITE") == "1":
        data[section] = got
        GOLDEN.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
        pytest.skip(f"golden {section} recorded")
    assert got == data[section]


def test_register_level_swe1_graphs_are_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path / "lrtx"))
    _record("graphs", {name: _graph(kw) for name, kw in GRAPHS.items()})


def test_swe1_role_skills_are_unchanged():
    _record("skills", {r: _sha((REPO_ROOT / f".fabro/skills/{r}/SKILL.md").read_bytes())
                       for r in ("swe1-author", "swe1-inspector")})


DS = REPO_ROOT / "examples/0002-arm_55_rcc_st/inputs/DS14791-rev9-stm32n6x5-x7-datasheet.md"


@pytest.mark.skipif(not DS.is_file(), reason="owner datasheet input (git-ignored) not present")
def test_register_level_packets_and_author_gate_are_unchanged(tmp_path, monkeypatch):
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import swe1
    from forge_factory.lrtx import swe1_quality as Q
    from test_lrtx_swe1 import ANSWERS, _gate, _scripted

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    from forge_factory import workorder
    from forge_factory.workflow.builder import binding_for, build

    ws, _m = workorder.prepare(REPO_ROOT / "examples/0009a-iwdg-ll", "WO-T-IWDG-LL")
    _g, nodes = build("WO-T-IWDG-LL", layer="LL", trace=True, peripheral="iwdg")
    binding_for("WO-T-IWDG-LL", str(ws), nodes).dump(ws / ".forge-run/binding.json")

    def ident(p: dict) -> list[str]:
        return [p["input_hash"], _sha(canonical_json(p["_messages"]))]

    calls: list[dict] = []
    monkeypatch.setattr(S, "call", _scripted(ANSWERS, calls))
    assert swe1.visit(ws, "qwen3-coder:30b")["status"] == "PASS"
    author = {p["task"]: ident(p) for p in calls}

    from forge_factory.inspection import gate

    steps: list[str] = []
    for name in ("check_author_output", "step_author"):
        if hasattr(gate, name):
            orig = getattr(gate, name)
            monkeypatch.setattr(gate, name, lambda *a, _o=orig, _n=name, **k: (steps.append(_n), _o(*a, **k))[1])
    from forge_factory.assurance import register_contract as RC

    for name in ("check_effects",):
        orig = getattr(RC, name)
        monkeypatch.setattr(RC, name, lambda *a, _o=orig, _n=name, **k: (steps.append(f"RC.{_n}"), _o(*a, **k))[1])
    rc = _gate(ws, monkeypatch)

    phase1: list[dict] = []

    def judge(p, **_k):
        phase1.append(p)
        swr = p["output_schema"]["properties"]["requirement_id"]["enum"][0]
        doc = {"requirement_id": swr, "findings": []}
        return {"doc": doc, "errors": S.validate(doc, p["output_schema"]), "usage": None, "wall_ms": 1.0,
                "finish_reason": "stop"}
    monkeypatch.setattr(S, "call", judge)
    assert Q.iq_inspect(ws, "qwen3-coder:30b")["status"] == "PASS"
    _record("iwdg_register_level", {"author_packets": author, "gate": {"rc": rc, "steps": steps},
                                    "phase1_packets": {p["task"]: ident(p) for p in phase1}})
