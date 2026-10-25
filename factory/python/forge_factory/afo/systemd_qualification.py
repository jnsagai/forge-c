"""Isolated real systemd semantics checks, with no model or production service action.

Creates only transient forge-c-014-qual-* units; all project artifacts go under
--out. Does not install units, reboot, touch Fabro/Ollama or qualify Omniverse uptime.
"""

from __future__ import annotations
import argparse
import json
import socket
import subprocess
import time
import uuid
from pathlib import Path
from ..common import utc_now
from .durable import immutable_json


def call(args, check=False):
    return subprocess.run(args, capture_output=True, text=True, timeout=10, check=check)


def show(unit):
    r = call(["systemctl", "--user", "show", unit, "--property=ActiveState,SubState,Result,NRestarts,MainPID"])
    return dict(x.split("=", 1) for x in r.stdout.splitlines() if "=" in x)


def wait_for(unit, predicate, seconds=8):
    until = time.monotonic() + seconds
    observations = []
    while time.monotonic() < until:
        s = show(unit)
        observations.append({"mono": time.monotonic(), "state": s})
        if predicate(s):
            return True, observations
        time.sleep(0.1)
    return False, observations


def run(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    helper = out / "notify-and-hang.py"
    helper.write_text(
        "import os,socket,time\np=os.environ['NOTIFY_SOCKET']\np='\\0'+p[1:] if p.startswith('@') else p\ns=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)\ns.sendto(b'READY=1',p)\ntime.sleep(60)\n"
    )
    version = call(["systemctl", "--version"]).stdout.splitlines()[0]
    tag = uuid.uuid4().hex[:12]
    units = []
    rows = []

    def start(name, command, properties):
        unit = f"forge-c-014-qual-{tag}-{name}.service"
        units.append(unit)
        argv = ["systemd-run", "--user", "--quiet", "--unit", unit]
        for prop in ["Restart=always", "RestartSec=100ms", "LimitCORE=0", *properties]:
            argv += ["--property", prop]
        result = call([*argv, *command])
        if result.returncode:
            raise RuntimeError("TRANSIENT_UNIT_START_FAILED:" + result.stderr[-300:])
        return unit

    try:
        clean = start("clean", ["/usr/bin/true"], ["StartLimitIntervalSec=2", "StartLimitBurst=2"])
        ok, observations = wait_for(clean, lambda s: s.get("Result") == "start-limit-hit", 5)
        rows.append({"case": "unexpected-clean-exit-restarts-then-rate-limits", "pass": ok, "observations": observations})
        # Rate-limit interval elapsing does not start the failed service. A later explicit bounded slow start does.
        time.sleep(2.1)
        before = show(clean)
        result = call(["systemctl", "--user", "start", clean])
        restored, obs = wait_for(clean, lambda s: s.get("Result") == "start-limit-hit", 5)
        rows.append(
            {
                "case": "slow-start-after-burst-exhaustion",
                "pass": before.get("ActiveState") == "failed" and result.returncode == 0 and restored,
                "before": before,
                "start_returncode": result.returncode,
                "observations": obs,
            }
        )
        crash = start("crash", ["/usr/bin/sleep", "60"], ["StartLimitIntervalSec=10", "StartLimitBurst=3"])
        active, _ = wait_for(crash, lambda s: s.get("ActiveState") == "active", 3)
        killed = call(["systemctl", "--user", "kill", "--kill-who=main", "--signal=KILL", crash])
        restarted, obs = wait_for(crash, lambda s: int(s.get("NRestarts", "0")) >= 1 and s.get("ActiveState") == "active", 5)
        rows.append(
            {"case": "unexpected-process-kill", "pass": active and killed.returncode == 0 and restarted, "observations": obs}
        )
        hang = start(
            "hang",
            ["/usr/bin/python3", str(helper)],
            ["Type=notify", "WatchdogSec=1", "TimeoutStartSec=3", "StartLimitIntervalSec=5", "StartLimitBurst=2"],
        )
        limited, obs = wait_for(
            hang,
            lambda s: (
                s.get("ActiveState") == "failed"
                and s.get("Result") in ("watchdog", "start-limit-hit")
                and int(s.get("NRestarts", "0")) >= 2
            ),
            8,
        )
        rows.append(
            {
                "case": "hung-notify-worker-watchdog",
                "pass": limited and any(int(r["state"].get("NRestarts", "0")) >= 1 for r in obs),
                "observations": obs,
            }
        )
        call(["systemctl", "--user", "stop", crash], check=True)
        time.sleep(0.5)
        stopped = show(crash)
        rows.append(
            {"case": "explicit-service-stop-is-not-restarted", "pass": stopped.get("ActiveState") == "inactive", "state": stopped}
        )
    finally:
        for unit in units:
            call(["systemctl", "--user", "stop", unit])
            call(["systemctl", "--user", "reset-failed", unit])  # dispose only this isolated transient test's failed state
    report = {
        "scope": "ISOLATED_SYSTEMD_SEMANTICS_NO_MODEL_NO_DEPLOYMENT",
        "host": socket.gethostname(),
        "at": utc_now(),
        "version": version,
        "status": "PASS" if rows and all(r["pass"] for r in rows) else "FAIL",
        "rows": rows,
        "remote_profile_reboot_mount_campaign": "NOT_RUN",
        "24_72_168_hour_availability": "NOT_RUN",
    }
    immutable_json(out / "report.json", report)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    report = run(a.out)
    print(json.dumps({"status": report["status"], "report": str(a.out / "report.json")}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
