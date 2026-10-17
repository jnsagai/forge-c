"""CRE-T044 (CRE-FR-005, AT-008/AT-009) — CRE admission on the 002 repair-dispatch path: durable per-fingerprint
budget (survives restarts and recurrences), factory-wide hourly quota, deterministic jittered backoff; enforced in
PILOT/ACTIVE, shadow-recorded in OBSERVE_ONLY without changing 002 dispatch."""
import pytest
from forge_factory.reliability import policy as RP
from forge_factory.reliability import recovery as R
from forge_factory.reliability.store import CREStore
from forge_factory.reliability.supervisor_hook import CREHook
from forge_factory.supervisor.store import IncidentStore

T0 = 2_000_000_000.0


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return tmp_path


@pytest.fixture
def enforcing(monkeypatch):
    monkeypatch.setattr(RP.Policy, "mode", property(lambda self: "PILOT"))


def adm(env):
    return R.DispatchAdmission(CREStore(env / "i.sqlite3"), RP.load())


def test_budget_is_per_fingerprint_and_survives_restarts(env, enforcing):
    r = RP.load().data["recovery"]
    n_max = int(r["max_repair_attempts_per_incident"])
    t, decisions = T0, []
    for _ in range(n_max + 2):  # a fresh admission object each time = supervisor restart
        d = adm(env).admit("llm-gateway:CONFIG_INVALID", now=t)
        decisions.append(d)
        t = max(t, d.not_before_epoch) + 1 if d.allowed else t + 1
    assert sum(d.allowed for d in decisions) == n_max
    assert decisions[-1].reason.startswith("REPAIR_BUDGET_EXHAUSTED")
    assert adm(env).admit("mcp:CONFIG_INVALID", now=t).allowed  # another fingerprint has its own budget
    assert adm(env).admit("llm-gateway:CONFIG_INVALID", now=t + R.DispatchAdmission.RECURRENCE_WINDOW_S + 1).allowed


def test_backoff_is_deterministic_jittered_and_enforced(env, enforcing):
    a = adm(env).admit("fp-a", now=T0)
    denied = adm(env).admit("fp-a", now=T0 + 0.5)
    assert a.allowed and not denied.allowed and denied.reason.startswith("BACKOFF_PENDING")
    r = RP.load().data["recovery"]
    lo, hi = 1 - float(r["jitter_ratio"]), 1 + float(r["jitter_ratio"])
    assert lo * float(r["initial_backoff_seconds"]) <= a.not_before_epoch - T0 <= hi * float(r["initial_backoff_seconds"])
    other = R.DispatchAdmission(CREStore(env / "j.sqlite3"), RP.load())  # independent store, same inputs
    assert other.admit("fp-a", now=T0).not_before_epoch == a.not_before_epoch  # same key/attempt -> same jitter (reproducible)
    assert other.admit("fp-b", now=T0).not_before_epoch != a.not_before_epoch  # different keys desynchronise


def test_factory_wide_hourly_quota(env, enforcing):
    q = int(RP.load().data["recovery"]["max_repairs_per_hour"])
    got = [adm(env).admit(f"fp-{i}", now=T0 + i) for i in range(q + 1)]
    assert [d.allowed for d in got] == [True] * q + [False]
    assert got[-1].reason.startswith("HOURLY_REPAIR_QUOTA")
    assert adm(env).admit("fp-late", now=T0 + 3601 + q).allowed


def _incident(store, fp="llm-gateway:CONFIG_INVALID:-:0.4"):
    inc, _ = store.open_or_dedup(fp, "llm-gateway", "CONFIG_INVALID", last_error="x")
    store.transition(inc["incident_id"], "TRIAGED")
    return store.must(inc["incident_id"])


def test_hook_enforces_and_sends_exhausted_recurrences_to_offline_attention(env, enforcing, monkeypatch):
    clock = [T0]
    monkeypatch.setattr(R.DispatchAdmission, "clock", staticmethod(lambda: clock[0]))
    store = IncidentStore(env / "i.sqlite3")
    hook = CREHook(env / "i.sqlite3")
    n_max = int(RP.load().data["recovery"]["max_repair_attempts_per_incident"])
    states = []
    for _ in range(n_max + 1):  # each recurrence is a NEW 002 incident (attempts=0) with the same fingerprint
        inc = _incident(store)
        inc2 = _incident(store, "mcp:CONFIG_INVALID:-:0.4") if not states else None
        out = hook.on_poll([], store, [inc])
        if inc2:  # a TRIAGED incident still inside its backoff window is deferred, not terminated
            hook.on_poll([], store, [inc2])
            assert hook.on_poll([], store, [inc2]) == [] and store.must(inc2["incident_id"])["state"] == "TRIAGED"
            store.transition(inc2["incident_id"], "RESOLVED", "test")
        states.append("dispatched" if out == [inc] else store.must(inc["incident_id"])["state"])
        if out:
            store.transition(inc["incident_id"], "REPAIRING", attempts=1)
            store.transition(inc["incident_id"], "REQUIRES_OFFLINE_ATTENTION", "test: repair failed")
        clock[0] += 3600  # past any backoff and the hourly quota
    assert states == ["dispatched"] * n_max + ["REQUIRES_OFFLINE_ATTENTION"]  # recurrences cannot reset the budget


def test_observe_only_shadows_and_keeps_002_dispatch(env):
    assert RP.load().mode == "OBSERVE_ONLY"
    store = IncidentStore(env / "i.sqlite3")
    hook = CREHook(env / "i.sqlite3")
    inc = _incident(store)
    for _ in range(5):
        assert hook.on_poll([], store, [inc]) == [inc]  # never filtered
    with CREStore(env / "i.sqlite3").conn() as c:
        outcomes = [r[0] for r in c.execute("SELECT outcome FROM cre_retry_attempts WHERE op_key LIKE "
                                            "'repair_dispatch:%'")]
    assert outcomes == ["SHADOW_ADMITTED"]  # later polls fall in the backoff window (recorded without noise)
    assert store.must(inc["incident_id"])["state"] == "TRIAGED"
