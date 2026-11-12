"""Known provider usage reuses unspent request reservations inside a fixed job envelope."""

# ruff: noqa: F811
import io
import json
import urllib.error

import pytest
from forge_factory.afo.durable import Refused, canonical
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.lrtx import structured
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401


def request(p, name):
    return p.ledger.reserve_request(
        "mission-test", p.ctx.job_id, name, body_sha256="a" * 64, input_tokens=6000, output_cap=6000, authorize=lambda: True
    )


def active(p):
    Executions(p.store).reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)


def test_complete_usage_allows_next_request_without_reducing_mission_charge(protocol):
    p = protocol
    active(p)
    before = p.ledger.snapshot("mission-test")["charged_tokens"]
    request(p, "first")
    first = p.ledger.reconcile_request(
        "first", input_tokens=1000, output_tokens=1000, quiescent=True, evidence_ref="provider:complete"
    )
    assert first["charge"] == 2000 and first["reserved_tokens"] == 12000
    assert p.ledger.snapshot("mission-test")["charged_tokens"] == before == 16000
    request(p, "second")
    assert p.ledger.snapshot("mission-test")["requests"] == 2


def test_unknown_or_unfinished_usage_stays_reserved(protocol):
    p = protocol
    active(p)
    request(p, "unknown")
    rec = p.ledger.reconcile_request("unknown", quiescent=True, evidence_ref="kernel-ended")
    assert rec["charge"] == 12000 and rec["reported_tokens"] is None
    with pytest.raises(Refused, match="JOB_TOKEN_ENVELOPE_EXHAUSTED"):
        request(p, "next")


def test_legacy_request_charge_is_not_migrated_or_refunded(protocol):
    p = protocol
    active(p)
    rec = request(p, "legacy")
    rec.pop("accounting")
    with p.store.tx() as c:
        c.execute("UPDATE afo_request_ledger SET record=? WHERE request_id=?", (canonical(rec).decode(), "legacy"))
    out = p.ledger.reconcile_request("legacy", input_tokens=1000, output_tokens=1000, quiescent=True, evidence_ref="complete")
    assert out["charge"] == 12000


def test_late_report_retains_quiescence_and_highest_reported_spend(protocol):
    p = protocol
    active(p)
    request(p, "late")
    p.ledger.reconcile_request("late", input_tokens=1000, output_tokens=1000, quiescent=True, evidence_ref="complete")
    out = p.ledger.reconcile_request("late", input_tokens=500, output_tokens=500)
    assert out["state"] == "QUIESCENT" and out["reported_tokens"] == out["charge"] == 2000
    out = p.ledger.reconcile_request("late", input_tokens=20000, output_tokens=1000)
    assert p.ledger.snapshot("mission-test")["charged_tokens"] == out["charge"] == 21000
    with pytest.raises(Refused, match="JOB_TOKEN_ENVELOPE_EXHAUSTED"):
        request(p, "overrun")


def test_structured_refusal_preserves_bounded_typed_reason_without_body_leak(monkeypatch):
    packet = dict(model="fixture", _messages=[], output_reserve=20, output_schema={})
    body = json.dumps({"error": {"type": "JOB_TOKEN_ENVELOPE_EXHAUSTED", "message": "PRIVATE_BODY"}}).encode()

    def denied(*a, **kw):
        raise urllib.error.HTTPError("http://localhost", 429, "refused", {}, io.BytesIO(body))

    monkeypatch.setattr(structured.urllib.request, "urlopen", denied)
    result = structured.call(packet, url="http://localhost")
    assert result["errors"] == ["CALL_REFUSED:JOB_TOKEN_ENVELOPE_EXHAUSTED"]
    assert "PRIVATE_BODY" not in str(result)
