"""AFO M0 (T003/T004/T006; AFO-FR-002/003/004/006; AT-063/AT-064): fail-closed policy, signed owner authorization
bound to scope/expiry/action/policy hash/revocation, and the authority intersection with the constitution and CRE."""
import json
import subprocess
from datetime import UTC, datetime, timedelta

import pytest
import yaml
from forge_factory.afo import authority, authz, policy
from forge_factory.common import REPO_ROOT

EXAMPLE = REPO_ROOT / "config/factory/afo-policy.yaml"
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    key = tmp_path / "owner_ed25519"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "owner", "-f", str(key)], check=True)
    signers = tmp_path / "allowed_signers"
    signers.write_text(f'Jefferson namespaces="{authz.NAMESPACE}" {(tmp_path / "owner_ed25519.pub").read_text()}')
    monkeypatch.setattr(authz, "ALLOWED_SIGNERS", signers)
    monkeypatch.setattr(authz, "REVOKED", tmp_path / "auth" / "revoked.txt")
    monkeypatch.setattr(authz, "verify", _verify_with(signers))
    (tmp_path / "auth").mkdir()
    return tmp_path, key


def _verify_with(signers):
    orig = authz.__dict__["verify"].__wrapped__ if hasattr(authz.verify, "__wrapped__") else authz.verify

    def v(auth, **kw):
        kw.setdefault("allowed_signers", signers)
        return orig(auth, **kw)
    return v


def _policy(tmp_path, mode="PILOT", **changes):
    pol = yaml.safe_load(EXAMPLE.read_text())
    pol["mode"] = mode
    if mode in ("PILOT", "ACTIVE"):
        pol["authorization_ref"] = "AUTH-1"
    for k, v in changes.items():
        sect, key = k.split("__")
        pol[sect][key] = v
    p = tmp_path / "afo-policy.yaml"
    p.write_text(yaml.safe_dump(pol))
    return p


def _auth(tmp_path, key, sha, aid="AUTH-1", mode="PILOT", sign=True, **over):
    rec = {"schema_version": "1.0", "authorization_id": aid, "approver": "Jefferson",
           "approval_evidence_ref": "owner message 2026-10-19", "issued_utc": "2026-10-19T00:00:00Z",
           "expires_utc": "2026-10-26T00:00:00Z", "policy_sha256": sha, "mode": mode,
           "allowed_actions": ["launch_workorder", "reconcile_run", "service_restart"],
           "scope": {"driver_classes": ["STM32N6_RCC_HAL"], "models": ["deepseek-flash"]},
           "signature_ref": f"{aid}.sig", "revoked_utc": None, **over}
    p = tmp_path / "auth" / f"{aid}.json"
    p.write_text(json.dumps(rec))
    if sign:
        authz.sign(p, key)
    return p, rec


def test_absent_invalid_or_floor_breaking_policy_is_disabled(env, tmp_path, monkeypatch):
    assert policy.load(tmp_path / "missing.yaml").mode == "DISABLED"
    bad = _policy(tmp_path, "OBSERVE_ONLY", maintenance__auto_merge_source=True)
    e = policy.load(bad)
    assert e.mode == "DISABLED" and any(i.startswith("SCHEMA:") for i in e.issues)
    monkeypatch.setattr(policy, "schema_errors", lambda pol: [])             # a weakened schema alone opens nothing
    e = policy.load(bad)
    assert e.mode == "DISABLED" and e.issues == ["FLOOR_VIOLATION:maintenance.auto_merge_source=True (must be False)"]
    (tmp_path / "junk.yaml").write_text(": : :\n")
    assert policy.load(tmp_path / "junk.yaml").mode == "DISABLED"


def test_the_shipped_policy_requests_pilot_for_the_production_line_and_acts_only_when_owner_signed():
    """Owner 2026-10-25 ("AFO ... solve it! I want it running with codex and claude as inspector, forget about
    deepseek now"): PILOT with the codex-claude profile only. Without the owner's valid signature the effective mode
    stays OBSERVE_ONLY; the shipped authorization record is bound to the exact shipped policy."""
    e = policy.load()
    assert yaml.safe_load(EXAMPLE.read_text())["mode"] == "PILOT"
    assert e.get("engineering.allowed_model_profiles") == ["codex-claude"]
    rec = json.loads((authz.AUTH_DIR / f"{e.get('authorization_ref')}.json").read_text())
    assert authz.schema_errors(rec) == [] and rec["policy_sha256"] == e.sha256 and rec["scope"]["models"] == ["codex-claude"]
    sig = authz.AUTH_DIR / rec["signature_ref"]
    assert (e.mode, e.authorization_id) == ("PILOT", rec["authorization_id"]) if sig.is_file() else \
        (e.mode == "OBSERVE_ONLY" and e.issues[0].startswith("MODE_PILOT_NOT_AUTHORIZED"))


def test_pilot_takes_effect_only_with_a_valid_signed_authorization(env, tmp_path):
    _, key = env
    pol = _policy(tmp_path)
    sha = policy.load(pol, auth_base=tmp_path / "auth", now=NOW).sha256
    e = policy.load(pol, auth_base=tmp_path / "auth", now=NOW)
    assert e.mode == "OBSERVE_ONLY" and e.issues[0].startswith("MODE_PILOT_NOT_AUTHORIZED:AUTH_RECORD_MISSING")
    _auth(tmp_path, key, sha)
    e = policy.load(pol, auth_base=tmp_path / "auth", now=NOW)
    assert e.mode == "PILOT" and e.authorization_id == "AUTH-1"
    assert policy.load(pol, auth_base=tmp_path / "auth", now=NOW + timedelta(days=8)).mode == "OBSERVE_ONLY"  # expired


@pytest.mark.parametrize("case", ["tampered", "unsigned", "other_policy", "revoked_field", "revocation_list",
                                  "wrong_mode", "agent_key"])
def test_each_broken_authorization_is_refused(env, tmp_path, case):
    _, key = env
    pol = _policy(tmp_path)
    sha = policy.load(pol).sha256
    if case == "tampered":
        p, rec = _auth(tmp_path, key, sha)
        p.write_text(json.dumps({**rec, "allowed_actions": rec["allowed_actions"] + ["finalize_blocked"]}))
    elif case == "unsigned":
        _auth(tmp_path, key, sha, sign=False)
    elif case == "other_policy":
        _auth(tmp_path, key, "0" * 64)
    elif case == "revoked_field":
        p, rec = _auth(tmp_path, key, sha)
        p.write_text(json.dumps({**rec, "revoked_utc": "2026-10-19T06:00:00Z"}))     # revocation needs no re-signing
    elif case == "revocation_list":
        _auth(tmp_path, key, sha)
        authz.REVOKED.write_text("AUTH-1  # owner revoked 2026-10-19\n")
    elif case == "wrong_mode":
        _auth(tmp_path, key, sha, mode="ACTIVE")
    elif case == "agent_key":
        other = tmp_path / "agent_key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other)], check=True)
        _auth(tmp_path, other, sha)
    e = policy.load(pol, auth_base=tmp_path / "auth", now=NOW)
    assert e.mode == "OBSERVE_ONLY", (case, e)


class _Cre:
    def __init__(self, mode, actions=()):
        self.mode, self.actions = mode, set(actions)

    def automatic_action_allowed(self, a):
        return self.mode == "ACTIVE" and a in self.actions


def test_authority_intersection(env, tmp_path, monkeypatch):
    _, key = env
    pol = _policy(tmp_path)
    sha = policy.load(pol).sha256
    _auth(tmp_path, key, sha)
    monkeypatch.setattr(authz, "AUTH_DIR", tmp_path / "auth")
    monkeypatch.setattr(authz, "find", lambda mode, s, **kw: authz._find_orig(
        mode, s, **{**kw, "base": tmp_path / "auth", "now": NOW}))
    pilot = policy.load(pol, auth_base=tmp_path / "auth", now=NOW)
    obs = policy.load(EXAMPLE)
    D = authority.decide
    for a in ("source_deploy", "safety_approval", "edit_cre_policy", "enable_cre_mode", "promote_factory_code"):
        assert D(a, afo=pilot).code == "FORBIDDEN_BY_CONSTITUTION"                    # never, even when authorized
    assert D("read_status", afo=obs).allow and not D("launch_workorder", afo=obs).allow
    assert D("launch_workorder", {"driver_class": "STM32N6_RCC_HAL"}, afo=pilot).allow
    assert D("launch_workorder", {"model": "qwen3:8b"}, afo=pilot).code == "AFO_AUTH_OUT_OF_SCOPE"
    assert D("finalize_blocked", afo=pilot).code == "AFO_AUTH_ACTION_NOT_ALLOWED"
    assert D("service_restart", afo=pilot, cre=_Cre("OBSERVE_ONLY")).code == "CRE_NOT_AUTHORIZED"   # no implicit CRE
    assert D("service_restart", afo=pilot, cre=_Cre("ACTIVE", ["service_restart"])).allow
    assert D("format_disk", afo=pilot).code == "UNKNOWN_ACTION"
    log = [json.loads(x) for x in (tmp_path / "state/afo/decisions.jsonl").read_text().splitlines()]
    assert len(log) >= 12 and all(r["decision_id"].startswith("afo-dec-") and r["kind"] == "authority" for r in log)


authz._find_orig = authz.find
