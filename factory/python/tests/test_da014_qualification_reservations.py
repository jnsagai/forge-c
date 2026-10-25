"""Real detached signatures and mission reservations, without native/model effects."""
# ruff: noqa: F811

import copy
import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from forge_factory.afo import authz, planner, policy
from forge_factory.afo import local_agent as L
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.common import sha256_file
from forge_factory.lrtx.profile import load
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_qualification import identity


@pytest.fixture
def signed(local, tmp_path, monkeypatch):
    store, order, bundle, eff, ws, _ = local
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ledger = MissionLedger(store)
    ledger.register(
        "qualification-only",
        "distinct-qualification-lineage",
        dict(
            max_attempts=0,
            max_jobs=1,
            max_requests=1,
            max_tokens=32768,
            max_tools=0,
            max_corrections=0,
            deadline=time.time() + 600,
        ),
        "AUTH-QUAL",
        authorize=lambda *a: True,
    )
    ledger.link("qualification-only", order["order_id"])
    case = planner.case(bundle, ws, {"attempts": 0}, mission_id="qualification-only")
    model = "qwen3.6:35b-a3b"
    info = load("local-rtx-v2-omniverse2")["models"]["allowed"][model]
    jid = "afo-agent-" + hashlib.sha256(f"{bundle['attempt_id']}:afo-recovery-planner".encode()).hexdigest()[:24]
    ident = {
        **identity(),
        "model_digest": info["digest"],
        "precision": info["quantization"],
        "reasoning": "high",
        "context_tokens": 65536,
        "adapter_revision": "1" * 40,
    }
    monkeypatch.setattr(Q, "revision", lambda: "1" * 40)
    binding = {"job_id": jid, "case": str(case), "case_sha256": sha256_file(case), "mission_id": "qualification-only"}
    manifest = Q.freeze(
        "protocol",
        tmp_path / "manifest.json",
        identity=ident,
        inputs=[case],
        jobs={"fixture:0": binding},
        model_profile=model,
        job_token_reservations={jid: 32768},
    )
    authdir = tmp_path / "auth"
    authdir.mkdir()
    key = tmp_path / "fixture-owner-key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True, capture_output=True)
    signers = authdir / "allowed-signers"
    signers.write_text("fixture-owner " + key.with_suffix(".pub").read_text())
    monkeypatch.setattr(authz, "AUTH_DIR", authdir)
    monkeypatch.setattr(authz, "ALLOWED_SIGNERS", signers)
    pol = copy.deepcopy(eff.policy)
    pol["authorization_ref"] = "AUTH-QUAL"
    eff = policy.Effective("PILOT", "PILOT", "a" * 64, pol)
    now = datetime.now(UTC)
    grant = dict(
        schema_version="1.0",
        authorization_id="AUTH-QUAL",
        approver="fixture-owner",
        approval_evidence_ref="fixture:explicit-qualification",
        issued_utc=(now - timedelta(seconds=1)).isoformat(),
        expires_utc=(now + timedelta(minutes=10)).isoformat(),
        policy_sha256=eff.sha256,
        mode="PILOT",
        allowed_actions=["recover_workorder"],
        scope={"models": [model]},
        signature_ref="AUTH-QUAL.sig",
        signed_runbook_ref="qualification-014:" + digest(manifest),
    )
    path = authdir / "AUTH-QUAL.json"
    path.write_text(json.dumps(grant))
    authz.sign(path, key)
    return SimpleNamespace(
        store=store,
        order=order,
        bundle=bundle,
        eff=eff,
        ws=ws,
        case=case,
        manifest=manifest,
        jid=jid,
        ledger=ledger,
        grant=grant,
        grant_path=path,
        key=key,
    )


def prepare(p, *, manifest=True):
    return L.prepare(
        p.store,
        p.order,
        p.bundle["attempt_id"],
        "afo-recovery-planner",
        p.case,
        p.ws,
        p.eff,
        qualification_manifest=p.manifest if manifest else None,
    )


def test_explicit_signed_initial_envelope_is_charged_once_and_has_no_request(signed):
    p = signed
    job = prepare(p)
    assert job["reserved_tokens"] == 32768
    assert job["qualification_initial_reservation"]["registry_default_tokens"] == 16000
    assert job["qualification_initial_reservation"]["authorization_ref"] == "AUTH-QUAL"
    assert job["qualification_manifest_sha256"] == digest(p.manifest)
    assert prepare(p)["nonce"] == job["nonce"]
    snap = p.ledger.snapshot("qualification-only")
    assert (snap["jobs"], snap["charged_tokens"], snap["requests"]) == (1, 32768, 0)
    assert snap["usage_unknown"]


def test_production_prepare_keeps_registry_envelope(signed):
    job = prepare(signed, manifest=False)
    assert job["reserved_tokens"] == 16000
    assert "qualification_initial_reservation" not in job


def test_signed_qualification_cannot_rebind_existing_job_reservation(signed):
    p = signed
    prepare(p, manifest=False)
    before = p.ledger.snapshot("qualification-only")
    with pytest.raises(Refused, match="EXECUTION_RESERVATION_REBOUND"):
        prepare(p)
    assert p.ledger.snapshot("qualification-only") == before
    assert L.records(p.store, p.order["order_id"])[0]["reserved_tokens"] == 16000


@pytest.mark.parametrize("fault", ["changed-envelope", "revoked", "expired", "different-case", "policy-cap", "changed-source"])
def test_mutated_unsigned_revoked_or_out_of_scope_qualification_cannot_reserve(signed, fault, monkeypatch):
    p = signed
    code = "QUALIFICATION_INITIAL_RESERVATION_NOT_SIGNED"
    if fault == "changed-envelope":
        p.manifest["job_token_reservations"][p.jid] = 48000
    elif fault == "revoked":
        (p.grant_path.parent / "revoked.txt").write_text("AUTH-QUAL\n")
        code = "AUTH_REVOKED"
    elif fault == "expired":
        p.grant["expires_utc"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        p.grant_path.write_text(json.dumps(p.grant))
        authz.sign(p.grant_path, p.key)
        code = "AUTH_NOT_CURRENT"
    elif fault == "different-case":
        p.manifest["jobs"]["fixture:0"]["case_sha256"] = "0" * 64
        code = "QUALIFICATION_INITIAL_RESERVATION_BINDING_MISMATCH"
    elif fault == "policy-cap":
        p.eff.policy["budgets"]["max_model_tokens_per_order"] = 16000
        code = "QUALIFICATION_INITIAL_RESERVATION_EXCEEDS_POLICY"
    else:
        monkeypatch.setattr(Q, "revision", lambda: "2" * 40)
        code = "QUALIFICATION_INITIAL_RESERVATION_SOURCE_MISMATCH"
    before = p.ledger.snapshot("qualification-only")
    with pytest.raises(Refused, match=code):
        prepare(p)
    assert p.ledger.snapshot("qualification-only") == before
    assert not L.records(p.store, p.order["order_id"])


@pytest.mark.parametrize("cap", [True, 0, -1, 65537, "32768"])
def test_frozen_qualification_allowances_remain_finite_integer_context_bounds(tmp_path, cap):
    with pytest.raises(Refused, match="QUALIFICATION_INITIAL_RESERVATIONS_INVALID"):
        Q.freeze(
            "protocol",
            tmp_path / "manifest.json",
            identity=identity(),
            jobs={"fixture:0": {"job_id": "job"}},
            job_token_reservations={"job": cap},
        )
    assert not (tmp_path / "manifest.json").exists()
