#!/bin/bash
set -u
D=/mnt/data/forge-c/operations/swe1-ornith-20261031; W=$D/work; R=$D/repo; LOG=$D/progress.log
SRC=/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/state/workorders/WO-AFO-7f71565db57f0a76-a1/workspace
p() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
for i in $(seq 1 900); do
  [ -f $W/server.ready ] && break
  [ -f $W/server.stopped.json ] || [ -f $W/server.failed ] && { p "RUN NOT STARTED: server not ready"; exit 1; }
  sleep 1
done
[ -f $W/server.ready ] || { p "RUN NOT STARTED: server not ready in 900 s"; touch $W/server.stop; exit 1; }
mkdir -p $D/state
python3 $W/monitor.py > $W/monitor.log 2>&1 &
mon=$!
p "MODELCMP STARTING (repeat 2, SWE.1, model alias ornith-1.5-35b-a3b-q8)"
cd $R/factory/python
t0=$(date +%s.%N)
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
  FORGE_LRTX_GATEWAY_URL=http://127.0.0.1:18592/v1 FORGE_STATE_DIR=$D/state FORGE_DATA_ROOT=/mnt/data/forge-c \
  PYTHONPATH=$R/factory/python FORGE_LRTX_PROFILE=local-rtx-v2-omniverse2-q38-delivery-first PYTHONDONTWRITEBYTECODE=1 \
  /mnt/data/forge-c/venv/bin/python -m forge_factory.lrtx.modelcmp --workspace $SRC --model ornith-1.5-35b-a3b-q8 \
  --repeat 2 --phase SWE.1 --out $D/report.json > $W/modelcmp.stdout 2> $W/modelcmp.stderr
rc=$?
echo "{\"rc\":$rc,\"wall_s\":$(python3 -c "print(round($(date +%s.%N)-$t0,1))"),\"at\":\"$(date -u +%FT%TZ)\"}" > $W/modelcmp.exit.json
sleep 6; touch $W/monitor.stop; wait $mon
p "MODELCMP FINISHED rc $rc ($(cat $W/modelcmp.exit.json))"
touch $W/server.stop
