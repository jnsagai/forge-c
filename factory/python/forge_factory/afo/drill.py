"""AFO-T014 (AFO-FR-009/010/014, AT-001/003/004/005/007/009) - isolated systemd process-failure drill.

Runs against a THROWAWAY copy of the rendered Conductor unit (unique name forge-afo-drill-<id>.service, its own
state directory, short intervals, no data-volume preflight) - never against the live Forge-C services, which are
serving runs and share the host with other projects. Steps, each with observed systemd properties:
  1 start -> active, READY from the first completed cycle, heartbeat written
  2 SIGKILL the main PID -> systemd restarts it (NRestarts+1, new PID, fresh heartbeat)
  3 SIGSTOP (hang) -> no WATCHDOG ping -> systemd's watchdog kills and restarts it
  4 SIGTERM -> clean exit 0, unit inactive, NOT restarted (Restart=on-failure)
  5 crash loop -> stops after StartLimitBurst restarts and stays failed (no restart storm)
The unit file is removed afterwards. Output: a JSON record of every step.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from ..common import REPO_ROOT, utc_now
from .services import UNIT_DIR, values


def _show(unit: str) -> dict:
    r = subprocess.run(["systemctl", "--user", "show", unit, "--property=ActiveState,SubState,Result,NRestarts,MainPID,"
                        "ExecMainStatus"], capture_output=True, text=True, timeout=20)
    return dict(x.split("=", 1) for x in r.stdout.splitlines() if "=" in x)


def _wait(unit: str, pred, timeout: float) -> dict:
    end = time.time() + timeout
    s = _show(unit)
    while time.time() < end:
        s = _show(unit)
        if pred(s):
            return s
        time.sleep(0.5)
    return s


def unit_text(state: Path, burst: int = 3, watchdog: int = 6) -> str:
    v = values()
    return f"""[Unit]
Description=Forge-C AFO restart drill (throwaway)
StartLimitIntervalSec=300
StartLimitBurst={burst}

[Service]
Type=notify
NotifyAccess=main
ExecStart={v['@VENV@']}/bin/python -m forge_factory.afo.conductor --interval 1
WatchdogSec={watchdog}
Restart=on-failure
RestartSec=1
Environment=PYTHONPATH={REPO_ROOT}/factory/python
Environment=FORGE_REPO_ROOT={REPO_ROOT}
Environment=FORGE_STATE_DIR={state}
"""


def run() -> dict:
    name = f"forge-afo-drill-{uuid.uuid4().hex[:8]}.service"
    steps, ok = [], True
    with tempfile.TemporaryDirectory() as td:
        state = Path(td) / "state"
        hb = state / "afo/conductor.heartbeat"
        unit = UNIT_DIR / name
        UNIT_DIR.mkdir(parents=True, exist_ok=True)
        unit.write_text(unit_text(state))
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)

        def step(label: str, passed: bool, obs: dict) -> None:
            nonlocal ok
            ok &= passed
            steps.append({"step": label, "pass": passed, "observed": obs, "at": utc_now()})

        try:
            subprocess.run(["systemctl", "--user", "start", name], check=True, timeout=60)
            s = _wait(name, lambda s: s.get("ActiveState") == "active", 30)
            step("1_start_ready", s.get("ActiveState") == "active" and hb.is_file(), s)
            pid0, r0 = int(s["MainPID"]), int(s.get("NRestarts", 0))
            os.kill(pid0, signal.SIGKILL)
            s = _wait(name, lambda s: s.get("ActiveState") == "active" and s.get("MainPID") not in ("0", str(pid0)), 30)
            step("2_sigkill_restarted", int(s.get("NRestarts", 0)) == r0 + 1 and s.get("MainPID") != str(pid0), s)
            pid1, r1 = int(s["MainPID"]), int(s.get("NRestarts", 0))
            os.kill(pid1, signal.SIGSTOP)
            s = _wait(name, lambda s: s.get("ActiveState") == "active" and s.get("MainPID") not in ("0", str(pid1)), 40)
            step("3_hang_watchdog_restarted", int(s.get("NRestarts", 0)) == r1 + 1 and s.get("MainPID") != str(pid1), s)
            pid2 = int(s["MainPID"])
            time.sleep(2)
            os.kill(pid2, signal.SIGTERM)
            s = _wait(name, lambda s: s.get("ActiveState") in ("inactive", "failed"), 30)
            time.sleep(3)
            s = _show(name)
            step("4_sigterm_clean_no_restart", s.get("ActiveState") == "inactive" and s.get("Result") == "success", s)
            subprocess.run(["systemctl", "--user", "reset-failed", name], check=False)
            subprocess.run(["systemctl", "--user", "start", name], check=True, timeout=60)
            for _ in range(8):  # crash repeatedly; StartLimitBurst=3 must end it
                s = _wait(name, lambda s: s.get("ActiveState") == "active" and s.get("MainPID") != "0", 10)
                if s.get("ActiveState") != "active":
                    break
                os.kill(int(s["MainPID"]), signal.SIGKILL)
                time.sleep(1.5)
            s = _wait(name, lambda s: s.get("ActiveState") == "failed", 20)
            time.sleep(6)  # stays down: no further restart after the limit
            later = _show(name)
            step("5_crash_loop_bounded", s.get("ActiveState") == "failed" and later.get("ActiveState") == "failed"
                 and int(later.get("NRestarts", 99)) <= 3 and later.get("NRestarts") == s.get("NRestarts"),
                 {**later, "restarts_limit": 3})
        except Exception as exc:  # noqa: BLE001 - the record says what broke; cleanup always runs
            step("error", False, {"error": f"{type(exc).__name__}: {exc}"[:300]})
        finally:
            subprocess.run(["systemctl", "--user", "stop", name], check=False, timeout=60)
            subprocess.run(["systemctl", "--user", "reset-failed", name], check=False)
            unit.unlink(missing_ok=True)
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    return {"schema": "forge-c/afo-restart-drill/0.1", "unit": name, "ok": ok, "steps": steps,
            "scope": "throwaway copy of the Conductor unit; live Forge-C services and other projects untouched"}


def main(argv: list[str] | None = None) -> int:
    r = run()
    print(json.dumps(r, indent=1))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
