"""CONTROL renewal uses real signed TEST grants/normal receipts; no live authority or inference."""
# ruff: noqa: F811
import copy
import json
import time
from pathlib import Path

import pytest
from forge_factory.afo import authz
from forge_factory.afo import line_orders as O
from forge_factory.afo import line_recovery_control as C
from forge_factory.afo import line_soak_prerequisites as P
from forge_factory.afo import mission_capacity as MC
from forge_factory.afo import mission_deadline as MD
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.common import sha256_file
from test_da014_qualification import identity
from test_line_conductor_m3 import ORN, env  # noqa: F401
from test_line_soak_intake import planned  # noqa: F401
from test_line_soak_prerequisites import database_snapshot, pending, ref  # noqa: F401
from test_mission_capacity import mission  # noqa: F401


def sign(p, value):
    path = p.env["tmp"] / "auth" / (value["authorization_id"] + ".json")
    path.write_text(json.dumps(value))
    authz.sign(path, p.env["key"])


def current_control(p, value, name):
    cref = ref(p.env["tmp"] / (name + ".json"), value)
    grant = json.loads((p.env["tmp"] / "auth/AUTH-CONTROL.json").read_text())
    grant["signed_runbook_ref"] = "line-recovery-014:" + digest(value)
    sign(p, grant)
    request = {"order_id": p.future_spec["wo"], "driver_class": p.future_spec["driver_class"], "model": value["profile"]}
    assert C.configuration(cref, p.eff, request=request) == value
    return cref


def renewed(p):
    ledger = MissionLedger(p.store)
    mid = p.control["mission"]["mission_id"]
    ledger.execution(mid, "CONTROL-earlier-product", "PRODUCT", reserved_tokens=137, reported_tokens=7)
    before = ledger.snapshot(mid)
    doc = {"schema": MD.SCHEMA, "mission_id": mid, "snapshot_sha256": digest(before),
           "deadline_epoch": time.time() + 1200, "authorization_ref": "AUTH-M9-DEADLINE-TEST",
           "request": {"order_id": p.future_spec["wo"], "driver_class": p.future_spec["driver_class"],
                       "model": p.control["profile"]}, "reason": "CONTROL-only explicit time extension, no counter refill"}
    grant = json.loads((p.env["tmp"] / "auth/AUTH-CONTROL.json").read_text())
    grant.update(authorization_id=doc["authorization_ref"], signature_ref=doc["authorization_ref"] + ".sig",
                 signed_runbook_ref="mission-deadline-extension-014:" + digest(doc))
    sign(p, grant)
    with p.store.tx() as c:
        raw = c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (mid,)).fetchone()[0]
    receipt = MD.extend(p.store, doc, p.eff)
    after = ledger.snapshot(mid)
    control = copy.deepcopy(p.control)
    control["mission"]["limits"] = after["limits"]
    cref = current_control(p, control, "renewed-control")
    assert after["authorization_ref"] != control["authorization_ref"] == after["initial_authorization_ref"]
    for key in ("attempts", "jobs", "requests", "tools", "corrections", "charged_tokens", "usage_unknown", "unique_executions"):
        assert after[key] == before[key]
    with p.store.tx() as c:
        assert c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (mid,)).fetchone()[0] == raw
    assert receipt["allowance_counters_reset"] is False
    return control, cref, before, after


def projection(p, control, cref, *, queued):
    from forge_factory.afo import line_soak_intake as I

    lin = p.future_campaign.lineages[0]
    _, how = O.quality_delivery(lin, p.env["line"])
    order = O.phase_order(lin, "SWE.1", "START", wo=lin.wo("SWE.1"), resume_from=None, provided_from=None,
                          quality_via=(how or None), durable_control=cref)
    spec = O.placed_spec(order, p.future_campaign, p.future_grant)
    spec["digest"] = O._digest(spec)
    envelope = O.envelope_for(order, lin, p.future_campaign, p.future_grant, time.time(), spec["digest"], line_id="local")
    binding = {**p.future_binding, "line_intake_identity": I.identity(spec, envelope, cref)}
    if queued:
        path = O.supervisor_dir() / "line-orders" / (spec["wo"] + ".json")
        O._atomic(path, spec)
        oid, created = p.store.submit(envelope, repo=p.future_campaign.root, max_queued=100,
                                     approve=lambda e: (True, "NORMAL_APPROVED_CAMPAIGN_CONTROL"))
        assert created and oid == binding["order_id"]
        descriptor = {"schema": "forge-c/line-soak-pending-order/1", "order_id": oid, "attempt_seq": 1,
                      "spec_ref": {"path": str(path), "sha256": sha256_file(path)}, "control_ref": cref,
                      "line_origin": p.planned["line_origin"]}
    else:
        descriptor = {**p.planned, "control_ref": cref, "spec_ref": ref(p.env["tmp"] / "renewed-spec.json", spec)}
    doc = {**p.doc, "jobs": {"renewal": ref(p.env["tmp"] / "renewed-descriptor.json", descriptor)}}
    idx = ref(p.env["tmp"] / "renewed-index.json", doc)
    plan = {**p.future_plan, "prerequisites_ref": idx}
    pref = ref(p.env["tmp"] / "renewed-plan.json", plan)
    manifest = Q.freeze("operation-24", p.env["tmp"] / "renewed-manifest.json", identity=identity(),
                        inputs=[Path(idx["path"]), Path(doc["recovery_policy_ref"]["path"]), Path(pref["path"])],
                        jobs={"renewal": binding}, model_profile=ORN)
    return manifest, plan, binding


@pytest.mark.parametrize("queued", [False, True])
def test_current_signed_control_accepts_original_authority_with_effective_time_without_reset(planned, queued):
    p = planned
    control, cref, before, expected = renewed(p)
    manifest, plan, binding = projection(p, control, cref, queued=queued)
    database = database_snapshot(p.store)
    result = P.check(manifest, plan)
    assert result["blockers"] == [], result
    assert result["jobs"][0]["mission"] == expected
    assert P.admission_boundary(manifest, plan, result)["blockers"] == []
    assert database_snapshot(p.store) == database  # preview cannot refill/rewrite/link/reserve
    ledger = MissionLedger(p.store)
    # Ordinary continuation accounting on the same real registered mission remains cumulative.
    ledger.link(expected["mission_id"], binding["order_id"])
    ledger.execution(expected["mission_id"], binding["job_id"], "PRODUCT", reserved_tokens=100, reported_tokens=5)
    after = ledger.snapshot(expected["mission_id"])
    assert after["initial_authorization_ref"] == control["authorization_ref"]
    assert after["authorization_ref"] == expected["authorization_ref"]
    assert after["limits"] == expected["limits"] and after["charged_tokens"] == before["charged_tokens"] + 100
    assert after["attempts"] == before["attempts"] + 1


@pytest.mark.parametrize("fault", ["base-authority", "deadline-receipt", "effective-caps", "current-signature"])
def test_renewal_does_not_accept_changed_authority_chain_caps_or_current_control(planned, fault):
    p = planned
    control, cref, _, expected = renewed(p)
    if fault == "effective-caps":
        control["mission"]["limits"] = {**control["mission"]["limits"], "max_attempts": expected["limits"]["max_attempts"] + 1}
        cref = current_control(p, control, "unamended-cap-control")
    manifest, plan, _ = projection(p, control, cref, queued=False)
    if fault in ("base-authority", "deadline-receipt"):
        with p.store.tx() as c:
            if fault == "base-authority":
                row = json.loads(c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (expected["mission_id"],)).fetchone()[0])
                row["authorization_ref"] = "UNRELATED-CONTROL"
                c.execute("UPDATE afo_missions SET record=? WHERE mission_id=?", (json.dumps(row), expected["mission_id"]))
            else:
                c.execute("UPDATE afo_independent_decisions SET sha256=? WHERE kind=?", ("0" * 64, MD.KIND))
    else:
        if fault == "current-signature":
            (p.env["tmp"] / "auth/AUTH-CONTROL.sig").write_text("CONTROL deliberately invalid signature")
    before = database_snapshot(p.store)
    result = P.check(manifest, plan)
    assert result["status"] == "BLOCKED", result
    assert database_snapshot(p.store) == before


def test_capacity_and_time_replay_remain_exact_and_broken_capacity_chain_refuses(mission):
    """Normal amendment APIs, existing fixture authority substitution explicitly CONTROL only."""
    m = mission
    base = m.ledger.snapshot("rcc")
    MC.amend(m.store, m.doc, m.eff)
    doc = {"schema": MD.SCHEMA, "mission_id": "rcc", "snapshot_sha256": digest(m.ledger.snapshot("rcc")),
           "deadline_epoch": time.time() + 600, "authorization_ref": "AUTH-TIME-TEST",
           "request": m.doc["request"], "reason": "CONTROL time independent of capacity"}
    m.grant(doc, "mission-deadline-extension-014:")
    MD.extend(m.store, doc, m.eff)
    expected = m.ledger.snapshot("rcc")
    ctl = {"authorization_ref": base["authorization_ref"], "mission": {
        "mission_id": "rcc", "lineage": base["lineage"], "limits": expected["limits"]}}
    with ReadSnapshot(m.store.path) as reader:
        assert P.bound_mission(reader, ctl) == expected
        with pytest.raises(Refused, match="MISSION_CHANGED"):
            P.bound_mission(reader, {**ctl, "mission": {**ctl["mission"], "limits": base["limits"]}})
    with m.store.tx() as c:
        c.execute("UPDATE afo_independent_decisions SET sha256=? WHERE kind=?", ("0" * 64, MC.KIND))
    with ReadSnapshot(m.store.path) as reader, pytest.raises(Refused, match="CAPACITY_HISTORY_CHANGED"):
        P.bound_mission(reader, ctl)
