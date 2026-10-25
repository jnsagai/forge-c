"""Protocol/accounting fault fixtures. No model/GPU or live service is used."""

import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from forge_factory.afo import diagnosis_packet as P
from forge_factory.afo import semantic_proposal as S
from forge_factory.afo.completion_receipt import Context, Receipts
from forge_factory.afo.durable import Refused, canonical, digest, immutable_json, strict_json
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.common import sha256_file
from test_afo_m4_recovery import order  # noqa: F401


def limits():
    return dict(
        max_attempts=6, max_jobs=4, max_requests=8, max_tokens=64000, max_tools=32, max_corrections=1, deadline=time.time() + 3600
    )


@pytest.fixture
def protocol(order, tmp_path):  # noqa: F811
    from forge_factory.afo.local_agent import SCHEMA

    store, o, b, _, eff = order
    ledger = MissionLedger(store)
    ledger.register("mission-test", "owner:campaign", limits(), "AUTH-fixture", authorize=lambda *a: True)
    ledger.link("mission-test", o["order_id"])
    ws = tmp_path / "evidence"
    (ws / "workproducts/SWE.3").mkdir(parents=True)
    (ws / "software/hal").mkdir(parents=True)
    source = ws / "workproducts/SWE.3/unit_specifications.md"
    source.write_text("Authoritative unit contract\n" + "x" * 1600 + "\nDECISIVE_LATE_FINDING")
    ref = P.seal(
        ws,
        b,
        [{"id": "late", "detail": "x" * 1700 + " decisive counterexample", "obligation_id": "USPEC-001"}],
        [{"path": source.relative_to(ws).as_posix()}],
        required_obligations=["SWR-001"],
    )
    packet = P.load(ref)
    case = tmp_path / "case.json"
    immutable_json(case, {"bundle": b, "packet_ref": ref, "workspace": str(ws)})
    job = dict(
        job_id="afo-agent-" + "1" * 24,
        mission_id="mission-test",
        order_id=o["order_id"],
        attempt_id=b["attempt_id"],
        role="afo-recovery-planner",
        reserved_tokens=16000,
        reported_tokens=None,
        nonce="a" * 32,
        case=str(case),
        case_sha256=sha256_file(case),
    )
    with store.tx() as c:
        c.execute(SCHEMA)
        c.execute(
            "INSERT INTO afo_local_agent_jobs VALUES (?,?,?,?,?,?)",
            (job["job_id"], o["order_id"], b["attempt_id"], "afo-recovery-planner", "RUNNING", canonical(job).decode()),
        )
    ledger.execution("mission-test", job["job_id"], "DIAGNOSIS", reserved_tokens=16000)
    ctx = Context.from_job(store, job["job_id"])
    proposal = {
        "decision": "PROPOSE_REPAIR",
        "evidence_refs": [packet["artifacts"][0]["ref"]],
        "strategy": "REWORK_LOCAL",
        "target_obligations": ["USPEC-001"],
        "affected_phase": "SWE.3",
        "causal_hypothesis": "One contract effect is absent from the implementation",
        "technique_id": "repair-implementation",
        "material_difference": "Implement the missing effect",
        "proposed_change": "Correct the affected function",
        "artifact_scope": ["software/hal"],
        "validation_expectations": [{"test_ref": "gate:SWE.3:route=PASS", "expected_result": "PASS"}],
    }
    return SimpleNamespace(
        store=store,
        order=o,
        bundle=b,
        eff=eff,
        ledger=ledger,
        ctx=ctx,
        packet=packet,
        ref=ref,
        ws=ws,
        source=source,
        proposal=proposal,
        job=job,
    )


def test_canonical_rejects_duplicate_nonfinite_and_preserves_unicode():
    assert canonical({"b": "é", "a": 1}) == b'{"a":1,"b":"\xc3\xa9"}'
    for raw in ['{"decision":"x","decision":"y"}', '{"x":NaN}', '{"x":Infinity}']:
        with pytest.raises(Refused):
            strict_json(raw)
    with pytest.raises(ValueError):
        canonical({"x": float("nan")})


def test_complete_inventory_retains_late_findings_and_primary_bytes(protocol):
    p = protocol
    assert p.packet["complete"] and not p.packet["truncated"]
    assert p.packet["findings"][0]["detail"].endswith("decisive counterexample")
    assert P.evidence(p.packet, p.packet["artifacts"][0]["ref"], role="afo-recovery-planner", phase="SWE.3").endswith(
        "DECISIVE_LATE_FINDING"
    )
    assert "SWR-001" in p.packet["required_obligations"]


@pytest.mark.parametrize("fault", ["role", "phase", "ref", "changed", "escape", "symlink"])
def test_evidence_boundaries(protocol, tmp_path, fault):
    p = protocol
    role, phase, ref = "afo-recovery-planner", "SWE.3", p.packet["artifacts"][0]["ref"]
    if fault == "role":
        role = "swe1-author"
    if fault == "phase":
        phase = "SWE.1"
    if fault == "ref":
        ref = "artifact:another-case"
    if fault == "changed":
        p.source.write_text("substitution")
    if fault == "escape":
        p.packet["artifacts"][0]["path"] = "../../outside"
    if fault == "symlink":
        dest = tmp_path / "outside"
        dest.write_text(p.source.read_text())
        p.source.unlink()
        p.source.symlink_to(dest)
    with pytest.raises(Refused):
        P.evidence(p.packet, ref, role=role, phase=phase)


def test_partition_global_coverage_and_serialization(protocol):
    p = protocol
    units = P.partition(
        p.packet, max_bytes=12000, instructions="explicit input", skill="locked role", tool_schema={"a": "schema"}
    )
    assert {u["obligation_id"] for u in units} == set(p.packet["obligations"])
    assert units[0]["body"]["case"]["required_obligations"] == p.packet["required_obligations"]
    assert units[0]["accounting"]["serialized_bytes"] == len(canonical(units[0]["body"]))
    with pytest.raises(Refused, match="EXCEEDS_CONTEXT"):
        P.partition(p.packet, max_bytes=500)
    bad = copy.deepcopy(p.packet)
    bad["obligations"]["USPEC-001"]["dependencies"] = ["UNRESOLVED"]
    with pytest.raises(Refused, match="DEPENDENCY"):
        P.partition(bad, max_bytes=12000)
    with pytest.raises(Refused):
        P.checkpoint(p.packet, {"USPEC-001": {"packet_sha256": "stale"}})


@pytest.mark.parametrize(
    "change",
    [
        dict(order_id="spoof"),
        dict(causal_hypothesis=""),
        dict(decision="NEEDS_EVIDENCE"),
        dict(affected_phase=3),
        dict(evidence_refs=["unknown"]),
        dict(technique_id="random"),
    ],
)
def test_semantic_fields_never_coerced_or_invented(protocol, change):
    with pytest.raises(Refused):
        S.check(S.parse({**protocol.proposal, **change}), protocol.packet)


def test_binding_deterministic_not_reworded_difference(protocol):
    p = protocol
    kw = dict(budget=dict(tokens_max=100, wall_seconds_max=60, turns_max=4), policy_ref="policy:test")
    a = S.bind(p.proposal, p.packet, **kw)
    assert a == S.bind(p.proposal, p.packet, **kw) and a["order_id"] == p.order["order_id"]
    assert S.signature(p.proposal) == S.signature({**p.proposal, "material_difference": "random seed new words"})
    assert a["notes"] == "semantic-proposal:" + digest(p.proposal)


def test_receipt_recovery_and_idempotent_dispatch(protocol):
    p = protocol
    broker = Receipts(p.store)
    stored = broker.submit(p.ctx, p.proposal)
    assert stored["admissibility_state"] == "PENDING" and stored["execution_state"] == "NOT_REQUESTED"
    assert broker.submit(p.ctx, p.proposal) == stored
    accepted = broker.admit(stored["receipt_id"], packet=p.packet, bundle=p.bundle, eff=p.eff, authorize=lambda: True)
    assert accepted["admissibility_state"] == "ACCEPTED", accepted
    assert broker.bound_plan(accepted)["strategy"] == "REWORK_LOCAL"
    dispatched = broker.request_dispatch(stored["receipt_id"], authorize=lambda: True)
    assert broker.request_dispatch(stored["receipt_id"], authorize=lambda: True) == dispatched
    assert broker.verify_chain(stored["receipt_id"])
    with p.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_durable_effects").fetchone()[0] == 1
    assert broker.compact(stored["receipt_id"])["status"] == "PASS"  # proposal, not product acceptance


def test_rejected_submission_revocation_and_revision_race(protocol):
    p = protocol
    broker = Receipts(p.store)
    rejected = broker.submit(p.ctx, '{"decision":"PASS"}')
    assert rejected["submission_state"] == "REJECTED" and rejected["decision"] is None
    stored = broker.submit(p.ctx, p.proposal)
    assert (
        broker.admit(stored["receipt_id"], packet=p.packet, bundle=p.bundle, eff=p.eff, authorize=lambda: False)[
            "admissibility_state"
        ]
        == "REJECTED"
    )
    with pytest.raises(Refused):
        broker.request_dispatch(stored["receipt_id"], authorize=lambda: True)
    with pytest.raises(Refused):
        broker._advance(stored["receipt_id"], 1, {})
    with pytest.raises(Refused):
        broker.submit(p.ctx, {**p.proposal, "proposed_change": "third correction"})


def test_close_cannot_dispatch(protocol):
    p = protocol
    broker = Receipts(p.store)
    close = {
        "decision": "CLOSE_BLOCKED",
        "evidence_refs": p.proposal["evidence_refs"],
        "blocking_reason": "UNRESOLVED_EVIDENCE",
        "explanation": "The required source is unavailable",
    }
    stored = broker.submit(p.ctx, close)
    accepted = broker.admit(stored["receipt_id"], packet=p.packet, bundle=p.bundle, eff=p.eff, authorize=lambda: True)
    assert accepted["execution_state"] == "NOT_APPLICABLE"
    assert broker.compact(stored["receipt_id"])["status"] == "BLOCKED"
    assert broker.request_dispatch(stored["receipt_id"], authorize=lambda: True)["execution_state"] == "NOT_APPLICABLE"


def test_unique_history_and_continuation_no_reset(protocol):
    p = protocol
    for _ in range(4):
        p.ledger.execution("mission-test", "fabro:server:run-A", "PRODUCT", reserved_tokens=0, imported=True)
    assert p.ledger.snapshot("mission-test")["attempts"] == 1
    p.ledger.link("mission-test", "continued-order", continuation_of=p.order["order_id"])
    assert p.ledger.for_order("continued-order") == "mission-test"
    for i in range(3):
        p.ledger.execution("mission-test", f"job-{i}", "DIAGNOSIS", reserved_tokens=16000)
    with pytest.raises(Refused, match="EXHAUSTED"):
        p.ledger.execution("mission-test", "new-job", "DIAGNOSIS", reserved_tokens=16000)
    with pytest.raises(Refused, match="RESET"):
        p.ledger.register("mission-test", "owner:campaign", limits(), "new-auth", authorize=lambda *a: True)


def native(status="RUNNING", cancel=202, matches=()):
    return SimpleNamespace(
        get_run=lambda rid: {"lifecycle": {"status": {"kind": status}}},
        cancel=lambda rid: cancel,
        list_runs=lambda **kw: list(matches),
    )


def test_terminal_outcome_cancel_ack_retains_capacity(protocol):
    p = protocol
    ex = Executions(p.store)
    ex.reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    ex.dispatch_intent(p.ctx.job_id)
    ex.adopt(p.ctx.job_id, ["native-A"])
    ex.outcome(p.ctx.job_id, "BLOCKED", "protocol failure")
    r = ex.reconcile(p.ctx.job_id, native(), cancel=True)
    assert r["task_outcome"] == "BLOCKED" and r["execution_liveness"] == "LIVE"
    assert r["cancellation_state"] == "ACKNOWLEDGED" and r["resource_lease"] == "HELD"
    with pytest.raises(Refused, match="BUSY"):
        p.ledger.acquire_inference("another-job", "mission-test")
    r = ex.reconcile(p.ctx.job_id, native("CANCELLED"))
    assert r["resource_lease"] == "RELEASED" and r["execution_liveness"] == "QUIESCENT"
    assert r["task_outcome"] == "BLOCKED"
    with pytest.raises(Refused):
        ex.outcome(p.ctx.job_id, "ACTIVE", "restart")


def test_lost_launch_late_adoption_after_revocation(protocol):
    p = protocol
    ex = Executions(p.store)
    ex.reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    ex.dispatch_intent(p.ctx.job_id)
    ex.revoke(p.ctx.job_id)
    ex.outcome(p.ctx.job_id, "BLOCKED", "revoked")
    assert ex.reconcile(p.ctx.job_id, native(), cancel=True)["resource_lease"] == "HELD"
    hits = [{"id": "late", "labels": {"afo_agent": p.ctx.job_id, "afo_nonce": p.ctx.launch_nonce}}]
    r = ex.reconcile(p.ctx.job_id, native(matches=hits), cancel=True)
    assert r["native_run_ids"] == ["late"] and r["cancellation_state"] == "ACKNOWLEDGED"


def test_request_concurrency_unknown_usage_and_overshoot(protocol):
    p = protocol
    Executions(p.store).reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)

    def reserve(n):
        try:
            return p.ledger.reserve_request(
                "mission-test",
                p.ctx.job_id,
                f"request-{n}",
                body_sha256=digest(n),
                input_tokens=1000,
                output_cap=1000,
                authorize=lambda: True,
            )
        except Refused as e:
            return e.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, [1, 2]))
    accepted = [r for r in results if isinstance(r, dict)]
    assert len(accepted) == 1 and "INFERENCE_REQUEST_BUSY" in results
    rid = accepted[0]["request_id"]
    assert p.ledger.snapshot("mission-test")["charged_tokens"] == 16000
    p.ledger.reconcile_request(rid)
    assert reserve(3) == "INFERENCE_REQUEST_BUSY"
    p.ledger.reconcile_request(rid, input_tokens=1000, output_tokens=18000, quiescent=True, evidence_ref="provider:terminal")
    assert p.ledger.snapshot("mission-test")["charged_tokens"] == 19000
    assert reserve(4) == "JOB_TOKEN_ENVELOPE_EXHAUSTED"
