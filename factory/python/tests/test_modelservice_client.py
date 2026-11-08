"""Feature 017 T017: the factory's model-service profile and per-model link state (data-model ModelServiceProfile)."""
import httpx
import pytest
from forge_factory.modelservice import client as K
from forge_factory.modelservice.reasons import Reason

QWEN, ORN = "qwen3.6-35b-a3b-fp8", "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"


def profile(**kw):
    p = {"mode": "external", "base_url": "http://tier/v1", "credential_ref": "forge-qual",
         "expected_identity": {QWEN: {"precision": "fp8", "reasoning_mode": "off", "min_context_limit": 65536},
                               ORN: {"precision": "other", "reasoning_mode": "on", "min_context_limit": 65536}},
         "share": {"concurrency": 2, "queue_wait_max_s": 60}, "outage_wait_max_s": 120}
    p.update(kw)
    return p


def test_profile_validation():
    assert K.load_profile({"mode": "owned"})["mode"] == "owned"
    K.load_profile(profile())
    for missing in ("base_url", "credential_ref", "expected_identity", "share"):
        bad = profile()
        bad.pop(missing)
        with pytest.raises(K.ProfileError):
            K.load_profile(bad)
    with pytest.raises(K.ProfileError):
        K.load_profile({"mode": "owned", "credential_ref": "x", "unknown": 1})


def _ident(name, fp="a", **kw):
    d = {"name": name, "revision_fingerprint": fp * 64, "precision": "fp8" if name == QWEN else "other",
         "reasoning_mode": "off" if name == QWEN else "on", "context_limit": 65536, "engine": {"name": "x", "version": "1"},
         "attested": True}
    d.update(kw)
    return d


def _client(handler, **kw):
    return K.ModelServiceClient(profile(**kw), httpx.Client(transport=httpx.MockTransport(handler)), key=lambda: "K")


def test_preflight_pins_attested_identities():
    def h(req):
        assert req.headers["authorization"] == "Bearer K"
        return httpx.Response(200, json=_ident(req.url.params["model"]))
    c = _client(h)
    got = c.preflight([QWEN, ORN])
    assert got[QWEN]["attested"] and c.links[QWEN].state == K.PINNED and c.links[ORN].state == K.PINNED
    ev = c.evidence()
    assert ev["model_service_mode"] == "external" and ev["models"][QWEN]["identity"]["revision_fingerprint"] == "a" * 64


def test_preflight_falls_back_to_models_endpoint_unattested():
    def h(req):
        if req.url.path == "/forge/v1/identity":
            return httpx.Response(404)
        return httpx.Response(200, json={"data": [{"id": QWEN, "max_model_len": 65536}]})
    c = _client(h)
    got = c.preflight([QWEN])
    assert got[QWEN]["attested"] is False
    with pytest.raises(K.ProfileError, match="model_not_offered"):
        c.preflight([ORN])
    with pytest.raises(K.ProfileError, match="model_not_offered"):
        c.preflight(["unknown-model"])


def test_preflight_refuses_a_wrong_model():
    c = _client(lambda req: httpx.Response(200, json=_ident(QWEN, precision="awq-int4")))
    with pytest.raises(K.ProfileError, match="identity_changed:.*precision"):
        c.preflight([QWEN])
    assert c.links[QWEN].state == K.BLOCKED
    c = _client(lambda req: httpx.Response(200, json=_ident(QWEN, context_limit=32768)))
    with pytest.raises(K.ProfileError, match="context_limit"):
        c.preflight([QWEN])


def test_credential_refused_is_named():
    c = _client(lambda req: httpx.Response(401, json={}))
    with pytest.raises(PermissionError, match="credential_refused"):
        c.read_identity(QWEN)


def test_link_state_machine_bounds_every_wait():
    t = {"now": 0.0}
    c = K.ModelServiceClient(profile(), httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
                             key=lambda: "K", clock=lambda: t["now"])
    c.pin(QWEN, _ident(QWEN))
    assert c.outcome(QWEN, Reason.SHARE_EXHAUSTED) == K.QUEUED
    t["now"] = 30
    assert c.outcome(QWEN, Reason.SHARE_EXHAUSTED) == K.QUEUED
    assert c.outcome(QWEN, None) == K.PINNED
    assert c.outcome(QWEN, Reason.SERVICE_UNREACHABLE) == K.WAITING
    t["now"] = 200
    assert c.outcome(QWEN, Reason.SERVICE_UNREACHABLE) == K.BLOCKED and c.links[QWEN].reason == "service_unreachable"
    c.pin(ORN, _ident(ORN))
    c.pin(ORN, _ident(ORN))  # the same identity again (a swap back): still pinned
    assert c.links[ORN].state == K.PINNED
    c.pin(ORN, _ident(ORN, fp="e"))
    assert c.links[ORN].state == K.BLOCKED and c.links[ORN].reason == "identity_changed"


def test_owned_mode_has_no_client():
    with pytest.raises(K.ProfileError, match="NOT_EXTERNAL_MODE"):
        K.ModelServiceClient({"mode": "owned"}, httpx.Client(), key=lambda: "K")
