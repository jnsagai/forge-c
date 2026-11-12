"""Durable Maintainer integration: candidate receipts are not independent repair verdicts."""

# ruff: noqa: F811
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import local_agent as L
from forge_factory.afo import maintainer as M
from forge_factory.afo.durable import Refused, immutable_json
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.common import sha256_file
from forge_factory.reliability import isolation
from test_afo_local_autonomy import local, order  # noqa: F401
from test_afo_m5_maintainer import SIG, _case, _good_candidate, _head, factory  # noqa: F401
from test_da014_integration import ready
from test_da014_protocol import limits, protocol  # noqa: F401


def test_submission_replays_without_another_commit_and_rejects_changed_request(factory):
    case = _case(factory)
    _good_candidate(case)
    sub = M.submit(case, "fix addition", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    assert M.submit(case, "fix addition", M.CANDIDATE_TESTS + "rpr_calc.py", SIG) == sub
    assert _head(Path(case["src"])) == sub["candidate"]
    with pytest.raises(M.MaintainerDenied, match="SUBMISSION_REPLAY_CHANGED"):
        M.submit(case, "different request", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    receipt = M.submission(case, require_receipt=True)[1]
    assert receipt["submission_sha256"] == sha256_file(M.case_dir(case["proposal_id"]) / "submission.json")


def test_crash_after_commit_is_adopted_before_resealing(factory, monkeypatch):
    case = _case(factory)
    _good_candidate(case)
    original = M.veto
    monkeypatch.setattr(M, "veto", lambda *a: (_ for _ in ()).throw(TimeoutError("crash after commit")))
    with pytest.raises(TimeoutError):
        M.submit(case, "fix addition", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    committed = _head(Path(case["src"]))
    monkeypatch.setattr(M, "veto", original)
    sub = M.submit(case, "fix addition", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    assert sub["candidate"] == committed == _head(Path(case["src"]))


def test_submission_tampering_is_rejected_before_review(factory):
    case = _case(factory)
    _good_candidate(case)
    M.submit(case, "fix addition", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    path = M.case_dir(case["proposal_id"]) / "submission.json"
    path.chmod(0o600)
    path.write_text(path.read_text().replace("fix addition", "invent success"))
    with pytest.raises(M.MaintainerDenied, match="SUBMISSION_RECEIPT_MISMATCH"):
        M.submission(case, require_receipt=True)


def test_durable_maintenance_prepares_without_a_semantic_packet(local, monkeypatch, tmp_path):
    s, o, b, eff, ws, _ = local
    ledger = MissionLedger(s)
    ledger.register("maintenance-mission", "maintenance:fixture", limits(), "AUTH-fixture", authorize=lambda *a: True)
    ledger.link("maintenance-mission", o["order_id"])
    case = tmp_path / "maintenance-case.json"
    immutable_json(case, {"proposal_id": "mnt-fixture-a1", "incident": {"order_id": o["order_id"]}})
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    monkeypatch.setattr(isolation, "available", lambda: True)
    job = L.prepare(s, o, b["attempt_id"], "afo-factory-maintainer", case, ws, eff)
    assert job["durable_native"] == "maintenance-1" and not job.get("durable_protocol")
    assert job["mission_id"] == "maintenance-mission" and job["model_digest"]
    with s.tx() as c:
        rec = json.loads(c.execute("SELECT record FROM afo_mission_executions WHERE identity=?", (job["job_id"],)).fetchone()[0])
    assert rec["kind"] == "MAINTENANCE" and rec["reserved_tokens"] == job["reserved_tokens"]


def test_candidate_receipt_survives_missing_final_but_waits_for_provider_quiescence(protocol, factory, monkeypatch):
    p = protocol
    case = M.prepare("mnt-durable-a1", "HEAD", {"order_id": p.order["order_id"]}, factory)
    _good_candidate(case)
    M.submit(case, "fix addition", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    job = ready(p, monkeypatch)
    job.pop("durable_protocol")
    job.update(
        durable_native="maintenance-1", role="afo-factory-maintainer", case=str(M.case_dir(case["proposal_id"]) / "case.json")
    )
    job["case_sha256"] = sha256_file(Path(job["case"]))
    L.save(p.store, job)
    client = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "SUCCEEDED"}}}, usage=lambda _: {})
    job = L.poll(p.store, p.order, job, p.eff, client=client, launch_fn=lambda _: "native-maintainer")
    p.ledger.reserve_request(
        "mission-test", job["job_id"], "req-maint", body_sha256="a" * 64, input_tokens=10, output_cap=20, authorize=lambda: True
    )
    p.ledger.start_request("req-maint", authorize=lambda: True)
    job = L.poll(p.store, p.order, job, p.eff, client=client)
    assert job["state"] == "RUNNING" and Executions(p.store).get(job["job_id"])["resource_lease"] == "HELD"
    p.ledger.reconcile_request("req-maint", input_tokens=10, output_tokens=3, quiescent=True, evidence_ref="provider-finished")
    job = L.poll(p.store, p.order, job, p.eff, client=client)
    assert job["state"] == "SUCCEEDED" and job["completion"]["status"] == "PASS"
    rec = Executions(p.store).get(job["job_id"])
    assert rec["task_outcome"] == "BLOCKED" and rec["terminal_reason"] == "CANDIDATE_REQUIRES_INDEPENDENT_REVIEW"


def test_native_success_without_submission_is_not_a_maintenance_receipt(protocol, monkeypatch):
    p = protocol
    job = ready(p, monkeypatch)
    job.pop("durable_protocol")
    job.update(durable_native="maintenance-1", role="afo-factory-maintainer")
    L.save(p.store, job)
    client = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "SUCCEEDED"}}}, usage=lambda _: {})
    L.poll(p.store, p.order, job, p.eff, client=client, launch_fn=lambda _: "native-maintainer")
    job = L.poll(p.store, p.order, job, p.eff, client=client)
    assert job["state"] == "FAILED" and job["error"].startswith("NO_VALID_MAINTENANCE_RECEIPT:")


def test_unqualified_maintenance_cannot_send_inference(protocol, monkeypatch):
    from forge_factory.afo.request_admission import reserve
    from forge_factory.lrtx import role_capability

    p = protocol
    job = ready(p, monkeypatch)
    job.pop("durable_protocol")
    job.update(durable_native="maintenance-1", role="afo-factory-maintainer")
    L.save(p.store, job)
    Executions(p.store).reserve(job["job_id"], job["mission_id"], job["nonce"])
    seen = []

    def unqualified(j, role, **kwargs):
        seen.append(role)
        raise Refused("CAPABILITY_LIMIT", "maintenance is not diagnosis qualification")

    monkeypatch.setattr(role_capability, "admit_job", unqualified)
    with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
        reserve(
            p.store,
            {"job_id": job["job_id"], "nonce": job["nonce"], "request_id": "req-unqualified"},
            {"model": job["model"], "messages": [{"role": "user", "content": "fix"}], "max_tokens": 20},
            eff=p.eff,
        )
    assert seen == ["afo-factory-maintainer"]
    with p.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_request_ledger").fetchone()[0] == 0


def test_missing_receipt_cannot_downgrade_a_new_submission_to_legacy(factory):
    case = _case(factory)
    _good_candidate(case)
    M.submit(case, "fix addition", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    (M.case_dir(case["proposal_id"]) / "submission-receipt.json").unlink()
    with pytest.raises(FileNotFoundError):
        M.submission(case)
