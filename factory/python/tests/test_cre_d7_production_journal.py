"""CRE-T045 (CRE-FR-007) — production side effects (archive write, infra CAS switch/rollback, work-order launch) are
journaled with replay classes; enforced in PILOT/ACTIVE, shadow-recorded without behaviour change in OBSERVE_ONLY."""
import json
import os
import stat

import pytest
from forge_factory import workorder as WO
from forge_factory.release import finalize as F
from forge_factory.reliability import policy as RP
from forge_factory.reliability import production as P
from forge_factory.reliability.store import CREStore


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(tmp_path / "archives"))
    return tmp_path


@pytest.fixture
def enforcing(monkeypatch):
    monkeypatch.setattr(RP.Policy, "mode", property(lambda self: "PILOT"))


def rows(key):
    with CREStore().conn() as c:
        return [(r["status"], r["replay_class"]) for r in
                c.execute("SELECT status, replay_class FROM cre_side_effects WHERE idem_key=? ORDER BY seq", (key,))]


def shadow_events(key):
    with CREStore().conn() as c:
        recs = [json.loads(r[0]) for r in c.execute("SELECT record FROM cre_events WHERE type='cre.side_effect'")]
    return [r["payload"]["shadow_decision"] for r in recs if r["correlation_id"] == key and
            r["payload"].get("state") == "SHADOW"]


def fake_fabro(tmp_path):
    count = tmp_path / "launches"
    fab = tmp_path / "fabro"
    fab.write_text(f"#!/bin/sh\necho x >> {count}\necho run-$(wc -l < {count} | tr -d ' ')\n")
    fab.chmod(fab.stat().st_mode | stat.S_IXUSR)
    return str(fab), count


def ws_of(tmp_path):
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    return ws


# ---- observe-only: journaled, 002 behaviour unchanged ------------------------------------------------------------
def test_observe_only_records_and_shadows_but_never_changes_behaviour(env):
    calls = []
    a = P.guarded("workorder_launch", "workorder_launch:WO-A", lambda k: calls.append(k) or {"fabro_run_id": "r1"})
    b = P.guarded("workorder_launch", "workorder_launch:WO-A", lambda k: calls.append(k) or {"fabro_run_id": "r2"})
    assert a["executed"] and b["executed"] and len(calls) == 2  # 002 relaunch behaviour kept
    assert a["shadow_decision"] == "EXECUTE" and b["shadow_decision"] == "ALREADY_DONE"
    assert shadow_events("workorder_launch:WO-A") == ["ALREADY_DONE"]  # what enforcement would have done
    assert rows("workorder_launch:WO-A") == [("PENDING", "REPLAY_WITH_IDEMPOTENCY_KEY"),
                                             ("DONE", "REPLAY_WITH_IDEMPOTENCY_KEY")] * 2


def test_observe_only_cre_store_failure_never_blocks_the_action(env, monkeypatch):
    def broken(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr("forge_factory.reliability.store.CREStore.__init__", broken)
    out = P.guarded("archive_write", "archive_write:WO-B", lambda k: {"ok": True})
    assert out["executed"] and out["status"] == "UNJOURNALED" and out["receipt"] == {"ok": True}
    log = "".join(p.read_text() for p in (env / "state/events").rglob("*.jsonl"))
    assert "cre journal degraded" in log


def test_failure_is_recorded_and_reraised(env):
    with pytest.raises(RuntimeError):
        P.guarded("infra_cas_switch", "infra_cas_switch:att-f", lambda k: (_ for _ in ()).throw(RuntimeError("x")))
    assert [s for s, _ in rows("infra_cas_switch:att-f")] == ["PENDING", "FAILED"]


# ---- enforcing (PILOT/ACTIVE) ------------------------------------------------------------------------------------
def test_enforcing_never_repeats_done_and_stops_on_unknown_outcome(env, enforcing):
    calls = []
    P.guarded("workorder_launch", "workorder_launch:WO-C", lambda k: calls.append(k) or {"fabro_run_id": "r1"})
    again = P.guarded("workorder_launch", "workorder_launch:WO-C", lambda k: calls.append(k) or {"fabro_run_id": "x"})
    assert again["status"] == "ALREADY_DONE" and again["receipt"] == {"fabro_run_id": "r1"} and len(calls) == 1
    with pytest.raises(KeyboardInterrupt):  # crash during the CAS switch: outcome unknown, PENDING stays
        P.guarded("infra_cas_switch", "infra_cas_switch:att-1", lambda k: (_ for _ in ()).throw(KeyboardInterrupt()))
    after = P.guarded("infra_cas_switch", "infra_cas_switch:att-1", lambda k: calls.append(k))
    assert after["status"] == "REQUIRES_OFFLINE_ATTENTION" and not after["executed"] and len(calls) == 1
    with pytest.raises(RuntimeError):  # a failed (possibly partial) compensatable action is not replayed either
        P.guarded("infra_cas_switch", "infra_cas_switch:att-2", lambda k: (_ for _ in ()).throw(RuntimeError("x")))
    assert P.guarded("infra_cas_switch", "infra_cas_switch:att-2", lambda k: 1)["status"] == \
        "REQUIRES_OFFLINE_ATTENTION"
    with pytest.raises(RuntimeError):  # an idempotent action that failed is retried
        P.guarded("archive_write", "archive_write:WO-D", lambda k: (_ for _ in ()).throw(RuntimeError("x")))
    assert P.guarded("archive_write", "archive_write:WO-D", lambda k: {"ok": 1})["status"] == "DONE"


def test_enforcing_fails_closed_when_the_journal_is_unavailable(env, enforcing, monkeypatch):
    def broken(*a, **k):
        raise OSError("locked")
    monkeypatch.setattr("forge_factory.reliability.store.CREStore.__init__", broken)
    calls = []
    with pytest.raises(OSError):
        P.guarded("workorder_launch", "workorder_launch:WO-E", lambda k: calls.append(k))
    assert calls == []


# ---- real production sites ---------------------------------------------------------------------------------------
def test_work_order_launch_is_journaled_and_idempotent_when_enforcing(env, enforcing, monkeypatch):
    fab, count = fake_fabro(env)
    monkeypatch.setattr(WO, "fabro_env", lambda: dict(os.environ))
    ws = ws_of(env)
    assert WO.launch_run(ws, "WO-L", env / "run.toml", fab) == "run-1"
    assert WO.launch_run(ws, "WO-L", env / "run.toml", fab) == "run-1"  # replayed launch: no second Fabro run
    assert count.read_text().count("x") == 1
    assert [s for s, _ in rows("workorder_launch:WO-L")] == ["PENDING", "DONE"]


def test_work_order_launch_observe_only_keeps_002_relaunch(env, monkeypatch):
    fab, count = fake_fabro(env)
    monkeypatch.setattr(WO, "fabro_env", lambda: dict(os.environ))
    ws = ws_of(env)
    assert WO.launch_run(ws, "WO-M", env / "run.toml", fab) == "run-1"
    assert WO.launch_run(ws, "WO-M", env / "run.toml", fab) == "run-2"
    assert shadow_events("workorder_launch:WO-M") == ["ALREADY_DONE"]


def test_archive_write_is_journaled_once_and_write_once_holds(env):
    ws = env / "ws"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text("- **SWR-001** The RCC driver shall reset.\n")
    out = F.finalize(ws, "WO-J")
    assert [s for s, _ in rows("archive_write:WO-J")] == ["PENDING", "DONE"]
    with CREStore().conn() as c:
        receipt = json.loads(c.execute("SELECT receipt FROM cre_side_effects WHERE idem_key=? AND status='DONE'",
                                       ("archive_write:WO-J",)).fetchone()[0])
    assert receipt == {"archive_sha256": out["archive_sha256"], "package_status": out["package_status"]}
    F.finalize(ws, "WO-J")  # replay: write-once early return, no second journal entry
    assert len(rows("archive_write:WO-J")) == 2


def test_infra_cas_switch_and_rollback_are_journaled(env, monkeypatch):
    from forge_factory.repair import infra as I
    from forge_factory.repair import promotion as PR
    from forge_factory.supervisor.store import IncidentStore

    monkeypatch.setenv("FORGE_INFRA_REPO", str(env / "infra"))
    monkeypatch.setenv("FORGE_DATA_ROOT", str(env))
    infra = I.ensure_infra()
    cfg = infra / "runtime/llm-gateway.json"
    cfg.write_text(json.dumps({"bind": "127.0.0.1", "port": 9999, "upstream": "http://127.0.0.1:11435"}))
    I.git(infra, "commit", "-qam", "induced fault")
    store = IncidentStore()
    inc, _ = store.open_or_dedup("llm-gateway:CONFIG_INVALID:-:0.4", "llm-gateway", "CONFIG_INVALID")
    store.transition(inc["incident_id"], "TRIAGED")
    store.transition(inc["incident_id"], "REPAIRING", attempts=1)
    wt = PR.create_repair_worktree("att-j", infra)
    (wt / "runtime/llm-gateway.json").write_text(json.dumps({"bind": "127.0.0.1", "port": 11436,
                                                             "upstream": "http://127.0.0.1:11435"}))
    PR.commit_worktree(wt, "fix port")
    old = I.git(infra, "rev-parse", "main")
    out = PR.promote("att-j", inc["incident_id"], store, lambda _p: False, stable_polls=2, poll_interval_s=0.01)
    assert out["status"] == "ROLLED_BACK" and I.git(infra, "rev-parse", "main") == old  # health never restored
    assert rows("infra_cas_switch:att-j") == [("PENDING", "COMPENSATABLE"), ("DONE", "COMPENSATABLE")]
    assert [s for s, _ in rows("infra_cas_rollback:att-j")] == ["PENDING", "DONE"]
