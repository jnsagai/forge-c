#!/bin/bash
set -euo pipefail
umask 077
Q=/mnt/data/forge-c/inspector-014-b309039
test ! -e "$Q/gpuq/STOP" || { echo OPERATOR_QUEUE_STOP; exit 2; }
unset PYTHONPATH
source "$Q/inspector-env.sh"
P="$Q/host-bus-fbd8bc8/repo"
cd "$R"
$STACK exec -- env FORGE_REPO_ROOT="$P" PYTHONPATH="$P/factory/python" FORGE_DATA_ROOT=/mnt/data/forge-c FORGE_STATE_DIR="$Q/unit-state/st3-diagnosis" FORGE_EVENTS_DIR="$Q/unit-events/st3-diagnosis" TMPDIR="$Q/runs/qwen-bus-query-review-20261027/tmp" PYTHONDONTWRITEBYTECODE=1 timeout --signal=TERM --kill-after=10s 300s "$L/venv/bin/python" "$Q/runs/qwen-bus-query-review-20261027.py" --resume
