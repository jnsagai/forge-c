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


def test_time_box_continues_the_same_visit_with_its_shared_budget(ws, monkeypatch):  # noqa: F811
    """Fabro ends a command node silent for 1800 s: a visit stops before a model call past its time box and the next
    node execution resumes the SAME visit (call count and findings kept); finished tasks are not repeated."""
    from forge_factory.lrtx import runner

    calls = []
    monkeypatch.setattr(S, "call", _scripted(ANSWERS, calls))
    clock = {"t": 0.0}
    monkeypatch.setattr("forge_factory.lrtx.visit.time.monotonic", lambda: clock["t"])

    def tick(p):  # every model call takes 500 s of the 1200 s box
        clock["t"] += 500
        return ANSWERS[p["task"]]
    monkeypatch.setattr(S, "call", _scripted({k: tick for k in ANSWERS}, calls))
    rep = swe1.visit(ws, "m", time_budget_s=1200)
    assert rep["status"] == "CONTINUE" and len(calls) == 3
    assert runner.main(["continue-check", "--phase", "SWE.1", "--workspace", str(ws)]) == 0
    st = json.loads((ws / ".forge-run/lrtx/SWE.1/visit-state.json").read_text())
    assert st["open"] and st["calls"] == 3
    rep = swe1.visit(ws, "m", resume=True, time_budget_s=1200)
    assert rep["status"] == "PASS" and len(calls) == 6  # the 3 remaining tasks, each called exactly once
    st = json.loads((ws / ".forge-run/lrtx/SWE.1/visit-state.json").read_text())
    assert not st["open"] and st["calls"] == 6 and st["continuations"] == 1
    assert runner.main(["continue-check", "--phase", "SWE.1", "--workspace", str(ws)]) == 1
    # a new visit after the finished one starts a fresh budget; the time-box records are not "finished visits"
    assert swe1.visit(ws, "m")["status"] == "PASS"
    assert json.loads((ws / ".forge-run/lrtx/SWE.1/visit-state.json").read_text())["calls"] == 0


def test_continuation_nodes_have_their_own_visit_limit():
    from forge_factory.workflow.builder import MAX_VISITS, build

    g, _ = build("WO-X", layer="LL", trace=True, peripheral="iwdg",
                 structured={"phases": ["SWE.1"], "inspect_phases": ["SWE.1"], "model": "m", "visit_time_s": 900})
    assert "  swe1_author -> swe1_author_cont\n" in g and "  swe1_author -> swe1_author_gate\n" not in g
    assert '  swe1_author_cont -> swe1_author_more [condition="outcome=succeeded"]' in g
    assert "  swe1_inspector_more -> swe1_inspector_cont" in g and "--time-budget 900 --resume" in g
    assert f'swe1_author [shape=parallelogram, label="SWE.1 structured author (local profile)", max_visits={MAX_VISITS},' \
        in g


def test_failed_visits_show_their_progress_to_the_route_gate_only_for_profile_runs(ws, monkeypatch):  # noqa: F811
    """lrtx3 (2026-10-21): two failed visits looked identical to the STUCK rule (the same presence rejection) although
    their validated task issues differed. Profile runs add the runner's task issues to the rejection record."""
    from forge_factory.inspection import gate

    def rejected_issues():
        log = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
        return [d for d in log if d.get("step") == "author"][-1]["issues"]
    swe1.reply(ws, "FAILED", ["requirements:IWDG_PR: [x] acts on IWDG_KR.KEY"])
    monkeypatch.setattr(sys, "stdin", io.StringIO((ws / ".forge-run/lrtx/SWE.1/reply.json").read_text()))
    gate.main(["--workspace", str(ws), "--phase", "SWE.1", "--step", "author"])
    assert not any(i.startswith("LRTX_TASK_INVALID") for i in rejected_issues())  # no profile in this manifest
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    (ws / ".forge-run/manifest.json").write_text(json.dumps({**man, "local_profile": {"id": "local-rtx-v1"}}))
    for text in ("requirements:IWDG_PR: [x] acts on IWDG_KR.KEY", "requirements:IWDG_PR: [y] EARS_NO_SHALL"):
        swe1.reply(ws, "FAILED", [text])
        monkeypatch.setattr(sys, "stdin", io.StringIO((ws / ".forge-run/lrtx/SWE.1/reply.json").read_text()))
        gate.main(["--workspace", str(ws), "--phase", "SWE.1", "--step", "author"])
        assert f"LRTX_TASK_INVALID:{text}" in rejected_issues()
    assert gate.stuck_signature(ws, "SWE.1") is None  # different task issues: progress, not STUCK
    monkeypatch.setattr(sys, "stdin", io.StringIO((ws / ".forge-run/lrtx/SWE.1/reply.json").read_text()))
    gate.main(["--workspace", str(ws), "--phase", "SWE.1", "--step", "author"])
    assert gate.stuck_signature(ws, "SWE.1") is not None  # identical twice: STUCK as before


def test_invalid_tasks_get_further_repair_rounds_within_the_visit(ws, monkeypatch):  # noqa: F811
    calls = []
    good = ANSWERS["requirements:IWDG_SR_2"]

    def sr2(p):  # needs 5 answers: more than one task's repairs, fewer than the visit budget
        n = len([c for c in calls if c["task"] == "requirements:IWDG_SR_2"])
        if n >= 5:
            return good
        return {**good, "not_covered": [], "requirements": good["requirements"][: 1 + n % 2]}
    monkeypatch.setattr(S, "call", _scripted({**ANSWERS, "requirements:IWDG_SR_2": sr2}, calls))
    rep = swe1.visit(ws, "m")
    assert rep["status"] == "PASS", rep


def test_scope_hints_mark_fields_the_scope_excludes(ws):  # noqa: F811
    inv = swe1.inventory(ws)
    hints = {f: h for g in swe1.groups(inv) for f, h in swe1.scope_hints(ws, g).items()}
    assert "out-of-scope term(s) window" in hints["WVU"] and "interrupt" in hints["EWU"]
    assert hints["PVU"] == "named in the work-order scope"
    assert swe1.out_of_scope_named(ws) >= {"IWDG_WINR", "IWDG_EWCR", "IWDG_ICR"}


def test_inspector_findings_refuted_by_evidence_are_re_judged(ws1, monkeypatch):  # noqa: F811
    """lrtx4 (2026-10-21): the Qwen inspector failed SWE1-01..06 on the owner's PENDING allocation decision and on
    verification criteria that the document has. Such findings go back to the inspector; others are kept."""
    pending = "Software safety requirements are not allocated yet; the safety allocation is PENDING owner review."
    nover = "SWR-011 has no verification criterion and is not measurable."
    real = "SWR-001 conflates starting the watchdog with refreshing it (0xAAAA is the refresh key)."
    found = review.fact_conflicts(ws1, "SWE.1", "SWE1-02", [pending, nover, real])
    assert len(found) == 2 and "PENDING allocation" in found[0] and "SWR-011 lacks verification" in found[1]
    answers = iter([{"verdict": "FAIL", "findings": [pending], "evidence_checked": [swe1.REQS]},
                    {"verdict": "FAIL", "findings": [real], "evidence_checked": [swe1.REQS]}])

    def insp(p):
        return next(answers) if p["task"].endswith("SWE1-02") else {"verdict": "PASS", "findings": [],
                                                                    "evidence_checked": [swe1.REQS]}
    monkeypatch.setattr(S, "call", _scripted(Answers({}, insp), []))
    assert review.visit(ws1, "SWE.1", "m")["status"] == "REWORK"
    ins = json.loads(sorted((ws1 / "inspection/SWE.1").glob("INS-*.json"))[-1].read_text())
    assert ins["items"]["SWE1-02"]["findings"] == [real]  # the real defect is kept, the refuted one re-judged away


def test_source_labels_around_provided_paths_are_accepted():
    """lrtx4: 'source safety/...' and 'source/traceability/...' were rejected as unknown sources three times per item;
    the inspection recorded nothing and the phase blocked."""
    paths = {"safety/software_safety_requirements.md", ".forge-run/manifest.json#scope-target-budgets"}
    doc = {"verdict": "PASS", "findings": [], "evidence_checked": [
        "source safety/software_safety_requirements.md", "source/safety/software_safety_requirements.md",
        "SOURCE .forge-run/manifest.json#scope-target-budgets", "`safety/software_safety_requirements.md`"]}
    assert review.validate_verdict(doc, paths) == []
    assert review.validate_verdict({**doc, "evidence_checked": ["source/other.md"]}, paths) == [
        "evidence_checked names source/other.md, which is not a provided source"]
