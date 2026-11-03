"""CAPA-122 (run WO-F014-CMP-SWE1-CRCL-20261102-10, cloud line, 2026-11-03): a model-call outage is an infrastructure
outcome. The structured visit waits and retries (bounded), then ends on INFRA_UNAVAILABLE:MODEL_CALLS_REFUSED; the
author/inspect gates record no attempt and the route blocks retryably - no STUCK, no rework cycle, no reservation."""
from __future__ import annotations

import contextlib
import io
import json

import pytest
from forge_factory import development_execution as D
from forge_factory.inspection import gate, outage
from forge_factory.inspection.engine import Store
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import visit as V

REFUSAL = "CALL_REFUSED:bridge_upstream_failed"


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    w = tmp_path / "ws"
    (w / ".forge-run").mkdir(parents=True)
    (w / ".forge-run/manifest.json").write_text(json.dumps({
        "work_order": "WO-T-122", "layer": "LL", "created_at": "2026-11-03T00:00:00Z", "purpose": "ASPICE_ONLY",
        "local_profile": {"id": "cloud-bridge-claude-author-claude-inspector"},
        "development_execution": D.binding(D.HIGH, "ASPICE_ONLY"), "scope": [], "target": {}, "budgets": {}}))
    return w


def _build(task):
    def build(_fi, _pr):
        return {"task": task, "role": "swe1-author", "phase": "SWE.1", "model": "m", "input_hash": "h-" + task,
                "accounting": {"estimated_prompt_tokens": 1}, "output_schema": {"type": "object"}}
    return build


def _budget(w):
    b, _f = V.open_visit(w, "SWE.1", False, list, 256, None)
    b["schema_mode"], b["schema_mode_basis"] = "json_schema", "test"
    return b


def _script(monkeypatch, answers):
    calls = []

    def call(p, **_k):
        calls.append(p["task"])
        a = answers.pop(0) if answers else REFUSAL
        if isinstance(a, dict):
            return {"doc": a, "errors": [], "usage": None, "wall_ms": 1.0, "raw_chars": 2, "finish_reason": "stop"}
        return {"doc": None, "errors": [a], "usage": None, "wall_ms": 1.0, "raw_chars": 0, "finish_reason": None}
    monkeypatch.setattr(S, "call", call)
    return calls


def _sleeps(monkeypatch):
    slept = []
    monkeypatch.setattr(V.time, "sleep", slept.append)
    return slept


@pytest.mark.parametrize("err", [REFUSAL, "CALL_REFUSED:HTTP_500", "CALL_REFUSED:HTTP_503", "CALL_REFUSED:unavailable_error",
                                 "CALL_REFUSED:PROVIDER_REQUEST_OUTCOME_UNKNOWN",
                                 "CALL_REFUSED:PROVIDER_READ_TIMEOUT_OUTCOME_UNKNOWN",
                                 "CALL_FAILED:<urlopen error [Errno 111] Connection refused>"])
def test_outage_codes_of_the_bridge_gateway_and_llama_server(err):
    assert outage.call_outage([err]) == err


@pytest.mark.parametrize("err", ["CALL_REFUSED:MISSION_REQUESTS_EXHAUSTED", "CALL_REFUSED:HTTP_400",
                                 "CALL_REFUSED:cost_cap", "CALL_REFUSED:admission_queue_full",
                                 "CALL_REFUSED:DEVELOPMENT_PHASE_REPAIR_EXHAUSTED", "NOT_JSON:x"])
def test_admission_budget_and_contract_refusals_are_not_outages(err):
    assert outage.call_outage([err]) is None


def test_wait_schedule_is_bounded_and_configurable(monkeypatch):
    assert sum(outage.wait_steps()) == outage.DEFAULT_WAIT_S
    monkeypatch.setenv("FORGE_LRTX_OUTAGE_WAIT_S", "0")
    assert outage.wait_steps() == []
    monkeypatch.setenv("FORGE_LRTX_OUTAGE_WAIT_S", "100000")
    assert sum(outage.wait_steps()) == 3600


def test_a_short_outage_is_waited_out_without_a_repair_attempt(ws, monkeypatch):
    calls = _script(monkeypatch, [REFUSAL, REFUSAL, {"ok": True}])
    slept = _sleeps(monkeypatch)
    b = _budget(ws)
    rec = V.run_task(ws, "SWE.1", "requirements:A", _build("requirements:A"), lambda _d: [], b)
    assert rec["status"] == "VALID" and len(rec["attempts"]) == 1 and rec["attempts"][0]["n"] == 0
    assert slept == [30.0, 60.0] and len(calls) == 3 and b["calls"] == 1 and not b.get("outage")


def test_a_persistent_outage_ends_the_visit_on_the_infrastructure_outcome(ws, monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_OUTAGE_WAIT_S", "90")
    b = _budget(ws)
    _script(monkeypatch, [{"ok": 1}])
    assert V.run_task(ws, "SWE.1", "requirements:B", _build("requirements:B"), lambda _d: [], b)["status"] == "VALID"
    ck = V._ckpt(ws, "SWE.1", "requirements:B")
    before = ck.read_text()
    calls = _script(monkeypatch, [])
    slept = _sleeps(monkeypatch)
    a = V.run_task(ws, "SWE.1", "requirements:A", _build("requirements:A"), lambda _d: [], b)
    rb = V.run_task(ws, "SWE.1", "requirements:B", _build("requirements:B"), lambda _d: [], b, ["SWE1-02: x"])
    assert slept == [30.0, 60.0] and calls == ["requirements:A"] * 3  # B: no call once the outage is declared
    assert a["status"] == rb["status"] == "INVALID" and outage.all_outage(a["errors"] + rb["errors"])
    assert ck.read_text() == before and rb["doc"] == {"ok": 1}  # the valid answer is kept exactly
    assert not V._ckpt(ws, "SWE.1", "requirements:A").exists()
    doc = V.reply(ws, "SWE.1", "FAILED", [f"requirements:A: {e}" for e in a["errors"]], b)
    assert outage.all_outage(doc["issues"])  # the marker survives the 120-character agent-output bound
    rec = json.loads((ws / ".forge-run/lrtx/SWE.1/visits.jsonl").read_text().splitlines()[-1])
    assert rec["infra_outcome"] == outage.CODE and rec["outage_waited_s"] == 90.0


def test_an_allowance_exhausted_by_refused_calls_is_still_the_outage(ws, monkeypatch):
    _script(monkeypatch, [REFUSAL, "CALL_REFUSED:DEVELOPMENT_PHASE_REPAIR_EXHAUSTED"])
    _sleeps(monkeypatch)
    rec = V.run_task(ws, "SWE.1", "requirements:A", _build("requirements:A"), lambda _d: [], _budget(ws))
    assert outage.all_outage(rec["errors"]) and "DEVELOPMENT_PHASE_REPAIR_EXHAUSTED" in rec["outage"]


def test_the_next_visit_answers_the_findings_the_outage_visit_could_not(ws):
    log = ws / ".forge-run/lrtx/SWE.1/visits.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps({"at": "2026-11-03T00:55:00Z", "status": "PASS", "issues": []}) + "\n"
                   + json.dumps({"at": "2026-11-03T01:00:19Z", "status": "FAILED", "infra_outcome": outage.CODE,
                                 "issues": ["requirements:A: INFRA_UNAVAILABLE:MODEL_CALLS_REFUSED (x)"]}) + "\n")
    assert V.last_finished(ws, "SWE.1") == "2026-11-03T00:55:00Z"
    _b, findings = V.open_visit(ws, "SWE.1", False, lambda: ["SWE1-02: real finding"], 10, None)
    assert findings == ["SWE1-02: real finding"]  # the outage issues are not carried as repair findings


def _outage_reply(ws, monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_OUTAGE_WAIT_S", "0")
    _script(monkeypatch, [])
    b = _budget(ws)
    rec = V.run_task(ws, "SWE.1", "requirements:A", _build("requirements:A"), lambda _d: [], b)
    return json.dumps(V.reply(ws, "SWE.1", "FAILED", [f"requirements:A: {e}" for e in rec["errors"]], b))


def _log(ws):
    return [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]


def _quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a)


def test_the_author_gate_and_route_record_an_infrastructure_outcome(ws, monkeypatch):
    for _ in range(2):
        assert _quiet(gate.step_author, Store(ws), "SWE.1", _outage_reply(ws, monkeypatch)) != 0
    assert [r["result"] for r in _log(ws)] == [outage.INFRA, outage.INFRA]
    assert gate.author_rejections(ws, "SWE.1") == 0 and gate.stuck_signature(ws, "SWE.1") is None
    assert _quiet(gate.step_route, Store(ws), "SWE.1") == 1
    g = _log(ws)[-1]["gate"]
    assert g["decision"] == "BLOCKED" and g["reason"].startswith("INFRA_UNAVAILABLE: MODEL_CALLS_REFUSED")
    assert g["infra_outcome"]["retryable"] is True and "STUCK" not in g["reason"]
    with D.phase_state(ws, "SWE.1") as st:
        assert "phase_reworks" not in st  # no development rework reservation was spent
    assert gate._count(ws, "SWE.1", "route") == 0
    assert outage.package_findings(ws)[0]["id"] == "SWE.1:INFRA_UNAVAILABLE"


def test_a_structured_inspector_outage_blocks_retryably(ws):
    reply = json.dumps({"status": "FAILED", "artifacts": [], "next_action": "rework",
                        "issues": ["SWE1-02: INFRA_UNAVAILABLE:MODEL_CALLS_REFUSED (CALL_REFUSED:HTTP_500; retried)"]})
    assert _quiet(gate.step_inspect, Store(ws), "SWE.1", reply) != 0
    assert _log(ws)[-1]["result"] == outage.INFRA
    assert _quiet(gate.step_route, Store(ws), "SWE.1") == 1 and _log(ws)[-1]["gate"]["infra_outcome"]["step"] == "inspect"


def test_a_real_failed_visit_is_still_a_rejected_attempt(ws):
    reply = json.dumps({"status": "FAILED", "artifacts": [], "next_action": "rework",
                        "issues": ["requirements:A: SWR-001 cites no RM section"]})
    _quiet(gate.step_author, Store(ws), "SWE.1", reply)
    assert _log(ws)[-1]["result"] == "REJECTED" and gate.author_rejections(ws, "SWE.1") == 1
    assert outage.pending(ws, "SWE.1") is None


def test_an_infra_row_between_two_identical_rejections_keeps_the_stuck_rule(ws, monkeypatch):
    real = json.dumps({"status": "FAILED", "artifacts": [], "next_action": "rework", "issues": ["X_CODE:1"]})
    _quiet(gate.step_author, Store(ws), "SWE.1", real)
    _quiet(gate.step_author, Store(ws), "SWE.1", _outage_reply(ws, monkeypatch))
    _quiet(gate.step_author, Store(ws), "SWE.1", real)
    assert gate.stuck_signature(ws, "SWE.1") is not None
