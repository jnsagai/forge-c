"""Signed finite controller inputs only. Synthetic fixtures are not live qualification."""
import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from forge_factory.afo import line_recovery_control as C
from forge_factory.afo.durable import Refused, digest, immutable_json


@pytest.fixture
def control(tmp_path, monkeypatch):
    from forge_factory.afo import authz

    eff = SimpleNamespace(mode="PILOT", sha256="b" * 64, get=lambda key, default=None:
                          {"authorization_ref": "fixture-control"}.get(key, default))
    cfg = {"schema": C.SCHEMA, "source_revision": "a" * 40, "policy_sha256": eff.sha256,
           "authorization_ref": "fixture-control", "profile": "fixture-local", "profile_sha256": "c" * 64,
           "operations_intent": str(tmp_path / "private-intent.json"),
           "mission": {"mission_id": "mission-fixture", "lineage": "fixture-lineage",
                       "limits": {"max_attempts": 3, "max_jobs": 2, "max_requests": 8, "max_tokens": 240000,
                                  "max_tools": 24, "max_corrections": 1, "deadline": time.time() + 120}},
           "role_capabilities": {}, "product_role_trial": None}
    monkeypatch.setattr(authz, "AUTH_DIR", tmp_path)
    allowed = SimpleNamespace(allow=True, code="AUTH_OK")
    monkeypatch.setattr(authz, "find", lambda *args, **kwargs: allowed)
    monkeypatch.setattr(C, "revision", lambda: {"commit": "a" * 40, "dirty": False})
    monkeypatch.setattr(C, "profile_identity", lambda _: "c" * 64)

    def publish(value):
        sha = digest(value)
        p = tmp_path / (sha + ".json")
        immutable_json(p, value)
        grant = {"signed_runbook_ref": "line-recovery-014:" + sha,
                 "expires_utc": "2099-01-01T00:00:00+00:00"}
        (tmp_path / "fixture-control.json").write_text(json.dumps(grant))
        return {"path": str(p), "sha256": sha}
    return SimpleNamespace(cfg=cfg, eff=eff, publish=publish, allowed=allowed)


def test_explicit_signed_config_is_source_profile_policy_and_finite_mission_bound(control):
    c = control
    ref = c.publish(c.cfg)
    assert C.configuration(ref, c.eff) == c.cfg
    assert C.role_inputs(ref, c.eff) == {"role_capabilities": {}, "product_role_trial": None}


@pytest.mark.parametrize("changed", ["source", "dirty", "profile", "policy", "signature", "expiry"])
def test_configuration_refuses_changed_or_expired_controller_authority(control, monkeypatch, changed):
    c = control
    ref = c.publish(c.cfg)
    if changed == "source":
        monkeypatch.setattr(C, "revision", lambda: {"commit": "d" * 40, "dirty": False})
    elif changed == "dirty":
        monkeypatch.setattr(C, "revision", lambda: {"commit": "a" * 40, "dirty": True})
    elif changed == "profile":
        monkeypatch.setattr(C, "profile_identity", lambda _: "d" * 64)
    elif changed == "policy":
        c.eff.sha256 = "d" * 64
    elif changed == "signature":
        c.allowed.allow = False
        c.allowed.code = "AUTH_REVOKED"
    else:
        c.cfg["mission"]["limits"]["deadline"] = 0
        ref = c.publish(c.cfg)
    with pytest.raises(Refused):
        C.configuration(ref, c.eff)


def test_signed_finite_config_cannot_infer_role_qualification_or_accept_invalid_limits(control):
    c = control
    altered = copy.deepcopy(c.cfg)
    altered["mission"]["limits"]["max_tokens"] = -1
    with pytest.raises(Refused, match="FINITE_MISSION"):
        C.configuration(c.publish(altered), c.eff)
    ref = c.publish(c.cfg)
    assert C.role_inputs(ref, c.eff)["role_capabilities"] == {}



def test_separate_controller_checkout_cannot_replace_executing_worker_source(control, monkeypatch):
    c = control
    ref = c.publish(c.cfg)
    monkeypatch.setattr(C, "revision", lambda: {"commit": "d" * 40, "dirty": False})
    assert C.controller_configuration(ref, c.eff, target_revision="a" * 40, request={}) == c.cfg
    with pytest.raises(Refused, match="EXECUTING_REVISION_MISMATCH"):
        C.configuration(ref, c.eff)
