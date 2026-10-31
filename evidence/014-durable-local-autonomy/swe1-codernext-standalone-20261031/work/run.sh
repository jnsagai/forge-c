#!/bin/bash
# Protocol check, then (only if strict json_schema holds) the author arm (modelcmp, direct server), then two
# inspections on fresh copies: (a) own attempt-1 baseline, (b) Ornith attempt-2 baseline (omission target). Gate each.
set -u
D=/mnt/data/forge-c/operations/swe1-codernext-20261031; W=$D/work; R=/mnt/data/forge-c/operations/swe1-qwen-20261031/repo
LOG=$D/progress.log; MODEL=qwen3-coder-next:q4_K_M; PROF=local-rtx-v2-omniverse2-q38-delivery-first
SRC=/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/state/workorders/WO-AFO-7f71565db57f0a76-a1/workspace
OA2=/mnt/data/forge-c/operations/swe1-ornith-20261031/report-workspaces/ornith-1.5-35b-a3b-q8-02/workspace
START=$D/start-ws; PY=/mnt/data/forge-c/venv/bin/python; LAST_START=$(cat $W/last_pass_start_epoch)
p() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
[ -f $W/server.ready ] || { p "RUN NOT STARTED: server not ready"; exit 1; }
BASE=(env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY FORGE_LRTX_GATEWAY_URL=http://127.0.0.1:18610/v1
      FORGE_DATA_ROOT=/mnt/data/forge-c PYTHONPATH=$R/factory/python FORGE_LRTX_PROFILE=$PROF PYTHONDONTWRITEBYTECODE=1
      PYTHONUNBUFFERED=1)
# ---- step 1: protocol
mkdir -p $D/protocol-state
p "PROTOCOL CHECK STARTING (Q1 strict json_schema x20, control, Q3 truncation x4, Q5 stream usage, factory structured.call x2)"
cd $R/factory/python
"${BASE[@]}" FORGE_STATE_DIR=$D/protocol-state $PY $W/protocol.py $W/protocol-result.json > $W/protocol.stdout 2> $W/protocol.stderr
prc=$?
v=$(python3 -c "import json;print(json.dumps(json.load(open('$W/protocol-result.json'))['verdicts']))" 2>/dev/null || echo MISSING)
p "PROTOCOL CHECK FINISHED rc $prc verdicts $v"
q1=$(python3 -c "import json;print(json.load(open('$W/protocol-result.json'))['verdicts']['Q1_strict_json_schema'])" 2>/dev/null || echo MISSING)
if [ "$prc" != 0 ] || [ "$q1" != PASS ]; then p "STOP: strict json_schema does not hold (Q1 $q1, rc $prc) - factory not run"; touch $W/serve.stop; exit 0; fi
# ---- step 2: author arm
cp -a $SRC $START
python3 $W/isolate.py $SRC $START $W/isolated-start $W/isolation-edits-start.json $SRC > $W/isolate-start.out
p "START-WS READY: $START (cp -a of trial 06); isolation: $(head -c 300 $W/isolate-start.out)"
mkdir -p $D/state
python3 $W/monitor.py author > $W/monitor-author.log 2>&1 &
mon=$!
p "MODELCMP STARTING (repeat 2, SWE.1, model $MODEL, direct server 18610, no gateway)"
t0=$(date +%s.%N)
"${BASE[@]}" FORGE_STATE_DIR=$D/state $PY -m forge_factory.lrtx.modelcmp --workspace $START --model $MODEL \
  --repeat 2 --phase SWE.1 --out $D/report.json > $W/modelcmp.stdout 2> $W/modelcmp.stderr
rc=$?
echo "{\"rc\":$rc,\"wall_s\":$(python3 -c "print(round($(date +%s.%N)-$t0,1))"),\"at\":\"$(date -u +%FT%TZ)\"}" > $W/modelcmp.exit.json
sleep 4; touch $W/monitor-author.stop; wait $mon
p "MODELCMP FINISHED rc $rc ($(cat $W/modelcmp.exit.json))"
inspect() {  # $1 tag, $2 source workspace, rest: old paths to rebind
  local TAG=$1 FROM=$2; shift 2
  local I=$D/inspect-$TAG
  if [ $(date +%s) -ge $LAST_START ]; then p "[$TAG] NOT STARTED: time limit"; return; fi
  [ -f $W/serve.stopped.json ] && { p "[$TAG] NOT STARTED: server stopped"; return; }
  cp -a $FROM $I
  python3 $W/isolate.py $FROM $I $W/isolated-$TAG $W/isolation-edits-$TAG.json "$@" > $W/isolate-$TAG.out
  p "[$TAG] INSPECT COPY READY: $I (copy of $FROM); isolation: $(head -c 300 $W/isolate-$TAG.out)"
  python3 $W/snapshot.py $W/ro-$TAG-before.json $(cat $W/ro-roots.txt) $D/report-workspaces > $W/ro-$TAG-before.out
  mkdir -p $D/inspect-state-$TAG
  python3 $W/monitor.py inspect $I $TAG > $W/monitor-$TAG.log 2>&1 &
  local mon=$! n=0 resume=""
  cd $R/factory/python
  while :; do
    n=$((n+1))
    p "[$TAG] INSPECT RUNNER PASS $n START (inspect SWE.1 --time-budget 1200 $resume)"
    t0=$(date +%s.%N)
    "${BASE[@]}" FORGE_STATE_DIR=$D/inspect-state-$TAG $PY -m forge_factory.lrtx.runner inspect --phase SWE.1 --workspace $I \
      --model $MODEL --time-budget 1200 $resume > $W/runner-$TAG-pass$n.stdout 2> $W/runner-$TAG-pass$n.stderr
    rc=$?
    st=$(python3 -c "import json;print(json.load(open('$I/.forge-run/lrtx/SWE.1/inspect-reply.json')).get('status'))" 2>/dev/null || echo MISSING)
    calls=$(tail -1 $I/.forge-run/lrtx/SWE.1/inspections.jsonl 2>/dev/null | python3 -c "import json,sys;print(json.loads(sys.stdin.read()).get('calls'))" 2>/dev/null)
    echo "{\"pass\":$n,\"rc\":$rc,\"status\":\"$st\",\"calls\":\"$calls\",\"wall_s\":$(python3 -c "print(round($(date +%s.%N)-$t0,1))"),\"at\":\"$(date -u +%FT%TZ)\"}" >> $W/passes-$TAG.jsonl
    p "[$TAG] INSPECT RUNNER PASS $n FINISHED rc $rc status $st calls $calls wall $(tail -1 $W/passes-$TAG.jsonl)"
    [ "$st" = CONTINUE ] || break
    [ $(date +%s) -lt $LAST_START ] || { p "[$TAG] TIME LIMIT: no further --resume pass"; break; }
    [ -f $W/serve.stopped.json ] && { p "[$TAG] server stopped; no further pass"; break; }
    resume="--resume"
  done
  sleep 3; touch $W/monitor-$TAG.stop; wait $mon
  local GATE
  GATE=$("${BASE[@]}" FORGE_STATE_DIR=$D/inspect-state-$TAG $PY -c "from forge_factory.workflow.builder import gate_cmd;print(gate_cmd('SWE.1','inspect'))")
  echo "$GATE" > $W/gate-$TAG.cmd
  cd $I
  bash -c "cat .forge-run/lrtx/SWE.1/inspect-reply.json | $GATE" > $W/gate-$TAG.stdout 2> $W/gate-$TAG.stderr
  local grc=$?
  echo "{\"rc\":$grc,\"at\":\"$(date -u +%FT%TZ)\"}" > $W/gate-$TAG.exit.json
  p "[$TAG] INSPECT GATE rc $grc: $(head -c 300 $W/gate-$TAG.stdout | tr '\n' ' ')"
  python3 $W/snapshot.py $W/ro-$TAG-after.json $(cat $W/ro-roots.txt) $D/report-workspaces > $W/ro-$TAG-after.out
  python3 $W/compare.py $W/ro-$TAG-before.json $W/ro-$TAG-after.json $W/ro-$TAG-compare.json > $W/ro-$TAG-compare.out
  cd $W
}
# ---- step 3a: own attempt-1 baseline
dec=$(python3 -c "
import json
try:
    r=json.load(open('$D/report.json'))['rows'][0]
    print('GO' if r['visit']=='PASS' and str(r['gate']).startswith('FROZEN') else f\"NO_GO visit={r['visit']} gate={r['gate']}\")
except Exception as e: print('NO_GO report unreadable', type(e).__name__)")
p "INSPECTION (a) DECISION: $dec"
if [ "${dec%% *}" = GO ]; then
  A1=$(python3 -c "import json;print(json.load(open('$D/report.json'))['rows'][0]['workspace'])")
  inspect own $A1 $START $SRC
fi
# ---- step 3b: Ornith attempt-2 baseline (omission target)
inspect omission $OA2 $SRC
touch $W/serve.stop
for i in $(seq 1 90); do [ -f $W/serve.stopped.json ] && break; sleep 1; done
p "RUN DONE"
