"""T024: supervisor under systemd (user) watchdog — SIGKILL -> OS restart; incident DB stays valid."""
import json
import os
import signal
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest

UNIT = "forge-supervisor.service"


def prop(name: str) -> str:
    return subprocess.run(["systemctl", "--user", "show", UNIT, f"--property={name}", "--value"], capture_output=True,
                          text=True, check=True).stdout.strip()


@pytest.mark.skipif(os.environ.get("FORGE_SYSTEMD_LIVE") != "1", reason="live systemd test disabled")
def test_sigkill_restarts_and_db_integrity():
    assert prop("ActiveState") == "active" and prop("Type") == "notify" and prop("Restart") == "always"
    assert prop("WatchdogUSec") not in ("0", "", "infinity")
    pid = int(prop("MainPID"))
    restarts = int(prop("NRestarts") or 0)
    os.kill(pid, signal.SIGKILL)
    deadline = time.time() + 60
    new = pid
    while time.time() < deadline:
        time.sleep(1)
        if prop("ActiveState") == "active" and int(prop("MainPID") or 0) not in (0, pid):
            new = int(prop("MainPID"))
            break
    assert new != pid and int(prop("NRestarts")) == restarts + 1
    home = Path(os.environ["FORGE_STATE_DIR"]) / "supervisor"
    before = json.loads((home / "checkpoint.json").read_text())["polls"]
    deadline = time.time() + 90
    while time.time() < deadline and json.loads((home / "checkpoint.json").read_text())["polls"] <= before:
        time.sleep(2)
    assert json.loads((home / "checkpoint.json").read_text())["polls"] > before  # resumed counting after restart
    c = sqlite3.connect(home / "incidents.sqlite3")
    assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    health = json.loads((home / "health.json").read_text())
    assert health["model_calls"] == 0 and health["model_tokens"] == 0
