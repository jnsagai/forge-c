"""Feature 010 P2: structured SWE.1 for the local profile (LRTX-T011..T015) with a scripted model.

The scripted answers are the IWDG LL requirements of the Codex rc1 run, split per task. The assembled work products
must pass the UNCHANGED SWE.1 author gate; invalid answers must be repaired locally, never assembled.
"""
from __future__ import annotations

import io
import json
import sys

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1

DS = REPO_ROOT / "examples/0002-arm_55_rcc_st/inputs/DS14791-rev9-stm32n6x5-x7-datasheet.md"  # git-ignored owner input
pytestmark = pytest.mark.skipif(not DS.is_file(), reason="owner datasheet input (git-ignored) not present")
SYS = "IWDG LL driver"


def _req(key, st, page, effects=(), by="host_unit_test"):
    return {"key": key, "statement": st, "source_page": page, "verified_by": by, "effects": list(effects),
            "verification": "Host unit test calls the function on the RAM register array and passes when the register "
                            "field holds the expected value."}


def _eff(case, reg, fld, op, value=""):
    return {"case": case, "register": reg, "field": fld, "op": op, "value": value}


ANSWERS = {
    "requirements:IWDG_KR": {"requirements": [
        _req("start", f"When LL_IWDG_Enable is called, the {SYS} shall write 0x0000CCCC to IWDG_KR.KEY.", 2989,
             [_eff("START", "IWDG_KR", "KEY", "write", "0xCCCC")]),
        _req("refresh", f"When LL_IWDG_ReloadCounter is called, the {SYS} shall write 0x0000AAAA to IWDG_KR.KEY.", 2989,
             [_eff("REFRESH", "IWDG_KR", "KEY", "write", "0xAAAA")]),
        _req("unlock", f"When LL_IWDG_EnableWriteAccess is called, the {SYS} shall write 0x00005555 to IWDG_KR.KEY.",
             2989, [_eff("UNLOCK", "IWDG_KR", "KEY", "write", "0x5555")]),
        _req("lock", f"When LL_IWDG_DisableWriteAccess is called, the {SYS} shall write 0x00000000 to IWDG_KR.KEY.",
             2989, [_eff("LOCK", "IWDG_KR", "KEY", "write", "0x0")])], "not_covered": [], "open_points": []},
    "requirements:IWDG_PR": {"requirements": [
        _req("prescaler", f"When LL_IWDG_SetPrescaler is called with a value from 0U to 15U, the {SYS} shall write the "
             "value to IWDG_PR.PR.", 2990, [_eff("SET_PRESCALER", "IWDG_PR", "PR", "write", "0x5")])],
        "not_covered": [], "open_points": []},
    "requirements:IWDG_RLR": {"requirements": [
        _req("reload", f"When LL_IWDG_SetReloadCounter is called with a value from 0U to 4095U, the {SYS} shall write "
             "the value to IWDG_RLR.RL.", 2990, [_eff("SET_RELOAD", "IWDG_RLR", "RL", "write", "0xFFF")])],
        "not_covered": [], "open_points": []},
    "requirements:IWDG_SR_1": {"requirements": [
        _req("onf_set", f"When LL_IWDG_IsActive is called with IWDG_SR.ONF set, the {SYS} shall return 1U.", 2991,
             [_eff("ONF_SET", "IWDG_SR", "ONF", "no_write")])],
        "not_covered": [{"field": "IWDG_SR.EWIF", "reason": "early wake-up interrupt out of scope"},
                        {"field": "EWU", "reason": "early wake-up interrupt out of scope"}], "open_points": []},
    "requirements:IWDG_SR_2": {"requirements": [
        _req("pvu", f"When LL_IWDG_IsActiveFlag_PVU is called with IWDG_SR.PVU set, the {SYS} shall return 1U.", 2991,
             [_eff("PVU_SET", "IWDG_SR", "PVU", "no_write")]),
        _req("rvu", f"When LL_IWDG_IsActiveFlag_RVU is called with IWDG_SR.RVU set, the {SYS} shall return 1U.", 2991,
             [_eff("RVU_SET", "IWDG_SR", "RVU", "no_write")])],
        "not_covered": [{"field": "IWDG_SR.WVU", "reason": "window option out of scope"}], "open_points": []},
    "requirements:crosscutting": {"requirements": [
        _req("startup", f"While no LL function has been called after reset, the {SYS} shall not write any IWDG "
             "register.", 2989, by="target_robot_test")], "not_covered": [], "open_points": ["none observed"]},
}


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    from forge_factory import workorder
    from forge_factory.workflow.builder import binding_for, build

    w, _m = workorder.prepare(REPO_ROOT / "examples/0009a-iwdg-ll", "WO-T-IWDG-LL")
    _g, nodes = build("WO-T-IWDG-LL", layer="LL", trace=True, peripheral="iwdg")
    binding_for("WO-T-IWDG-LL", str(w), nodes).dump(w / ".forge-run/binding.json")
    return w


def _scripted(answers, calls):
    def call(p, **_k):
        calls.append(p)
        doc = answers[p["task"]]
        doc = doc(p) if callable(doc) else doc
        return {"doc": json.loads(json.dumps(doc)), "errors": S.validate(doc, p["output_schema"]),
                "usage": {"prompt_tokens": 1000, "completion_tokens": 200}, "wall_ms": 1.0, "finish_reason": "stop"}
    return call


def _gate(ws_, monkeypatch):
    from forge_factory.inspection import gate

    monkeypatch.setattr(sys, "stdin", io.StringIO((ws_ / ".forge-run/lrtx/SWE.1/reply.json").read_text()))
    return gate.main(["--workspace", str(ws_), "--phase", "SWE.1", "--step", "author"])


def test_inventory_covers_every_key_section_field(ws):
    inv = swe1.inventory(ws)
    assert inv["missing_sections"] == [] and "IWDG_KR.KEY" in inv["items"] and len(inv["items"]) == 9
    assert [g["id"] for g in swe1.groups(inv)] == ["IWDG_KR", "IWDG_PR", "IWDG_RLR", "IWDG_SR_1", "IWDG_SR_2"]
    p = swe1.group_packet(ws, swe1.groups(inv)[0], "qwen3-coder:30b")
    assert p["accounting"]["fits"] and p["accounting"]["estimated_prompt_tokens"] < 6000
    assert p["skill"]["path"] == ".fabro/skills/swe1-author/SKILL.md" and "Allowed MCP tools" not in p["_messages"][0]["content"]


def test_visit_assembles_work_products_the_unchanged_gate_freezes(ws, monkeypatch):
    calls = []
    monkeypatch.setattr(S, "call", _scripted(ANSWERS, calls))
    rep = swe1.visit(ws, "qwen3-coder:30b")
    assert rep["status"] == "PASS", rep
    md = (ws / swe1.REQS).read_text()
    assert "- **SWR-011** The IWDG LL driver shall occupy at most 4096 bytes of flash." in md
    assert "PENDING owner allocation review" in (ws / swe1.SAFETY).read_text()
    eff = json.loads((ws / swe1.EFFECTS).read_text())["effects"]
    assert {e["swr"] for e in eff} == {f"SWR-{i:03d}" for i in range(1, 10)}
    assert "SWR-010,SWR-010,software/tests/software/test_iwdg_requirements.robot" in (ws / swe1.CSV).read_text()
    assert _gate(ws, monkeypatch) == 0  # frozen by the unchanged SWE.1 author gate
    assert len(calls) == 6
    # second visit with unchanged inputs and no findings: every task reused, no model call
    calls.clear()
    assert swe1.visit(ws, "qwen3-coder:30b")["status"] == "PASS" and calls == []


def test_uncovered_field_is_repaired_locally_and_only_that_task_reruns(ws, monkeypatch):
    calls = []
    bad = json.loads(json.dumps(ANSWERS["requirements:IWDG_SR_2"]))
    bad["not_covered"] = []

    def sr2(p):
        return ANSWERS["requirements:IWDG_SR_2"] if p["findings"] else bad
    monkeypatch.setattr(S, "call", _scripted({**ANSWERS, "requirements:IWDG_SR_2": sr2}, calls))
    assert swe1.visit(ws, "qwen3-coder:30b")["status"] == "PASS"
    sr2_calls = [p for p in calls if p["task"] == "requirements:IWDG_SR_2"]
    assert len(sr2_calls) == 2 and "IWDG_SR.WVU is neither named" in sr2_calls[1]["findings"][0]
    assert sr2_calls[1]["repair_of"] is not None


def test_invalid_answer_is_never_assembled(ws, monkeypatch):
    calls = []
    broken = {"requirements": [_req("x", "The IWDG driver should maybe write IWDG_KR.KEY", 2989)],
              "not_covered": [], "open_points": []}
    monkeypatch.setattr(S, "call", _scripted({**ANSWERS, "requirements:IWDG_KR": broken}, calls))
    rep = swe1.visit(ws, "qwen3-coder:30b", max_calls=40)
    assert rep["status"] == "FAILED" and any("requirements:IWDG_KR" in i for i in rep["issues"])
    assert not (ws / swe1.REQS).exists()
    assert len([p for p in calls if p["task"] == "requirements:IWDG_KR"]) == 3  # bounded: 1 + 2 repairs
    assert _gate(ws, monkeypatch) != 0


def test_visit_call_budget_is_shared_across_tasks(ws, monkeypatch):
    calls = []
    monkeypatch.setattr(S, "call", _scripted(ANSWERS, calls))
    rep = swe1.visit(ws, "qwen3-coder:30b", max_calls=3)
    assert rep["status"] == "FAILED" and len(calls) == 3
    assert any("VISIT_CALL_BUDGET_EXHAUSTED" in i for i in rep["issues"])


def test_packet_refuses_instead_of_truncating(ws, monkeypatch):
    monkeypatch.setattr(S, "CONTEXT_TOKENS", 3000)
    with pytest.raises(S.PacketRefused, match="PACKET_TOO_LARGE"):
        swe1.group_packet(ws, swe1.groups(swe1.inventory(ws))[0], "m")


def test_schema_validator_reports_paths():
    assert S.validate({"answer": "maybe", "items": [1]}, S.PROBE_SCHEMA) == [
        "$.answer: 'maybe' not in ['yes', 'no']", "$.items: fewer than 2 items"]
    assert S._parse_json('```json\n{"a": 1}\n```')[0] == {"a": 1}


def test_structured_graph_replaces_only_the_selected_author_and_feeds_the_unchanged_gate():
    from forge_factory import acp
    from forge_factory.workflow.builder import build

    base, n0 = build("WO-X", layer="LL", trace=True, peripheral="iwdg")
    g, n1 = build("WO-X", layer="LL", trace=True, peripheral="iwdg",
                  structured={"phases": ["SWE.1"], "model": "qwen3-coder:30b"})
    assert n0 == n1  # same nodes and role bindings
    removed = sorted(set(base.splitlines()) - set(g.splitlines()))
    added = sorted(set(g.splitlines()) - set(base.splitlines()))
    assert sorted(r.split(" [")[0].strip() for r in removed) == ["swe1_author", "swe1_author -> swe1_author_gate",
                                                           "swe1_author_gate"]
    assert {a.split(" [")[0].split(" ->")[0].strip() for a in added} == {
        "swe1_author", "swe1_author_gate", "swe1_author_cont", "swe1_author_more"}
    author = next(a for a in added if a.startswith("  swe1_author [shape"))
    gate = next(a for a in added if a.startswith("  swe1_author_gate ["))
    assert "forge_factory.lrtx.runner author --phase SWE.1" in author and 'prompt="' not in author
    assert gate.count("cat .forge-run/lrtx/SWE.1/reply.json | ") == 1 and "stdin_source" not in gate
    assert "swe1_author" not in acp.native_agent_nodes(g) and "swe2_author" in acp.native_agent_nodes(g)


def test_profile_enables_structured_swe1_for_ll_only():
    from forge_factory.workorder import local_profile_structured

    local = {"id": "local-rtx-v1"}
    ll = local_profile_structured(local, {"layer": "LL"}, "m")
    assert ll["phases"] == ll["inspect_phases"] == ["SWE.1", "SWE.2"] and ll["reinspect"] is True
    hal = local_profile_structured(local, {"layer": "HAL"}, "m")
    assert hal["phases"] == [] and hal["inspect_phases"] == [] and hal["reinspect"] is True
    assert local_profile_structured(None, {"layer": "LL"}, "m") is None


def test_runner_clears_a_stale_reply_and_records_errors(ws, monkeypatch, capsys):
    from forge_factory.lrtx import runner

    stale = ws / ".forge-run/lrtx/SWE.1/reply.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text('{"status":"PASS","artifacts":[],"issues":[],"next_action":"next"}')

    def boom(*_a, **_k):
        raise RuntimeError("gateway down")
    monkeypatch.setattr(swe1, "visit", boom)
    assert runner.main(["author", "--phase", "SWE.1", "--workspace", str(ws), "--model", "m"]) == 0
    rep = json.loads(stale.read_text())
    assert rep["status"] == "FAILED" and rep["issues"][0].startswith("LRTX_RUNNER_ERROR:RuntimeError")


def test_structured_inspectors_and_direct_reinspection_rewire_only_the_profile_graph():
    from forge_factory import acp
    from forge_factory.workflow.builder import build

    base, _ = build("WO-X", layer="LL", trace=True, peripheral="iwdg")
    g, _ = build("WO-X", layer="LL", trace=True, peripheral="iwdg",
                 structured={"phases": [], "inspect_phases": ["SWE.1"], "reinspect": True, "model": "m"})
    assert "swe1_inspector" not in acp.native_agent_nodes(g) and "swe2_inspector" in acp.native_agent_nodes(g)
    assert 'swe1_inspect_gate [shape=parallelogram, label="SWE.1 inspection gate", script="cat ' \
           ".forge-run/lrtx/SWE.1/inspect-reply.json | " in g
    for n in range(1, 7):
        assert f'  swe{n}_route -> swe{n}_reinspect [condition="outcome=succeeded"]' in g
        target = "swe3_fix_author" if n == 3 else f"swe{n}_author"
        assert f"  swe{n}_reinspect -> {target}\n" in g and f'  swe{n}_route -> {target} [condition' in base
        assert f'  swe{n}_reinspect -> swe{n}_inspector [condition="outcome=succeeded"]' in g
