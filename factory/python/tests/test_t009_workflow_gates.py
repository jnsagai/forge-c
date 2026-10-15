"""T009/T046/T047: generated SWE.1–6 Fabro loops, deterministic gate CLI, no human gates, finalizer reachable."""
import json
import os
import re
import subprocess
import sys

import pytest
from forge_factory.inspection.engine import load_checklist
from forge_factory.workflow.builder import MAX_VISITS, build


def edges(dot):
    return re.findall(r"^\s*(\w+) -> (\w+)(?: \[condition=\"([^\"]+)\"\])?$", dot, re.M)


def test_graph_has_six_separate_loops_and_verification_node():
    dot, nodes = build("wo-test")
    assert "hexagon" not in dot  # no human gate in unattended run
    for n in range(1, 7):
        assert nodes[f"swe{n}_author"]["role"] == f"swe{n}-author"
        assert nodes[f"swe{n}_inspector"]["role"] == f"swe{n}-inspector"
    assert "swe3_verify" in dot and "--check hal_guideline" in dot
    e = edges(dot)
    assert ("swe3_author_gate", "swe3_verify", "outcome=succeeded") in e
    assert ("swe2_inspect_gate", "swe3_regmap", "outcome=succeeded") in e and ("swe3_regmap", "swe3_ll_author", "") in e
    assert ("swe3_ll_author", "swe3_hal_author", "") in e and ("swe3_hal_author", "swe3_author", "") in e
    assert "forge_factory.inspection.regmap" in dot and nodes["swe3_hal_author"]["role"] == "swe3-author"
    assert ("swe3_inspect_gate", "swe4_scaffold", "outcome=succeeded") in e and ("swe4_scaffold", "swe4_test_author", "") in e
    assert ("swe4_test_author", "swe4_author", "") in e and "forge_factory.workflow.scaffold" in dot
    assert nodes["swe3_ll_author"] == {"role": "swe3-author", "phase": "SWE.3"}
    assert ("swe3_verify", "swe3_inspector", "outcome=succeeded") in e
    assert ("swe3_verify", "swe3_route", "") in e  # failure = unconditional fallback (fail closed)
    assert f"max_visits={MAX_VISITS}" in dot and MAX_VISITS == 1 + load_checklist("SWE.3")["policy"]["maximum_rework_cycles"]


def test_code_model_profile_applies_only_to_code_nodes():
    from forge_factory.workflow.builder import CODE_NODES

    dot, nodes = build("wo-test", code_model="qwen3-coder:30b")
    assert {k for k, v in nodes.items() if v.get("model")} == set(CODE_NODES)
    assert dot.count('model="qwen3-coder:30b"') == len(CODE_NODES)
    assert 'swe1_author [label=' in dot and 'swe3_inspector [label=' in dot  # inspectors/others keep the default
    assert build("wo-test")[0].count('model="') == 0


def test_every_node_can_reach_finalize():
    dot, _ = build("wo-test")
    e = edges(dot)
    graph = {}
    for a, b, _c in e:
        graph.setdefault(a, set()).add(b)
    nodes = set(graph) | {b for _, b, _ in e}
    for node in nodes - {"exit", "finalize"}:
        seen, todo = set(), [node]
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            todo += list(graph.get(x, ()))
        assert "finalize" in seen, node


def test_route_success_only_to_author_and_failure_fallback_to_finalize():
    dot, _ = build("wo-test")
    e = edges(dot)
    for n in range(1, 7):
        assert (f"swe{n}_route", f"swe{n}_author", "outcome=succeeded") in e
        assert (f"swe{n}_route", "finalize", "") in e


def gate(ws, phase, step, stdin="", check=""):
    cmd = [sys.executable, "-m", "forge_factory.inspection.gate", "--workspace", str(ws), "--phase", phase,
           "--step", step] + (["--check", check] if check else [])
    return subprocess.run(cmd, input=stdin.encode(), capture_output=True, env={**os.environ,
                          "FORGE_EVENTS_DIR": str(ws / ".ev")})


def test_gate_cli_author_rejects_prose_and_freezes_valid(tmp_path):
    (tmp_path / "workproducts/SWE.1").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** The RCC driver shall reset all clocks.\n")
    assert gate(tmp_path, "SWE.1", "author", "Done, looks great!").returncode >= 10
    ok = gate(tmp_path, "SWE.1", "author", json.dumps({"status": "PASS", "artifacts": [], "issues": [],
                                                      "next_action": "next"}))
    assert ok.returncode == 0 and "BL-SWE.1-001" in ok.stdout.decode()
    # Inspector claiming PASS without a recorded inspection must not pass the gate.
    fake = gate(tmp_path, "SWE.1", "inspect", json.dumps({"status": "PASS", "artifacts": [], "issues": [],
                                                         "next_action": "next"}))
    assert fake.returncode >= 10 and "REINSPECT" in fake.stdout.decode()
    assert gate(tmp_path, "SWE.1", "route").returncode == 0  # rework budget available


def test_gate_verify_node_fails_on_missing_code(tmp_path):
    r = gate(tmp_path, "SWE.3", "verify", check="hal_guideline")
    r2 = gate(tmp_path, "SWE.3", "verify", check="hal_guideline")
    assert r.returncode >= 10 and r2.returncode == r.returncode + 1  # distinct Fabro failure signatures
    assert (tmp_path / "verification/static/hal_guideline_conformance.json").is_file()


@pytest.mark.skipif(os.environ.get("FORGE_FABRO_LIVE") != "1", reason="live Fabro disabled")
def test_installed_fabro_validates_generated_workflow(tmp_path):
    dot, _ = build("wo-validate")
    (tmp_path / "workflow.fabro").write_text(dot)
    (tmp_path / "workflow.toml").write_text('_version = 1\n[workflow]\ngraph = "workflow.fabro"\n[run]\ngoal = "v"\n')
    r = subprocess.run([os.environ["FORGE_FABRO_BIN"], "validate", str(tmp_path / "workflow.toml")],
                       env={**os.environ, "HOME": os.environ["FORGE_FABRO_HOME"], "FABRO_NO_UPGRADE_CHECK": "1"},
                       capture_output=True, text=True)
    assert "Validation: OK" in r.stdout + r.stderr, r.stdout + r.stderr


def test_author_gate_uses_tool_evidence_not_agent_prose(tmp_path):
    (tmp_path / "workproducts/SWE.1").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** The RCC driver shall reset all clocks.\n")
    assert gate(tmp_path, "SWE.1", "author", "").returncode >= 10  # nothing frozen: empty reply rejected
    from forge_factory.inspection.engine import Store
    Store(tmp_path).freeze("SWE.1", "swe1-author")  # frozen via MCP during the stage
    ok = gate(tmp_path, "SWE.1", "author", "")
    assert ok.returncode == 0 and "CONTRACT_VIOLATION_RECORDED" in ok.stdout.decode()
    assert "AGENT_OUTPUT_CONTRACT_VIOLATION" in (tmp_path / ".forge-run/gates/gate-log.jsonl").read_text()
    bad = gate(tmp_path, "SWE.1", "author", '{"status":"BLOCKED","artifacts":[],"issues":["x"],"next_action":"halt"}')
    assert bad.returncode >= 10  # explicit agent BLOCKED is honoured


def test_author_prose_ending_in_contract_json_is_frozen_with_violation_recorded(tmp_path):
    (tmp_path / "workproducts/SWE.1").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** The RCC driver shall reset all clocks.\n")
    reply = 'Baseline ready, EARS PASS.\n{"status":"PASS","artifacts":[],"issues":[],"next_action":"next"}'
    ok = gate(tmp_path, "SWE.1", "author", reply)
    assert ok.returncode == 0 and "BL-SWE.1-001" in ok.stdout.decode()
    log = (tmp_path / ".forge-run/gates/gate-log.jsonl").read_text()
    assert '"FROZEN"' in log and "AGENT_OUTPUT_CONTRACT_VIOLATION" in log
    blocked = gate(tmp_path, "SWE.1", "author",
                   'Ran out of turns.\n{"status":"BLOCKED","artifacts":[],"issues":["x"],"next_action":"halt"}')
    assert blocked.returncode >= 10  # a trailing BLOCKED contract is honoured too


def test_route_counts_author_rejections_in_rework_budget(tmp_path):
    assert gate(tmp_path, "SWE.3", "author", "prose").returncode >= 10
    assert gate(tmp_path, "SWE.3", "route").returncode == 0  # 1 failed cycle: rework allowed
    assert gate(tmp_path, "SWE.3", "author", "prose").returncode >= 10
    assert gate(tmp_path, "SWE.3", "route").returncode == 1  # BLOCKED -> finalizer (not an endless rework loop)


def test_route_counts_its_own_invocations_when_no_gate_ran(tmp_path):
    # agent session crashed: Fabro skipped the author gate (no stdin) and went straight to route twice
    assert gate(tmp_path, "SWE.3", "route").returncode == 0
    assert gate(tmp_path, "SWE.3", "route").returncode == 1  # 2nd failed cycle -> BLOCKED -> finalizer
