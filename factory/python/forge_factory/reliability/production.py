"""CRE-T045 (CRE-FR-007) — production side effects go through the CRE side-effect journal.

| op_class          | site                                         | replay class                | idempotency key        |
|-------------------|----------------------------------------------|-----------------------------|------------------------|
| archive_write     | release/finalize.py seals the package        | REPLAY_WITH_IDEMPOTENCY_KEY | archive_write:<run>    |
| infra_cas_switch  | repair/promotion.py switches infra `main`    | COMPENSATABLE (reverse CAS) | infra_cas_switch:<att> |
| infra_cas_rollback| repair/promotion.py compensates the switch   | REPLAY_WITH_IDEMPOTENCY_KEY | infra_cas_rollback:<att>|
| workorder_launch  | workorder.py starts the Fabro run            | REPLAY_WITH_IDEMPOTENCY_KEY | workorder_launch:<wo>  |

Mode: PILOT/ACTIVE enforce the journal decision (ALREADY_DONE -> no second execution, unknown outcome of a
COMPENSATABLE/NON_REPLAYABLE action -> REQUIRES_OFFLINE_ATTENTION, CRE DB unavailable -> fail closed).
OBSERVE_ONLY records the same PENDING/DONE/FAILED entries and the would-be decision (`cre.side_effect` event with
`shadow_decision`), but keeps the 002 behaviour: the action runs, and a CRE error never blocks production (audit WARN).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..events.emit import emit

REPLAY = {"archive_write": "REPLAY_WITH_IDEMPOTENCY_KEY", "infra_cas_switch": "COMPENSATABLE",
          "infra_cas_rollback": "REPLAY_WITH_IDEMPOTENCY_KEY", "workorder_launch": "REPLAY_WITH_IDEMPOTENCY_KEY"}


class JournalRefused(RuntimeError):
    def __init__(self, status: str, key: str):
        super().__init__(f"{status}:{key}")
        self.status, self.key = status, key


def enforcing() -> bool:
    """True in PILOT/ACTIVE (journal decisions and idempotency checks apply); False when observe-only/unreadable."""
    from .policy import load

    try:
        return load().mode in ("PILOT", "ACTIVE")
    except Exception:  # noqa: BLE001
        return False


def guarded(op_class: str, key: str, fn: Callable[[str], Any]) -> dict:
    """Run a production side effect through the journal. Returns {executed, status, receipt, mode}."""
    from . import events as E
    from .policy import load
    from .recovery import SideEffectJournal
    from .store import CREStore

    try:
        pol = load()
        enforce = pol.mode in ("PILOT", "ACTIVE")
    except Exception as exc:  # noqa: BLE001 - an unreadable CRE policy must not change 002 behaviour
        emit("audit", "WARN", f"cre journal unavailable ({type(exc).__name__}); {op_class} unjournaled",
             correlation_id=key[:120])
        return {"executed": True, "status": "UNJOURNALED", "receipt": fn(key), "mode": "UNKNOWN"}
    if enforce:  # fail closed: a CRE store error propagates before the side effect runs
        j = SideEffectJournal(CREStore(), pol)
        return {**j.perform(key, op_class, REPLAY[op_class], fn), "mode": pol.mode}

    def contained(what: str, f: Callable[[], Any]) -> bool:
        try:
            f()
            return True
        except Exception as exc:  # noqa: BLE001 - observe-only: a CRE error never blocks the 002 action
            emit("audit", "WARN", f"cre journal degraded at {what} ({type(exc).__name__}); {op_class} continues",
                 correlation_id=key[:120])
            return False

    st: dict = {}

    def prepare() -> None:
        store = CREStore()
        j = SideEffectJournal(store, pol)
        st["j"] = j
        st["decision"], st["replay"], _ = j.decide(key, op_class, REPLAY[op_class])
        if st["decision"] != "EXECUTE":
            E.record(store, E.build("cre.side_effect", f"{key}|shadow|{st['decision']}", {
                "op_class": op_class, "replay_class": st["replay"], "state": "SHADOW",
                "shadow_decision": st["decision"]}, policy_sha256=pol.sha256, correlation_id=key[:120]))
        j._append(key, op_class, st["replay"], "PENDING")

    journaled = contained("pending", prepare)
    try:
        receipt = fn(key)
    except Exception as exc:
        err = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        if journaled:
            contained("failed", lambda: st["j"]._append(key, op_class, st["replay"], "FAILED", err))
        raise
    if journaled:
        journaled = contained("done", lambda: st["j"]._append(key, op_class, st["replay"], "DONE", receipt))
    return {"executed": True, "status": "DONE" if journaled else "UNJOURNALED", "receipt": receipt,
            "mode": pol.mode, "shadow_decision": st.get("decision")}
