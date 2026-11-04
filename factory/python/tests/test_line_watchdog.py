"""Reuse the existing operator-intent fence/cooldown; a line watchdog cannot invent restart authority."""
import json
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_watchdog as W
from forge_factory.afo.operations import Intent
from forge_factory.afo.durable import Refused


ACTIVE = {"ActiveState": "active", "MainPID": "12", "UnitFileState": "enabled", "Result": "success"}
FAILED = {**ACTIVE, "ActiveState": "failed", "MainPID": "0", "Result": "signal"}


@pytest.mark.parametrize("patch,expected", [
    ({}, "HEALTHY"), ({"pid": 13}, "HEARTBEAT_PID_MISMATCH"),
    ({"pid": True}, "HEARTBEAT_PID_MISMATCH"), ({"epoch": 0}, "HEARTBEAT_STALE"),
    ({"epoch": 1100}, "HEARTBEAT_STALE"), ({"epoch": "bad"}, "HEARTBEAT_STALE"),
    ({"ok": False}, "CYCLE_FAILED"), ({"mode": "UNKNOWN"}, "HEARTBEAT_MODE_INVALID"),
])
def test_health_is_bound_to_current_unit_and_fresh_completed_cycle(tmp_path, patch, expected):
    heartbeat = tmp_path / "heartbeat"
    heartbeat.write_text(json.dumps({"pid": 12, "epoch": 1000, "ok": True, "mode": "PILOT"} | patch))
    result = W.check(180, now=1030, heartbeat=heartbeat, probe=lambda: ACTIVE)
    assert result["code"] == expected
    assert result["ok"] is (expected == "HEALTHY")


def test_missing_and_malformed_heartbeat_never_means_healthy(tmp_path):
    p = tmp_path / "heartbeat"
    assert not W.check(heartbeat=p, probe=lambda: ACTIVE)["ok"]
    p.write_text("[]")
    assert W.check(heartbeat=p, probe=lambda: ACTIVE)["code"] == "HEARTBEAT_INVALID"


@pytest.fixture
def intent(tmp_path):
    root = tmp_path / "control"
    root.mkdir(mode=0o700)
    i = Intent(root / "operations.json")
    i.set("RUNNING", actor="fixture-owner", reason="approved fixture", initialize=True)
    return i


def test_recovery_keeps_existing_authority_unit_state_and_volume_barriers(intent):
    calls = []
    run = lambda argv: calls.append(argv) or SimpleNamespace(returncode=0)
    for state in (ACTIVE, FAILED | {"UnitFileState": "disabled"}, FAILED | {"UnitFileState": "masked"},
                  FAILED | {"ActiveState": "inactive", "Result": "success"}):
        result = W.recover(intent.path, probe=lambda: state, runner=run, authorize=lambda: True,
                           ready=lambda: {"ok": True}, now=100)
        assert result["action"] == "NO_APPROVED_RECOVERY"
    assert W.recover(intent.path, probe=lambda: FAILED, runner=run, authorize=lambda: False,
                     ready=lambda: {"ok": True}, now=100)["action"] == "WAITING_FOR_PREAUTHORIZED_OPERATIONAL_RECIPE"
    assert W.recover(intent.path, probe=lambda: FAILED, runner=run, authorize=lambda: True,
                     ready=lambda: {"ok": False}, now=100)["action"] == "WAITING_FOR_AUTHORITATIVE_VOLUME"
    assert not calls


def test_recovery_uses_only_line_unit_and_cooldown_survives_new_worker(intent):
    calls = []
    run = lambda argv: calls.append(argv) or SimpleNamespace(returncode=0)
    args = dict(probe=lambda: FAILED, runner=run, authorize=lambda: True, ready=lambda: {"ok": True})
    assert W.recover(intent.path, now=100, **args)["action"] == "START_REQUESTED"
    assert calls == [["systemctl", "--user", "start", W.UNIT]]
    assert W.recover(intent.path, now=101, **args)["action"] == "COOLDOWN"
    assert len(calls) == 1
    assert Intent(intent.path).read()["next_recovery_epoch"] == 700


def test_operator_stop_and_unknown_intent_prevent_recovery_and_boot(intent):
    intent.set("STOPPED", actor="fixture-owner", reason="explicit stop")
    assert not W.boot_allowed(intent.path)
    assert W.recover(intent.path)["action"] == "WAITING_FOR_AUTHENTICATED_OPERATIONS_INTENT"
    assert not W.boot_allowed(intent.path.with_name("missing"))
    with pytest.raises(Refused, match="UNAPPROVED_CONDUCTOR_RECOVERY_UNIT"):
        intent.start(2, probe=lambda: FAILED, unit="x-verse.service")


def test_stop_between_preflight_and_start_fences_the_recovery_effect(intent):
    calls = []

    def ready():
        intent.set("STOPPED", actor="fixture-owner", reason="stop won race")
        return {"ok": True}

    with pytest.raises(Refused, match="OPERATIONS_START_FENCED"):
        W.recover(intent.path, ready=ready, probe=lambda: FAILED, authorize=lambda: True,
                  runner=lambda argv: calls.append(argv), now=100)
    assert not calls


def test_default_restart_authority_still_comes_from_existing_cre_policy(intent, monkeypatch):
    from forge_factory.afo import operations

    checked = []
    monkeypatch.setattr(operations, "operational_authorized", lambda action="restart_conductor":
                        checked.append(action) or False)
    result = W.recover(intent.path, ready=lambda: {"ok": True}, probe=lambda: FAILED,
                       runner=lambda _argv: pytest.fail("CRE has not authorized restart"), now=100)
    assert result["action"] == "WAITING_FOR_PREAUTHORIZED_OPERATIONAL_RECIPE"
    assert checked == ["restart_conductor"]
