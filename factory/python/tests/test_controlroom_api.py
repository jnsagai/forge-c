"""CR-T010/CR-T011: Control Room API - auth, read-only routes, page, SSE delivery latency (SC-001)."""
import json
import threading
import time

import pytest
from controlroom_fixtures import CFG, FakeProbe, append, passed, workspace
from fastapi.testclient import TestClient
from forge_factory.controlroom.floor import Floor


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    from forge_factory.controlroom import config as C
    from forge_factory.dashboard.app import create_app, tokens

    monkeypatch.setattr(C, "load", lambda path=None: dict(CFG))
    root = tmp_path / "wo"
    root.mkdir()
    app = create_app(collect=False, control_room_floor=Floor(root=root, probe=FakeProbe()))
    c = TestClient(app)
    c.root, c.tok = root, tokens()["viewer"]
    return c


def _h(c):
    return {"Authorization": f"Bearer {c.tok}"}


def test_floor_needs_auth_and_returns_a_snapshot(client):
    assert client.get("/api/v1/control-room/floor").status_code == 401
    workspace(client.root, "WO-A-r1", passed("SWE.1", 1))
    s = client.get("/api/v1/control-room/floor", headers=_h(client)).json()
    assert s["schema"] == "forge-c/control-room-floor/0.1" and s["units"][0]["station"] == "SWE.2"


def test_page_is_served_and_embeds_the_first_snapshot_only_when_signed_in(client):
    r = client.get("/control-room")
    assert r.status_code == 200 and "Forge-C Control Room" in r.text and "window.__INIT__=" not in r.text
    client.cookies.set("forge_dashboard_session", client.tok)
    assert "window.__INIT__=" in client.get("/control-room").text


def test_control_room_routes_are_read_only(client):
    routes = [r for r in client.app.routes if getattr(r, "path", "").startswith("/api/v1/control-room")]
    assert routes and all(set(r.methods) <= {"GET", "HEAD"} for r in routes)


def test_login_redirects_only_to_known_pages(client):
    r = client.get(f"/login?token={client.tok}&next=/control-room", follow_redirects=False)
    assert r.headers["location"] == "/control-room"
    r = client.get(f"/login?token={client.tok}&next=https://evil.example", follow_redirects=False)
    assert r.headers["location"] == "/"


def _serve(app):
    """A real loopback server: the TestClient buffers a streaming body, so latency is measured over HTTP."""
    import socket

    import uvicorn

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    return srv, port


def test_stream_delivers_floor_changes_within_5_seconds(client):
    """SC-001: >= 95 % of recorded station changes reach the stream within 5 s (20 trials keep the suite short;
    the 100-event run is CR-T044 evidence)."""
    import httpx

    srv, port = _serve(client.app)
    ws = workspace(client.root, "WO-S-r1", [])
    latencies, seen = [], []

    def writer():
        time.sleep(1.5)
        for i in range(20):
            p = "SWE.1"  # one station whose recorded reason changes on every row
            t0 = time.monotonic()
            append(ws, {"phase": p, "step": "route", "gate": {"decision": "REWORK", "reason": f"R{i}"}, "ts": "2026-10-19T10:00:00Z"})
            while len(seen) <= i and time.monotonic() - t0 < 8:
                time.sleep(0.05)
            latencies.append(time.monotonic() - t0)

    th = threading.Thread(target=writer)
    with httpx.stream("GET", f"http://127.0.0.1:{port}/api/v1/control-room/stream?max_seconds=60", headers=_h(client),
                      timeout=30) as r:
        th.start()
        ev = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                ev = line[7:]
            elif line.startswith("data: ") and ev == "floor":
                d = json.loads(line[6:])
                reasons = [st["reason"] for st in d["stations"] if st["reason"]]
                if reasons and reasons[0].startswith("R") and (not seen or seen[-1] != reasons[0]):
                    seen.append(reasons[0])
                if len(seen) >= 20:
                    break
            elif line.startswith("data: ") and ev == "heartbeat":
                assert "data_age_s" in json.loads(line[6:])
            if not th.is_alive() and len(latencies) >= 20:
                break
    th.join(10)
    srv.should_exit = True
    within = sum(1 for x in latencies if x <= 5.0)
    assert len(latencies) == 20 and within >= 19, latencies
