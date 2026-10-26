"""DA-T054 / DA-FR-054: the diagnosis-repair rung. Under AFO a phase whose ladder is exhausted BLOCKs first so AFO
recovery diagnoses and repairs it; only when recovery finds no further strategy (or its budget is spent) does AFO launch
one final attempt marked recovery-exhausted, in which the route gate may register the gap and continue. A plain local
run has no recovery path and says so in the gap record."""
import json

from forge_factory.afo import recovery
from forge_factory.inspection import gate as G
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_advisory import _exhaust, advisory  # noqa: F401
from test_rework_progress_extension import _route, _ws


def _ws_with(tmp_path, **manifest):
    ws = tmp_path / "attempt-ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", **manifest}))
    return ws


def _closing(monkeypatch, order, ws):  # noqa: F811
    s, o, b, _, eff = order
    monkeypatch.setattr(recovery, "rule_plan", lambda *a, **k: None)  # no rule and no planner left
    d = recovery.decide(s, o, b, ws=ws, eff=eff, auth_models=None)
    assert d["plan"]["strategy"] == "CLOSE_BLOCKED" and d["status"] == "VALIDATED"
    return d


def test_exhausted_recovery_launches_one_final_attempt_marked_for_advisory(order, tmp_path, monkeypatch):  # noqa: F811
    s, o, b, epoch, eff = order
    monkeypatch.setattr(G, "advisory_enabled", lambda ws: True)
    ws = _ws_with(tmp_path)
    d = _closing(monkeypatch, order, ws)
    assert recovery.advisory_final(d, b, ws)
    r = recovery.execute_advisory(s, s.order(o["order_id"]), d, epoch=epoch, eff=eff, previous_wo="WO-AFO-x-a1",
                                  bundle=b, ws=ws)
    assert r["action"] == "advisory_attempt" and s.order(o["order_id"])["state"] == "WAITING_RECOVERY"
    cmd = [c for c in s.commands("PENDING") if c["attempt_id"] == r["attempt_id"]][0]
    payload = json.loads(cmd["payload"])
    assert payload["resume_from"] == "WO-AFO-x-a1" and payload["resume_upto"] == "SWE.3"
    assert payload["recovery_exhausted"] == {"SWE.3": {"plan_id": d["plan"]["plan_id"],
                                                       "rationale_code": "NO_MATERIALLY_DIFFERENT_STRATEGY"}}


def test_a_phase_already_marked_or_another_class_or_no_advisory_profile_closes_as_before(order, tmp_path,  # noqa: F811
                                                                                          monkeypatch):
    s, o, b, epoch, eff = order
    monkeypatch.setattr(G, "advisory_enabled", lambda ws: True)
    marked = _ws_with(tmp_path, afo={"attempt_id": "a2", "recovery_exhausted": {"SWE.3": {"plan_id": "p"}}})
    d = _closing(monkeypatch, order, marked)
    assert not recovery.advisory_final(d, b, marked)  # the final attempt is never repeated
    assert not recovery.advisory_final(d, {**b, "failure_class": "SPECIFICATION_GAP"}, _ws_with(tmp_path / "x"))
    monkeypatch.setattr(G, "advisory_enabled", lambda ws: False)
    assert not recovery.advisory_final(d, b, _ws_with(tmp_path / "y"))
    assert recovery.execute(s, s.order(o["order_id"]), d, epoch=epoch, eff=eff, previous_wo="x")["action"] == "blocked"


def _afo(ws, **afo):
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    (ws / ".forge-run/manifest.json").write_text(json.dumps({**m, "afo": {"attempt_id": "afo-o-a1", **afo}}))


def test_under_afo_the_route_blocks_until_recovery_is_exhausted_for_the_phase(tmp_path, advisory):  # noqa: F811
    ws = _ws(tmp_path)
    _afo(ws)
    _exhaust(ws)
    rc, g = _route(ws)
    assert rc == 1 and g["decision"] == "BLOCKED" and not (ws / ".forge-run/advisory").exists()  # AFO diagnoses first
    ws2 = _ws(tmp_path / "final")
    _afo(ws2, recovery_exhausted={"SWE.4": {"plan_id": "rp-1", "rationale_code": "NO_MATERIALLY_DIFFERENT_STRATEGY"}})
    _exhaust(ws2)
    rc, g = _route(ws2)
    assert g["decision"] == "ADVISORY_CONTINUE"
    rec = [json.loads(x) for x in (ws2 / g["advisory_ref"]).read_text().splitlines()][-1]
    rung = next(r for r in rec["attempts"]["ladder"] if r["rung"] == "diagnosis_repair")
    assert rung == {"rung": "diagnosis_repair", "status": "EXHAUSTED", "plan_id": "rp-1",
                    "rationale_code": "NO_MATERIALLY_DIFFERENT_STRATEGY"}
