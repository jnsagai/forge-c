"""CONTROL: time-only mission renewal preserves the original finite lineage and spend."""
# ruff: noqa: F811 - imported pytest fixture is consumed by name
import copy
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from forge_factory.afo import authz
from forge_factory.afo import line_recovery_product as P
from forge_factory.afo import mission_deadline as D
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.mission_ledger import MissionLedger
from test_line_recovery_product_bridge import product  # noqa: F401


@pytest.fixture
def renewal(product, tmp_path, monkeypatch):
    p = product
    ledger = MissionLedger(p.store)
    old = copy.deepcopy(p.control["mission"])
    old["limits"]["deadline"] = time.time() - 1
    ledger.register(**old, authorization_ref=p.control["authorization_ref"], authorize=lambda *_: True)
    ledger.execution(old["mission_id"], "retained-old-launch", "PRODUCT", reserved_tokens=100_000, imported=True)
    before = ledger.snapshot(old["mission_id"])
    with p.store.tx() as c:
        base = c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (old["mission_id"],)).fetchone()[0]
    doc = dict(schema=D.SCHEMA, mission_id=old["mission_id"], snapshot_sha256=digest(before),
               deadline_epoch=time.time()+1200, authorization_ref="fixture-independent-deadline-authority",
               request=dict(order_id=p.spec["wo"], driver_class=p.spec["driver_class"], model=p.spec["profile"]),
               reason="Synthetic owner-signed time-only extension CONTROL; no production authority")
    auth = tmp_path / "renewal-auth"
    auth.mkdir()
    (auth / (doc["authorization_ref"]+".json")).write_text(json.dumps(dict(
        schema_version="1.0", authorization_id=doc["authorization_ref"], approver="FixtureOwner",
        approval_evidence_ref="SYNTHETIC_CONTROL_NOT_OWNER_AUTHORITY",
        issued_utc=datetime.fromtimestamp(time.time()-30, UTC).isoformat(),
        expires_utc=datetime.fromtimestamp(time.time()+1800, UTC).isoformat(),
        policy_sha256="c"*64, mode="PILOT", allowed_actions=["recover_workorder"],
        scope=dict(order_ids=[p.spec["wo"]], driver_classes=[p.spec["driver_class"]], models=[p.spec["profile"]]),
        signature_ref="fixture.sig", signed_runbook_ref="mission-deadline-extension-014:"+digest(doc))))
    monkeypatch.setattr(authz, "AUTH_DIR", auth)
    # Detached-signature cryptography alone is substituted. Normal authz schema,
    # time, policy, scope, revocation and all append-only accounting checks run.
    monkeypatch.setattr(authz, "signature_valid", lambda *a, **kw: True)
    D.extend(p.store, doc, SimpleNamespace(mode="PILOT", sha256="c"*64, get=lambda *_: 1800))
    p.control["mission"]["limits"] = ledger.snapshot(old["mission_id"])["limits"]
    return SimpleNamespace(p=p, ledger=ledger, before=before, base=base, doc=doc)


def test_normal_time_extension_links_next_order_without_replacing_base_or_spend(renewal):
    r = renewal
    p = r.p
    before = r.ledger.snapshot(p.control["mission"]["mission_id"])
    assert before["authorization_ref"] != p.control["authorization_ref"]
    snap = P.link_mission(p.store, p.store.order(p.oid), p.control, p.spec)
    assert snap == before
    assert r.ledger.for_order(p.oid) == snap["mission_id"]
    assert P.link_mission(p.store, p.store.order(p.oid), p.control, p.spec) == before
    assert snap["attempts"] == 1 and snap["charged_tokens"] == 100_000 and snap["usage_unknown"] is True
    with p.store.tx() as c:
        assert c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (snap["mission_id"],)).fetchone()[0] == r.base
    # A renewed mission window never widens the existing per-order execution wall.
    out = P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client,
                     launch=lambda *a, **kw: {"outcome": "LAUNCHED", "fabro_run_id": "CONTROL-NEW-NATIVE"})
    assert out["actions"][0]["action"] == "launched"
    job = P.registered(p.store, P.job_id(p.aid))
    assert job["deadline_epoch"] <= p.store.order(p.oid)["created_epoch"] + 600
    after = r.ledger.snapshot(snap["mission_id"])
    assert after["attempts"] == 2 and after["charged_tokens"] == 220_000 and after["usage_unknown"] is True


@pytest.mark.parametrize("fault", ["authority", "lineage", "capacity", "deadline", "history", "extension-integrity"])
def test_renewal_never_links_changed_authority_limits_or_unaccounted_history(renewal, fault):
    r = renewal
    p = r.p
    if fault == "authority":
        p.control["authorization_ref"] = "foreign-control"
    elif fault == "lineage":
        p.control["mission"]["lineage"] += "-renamed"
    elif fault == "capacity":
        p.control["mission"]["limits"]["max_tokens"] += 1
    elif fault == "deadline":
        p.control["mission"]["limits"]["deadline"] += 1
    elif fault == "history":
        p.store.attempt_transition(p.aid, "DISPATCH_PENDING")
        p.store.attempt_transition(p.aid, "RUNNING", fabro_run_id="UNACCOUNTED-NATIVE")
    else:
        with p.store.tx() as c:
            c.execute("UPDATE afo_independent_decisions SET sha256=? WHERE kind=?", ("0"*64, D.KIND))
    with pytest.raises(Refused):
        P.link_mission(p.store, p.store.order(p.oid), p.control, p.spec)
    with pytest.raises(Refused, match="MISSION_LINK_REQUIRED"):
        r.ledger.for_order(p.oid)


def test_existing_link_cannot_switch_original_control_authority(renewal):
    p = renewal.p
    P.link_mission(p.store, p.store.order(p.oid), p.control, p.spec)
    changed = {**p.control, "authorization_ref": "foreign-control"}
    with pytest.raises(Refused, match="MISSION_AUTHORITY_CHANGED"):
        P.link_mission(p.store, p.store.order(p.oid), changed, p.spec)
