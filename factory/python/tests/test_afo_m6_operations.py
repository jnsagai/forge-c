"""AFO M6 (AFO-T054..T061; AT-014/037..040/042/052..056) - dead-letter cases, alert outbox, read-only Autonomy API and
view, authenticated operator controls, AFO evidence inside the release package, mixed-workload isolation and the
redaction / forged-write / audit-preservation negatives."""
import json
import os
import sqlite3
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from forge_factory.afo import alerts, deadletter
from forge_factory.afo import dashboard_api as F
from forge_factory.afo.queue import QueueError, Store
from test_afo_m2_queue import _env, repo  # noqa: F401 - the M2 queue fixture and helper

CANARY = "ghp_" + "Q7" * 18


def _blocked(s, repo, rid, reason="ORDER_ATTEMPT_BUDGET_EXHAUSTED: 3 attempts"):  # noqa: F811
    oid, _ = s.submit(_env(repo, rid=rid, name=rid), repo=repo, max_queued=50)
    for to in ("ADMITTED", "RUNNING"):
        s.transition(oid, to, "test")
    s.transition(oid, "BLOCKED", reason, terminal_reason=reason)
    return oid


@pytest.fixture()
def env(repo, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(tmp_path / "archives"))
    return repo


def test_dead_letter_exactly_once_immutable_and_operator_states(env):
    s = Store()
    oid = _blocked(s, env, "RCC-DLQ-1")
    cid, new = deadletter.record_case(s, oid)
    assert new and deadletter.record_case(s, oid) == (cid, False)                  # repeated finalizer callback
    assert deadletter.sweep(s) == [] and deadletter.sweep(Store()) == []            # sweep + "restart": no new case
    cases = deadletter.cases(s)
    assert len(cases) == 1 and cases[0]["record"]["reason_code"] == "ORDER_ATTEMPT_BUDGET_EXHAUSTED"
    assert cases[0]["record"]["package_status"] == "BLOCKED" and "re-submit" in cases[0]["record"]["required_action"]
    assert len(alerts.notifications(s)) == 1                                        # one alert per case
    c = sqlite3.connect(s.path, isolation_level=None)                               # autocommit: no lock left
    for sql in ("UPDATE afo_dead_letters SET reason_code='X'", "UPDATE afo_dead_letters SET record='{}'",
                "DELETE FROM afo_dead_letters"):
        with pytest.raises(sqlite3.DatabaseError, match="IMMUTABLE_DEAD_LETTER"):
            c.execute(sql)
    c.close()
    with pytest.raises(QueueError):
        deadletter.set_state(s, cid, "ACKNOWLEDGED", "op", "")                     # reason required
    deadletter.set_state(s, cid, "ACKNOWLEDGED", "op", "looking at it")
    deadletter.set_state(s, cid, "CLOSED", "op", "resubmitted as a new order")
    with pytest.raises(QueueError) as e:
        deadletter.set_state(s, cid, "OPEN", "op", "reopen")
    assert e.value.code == "CASE_TRANSITION_DENIED"
    oid2, _ = s.submit(_env(env, rid="RCC-RUN", name="run"), repo=env, max_queued=50)
    with pytest.raises(QueueError) as e:
        deadletter.record_case(s, oid2)                                             # only after BLOCKED finalization
    assert e.value.code == "NOT_BLOCKED"


def test_mixed_workload_isolation_and_per_order_terminality(env):
    """T060 (AT-037/038/039): failed orders get cases; healthy and running orders are untouched; terminal states are
    final (no hidden re-entry) and a BLOCKED case is never a READY count."""
    s = Store()
    bad = [_blocked(s, env, f"RCC-BAD-{i}", reason=r) for i, r in enumerate(
        ["PACKAGE_MISSING", "WAITING_EXTERNAL_CHANGE_TTL:86400s", "package BLOCKED / BLOCKED, 3 gaps"])]
    ok, _ = s.submit(_env(env, rid="RCC-OK", name="ok"), repo=env, max_queued=50)
    for to in ("ADMITTED", "RUNNING", "VALIDATING", "READY_FOR_OFFLINE_REVIEW"):
        s.transition(ok, to, "verified archive")
    run, _ = s.submit(_env(env, rid="RCC-RUNNING", name="running"), repo=env, max_queued=50)
    s.transition(run, "ADMITTED", "t")
    assert sorted(deadletter.sweep(s)) == sorted(c["case_id"] for c in deadletter.cases(s)) and len(deadletter.cases(s)) == 3
    assert {c["order_id"] for c in deadletter.cases(s)} == set(bad)
    assert [c["record"]["reason_code"] for c in sorted(deadletter.cases(s), key=lambda c: bad.index(c["order_id"]))] == [
        "PACKAGE_MISSING", "WAITING_EXTERNAL_CHANGE_TTL", "PACKAGE"]
    assert s.order(ok)["state"] == "READY_FOR_OFFLINE_REVIEW" and s.order(run)["state"] == "ADMITTED"
    for oid, to in ((bad[0], "QUEUED"), (ok, "BLOCKED"), (bad[1], "RUNNING")):
        with pytest.raises(QueueError) as e:
            s.transition(oid, to, "re-enter")
        assert e.value.code == "TRANSITION_DENIED"
    summ = F.summary()
    assert summ["orders"]["BLOCKED"] == 3 and summ["orders"]["READY_FOR_OFFLINE_REVIEW"] == 1
    assert summ["dead_letters_open"] == 3 and "never counted" in summ["statement"]


def test_alerts_dedupe_rearm_local_fallback_retry_and_redaction(env):
    s = Store()
    sent, emitted = [], []
    with s.tx() as c:
        alerts.enqueue(c, "dlq:x", "WARN", {"order_id": "afo-1", "detail": f"token {CANARY}"}, now=1000)
        assert alerts.enqueue(c, "dlq:x", "WARN", {"order_id": "afo-1"}, now=1010)[1] == "counted"
    flaky = {"n": 0}

    def webhook(msg):
        flaky["n"] += 1
        if flaky["n"] == 1:
            raise ConnectionError("down")
        sent.append(msg)

    r1 = alerts.deliver(s, {"webhook": webhook}, now=1020, emit=lambda *a, **k: emitted.append((a, k)))
    assert r1[0]["state"] == "RETRY" and len(emitted) == 1                          # local notice always written
    assert alerts.deliver(s, {"webhook": webhook}, now=1030, emit=lambda *a, **k: emitted.append(a)) == []  # backoff
    r2 = alerts.deliver(s, {"webhook": webhook}, now=1020 + 3600, emit=lambda *a, **k: emitted.append(a))
    assert r2[0]["state"] == "DELIVERED" and len(sent) == 1 and len(emitted) == 1  # retry re-sends adapter only
    log = alerts.notice_log()
    assert oct(log.stat().st_mode & 0o777) == "0o600"
    lines = log.read_text().splitlines()
    assert len(lines) == 1 and CANARY not in log.read_text() and CANARY not in json.dumps(sent)
    with s.tx() as c:                                                               # same fact inside the window
        assert alerts.enqueue(c, "dlq:x", "WARN", {}, now=1020 + 3600 + 10)[1] == "counted"
    with s.tx() as c:                                                               # still open after the window
        assert alerts.enqueue(c, "dlq:x", "WARN", {}, now=1020 + 3600 + 10 + 901)[1] == "rearmed"
    alerts.deliver(s, {}, now=10_000, emit=lambda *a, **k: None)
    assert len(log.read_text().splitlines()) == 2 and alerts.notifications(s)[0]["count"] == 4


@pytest.fixture()
def client(env):
    from forge_factory.dashboard.app import create_app, tokens
    from forge_factory.events.store import EventStore

    return TestClient(create_app(EventStore(), collect=False)), tokens()


def test_read_only_autonomy_api_with_roles_pagination_and_no_writes(env, client):
    c, toks = client
    V, A = {"Authorization": f"Bearer {toks['viewer']}"}, {"Authorization": f"Bearer {toks['auditor']}"}
    assert c.get("/api/v1/afo/summary").status_code == 401
    assert c.get("/api/v1/afo/summary", headers=V).json()["store"] == "absent"
    assert not Store.__init__ or not (Path(os.environ["FORGE_STATE_DIR"]) / "conductor/conductor.sqlite3").exists()
    s = Store()
    oids = [_blocked(s, env, f"RCC-API-{i}") for i in range(3)]
    deadletter.sweep(s)
    s.set_control("paused", "0", "op", "init")
    before = s.path.read_bytes()
    o = c.get("/api/v1/afo/orders?limit=2", headers=V).json()
    assert len(o["items"]) == 2 and o["next_cursor"] == "2"
    assert len(c.get("/api/v1/afo/orders?limit=2&cursor=2", headers=V).json()["items"]) == 1
    assert c.get("/api/v1/afo/orders?state=bad", headers=V).status_code == 422
    d = c.get(f"/api/v1/afo/orders/{oids[0]}", headers=V).json()
    assert d["order"]["state"] == "BLOCKED" and set(d["dead_letters"][0]) == {"case_id", "reason_code",
                                                                            "required_action", "state"}
    assert "artifact_refs" in c.get(f"/api/v1/afo/orders/{oids[0]}", headers=A).json()["dead_letters"][0]
    assert c.get("/api/v1/afo/orders/../../etc", headers=V).status_code in (404, 422)
    assert c.get("/api/v1/afo/orders/afo-00000000", headers=V).status_code == 404
    assert len(c.get("/api/v1/afo/dead-letters", headers=V).json()["items"]) == 3
    assert c.get("/api/v1/afo/operations", headers=V).json()["operator_actions"] == []        # auditor only
    assert c.get("/api/v1/afo/operations", headers=A).json()["operator_actions"][0]["actor"] == "op"
    assert c.get("/api/v1/afo/proposals", headers=V).json()["items"] == []
    assert s.path.read_bytes() == before                                             # reads changed nothing


def test_operator_controls_need_the_operator_token_and_every_denial_is_audited(env, client):
    """T058 / T061 (AT-014/053/054): unauthenticated, viewer/auditor bearer and cookie-session requests are refused
    and audited; the operator token pauses, drains and resumes; no other write endpoint exists."""
    c, toks = client
    s = Store()
    r = c.post("/api/v1/afo/operator/pause", json={"reason": "x"})
    assert r.status_code == 401
    for t in (toks["viewer"], toks["auditor"], "forged-token"):
        assert c.post("/api/v1/afo/operator/pause", json={"reason": "x"},
                      headers={"Authorization": f"Bearer {t}"}).status_code == 403
    c.cookies.set("forge_dashboard_session", toks["auditor"])                      # a browser session is not enough
    assert c.post("/api/v1/afo/operator/resume", json={"reason": "x"}).status_code == 401
    c.cookies.clear()
    denied = [a for a in F.operations(auditor=True)["operator_actions"] if a["action"].startswith("denied:")]
    assert len(denied) == 5 and {a["actor"] for a in denied} == {"anonymous", "bearer", "cookie-session"}
    assert s.control().get("paused") in (None, "0")
    op = {"Authorization": f"Bearer {F.issue_operator_token()}"}
    assert c.post("/api/v1/afo/operator/pause", json={}, headers=op).status_code == 422   # reason required
    assert c.post("/api/v1/afo/operator/pause", json={"reason": "maintenance"}, headers=op).json()["control"]["paused"] == "1"
    assert c.post("/api/v1/afo/operator/drain", json={"reason": "drain"}, headers=op).json()["control"]["draining"] == "1"
    assert c.post("/api/v1/afo/operator/resume", json={"reason": "done"}, headers=op).json()["control"] == {
        "paused": "0", "draining": "0"}
    assert c.post("/api/v1/afo/operator/retry", json={"reason": "x"}, headers=op).status_code == 404
    assert oct(F.operator_token_path().stat().st_mode & 0o777) == "0o600"
    for path in ("/api/v1/afo/orders", "/api/v1/afo/summary", "/api/v1/events", "/api/v1/afo/dead-letters"):
        assert c.post(path, json={"type": "afo.forged"}, headers=op).status_code == 405  # no forged writes
    acts = [a["action"] for a in F.operations(auditor=True)["operator_actions"]]
    assert {"paused=1", "draining=1", "paused=0", "draining=0"} <= set(acts)
    oid = _blocked(s, env, "RCC-AUDIT")
    deadletter.record_case(s, oid)
    c2 = sqlite3.connect(s.path, isolation_level=None)
    with pytest.raises(sqlite3.DatabaseError, match="IMMUTABLE_DEAD_LETTER"):        # audit kept: DLQ append-only
        c2.execute("DELETE FROM afo_dead_letters")
    c2.close()


def test_autonomy_view_is_wired_to_existing_endpoints():
    from forge_factory.dashboard.app import STATIC, create_app

    html = (STATIC / "index.html").read_text()
    assert "Autonomy (feature 005 AFO" in html and "loadAutonomy();" in html
    used = {"/api/v1/" + p for p in ("afo/summary", "afo/orders", "afo/dead-letters", "afo/proposals", "afo/operations")}
    routes = {r.path for r in create_app(collect=False).routes}
    assert used <= routes and "/api/v1/afo/orders/{oid}" in routes
    assert "operator/" not in html.split("loadAutonomy")[1].split("const FRONT")[0].replace("operator token", "")


def test_release_package_carries_afo_evidence_only_for_afo_attempts(env, tmp_path):
    """T059 (AT-037/056): READY/BLOCKED decided by the packager; an AFO attempt's archive adds hashed queue,
    attempt, plan, checkpoint, event and service-context records; a non-AFO work order gets nothing new."""
    from forge_factory.release import finalize as FIN
    from test_m7_governance_release import complete_workspace

    s = Store()
    oid, _ = s.submit(_env(env, rid="RCC-PKG", name="pkg"), repo=env, max_queued=50)
    epoch = s.acquire_lease("scheduler", "A", 60)
    aid = s.admit(oid, epoch=epoch, scope="scheduler", policy_sha256="p" * 64, authorization_id="AUTH-1",
                  max_concurrent=1)
    s.attempt_transition(aid, "DISPATCH_PENDING", workspace_ref="workorder:WO-AFO-PKG")
    plain = tmp_path / "WO-PLAIN" / "workspace"
    afo = tmp_path / "WO-AFO-PKG" / "workspace"
    for w in (plain, afo):
        w.mkdir(parents=True)
        complete_workspace(w)
    p1, p2 = FIN.finalize(plain, "WO-PLAIN"), FIN.finalize(afo, "WO-AFO-PKG")
    assert p1["package_status"] == p2["package_status"]                             # status never changed by AFO
    with zipfile.ZipFile(p1["archive"]) as z:
        assert not [n for n in z.namelist() if "/operations/afo/" in n]
    with zipfile.ZipFile(p2["archive"]) as z:
        names = [n for n in z.namelist() if "/operations/afo/" in n]
        idx = json.loads(z.read(next(n for n in names if n.endswith("/index.json"))))
        from forge_factory.common import sha256_bytes

        for name, sha in idx["files"].items():
            assert sha256_bytes(z.read(next(n for n in names if n.endswith("/operations/afo/" + name)))) == sha
        ctx = json.loads(z.read(next(n for n in names if n.endswith("service-context.json"))))
    assert idx["order_id"] == oid and idx["attempt_id"] == aid and ctx["policy_sha256"] == "p" * 64
    assert {"attempts.jsonl", "recovery-plans.jsonl", "checkpoints.jsonl", "lifecycle-events.jsonl",
            "dead-letters.jsonl", "service-context.json", "order.json"} == set(idx["files"])
    s.transition(oid, "RUNNING", "t")
    s.transition(oid, "BLOCKED", "package BLOCKED / BLOCKED, 1 gaps", terminal_reason="package BLOCKED / BLOCKED")
    cid, _ = deadletter.record_case(s, oid, ws=afo)
    refs = deadletter.cases(s)[0]["record"]["artifact_refs"]
    assert any(r.startswith("package-record:") for r in refs) and any(r.startswith("archive:") for r in refs)
