"""EASA-T070: the ENFORCING readiness decision is read-only and evidence-based; it never records a mode request,
never switches the mode and never states a safety approval."""
import json

from forge_factory.assurance import policy, readiness
from forge_factory.assurance.store import AssuranceStore


def test_t070_not_ready_without_authorization_pilot_and_ready_package(tmp_path, monkeypatch):
    monkeypatch.setattr("forge_factory.common.state_dir", lambda: tmp_path / "state")
    wo = tmp_path / "state/workorders/WO-A/workspace/.forge-run"
    wo.mkdir(parents=True)
    (wo / "package.json").write_text(json.dumps({"package_status": "BLOCKED"}))
    store = AssuranceStore(tmp_path / "easa.sqlite3")
    d = readiness.decide(["WO-A", "WO-MISSING"], store=store)
    assert d["decision"] == "NOT_READY" and d["readiness"]["safety_approval"] is None
    b = d["readiness"]["blocking_items"]
    assert "MODE:HUMAN_AUTHORIZATION_MISSING" in b and "MODE:VALIDATED_PILOT_MISSING" in b
    assert any(x.startswith("E2E:NO_READY_PACKAGE (1 finished") for x in b)
    assert d["pilots"]["yield"] == 0.0 and d["readiness"]["technical_gates"] == "NOT_DEMONSTRATED"
    assert store.history("mode") == []                     # read-only: no mode request recorded


def test_t070_preconditions_are_the_same_rules_request_mode_enforces():
    assert policy.mode_preconditions("OBSERVE_ONLY", "PILOT", None, None) == ["HUMAN_AUTHORIZATION_MISSING"]
    auth = {"approved_by": "agent:swe-author", "approved_at": "2026-10-17", "reference": "x"}
    assert "HUMAN_AUTHORIZATION_MISSING" in policy.mode_preconditions("PILOT", "ENFORCING", auth, None)
    assert policy.mode_preconditions("ENFORCING", "OBSERVE_ONLY", None, None) == []      # downgrade always allowed
