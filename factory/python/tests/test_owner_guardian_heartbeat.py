"""Actual private nonce service and first-cycle guard; no model/product authority."""
# ruff: noqa: F811
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import owner_launch_guard as G
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused
from forge_factory.afo.mission_ledger import MissionLedger
from test_owner_supervised_development import supervised  # noqa: F401


def record_and_heartbeat(supervised):
    ref = supervised["ref"]
    return json.loads(Path(ref["path"]).read_bytes()), Path(ref["path"]).with_suffix(".heartbeat.json")


def test_actual_first_nonce_publishes_guard_readable_liveness_without_work(supervised):
    record, heartbeat = record_and_heartbeat(supervised)
    before = MissionLedger(supervised["store"]).snapshot(D.MISSION)
    assert not heartbeat.exists()
    D._attest(record, record["guardian_socket"])
    G.heartbeat(heartbeat, os.getpid(), D.MODE, "at", "PRIVATE_GUARD", time.time())
    value = json.loads(heartbeat.read_bytes())
    assert value["record_sha256"] == supervised["ref"]["sha256"]
    assert value["cycle_state"] == "NOT_STARTED" and value["last_completed_cycle"] == -1
    assert value["last_cycle_completed_at"] is None
    assert heartbeat.stat().st_mode & 0o777 == 0o600
    assert MissionLedger(supervised["store"]).snapshot(D.MISSION) == before


def test_late_guard_attestation_refreshes_liveness_without_inventing_cycle_progress(supervised, monkeypatch):
    record, heartbeat = record_and_heartbeat(supervised)
    D._attest(record, record["guardian_socket"])
    D._publish_heartbeat(record, cycle=2, completed=True)
    D._publish_heartbeat(record, cycle=3)
    before = json.loads(heartbeat.read_bytes())
    # Isolate this module's clock facade: never alter global time.sleep or the
    # interpreter/SQLite/socket clocks. A real nonce request drives the refresh.
    real_clock = D.time
    facade = SimpleNamespace(time=lambda: real_clock.time() + 181,
                             monotonic=lambda: real_clock.monotonic() + 16)
    monkeypatch.setattr(D, "time", facade)
    D._attest(record, record["guardian_socket"])
    after = json.loads(heartbeat.read_bytes())
    G.heartbeat(heartbeat, os.getpid(), D.MODE, "at", "PRIVATE_GUARD", facade.time())
    assert after["at"] > before["at"] + 180
    for key in ("cycle", "cycle_state", "last_completed_cycle", "last_cycle_completed_at"):
        assert after[key] == before[key]
    assert after["cycle"] == 3 and after["last_completed_cycle"] == 2


def test_atomic_heartbeat_replacement_preserves_complete_previous_observation(supervised, monkeypatch):
    record, heartbeat = record_and_heartbeat(supervised)
    D._publish_heartbeat(record, cycle=0)
    previous = heartbeat.read_bytes()
    replace = os.replace
    observations = []

    def observed(source, target):
        assert Path(target) == heartbeat and heartbeat.read_bytes() == previous
        assert json.loads(Path(source).read_bytes())["last_completed_cycle"] == 0
        observations.append("complete_private_stage")
        return replace(source, target)

    monkeypatch.setattr(D.os, "replace", observed)
    D._publish_heartbeat(record, cycle=0, completed=True)
    assert observations == ["complete_private_stage"]
    assert json.loads(heartbeat.read_bytes())["cycle_state"] == "COMPLETE"
    assert not list(heartbeat.parent.glob(".heartbeat-*"))


def test_failed_publication_preserves_prior_observation_and_typed_failure(supervised, monkeypatch):
    record, heartbeat = record_and_heartbeat(supervised)
    D._publish_heartbeat(record, cycle=0)
    before = heartbeat.read_bytes()

    def failed(*_):
        raise OSError("PRIVATE_STORAGE_FAULT_NOT_A_STATUS_DETAIL")

    monkeypatch.setattr(D.os, "replace", failed)
    with pytest.raises(Refused, match="HEARTBEAT_STORAGE_UNAVAILABLE"):
        D._publish_heartbeat(record, cycle=0, completed=True)
    assert heartbeat.read_bytes() == before and not list(heartbeat.parent.glob(".heartbeat-*"))


@pytest.mark.parametrize("field,value", [("pid", 1), ("record_sha256", "0" * 64), ("mode", "PILOT")])
def test_changed_heartbeat_identity_is_not_overwritten(supervised, field, value):
    record, heartbeat = record_and_heartbeat(supervised)
    D._publish_heartbeat(record, cycle=0)
    bad = json.loads(heartbeat.read_bytes())
    bad[field] = value
    heartbeat.write_text(json.dumps(bad))
    before = heartbeat.read_bytes()
    with pytest.raises(Refused, match="HEARTBEAT_IDENTITY_CHANGED"):
        D._publish_heartbeat(record, cycle=0, completed=True)
    assert heartbeat.read_bytes() == before


def test_main_first_cycle_can_run_existing_heartbeat_guard_before_any_completion(supervised, monkeypatch, tmp_path):
    from forge_factory.afo import line_launcher as LL
    from forge_factory.afo import line_orders as O

    before = MissionLedger(supervised["store"]).snapshot(D.MISSION)
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    monkeypatch.setenv("FORGE_DURABLE_NATIVE_HEADER", "1")
    monkeypatch.setattr(LL.LineConfig, "from_env", lambda: SimpleNamespace(stack_root=tmp_path))
    monkeypatch.setattr(O, "RealLine", lambda _: object())
    monkeypatch.setattr(D, "provider_preflight", lambda _: {"placing": True})
    observed = []

    class Placer:
        def __init__(self, *_, **__):
            pass

        def cycle(self):
            path = Path(os.environ[D.FILE]).with_suffix(".heartbeat.json")
            G.heartbeat(path, os.getpid(), D.MODE, "at", "PRIVATE_FIRST_CYCLE_GUARD", time.time())
            value = json.loads(path.read_bytes())
            assert value["cycle"] == 0 and value["cycle_state"] == "IN_PROGRESS"
            assert value["last_completed_cycle"] == -1 and value["last_cycle_completed_at"] is None
            observed.append(path)
            return {"actions": []}

    monkeypatch.setattr(O, "Placer", Placer)
    assert D.main(["--control", supervised["control_ref"]["path"],
                   "--runtime-policy", str(supervised["runtime"]), "--line-policy", str(supervised["line"]),
                   "--campaigns", str(tmp_path / "unused-campaigns"),
                   "--expiry-ticket", str(supervised["ticket_path"]), "--max-cycles", "1"]) == 0
    assert len(observed) == 1
    done = json.loads(observed[0].read_bytes())
    assert done["last_completed_cycle"] == 0 and done["cycle_state"] == "COMPLETE"
    assert MissionLedger(supervised["store"]).snapshot(D.MISSION) == before
