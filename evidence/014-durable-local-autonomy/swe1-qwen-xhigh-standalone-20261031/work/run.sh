#!/bin/bash
# Step 2 (author arm: modelcmp, Qwen) then step 3 (Qwen inspection of attempt 1, if visit PASS + gate FROZEN).
set -u
D=/mnt/data/forge-c/operations/swe1-qwen-xhigh-20261031; W=$D/work; R=/mnt/data/forge-c/operations/swe1-qwen-20261031/repo; LOG=$D/progress.log
START=$D/start-ws; I=$D/inspect-ws; MODEL=qwen3.8:27b-q8_0; PROF=local-rtx-v2-omniverse2-q38-delivery-first
SRC=/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/state/workorders/WO-AFO-7f71565db57f0a76-a1/workspace
O=/mnt/data/forge-c/operations/swe1-ornith-20261031; M=/mnt/data/forge-c/operations/swe1-qwen-20261031
LAST_START=$(cat $W/last_pass_start_epoch)
PY=/mnt/data/forge-c/venv/bin/python
p() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
for i in $(seq 1 900); do
  [ -f $W/gateway.ready ] && break
  { [ -f $W/serve.stopped.json ] || [ -f $W/serve.failed ]; } && { p "RUN NOT STARTED: server/gateway not ready"; exit 1; }
  sleep 1
done
[ -f $W/gateway.ready ] || { p "RUN NOT STARTED: gateway not ready in 900 s"; touch $W/serve.stop; exit 1; }
BASE=(env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY FORGE_LRTX_GATEWAY_URL=http://127.0.0.1:18600/v1
      FORGE_DATA_ROOT=/mnt/data/forge-c PYTHONPATH=$R/factory/python FORGE_LRTX_PROFILE=$PROF PYTHONDONTWRITEBYTECODE=1
      PYTHONUNBUFFERED=1)
# ---- step 2: author arm
mkdir -p $D/state
python3 $W/monitor.py author > $W/monitor-author.log 2>&1 &
mon=$!
p "MODELCMP STARTING (repeat 2, SWE.1, model $MODEL, gateway 18600, xhigh)"
cd $R/factory/python
t0=$(date +%s.%N)
"${BASE[@]}" FORGE_STATE_DIR=$D/state $PY -m forge_factory.lrtx.modelcmp --workspace $START --model $MODEL \
  --repeat 2 --phase SWE.1 --out $D/report.json > $W/modelcmp.stdout 2> $W/modelcmp.stderr
rc=$?
echo "{\"rc\":$rc,\"wall_s\":$(python3 -c "print(round($(date +%s.%N)-$t0,1))"),\"at\":\"$(date -u +%FT%TZ)\"}" > $W/modelcmp.exit.json
sleep 4; touch $W/monitor-author.stop; wait $mon
p "MODELCMP FINISHED rc $rc ($(cat $W/modelcmp.exit.json))"
# ---- step 3 decision
dec=$(python3 -c "
import json
try:
    r=json.load(open('$D/report.json'))['rows'][0]
    print('GO' if r['visit']=='PASS' and str(r['gate']).startswith('FROZEN') else f\"NO_GO visit={r['visit']} gate={r['gate']}\")
except Exception as e: print('NO_GO report unreadable', type(e).__name__)")
p "INSPECTION DECISION: $dec"
if [ "${dec%% *}" != GO ]; then touch $W/serve.stop; exit 0; fi
if [ $(date +%s) -ge $LAST_START ]; then p "INSPECTION NOT STARTED: time limit (last start $(date -u -d @$LAST_START +%TZ))"; touch $W/serve.stop; exit 0; fi
A1=$(python3 -c "import json;print(json.load(open('$D/report.json'))['rows'][0]['workspace'])")
cp -a $A1 $I
python3 $W/isolate.py $A1 $I $W/isolated-inspect $W/isolation-edits-inspect.json $START $SRC > $W/isolate-inspect.out
p "INSPECT-WS READY: $I (copy of attempt-1 workspace); isolation: $(cat $W/isolate-inspect.out | head -c 300)"
python3 $W/snapshot.py $W/ro-inspect-before.json $SRC $O/report-workspaces $O/inspect-ws $M/report-workspaces $M/inspect-ws $M/start-ws $D/report-workspaces > $W/ro-inspect-before.out
python3 $W/monitor.py inspect > $W/monitor-inspect.log 2>&1 &
mon=$!
mkdir -p $D/inspect-state
n=0; resume=""
while :; do
  n=$((n+1))
  p "INSPECT RUNNER PASS $n START (inspect SWE.1 --time-budget 1200 $resume)"
  t0=$(date +%s.%N)
  "${BASE[@]}" FORGE_STATE_DIR=$D/inspect-state $PY -m forge_factory.lrtx.runner inspect --phase SWE.1 --workspace $I \
     --model $MODEL --time-budget 1200 $resume > $W/runner-pass$n.stdout 2> $W/runner-pass$n.stderr
  rc=$?
  st=$(python3 -c "import json;print(json.load(open('$I/.forge-run/lrtx/SWE.1/inspect-reply.json')).get('status'))" 2>/dev/null || echo MISSING)
  calls=$(tail -1 $I/.forge-run/lrtx/SWE.1/inspections.jsonl 2>/dev/null | python3 -c "import json,sys;print(json.loads(sys.stdin.read()).get('calls'))" 2>/dev/null)
  echo "{\"pass\":$n,\"rc\":$rc,\"status\":\"$st\",\"calls\":\"$calls\",\"wall_s\":$(python3 -c "print(round($(date +%s.%N)-$t0,1))"),\"at\":\"$(date -u +%FT%TZ)\"}" >> $W/passes.jsonl
  p "INSPECT RUNNER PASS $n FINISHED rc $rc status $st calls $calls wall $(tail -1 $W/passes.jsonl)"
  [ "$st" = CONTINUE ] || break
  [ $(date +%s) -lt $LAST_START ] || { p "INSPECT TIME LIMIT: no further --resume pass (last start allowed $(date -u -d @$LAST_START +%TZ))"; break; }
  [ -f $W/serve.stopped.json ] && { p "INSPECT server stopped; no further pass"; break; }
  resume="--resume"
done
sleep 4; touch $W/monitor-inspect.stop; wait $mon
touch $W/serve.stop
for i in $(seq 1 90); do [ -f $W/serve.stopped.json ] && break; sleep 1; done
GATE=$("${BASE[@]}" FORGE_STATE_DIR=$D/inspect-state $PY -c "from forge_factory.workflow.builder import gate_cmd;print(gate_cmd('SWE.1','inspect'))")
echo "$GATE" > $W/gate.cmd
cd $I
bash -c "cat .forge-run/lrtx/SWE.1/inspect-reply.json | $GATE" > $W/gate.stdout 2> $W/gate.stderr
grc=$?
echo "{\"rc\":$grc,\"at\":\"$(date -u +%FT%TZ)\"}" > $W/gate.exit.json
p "INSPECT GATE rc $grc: $(head -c 300 $W/gate.stdout | tr '\n' ' ')"
python3 $W/snapshot.py $W/ro-inspect-after.json $SRC $O/report-workspaces $O/inspect-ws $M/report-workspaces $M/inspect-ws $M/start-ws $D/report-workspaces > $W/ro-inspect-after.out
p "RUN DONE"
