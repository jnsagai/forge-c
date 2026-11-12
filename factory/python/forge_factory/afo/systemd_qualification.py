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
import sys
from pathlib import Path
from ..common import REPO_ROOT, data_root, utc_now
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
        intentional = start(
            "intentional-exit",
            ["/usr/bin/python3", "-c", "raise SystemExit(77)"],
            ["RestartPreventExitStatus=77", "StartLimitIntervalSec=5", "StartLimitBurst=2"],
        )
        exited, obs = wait_for(intentional, lambda s: s.get("ActiveState") == "failed", 3)
        time.sleep(0.3)
        final = show(intentional)
        rows.append(
            {
                "case": "operator-exit-77-prevents-restart-always",
                "pass": exited and final.get("NRestarts") == "0",
                "observations": obs,
                "state": final,
            }
        )
        blocked = start(
            "boot-condition",
            ["/usr/bin/sleep", "60"],
            ["ExecCondition=/usr/bin/false", "StartLimitIntervalSec=5", "StartLimitBurst=2"],
        )
        inactive, obs = wait_for(blocked, lambda s: s.get("ActiveState") == "inactive", 3)
        rows.append(
            {
                "case": "stopped-boot-condition-does-not-enter-restart-loop",
                "pass": inactive and show(blocked).get("NRestarts") == "0",
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


def line_command(state: Path, snapshot: Path) -> list[str]:
    """The actual model-free Line Conductor, forced to private state and a recorded empty Fabro view."""
    return [sys.executable, "-m", "forge_factory.afo.line_conductor", "--mode", "OBSERVE", "--line", "drill",
            "--interval", "0.25", "--fabro-snapshot", str(snapshot), "--launch-dir", str(state / "launch")]


def line_run(out):
    """Qualify real Line Conductor readiness/restart semantics in a unique transient unit. No production action.

    The slow-start case is an explicitly exercised recovery recipe, not evidence of an installed independent
    recovery timer. Operational fault/model recovery and long-run availability require separate qualification.
    """
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    state = out / "state"
    state.mkdir()
    snapshot = out / "fabro-snapshot.json"
    snapshot.write_text("{}\n")
    name = f"forge-c-014-qual-{uuid.uuid4().hex[:12]}-line.service"
    hb = state / "supervisor/line-conductor.heartbeat"
    feed = state / "supervisor/issues.json"
    rows = []

    def record(case, passed, **facts):
        rows.append({"case": case, "pass": bool(passed), **facts})

    def heartbeat(pid):
        try:
            h = json.loads(hb.read_text())
            f = json.loads(feed.read_text())
        except (OSError, ValueError):
            return False
        return (h.get("pid") == int(pid) and h.get("ok") is True and h.get("mode") == "OBSERVE"
                and 0 <= time.time() - h.get("epoch", 0) <= 5
                and f.get("supervisor", {}).get("model_calls_healthy") == 0 and "placement" not in f)

    properties = ["Type=notify", "NotifyAccess=main", "Restart=always", "RestartSec=100ms", "KillMode=process",
                  "WatchdogSec=2", "TimeoutStartSec=10", "StartLimitIntervalSec=10", "StartLimitBurst=3", "LimitCORE=0"]
    argv = ["systemd-run", "--user", "--quiet", "--unit", name]
    for prop in properties:
        argv += ["--property", prop]
    for key, value in {"PYTHONPATH": str(REPO_ROOT / "factory/python"), "FORGE_REPO_ROOT": str(REPO_ROOT),
                       "FORGE_DATA_ROOT": str(data_root()), "FORGE_STATE_DIR": str(state),
                       "FORGE_LINE_CONDUCTOR_UNIT": name}.items():
        argv += ["--setenv", f"{key}={value}"]
    version = call(["systemctl", "--version"]).stdout.splitlines()[0]
    try:
        result = call([*argv, *line_command(state, snapshot)])
        if result.returncode:
            raise RuntimeError("TRANSIENT_LINE_UNIT_START_FAILED:" + result.stderr[-200:])
        ready, obs = wait_for(name, lambda s: s.get("ActiveState") == "active" and heartbeat(s.get("MainPID", "0")), 10)
        record("actual-line-ready-model-free", ready, observations=obs)
        for label, sig in (("unexpected-kill-restarts", "KILL"), ("unexpected-clean-exit-restarts", "TERM"),
                           ("hung-line-watchdog-restarts", "STOP")):
            call(["systemctl", "--user", "reset-failed", name], check=True)  # isolate this drill's next injection
            before = show(name)
            pid = before.get("MainPID")
            killed = call(["systemctl", "--user", "kill", "--kill-who=main", "--signal=" + sig, name])
            restored, obs = wait_for(name, lambda s: s.get("ActiveState") == "active"
                                    and s.get("MainPID") not in ("0", pid) and heartbeat(s.get("MainPID", "0")), 10)
            record(label, killed.returncode == 0 and restored, before=before, observations=obs)
        # Exhaust a bounded burst with deliberate main-process kills, then demonstrate a slow explicit restore.
        call(["systemctl", "--user", "reset-failed", name], check=True)
        for _ in range(6):
            s = show(name)
            if s.get("ActiveState") == "failed":
                break
            call(["systemctl", "--user", "kill", "--kill-who=main", "--signal=KILL", name])
            wait_for(name, lambda v: v.get("ActiveState") in ("active", "failed")
                     and (v.get("MainPID") != s.get("MainPID") or v.get("ActiveState") == "failed"), 3)
        limited, obs = wait_for(name, lambda s: s.get("ActiveState") == "failed", 5)
        # Some systemd versions retain Result=signal from the last killed process after limiting its next start.
        # Require the manager's explicit rate-limit message as well as a failed unit and bounded restart count.
        journal = call(["journalctl", "--user", "-u", name, "--no-pager", "-o", "json"]).stdout
        limit_messages = []
        for line in journal.splitlines():
            try:
                message = json.loads(line).get("MESSAGE", "")
            except ValueError:
                continue
            if message == name + ": Start request repeated too quickly.":
                limit_messages.append(message)
        bounded = bool(obs) and int(obs[-1]["state"].get("NRestarts", "99")) <= 4
        record("restart-storm-is-rate-limited", limited and limit_messages and bounded,
               observations=obs, manager_rate_limit_messages=limit_messages)
        time.sleep(10.2)
        before = show(name)
        started = call(["systemctl", "--user", "start", name])
        restored, obs = wait_for(name, lambda s: s.get("ActiveState") == "active" and heartbeat(s.get("MainPID", "0")), 10)
        record("bounded-slow-start-restores-real-line", before.get("ActiveState") == "failed"
               and started.returncode == 0 and restored, before=before, observations=obs)
        call(["systemctl", "--user", "stop", name], check=True)
        time.sleep(0.5)
        stopped = show(name)
        record("operator-service-stop-is-respected", stopped.get("ActiveState") == "inactive", observed=stopped)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        record("drill-error", False, error=type(exc).__name__ + ":" + str(exc)[:240])
    finally:
        call(["systemctl", "--user", "stop", name])
        call(["systemctl", "--user", "reset-failed", name])
    report = {"scope": "ISOLATED_ACTUAL_LINE_CONDUCTOR_NO_MODEL_NO_PRODUCTION_ACTION", "host": socket.gethostname(),
              "at": utc_now(), "version": version, "unit": name, "command": line_command(state, snapshot),
              "properties": properties, "rows": rows, "status": "PASS" if rows and all(r["pass"] for r in rows) else "FAIL",
              "production_line_state": "NOT_TOUCHED", "independent_line_recovery_timer": "NOT_QUALIFIED",
              "operational_model_recovery": "NOT_QUALIFIED", "24_72_hour_soak": "NOT_RUN"}
    immutable_json(out / "line-report.json", report)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--line-conductor", action="store_true", help="Exercise the actual OBSERVE Line Conductor in private state")
    a = ap.parse_args(argv)
    report = line_run(a.out) if a.line_conductor else run(a.out)
    print(json.dumps({"status": report["status"], "report": str(a.out / ("line-report.json" if a.line_conductor else "report.json"))}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
