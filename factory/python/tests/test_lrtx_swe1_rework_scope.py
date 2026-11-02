"""CAPA-108 (run WO-F014-CMP-SWE1-RCC-20261102-03): after an inspection REWORK the structured SWE.1 author re-authored
far more than the flagged items. One finding citing an SWR range and 'Open points' without a note id reached every
register task, a finding citing only a work-order budget requirement reached none, and every resumed node execution
re-sent the visit's findings to tasks that had already answered them, so the visit restarted at its first task after
each time box. A rework now re-authors only the tasks a finding names, once per visit; unnamed tasks with unchanged
inputs are reused and an unattributable finding keeps its earlier route and is recorded."""
import copy
import json

from forge_factory.common import utc_now
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1
from forge_factory.lrtx import visit as V
from test_lrtx_swe1 import ANSWERS, _scripted, pytestmark, ws  # noqa: F401 - prepared IWDG LL work order, skip marker

NOTE = "{reg} write access depends on the caller's privilege configuration."
FIX = "The caller holds the access rights the {reg} write needs before calling the driver."


def _answers():
    """Every register task records an open point (as in the incident), and a rework answer adds a stated
    precondition, so it differs from the answer the findings rejected."""
    out = copy.deepcopy(ANSWERS)
    for task, doc in out.items():
        reg = task.split(":", 1)[1]
        doc["open_points"] = [NOTE.format(reg=reg)]
    def answer(doc, reg):
        return lambda p: {**doc, "open_points": doc["open_points"] + [FIX.format(reg=reg)]} if p.get("findings") else doc
    return {task: answer(doc, task.split(":", 1)[1]) for task, doc in out.items()}


def _rework(ws_, findings):
    """The inspection's failed items as the gate log records them for the next visit."""
    with (ws_ / ".forge-run/gates/gate-log.jsonl").open("a") as f:
        f.write(json.dumps({"phase": "SWE.1", "ts": utc_now(), "result": "FAIL", "issues": findings}) + "\n")


def _swr(ws_, task):
    amap = json.loads((ws_ / ".forge-run/lrtx/SWE.1/assembly.json").read_text())
    return sorted(s for s, v in amap["swr"].items() if v["task"] == task)


def _first_visit(ws_, monkeypatch, calls):
    (ws_ / ".forge-run/gates").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(S, "call", _scripted(_answers(), calls))
    assert swe1.visit(ws_, "m")["status"] == "PASS"
    calls.clear()


def test_a_rework_reauthors_only_the_tasks_its_findings_name(ws, monkeypatch):  # noqa: F811
    calls = []
    _first_visit(ws, monkeypatch, calls)
    kr, rlr = _swr(ws, "requirements:IWDG_KR"), _swr(ws, "requirements:IWDG_RLR")
    budget = _swr(ws, "budgets")
    _rework(ws, [
        # an SWR range and an open-points mention with no note id (incident SWE1-02, first finding)
        f"SWE1-02: Major - software_requirements.md, {kr[0]}–{kr[-1]} and Open points: the writes lack a "
        "defined caller access precondition, although the open points identify privilege restrictions.",
        f"SWE1-03: Major - software_requirements.md, {rlr[0]}: failure behaviour within the supported domain is "
        "not established.",
        # cites only a deterministic work-order budget requirement (no author task)
        f"SWE1-02: Major - software_requirements.md, {budget[0]}: the measured image is not defined."])
    assert swe1.visit(ws, "m")["status"] == "PASS"
    authored = {p["task"] for p in calls}
    # the cross-cutting task is the budget finding's recorded fallback; no other register task re-authors
    assert authored == {"requirements:IWDG_KR", "requirements:IWDG_RLR", "requirements:crosscutting"}, authored
    assert all(p["findings"] for p in calls if p["task"] != "requirements:crosscutting")
    routing = json.loads((ws / ".forge-run/lrtx/SWE.1/rework-routing.json").read_text())
    assert [r["tasks"] for r in routing["findings"]] == [
        ["requirements:IWDG_KR"], ["requirements:IWDG_RLR"], ["requirements:crosscutting"]]
    assert [r["unattributed"] for r in routing["findings"]] == [False, False, True]
    assert routing["findings"][0].get("open_points_unlocated") is True and routing["unattributed"] == 1


def test_resumed_rework_reuses_answers_of_earlier_node_executions(ws, monkeypatch):  # noqa: F811
    """The time box ends each node execution after one model call; the visit must still progress to PASS."""
    calls = []
    _first_visit(ws, monkeypatch, calls)
    kr, rlr = _swr(ws, "requirements:IWDG_KR"), _swr(ws, "requirements:IWDG_RLR")
    _rework(ws, [f"SWE1-02: Major - software_requirements.md, {kr[0]}: the write lacks a caller precondition.",
                 f"SWE1-03: Major - software_requirements.md, {rlr[0]}: failure behaviour is not established."])
    clock = {"t": 0.0}
    scripted = _scripted(_answers(), calls)

    def call(p, **kw):
        clock["t"] += 100.0
        return scripted(p, **kw)

    monkeypatch.setattr(S, "call", call)
    monkeypatch.setattr(V, "time", type("Clock", (), {"monotonic": staticmethod(lambda: clock["t"])}))
    statuses = []
    for n in range(6):
        statuses.append(swe1.visit(ws, "m", resume=n > 0, time_budget_s=50)["status"])
        if statuses[-1] != "CONTINUE":
            break
    assert statuses[0] == "CONTINUE" and statuses[-1] == "PASS", statuses
    per = {t: sum(p["task"] == t for p in calls) for t in {p["task"] for p in calls}}
    # each named task answers once; the rest (including the cross-cutting task, whose inputs are unchanged) is reused
    assert per == {"requirements:IWDG_KR": 1, "requirements:IWDG_RLR": 1}, per
    record = json.loads((ws / ".forge-run/lrtx/SWE.1/packets/requirements__IWDG_KR.json").read_text())
    assert record["rework"]["execution"] == 0 and len(record["rework"]["findings_sha256"]) == 64


def test_same_findings_in_one_node_execution_or_a_new_visit_still_rerun(tmp_path, monkeypatch):
    """The reuse is bound to an earlier node execution of the same visit: a joint-check round in the same execution
    and the same findings in a later visit re-run the task as before."""
    from test_lrtx_rework_unchanged import _build

    seen = []
    answers = [{"answer": "yes", "items": [i, i + 1]} for i in range(6)]  # valid for the probe packet schema

    def call(p, **_kw):
        seen.append(p)
        return {"doc": answers[len(seen) - 1], "errors": [], "usage": None, "wall_ms": 1.0, "raw_chars": 1,
                "finish_reason": "stop", "format_note": None}

    monkeypatch.setattr(S, "call", call)
    root = tmp_path / "root"
    findings = ["SWE1-03: no failure handling specified"]

    def budget(visit, execution):
        return {"calls": 0, "max_calls": 10, "state": None, "deadline": None, "schema_mode": "json_schema",
                "visit": visit, "execution": execution}
    task = "requirements:crosscutting"
    first = V.run_task(root, "SWE.1", task, _build, lambda _d: [], budget("v1", 0), findings)
    assert first["status"] == "VALID" and first["rework"]["execution"] == 0 and len(seen) == 1
    V.run_task(root, "SWE.1", task, _build, lambda _d: [], budget("v1", 0), findings)  # same execution: re-runs
    assert len(seen) == 2
    again = V.run_task(root, "SWE.1", task, _build, lambda _d: [], budget("v1", 1), findings)  # resumed: reused
    assert again["reused"] and len(seen) == 2
    V.run_task(root, "SWE.1", task, _build, lambda _d: [], budget("v1", 1), findings + ["another"])  # new findings
    assert len(seen) == 3
    V.run_task(root, "SWE.1", task, _build, lambda _d: [], budget("v2", 1), findings + ["another"])  # new visit
    assert len(seen) == 4


def test_attribution_by_register_field_and_section_and_the_unattributed_fallback():
    tasks = {"requirements:R_ENR_1": {"register": "R_ENR", "section": "9.10.79", "fields": ["ALPHAEN", "BETAEN"]},
             "requirements:R_ENR_2": {"register": "R_ENR", "section": "9.10.79", "fields": ["GAMMAEN"]},
             "requirements:R_RSTR": {"register": "R_RSTR", "section": "9.10.64", "fields": ["ALPHARST"]}}
    amap = {"swr": {"SWR-001": {"task": "requirements:R_ENR_1", "key": "a"},
                    "SWR-002": {"task": "budgets", "key": "flash"}}, "case": {},
            "open_points": {"OP-00000000000000aa": {"task": "requirements:R_RSTR", "register": "R_RSTR",
                                                    "text": "The reset input names no release order."}}}
    cc = "requirements:crosscutting"
    routed, report = V.attribute_findings([
        "gaps.md, RM-9.10.79: no coverage gap is recorded for GAMMAEN.",  # section narrowed by the field it names
        "R_ENR.BETAEN has no requirement.",  # qualified field
        "R_ENR is incomplete.",  # register alone: all of its split tasks
        "SWR-002: the flash limit has no measured image.",  # budget row only: cross-cutting, recorded
        "The Open points section contradicts the declared scope.",  # earlier fan-out: every note origin
        "The baseline is not internally consistent."], amap, cc, tasks)
    assert [r["tasks"] for r in report] == [
        ["requirements:R_ENR_2"], ["requirements:R_ENR_1"], ["requirements:R_ENR_1", "requirements:R_ENR_2"],
        [cc], ["requirements:R_RSTR"], [cc]]
    assert [r["unattributed"] for r in report] == [False, False, False, True, True, True]
    assert [r.get("fallback") for r in report][3:] == ["default", "open_point_origins", "default"]
    assert sum(len(v) for v in routed.values()) == 7  # every finding routed at least once, none dropped
