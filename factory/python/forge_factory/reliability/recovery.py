"""CRE D2 (CRE-T011..T015) — provably finite operational recovery. Deterministic, model-free, restart-safe.

* RetryAdmission: only TRANSIENT_DEPENDENCY faults of replayable operations are retried; attempts are counted in an
  append-only ledger (a restart cannot reset them); backoff = min(max, initial*2^(n-1)) with deterministic jitter.
* Breaker: per dependency CLOSED -> OPEN (threshold) -> HALF_OPEN (after cooldown, bounded probes) -> CLOSED|OPEN.
* ScopeLeases: one owner per scope (compare-and-set in one IMMEDIATE transaction; expired leases may be taken over).
* SideEffectJournal: replay classes; NON_REPLAYABLE actions are journaled PENDING before and DONE after; a PENDING
  entry found after a crash is never executed again -> REQUIRES_OFFLINE_ATTENTION (ADR-CRE-003).
* RecoveryController: explicit FSM with a transition table, per-scope retry/repair budgets and a hard transition cap,
  so every admitted incident reaches RECOVERED or REQUIRES_OFFLINE_ATTENTION in a bounded number of steps.
All decisions are CRE events (cre.retry_decided, cre.circuit_*, cre.recovery_*, cre.side_effect).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..common import utc_now
from . import events as E
from .policy import Policy
from .store import CREStore

REPLAY_CLASSES = ("REPLAY_SAFE", "REPLAY_WITH_IDEMPOTENCY_KEY", "COMPENSATABLE", "NON_REPLAYABLE")
TERMINAL = {"RECOVERED", "REQUIRES_OFFLINE_ATTENTION"}
TRANSITIONS: dict[str, set[str]] = {
    "DETECTED": {"CLASSIFIED", "REQUIRES_OFFLINE_ATTENTION"},
    "CLASSIFIED": {"RETRY_ELIGIBLE", "REPAIR_ELIGIBLE", "REQUIRES_OFFLINE_ATTENTION", "RECOVERED"},
    "RETRY_ELIGIBLE": {"RETRY_SCHEDULED", "EXHAUSTED", "RECOVERED"},
    "RETRY_SCHEDULED": {"CHECKING_HEALTH"},
    "REPAIR_ELIGIBLE": {"REPAIR_DISPATCHED", "EXHAUSTED", "RECOVERED"},
    "REPAIR_DISPATCHED": {"CHECKING_HEALTH", "REPAIR_ELIGIBLE"},
    "CHECKING_HEALTH": {"RECOVERED", "RETRY_ELIGIBLE", "REPAIR_ELIGIBLE", "EXHAUSTED"},
    "EXHAUSTED": {"REQUIRES_OFFLINE_ATTENTION"},
    "RECOVERED": set(),
    "REQUIRES_OFFLINE_ATTENTION": set(),
}
SIGNALS = ("fault", "healthy", "unhealthy", "dispatch_ok", "dispatch_failed", "rolled_back", "retry_due")


class RecoveryError(ValueError):
    pass


def _jitter(key: str, attempt: int, ratio: float) -> float:
    u = int(hashlib.sha256(f"{key}|{attempt}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF  # [0,1], reproducible
    return 1.0 + ratio * (2 * u - 1)


@dataclass(frozen=True)
class RetryDecision:
    allowed: bool
    attempt: int
    not_before_epoch: float
    reason: str


class RetryAdmission:
    def __init__(self, store: CREStore, policy: Policy):
        self.s, self.p = store, policy

    def attempts(self, op_key: str) -> int:
        with self.s.conn() as c:
            return int(c.execute("SELECT count(*) FROM cre_retry_attempts WHERE op_key=? AND outcome='ADMITTED'",
                                 (op_key,)).fetchone()[0])

    def backoff(self, op_key: str, attempt: int) -> float:
        r = self.p.data["recovery"]
        base = min(float(r["max_backoff_seconds"]), float(r["initial_backoff_seconds"]) * 2 ** max(0, attempt - 1))
        return round(base * _jitter(op_key, attempt, float(r["jitter_ratio"])), 3)

    def admit(self, op_key: str, *, failure_class: str, replay_class: str, op_class: str = "",
              dependency: str | None = None, breaker: Breaker | None = None, now: float | None = None,
              budget_tokens_left: int | None = None, budget_seconds_left: float | None = None) -> RetryDecision:
        now = time.time() if now is None else now
        r = self.p.data["recovery"]
        n = self.attempts(op_key)
        last = self._last_not_before(op_key)
        reason = ""
        if failure_class != "TRANSIENT_DEPENDENCY":
            reason = f"NOT_RETRYABLE_CLASS:{failure_class}"  # AT-004: deterministic failures are never blind-retried
        elif replay_class not in REPLAY_CLASSES:
            reason = f"UNKNOWN_REPLAY_CLASS:{replay_class}"
        elif replay_class in ("NON_REPLAYABLE", "COMPENSATABLE") or op_class in r["non_replayable_operation_classes"]:
            reason = f"NON_REPLAYABLE:{op_class or replay_class}"
        elif n >= int(r["max_transient_retries_per_operation"]):
            reason = f"RETRY_BUDGET_EXHAUSTED:{n}"
        elif budget_tokens_left is not None and budget_tokens_left <= 0:
            reason = "TOKEN_BUDGET_EXHAUSTED"
        elif budget_seconds_left is not None and budget_seconds_left <= 0:
            reason = "TIME_BUDGET_EXHAUSTED"
        elif dependency and breaker is not None and not breaker.allow(dependency, now):
            reason = f"CIRCUIT_OPEN:{dependency}"
        elif last and now < last:
            reason = f"BACKOFF_PENDING:{round(last - now, 3)}s"
        if reason:
            dec = RetryDecision(False, n, last or now, reason)
            self._log(op_key, n, now, last or now, "DENIED", reason)
            return dec
        nb = now + self.backoff(op_key, n + 1)
        self._log(op_key, n + 1, now, nb, "ADMITTED", f"backoff {round(nb - now, 3)}s")
        return RetryDecision(True, n + 1, nb, "ADMITTED")

    def _last_not_before(self, op_key: str) -> float:
        with self.s.conn() as c:
            row = c.execute("SELECT not_before_epoch FROM cre_retry_attempts WHERE op_key=? AND outcome='ADMITTED' "
                            "ORDER BY attempt DESC LIMIT 1", (op_key,)).fetchone()
        return float(row[0]) if row else 0.0

    def _log(self, op_key: str, attempt: int, now: float, nb: float, outcome: str, detail: str) -> None:
        if outcome == "ADMITTED":  # the ledger holds admitted attempts only (it is the restart-safe budget)
            with self.s.conn() as c:
                c.execute("INSERT INTO cre_retry_attempts(op_key,attempt,decided_at,not_before_epoch,outcome,detail) "
                          "VALUES (?,?,?,?,?,?)", (op_key, attempt, utc_now(), nb, outcome, detail[:200]))
        ev = E.build("cre.retry_decided", f"{op_key}|{outcome}|{attempt}|{detail}", {
            "op_key": op_key[:200], "attempt": attempt, "decision": outcome, "detail": detail[:200]},
            policy_sha256=self.p.sha256, correlation_id=op_key[:120])
        E.record(self.s, ev)


class Breaker:
    def __init__(self, store: CREStore, policy: Policy):
        self.s, self.p = store, policy
        r = policy.data["recovery"]
        self.threshold, self.cooldown = int(r["breaker_failure_threshold"]), float(r["breaker_cooldown_seconds"])
        self.probes = int(r["breaker_half_open_probes"])

    def state(self, dep: str) -> dict:
        with self.s.conn() as c:
            row = c.execute("SELECT * FROM cre_breakers WHERE dependency=?", (dep,)).fetchone()
        return dict(row) if row else {"dependency": dep, "state": "CLOSED", "failures": 0, "opened_at_epoch": None,
                                      "half_open_probes": 0}

    def _put(self, st: dict, to: str, reason: str) -> None:
        frm = self.state(st["dependency"])["state"]
        with self.s.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT INTO cre_breakers(dependency,state,failures,opened_at_epoch,half_open_probes,updated_at) "
                      "VALUES (?,?,?,?,?,?) ON CONFLICT(dependency) DO UPDATE SET state=excluded.state, "
                      "failures=excluded.failures, opened_at_epoch=excluded.opened_at_epoch, "
                      "half_open_probes=excluded.half_open_probes, updated_at=excluded.updated_at",
                      (st["dependency"], to, st["failures"], st["opened_at_epoch"], st["half_open_probes"], utc_now()))
            if frm != to:
                c.execute("INSERT INTO cre_breaker_history(dependency,from_state,to_state,at,reason) VALUES (?,?,?,?,?)",
                          (st["dependency"], frm, to, utc_now(), reason))
            c.execute("COMMIT")
        if frm != to:
            typ = {"OPEN": "cre.circuit_opened", "HALF_OPEN": "cre.circuit_half_open", "CLOSED": "cre.circuit_closed"}[to]
            with self.s.conn() as c:
                seq = c.execute("SELECT max(seq) FROM cre_breaker_history WHERE dependency=?",
                                (st["dependency"],)).fetchone()[0]
            E.record(self.s, E.build(typ, f"{st['dependency']}|{seq}", {"dependency": st["dependency"], "to": to,
                                                                        "reason": reason[:160]},
                                     policy_sha256=self.p.sha256, correlation_id=f"breaker:{st['dependency']}"))

    def allow(self, dep: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        st = self.state(dep)
        if st["state"] == "CLOSED":
            return True
        if st["state"] == "OPEN":
            if now - float(st["opened_at_epoch"] or 0) < self.cooldown:
                return False  # AT-009: no calls during cooldown
            st["half_open_probes"] = 0
            self._put(st, "HALF_OPEN", "cooldown elapsed")
            st = self.state(dep)
        if st["half_open_probes"] >= self.probes:
            return False
        st["half_open_probes"] += 1
        self._put(st, "HALF_OPEN", "probe admitted")
        return True

    def record_success(self, dep: str) -> None:
        st = self.state(dep)
        if st["state"] == "CLOSED" and not st["failures"]:
            return  # closure: a healthy observation of a healthy dependency changes nothing (no write)
        st.update(failures=0, opened_at_epoch=None, half_open_probes=0)
        self._put(st, "CLOSED", "success")

    def record_failure(self, dep: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        st = self.state(dep)
        st["failures"] = int(st["failures"]) + 1
        if st["state"] == "OPEN":
            self._put(st, "OPEN", "failure while open (cooldown not restarted)")
        elif st["state"] == "HALF_OPEN" or st["failures"] >= self.threshold:
            st.update(opened_at_epoch=now, half_open_probes=0)
            self._put(st, "OPEN", f"{st['failures']} consecutive failures")
        else:
            self._put(st, st["state"], "failure counted")


class ScopeLeases:
    def __init__(self, store: CREStore):
        self.s = store

    def acquire(self, scope: str, owner: str, ttl: float, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self.s.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT owner, expires_epoch FROM cre_scope_leases WHERE scope=?", (scope,)).fetchone()
            ok = row is None or row[0] == owner or float(row[1]) <= now
            if ok:
                c.execute("INSERT INTO cre_scope_leases VALUES (?,?,?) ON CONFLICT(scope) DO UPDATE SET "
                          "owner=excluded.owner, expires_epoch=excluded.expires_epoch", (scope, owner, now + ttl))
            c.execute("COMMIT")
        return ok

    def release(self, scope: str, owner: str) -> None:
        with self.s.conn() as c:
            c.execute("DELETE FROM cre_scope_leases WHERE scope=? AND owner=?", (scope, owner))


class DispatchAdmission:
    """CRE-T044 (CRE-FR-005): admission of 002 repair dispatch, durable across supervisor restarts.

    Keyed by the incident FINGERPRINT (a recurrence opens a new 002 incident with attempts=0; the CRE budget does
    not reset): at most `max_repair_attempts_per_incident` dispatches per fingerprint per RECURRENCE_WINDOW_S,
    at most `max_repairs_per_hour` factory-wide, and a deterministic jittered exponential backoff between attempts
    on the same fingerprint. Enforcing (PILOT/ACTIVE) ledger rows are `ADMITTED`; OBSERVE_ONLY records the same
    decisions as `SHADOW_ADMITTED` and never filters (002 behaviour unchanged).
    """

    RECURRENCE_WINDOW_S = 86400.0

    def __init__(self, store: CREStore, policy: Policy):
        self.s, self.p, self.r = store, policy, RetryAdmission(store, policy)
        self.enforce = policy.mode in ("PILOT", "ACTIVE")
        self.outcome = "ADMITTED" if self.enforce else "SHADOW_ADMITTED"

    def _rows(self, key: str | None, since: str = "") -> list[sqlite3.Row]:
        """Ledger rows of this mode: one fingerprint (key) or every repair dispatch (key None) decided >= since."""
        with self.s.conn() as c:
            if key is not None:
                return list(c.execute("SELECT * FROM cre_retry_attempts WHERE outcome=? AND op_key=? "
                                      "AND decided_at >= ? ORDER BY attempt", (self.outcome, key, since)))
            return list(c.execute("SELECT * FROM cre_retry_attempts WHERE outcome=? AND op_key LIKE "
                                  "'repair_dispatch:%' AND decided_at >= ? ORDER BY seq", (self.outcome, since)))

    clock = staticmethod(time.time)  # injectable for tests

    def admit(self, fingerprint: str, now: float | None = None) -> RetryDecision:
        now = self.clock() if now is None else now
        r = self.p.data["recovery"]
        key = f"repair_dispatch:{fingerprint}"
        mine = self._rows(key)
        since = _iso(now - self.RECURRENCE_WINDOW_S)
        recent = [x for x in mine if x["decided_at"] >= since]
        hour = self._rows(None, _iso(now - 3600))
        last_nb = float(mine[-1]["not_before_epoch"]) if mine else 0.0
        reason = ""
        if len(recent) >= int(r["max_repair_attempts_per_incident"]):
            reason = f"REPAIR_BUDGET_EXHAUSTED:{len(recent)}"
        elif len(hour) >= int(r["max_repairs_per_hour"]):
            reason = f"HOURLY_REPAIR_QUOTA:{len(hour)}"
        elif now < last_nb:
            reason = f"BACKOFF_PENDING:{round(last_nb - now, 3)}s"
        attempt = (int(mine[-1]["attempt"]) if mine else 0) + 1
        if reason:
            if self.enforce or not reason.startswith("BACKOFF_PENDING"):  # shadow: no per-poll backoff noise
                self._event(key, attempt - 1, f"{'' if self.enforce else 'SHADOW_'}DENIED", reason)
            return RetryDecision(False, attempt - 1, last_nb or now, reason)
        nb = now + self.r.backoff(key, len(recent) + 1)
        with self.s.conn() as c:
            c.execute("INSERT INTO cre_retry_attempts(op_key,attempt,decided_at,not_before_epoch,outcome,detail) "
                      "VALUES (?,?,?,?,?,?)", (key, attempt, _iso(now), nb, self.outcome,
                                               f"backoff {round(nb - now, 3)}s"))
        self._event(key, attempt, self.outcome, f"next not before +{round(nb - now, 3)}s")
        return RetryDecision(True, attempt, nb, self.outcome)

    def _event(self, key: str, attempt: int, decision: str, detail: str) -> None:
        E.record(self.s, E.build("cre.retry_decided", f"{key}|{decision}|{attempt}|{detail}", {
            "op_key": key[:200], "attempt": attempt, "decision": decision, "detail": detail[:200]},
            policy_sha256=self.p.sha256, correlation_id=key[:120]))


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class SideEffectJournal:
    def __init__(self, store: CREStore, policy: Policy):
        self.s, self.p = store, policy

    def _last(self, key: str) -> dict | None:
        with self.s.conn() as c:
            row = c.execute("SELECT * FROM cre_side_effects WHERE idem_key=? ORDER BY seq DESC LIMIT 1", (key,)).fetchone()
        return dict(row) if row else None

    def _append(self, key: str, op_class: str, replay: str, status: str, receipt: Any = None) -> None:
        with self.s.conn() as c:
            c.execute("INSERT INTO cre_side_effects(idem_key,op_class,replay_class,status,at,receipt) VALUES (?,?,?,?,?,?)",
                      (key, op_class, replay, status, utc_now(), json.dumps(receipt)[:2000] if receipt is not None else None))
        E.record(self.s, E.build("cre.side_effect", f"{key}|{status}|{utc_now()}", {
            "op_class": op_class, "replay_class": replay, "state": status}, policy_sha256=self.p.sha256,
            correlation_id=key[:120]))

    def replay_class(self, op_class: str, declared: str) -> str:
        if op_class in self.p.data["recovery"]["non_replayable_operation_classes"]:
            return "NON_REPLAYABLE"  # the policy floor wins over any declaration
        if declared not in REPLAY_CLASSES:
            raise RecoveryError(f"UNKNOWN_REPLAY_CLASS:{declared}")
        return declared

    def decide(self, key: str, op_class: str, declared: str) -> tuple[str, str, dict | None]:
        """Pure decision from the journal: (EXECUTE | ALREADY_DONE | REQUIRES_OFFLINE_ATTENTION, replay class, last)."""
        replay = self.replay_class(op_class, declared)
        last = self._last(key)
        if last and last["status"] == "DONE" and replay != "REPLAY_SAFE":
            return "ALREADY_DONE", replay, last
        # AT-011: a PENDING (crash) or FAILED (partial) outcome is unknown -> never replayed for these classes
        if last and last["status"] in ("PENDING", "FAILED") and replay in ("NON_REPLAYABLE", "COMPENSATABLE"):
            return "REQUIRES_OFFLINE_ATTENTION", replay, last
        if last and last["status"] == "REQUIRES_OFFLINE_ATTENTION":
            return "REQUIRES_OFFLINE_ATTENTION", replay, last
        return "EXECUTE", replay, last

    def execute(self, key: str, op_class: str, replay: str, fn: Callable[[str], Any]) -> Any:
        self._append(key, op_class, replay, "PENDING")
        try:
            receipt = fn(key)  # crash here => PENDING stays; the next call decides by replay class
        except Exception as exc:  # a raised error is a known (possibly partial) failure, recorded as such
            self._append(key, op_class, replay, "FAILED", {"error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            raise
        self._append(key, op_class, replay, "DONE", receipt)
        return receipt

    def perform(self, key: str, op_class: str, declared: str, fn: Callable[[str], Any]) -> dict:
        decision, replay, last = self.decide(key, op_class, declared)
        if decision == "ALREADY_DONE":
            return {"executed": False, "status": "ALREADY_DONE", "receipt": json.loads(last["receipt"] or "null")}
        if decision == "REQUIRES_OFFLINE_ATTENTION":
            if last["status"] != "REQUIRES_OFFLINE_ATTENTION":
                self._append(key, op_class, replay, "REQUIRES_OFFLINE_ATTENTION")
            return {"executed": False, "status": "REQUIRES_OFFLINE_ATTENTION", "receipt": None}
        return {"executed": True, "status": "DONE", "receipt": self.execute(key, op_class, replay, fn)}


class RecoveryController:
    """Per-scope FSM. step() is a pure decision on (state, signal, budgets) followed by a durable transition."""

    def __init__(self, store: CREStore, policy: Policy):
        self.s, self.p = store, policy
        r = policy.data["recovery"]
        self.max_retries = int(r["max_transient_retries_per_operation"])
        self.max_repairs = int(r["max_repair_attempts_per_incident"])
        self.max_transitions = 3 * (self.max_retries + self.max_repairs) + 8  # hard bound (finite even if misused)

    def get(self, scope: str) -> dict | None:
        with self.s.conn() as c:
            row = c.execute("SELECT * FROM cre_recovery WHERE scope=?", (scope,)).fetchone()
        return dict(row) if row else None

    def history(self, scope: str) -> list[dict]:
        with self.s.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM cre_recovery_history WHERE scope=? ORDER BY seq", (scope,))]

    def open(self, scope: str, failure_class: str, fingerprint: str | None = None) -> dict:
        with self.s.conn() as c:
            c.execute("INSERT OR IGNORE INTO cre_recovery(scope,fingerprint,failure_class,state,attempts,opened_at,"
                      "updated_at) VALUES (?,?,?,?,?,?,?)", (scope, fingerprint, failure_class, "DETECTED", 0, utc_now(),
                                                           utc_now()))
        return self.get(scope)  # type: ignore[return-value]

    def _move(self, rec: dict, to: str, reason: str, count: bool = False) -> dict:
        frm = rec["state"]
        if to not in TRANSITIONS[frm]:
            raise RecoveryError(f"INVALID_TRANSITION:{frm}->{to}")
        with self.s.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            cur = c.execute("SELECT state FROM cre_recovery WHERE scope=?", (rec["scope"],)).fetchone()[0]
            if cur != frm:  # another controller moved it: no lost update
                c.execute("ROLLBACK")
                raise RecoveryError(f"CONCURRENT_UPDATE:{rec['scope']}")
            c.execute("UPDATE cre_recovery SET state=?, attempts=attempts+?, updated_at=?, terminal_reason=? WHERE scope=?",
                      (to, 1 if count else 0, utc_now(), reason if to in TERMINAL else None, rec["scope"]))
            c.execute("INSERT INTO cre_recovery_history(scope,from_state,to_state,at,reason) VALUES (?,?,?,?,?)",
                      (rec["scope"], frm, to, utc_now(), reason[:200]))
            n = c.execute("SELECT count(*) FROM cre_recovery_history WHERE scope=?", (rec["scope"],)).fetchone()[0]
            c.execute("COMMIT")
        E.record(self.s, E.build("cre.recovery_terminal" if to in TERMINAL else "cre.recovery_transition",
                                 f"{rec['scope']}|{n}", {"from": frm, "to": to, "reason": reason[:160],
                                                         "failure_class": rec["failure_class"]},
                                 policy_sha256=self.p.sha256, correlation_id=rec["scope"][:120],
                                 fingerprint=rec.get("fingerprint")))
        return self.get(rec["scope"])  # type: ignore[return-value]

    def _counts(self, scope: str) -> tuple[int, int, int]:
        h = self.history(scope)
        return (sum(x["to_state"] == "RETRY_SCHEDULED" for x in h), sum(x["to_state"] == "REPAIR_DISPATCHED" for x in h),
                len(h))

    def step(self, scope: str, signal: str, *, repairable: bool = True) -> dict:
        if signal not in SIGNALS:
            raise RecoveryError(f"UNKNOWN_SIGNAL:{signal}")
        rec = self.get(scope)
        if rec is None:
            raise RecoveryError(f"UNKNOWN_SCOPE:{scope}")
        st = rec["state"]
        if st in TERMINAL:
            return rec  # terminal states are absorbing
        retries, repairs, n = self._counts(scope)
        if n >= self.max_transitions:  # safety net; the budgets below already bound every path
            for to in ("EXHAUSTED", "REQUIRES_OFFLINE_ATTENTION", "CHECKING_HEALTH"):
                if to in TRANSITIONS[st]:
                    return self._move(rec, to, f"TRANSITION_CAP:{n}")
        cls = rec["failure_class"]
        if st == "DETECTED":
            return self._move(rec, "CLASSIFIED", f"class {cls}")
        if st == "CLASSIFIED":
            if signal == "healthy":
                return self._move(rec, "RECOVERED", "healthy before any action")
            if cls == "TRANSIENT_DEPENDENCY":
                return self._move(rec, "RETRY_ELIGIBLE", "transient")
            if cls == "INFRASTRUCTURE" and repairable:
                return self._move(rec, "REPAIR_ELIGIBLE", "infrastructure")
            return self._move(rec, "REQUIRES_OFFLINE_ATTENTION", f"no automatic route for {cls}")
        if st == "RETRY_ELIGIBLE":
            if signal == "healthy":
                return self._move(rec, "RECOVERED", "healthy")
            if retries >= self.max_retries:
                return self._move(rec, "EXHAUSTED", f"retry budget {retries}/{self.max_retries}")
            return self._move(rec, "RETRY_SCHEDULED", f"retry {retries + 1}/{self.max_retries}", count=True)
        if st == "RETRY_SCHEDULED":
            return self._move(rec, "CHECKING_HEALTH", "retry executed")
        if st == "REPAIR_ELIGIBLE":
            if signal == "healthy":
                return self._move(rec, "RECOVERED", "healthy")
            if repairs >= self.max_repairs:
                return self._move(rec, "EXHAUSTED", f"repair budget {repairs}/{self.max_repairs}")
            return self._move(rec, "REPAIR_DISPATCHED", f"repair {repairs + 1}/{self.max_repairs}", count=True)
        if st == "REPAIR_DISPATCHED":
            if signal in ("dispatch_failed", "rolled_back"):
                return self._move(rec, "REPAIR_ELIGIBLE", signal)
            return self._move(rec, "CHECKING_HEALTH", "repair finished")
        if st == "CHECKING_HEALTH":
            if signal == "healthy":
                return self._move(rec, "RECOVERED", "health verified")
            if cls == "TRANSIENT_DEPENDENCY":
                return self._move(rec, "RETRY_ELIGIBLE", "still unhealthy") if retries < self.max_retries else \
                    self._move(rec, "EXHAUSTED", f"retry budget {retries}/{self.max_retries}")
            return self._move(rec, "REPAIR_ELIGIBLE", "still unhealthy") if repairs < self.max_repairs else \
                self._move(rec, "EXHAUSTED", f"repair budget {repairs}/{self.max_repairs}")
        if st == "EXHAUSTED":
            return self._move(rec, "REQUIRES_OFFLINE_ATTENTION", "budget exhausted")
        raise RecoveryError(f"UNHANDLED_STATE:{st}")  # pragma: no cover - table and code are kept in sync by tests

    def drive_to(self, scope: str, target: str, reason: str) -> dict:
        """Observe-only mirror of a terminal 002 incident: shortest valid path to RECOVERED/REQUIRES_OFFLINE_ATTENTION."""
        if target not in TERMINAL:
            raise RecoveryError(f"NOT_TERMINAL:{target}")
        for _ in range(4):
            rec = self.get(scope)
            if rec is None or rec["state"] in TERMINAL:
                return rec  # type: ignore[return-value]
            st = rec["state"]
            nxt = target if target in TRANSITIONS[st] else (
                "EXHAUSTED" if "EXHAUSTED" in TRANSITIONS[st] else "CLASSIFIED" if st == "DETECTED" else "CHECKING_HEALTH")
            self._move(rec, nxt, f"mirror 002: {reason}"[:200])
        return self.get(scope)  # type: ignore[return-value]
