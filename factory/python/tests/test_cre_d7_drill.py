"""CRE-T048 — owner-authorized live Fabro crash -> recovery drill: the recorded evidence is complete and consistent
with the durable stores (the drill itself is run once by `python -m forge_factory.reliability.drill`, not by pytest).
"""
import json
import sqlite3

import pytest
from forge_factory.common import REPO_ROOT, state_dir
from forge_factory.reliability.store import CREStore

RECORDS = sorted((REPO_ROOT / "evidence/cre/live").glob("fabro-crash-drill-*.json"))


@pytest.fixture(scope="module")
def rec():
    if not RECORDS:
        pytest.skip("no live drill record")
    return json.loads(RECORDS[-1].read_text())


def test_drill_passed_with_every_step_in_order(rec):
    assert rec["schema"] == "forge-c/cre-live-drill/1.0" and rec["result"] == "PASS"
    assert [s["step"] for s in rec["steps"]] == ["crash", "detected", "recovery_action", "fabro_healthy",
                                                  "incident_resolved"]
    pre = rec["preconditions"]
    assert pre["fabro_up"] and pre["active_runs"] == 0 and pre["dispatch_suspended"]
    assert rec["steps"][0]["signal"] == "SIGKILL"
    assert 0 < rec["detection_latency_s"] <= rec["time_to_recover_s"]


def test_recovery_was_model_free_and_invariants_held(rec):
    assert rec["supervisor_after"]["model_calls"] == 0 and rec["supervisor_after"]["model_tokens"] == 0
    assert rec["supervisor_after"]["status"] == "HEALTHY"
    assert rec["dispatch_decision"]["executed"] is False
    inv = rec["invariants"]
    assert inv["protected_inputs_unchanged"] and inv["archives_unchanged"]
    assert inv["fabro_runs_after"] == inv["fabro_runs_before"] > 0  # run history survived the crash
    assert rec["cre_recovery_scope"]["state"] == "RECOVERED"
    assert rec["steps"][2]["journal_status"] == "DONE"


def test_record_matches_the_durable_incident_and_audit_stores(rec):
    db = state_dir() / "supervisor/incidents.sqlite3"
    if not db.is_file():
        pytest.skip("live state not present")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = c.execute("SELECT component, state FROM incidents WHERE incident_id=?", (rec["incident"],)).fetchone()
    finally:
        c.close()
    assert row == ("fabro", "RESOLVED")
    with CREStore().conn() as c2:
        row = c2.execute("SELECT record FROM cre_events WHERE event_id=?", (rec["authorization_event"],)).fetchone()
    assert row is not None
    ev = json.loads(row[0])
    assert ev["source_type"] == "HUMAN_REVIEW" and ev["payload"]["decision"] == "AUTHORIZED"
