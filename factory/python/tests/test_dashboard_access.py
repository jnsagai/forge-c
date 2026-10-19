"""OD-2026-10-19-09: dashboard sign-in can be switched off until deployment - anonymous role on loopback only,
operator actions still need the operator token, invalid settings fail closed to token mode."""
import pytest
from fastapi.testclient import TestClient
from forge_factory.dashboard import access as A


@pytest.fixture()
def app_off(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_DASHBOARD_AUTH", "disabled")
    from forge_factory.controlroom.floor import Floor
    from forge_factory.controlroom.scorecard import EventCache
    from forge_factory.dashboard.app import create_app

    app = create_app(collect=False, control_room_floor=Floor(root=tmp_path / "wo"),
                     control_room_events=EventCache(root=tmp_path / "wo"))
    c = TestClient(app, client=("127.0.0.1", 50000))      # a browser on this machine
    c.remote = TestClient(app, client=("100.87.10.79", 50001))  # the phone over Tailscale
    return c


def test_disabled_sign_in_serves_the_anonymous_role_without_a_token(app_off):
    me = app_off.get("/api/v1/me").json()
    assert me["role"] == "viewer" and me["auth"] == "disabled" and "security" not in me["channels"]
    assert app_off.get("/api/v1/control-room/floor").status_code == 200
    page = app_off.get("/control-room").text
    assert 'window.__INIT__=' in page and '"auth": "disabled"' in page


def test_a_valid_token_still_gives_its_own_role(app_off):
    from forge_factory.dashboard.app import tokens

    me = app_off.get("/api/v1/me", headers={"Authorization": f"Bearer {tokens()['auditor']}"}).json()
    assert me["role"] == "auditor" and "audit" in me["channels"]


def test_operator_actions_still_need_the_operator_token(app_off):
    r = app_off.post("/api/v1/afo/operator/pause", json={"reason": "x"})
    assert r.status_code in (401, 403)


def test_token_mode_still_requires_sign_in(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    from forge_factory.dashboard.app import create_app

    c = TestClient(create_app(collect=False))
    assert c.get("/api/v1/me").status_code == 401


def test_other_devices_always_need_a_token(app_off):
    from forge_factory.dashboard.app import tokens

    assert app_off.remote.get("/api/v1/control-room/floor").status_code == 401
    assert "window.__INIT__=" not in app_off.remote.get("/control-room").text       # shows the sign-in box
    tok = tokens()["viewer"]
    r = app_off.remote.get(f"/login?token={tok}&next=/control-room", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/control-room"
    assert app_off.remote.get("/api/v1/control-room/floor", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


def test_invalid_setting_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("FORGE_DASHBOARD_AUTH", "maybe")
    a = A.load()
    assert a["auth"] == "token" and a["error"]
    monkeypatch.delenv("FORGE_DASHBOARD_AUTH")
    monkeypatch.setattr(A, "CONFIG", tmp_path / "missing.yaml")
    assert A.load()["auth"] == "token"
    assert A.anonymous_role({"auth": "disabled", "anonymous_role": "viewer"}, "127.0.0.1") == "viewer"
    assert A.anonymous_role({"auth": "disabled", "anonymous_role": "viewer"}, "192.168.1.50") is None
    assert A.anonymous_role({"auth": "token", "anonymous_role": "viewer"}, "127.0.0.1") is None


def test_committed_config_is_off_until_deployment(monkeypatch):
    monkeypatch.delenv("FORGE_DASHBOARD_AUTH")
    a = A.load()
    assert a["auth"] == "disabled" and a["anonymous_role"] == "viewer" and a["decision"] == "OD-2026-10-19-09"
