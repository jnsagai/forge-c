"""Opt-in LOCAL CONTROL only: real systemd startup fencing and deliberate stop.

Never installs/enables units or targets an existing name. Empty Fabro replay + OBSERVE/private state means no
model, native child, grant or product work. This does not qualify production deployment/timer/endurance.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest

from forge_factory.afo import operations
from forge_factory.afo.durable import immutable_json
from forge_factory.common import REPO_ROOT


@pytest.mark.skipif(os.environ.get("FORGE_LINE_BOOT_SYSTEMD_CONTROL") != "1", reason="opt-in disposable LOCAL systemd CONTROL")
def test_private_public_line_boot_fence_and_explicit_os_stop(tmp_path):
    # Fail visibly if explicitly requested but the user manager is unavailable; no fake systemd fallback.
    commands = []

    def call(argv):
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        commands.append({"argv": argv, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        return result

    assert call(["systemctl", "--user", "show", "--property=Version"]).returncode == 0
    output = Path(os.environ["FORGE_LINE_BOOT_SYSTEMD_OUT"])
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    names = []

    def state(name):
        result = call(["systemctl", "--user", "show", name,
                       "--property=ActiveState,SubState,MainPID,NRestarts,Result,ExecMainStatus,UnitFileState"])
        assert result.returncode == 0, result.stderr
        return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)

    def wait(name, predicate):
        until = time.monotonic() + 12
        observations = []
        while time.monotonic() < until:
            current = state(name)
            observations.append(current)
            if predicate(current):
                return current, observations
            time.sleep(0.1)
        pytest.fail("DISPOSABLE_UNIT_CONTROL_TIMEOUT:" + json.dumps(observations[-4:]))

    try:
        for initial in ("STOPPED", "UNKNOWN"):
            root = tmp_path / initial
            private = root / "private"
            private.mkdir(parents=True, mode=0o700)
            intent = operations.Intent(private / "intent.json")
            if initial == "STOPPED":
                intent.set(initial, actor="CONTROL", reason="CONTROL", initialize=True)
            snapshot = root / "empty-fabro.json"
            snapshot.write_text("{}")
            line_state = root / "line-state"
            name = f"forge-c-014-qual-{uuid.uuid4().hex[:12]}-boot.service"
            names.append(name)
            properties = ["Type=notify", "NotifyAccess=main", "Restart=always", "RestartPreventExitStatus=77",
                          "RestartSec=100ms", "WatchdogSec=5", "TimeoutStartSec=10", "KillMode=process",
                          "StartLimitIntervalSec=30", "StartLimitBurst=5", "LimitCORE=0"]
            argv = ["systemd-run", "--user", "--quiet", "--no-block", "--unit", name]
            for prop in properties:
                argv.extend(["--property", prop])
            for key, value in {"PYTHONPATH": str(REPO_ROOT / "factory/python"), "FORGE_REPO_ROOT": str(REPO_ROOT),
                               "FORGE_DATA_ROOT": str(root / "data"), "FORGE_STATE_DIR": str(line_state),
                               "FORGE_OPERATIONS_INTENT": str(intent.path), "PYTHONDONTWRITEBYTECODE": "1"}.items():
                argv.extend(["--setenv", key + "=" + value])
            command = [sys.executable, "-m", "forge_factory.afo.line_conductor", "--mode", "OBSERVE", "--line", "local",
                       "--interval", "0.1", "--fabro-snapshot", str(snapshot), "--launch-dir", str(root / "launch")]
            result = call([*argv, *command])
            assert result.returncode == 0, result.stderr
            blocked, observations = wait(name, lambda s: s.get("ActiveState") == "failed")
            time.sleep(0.3)
            assert state(name)["NRestarts"] == "0" and blocked["ExecMainStatus"] == "77"
            assert not line_state.exists()
            rows.append({"case": initial + "_BOOT_FENCED", "pass": True, "unit": name, "observations": observations})
            intent.set("RUNNING", actor="CONTROL", reason="CONTROL explicit resume", initialize=(initial == "UNKNOWN"))
            assert call(["systemctl", "--user", "start", name]).returncode == 0
            active, observations = wait(name, lambda s: s.get("ActiveState") == "active")
            heartbeat = json.loads((line_state / "supervisor/line-conductor.heartbeat").read_bytes())
            feed = json.loads((line_state / "supervisor/issues.json").read_bytes())
            assert heartbeat["pid"] == int(active["MainPID"]) and heartbeat["ok"] is True
            assert feed["supervisor"]["model_calls_healthy"] == 0 and "placement" not in feed
            assert call(["systemctl", "--user", "stop", name]).returncode == 0
            stopped, stopped_obs = wait(name, lambda s: s.get("ActiveState") == "inactive")
            time.sleep(0.3)
            assert state(name)["ActiveState"] == "inactive" and state(name)["NRestarts"] == "0"
            # Replay the actual stopped state through the existing recipe. It must not undo the OS stop.
            outcome = intent.start(intent.read()["epoch"], probe=lambda: stopped, authorize=lambda: True,
                                   runner=lambda _argv: pytest.fail("explicit stop cannot recover"),
                                   unit="forge-line-conductor-local.service")
            assert outcome["action"] == "NO_APPROVED_RECOVERY"
            rows.append({"case": initial + "_RESUME_THEN_OS_STOP", "pass": True, "unit": name,
                         "observations": observations, "stopped": stopped_obs, "recovery": outcome})
    finally:
        for name in names:
            call(["systemctl", "--user", "stop", name])
            call(["systemctl", "--user", "reset-failed", name])  # disposable test names only, never the real unit
        immutable_json(output / "report.json", {"scope": "LOCAL_DISPOSABLE_SYSTEMD_CONTROL", "rows": rows, "commands": commands,
                       "status": "PASS" if len(rows) == 4 and all(row["pass"] for row in rows) else "FAIL",
                       "production_timer_recovery_and_endurance": "NOT_RUN"})
