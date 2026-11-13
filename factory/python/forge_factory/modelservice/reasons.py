"""Machine reasons of the model channel, factory side (feature 017, FR-005, contracts/model-channel.md).

Every non-success outcome of a model call maps to exactly one reason, and every reason to one behaviour. The
factory never turns a refusal or an outage into a model failure, and never records a lost call as a success.
"""
from __future__ import annotations

import ssl
from enum import StrEnum

import httpx


class Reason(StrEnum):
    CREDENTIAL_REFUSED = "credential_refused"
    SHARE_EXHAUSTED = "share_exhausted"
    CONTEXT_EXCEEDED = "context_exceeded"
    IDENTITY_CHANGED = "identity_changed"
    MODEL_NOT_OFFERED = "model_not_offered"
    SERVICE_UNREACHABLE = "service_unreachable"
    CHANNEL_INTERRUPTED = "channel_interrupted"
    OUTCOME_UNKNOWN = "outcome_unknown"


BEHAVIOUR = {
    Reason.CREDENTIAL_REFUSED: "block",       # incident; no blind retry
    Reason.IDENTITY_CHANGED: "block",         # never continue on a silently different model
    Reason.MODEL_NOT_OFFERED: "block",        # pre-run check should have caught it
    Reason.SHARE_EXHAUSTED: "bounded_wait",   # the service's share or a swap: wait up to queue_wait_max_s
    Reason.SERVICE_UNREACHABLE: "outage_wait",
    Reason.CHANNEL_INTERRUPTED: "outage_wait",
    Reason.OUTCOME_UNKNOWN: "recovery",       # recorded as unknown; the normal bounded recovery decides
    Reason.CONTEXT_EXCEEDED: "repartition",   # refused before sending; never truncated
}

_BY_FORGE_REASON = {
    "credential_refused": Reason.CREDENTIAL_REFUSED, "share_exhausted": Reason.SHARE_EXHAUSTED,
    "queue_timeout": Reason.SHARE_EXHAUSTED, "context_exceeded": Reason.CONTEXT_EXCEEDED,
    "identity_mismatch": Reason.IDENTITY_CHANGED, "model_not_offered": Reason.MODEL_NOT_OFFERED,
    "model_unavailable": Reason.SERVICE_UNREACHABLE,
}


def _tls(exc: BaseException) -> bool:
    seen, cur = set(), exc
    while cur is not None and id(cur) not in seen:
        if isinstance(cur, ssl.SSLError):
            return True
        seen.add(id(cur))
        cur = cur.__cause__ or cur.__context__
    return False


def classify(*, status: int | None = None, forge_reason: str | None = None, exc: BaseException | None = None,
             sent: bool = False) -> Reason | None:
    """The reason for one call outcome, or None for a normal answer (or a 4xx the contract does not name, which the
    caller handles as an ordinary request error)."""
    if exc is not None:
        if _tls(exc):
            return Reason.CHANNEL_INTERRUPTED
        if isinstance(exc, httpx.ConnectError | httpx.ConnectTimeout | httpx.PoolTimeout):
            return Reason.SERVICE_UNREACHABLE
        if isinstance(exc, httpx.TransportError | httpx.TimeoutException):
            return Reason.OUTCOME_UNKNOWN if sent else Reason.CHANNEL_INTERRUPTED
        return Reason.OUTCOME_UNKNOWN if sent else Reason.SERVICE_UNREACHABLE
    if status is None or 200 <= status < 300:
        return None
    if forge_reason in _BY_FORGE_REASON:
        return _BY_FORGE_REASON[forge_reason]
    if status in (401, 403):
        return Reason.CREDENTIAL_REFUSED
    if status == 429:
        return Reason.SHARE_EXHAUSTED
    if status == 409:
        return Reason.IDENTITY_CHANGED
    if status >= 500:
        return Reason.SERVICE_UNREACHABLE
    return None


def behaviour(reason: Reason) -> str:
    return BEHAVIOUR[reason]
