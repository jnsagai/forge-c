"""The policy the gates use is fail-closed: an unapproved file, or a mode no human-authorized transition accepted,
never takes effect (found while enabling the owner-authorized PILOT, 2026-10-18)."""
import yaml
from forge_factory.assurance import contracts, policy
from forge_factory.assurance.store import AssuranceStore

AUTH = {"approved_by": "Jefferson Nascimento", "approved_at": "2026-10-18", "reference": "owner instruction"}


def _pilot_file(tmp_path):
    pol = contracts.load(contracts.POLICY_EXAMPLE)
    pol.update(mode="PILOT", authorization=AUTH)
    f = tmp_path / "assurance-policy.yaml"
    f.write_text(yaml.safe_dump(pol))
    return f, pol


def test_unapproved_file_and_unaccepted_mode_never_take_effect(tmp_path):
    store = AssuranceStore(tmp_path / "easa.sqlite3")
    f, pol = _pilot_file(tmp_path)
    assert policy.active(store, f)["mode"] == "OBSERVE_ONLY"                 # file not approved: built-in default
    policy.approve(store, pol, "Jefferson Nascimento")
    a = policy.active(store, f)
    assert a["mode"] == "OBSERVE_ONLY" and a["mode_requested_in_file"] == "PILOT"  # approved, but no accepted transition
    d = policy.request_mode(store, pol, "PILOT")                                  # no authorization -> rejected
    assert d["decision"] == "REJECTED" and "HUMAN_AUTHORIZATION_MISSING" in d["issues"]
    assert policy.active(store, f)["mode"] == "OBSERVE_ONLY"
    assert policy.request_mode(store, pol, "PILOT", authorization=AUTH)["decision"] == "ACCEPTED"
    assert policy.active(store, f)["mode"] == "PILOT"


def test_agent_cannot_authorize_the_mode(tmp_path):
    store = AssuranceStore(tmp_path / "easa.sqlite3")
    _, pol = _pilot_file(tmp_path)
    d = policy.request_mode(store, pol, "PILOT", authorization={**AUTH, "approved_by": "agent:swe-author"})
    assert d["decision"] == "REJECTED" and policy.accepted_mode(store) == "OBSERVE_ONLY"
