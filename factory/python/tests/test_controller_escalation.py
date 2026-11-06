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
    P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, cfg=p.cfg,
               launch=lambda *args: dict(outcome="STACK_STOP_FAILED"))
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
    assert len(list((p.store.path.parent / "controller-escalations").glob("case-*/export.zip"))) == 1


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
    assert not (p.store.path.parent / "controller-escalations").exists()


def test_nonpinned_store_and_wrong_canonical_path_refuse(settled):
    p = settled
    with pytest.raises(Exception):
        E.cycle(p.store, p.cfg, store_identity=p.identity)
    with pytest.raises(Exception):
        E.cycle(p.pinned, p.cfg, store_identity=dict(device=0, inode=0))


def test_ambiguous_transport_stays_held_and_is_not_a_no_native_case(product):
    p = product
    def unknown(*args):
        raise TimeoutError("not evidence of no native")
    P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, cfg=p.cfg, launch=unknown)
    s = p.store.path.stat()
    result = E.cycle(Store(p.store.path, must_exist=True), p.cfg,
                     store_identity=dict(device=s.st_dev, inode=s.st_ino))
    assert result["exports"] == []
    assert Executions(p.store).get(P.job_id(p.aid))["resource_lease"] == "HELD"


def test_tampered_export_is_refused_not_overwritten(settled):
    p = settled
    def crash(at):
        if at == "bundle_written":
            raise RuntimeError("PRIVATE_CRASH")
    with pytest.raises(RuntimeError):
        drain(p, _checkpoint=crash)
    archive = next((p.store.path.parent / "controller-escalations").glob("case-*/export.zip"))
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
