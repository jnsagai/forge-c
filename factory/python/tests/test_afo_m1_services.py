"""AFO M1 (T007-T013; AT-001..AT-009): fail-closed data-volume preflight, rendered units with bounded restarts and the
preflight, Conductor heartbeat only after completed cycles, external watchdog alerting with dedup."""
import json

import pytest
from forge_factory.afo import conductor, host, policy, services, watchdog

VOL = {"target": "/media/x/vol", "source": "/dev/loop10", "fstype": "ext4", "uuid": "U-1"}
ROOTFS = {"target": "/", "source": "/dev/nvme0n1p6", "fstype": "ext4", "uuid": "R-1"}


@pytest.fixture()
def vol(tmp_path, monkeypatch):
    root = tmp_path / "data"
    (root / "state").mkdir(parents=True)
    fs = {"cur": VOL}
    monkeypatch.setattr(host, "fs_info", lambda p: ROOTFS if str(p) == "/" else fs["cur"])
    return root, fs


def test_preflight_passes_only_on_the_recorded_volume(vol):
    root, fs = vol
    r = host.preflight(root)
    assert not r["ok"] and r["issues"][0].startswith("SENTINEL_MISSING_OR_INVALID")
    host.init(root)
    assert host.preflight(root)["ok"]
    fs["cur"] = {**VOL, "uuid": "OTHER"}                                     # another volume mounted there
    assert host.preflight(root)["issues"][0].startswith("VOLUME_UUID_MISMATCH")
    fs["cur"] = ROOTFS                                                       # volume not mounted: root fs
    r = host.preflight(root)
    assert not r["ok"] and r["issues"][0].startswith("DATA_ROOT_ON_ROOT_FS")
    with pytest.raises(SystemExit):
        host.init(root)                                                       # refuses to bless the root fs
    assert not host.preflight(root.parent / "absent")["ok"]


def test_rendered_units_are_complete_bounded_and_preflighted():
    units = services.render()
    assert set(units) == set(services.UNITS)
    for name, text in units.items():
        assert not [w for w in text.split() if w.startswith("@") and w.endswith("@")], name
        if name.endswith(".service") and name != "forge-afo-watchdog.service":
            assert "Restart=on-failure" in text and "StartLimitBurst=5" in text, name
            assert "RequiresMountsFor=" in text and "forge_factory.afo.host preflight" in text, name
    c = units["forge-conductor.service"]
    assert "Type=notify" in c and "WatchdogSec=120" in c and "NotifyAccess=main" in c
    assert "pkill" not in "".join(units.values())                             # never a process-name pattern
    assert services.verify(units)["ok"]


def test_units_put_the_forge_llvm_toolchain_first_on_path(tmp_path, monkeypatch):
    """Feature 015: AFO runs inherit the Conductor's PATH; without the toolchain forge-env.sh adds, the host clang 12
    rejected -fcoverage-mcdc (WO-AFO-707cd2711fc865be-a1 DEF-003, coverage BLOCKED)."""
    llvm = tmp_path / "llvm/bin"
    llvm.mkdir(parents=True)
    (llvm / "clang").write_text("#!/bin/sh\n")
    (llvm / "clang").chmod(0o755)
    monkeypatch.setenv("FORGE_LLVM_BIN", str(llvm))
    path = services.values()["@PATH@"].split(":")
    assert path[1] == str(llvm) and path.index(str(llvm)) < path.index("/usr/local/bin")
    assert f"Environment=PATH={':'.join(path)}" in services.render()["forge-conductor.service"]
    monkeypatch.setenv("FORGE_LLVM_BIN", str(tmp_path / "absent"))
    assert services.values()["@PATH@"].split(":")[1] == "/usr/local/bin"  # no toolchain: the host PATH as before


def test_conductor_heartbeat_follows_completed_cycles(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    assert conductor.Conductor(0.1, max_cycles=2).run() == 0
    hb = json.loads(conductor.heartbeat_path().read_text())
    assert hb["cycle"] == 1 and hb["ok"] and hb["mode"] == policy.load().mode  # the effective mode (PILOT while the
    # shipped owner authorization is valid, OBSERVE_ONLY otherwise)
    monkeypatch.setattr(conductor, "cycle", lambda n: (_ for _ in ()).throw(RuntimeError("db locked")))
    conductor.Conductor(0.1, max_cycles=1).run()
    hb = json.loads(conductor.heartbeat_path().read_text())
    assert not hb["ok"] and "db locked" in hb["detail"]


def test_watchdog_alerts_once_per_window(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    assert watchdog.check(300)["code"] == "HEARTBEAT_MISSING"
    conductor.write_heartbeat(5, "OBSERVE_ONLY", True)
    assert watchdog.check(300)["ok"]
    stale = watchdog.check(300, now=__import__("time").time() + 1000)
    assert stale["code"] == "HEARTBEAT_STALE"
    assert watchdog.alert(stale, 900, now=1000.0) and not watchdog.alert(stale, 900, now=1500.0)
    assert watchdog.alert(stale, 900, now=2000.0)                            # after the window: alert again
    conductor.write_heartbeat(6, "OBSERVE_ONLY", False, "cycle error")
    assert watchdog.check(300)["code"] == "CYCLE_FAILED"
