"""Model-free external Line Conductor health and existing Intent-fenced recovery.

No automatic policy activation or intent initialization. A restart requires the existing CRE preauthorization,
an authenticated RUNNING/PAUSED/DRAINING intent, healthy authoritative data volume and enabled failed unit.
The existing persistent cooldown and effect/intent serialization own every start. Explicit stop is respected.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from pathlib import Path

from .operations import Intent

UNIT = "forge-line-conductor-local.service"


def unit_state():
    result = subprocess.run(["systemctl", "--user", "show", UNIT,
        "--property=ActiveState,SubState,MainPID,Result,UnitFileState,Job"],
        capture_output=True, text=True, timeout=10)
    if result.returncode:
        return {}
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def check(max_age=180, *, now=None, heartbeat=None, probe=None):
    from .line_conductor import heartbeat_path

    if type(max_age) not in (int, float) or not math.isfinite(max_age) or max_age <= 0:
        raise ValueError("LINE_WATCHDOG_MAX_AGE_INVALID")
    now = time.time() if now is None else now
    state = (probe or unit_state)()
    try:
        h = json.loads(Path(heartbeat or heartbeat_path()).read_text())
    except (OSError, ValueError):
        return {"ok": False, "code": "HEARTBEAT_MISSING", "unit": UNIT}
    if not isinstance(h, dict):
        return {"ok": False, "code": "HEARTBEAT_INVALID", "unit": UNIT}
    if state.get("ActiveState") != "active":
        return {"ok": False, "code": "LINE_UNIT_NOT_ACTIVE", "unit": UNIT}
    pid = h.get("pid")
    if type(pid) is not int or pid <= 0 or str(pid) != state.get("MainPID"):
        return {"ok": False, "code": "HEARTBEAT_PID_MISMATCH", "unit": UNIT}
    epoch = h.get("epoch")
    if type(epoch) not in (int, float) or not math.isfinite(epoch) or not 0 <= now - epoch <= max_age:
        return {"ok": False, "code": "HEARTBEAT_STALE", "unit": UNIT}
    if h.get("ok") is not True:
        return {"ok": False, "code": "CYCLE_FAILED", "unit": UNIT}
    if h.get("mode") not in ("PILOT", "OBSERVE"):
        return {"ok": False, "code": "HEARTBEAT_MODE_INVALID", "unit": UNIT}
    return {"ok": True, "code": "HEALTHY", "unit": UNIT, "pid": pid, "mode": h.get("mode"),
            "age_s": round(now - epoch, 1)}


def recover(intent_path, *, now=None, probe=None, runner=None, authorize=None, ready=None):
    from .host import preflight

    intent = Intent(intent_path)
    record = intent.read()
    if record["mode"] not in ("RUNNING", "PAUSED", "DRAINING"):
        return {"action": "WAITING_FOR_AUTHENTICATED_OPERATIONS_INTENT", "intent": record["mode"]}
    if not (ready or preflight)()["ok"]:
        return {"action": "WAITING_FOR_AUTHORITATIVE_VOLUME"}
    from .line_watchdog_package import verify_runtime_dependencies

    verify_runtime_dependencies()
    # Intent.start keeps its default CRE authorization check unless an independent test supplies a fixture.
    return intent.start(record["epoch"], probe=probe or unit_state, runner=runner, now=now,
                        authorize=authorize, unit=UNIT)


def boot_allowed(intent_path):
    return Intent(intent_path).read()["mode"] in ("RUNNING", "PAUSED", "DRAINING")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["check", "recover", "boot-check", "status"])
    ap.add_argument("--intent", required=True, type=Path)
    ap.add_argument("--max-age", type=float, default=180)
    args = ap.parse_args(argv)
    if not args.intent.is_absolute():
        raise SystemExit("LINE_OPERATIONS_INTENT_MUST_BE_ABSOLUTE")
    if args.command == "boot-check":
        return 0 if boot_allowed(args.intent) else 1
    if args.command == "status":
        print(json.dumps(Intent(args.intent).read()))
        return 0
    status = check(args.max_age)
    if args.command == "recover":
        # A fresh heartbeat cannot hide a failed/replaced unit; recovery probes the current enabled/failed state.
        status["recovery"] = recover(args.intent)
    print(json.dumps(status))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
