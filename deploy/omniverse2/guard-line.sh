#!/bin/bash
# Read-only Omniverse2 M3 host guard. Arg 1: own llama-server PID (or empty).
# Install at operations/swe1-obligations-20261031/work/guard.sh during the signed PILOT cutover.
# Keeps the GPU queue, foreign GPU PID and owner-intent checks; requires a healthy current M3 unit.
MY=${1:-}
Q=/mnt/data/forge-c/inspector-014-b309039/gpuq
HB=/mnt/data/forge-c/swe1-fabro-20261031/lrtx/state/supervisor/line-conductor.heartbeat
I1=/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/control/operations.json
I2=/home/omniverse2/.local/state/forge-c-production-014/operations.json
r=()
[ -n "$(ls -A $Q/pending 2>/dev/null)" ] && r+=(GPUQ_PENDING_NOT_EMPTY)
[ -n "$(ls -A $Q/running 2>/dev/null)" ] && r+=(GPUQ_RUNNING_NOT_EMPTY)
hb=$(python3 - "$HB" <<'PYGUARD'
import json, subprocess, sys, time

def check_heartbeat(d, main_pid, active, now):
    if active != "active" or main_pid <= 0:
        return "M3_UNIT_INACTIVE"
    if type(d.get("pid")) is not int or d["pid"] != main_pid:
        return "M3_PID_MISMATCH"
    if d.get("mode") != "PILOT" or d.get("ok") is not True:
        return "M3_NOT_HEALTHY_PILOT"
    epoch = d.get("epoch")
    if type(epoch) not in (int, float) or not 0 <= now - epoch <= 180:
        return "M3_HEARTBEAT_STALE"
    return "OK"

try:
    unit = "forge-line-conductor-local.service"
    props = subprocess.check_output(["systemctl", "--user", "show", unit,
                                    "-p", "MainPID", "-p", "ActiveState"], text=True, timeout=10)
    props = dict(line.split("=", 1) for line in props.splitlines() if "=" in line)
    with open(sys.argv[1]) as f:
        heartbeat = json.load(f)
    print(check_heartbeat(heartbeat, int(props.get("MainPID", "0")),
                          props.get("ActiveState"), time.time()))
except Exception:
    print("M3_HEARTBEAT_UNAVAILABLE")
PYGUARD
)
[ "$hb" = "OK" ] || r+=("CONDUCTOR_HEARTBEAT_CHANGED:$hb")
[ "$(sha256sum < $I1 | cut -c1-64)" = 9eff2df365375ae5eeae327dcd2bfefb440f14d100196a6dc1caee5b28f4d545 ] || r+=(AFO_INTENT_CHANGED)
[ "$(sha256sum < $I2 | cut -c1-64)" = 1387fbb25538882a981b90ec6169f563dd88b4e0943ce49c402f59f90947e63c ] || r+=(PRODUCTION_INTENT_CHANGED)
for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
  [ "$p" = "$MY" ] || r+=("FOREIGN_GPU_PROCESS:$p")
done
if [ ${#r[@]} -eq 0 ]; then echo OK; else echo "FAIL:${r[*]}"; fi
