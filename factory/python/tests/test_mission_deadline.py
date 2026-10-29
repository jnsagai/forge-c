"""Explicit future time is separately authorized; original expenditure, uncertainty and non-time caps never reset."""
import json
import subprocess
import time
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from forge_factory.afo import authz, mission_admin, policy
from forge_factory.afo import mission_deadline as D
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from forge_factory.common import REPO_ROOT, load_yaml

REAL_VERIFY = authz.verify


@pytest.fixture
def mission(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    root = tmp_path / "auth"
    root.mkdir()
    monkeypatch.setattr(authz, "AUTH_DIR", root)
    monkeypatch.setattr(authz, "find", lambda *a, **k: SimpleNamespace(allow=True, code="FIXTURE_AUTHORITY"))
    monkeypatch.setattr(authz, "verify", lambda *a, **k: SimpleNamespace(allow=True, code="FIXTURE_AUTHORITY"))
    store = Store()
    ledger = MissionLedger(store)
    limits = dict(max_attempts=3, max_jobs=4, max_requests=100, max_tokens=2_000_000,
                  max_tools=100, max_corrections=1, deadline=time.time() - 10)
    ledger.register("m1", "same:idr:objective", limits, "AUTH_OLD_FIXTURE", authorize=lambda *a: True)
    ledger.execution("m1", "old-native", "PRODUCT", reserved_tokens=100_000, imported=True)
    base = load_yaml(REPO_ROOT / "config/factory/afo-policy.yaml")
    base["budgets"].update(max_model_tokens_per_order=2_000_000,max_inference_requests_per_order=100,
                           max_tool_calls_per_order=100)
    eff = policy.Effective("PILOT", "PILOT", "c" * 64, base)
    doc = {"schema": D.SCHEMA, "mission_id": "m1", "snapshot_sha256": digest(ledger.snapshot("m1")),
           "deadline_epoch": time.time() + 600, "authorization_ref": "AUTH-NEW-FIXTURE",
           "request": {"order_id": "new-request", "driver_class": "LL", "model": "local"},
           "reason": "Synthetic operator time-only continuation fixture; no actual authority"}

    def grant(value):
        record = {"authorization_id": value["authorization_ref"], "expires_utc": datetime.fromtimestamp(time.time() + 1200, UTC).isoformat(),
                  "signed_runbook_ref": "mission-deadline-extension-014:" + digest(value)}
        (root / (value["authorization_ref"] + ".json")).write_text(json.dumps(record))
        return record

    grant(doc)
    return SimpleNamespace(store=store, ledger=ledger, doc=doc, eff=eff, root=root, grant=grant)


def test_explicit_time_extension_keeps_history_caps_and_unknown_usage(mission):
    m = mission
    before = m.ledger.snapshot("m1")
    with m.store.tx() as c:
        base = c.execute("SELECT record FROM afo_missions WHERE mission_id='m1'").fetchone()[0]
    receipt = D.extend(m.store,m.doc,m.eff)
    after = m.ledger.snapshot("m1")
    assert receipt["native_effects"] is False and receipt["allowance_counters_reset"] is False
    assert after["limits"] == {**before["limits"], "deadline": m.doc["deadline_epoch"]}
    assert after["initial_limits"] == before["limits"]
    assert after["initial_authorization_ref"] == before["authorization_ref"]
    for field in ("attempts", "jobs", "requests", "tools", "charged_tokens", "usage_unknown", "unique_executions"):
        assert after[field] == before[field]
    with m.store.tx() as c:
        assert c.execute("SELECT record FROM afo_missions WHERE mission_id='m1'").fetchone()[0] == base
    assert D.extend(m.store,m.doc,m.eff) == receipt
    assert len(m.ledger.snapshot("m1")["deadline_extensions"]) == 1
    m.ledger.execution("m1","new-native","PRODUCT",reserved_tokens=100_000)
    assert m.ledger.snapshot("m1")["charged_tokens"] == 200_000
    assert m.ledger.snapshot("m1")["attempts"] == 2


def test_existing_mission_registration_accepts_only_the_explicit_effective_window(mission):
    m = mission
    D.extend(m.store,m.doc,m.eff)
    snap = m.ledger.snapshot("m1")
    document = dict(mission_id="m1",lineage=snap["lineage"],limits=snap["limits"],
                    authorization_ref=snap["authorization_ref"],request=m.doc["request"],orders=[])
    assert mission_admin.register(m.store,document,m.eff) == snap
    document["limits"] = {**document["limits"],"max_attempts":4}
    with pytest.raises(Refused):
        mission_admin.register(m.store,document,m.eff)


@pytest.mark.parametrize("failure", ["ordinary_grant", "stale_snapshot", "outside_expiry", "extra_cap", "live_native"])
def test_extension_does_not_bypass_existing_authorities_or_quiescence(mission, failure):
    m = mission
    before = m.ledger.snapshot("m1")
    if failure == "ordinary_grant":
        record=m.grant(m.doc)
        record["signed_runbook_ref"] = "qualification-product-014:ordinary-experiment"
        (m.root/(m.doc["authorization_ref"]+".json")).write_text(json.dumps(record))
    elif failure == "stale_snapshot":
        m.ledger.execution("m1","another-old","PRODUCT",reserved_tokens=10,imported=True)
    elif failure == "outside_expiry":
        m.doc["deadline_epoch"]=time.time()+10000
        m.grant(m.doc)
    elif failure == "extra_cap":
        m.doc["max_tokens"]=100_000_000
        m.grant(m.doc)
    else:
        m.ledger.execution("m1","held-native","PRODUCT",reserved_tokens=1,imported=True)
        Executions(m.store).reserve("held-native","m1","a" * 32)
        m.doc["snapshot_sha256"]=digest(m.ledger.snapshot("m1"))
        m.grant(m.doc)
    with pytest.raises(Refused, match="MISSION_NATIVE_QUIESCENCE_REQUIRED" if failure == "live_native" else None):
        D.extend(m.store,m.doc,m.eff)
    assert m.ledger.snapshot("m1")["limits"] == before["limits"]
    if failure == "live_native":
        assert Executions(m.store).get("held-native")["resource_lease"] == "HELD"


def test_new_time_cannot_refill_exhausted_product_attempts(mission):
    m = mission
    for i in range(2):
        m.ledger.execution("m1",f"exhausted-{i}","PRODUCT",reserved_tokens=100_000,imported=True)
    m.doc["snapshot_sha256"]=digest(m.ledger.snapshot("m1"))
    m.grant(m.doc)
    with pytest.raises(Refused,match="NON_TIME_ALLOWANCE_EXHAUSTED"):
        D.extend(m.store,m.doc,m.eff)


def test_actual_signature_scope_and_revocation_are_required_for_a_new_window(mission, monkeypatch):
    m=mission
    key=m.root/"fixture_key"
    subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",str(key)],check=True)
    signers=m.root/"fixture_signers"
    signers.write_text('FixtureOwner namespaces="'+authz.NAMESPACE+'" '+key.with_suffix('.pub').read_text())
    monkeypatch.setattr(authz,"ALLOWED_SIGNERS",signers)
    # Use the real public verification path, not the authority fixture used by the other tests.
    record={"schema_version":"1.0","authorization_id":m.doc["authorization_ref"],"approver":"FixtureOwner",
            "approval_evidence_ref":"SYNTHETIC_TEST_KEY_NOT_OWNER_AUTHORITY",
            "issued_utc":datetime.fromtimestamp(time.time()-10,UTC).isoformat(),
            "expires_utc":datetime.fromtimestamp(time.time()+1200,UTC).isoformat(),
            "policy_sha256":m.eff.sha256,"mode":"PILOT","allowed_actions":["recover_workorder"],
            "scope":{"order_ids":["new-request"],"driver_classes":["LL"],"models":["local"]},
            "signature_ref":m.doc["authorization_ref"]+".sig",
            "signed_runbook_ref":"mission-deadline-extension-014:"+digest(m.doc)}
    path=m.root/(m.doc["authorization_ref"]+".json")
    path.write_text(json.dumps(record))
    # Fixture-only key; the real owner's private key is never read or used here.
    authz.sign(path,key)
    monkeypatch.setattr(authz, "verify", REAL_VERIFY)
    record["revoked_utc"]=datetime.now(UTC).isoformat()
    path.write_text(json.dumps(record))
    with pytest.raises(Refused):
        D.extend(m.store,m.doc,m.eff)
    record.pop("revoked_utc")
    path.write_text(json.dumps(record))
    assert D.extend(m.store,m.doc,m.eff)["allowance_counters_reset"] is False


def test_replay_is_historical_only_and_tampering_never_changes_the_window(mission, monkeypatch):
    m=mission
    receipt=D.extend(m.store,m.doc,m.eff)
    monkeypatch.setattr(authz,"verify",lambda *a,**k:SimpleNamespace(allow=False,code="FIXTURE_REVOKED"))
    before=m.ledger.snapshot("m1")
    assert D.extend(m.store,m.doc,m.eff)==receipt and m.ledger.snapshot("m1")==before
    with m.store.tx() as c:
        row=c.execute("SELECT decision_id,record FROM afo_independent_decisions WHERE kind=?",(D.KIND,)).fetchone()
        altered=json.loads(row["record"])
        altered["deadline_epoch"]+=1000
        c.execute("UPDATE afo_independent_decisions SET record=? WHERE decision_id=?",
                  (json.dumps(altered),row["decision_id"]))
    with pytest.raises(Refused,match="HISTORY_CHANGED"):
        m.ledger.snapshot("m1")


def test_extension_chain_is_finite_and_retains_original_counter_limits(mission):
    m=mission
    for n in range(8):
        m.doc["snapshot_sha256"]=digest(m.ledger.snapshot("m1"))
        m.doc["authorization_ref"]=f"AUTH-EXTENSION-FIXTURE-{n}"
        m.doc["deadline_epoch"]=time.time()+600+n*10
        m.grant(m.doc)
        D.extend(m.store,m.doc,m.eff)
    snap=m.ledger.snapshot("m1")
    assert len(snap["deadline_extensions"])==8 and snap["charged_tokens"]==100_000
    m.doc["snapshot_sha256"]=digest(snap)
    m.doc["authorization_ref"]="AUTH-EXTENSION-FIXTURE-EXCESS"
    m.doc["deadline_epoch"]=time.time()+800
    m.grant(m.doc)
    with pytest.raises(Refused,match="EXTENSION_LIMIT"):
        D.extend(m.store,m.doc,m.eff)


def test_serial_continuation_intake_uses_effective_window_and_keeps_same_history(mission, monkeypatch):
    from forge_factory.afo import cli, overnight

    m = mission
    m.ledger.link("m1", "old-order")
    D.extend(m.store, m.doc, m.eff)
    snapshot = m.ledger.snapshot("m1")
    monkeypatch.setattr(cli, "approve", lambda *a: (True, "FIXTURE_AUTHORITY"))
    visible = []

    def submit(*a, **kw):
        # The existing mission and explicit parent are bound before queue visibility.
        assert m.ledger.for_order("new-order") == "m1"
        assert m.ledger.snapshot("m1") == snapshot
        visible.append("new-order")
        return "new-order", False

    monkeypatch.setattr(m.store, "submit", submit)
    entry = {"order_id": "new-order", "continuation_of": "old-order", "envelope": {},
             "mission": {"mission_id": "m1", "lineage": snapshot["lineage"],
                         "limits": snapshot["initial_limits"], "authorization_ref": m.doc["authorization_ref"],
                         "request": m.doc["request"]}}
    overnight.provision_order(m.store, entry, m.eff, m.doc["deadline_epoch"])
    assert visible == ["new-order"] and m.ledger.snapshot("m1") == snapshot
