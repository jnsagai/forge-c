# ruff: noqa: F811 - imported pytest fixture
"""Private normal settlement/export controls; no native/model runtime qualification."""

import json
import os
from pathlib import Path

import pytest
from forge_factory.afo import controller_escalation as E
from forge_factory.afo import line_recovery_product as P
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from test_line_recovery_product_bridge import product  # noqa: F401


@pytest.fixture
def settled(product):
    p = product
    p.cfg.runs_root = p.store.path.parent.parent.parent / "runs"
    P.dispatch(
        p.store, p.cmd, p.worker, p.spec, p.eff, p.client, cfg=p.cfg, launch=lambda *args: dict(outcome="STACK_STOP_FAILED")
    )
    p.pinned = Store(p.store.path, must_exist=True)
    s = p.pinned.path.stat()
    p.identity = dict(device=s.st_dev, inode=s.st_ino)
    return p


def drain(p, **kw):
    return E.cycle(p.pinned, p.cfg, store_identity=p.identity, **kw)


def test_real_settlement_exports_one_controller_case_without_native_or_spend(settled):
    p = settled
    before = MissionLedger(p.store).snapshot("fixture-mission")
    live = Executions(p.store).get(P.job_id(p.aid))
    result = drain(p)
    assert result["model_calls"] == 0 and result["status"] == "OBSERVED"
    assert len(result["exports"]) == 1
    out = result["exports"][0]
    assert Path(out["bundle"]).is_file() and Path(out["report"]).is_file()
    report = Path(out["report"]).read_text()
    assert "STACK_STOP_FAILED" in report and "NOT_RECORDED" in report
    assert "CONTROLLER_FAILURE_UNDIAGNOSED" in report
    assert MissionLedger(p.store).snapshot("fixture-mission") == before
    assert Executions(p.store).get(P.job_id(p.aid)) == live
    assert len(p.store.commands()) == 1 and p.store.commands()[0]["state"] == "QUARANTINED"
    with p.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_dead_letters").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM afo_notifications").fetchone()[0] == 1
    assert drain(p)["exports"] == []


@pytest.mark.parametrize("phase", ["case_sealed", "bundle_written", "receipt_committed"])
def test_crash_recovery_is_idempotent_and_preserves_budget(settled, phase):
    p = settled
    before = MissionLedger(p.store).snapshot("fixture-mission")

    def crash(at):
        if at == phase:
            raise RuntimeError("PRIVATE_CRASH")

    with pytest.raises(RuntimeError, match="PRIVATE_CRASH"):
        drain(p, _checkpoint=crash)
    E.cycle(Store(p.store.path, must_exist=True), p.cfg, store_identity=p.identity)
    assert MissionLedger(p.store).snapshot("fixture-mission") == before
    with p.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_lifecycle_events WHERE type='afo.controller_exported'").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM afo_dead_letters").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM afo_notifications").fetchone()[0] == 1
    assert len(list((E.archive_root() / "controller-exports").glob("case-*/export.zip"))) == 1


@pytest.mark.parametrize("change", ["missing", "rebound", "symlink"])
def test_storage_loss_or_rebound_never_initializes_or_exports(settled, change):
    p = settled
    saved = p.store.path.with_suffix(".saved")
    os.rename(p.store.path, saved)
    if change == "rebound":
        p.store.path.write_bytes(saved.read_bytes())
    elif change == "symlink":
        p.store.path.symlink_to(saved)
    with pytest.raises(Exception):
        drain(p)
    if change == "missing":
        assert not p.store.path.exists()
    assert not (E.archive_root() / "controller-exports").exists()


def test_nonpinned_store_and_wrong_canonical_path_refuse(settled):
    p = settled
    with pytest.raises(Exception):
        E.cycle(p.store, p.cfg, store_identity=p.identity)
    with pytest.raises(Exception):
        E.cycle(p.pinned, p.cfg, store_identity=dict(device=0, inode=0))


def test_ambiguous_transport_stays_held_and_is_not_a_no_native_case(product):
    p = product
    p.cfg.runs_root = p.store.path.parent.parent.parent / "runs"

    def unknown(*args):
        raise TimeoutError("not evidence of no native")

    P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, cfg=p.cfg, launch=unknown)
    s = p.store.path.stat()
    result = E.cycle(Store(p.store.path, must_exist=True), p.cfg, store_identity=dict(device=s.st_dev, inode=s.st_ino))
    assert result["exports"] == []
    assert Executions(p.store).get(P.job_id(p.aid))["resource_lease"] == "HELD"


def test_tampered_export_is_refused_not_overwritten(settled):
    p = settled

    def crash(at):
        if at == "bundle_written":
            raise RuntimeError("PRIVATE_CRASH")

    with pytest.raises(RuntimeError):
        drain(p, _checkpoint=crash)
    archive = next((E.archive_root() / "controller-exports").glob("case-*/export.zip"))
    archive.write_bytes(b"FOREIGN_CONTENT")
    with pytest.raises(Exception):
        drain(p)
    assert archive.read_bytes() == b"FOREIGN_CONTENT"


def test_declared_bounds_and_missing_evidence_are_explicit(settled):
    p = settled
    with pytest.raises(Exception):
        drain(p, max_cases=2)
    result = drain(p)
    case = json.loads(Path(result["exports"][0]["case"]).read_text())
    assert "LAUNCH_TRANSCRIPT_MISSING" in case["gaps"]
    assert case["execution"]["native_run_ids"] == []


def test_late_settlement_is_seen_after_earlier_stream_cursor(product):
    p = product
    p.cfg.runs_root = p.store.path.parent.parent.parent / "runs"
    p.pinned = Store(p.store.path, must_exist=True)
    s = p.store.path.stat()
    p.identity = dict(device=s.st_dev, inode=s.st_ino)
    assert drain(p)["exports"] == []
    P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, cfg=p.cfg, launch=lambda *a: dict(outcome="GUARD_FAIL"))
    assert len(drain(p)["exports"]) == 1


def test_stream_work_is_bounded_and_cursor_is_authenticated(product):
    p = product
    p.cfg.runs_root = p.store.path.parent.parent.parent / "runs"
    p.pinned = Store(p.store.path, must_exist=True)
    s = p.store.path.stat()
    p.identity = dict(device=s.st_dev, inode=s.st_ino)
    with p.store.tx() as c:
        for i in range(100):
            p.store._event(c, "private_healthy_fact", p.oid, payload=dict(i=i))
    result = drain(p)
    assert result["examined_events"] == E.MAX_EVENTS and result["exports"] == []
    with p.store.tx() as c:
        row = c.execute("SELECT value FROM afo_control WHERE key=?", (E.CURSOR,)).fetchone()
        pointer = json.loads(row[0])
        assert pointer["schema"] == E.CURSOR_SCHEMA
        pointer["event_sha256"] = "0" * 64
        c.execute("UPDATE afo_control SET value=? WHERE key=?", (json.dumps(pointer), E.CURSOR))
    with pytest.raises(Exception):
        drain(p)


def test_archive_location_must_not_be_reclaimable(settled, monkeypatch):
    p = settled
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(p.cfg.runs_root / "exports"))
    with pytest.raises(Exception):
        drain(p)


def test_oversize_and_unsafe_transcripts_are_gaps_not_bodies(settled):
    p = settled
    root = p.cfg.runs_root / ".launch" / p.spec["wo"]
    root.mkdir(parents=True)
    (root / "attempt-1.json").write_bytes(b"NEVER_BODY" * E.MAX_RECORD)
    result = drain(p)
    case = json.loads(Path(result["exports"][0]["case"]).read_text())
    assert "CONTROLLER_EXPORT_FILE_BOUND_OR_TYPE" in case["gaps"]
    assert "NEVER_BODY" not in Path(result["exports"][0]["report"]).read_text()


def test_deadletter_batch_cannot_pin_cursor_ahead_of_late_settlement(product):
    p = product
    p.cfg.runs_root = p.store.path.parent.parent.parent / "runs"
    p.pinned = Store(p.store.path, must_exist=True)
    s = p.store.path.stat()
    p.identity = dict(device=s.st_dev, inode=s.st_ino)
    assert drain(p)["exports"] == []
    with p.store.tx() as c:
        for i in range(E.MAX_EVENTS):
            p.store._event(c, "dead_letter", p.oid, payload=dict(private_event=i))
    assert drain(p)["examined_events"] == E.MAX_EVENTS
    P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, cfg=p.cfg,
               launch=lambda *a: dict(outcome="STACK_STOP_FAILED"))
    results = [drain(p) for _ in range(3)]
    assert sum(len(r["exports"]) for r in results) == 1
    with p.store.tx() as c:
        before = c.execute("SELECT COUNT(*) FROM afo_lifecycle_events").fetchone()[0]
    drain(p)
    drain(p)
    with p.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_lifecycle_events").fetchone()[0] == before


def test_positive_transcript_and_exact_bound_stop_log_explain_recorded_guard(settled):
    import hashlib
    p = settled
    base = p.cfg.runs_root / ".launch" / p.spec["wo"]
    logs = base / "attempt-1"
    logs.mkdir(parents=True)
    raw = b"Refused: LINE_STACK_NATIVE_NOT_QUIESCENT\nNEVER_RAW_PROMPT token=NEVER_SECRET\n"
    (logs / "stack-stop.log").write_bytes(raw)
    (base / "attempt-1.json").write_text(json.dumps(dict(
        schema="forge-c/line-launch-attempt/1", work_order=p.spec["wo"], revision="a" * 40,
        fabro_run_id=None, outcome="STACK_STOP_FAILED", step_logs=str(logs),
        steps=[dict(step="guard",outcome="OK"),dict(step="stack_stop",outcome="RC_1",rc=1)])))
    result = drain(p)
    case = json.loads(Path(result["exports"][0]["case"]).read_text())
    assert case["records"]["stop_log"]["observed_codes"] == ["LINE_STACK_NATIVE_NOT_QUIESCENT"]
    assert case["records"]["stop_log"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert "stack_stop" in case["records"]["steps_recorded"]
    assert "workorder_launch" in case["records"]["steps_not_recorded"]
    report = Path(result["exports"][0]["report"]).read_text()
    assert "LINE_STACK_NATIVE_NOT_QUIESCENT" in report
    assert "NEVER_SECRET" not in report and "NEVER_RAW_PROMPT" not in report


def test_reporting_errors_are_contained_without_authorizing_or_changing_execution(settled, monkeypatch):
    p = settled
    before = Executions(p.store).get(P.job_id(p.aid))
    def unavailable(*a, **kw):
        from forge_factory.afo.durable import Refused
        raise Refused("CONTROLLER_EXPORT_ARTIFACT_REBOUND", "NEVER_DETAIL")
    monkeypatch.setattr(E, "cycle", unavailable)
    result = E.observe(p.pinned,p.cfg,store_identity=p.identity)
    assert result == dict(status="CAPTURE_FAILED",code="CONTROLLER_EXPORT_ARTIFACT_REBOUND",exports=[],model_calls=0)
    assert Executions(p.store).get(P.job_id(p.aid)) == before
