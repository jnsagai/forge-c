"""Feature 020 T010 (US1, FR-005): the governance nodes of a functional-level SWE.1 graph.

For a functional order the SWE.1 graph starts `swe1_governance` (model step, time-box continuation like every
structured node) -> `swe1_governance_check` (deterministic coverage check) -> the SWE.1 author; a failed check goes to
the finalizer, so the author never starts. Register-level graphs have no governance node and stay identical to the
T007 golden. The runner steps `governance` / `governance-check` and the continuation check read their own reply."""
from __future__ import annotations

import json
import re

import pytest
from forge_factory.workflow import builder

FUNCTIONAL = {"swe1_level": "functional", "swe1_template": "swe1-functional-v1"}
ST = {"model": "golden-model:q8", "author_model": "golden-author:q8", "inspector_model": "golden-inspector:q8",
      "timeout_s": 3600, "visit_time_s": 240, "phases": ["SWE.1"], "inspect_phases": ["SWE.1"],
      "two_phase_inspection": True}
KW = dict(layer="LL+HAL", trace=True, brownfield="FROZEN", delivery_style="cmsis", stop_after="SWE.1")


@pytest.fixture(autouse=True)
def lrtx_root(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path / "lrtx"))


def edges(g: str) -> set[str]:
    return {ln.strip() for ln in g.splitlines() if "->" in ln}


def node(g: str, name: str) -> str:
    m = re.search(rf"^  {name} \[(.*)\]$", g, re.M)
    assert m, name
    return m.group(1)


def test_functional_graph_runs_governance_and_its_check_before_the_author():
    st = {k: v for k, v in ST.items() if k not in ("author_model", "inspector_model")}
    g, nodes = builder.build("WO-F020-G", structured=st, assessment_manifest=dict(FUNCTIONAL), **KW)
    e = edges(g)
    assert "start -> swe1_governance" in e and "start -> swe1_author" not in e
    assert {"swe1_governance -> swe1_governance_cont",
            'swe1_governance_cont -> swe1_governance_more [condition="outcome=succeeded"]',
            "swe1_governance_cont -> swe1_governance_check", "swe1_governance_more -> swe1_governance_cont",
            'swe1_governance_check -> swe1_author [condition="outcome=succeeded"]',
            "swe1_governance_check -> finalize"} <= e
    gov = node(g, "swe1_governance")
    assert "forge_factory.lrtx.runner governance --phase SWE.1" in gov and "--model golden-model:q8" in gov
    assert "max_visits=" in gov and 'timeout="3600s"' in gov
    assert "--resume" in node(g, "swe1_governance_more")
    chk = node(g, "swe1_governance_check")
    assert "forge_factory.lrtx.runner governance-check --phase SWE.1" in chk and "--model" not in chk
    assert "continue-check --phase SWE.1 --workspace . --of governance" in node(g, "swe1_governance_cont")
    assert nodes["swe1_governance"]["role"] == "swe1-author" and nodes["swe1_governance"]["phase"] == "SWE.1"
    # the rest of the SWE.1 graph (two-phase inspection, rework route) is the register-level one
    assert "swe1_author -> swe1_author_cont" in e and "swe1_iq_check -> swe1_author_gate" in e
    assert 'swe1_route -> swe1_author [condition="outcome=succeeded"]' in e  # rework never re-runs governance


def test_functional_graph_with_model_swap_serves_the_author_model_for_governance():
    g, _ = builder.build("WO-F020-G", structured=dict(ST), assessment_manifest=dict(FUNCTIONAL), **KW)
    e = edges(g)
    assert "start -> swe1_governance_serve" in e
    assert 'swe1_governance_serve -> swe1_governance [condition="outcome=succeeded"]' in e
    assert 'swe1_governance_check -> swe1_author_serve [condition="outcome=succeeded"]' in e
    assert "--model golden-author:q8" in node(g, "swe1_governance_serve")
    assert "--model golden-author:q8" in node(g, "swe1_governance") and "swe1_governance_check_serve" not in g


def test_register_level_graph_has_no_governance_node_and_matches_the_golden():
    from test_f020_identity import GOLDEN, GRAPHS, _graph

    g, _ = builder.build("WO-F020-G", structured=dict(ST), **KW)
    assert "governance" not in g
    golden = json.loads(GOLDEN.read_text())["graphs"]
    name = "structured-swe1-two-phase-llhal-frozen"
    assert _graph(GRAPHS[name]) == golden[name]
    reg = {**FUNCTIONAL, "swe1_level": "register"}
    g2, _ = builder.build("WO-F020-G", structured=dict(ST), assessment_manifest=reg, **KW)
    assert "governance" not in g2


def test_functional_order_without_a_structured_swe1_author_is_refused():
    with pytest.raises(ValueError, match="SWE1_FUNCTIONAL_NEEDS_STRUCTURED_SWE1"):
        builder.build("WO-F020-G", assessment_manifest=dict(FUNCTIONAL), **KW)


def test_runner_governance_check_exit_code_follows_the_recorded_state(tmp_path, capsys):
    from forge_factory.lrtx import runner

    ws = tmp_path / "ws"
    (ws / ".forge-run/lrtx/SWE.1/governance").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(FUNCTIONAL))
    assert runner.main(["governance-check", "--phase", "SWE.1", "--workspace", str(ws)]) == 1  # nothing generated
    assert "GOVERNANCE_NOT_GENERATED" in capsys.readouterr().out
    (ws / ".forge-run/lrtx/SWE.1/governance-reply.json").write_text(json.dumps({"status": "CONTINUE"}))
    assert runner.main(["continue-check", "--phase", "SWE.1", "--workspace", str(ws), "--of", "governance"]) == 0
    (ws / ".forge-run/lrtx/SWE.1/governance-reply.json").write_text(json.dumps({"status": "PASS"}))
    assert runner.main(["continue-check", "--phase", "SWE.1", "--workspace", str(ws), "--of", "governance"]) == 1


def test_line_product_check_accepts_the_functional_graph(tmp_path):
    from forge_factory.afo import line_product_context as C
    from forge_factory.lrtx import profile as P
    from forge_factory.workflow.builder import binding_for

    prof = P.load("local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104")
    rm = prof["structured"]["role_models"]
    st = {**ST, "model": rm["author"], "author_model": rm["author"], "inspector_model": rm["inspector"]}
    g, nodes = builder.build("WO-X", structured=st, assessment_manifest=dict(FUNCTIONAL), **KW)
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/workflow.fabro").write_text(g)
    binding_for("WO-X", str(ws.resolve()), nodes).dump(ws / ".forge-run/binding.json")
    (ws / ".forge-run/model-profile.json").write_text(json.dumps({"default": rm["author"]}))
    job = {"model": rm["author"], "job_id": "afo-product-x", "nonce": "n", "factory_revision": {"commit": "a" * 40}}
    ref = C.capture(ws, job, prof, phase="SWE.1")
    ctx = json.loads(open(ref["path"]).read())
    assert {ctx["nodes"][n]["role"] for n in ("swe1_governance", "swe1_governance_more")} == {"swe1-author"}
