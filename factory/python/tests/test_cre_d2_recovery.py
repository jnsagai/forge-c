"""CRE D2 (CRE-T011..T016): bounded retries, breaker, leases, replay classes, supervisor integration, FSM properties
(AT-008..AT-013)."""
import json
import multiprocessing as mp
import os
import random
import sqlite3
import sys
import time

import pytest
from forge_factory.reliability import policy as RP
from forge_factory.reliability import recovery as R
from forge_factory.reliability.store import CREStore
from forge_factory.supervisor import probes as P
from forge_factory.supervisor import service as S
from forge_factory.supervisor.dispatch import dispatch
from forge_factory.supervisor.store import IncidentStore


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return tmp_path


def pol():
    return RP.load()


# ---- CRE-T011 / AT-008 -------------------------------------------------------------------------------------------
def test_retries_stay_bounded_across_restarts_and_use_deterministic_jitter(env):
    db = env / "i.sqlite3"
    t = 1_000_000.0
    decisions = []
    for restart in range(4):  # persistent 429 + a forced supervisor restart before every call
        adm = R.RetryAdmission(CREStore(db), pol())
        d = adm.admit("mcp:forge-tests-mcp:run_unit|WO-1", failure_class="TRANSIENT_DEPENDENCY",
                      replay_class="REPLAY_WITH_IDEMPOTENCY_KEY", now=t + restart * 1000)
        decisions.append(d)
    admitted = [d for d in decisions if d.allowed]
    assert len(admitted) == pol().get("recovery.max_transient_retries_per_operation") == 2
    assert decisions[-1].reason.startswith("RETRY_BUDGET_EXHAUSTED")
    a, b = R.RetryAdmission(CREStore(db), pol()), R.RetryAdmission(CREStore(env / "j.sqlite3"), pol())
    assert a.backoff("k", 3) == b.backoff("k", 3) and 2 * 4 * 0.8 <= a.backoff("k", 3) <= 2 * 4 * 1.2
    assert a.backoff("k", 30) <= 60 * 1.2  # capped by max_backoff_seconds


@pytest.mark.parametrize("cls,replay,op,reason", [
    ("PRODUCT_QUALITY", "REPLAY_SAFE", "", "NOT_RETRYABLE_CLASS:PRODUCT_QUALITY"),
    ("TRANSIENT_DEPENDENCY", "NON_REPLAYABLE", "", "NON_REPLAYABLE"),
    ("TRANSIENT_DEPENDENCY", "REPLAY_SAFE", "hardware_flash", "NON_REPLAYABLE:hardware_flash"),
])
def test_non_retryable_requests_are_denied_with_a_reason(env, cls, replay, op, reason):
    d = R.RetryAdmission(CREStore(env / "i.sqlite3"), pol()).admit("op", failure_class=cls, replay_class=replay,
                                                                    op_class=op)
    assert not d.allowed and d.reason.startswith(reason)


def test_backoff_is_honoured_and_budgets_deny(env):
    adm = R.RetryAdmission(CREStore(env / "i.sqlite3"), pol())
    first = adm.admit("op", failure_class="TRANSIENT_DEPENDENCY", replay_class="REPLAY_SAFE", now=100.0)
    early = adm.admit("op", failure_class="TRANSIENT_DEPENDENCY", replay_class="REPLAY_SAFE", now=100.5)
    assert first.allowed and not early.allowed and early.reason.startswith("BACKOFF_PENDING")
    assert adm.admit("op2", failure_class="TRANSIENT_DEPENDENCY", replay_class="REPLAY_SAFE",
                     budget_tokens_left=0).reason == "TOKEN_BUDGET_EXHAUSTED"


# ---- CRE-T012 / AT-009 -------------------------------------------------------------------------------------------
def test_breaker_opens_blocks_during_cooldown_and_probes_in_half_open(env):
    store = CREStore(env / "i.sqlite3")
    br = R.Breaker(store, pol())
    adm = R.RetryAdmission(store, pol())
    calls = 0
    for i in range(50):  # failure storm against one dependency
        if br.allow("mcp", now=1000.0 + i):
            calls += 1
            br.record_failure("mcp", now=1000.0 + i)
    assert calls == br.threshold and br.state("mcp")["state"] == "OPEN"  # throttled after the threshold
    d = adm.admit("x", failure_class="TRANSIENT_DEPENDENCY", replay_class="REPLAY_SAFE", dependency="mcp",
                  breaker=br, now=1100.0)
    assert d.reason == "CIRCUIT_OPEN:mcp"
    later = 1000.0 + br.cooldown + 60
    assert br.allow("mcp", now=later) and not br.allow("mcp", now=later + 1)  # exactly one probe
    br.record_failure("mcp", now=later + 2)
    assert br.state("mcp")["state"] == "OPEN"
    assert br.allow("mcp", now=later + 2 + br.cooldown + 1)
    br.record_success("mcp")
    assert br.state("mcp")["state"] == "CLOSED"
    with sqlite3.connect(store.path) as c:
        hist = [r[0] for r in c.execute("select to_state from cre_breaker_history where dependency='mcp' order by seq")]
    assert hist == ["OPEN", "HALF_OPEN", "OPEN", "HALF_OPEN", "CLOSED"]


# ---- CRE-T013 / AT-010 -------------------------------------------------------------------------------------------
def _grab(args):
    db, owner = args
    from forge_factory.reliability.recovery import ScopeLeases
    from forge_factory.reliability.store import CREStore
    return ScopeLeases(CREStore(db)).acquire("incident:inc-1", owner, 120)


def test_concurrent_ticks_yield_exactly_one_lease_and_fabro_down_uses_the_external_worker(env):
    db = env / "i.sqlite3"
    CREStore(db)
    with mp.get_context("spawn").Pool(6) as pool:
        got = pool.map(_grab, [(db, f"sup-{i}") for i in range(6)])
    assert sum(got) == 1
    st = IncidentStore(db)
    inc, _ = st.open_or_dedup("fabro:READINESS_FAILURE:-:0.4", "fabro", "READINESS_FAILURE")
    st.transition(inc["incident_id"], "TRIAGED")
    marker = env / "worker"
    res = dispatch(st.must(inc["incident_id"]), st, fabro_healthy=False,
                   launcher=[sys.executable, "-c", f"open({str(marker)!r},'w').write('ok')"])
    for _ in range(50):
        if marker.exists():
            break
        time.sleep(0.1)
    assert res["path"] == "external_local_worker" and marker.read_text() == "ok"  # no Fabro needed


# ---- CRE-T014 / AT-011 -------------------------------------------------------------------------------------------
def test_crash_after_side_effect_never_duplicates_a_non_replayable_action(env):
    store = CREStore(env / "i.sqlite3")
    j = R.SideEffectJournal(store, pol())
    effects = []

    def flash_then_crash(key):
        effects.append(key)
        raise KeyboardInterrupt("power loss before acknowledgement")

    with pytest.raises(KeyboardInterrupt):
        j.perform("flash:board-1", "hardware_flash", "REPLAY_SAFE", flash_then_crash)  # policy floor: NON_REPLAYABLE
    again = R.SideEffectJournal(CREStore(env / "i.sqlite3"), pol()).perform(
        "flash:board-1", "hardware_flash", "REPLAY_SAFE", lambda k: effects.append(k))
    assert again["status"] == "REQUIRES_OFFLINE_ATTENTION" and effects == ["flash:board-1"]  # executed exactly once
    calls = []
    with pytest.raises(KeyboardInterrupt):
        j.perform("upload:1", "artifact_upload", "REPLAY_WITH_IDEMPOTENCY_KEY",
                  lambda k: (calls.append(k), (_ for _ in ()).throw(KeyboardInterrupt()))[0])
    ok = j.perform("upload:1", "artifact_upload", "REPLAY_WITH_IDEMPOTENCY_KEY", lambda k: calls.append(k) or "rcpt")
    assert ok["status"] == "DONE" and calls == ["upload:1", "upload:1"]  # same idempotency key on resume
    assert j.perform("upload:1", "artifact_upload", "REPLAY_WITH_IDEMPOTENCY_KEY", lambda k: 1 / 0)["status"] == \
        "ALREADY_DONE"
    with pytest.raises(R.RecoveryError):
        j.perform("x", "op", "MAYBE", lambda k: None)


# ---- CRE-T015 / AT-012 -------------------------------------------------------------------------------------------
class HealthyProbes:
    def all(self, db):
        return [P.Sample("fabro", "fabro_readiness", "HEALTHY"), P.Sample("gpu", "gpu", "UNKNOWN")]


class BrokenProbes:
    def all(self, db):
        return [P.Sample("evidence_store", "evidence_store_writable", "DOWN", fault_type="DISK_PRESSURE",
                         detail="No space left on device")]


def test_100_healthy_polls_with_cre_make_zero_model_calls_and_change_nothing(env):
    S.install_model_guard()
    S.MODEL_CALLS["blocked_attempts"] = 0
    sup = S.Supervisor(S.load_policy(), HealthyProbes(), home=env / "sup", finalizer_enabled=False)
    sup.poll_once()
    db = sup.store.path
    snap = lambda: [sqlite3.connect(db).execute(f"select count(*) from {t}").fetchone()[0]  # noqa: E731
                    for t in ("cre_events", "cre_breakers", "cre_recovery", "cre_failure_observations")]
    before = snap()
    for _ in range(100):
        h = sup.poll_once()
    assert h["model_calls"] == 0 and h["model_tokens"] == 0 and h["status"] == "HEALTHY"
    assert snap() == before == [0, 0, 0, 0]  # closure: healthy polling leaves healthy state unchanged
    assert sup.cre is not None


def test_permanent_unfixable_fault_terminates_in_offline_attention(env):
    sup = S.Supervisor(S.load_policy(), BrokenProbes(), home=env / "sup", finalizer_enabled=False)
    for _ in range(5):
        sup.poll_once()
    [inc] = sup.store.all()  # live finding: the 002 router opened one new incident per poll for an unbroken fault
    assert inc["state"] == "REQUIRES_OFFLINE_ATTENTION"
    ctl = R.RecoveryController(CREStore(sup.store.path), RP.load())
    rec = ctl.get(f"incident:{inc['incident_id']}")
    assert rec["state"] == "REQUIRES_OFFLINE_ATTENTION" and rec["failure_class"] == "INFRASTRUCTURE"
    assert R.Breaker(CREStore(sup.store.path), RP.load()).state("evidence_store")["state"] == "OPEN"


def test_a_cre_failure_never_stops_supervision(env, monkeypatch):
    from forge_factory.reliability import supervisor_hook as H

    monkeypatch.setattr(H.CREHook, "on_poll", lambda *a, **k: 1 / 0)
    sup = S.Supervisor(S.load_policy(), HealthyProbes(), home=env / "sup", finalizer_enabled=False)
    assert sup.poll_once()["status"] == "HEALTHY"
    evs = [json.loads(x) for x in (env / "ev/factory-events.jsonl").read_text().splitlines()]
    assert any("cre hook degraded: ZeroDivisionError" in e["message"] for e in evs)


# ---- CRE-T016 / AT-013 -------------------------------------------------------------------------------------------
def test_fsm_property_every_signal_sequence_terminates_within_the_bound(env):
    store = CREStore(env / "i.sqlite3")
    ctl = R.RecoveryController(store, pol())
    bound = 3 * (ctl.max_retries + ctl.max_repairs) + 4
    rng = random.Random(20261016)
    seen_terminal = set()
    for case in range(300):
        cls = rng.choice(["TRANSIENT_DEPENDENCY", "INFRASTRUCTURE", "PRODUCT_QUALITY", "POLICY_SECURITY", "UNKNOWN"])
        scope = f"s{case}"
        ctl.open(scope, cls)
        for _ in range(200):
            rec = ctl.step(scope, rng.choice(R.SIGNALS), repairable=rng.random() < 0.8)
            if rec["state"] in R.TERMINAL:
                break
        h = ctl.history(scope)
        assert rec["state"] in R.TERMINAL, (cls, h)
        assert len(h) <= bound
        assert all(x["to_state"] in R.TRANSITIONS[x["from_state"]] for x in h)
        retries = sum(x["to_state"] == "RETRY_SCHEDULED" for x in h)
        repairs = sum(x["to_state"] == "REPAIR_DISPATCHED" for x in h)
        assert retries <= ctl.max_retries and repairs <= ctl.max_repairs
        if cls in ("PRODUCT_QUALITY", "POLICY_SECURITY", "UNKNOWN"):
            assert retries == repairs == 0  # never retried or repaired by infrastructure recovery
        assert ctl.step(scope, "fault")["state"] == rec["state"]  # absorbing
        seen_terminal.add(rec["state"])
    assert seen_terminal == R.TERMINAL
    covered = {(x["from_state"], x["to_state"]) for s in range(300) for x in ctl.history(f"s{s}")}
    table = {(a, b) for a, bs in R.TRANSITIONS.items() for b in bs}
    assert len(covered) >= 0.8 * len(table), sorted(table - covered)


def test_invalid_transition_restart_and_store_outage_fail_closed(env):
    db = env / "i.sqlite3"
    ctl = R.RecoveryController(CREStore(db), pol())
    ctl.open("x", "INFRASTRUCTURE")
    with pytest.raises(R.RecoveryError, match="INVALID_TRANSITION"):
        ctl._move(ctl.get("x"), "RECOVERED", "skip the checks")
    for sig in ("fault", "fault", "unhealthy"):
        ctl.step("x", sig)
    restarted = R.RecoveryController(CREStore(db), pol())  # supervisor watchdog restart: budgets continue
    for _ in range(20):
        restarted.step("x", "unhealthy")
    h = restarted.history("x")
    assert sum(x["to_state"] == "REPAIR_DISPATCHED" for x in h) == restarted.max_repairs
    assert restarted.get("x")["state"] == "REQUIRES_OFFLINE_ATTENTION"
    os.chmod(db, 0o444)  # partial store outage: read-only evidence store
    try:
        ro = R.RecoveryController.__new__(R.RecoveryController)
        ro.s, ro.p, ro.max_retries, ro.max_repairs, ro.max_transitions = CREStore.__new__(CREStore), pol(), 2, 2, 20
        ro.s.path = db
        with pytest.raises(sqlite3.OperationalError):
            ro.open("y", "INFRASTRUCTURE")
        assert ro.get("y") is None  # nothing was claimed as recovered
    finally:
        os.chmod(db, 0o644)


def test_unbroken_fault_is_one_incident_but_a_recurrence_after_recovery_is_new(env):
    probes = BrokenProbes()
    sup = S.Supervisor(S.load_policy(), probes, home=env / "sup", finalizer_enabled=False)
    for _ in range(4):
        sup.poll_once()
    assert len(sup.store.all()) == 1
    sup.probes = HealthyProbes()
    for _ in range(S.load_policy()["thresholds"]["stable_polls_for_recovery"]):
        sup.poll_once()
    sup.probes = probes
    sup.poll_once()
    newest, first = sup.store.all()  # newest first
    assert newest["previous_incident_id"] == first["incident_id"]  # recurrence is linked, history kept
