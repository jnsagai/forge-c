"""Feature 010 P3: structured independent inspection (LRTX-T019), direct re-inspection (T018), shared accounting
(T020) and dependency invalidation of checkpoints (T017), with scripted models and the unchanged gates."""
from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

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


def test_profile_graph_is_well_formed_dot_for_every_layer_and_peripheral():
    """lrtx5 (2026-10-21): Fabro refused the graph - the node swap replaced only the first line of an agent prompt
    that spans several lines (SWE.4/SWE.5 code examples), leaving the rest of the old statement in the graph."""
    from forge_factory import acp
    from forge_factory.workflow.builder import build

    full = {"phases": ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5"], "inspect_phases": ["SWE.1", "SWE.2", "SWE.3",
                                                                                         "SWE.4", "SWE.5"],
            "reinspect": True, "model": "m"}
    for periph in ("iwdg", None):
        g, nodes = build("WO-X", layer="LL", trace=True, peripheral=periph, structured=full)
        names = [n for _s, _e, _i, n, _a in acp.statements(g)]
        assert len(names) == len(set(names))  # every node statement exactly once
        body = g.split("\n", 1)[1].rsplit("}", 1)[0]
        for line in body.splitlines():  # outside statements, only edges and node statements remain
            t = line.strip()
            assert not t or "->" in t or re.match(r"^\w+ \[", t) or t.startswith(("graph [", "start [", "exit [")), t
        for n in ("swe4_test_author", "swe5_target_author", "swe3_ll_author"):
            assert 'prompt="' not in next(a for _s, _e, _i, nm, a in acp.statements(g) if nm == n)


@pytest.mark.skipif(not Path(os.environ.get("FORGE_FABRO_BIN", str(Path.home() / ".fabro/bin/fabro"))).is_file(),
                    reason="Fabro not installed")
@pytest.mark.parametrize("layer,periph", [("LL", "iwdg"), ("LL", None), ("HAL", "iwdg")])
def test_fabro_itself_accepts_every_profile_graph(tmp_path, layer, periph):
    import subprocess

    from forge_factory.workflow.builder import build

    six = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]
    st = {"phases": six if layer == "LL" else [], "inspect_phases": six if layer == "LL" else [],
          "reinspect": True, "model": "m"}
    g, _ = build("WO-X", layer=layer, trace=True, peripheral=periph, structured=st, isolation=layer == "HAL")
    (tmp_path / "workflow.fabro").write_text(g)
    fab = os.environ.get("FORGE_FABRO_BIN", str(Path.home() / ".fabro/bin/fabro"))
    out = subprocess.run([fab, "validate", str(tmp_path / "workflow.fabro")], capture_output=True, text=True,
                         env={**os.environ, "HOME": str(tmp_path), "FABRO_NO_UPGRADE_CHECK": "1"}, timeout=120)
    assert "Validation: OK" in out.stdout + out.stderr, (out.stdout + out.stderr)[-800:]


def test_direct_reinspection_output_differs_per_check_without_digits(ws1, capsys):  # noqa: F811
    """lrtx6 (2026-10-21): Fabro's failure-cycle breaker ended the run on the third identical reinspect output."""
    outs = []
    for _ in range(3):
        reinspect.main(["--phase", "SWE.1", "--workspace", str(ws1)])
        outs.append(re.sub(r"\d+", "<n>", capsys.readouterr().out))
    assert len(set(outs)) == 3, outs


def test_recorded_gaps_later_phase_evidence_and_present_startup_rules_are_re_judged(ws1):  # noqa: F811
    """lrtx7 (2026-10-21): the Qwen inspector failed SWE1-01/03/04/05/06 for the owner's recorded NOT_PROVIDED inputs,
    for missing tests/measurements and for 'no reset behaviour' although the document has a startup rule; the Claude
    inspector passed the same items of rc1. A real defect is not refuted."""
    gaps = ws1 / "traceability/upstream_gaps.md"
    assert "NOT_PROVIDED" in gaps.read_text()
    false = ["HSI contract is NOT_PROVIDED in the manifest, creating a gap in traceability as per upstream_gaps.md.",
             "SWR-001: Verification criteria not documented - the requirement states a pass criterion but no test file "
             "or test procedure is provided.",
             "SWR-011 states the driver shall occupy at most 4096 bytes of flash, but no evidence is provided in the "
             "checked sources that this constraint is explicitly measured or verified."]
    for f in false:
        assert review.fact_conflicts(ws1, "SWE.1", "SWE1-05", [f]), f
    text = (ws1 / swe1.REQS).read_text()
    if re.search(r"\*\*SWR-\d{3}\*\*\s+While no .*after reset", text):
        nostart = "The software requirements do not specify failure handling, reset/startup behavior or safe states."
        assert "specifies it" in review.fact_conflicts(ws1, "SWE.1", "SWE1-03", [nostart])[0]
    real = "SWR-001 requires the driver to set IWDG_SR.WVU, which is a read-only hardware status flag."
    assert review.fact_conflicts(ws1, "SWE.1", "SWE1-02", [real]) == []
    assert review.fact_conflicts(ws1, "SWE.2", "SWE2-01", false[:1]) == []  # SWE.1 rules only


def test_every_schema_valid_verdict_fits_the_check_inspection_contract():
    """lrtx7 (2026-10-21): 11+ findings for one item passed the task schema but check_inspection refused the record."""
    from forge_factory.mcp.servers import evidence as EV

    many = {"verdict": "FAIL", "findings": [f"finding number {i} about SWR-001" for i in range(11)],
            "evidence_checked": ["workproducts/SWE.1/software_requirements.md"]}
    assert any("findings" in e for e in S.validate(many, review.VERDICT_SCHEMA))
    ten = {**many, "findings": many["findings"][:10]}
    assert S.validate(ten, review.VERDICT_SCHEMA) == []
    EV.InspectIn(phase="SWE.1", baseline_id="BL-SWE.1-001",
                 verdicts={"SWE1-01": {"verdict": "FAIL", "findings": ten["findings"],
                                       "evidence_refs": ["configuration/baselines/SWE.1/BL-SWE.1-001.json",
                                                         *["x"] * 8]}})


def test_a_persisting_refuted_finding_is_recorded_with_all_findings_and_marked_contested(ws1, monkeypatch):  # noqa: F811
    """lrtx8 (2026-10-21): the inspector kept the recorded-gap finding through every repair; the visit recorded no
    inspection and lost a rework cycle. The verdict is now recorded as given (findings preserved, LRTX-FR-015) and
    the refutation is recorded beside it."""
    gap = "HSI contract is NOT_PROVIDED in the manifest, creating a gap in traceability as per upstream_gaps.md."

    def insp(p):
        if p["task"].endswith("SWE1-01"):
            return {"verdict": "FAIL", "findings": [gap], "evidence_checked": [swe1.REQS]}
        return {"verdict": "PASS", "findings": [], "evidence_checked": [swe1.REQS]}
    calls = []
    monkeypatch.setattr(S, "call", _scripted(Answers({}, insp), calls))
    rep = review.visit(ws1, "SWE.1", "m")
    assert rep["status"] == "REWORK"
    assert any(i.startswith("LRTX_INSPECTOR_FINDING_CONTESTED:SWE1-01:") for i in rep["issues"])
    ins = json.loads(sorted((ws1 / "inspection/SWE.1").glob("INS-*.json"))[-1].read_text())
    assert ins["items"]["SWE1-01"]["verdict"] == "FAIL" and ins["items"]["SWE1-01"]["findings"] == [gap]
    rec = json.loads((ws1 / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert list(rec["contested_findings"]) == ["SWE1-01"]
    assert sum(1 for p in calls if p["task"].endswith("SWE1-01")) == 3  # first answer + 2 repairs, then recorded


def test_an_item_with_other_defects_is_still_never_recorded(ws1, monkeypatch):  # noqa: F811
    gap = "HSI contract is NOT_PROVIDED in the manifest, creating a gap in traceability as per upstream_gaps.md."

    def insp(p):
        if p["task"].endswith("SWE1-01"):  # contested AND an evidence path that is not in the packet
            return {"verdict": "FAIL", "findings": [gap], "evidence_checked": ["somewhere/else.md"]}
        return {"verdict": "PASS", "findings": [], "evidence_checked": [swe1.REQS]}
    monkeypatch.setattr(S, "call", _scripted(Answers({}, insp), []))
    rep = review.visit(ws1, "SWE.1", "m")
    assert rep["status"] == "FAILED" and not list((ws1 / "inspection/SWE.1").glob("INS-*.json"))


def test_startup_refutation_only_for_findings_that_deny_startup_behaviour(ws1):  # noqa: F811
    """lrtx8 (2026-10-21): a legitimate safe-state finding that acknowledged the startup rule was refuted by a loose
    pattern. Only a finding that denies reset/startup behaviour, without naming the startup requirement, is."""
    text = (ws1 / swe1.REQS).read_text()
    m = re.search(r"\*\*(SWR-\d{3})\*\*\s+While no .*after reset", text)
    assert m, "fixture requirements carry the startup rule"
    deny = "The software requirements do not specify failure handling, reset/startup behavior or safe states."
    ack = (f"The software requirements do not specify safe states. While {m.group(1)} addresses startup behavior by "
           "ensuring no register writes occur, no requirement defines the behavior in a failure state.")
    fail = "The software requirements do not specify failure handling upon detecting a failure condition."
    assert any("specifies it" in c for c in review.fact_conflicts(ws1, "SWE.1", "SWE1-03", [deny]))
    assert review.fact_conflicts(ws1, "SWE.1", "SWE1-03", [ack]) == []
    assert review.fact_conflicts(ws1, "SWE.1", "SWE1-03", [fail]) == []


def test_gap_refutation_needs_an_upstream_input(ws1):  # noqa: F811
    """lrtx9 (2026-10-21): 'depends on an upstream budget that has not been provided' is the recorded budget gap; a
    verification criterion that is 'not provided' is not an upstream gap and must stay a finding."""
    budget = ("SWR-011: Requirement is not feasible because it depends on an upstream budget that has not been "
              "provided, violating the feasibility criterion.")
    crit = "SWR-001: the verification criterion is not provided for the unlock key requirement."
    assert any("NOT_PROVIDED" in c for c in review.fact_conflicts(ws1, "SWE.1", "SWE1-02", [budget]))
    assert not any("NOT_PROVIDED" in c for c in review.fact_conflicts(ws1, "SWE.1", "SWE1-06", [crit]))


def test_every_swe1_item_gets_the_owner_scope_note_like_the_agent_inspector(ws1):  # noqa: F811
    from forge_factory.workflow import prompts

    assert prompts.OWNER_SCOPE_NOTE in prompts.inspector_prompt("SWE.1")
    for item in ("SWE1-01", "SWE1-03", "SWE1-05", "SWE1-06"):
        assert prompts.OWNER_SCOPE_NOTE in review._notes(ws1, "SWE.1", item)
