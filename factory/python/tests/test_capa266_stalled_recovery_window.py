"""CAPA-266 (2026-11-15, SPI L51D): the maintenance window counted every WAITING_RECOVERY order as an active lane.
L51D's durable recovery validated a plan whose retry the placer refused (CAPA-265), so the order stayed
WAITING_RECOVERY with no further lifecycle event, nothing ran on the GPU, and defect mode skipped every tick
(LANE_NOT_IDLE ORDERS_ACTIVE:WAITING_RECOVERY=1): the maintainer could never get the defect that stalled the line.
A WAITING_RECOVERY order with no lifecycle event for STALLED_RECOVERY_S is stalled, not active; every other idle
check (inference owner, execution leases, request ledger, command outcomes) still holds, and the window stops the
lane model before the tier starts."""
import sqlite3
import time

from forge_factory.modelservice import window_adapters as W

NOW = 1_800_000_000.0
iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime(t))  # noqa: E731


def _lane(tmp_path, last_event_age=None, lifecycle=True):
    db = tmp_path / "lrtx/state/supervisor/line-queue.sqlite3"
    db.parent.mkdir(parents=True)
    c = sqlite3.connect(db)
    c.executescript("""CREATE TABLE afo_work_orders(order_id, state); CREATE TABLE afo_control(key, value, updated_utc, actor);
        CREATE TABLE afo_resource_ownership(resource, holder); CREATE TABLE afo_execution_liveness(record);
        CREATE TABLE afo_request_ledger(state); CREATE TABLE afo_commands_outbox(state);
        INSERT INTO afo_control VALUES ('paused','0','t','a'); INSERT INTO afo_work_orders VALUES ('o1','WAITING_RECOVERY');""")
    if lifecycle:
        c.execute("CREATE TABLE afo_lifecycle_events(seq, event_id, occurred_utc, type, order_id)")
        if last_event_age is not None:
            c.execute("INSERT INTO afo_lifecycle_events VALUES (1,'e1',?,'afo.plan_validated','o1')", (iso(NOW - last_event_age),))
    c.commit()
    c.close()
    lane = W.OwnerLane(lrtx=tmp_path / "lrtx", qual=tmp_path / "q", deployer=tmp_path / "d", intent=tmp_path / "i.json",
                       work=tmp_path / "w")
    lane.clock = lambda: NOW
    return lane


def test_a_recovery_without_any_event_for_30_min_does_not_hold_the_window(tmp_path):
    assert _lane(tmp_path, last_event_age=W.STALLED_RECOVERY_S + 60).idle() == (True, "IDLE")


def test_a_recovery_that_moved_recently_still_holds_the_window(tmp_path):
    assert _lane(tmp_path, last_event_age=300).idle() == (False, "ORDERS_ACTIVE:WAITING_RECOVERY=1")


def test_without_lifecycle_evidence_a_recovery_stays_active(tmp_path):
    assert _lane(tmp_path, last_event_age=None).idle() == (False, "ORDERS_ACTIVE:WAITING_RECOVERY=1")
    assert _lane(tmp_path / "x", lifecycle=False).idle() == (False, "ORDERS_ACTIVE:WAITING_RECOVERY=1")


def test_idle_check_never_combines_queue_and_lease_state_from_different_transactions(tmp_path, monkeypatch):
    lane = _lane(tmp_path, last_event_age=W.STALLED_RECOVERY_S + 60)
    db = lane.lrtx / "state/supervisor/line-queue.sqlite3"
    with sqlite3.connect(db) as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        writer.execute("INSERT INTO afo_resource_ownership VALUES ('inference','job-a')")

    check_recoveries = lane._stalled_recoveries

    def settle_and_admit(connection):
        # Each committed state is busy. A split read sees the old queue and new lease.
        with sqlite3.connect(db) as writer:
            writer.execute("DELETE FROM afo_resource_ownership WHERE resource='inference'")
            writer.execute("INSERT INTO afo_work_orders VALUES ('o2','RUNNING')")
        return check_recoveries(connection)

    monkeypatch.setattr(lane, "_stalled_recoveries", settle_and_admit)
    assert lane.idle() == (False, "INFERENCE_OWNER_PRESENT")
    monkeypatch.setattr(lane, "_stalled_recoveries", check_recoveries)
    assert lane.idle() == (False, "ORDERS_ACTIVE:RUNNING=1")
