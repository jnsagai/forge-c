"""M6 binding uses the actual M3 queue/campaign/signature; binding grants no model dispatch."""
import json

import pytest
from forge_factory.afo import line_orders as LO
from forge_factory.afo import line_recovery as R
from forge_factory.afo.queue import Store
from forge_factory.lrtx.profile import load

from test_line_conductor_m3 import (env, grant, lineage, placer, write_campaign, PROFILE, REV1)


@pytest.fixture
def placed(env, monkeypatch):
    path = write_campaign(env, [lineage("crc-hal", "CRCHAL", "20261104-L36")])
    grant(env)
    placer(env).cycle()
    store = Store(LO.supervisor_dir() / "line-queue.sqlite3")
    order = store.orders()[0]
    attempt = store.attempts(order["order_id"])[-1]
    ws = env["line"].workspace(order["request_id"])
    profile = load(PROFILE)
    p = ws / ".forge-run/manifest.json"
    man = json.loads(p.read_text())
    man["factory_revision"]["dirty"] = False
    man["local_profile"] = {"id": PROFILE, "version": profile["version"], "config": profile["_path"],
                            "config_sha256": profile["_sha256"]}
    p.write_text(json.dumps(man))
    (ws / ".forge-run/model-profile.json").write_text(json.dumps({"default": profile["structured"]["role_models"]["author"]}))
    monkeypatch.setattr(R, "_revision", lambda revision: REV1)
    return {"store": store, "order_id": order["order_id"], "attempt_id": attempt["attempt_id"],
            "workspace": ws, "campaign_path": path, "policy_path": env["tmp"] / "line-policy.yaml",
            "auth_base": env["tmp"] / "auth", "allowed_signers": env["signers"], "now": env["clock"]()}


def test_real_m3_binding_is_read_only_and_does_not_qualify_or_launch_a_model(placed):
    before = placed["store"].orders(), placed["store"].attempts(placed["order_id"])
    result = R.bind(**placed)
    assert result["status"] == "BOUND_CONTEXT_ONLY_NO_DISPATCH"
    assert result["dispatch_authorized"] is False
    assert result["role_qualification"] == "NOT_EVALUATED"
    assert result["authorization"]["code"] == "AUTH_OK"
    assert result["source_revision"] == REV1
    assert before == (placed["store"].orders(), placed["store"].attempts(placed["order_id"]))


@pytest.mark.parametrize("field,value", [("wo", "WO-FOREIGN"), ("profile", "other"),
                                         ("campaign_commit", "0" * 40), ("campaign_file", "elsewhere.yaml"),
                                         ("authorization_id", "OTHER")])
def test_changed_order_spec_or_approval_is_refused(placed, field, value):
    p = LO.supervisor_dir() / "line-orders" / (placed["store"].order(placed["order_id"])["request_id"] + ".json")
    spec = json.loads(p.read_text())
    spec[field] = value
    p.write_text(json.dumps(spec))
    with pytest.raises(R.BindingRefused):
        R.bind(**placed)


@pytest.mark.parametrize("part,patch", [("factory_revision", {"commit": "a" * 40, "dirty": False}),
                                       ("factory_revision", {"commit": REV1, "dirty": True}),
                                       ("local_profile", {"id": PROFILE, "version": 0})])
def test_source_provenance_cannot_be_rebound(placed, part, patch):
    p = placed["workspace"] / ".forge-run/manifest.json"
    man = json.loads(p.read_text())
    man[part] = patch
    p.write_text(json.dumps(man))
    with pytest.raises(R.BindingRefused):
        R.bind(**placed)


def test_foreign_workspace_and_attempt_are_refused(placed, tmp_path):
    with pytest.raises(R.BindingRefused, match="SOURCE_WORKSPACE"):
        R.bind(**(placed | {"workspace": tmp_path}))
    with pytest.raises(R.BindingRefused, match="ATTEMPT"):
        R.bind(**(placed | {"attempt_id": "foreign"}))


def test_expiry_is_rechecked_for_every_binding(placed):
    assert R.bind(**placed)["authorization"]["code"] == "AUTH_OK"
    with pytest.raises(R.BindingRefused, match="AUTH"):
        R.bind(**(placed | {"now": placed["now"] + 15 * 86400}))


def test_modified_campaign_and_missing_model_profile_are_refused(placed):
    path = placed["campaign_path"]
    original = path.read_text()
    path.write_text(original + "\n# not approved\n")
    with pytest.raises(R.BindingRefused, match="CAMPAIGN"):
        R.bind(**placed)
    path.write_text(original)
    (placed["workspace"] / ".forge-run/model-profile.json").unlink()
    with pytest.raises(R.BindingRefused, match="MODEL_PROFILE"):
        R.bind(**placed)


def test_foreign_provenance_symlink_is_refused(placed, tmp_path):
    p = placed["workspace"] / ".forge-run/manifest.json"
    foreign = tmp_path / "foreign-manifest.json"
    foreign.write_bytes(p.read_bytes())
    p.unlink()
    p.symlink_to(foreign)
    with pytest.raises(R.BindingRefused, match="PATH_ESCAPE"):
        R.bind(**placed)


def test_another_model_or_phase_cannot_reuse_source_binding(placed):
    p = placed["workspace"] / ".forge-run/model-profile.json"
    original = p.read_text()
    p.write_text(json.dumps({"default": "another-model"}))
    with pytest.raises(R.BindingRefused, match="MODEL_PROFILE_MISMATCH"):
        R.bind(**placed)
    p.write_text(original)
    p = placed["workspace"] / ".forge-run/manifest.json"
    man = json.loads(p.read_text())
    man["phase_scope"]["stop_after"] = "SWE.6"
    p.write_text(json.dumps(man))
    with pytest.raises(R.BindingRefused, match="PHASE_SCOPE"):
        R.bind(**placed)


def test_signature_revocation_is_checked_again_after_successful_binding(placed):
    assert R.bind(**placed)["dispatch_authorized"] is False
    p = placed["auth_base"] / "AUTH-T.json"
    record = json.loads(p.read_text())
    record["revoked_utc"] = "2026-11-04T00:00:00Z"
    p.write_text(json.dumps(record))
    with pytest.raises(R.BindingRefused, match="AUTH"):
        R.bind(**placed)
