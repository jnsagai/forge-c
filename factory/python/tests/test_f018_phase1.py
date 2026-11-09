"""Feature 018 phase 1: each SWE.1 requirement inspected and reworked on its own (owner 2026-11-09).

"one in which the inspection and rework cycle will be done requirement per requirement without modifying others".
Scripted models only; the IWDG LL set of test_lrtx_swe1 is the assembled input.
"""
# ruff: noqa: F811 - pytest fixtures imported from test_lrtx_swe1
from __future__ import annotations

import copy
import json
import re

import pytest
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1
from forge_factory.lrtx import swe1_quality as Q
from test_lrtx_swe1 import ANSWERS, SYS, _scripted, pytestmark, ws  # noqa: F401

MODEL = "qwen3-coder:30b"
GOOD_PR = (f"When LL_IWDG_SetPrescaler is called with a value, the {SYS} shall write the low 4 bits of the value to "
           "IWDG_PR.PR.")


@pytest.fixture()
def assembled(ws, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(ANSWERS, []))
    assert swe1.visit(ws, MODEL)["status"] == "PASS"
    return ws


def _finding(qid="IQ-05", sev="CORRECTABLE", unc=False):
    return {"quality_id": qid, "severity": sev, "evidence": "'..., so that a value above 15U is confined to the field'",
            "required_action": "state one obligation: write the low 4 bits", "input_uncertainty": unc}


def _model(ws, calls, verdict_for=None, rework_for=None):  # noqa: F811
    """Scripted inspector (iq:*) and author (iqfix:*) answers by requirement key (the current requirement is read from
    the workspace, as the packet's CURRENT ARTIFACT carries it)."""
    def call(p, **_k):
        calls.append(p)
        task = p["task"]
        key = task.rsplit(":", 1)[1]
        req = next(r["obj"] for r in Q.requirements(ws) if r["key"] == key)
        if task.startswith("iq:"):
            swr = p["output_schema"]["properties"]["requirement_id"]["enum"][0]
            doc = {"requirement_id": swr, "findings": (verdict_for or {}).get(key, lambda r: [])(req)}
        else:
            doc = {"requirement": rework_for[key](req)}
        return {"doc": copy.deepcopy(doc), "errors": S.validate(doc, p["output_schema"]),
                "usage": {"prompt_tokens": 500, "completion_tokens": 50}, "wall_ms": 1.0, "finish_reason": "stop"}
    return call


def _md_lines(ws):  # noqa: F811
    return (ws / swe1.REQS).read_text().splitlines()


def test_every_requirement_gets_its_own_verdict_and_a_flagged_one_is_reworked_alone(assembled, monkeypatch):
    ws = assembled
    calls = []
    fixed = {"prescaler": lambda r: {**r, "statement": GOOD_PR}}
    flag = {"prescaler": lambda r: [] if r["statement"] == GOOD_PR else [_finding()]}
    monkeypatch.setattr(S, "call", _model(ws, calls, flag, fixed))
    refs = Q.requirements(ws)
    assert len(refs) == len({(r["task"], r["key"]) for r in refs}) and any(r["generated"] for r in refs)
    assert Q.iq_inspect(ws, MODEL)["status"] == "PASS"
    judged = [p for p in calls if p["task"].startswith("iq:")]
    assert len(judged) == len(refs)  # one call per requirement
    assert all(p["role"] == "swe1-inspector" for p in judged)
    assert all([a["path"] for a in p["artifacts"]] == ["lrtx:requirement", "lrtx:task_requirements"] for p in judged)
    assert Q.iq_check(ws) == 0  # the prescaler requirement needs rework
    before = _md_lines(ws)
    calls.clear()
    rep = Q.iq_rework(ws, MODEL)
    assert rep["status"] == "PASS" and "PHASE1_REWORKED:1" in rep["issues"]
    assert [p["task"] for p in calls] == ["iqfix:requirements:IWDG_PR:prescaler"] and calls[0]["role"] == "swe1-author"
    after = _md_lines(ws)
    diff = [(a, b) for a, b in zip(before, after, strict=True) if a != b]
    assert len(diff) == 1 and GOOD_PR in diff[0][1]  # only that requirement's statement line changed
    ck = json.loads((ws / ".forge-run/lrtx/SWE.1/packets/requirements__IWDG_PR.json").read_text())
    assert ck["status"] == "VALID" and ck["phase1_rework"][0]["key"] == "prescaler"
    calls.clear()
    assert Q.iq_inspect(ws, MODEL)["status"] == "PASS"
    assert [p["task"] for p in calls] == ["iq:requirements:IWDG_PR:prescaler"]  # only the changed one re-judged
    assert Q.iq_check(ws) == 1
    s = Q.summary(ws)
    assert s["passed"] == s["requirements"] and s["carried"] == 0
    text = (ws / ".forge-run/lrtx" / Q.REPORT).read_text()
    assert "## Phase 1 - each requirement on its own" in text and f"Requirements {s['requirements']}: passed" in text
    calls.clear()
    assert Q.iq_inspect(ws, MODEL, resume=True)["status"] == "PASS" and calls == []  # nothing repeated


def test_rounds_are_bounded_and_open_findings_are_carried_to_the_set_phase(assembled, monkeypatch):
    ws = assembled
    calls = []
    n = {"i": 0}

    def drift(r):  # a different, still flagged answer every round
        n["i"] += 1
        return {**r, "statement": GOOD_PR.replace("low 4 bits", f"low 4 bits (variant {n['i']})")}
    monkeypatch.setattr(S, "call", _model(ws, calls, {"prescaler": lambda r: [_finding()]}, {"prescaler": drift}))
    for _ in range(10):
        Q.iq_inspect(ws, MODEL)
        if Q.iq_check(ws) != 0:
            break
        Q.iq_rework(ws, MODEL)
    assert Q.iq_check(ws) == 1
    s = Q.summary(ws)
    row = next(r for r in s["rows"] if r["key"] == "prescaler")
    assert row["state"] == "CARRIED" and row["reworks"] == Q.quality_checklist()["phase1"]["rounds"]
    assert [f["quality_id"] for f in s["carried_findings"]] == ["IQ-05"]


def test_no_change_invalid_answer_and_generated_requirements_are_carried(assembled, monkeypatch):
    ws = assembled
    calls = []
    flags = {"prescaler": lambda r: [_finding()], "reload": lambda r: [_finding("IQ-03")],
             "budget_flash": lambda r: [_finding("IQ-06", "BLOCKING")]}
    rework = {"prescaler": lambda r: r, "reload": lambda r: {**r, "key": "renamed_key"}}
    monkeypatch.setattr(S, "call", _model(ws, calls, flags, rework))
    Q.iq_inspect(ws, MODEL)
    before = _md_lines(ws)
    Q.iq_rework(ws, MODEL)
    assert _md_lines(ws) == before  # nothing written
    rows = {r["key"]: r for r in Q.summary(ws)["rows"]}
    assert rows["prescaler"]["stopped"] == "NO_CHANGE" and rows["reload"]["stopped"] == "REWORK_INVALID"
    assert rows["budget_flash"]["state"] == "CARRIED"  # factory-generated: never sent to the author
    assert not any(p["task"].startswith("iqfix:budgets") for p in calls)
    assert Q.iq_check(ws) == 1


def test_input_uncertainty_and_editorial_findings_are_not_reworked(assembled, monkeypatch):
    ws = assembled
    calls = []
    flags = {"prescaler": lambda r: [_finding(unc=True)], "reload": lambda r: [_finding("IQ-11", "EDITORIAL")]}
    monkeypatch.setattr(S, "call", _model(ws, calls, flags, {}))
    Q.iq_inspect(ws, MODEL)
    assert Q.iq_check(ws) == 1 and Q.pending_rework(ws) == []


def test_replace_requirement_refuses_a_key_change_and_keeps_the_set(assembled):
    ws = assembled
    before = _md_lines(ws)
    obj = next(r for r in ANSWERS["requirements:IWDG_PR"]["requirements"] if r["key"] == "prescaler")
    with pytest.raises(ValueError, match="PHASE1_SPLICE_INVALID"):
        swe1.replace_requirement(ws, "requirements:IWDG_PR", "prescaler", {**obj, "key": "other"})
    two = {**obj, "statement": GOOD_PR[:-1] + f" and the {SYS} shall write IWDG_KR.KEY."}
    with pytest.raises(ValueError, match="PHASE1_SPLICE_INVALID"):  # the task's own validator (EARS, one shall)
        swe1.replace_requirement(ws, "requirements:IWDG_PR", "prescaler", two)
    assert _md_lines(ws) == before


def test_phase1_is_skipped_when_the_author_did_not_pass(assembled, monkeypatch):
    ws = assembled
    swe1.reply(ws, "FAILED", ["x"])
    calls = []
    monkeypatch.setattr(S, "call", _model(ws, calls))
    assert "PHASE1_SKIPPED" in Q.iq_inspect(ws, MODEL)["issues"][0] and calls == []
    assert Q.iq_check(ws) == 1


def test_runner_steps_and_check_exit_codes(assembled, monkeypatch, capsys):
    from forge_factory.lrtx import runner

    ws = assembled
    calls = []
    monkeypatch.setattr(S, "call", _model(ws, calls, {"prescaler": lambda r: [_finding()]},
                                           {"prescaler": lambda r: {**r, "statement": GOOD_PR}}))
    assert runner.main(["iq-inspect", "--phase", "SWE.1", "--workspace", str(ws), "--model", MODEL]) == 0
    assert json.loads((ws / ".forge-run/lrtx/SWE.1/iq-inspect-reply.json").read_text())["status"] == "PASS"
    assert runner.main(["iq-check", "--phase", "SWE.1", "--workspace", str(ws)]) == 0
    assert runner.main(["continue-check", "--phase", "SWE.1", "--workspace", str(ws), "--of", "iq-inspect"]) == 1
    assert runner.main(["iq-rework", "--phase", "SWE.1", "--workspace", str(ws), "--model", MODEL]) == 0
    out = capsys.readouterr().out
    assert "phase one check" in out and not re.search(r"phase one check \S*\d", out)  # digit-free (cycle breaker)


def test_graph_inserts_phase1_between_author_and_freeze_gate_only_when_enabled(monkeypatch, tmp_path):
    from forge_factory.workflow.builder import build

    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path))
    st = {"phases": ["SWE.1"], "inspect_phases": ["SWE.1"], "model": "m", "author_model": "author-m",
          "inspector_model": "insp-m", "visit_time_s": 240}
    off, _ = build("WO-X", layer="LL", trace=True, peripheral="iwdg", structured=st)
    on, _ = build("WO-X", layer="LL", trace=True, peripheral="iwdg", structured={**st, "two_phase_inspection": True})
    assert "swe1_iq_inspect" not in off and "  swe1_author_cont -> swe1_author_gate\n" in off
    for edge in ("swe1_author_cont -> swe1_iq_inspect_serve", "swe1_iq_inspect -> swe1_iq_inspect_cont",
                 "swe1_iq_inspect_cont -> swe1_iq_check", 'swe1_iq_check -> swe1_iq_rework_serve [condition="outcome=succeeded"]',
                 "swe1_iq_check -> swe1_author_gate", "swe1_iq_rework -> swe1_iq_rework_cont",
                 "swe1_iq_rework_cont -> swe1_iq_inspect_serve"):
        assert f"  {edge}" in on, edge
    serve = {m.group(1): m.group(2) for m in re.finditer(r'  (\w+)_serve \[shape=parallelogram, label="Serve (\S+) for',
                                                          on)}
    assert serve["swe1_iq_inspect"] == "insp-m" and serve["swe1_iq_rework"] == "author-m"
    assert serve["swe1_author"] == "author-m" and serve["swe1_inspector"] == "insp-m"
    assert "swe1_iq_check_serve" not in on  # the check calls no model


def test_profile_switch_is_pinned_for_the_live_trial_profile():
    assert Q.enabled({"id": "local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104"})
    assert Q.enabled({"id": "other", "structured": {"two_phase_inspection": True}})
    assert not Q.enabled({"id": "other", "structured": {}}) and not Q.enabled(None)
