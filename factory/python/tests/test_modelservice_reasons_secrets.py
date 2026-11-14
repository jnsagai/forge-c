"""Feature 017 T006: reason mapping of the model channel (contracts/model-channel.md) and the private secret resolver."""
import os

import httpx
import pytest
from forge_factory.modelservice import reasons as R
from forge_factory.modelservice import secrets as S

REQ = httpx.Request("POST", "http://svc/v1/chat/completions")


@pytest.mark.parametrize("status,forge_reason,want", [
    (401, None, R.Reason.CREDENTIAL_REFUSED), (403, "credential_refused", R.Reason.CREDENTIAL_REFUSED),
    (429, "share_exhausted", R.Reason.SHARE_EXHAUSTED), (429, "queue_timeout", R.Reason.SHARE_EXHAUSTED),
    (429, None, R.Reason.SHARE_EXHAUSTED), (400, "context_exceeded", R.Reason.CONTEXT_EXCEEDED),
    (409, "identity_mismatch", R.Reason.IDENTITY_CHANGED), (404, "model_not_offered", R.Reason.MODEL_NOT_OFFERED),
    (503, "model_unavailable", R.Reason.SERVICE_UNREACHABLE), (500, None, R.Reason.SERVICE_UNREACHABLE),
    (502, None, R.Reason.SERVICE_UNREACHABLE), (200, None, None), (400, None, None), (404, None, None),
])
def test_status_table(status, forge_reason, want):
    assert R.classify(status=status, forge_reason=forge_reason) is want


def test_exceptions_before_and_after_send():
    assert R.classify(exc=httpx.ConnectError("x", request=REQ)) is R.Reason.SERVICE_UNREACHABLE
    assert R.classify(exc=httpx.ConnectTimeout("x", request=REQ)) is R.Reason.SERVICE_UNREACHABLE
    import ssl
    tls = httpx.ConnectError("tls", request=REQ)
    tls.__cause__ = ssl.SSLError("certificate verify failed")
    assert R.classify(exc=tls) is R.Reason.CHANNEL_INTERRUPTED
    # the request reached the service and the connection was lost: outcome unknown, never success or zero cost
    for exc in (httpx.ReadError("x", request=REQ), httpx.RemoteProtocolError("x", request=REQ),
                httpx.ReadTimeout("x", request=REQ)):
        assert R.classify(exc=exc, sent=True) is R.Reason.OUTCOME_UNKNOWN
    assert R.classify(exc=httpx.ReadError("x", request=REQ), sent=False) is R.Reason.CHANNEL_INTERRUPTED


def test_behaviour_per_reason():
    assert R.behaviour(R.Reason.SHARE_EXHAUSTED) == "bounded_wait"
    assert R.behaviour(R.Reason.SERVICE_UNREACHABLE) == "outage_wait"
    assert R.behaviour(R.Reason.CHANNEL_INTERRUPTED) == "outage_wait"
    for r in (R.Reason.CREDENTIAL_REFUSED, R.Reason.IDENTITY_CHANGED, R.Reason.MODEL_NOT_OFFERED):
        assert R.behaviour(r) == "block"
    assert R.behaviour(R.Reason.OUTCOME_UNKNOWN) == "recovery"
    assert R.behaviour(R.Reason.CONTEXT_EXCEEDED) == "repartition"
    assert {r.value for r in R.Reason} >= {"credential_refused", "share_exhausted", "context_exceeded", "identity_changed",
                                           "service_unreachable", "channel_interrupted", "outcome_unknown",
                                           "model_not_offered"}


def _secrets(tmp_path, mode=0o600, text="forge-qual=KEY-SECRET-123\n# comment\nengine-internal = ENG-456\n"):
    p = tmp_path / "model-service.secrets"
    p.write_text(text)
    os.chmod(p, mode)
    return p


def test_secret_resolver_reads_private_file_only(tmp_path, monkeypatch):
    p = _secrets(tmp_path)
    store = S.SecretFile(p)
    sec = store.get("forge-qual")
    assert sec.reveal() == "KEY-SECRET-123" and store.get("engine-internal").reveal() == "ENG-456"
    assert "KEY-SECRET-123" not in repr(sec) and "KEY-SECRET-123" not in str(sec) and "forge-qual" in repr(sec)
    with pytest.raises(S.SecretError) as e:
        store.get("missing")
    assert "KEY-SECRET-123" not in str(e.value)
    monkeypatch.setenv("FORGE_MODEL_SERVICE_SECRETS", str(p))
    assert S.resolve("forge-qual").reveal() == "KEY-SECRET-123"


@pytest.mark.parametrize("mode", [0o640, 0o604, 0o644, 0o660])
def test_secret_resolver_refuses_shared_files(tmp_path, mode):
    p = _secrets(tmp_path, mode)
    with pytest.raises(S.SecretError, match="SECRETS_FILE_NOT_PRIVATE"):
        S.SecretFile(p)


def test_secret_resolver_refuses_missing_and_malformed(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGE_MODEL_SERVICE_SECRETS", raising=False)
    with pytest.raises(S.SecretError, match="SECRETS_FILE_UNSET"):
        S.resolve("x")
    with pytest.raises(S.SecretError, match="SECRETS_FILE_MISSING"):
        S.SecretFile(tmp_path / "nope")
    p = _secrets(tmp_path, text="no-equals-sign VALUE-789\n")
    with pytest.raises(S.SecretError, match="SECRETS_FILE_MALFORMED:1") as e:
        S.SecretFile(p)
    assert "VALUE-789" not in str(e.value)
