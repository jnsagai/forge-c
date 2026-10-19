"""AFO M2 (T016-T025; AT-010..AT-016, AT-021, AT-041): durable queue, pinned approved intake, guarded transitions,
fenced leases, idempotent outbox, deterministic scheduler, concurrency, idle zero model calls, backup/restore."""
import hashlib
import json
import multiprocessing as mp
import subprocess
import time
from datetime import UTC, datetime

import pytest
import yaml
from forge_factory.afo import authz, cli, policy, scheduler
from forge_factory.afo.queue import QueueError, Store
from forge_factory.common import REPO_ROOT

NOW = datetime.now(UTC)
OK = {"mount": lambda: True, "fabro": lambda: True, "gateway": lambda: True, "mcp": lambda: True}


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    r = tmp_path / "repo"
    (r / "afo-manifests").mkdir(parents=True)
    return r


def _manifest(repo, name="m1", body=None):
    p = repo / "afo-manifests" / f"{name}.json"
    p.write_text(json.dumps(body or {"example": "examples/0002b-arm_55_rcc_hal", "provided_from": "WO-LL-r125",
                                     "model": "deepseek-flash", "acp_authors": "codex"}))
    return f"afo-manifests/{name}.json", hashlib.sha256(p.read_bytes()).hexdigest()


def _env(repo, rid="RCC-HAL-1", name="m1", prio="NORMAL", model="deepseek-flash", **over):
    ref, sha = _manifest(repo, name)
    return {"schema_version": "1.0", "request_id": rid, "tenant_scope": "local", "manifest_sha256": sha,
            "input_manifest_ref": ref, "approved_by": "Jefferson", "authorization_ref": "AUTH-1",
            "driver_class": "STM32N6_RCC_HAL", "target": "Arm Cortex-M55", "safety_scope": "SC-RCC-2026-10-18",
            "model_profile": model, "submitted_utc": "2026-10-19T08:00:00Z", "priority": prio, **over}


def test_store_migrates_with_wal_full_sync_and_private_file(repo):
    s = Store()
    assert s.schema_version() == 1
    c = s.connect()
    assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal" and c.execute("PRAGMA synchronous").fetchone()[0] == 2
    assert oct(s.path.stat().st_mode & 0o777) == "0o600"
    assert Store().schema_version() == 1                                      # re-open is a no-op migration


def test_intake_pins_the_manifest_is_idempotent_and_detects_conflicts(repo):
    s = Store()
    env = _env(repo)
    oid, created = s.submit(env, repo=repo, max_queued=10)
    assert created and s.order(oid)["state"] == "QUEUED"
    assert s.submit(env, repo=repo, max_queued=10) == (oid, False)           # same request + hash: same order
    with pytest.raises(QueueError) as e:
        s.submit({**env, "manifest_sha256": "f" * 64}, repo=repo, max_queued=10)
    assert e.value.code == "INTAKE_MANIFEST_HASH_MISMATCH"                     # pinned to the file content
    _, sha2 = _manifest(repo, "m1", {"example": "changed"})                      # same request, new manifest
    with pytest.raises(QueueError) as e:
        s.submit({**env, "manifest_sha256": sha2}, repo=repo, max_queued=10)
    assert e.value.code == "CONFLICT" and s.events(oid)[-1]["type"] == "afo.intake_conflict"
    for bad, code in (({"input_manifest_ref": "../../etc/passwd"}, "INTAKE_MANIFEST_MISSING"),
                      ({"priority": "URGENT"}, "INTAKE_SCHEMA")):
        with pytest.raises(QueueError) as e:
            s.submit({**_env(repo, rid="X2", name="m2"), **bad}, repo=repo, max_queued=10)
        assert e.value.code == code
    with pytest.raises(QueueError) as e:
        s.submit(_env(repo, rid="X3", name="m3"), repo=repo, max_queued=1)
    assert e.value.code == "INTAKE_BACKLOG_FULL"
    with pytest.raises(QueueError) as e:
        s.submit(_env(repo, rid="X4", name="m4"), repo=repo, max_queued=10, approve=lambda env: (False, "AUTH_REVOKED"))
    assert e.value.code == "INTAKE_NOT_APPROVED"


def test_transitions_follow_the_contract_fsm_with_cas_and_audit(repo):
    s = Store()
    oid, _ = s.submit(_env(repo), repo=repo, max_queued=10)
    with pytest.raises(QueueError):
        s.transition(oid, "READY_FOR_OFFLINE_REVIEW", "skip ahead")             # not an edge from QUEUED
    assert s.events(oid)[-1]["type"] == "afo.transition_denied"
    v = s.order(oid)["version"]
    with pytest.raises(QueueError):
        s.transition(oid, "PAUSED", "stale writer", expect_version=v - 1)
    assert s.transition(oid, "PAUSED", "operator", expect_version=v)
    n = len(s.events(oid))
    assert s.transition(oid, "PAUSED", "again") is False and len(s.events(oid)) == n   # idempotent no-op
    s.transition(oid, "QUEUED", "resume")
    s.transition(oid, "BLOCKED", "test")
    with pytest.raises(QueueError):
        s.transition(oid, "QUEUED", "no re-entry after terminal")


def test_leases_fence_a_stale_scheduler(repo):
    s = Store()
    oid, _ = s.submit(_env(repo), repo=repo, max_queued=10)
    e1 = s.acquire_lease("scheduler", "A", ttl=60, now=1000)
    assert e1 == 1 and s.acquire_lease("scheduler", "B", ttl=60, now=1030) is None
    assert s.acquire_lease("scheduler", "A", ttl=60, now=1030) == 1          # renewal keeps the epoch
    e2 = s.acquire_lease("scheduler", "B", ttl=60, now=1200)                 # A expired: takeover, new epoch
    assert e2 == 2
    with pytest.raises(QueueError) as e:
        s.admit(oid, epoch=e1, scope="scheduler", policy_sha256="x", authorization_id=None, max_concurrent=1)
    assert e.value.code == "FENCED" and s.order(oid)["state"] == "QUEUED"
    aid = s.admit(oid, epoch=e2, scope="scheduler", policy_sha256="x", authorization_id=None, max_concurrent=1)
    assert aid == f"{oid}-a1" and [c["kind"] for c in s.commands("PENDING")] == ["FABRO_LAUNCH"]
    with s.tx() as c:
        s._enqueue(c, "FABRO_LAUNCH", f"launch:{aid}", oid, aid, e2, {"attempt_id": aid})   # replayed intent
    assert len(s.commands()) == 1
    s.attempt_transition(aid, "DISPATCH_PENDING")
    with pytest.raises(QueueError):
        s.attempt_transition(aid, "PREPARED")


def _pilot(tmp_path, monkeypatch):
    key = tmp_path / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    signers = tmp_path / "signers"
    signers.write_text(f'Jefferson namespaces="{authz.NAMESPACE}" {(tmp_path / "k.pub").read_text()}')
    pol = yaml.safe_load((REPO_ROOT / "config/factory/afo-policy.yaml").read_text())
    pol.update(mode="PILOT", authorization_ref="AUTH-1")
    pp = tmp_path / "afo-policy.yaml"
    pp.write_text(yaml.safe_dump(pol))
    adir = tmp_path / "auth"
    adir.mkdir()
    sha = policy.load(pp).sha256
    rec = {"schema_version": "1.0", "authorization_id": "AUTH-1", "approver": "Jefferson", "approval_evidence_ref": "t",
           "issued_utc": "2026-01-01T00:00:00Z", "expires_utc": "2099-01-01T00:00:00Z", "policy_sha256": sha,
           "mode": "PILOT", "allowed_actions": ["submit_workorder", "launch_workorder"],
           "scope": {"driver_classes": ["STM32N6_RCC_HAL"]}, "signature_ref": "AUTH-1.sig", "revoked_utc": None}
    (adir / "AUTH-1.json").write_text(json.dumps(rec))
    authz.sign(adir / "AUTH-1.json", key)
    monkeypatch.setattr(authz, "AUTH_DIR", adir)
    monkeypatch.setattr(authz, "ALLOWED_SIGNERS", signers)
    orig = authz.verify
    monkeypatch.setattr(authz, "verify", lambda a, **kw: orig(a, **{**kw, "allowed_signers": signers}))
    monkeypatch.setattr(policy, "POLICY_PATH", pp)
    return policy.load(pp, auth_base=adir)


def test_scheduler_by_mode_with_authority_preflight_backoff_and_budget(repo, tmp_path, monkeypatch):
    s = Store()
    obs = policy.load()
    oid, _ = s.submit(_env(repo), repo=repo, max_queued=10)
    r = scheduler.cycle(s, "A", eff=obs, probes=OK)
    assert r["action"] == "simulated" and r["would"] == "admit" and s.order(oid)["state"] == "QUEUED"
    pilot = _pilot(tmp_path, monkeypatch)
    assert pilot.mode == "PILOT" and cli.approve(_env(repo), pilot) == (True, "AUTH_OK")
    down = {**OK, "fabro": lambda: False}
    r1 = scheduler.cycle(s, "A", eff=pilot, probes=down, now=time.time())
    assert r1["action"] == "deferred" and r1["issues"] == ["FABRO_UNAVAILABLE"] and r1["wait_s"] == 60
    assert scheduler.cycle(s, "A", eff=pilot, probes=OK)["action"] == "idle"          # backing off
    r2 = scheduler.cycle(s, "A", eff=pilot, probes=down, now=time.time() + 61)
    assert r2["wait_s"] == 120                                                          # exponential, bounded
    s.set_control("paused", "1", "op", "maintenance")
    assert scheduler.cycle(s, "A", eff=pilot, probes=OK, now=time.time() + 400)["code"] == "PAUSED"
    s.set_control("paused", "0", "op", "done")
    r3 = scheduler.cycle(s, "A", eff=pilot, probes=OK, now=time.time() + 400)
    assert r3["action"] == "admitted" and s.order(oid)["state"] == "ADMITTED"
    oid2, _ = s.submit(_env(repo, rid="RCC-HAL-2", name="m2"), repo=repo, max_queued=10)
    assert scheduler.cycle(s, "A", eff=pilot, probes=OK)["code"] == "CAPACITY"          # one worker
    oid3, _ = s.submit(_env(repo, rid="RCC-HAL-3", name="m3", model="qwen3:8b"), repo=repo, max_queued=10)
    s.transition(oid2, "PAUSED", "hold")
    r4 = scheduler.cycle(s, "A", eff=pilot, probes=OK)
    assert r4["action"] in ("refused", "blocked") and s.order(oid3)["state"] in ("QUEUED", "BLOCKED")


def test_priority_aging_prevents_starvation(repo):
    s = Store()
    low, _ = s.submit(_env(repo, rid="LOW", name="l", prio="LOW"), repo=repo, max_queued=10)
    time.sleep(0.05)
    high, _ = s.submit(_env(repo, rid="HIGH", name="h", prio="HIGH"), repo=repo, max_queued=10)
    t0 = s.order(high)["created_epoch"]
    assert s.next_candidate(aging_s=3600, now=t0 + 1)["order_id"] == high
    assert s.next_candidate(aging_s=3600, now=t0 + 3 * 3600)["order_id"] == high      # equal waits: still HIGH
    assert s.next_candidate(aging_s=0.01, now=t0 + 0.05)["order_id"] == low           # LOW has waited longer


def _submit_proc(args):
    import os
    state, repo, env = args
    os.environ["FORGE_STATE_DIR"] = state
    from pathlib import Path

    from forge_factory.afo.queue import Store as S
    return S().submit(env, repo=Path(repo), max_queued=100)[0]


def test_concurrent_duplicate_submits_make_one_order(repo, tmp_path):
    env = _env(repo)
    Store()
    with mp.get_context("spawn").Pool(6) as pool:
        ids = pool.map(_submit_proc, [(str(tmp_path / "state"), str(repo), env)] * 12)
    assert len(set(ids)) == 1 and len(Store().orders()) == 1
    assert sum(e["type"] == "afo.submitted" for e in Store().events()) == 1


def test_idle_conductor_makes_no_model_call(repo, monkeypatch):
    from forge_factory.afo import conductor
    from forge_factory.supervisor import service

    service.MODEL_CALLS["blocked_attempts"] = 0
    assert conductor.Conductor(0.05, max_cycles=5).run() == 0
    assert service.MODEL_CALLS["blocked_attempts"] == 0
    assert json.loads(conductor.heartbeat_path().read_text())["detail"].startswith("idle")


def test_backup_restore_and_event_forwarding_once(repo, tmp_path):
    s = Store()
    oid, _ = s.submit(_env(repo), repo=repo, max_queued=10)
    seen = []
    assert s.forward_events(lambda *a, **k: seen.append(k["payload_ref"])) == 2 and s.forward_events(lambda *a, **k: 0) == 0
    b = s.backup(tmp_path / "bk" / "c.sqlite3")
    assert b["integrity"] == "ok"
    r = Store.restore(tmp_path / "bk" / "c.sqlite3", tmp_path / "restored" / "c.sqlite3")
    assert r["integrity"] == "ok" and Store(tmp_path / "restored" / "c.sqlite3").order(oid)["state"] == "QUEUED"
    with pytest.raises(QueueError):
        Store.restore(tmp_path / "bk" / "c.sqlite3", s.path)                 # never overwrite the live store
    (tmp_path / "bad.sqlite3").write_bytes(b"not a database" * 100)
    with pytest.raises(Exception):  # noqa: B017 - corrupt backups are refused either way
        Store.restore(tmp_path / "bad.sqlite3", tmp_path / "x" / "c.sqlite3")
