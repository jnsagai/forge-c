"""Execute the installed shell guard against synthetic host probes; no real host mutation."""
import os
from pathlib import Path
import subprocess

import pytest


GUARD = Path(__file__).resolve().parents[3] / "deploy/omniverse2/guard-line.sh"


@pytest.mark.parametrize(
    "patch,pid,active,age,expected",
    [
        ({}, 12, "active", 30, "OK"),
        ({}, 13, "active", 30, "M3_PID_MISMATCH"),
        ({}, 12, "inactive", 30, "M3_UNIT_INACTIVE"),
        ({"mode": "OBSERVE"}, 12, "active", 30, "M3_NOT_HEALTHY_PILOT"),
        ({"ok": False}, 12, "active", 30, "M3_NOT_HEALTHY_PILOT"),
        ({}, 12, "active", 181, "M3_HEARTBEAT_STALE"),
        ({}, 12, "active", -1, "M3_HEARTBEAT_STALE"),
        ({"epoch": "bad"}, 12, "active", 30, "M3_HEARTBEAT_STALE"),
        ({"pid": "12"}, 12, "active", 30, "M3_PID_MISMATCH"),
    ],
)
def test_heartbeat_requires_current_healthy_unit(patch, pid, active, age, expected):
    source = GUARD.read_text().split("<<'PYGUARD'\n", 1)[1].split("\ntry:\n", 1)[0]
    ns = {}
    exec(compile(source, str(GUARD), "exec"), ns)
    heartbeat = {"pid": 12, "mode": "PILOT", "ok": True, "epoch": 1000} | patch
    assert ns["check_heartbeat"](heartbeat, pid, active, 1000 + age) == expected


@pytest.mark.parametrize(
    "failure,expected",
    [(None, "OK"), ("pending", "GPUQ_PENDING_NOT_EMPTY"),
     ("running", "GPUQ_RUNNING_NOT_EMPTY"), ("gpu", "FOREIGN_GPU_PROCESS:99"),
     ("intent1", "AFO_INTENT_CHANGED"), ("intent2", "PRODUCTION_INTENT_CHANGED"),
     ("heartbeat", "CONDUCTOR_HEARTBEAT_CHANGED:M3_HEARTBEAT_UNAVAILABLE")],
)
def test_full_shell_guard_preserves_host_exclusion_checks(tmp_path, failure, expected):
    # Rewrite only fixed host paths into the fixture; production accepts no environment overrides.
    text = GUARD.read_text()
    paths = {
        "/mnt/data/forge-c/inspector-014-b309039/gpuq": tmp_path / "queue",
        "/mnt/data/forge-c/swe1-fabro-20261031/lrtx/state/supervisor/line-conductor.heartbeat": tmp_path / "heartbeat",
        "/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/control/operations.json": tmp_path / "intent1",
        "/home/omniverse2/.local/state/forge-c-production-014/operations.json": tmp_path / "intent2",
    }
    for old, new in paths.items():
        text = text.replace(old, str(new))
    for name in ("pending", "running"):
        directory = tmp_path / "queue" / name
        directory.mkdir(parents=True)
        if failure == name:
            (directory / "work").touch()
    (tmp_path / "heartbeat").write_text("{}")
    for name in ("intent1", "intent2"):
        (tmp_path / name).write_text("changed" if failure == name else name)
    tools = tmp_path / "bin"
    tools.mkdir()
    scripts = {
        "python3": "printf '%s\\n' " + ("M3_HEARTBEAT_UNAVAILABLE" if failure == "heartbeat" else "OK"),
        "nvidia-smi": "printf '%s\\n' " + ("99" if failure == "gpu" else "12"),
        "sha256sum": "read -r value; case $value in intent1) echo 9eff2df365375ae5eeae327dcd2bfefb440f14d100196a6dc1caee5b28f4d545;; intent2) echo 1387fbb25538882a981b90ec6169f563dd88b4e0943ce49c402f59f90947e63c;; *) echo bad;; esac",
    }
    for name, body in scripts.items():
        target = tools / name
        target.write_text("#!/bin/bash\n" + body + "\n")
        target.chmod(0o755)
    script = tmp_path / "guard.sh"
    script.write_text(text)
    result = subprocess.run(["bash", str(script), "12"], env=os.environ | {"PATH": str(tools) + ":/usr/bin:/bin"},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert result.stdout.strip() == ("OK" if failure is None else "FAIL:" + expected)
