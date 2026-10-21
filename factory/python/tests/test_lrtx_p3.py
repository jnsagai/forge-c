"""Feature 010 P3: structured independent inspection (LRTX-T019), direct re-inspection (T018), shared accounting
(T020) and dependency invalidation of checkpoints (T017), with scripted models and the unchanged gates."""
from __future__ import annotations

import io
import json
import sys

import pytest
from forge_factory.inspection.engine import Store
from forge_factory.lrtx import reinspect, review, swe1, swe2
from forge_factory.lrtx import structured as S
from test_lrtx_swe1 import ANSWERS, _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import DESIGN, IFACE, ws1  # noqa: F401 - fixture


def _items(ws_, phase="SWE.1"):
    st = Store(ws_)
    return [c["id"] for c in st.applicable(st.checklist(phase))["checks"]
            if c.get("required") and not c.get("deterministic_check")]


def _inspector(verdicts):
    def answer(p):
        item = p["task"].rsplit(":", 1)[1]
        v = verdicts.get(item, "PASS")
        return {"verdict": "PASS", "findings": [], "evidence_checked": [swe1.REQS]} if v == "PASS" else \
            {"verdict": "FAIL", "findings": [v], "evidence_checked": [swe1.REQS]}
    return answer


class Answers(dict):
    """task -> answer; inspection tasks (inspect:<hash>:<item>) answered by one callable."""
    def __init__(self, base, inspector):
        super().__init__(base)
        self.inspector = inspector

    def __getitem__(self, k):
        return self.inspector if k.startswith("inspect:") else super().__getitem__(k)


def _gate(ws_, phase, step, monkeypatch, reply):
    from forge_factory.inspection import gate

    monkeypatch.setattr(sys, "stdin", io.StringIO((ws_ / f".forge-run/lrtx/{phase}/{reply}").read_text()))
    return gate.main(["--workspace", str(ws_), "--phase", phase, "--step", step])


def test_structured_inspection_records_through_the_unchanged_operation_and_gate(ws1, monkeypatch):  # noqa: F811
    calls = []
    monkeypatch.setattr(S, "call", _scripted(Answers({}, _inspector({})), calls))
    rep = review.visit(ws1, "SWE.1", "m")
    assert rep["status"] == "PASS", rep
    assert sorted(p["task"].rsplit(":", 1)[1] for p in calls) == sorted(_items(ws1))
    assert all(p["role"] == "swe1-inspector" and not p["artifacts"] for p in calls)  # no author context
    ins = json.loads(sorted((ws1 / "inspection/SWE.1").glob("INS-*.json"))[-1].read_text())
    assert ins["inspector_role"] == "swe1-inspector" and ins["verdict"] == "PASS"
    assert ins["items"]["SWE1-07"]["verdict"] == "PASS"  # deterministic item recomputed by the engine
    assert _gate(ws1, "SWE.1", "inspect", monkeypatch, "inspect-reply.json") == 0
    calls.clear()  # same baseline again: every verdict reused from its baseline-bound checkpoint
    review.visit(ws1, "SWE.1", "m")
    assert calls == []


def test_failed_item_keeps_its_finding_and_reaches_the_author_task(ws1, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(Answers({}, _inspector({"SWE1-03": "SWR-010 states no safe state"})), []))
    assert review.visit(ws1, "SWE.1", "m")["status"] == "REWORK"
    ins = json.loads(sorted((ws1 / "inspection/SWE.1").glob("INS-*.json"))[-1].read_text())
    assert ins["verdict"] == "FAIL" and "SWR-010 states no safe state" in ins["findings"][0]["detail"]
    found = swe1.rework_findings(ws1, "")
    routed = swe1.route_findings(found, json.loads((ws1 / ".forge-run/lrtx/SWE.1/assembly.json").read_text()))
    assert list(routed) == ["requirements:crosscutting"]  # SWR-010 is the startup requirement of that task


def test_incomplete_inspection_records_nothing(ws1, monkeypatch):  # noqa: F811
    def bad(p):
        return {"verdict": "PASS", "findings": ["but something is wrong here"], "evidence_checked": [swe1.REQS]}
    monkeypatch.setattr(S, "call", _scripted(Answers({}, bad), []))
    rep = review.visit(ws1, "SWE.1", "m")
    assert rep["status"] == "FAILED" and not (ws1 / "inspection/SWE.1").exists()
    assert Store(ws1).gate("SWE.1")["decision"] != "PASS"


def test_direct_reinspection_only_for_a_valid_never_inspected_baseline(ws1, monkeypatch):  # noqa: F811
    ok, why = reinspect.decide(ws1, "SWE.1")
    assert ok, why
    monkeypatch.setattr(S, "call", _scripted(Answers({}, _inspector({"SWE1-02": "SWR-001 is not atomic"})), []))
    review.visit(ws1, "SWE.1", "m")
    assert reinspect.decide(ws1, "SWE.1") == (False, "the baseline was inspected: findings go to the author")
    (ws1 / swe1.REQS).write_text((ws1 / swe1.REQS).read_text() + "\n")
    assert reinspect.decide(ws1, "SWE.1")[1].startswith("baseline not valid")


def test_decomposition_never_resets_the_rework_budget(ws, monkeypatch):  # noqa: F811
    """Every failed structured visit is one author cycle for the unchanged route gate; the phase blocks within its
    authored budget, and one visit never exceeds the role's call budget."""
    from forge_factory.inspection import gate

    broken = {"requirements": [], "not_covered": [], "open_points": []}  # never covers the KR field
    calls = []
    monkeypatch.setattr(S, "call", _scripted({**ANSWERS, "requirements:IWDG_KR": broken}, calls))
    codes = []
    for _ in range(6):
        calls.clear()
        rep = swe1.visit(ws, "m")
        assert rep["status"] == "FAILED" and len(calls) <= 35
        _gate(ws, "SWE.1", "author", monkeypatch, "reply.json")
        codes.append(gate.main(["--workspace", str(ws), "--phase", "SWE.1", "--step", "route"]))
        if codes[-1] != 0:
            break
    assert codes[-1] != 0 and len(codes) <= 3 + gate.extra_cycles()
    log = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
    assert log[-1]["gate"]["decision"] == "BLOCKED"


def test_changed_upstream_requirements_invalidate_dependent_swe2_tasks(ws1, monkeypatch):  # noqa: F811
    calls = []
    monkeypatch.setattr(S, "call", _scripted({"interfaces": IFACE, "design": DESIGN}, calls))
    assert swe2.visit(ws1, "m")["status"] == "PASS" and len(calls) == 2
    calls.clear()
    assert swe2.visit(ws1, "m")["status"] == "PASS" and calls == []  # unchanged inputs: both tasks reused
    md = (ws1 / swe1.REQS).read_text().replace("shall write the value to IWDG_PR.PR",
                                                "shall write the requested value to IWDG_PR.PR")
    (ws1 / swe1.REQS).write_text(md)
    calls.clear()
    swe2.visit(ws1, "m")
    assert [p["task"] for p in calls][:1] == ["interfaces"]  # the SWE.1 artifact hash changed: re-run, not reuse


@pytest.mark.parametrize("phase", ["SWE.1", "SWE.2"])
def test_inspection_packets_fit_and_carry_the_full_criterion(ws1, phase):  # noqa: F811
    if phase == "SWE.2":
        pytest.skip("needs a frozen SWE.2 baseline")
    bl, srcs = review.evidence(ws1, phase)
    st = Store(ws1)
    item = next(c for c in st.applicable(st.checklist(phase))["checks"] if c["id"] == "SWE1-03")
    p = review.item_packet(ws1, phase, item, bl, srcs, "m")
    assert p["accounting"]["fits"] and " ".join(item["criterion"].split()) in p["instructions"]
    assert all(s["path"] in bl["files"] or s["path"].startswith(".forge-run/manifest.json") for s in p["sources"])
