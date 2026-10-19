"""OD-2026-10-19-09: dashboard sign-in can be switched off until deployment - anonymous role on loopback only,
operator actions still need the operator token, invalid settings fail closed to token mode.
OD-2026-10-19-10: the owner's trusted devices (Tailscale address) need no token either, over Tailscale only."""
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
    assert a["auth"] == "disabled" and a["anonymous_role"] == "viewer" and a["decision"] == "OD-2026-10-19-10"
    assert a["trusted"] == {PHONE: "s22-ultra-de-jefferson"} and a["error"] is None


PHONE, TAILSCALE, WIFI = "100.73.215.92", "100.87.10.79", "192.168.1.69"


def _client(app_off, client, server):
    return TestClient(app_off.app, client=(client, 50002), base_url=f"http://{server}:8765")


def test_trusted_phone_over_tailscale_needs_no_token(app_off):
    phone = _client(app_off, PHONE, TAILSCALE)
    assert phone.get("/api/v1/me").json()["role"] == "viewer"
    assert phone.get("/api/v1/control-room/floor").status_code == 200
    assert "window.__INIT__=" in phone.get("/control-room").text
    assert phone.post("/api/v1/afo/operator/pause", json={"reason": "x"}).status_code in (401, 403)


def test_only_listed_devices_and_only_over_tailscale(app_off):
    assert _client(app_off, "100.101.102.103", TAILSCALE).get("/api/v1/control-room/floor").status_code == 401
    assert _client(app_off, "192.168.1.74", WIFI).get("/api/v1/control-room/floor").status_code == 401
    # the phone's address arriving on the Wi-Fi listen address is not trusted (not a Tailscale connection)
    assert _client(app_off, PHONE, WIFI).get("/api/v1/control-room/floor").status_code == 401


def test_token_mode_also_signs_in_the_trusted_phone(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    from forge_factory.dashboard.app import create_app

    phone = TestClient(create_app(collect=False), client=(PHONE, 50003), base_url=f"http://{TAILSCALE}:8765")
    assert phone.get("/api/v1/me").status_code == 401


@pytest.mark.parametrize("devices", [[{"name": "lan", "address": "192.168.1.74"}], [{"address": PHONE}],
                                     [{"name": "x", "address": "not-an-ip"}], "100.73.215.92"])
def test_invalid_trusted_devices_fail_closed(monkeypatch, tmp_path, devices):
    import yaml

    monkeypatch.delenv("FORGE_DASHBOARD_AUTH")
    cfg = tmp_path / "access.yaml"
    cfg.write_text(yaml.safe_dump({"auth": "disabled", "anonymous_role": "viewer", "trusted_devices": devices}))
    monkeypatch.setattr(A, "CONFIG", cfg)
    a = A.load()
    assert a["auth"] == "token" and a["error"] and A.anonymous_role(a, PHONE, TAILSCALE) is None
