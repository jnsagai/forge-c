"""M3 (T019–T023): incident ledger, model-free supervisor, probes, routing/dedup/breaker, dual dispatch path."""
import json
import socket
import sqlite3
import sys

import pytest
from forge_factory.supervisor import probes as P
from forge_factory.supervisor import service as S
from forge_factory.supervisor.dispatch import dispatch
from forge_factory.supervisor.router import Router, RouterState
from forge_factory.supervisor.store import IncidentStore, TransitionError


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    return tmp_path


def pol():
    return S.load_policy()


# ---------------- T019 -----------------------------------------------------------------------------------
def test_t019_transitions_guarded_dedup_append_only_and_restart(env):
    db = env / "inc.sqlite3"
    st = IncidentStore(db)
    a, created = st.open_or_dedup("fabro:READINESS_FAILURE:-:0.4", "fabro", "READINESS_FAILURE")
    b, created2 = st.open_or_dedup("fabro:READINESS_FAILURE:-:0.4", "fabro", "READINESS_FAILURE")
    assert created and not created2 and a["incident_id"] == b["incident_id"] and b["occurrences"] == 2
    with pytest.raises(TransitionError):
        st.transition(a["incident_id"], "RESOLVED" if False else "VERIFYING")
    st.transition(a["incident_id"], "TRIAGED")
    st2 = IncidentStore(db)  # "power loss / restart": new process view of the same durable DB
    assert st2.get(a["incident_id"])["state"] == "TRIAGED"
    st2.transition(a["incident_id"], "REPAIRING", attempts=1)
    st2.transition(a["incident_id"], "VERIFYING")
    st2.transition(a["incident_id"], "RESOLVED")
    with pytest.raises(TransitionError):
        st2.transition(a["incident_id"], "TRIAGED")  # terminal is immutable
    c, created3 = st2.open_or_dedup("fabro:READINESS_FAILURE:-:0.4", "fabro", "READINESS_FAILURE")
    assert created3 and c["previous_incident_id"] == a["incident_id"]
    con = sqlite3.connect(db)
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("UPDATE incident_history SET reason='x'")
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM incident_history")
    assert [h["to_state"] for h in st2.history(a["incident_id"])] == ["DETECTED", "TRIAGED", "REPAIRING", "VERIFYING",
                                                                       "RESOLVED"]


def test_t019_lease_single_owner(env):
    st = IncidentStore(env / "i.sqlite3")
    inc, _ = st.open_or_dedup("x:Y:-:0.4", "x", "Y")
    assert st.acquire_lease(inc["incident_id"], "A") and not st.acquire_lease(inc["incident_id"], "B")
    st.release_lease(inc["incident_id"], "A")
    assert st.acquire_lease(inc["incident_id"], "B")


# ---------------- T020 -----------------------------------------------------------------------------------
class HealthyProbes:
    def all(self, db):
        return [P.Sample("fabro", "fabro_readiness", "HEALTHY"), P.Sample("evidence_store", "evidence_store_writable",
                                                                          "HEALTHY"), P.Sample("gpu", "gpu", "UNKNOWN")]


def test_t020_100_healthy_polls_zero_model_calls(env, monkeypatch):
    S.install_model_guard()
    S.MODEL_CALLS["blocked_attempts"] = 0
    sup = S.Supervisor(pol(), HealthyProbes(), home=env / "sup", finalizer_enabled=False)
    for _ in range(100):
        h = sup.poll_once()
    assert h["polls"] == 100 and h["model_calls"] == 0 and h["model_tokens"] == 0 and h["status"] == "HEALTHY"
    evs = [json.loads(x) for x in (env / "ev/factory-events.jsonl").read_text().splitlines()]
    assert sum(1 for e in evs if e["channel"] == "supervisor" and e["message"].startswith("poll ")) == 100
    # the guard really blocks and counts a model-port connection (spy)
    with pytest.raises(PermissionError):
        socket.create_connection(("127.0.0.1", 11436), timeout=1)
    assert S.MODEL_CALLS["blocked_attempts"] == 1
    S.MODEL_CALLS["blocked_attempts"] = 0


def test_t020_interval_validation(tmp_path):
    import yaml
    from forge_factory.common import CONFIG_DIR
    p = yaml.safe_load((CONFIG_DIR / "supervisor-policy.yaml").read_text())
    for bad in (10, 301):
        p["poll_interval_seconds"] = bad
        f = tmp_path / f"p{bad}.yaml"
        f.write_text(yaml.safe_dump(p))
        with pytest.raises(ValueError):
            S.load_policy(f)


def test_t020_supervisor_has_no_model_client_imports():
    import ast
    import pathlib

    for f in pathlib.Path(S.__file__).parent.glob("*.py"):
        tree = ast.parse(f.read_text())
        names = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | \
                {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any("llm_gateway" in (m or "") or "openai" in (m or "") or "ollama" in (m or "") for m in names), f


# ---------------- T021 -----------------------------------------------------------------------------------
def test_t021_fabro_crash_disk_full_mcp_dashboard_unknowns(env, monkeypatch):
    pr = P.Probes(pol(), "http://127.0.0.1:9", None, "http://127.0.0.1:9", ["forge-nonexistent-mcp"], env)
    assert pr.fabro_readiness().status == "DOWN"
    assert pr.dashboard_health().fault_type == "DASHBOARD_DOWN"
    monkeypatch.setattr(P.shutil, "disk_usage", lambda d: type("U", (), {"free": 10 * 2**20})())
    assert {s.fault_type for s in pr.storage()} == {"DISK_PRESSURE"}
    monkeypatch.setattr(P.shutil, "which", lambda t: None)
    assert pr.gpu().status == "UNKNOWN"
    with pytest.raises(PermissionError):
        P._http_json("http://127.0.0.1:11435/api/tags")


def test_t021_frozen_stage_and_mcp_timeout(env, monkeypatch):
    pr = P.Probes(pol(), "http://127.0.0.1:32290", None, None, ["forge-docs-mcp"], env)

    def fake(url, timeout=3.0, headers=None):
        if url.endswith("/runs?page%5Blimit%5D=20"):
            return {"data": [{"id": "R1", "lifecycle": {"status": {"kind": "running"}}}]}
        return {"data": [{"ts": "2026-01-01T00:00:00Z"}]}
    monkeypatch.setattr(P, "_http_json", fake)
    s = pr.fabro_run_progress()[0]
    assert s.fault_type == "STAGE_STALL" and s.run_id == "R1"
    import forge_factory.mcp.preflight as PF
    monkeypatch.setattr(PF, "handshake", lambda sid: {"server": sid, "error": "TimeoutError:", "tools": []})
    assert pr.mcp_handshake().fault_type == "MCP_HANDSHAKE_FAILURE"


# ---------------- T022 -----------------------------------------------------------------------------------
def test_t022_dedup_single_repair_breaker_and_quota(env):
    st = IncidentStore(env / "i.sqlite3")
    p = pol()
    r = Router(p, st, RouterState())
    down = [P.Sample("fabro", "fabro_readiness", "DOWN", fault_type="READINESS_FAILURE")]
    assert r.observe(down) == []  # 1st failed poll: below threshold (2)
    elig = r.observe(down)
    assert len(elig) == 1 and len(st.active()) == 1
    assert len(r.observe(down + down)) == 1  # duplicate root cause -> still one incident, one candidate
    res = dispatch(elig[0], st, fabro_healthy=False, dry_run=True)
    assert res["path"] == "external_local_worker"
    assert r.observe(down) == []  # in repair: no second dispatch
    assert dispatch(elig[0], st, False, dry_run=True)["reason"] == "NOT_ELIGIBLE_STATE"
    inc = st.must(elig[0]["incident_id"])
    st.transition(inc["incident_id"], "ROLLED_BACK")
    st.transition(inc["incident_id"], "TRIAGED", attempts=2)
    r.observe(down)
    assert st.must(inc["incident_id"])["state"] == "REQUIRES_OFFLINE_ATTENTION"  # breaker (max 2 attempts)


def test_t022_self_recovery_and_not_repairable(env):
    st = IncidentStore(env / "i.sqlite3")
    r = Router(pol(), st, RouterState())
    disk = [P.Sample("evidence_store", "evidence_store_writable", "DEGRADED", fault_type="DISK_PRESSURE")]
    r.observe(disk)
    assert st.all()[0]["state"] == "REQUIRES_OFFLINE_ATTENTION"  # outside auto-repair scope
    q = [P.Sample("fabro-queue", "queued_run_age", "DEGRADED", fault_type="QUEUE_STALL", run_id="R9")]
    r.p["repair"]["request_ai_agent_on_eligible_incident"] = False
    r.observe(q)
    for _ in range(3):
        r.observe([])
    assert any(i["fault_type"] == "QUEUE_STALL" and i["state"] == "RESOLVED" for i in st.all())


# ---------------- T023 -----------------------------------------------------------------------------------
def test_t023_fabro_down_external_worker_actually_starts(env):
    st = IncidentStore(env / "i.sqlite3")
    inc, _ = st.open_or_dedup("fabro:READINESS_FAILURE:-:0.4", "fabro", "READINESS_FAILURE")
    st.transition(inc["incident_id"], "TRIAGED")
    marker = env / "worker-started"
    res = dispatch(st.must(inc["incident_id"]), st, fabro_healthy=False,
                   launcher=[sys.executable, "-c", f"open({str(marker)!r},'w').write('ok')"])
    import time
    for _ in range(50):
        if marker.exists():
            break
        time.sleep(0.1)
    assert res["path"] == "external_local_worker" and marker.read_text() == "ok"
    assert st.must(inc["incident_id"])["state"] == "REPAIRING" and st.attempts(inc["incident_id"])


def test_t023_healthy_engine_uses_fabro_child_path(env):
    st = IncidentStore(env / "i.sqlite3")
    inc, _ = st.open_or_dedup("mcp:forge-docs-mcp:MCP_HANDSHAKE_FAILURE:-:0.4", "mcp:forge-docs-mcp",
                              "MCP_HANDSHAKE_FAILURE")
    st.transition(inc["incident_id"], "TRIAGED")
    assert dispatch(st.must(inc["incident_id"]), st, fabro_healthy=True, dry_run=True)["path"] == "fabro_child_run"
