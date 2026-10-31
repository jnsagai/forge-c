#!/bin/bash
# Read-only guard. Arg 1: our server PID (or empty). Prints OK or FAIL:<reasons>.
MY=${1:-}
Q=/mnt/data/forge-c/inspector-014-b309039/gpuq
HB=/mnt/data/forge-c/production-local-014/state/afo/conductor.heartbeat
I1=/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/control/operations.json
I2=/home/omniverse2/.local/state/forge-c-production-014/operations.json
r=()
[ -n "$(ls -A $Q/pending 2>/dev/null)" ] && r+=(GPUQ_PENDING_NOT_EMPTY)
[ -n "$(ls -A $Q/running 2>/dev/null)" ] && r+=(GPUQ_RUNNING_NOT_EMPTY)
hb=$(python3 -c "import json;d=json.load(open('$HB'));print(d.get('mode'),d.get('detail'),d.get('pid'))" 2>/dev/null)
[ "$hb" = "OBSERVE_ONLY operations_wait 3699940" ] || r+=("CONDUCTOR_HEARTBEAT_CHANGED:${hb// /_}")
[ "$(sha256sum < $I1 | cut -c1-64)" = 9eff2df365375ae5eeae327dcd2bfefb440f14d100196a6dc1caee5b28f4d545 ] || r+=(AFO_INTENT_CHANGED)
[ "$(sha256sum < $I2 | cut -c1-64)" = 1387fbb25538882a981b90ec6169f563dd88b4e0943ce49c402f59f90947e63c ] || r+=(PRODUCTION_INTENT_CHANGED)
for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
  [ "$p" = "$MY" ] || r+=("FOREIGN_GPU_PROCESS:$p")
done
if [ ${#r[@]} -eq 0 ]; then echo OK; else echo "FAIL:${r[*]}"; fi
