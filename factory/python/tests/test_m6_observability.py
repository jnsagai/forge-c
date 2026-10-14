"""M6 (T034–T041, AT-18..21): events, capture policy, redaction, dashboard API/UI, SSE, token metrics."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from forge_factory.common import CONFIG_DIR
from forge_factory.events import policy as POL
from forge_factory.events.emit import emit
from forge_factory.events.store import Collector, EventStore, normalize_fabro

FIX = Path(__file__).parent / "fixtures"
CANARY = "ghp_CANARYsecretTOKEN0123456789abcdefABCD"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    return tmp_path


class FakeFabro:
    def __init__(self):
        self.evs = [json.loads(x) for x in (FIX / "fabro-0.362-probe-events.jsonl").read_text().splitlines()]

    def iter_events(self, run_id, since_seq=0, page=200):
        return [e for e in self.evs if e["seq"] > since_seq]


# ---------------- T034 -----------------------------------------------------------------------------------
def test_t034_replay_is_idempotent_and_ordered(env):
    for i in range(30):
        emit("workflow", "INFO", f"step {i}", run_id="R1")
    st = EventStore()
    col = Collector(st)
    n1 = col.ingest_segment() + col.ingest_fabro_run("R-fabro", FakeFabro())
    st.set_offset(f"file:{env / 'state/events/factory-events.jsonl'}", 0)  # force a full replay
    st.set_offset("fabro:R-fabro", 0)
    n2 = col.ingest_segment() + col.ingest_fabro_run("R-fabro", FakeFabro())
    assert n1 > 30 and n2 == 0 and st.count() == n1  # identical unique set after replay
    items = st.query(["workflow"], "INFO", run_id="R1", limit=500)["items"]
    assert [e["message"] for e in items] == [f"step {i}" for i in range(30)]  # order preserved
    assert all(e["correlation_id"] == "R1" for e in items)


# ---------------- T035 -----------------------------------------------------------------------------------
def test_t035_audit_cannot_be_disabled_and_live_reload_rejects(env, tmp_path):
    doc = yaml.safe_load((CONFIG_DIR / "trace-policy.yaml").read_text())
    p = tmp_path / "trace.yaml"
    p.write_text(yaml.safe_dump(doc))
    holder = POL.PolicyHolder(p)
    assert holder.current().captures("audit", "INFO")
    bad = dict(doc, capture_levels={**doc["capture_levels"], "audit": "OFF", "tools": "TRACE"})
    p.write_text(yaml.safe_dump(bad))
    os.utime(p, (1, 1))
    pol = holder.current()
    assert holder.rejections and pol.levels["audit"] == "INFO" and pol.levels["tools"] == "WARN"  # old policy kept
    good = dict(doc, capture_levels={**doc["capture_levels"], "tools": "TRACE", "metrics": "OFF"})
    p.write_text(yaml.safe_dump(good))
    os.utime(p, (2, 2))
    pol = holder.current()
    assert pol.captures("tools", "TRACE") and not pol.captures("metrics", "INFO")  # per-channel change applied
    assert pol.captures("security", "WARN") and not pol.captures("security", "DEBUG")


def test_t035_display_filters_do_not_alter_capture(env):
    for ch in ("ai", "tools", "audit", "human"):
        emit(ch, "INFO", f"{ch} event")
    st = EventStore()
    Collector(st).ingest_segment()
    before = st.count()
    shown = st.query(["human"], "INFO")["items"]
    assert [e["channel"] for e in shown] == ["human"] and st.count() == before
    assert st.query(["audit"], "INFO")["items"]  # hidden in view, still queryable


# ---------------- T036 -----------------------------------------------------------------------------------
def test_t036_secret_canary_never_persisted_and_no_reasoning(env):
    emit("tools", "WARN", f"compiler said token={CANARY}", payload_ref=f"Bearer {CANARY}")
    st = EventStore()
    col = Collector(st)
    col.ingest_segment()
    fake = FakeFabro()
    fake.evs = fake.evs + [{"seq": 999, "id": "x-999", "ts": "2026-10-14T21:00:00Z", "run_id": "R2", "event": "agent.message",
                            "node_id": "n", "properties": {"event": {"AssistantMessage": {
                                "model": "qwen3:8b", "text": f"my key is {CANARY}", "reasoning": "secret thoughts",
                                "tool_call_count": 1, "usage": {"tokens": {"input": 10, "output": 5}}}}}}]
    col.ingest_fabro_run("R2", fake)
    raw = (st.path.read_bytes() + (env / "state/events/factory-events.jsonl").read_bytes())
    assert CANARY.encode() not in raw and b"secret thoughts" not in raw
    ai = [e for e in st.query(["ai"], "TRACE", limit=500)["items"] if e["run_id"] == "R2"]
    assert ai and ai[0]["model"] == "qwen3:8b" and ai[0]["input_tokens"] == 10 and "key" not in ai[0]["message"]


def test_t036_retention_purge_keeps_audit(env):
    from datetime import UTC, datetime, timedelta
    st = EventStore()
    pol = POL.load()
    old = (datetime.now(UTC) - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for ch in ("tools", "audit"):
        st.insert({"schema_version": "0.4", "event_id": f"old-{ch}", "ts_utc": old, "channel": ch, "level": "WARN",
                   "message": "old", "redacted": False, "correlation_id": "c"}, "t", pol)
    assert st.purge(pol) == 1 and st.count(event_id="old-audit") == 1 and st.count(event_id="old-tools") == 0


def test_t036_raw_ai_capture_is_opt_in(env):
    ev = {"seq": 1, "id": "a1", "ts": "2026-10-14T21:00:00Z", "run_id": "R", "event": "agent.message", "properties": {
        "event": {"AssistantMessage": {"model": "m", "text": "hello world", "usage": {"tokens": {"input": 1, "output": 1}}}}}}
    assert "hello" not in normalize_fabro(ev, raw_ai=False)["message"]
    assert normalize_fabro(ev, raw_ai=True)["message"] == "hello world"


# ---------------- T037/T039/T040/T041 dashboard ------------------------------------------------------------
@pytest.fixture()
def client(env):
    from forge_factory.dashboard.app import create_app, tokens
    for i in range(7):
        emit("human", "INFO", f"human {i}")
    emit("security", "WARN", "DENY shell")
    emit("audit", "INFO", "ALLOW read_file")
    st = EventStore()
    Collector(st).ingest_segment()
    app = create_app(st, collect=False)
    return TestClient(app), tokens()


def test_t037_auth_roles_and_pagination(client):
    c, t = client
    assert c.get("/api/v1/health").status_code == 401
    v = {"Authorization": f"Bearer {t['viewer']}"}
    a = {"Authorization": f"Bearer {t['auditor']}"}
    assert c.get("/api/v1/me", headers=v).json()["role"] == "viewer"
    sec_v = c.get("/api/v1/events?channel=security,audit&min_level=TRACE", headers=v).json()
    sec_a = c.get("/api/v1/events?channel=security,audit&min_level=TRACE", headers=a).json()
    assert sec_v["items"] == [] and {e["channel"] for e in sec_a["items"]} == {"security", "audit"}
    p1 = c.get("/api/v1/events?channel=human&limit=3", headers=v).json()
    p2 = c.get(f"/api/v1/events?channel=human&limit=3&after_id={p1['next_cursor']}", headers=v).json()
    assert [e["message"] for e in p1["items"] + p2["items"]] == [f"human {i}" for i in range(6)]
    assert c.get("/api/v1/events?q=human%203", headers=v).json()["items"][0]["message"] == "human 3"
    for ep in ("health", "runs", "agents", "mcp", "incidents", "lessons", "packages", "tokens"):
        r = c.get(f"/api/v1/{ep}", headers=a)
        assert r.status_code == 200, ep
    assert c.post("/api/v1/events", headers=a).status_code == 405  # read-only


def test_t040_sse_resumes_from_last_event_id_without_duplicates(client):
    c, t = client
    h = {"Authorization": f"Bearer {t['auditor']}", "Last-Event-ID": "3"}
    with c.stream("GET", "/api/v1/events/stream?channel=human&max_seconds=1", headers=h) as r:
        body = "".join(r.iter_text())
    ids = [int(x[4:]) for x in body.splitlines() if x.startswith("id: ")]
    assert ids and min(ids) > 3 and len(ids) == len(set(ids))


def test_t038_t039_ui_is_responsive_and_filters_display_only(client):
    c, t = client
    html = c.get("/").text
    assert 'name="viewport"' in html and "minmax(min(100%" in html and "display filters only" in html.lower()
    c.cookies.set("forge_dashboard_session", t["viewer"])
    authed = c.get("/").text
    assert "window.__INIT__" in authed and '"role": "viewer"' in authed and "localStorage" in authed


def test_t041_token_metrics_sum_and_basis(env, client):
    c, t = client
    meter = env / "state/llm-gateway/usage.jsonl"
    meter.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"tokens_input": 100, "tokens_output": 10, "basis": "reported"},
            {"tokens_input": 50, "tokens_output": 5, "basis": "reported"},
            {"tokens_input": None, "tokens_output": None, "basis": "unknown"}]
    meter.write_text("".join(json.dumps(r) + "\n" for r in rows))
    item = c.get("/api/v1/tokens", headers={"Authorization": f"Bearer {t['auditor']}"}).json()["items"][-1]
    assert (item["total_input"], item["total_output"], item["unknown_requests"], item["basis"]) == (150, 15, 1, "mixed")


@pytest.mark.skipif(os.environ.get("FORGE_BROWSER_LIVE") != "1" or not shutil.which("firefox"), reason="browser smoke off")
def test_t038_browser_smoke_mobile_and_desktop():
    tok = json.loads((Path(os.environ["FORGE_STATE_DIR"]) / "dashboard/tokens.json").read_text())["auditor"]
    out = Path.home() / "snap/firefox/common/forge-shots"
    prof = Path.home() / "snap/firefox/common/forge-dash-profile"
    out.mkdir(parents=True, exist_ok=True)
    for w in (390, 1280):
        png = out / f"smoke-{w}.png"
        png.unlink(missing_ok=True)
        subprocess.run(["firefox", "--headless", "--profile", str(prof), "--screenshot", str(png), f"--window-size={w},1400",
                        f"http://127.0.0.1:8765/login?token={tok}"], capture_output=True, timeout=120, check=False)
        data = png.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n" and int.from_bytes(data[16:20], "big") == w and len(data) > 20000
