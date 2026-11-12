#!/bin/bash
# Omission test: Qwen inspection of the Ornith a02 baseline, first at medium, then at xhigh, each on its own fresh copy
# with its own server + gateway (serve.sh <run>). Then the inspect gate per run.
set -u
D=/mnt/data/forge-c/operations/swe1-omission-20261031; G=$D/work; R=/mnt/data/forge-c/operations/swe1-qwen-20261031/repo
LOG=$D/progress.log; MODEL=qwen3.8:27b-q8_0; PROF=local-rtx-v2-omniverse2-q38-delivery-first
PY=/mnt/data/forge-c/venv/bin/python
LAST_START=$(cat $G/last_pass_start_epoch)
p() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
for RUN in medium xhigh; do
  W=$D/work-$RUN; I=$D/inspect-$RUN
  if [ "$RUN" = medium ]; then GWPORT=18603; else GWPORT=18606; fi
  if [ $(date +%s) -ge $LAST_START ]; then p "[$RUN] NOT STARTED: time limit (last start $(date -u -d @$LAST_START +%TZ))"; continue; fi
  setsid bash $G/serve.sh $RUN > $W/serve.out 2>&1 < /dev/null &
  for i in $(seq 1 900); do
    [ -f $W/gateway.ready ] && break
    { [ -f $W/serve.stopped.json ] || [ -f $W/serve.failed ]; } && break
    sleep 1
  done
  if [ ! -f $W/gateway.ready ]; then p "[$RUN] NOT STARTED: server/gateway not ready"; touch $W/serve.stop; continue; fi
  E=(env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY FORGE_LRTX_GATEWAY_URL=http://127.0.0.1:$GWPORT/v1
     FORGE_STATE_DIR=$D/inspect-state-$RUN FORGE_DATA_ROOT=/mnt/data/forge-c PYTHONPATH=$R/factory/python
     FORGE_LRTX_PROFILE=$PROF PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1)
  mkdir -p $D/inspect-state-$RUN
  python3 $G/monitor.py $RUN > $W/monitor.log 2>&1 &
  mon=$!
  cd $R/factory/python
  n=0; resume=""
  while :; do
    n=$((n+1))
    p "[$RUN] INSPECT RUNNER PASS $n START (inspect SWE.1 --time-budget 1200 $resume)"
    t0=$(date +%s.%N)
    "${E[@]}" $PY -m forge_factory.lrtx.runner inspect --phase SWE.1 --workspace $I --model $MODEL --time-budget 1200 \
      $resume > $W/runner-pass$n.stdout 2> $W/runner-pass$n.stderr
    rc=$?
    st=$(python3 -c "import json;print(json.load(open('$I/.forge-run/lrtx/SWE.1/inspect-reply.json')).get('status'))" 2>/dev/null || echo MISSING)
    calls=$(tail -1 $I/.forge-run/lrtx/SWE.1/inspections.jsonl 2>/dev/null | python3 -c "import json,sys;print(json.loads(sys.stdin.read()).get('calls'))" 2>/dev/null)
    echo "{\"pass\":$n,\"rc\":$rc,\"status\":\"$st\",\"calls\":\"$calls\",\"wall_s\":$(python3 -c "print(round($(date +%s.%N)-$t0,1))"),\"at\":\"$(date -u +%FT%TZ)\"}" >> $W/passes.jsonl
    p "[$RUN] INSPECT RUNNER PASS $n FINISHED rc $rc status $st calls $calls wall $(tail -1 $W/passes.jsonl)"
    [ "$st" = CONTINUE ] || break
    [ $(date +%s) -lt $LAST_START ] || { p "[$RUN] TIME LIMIT: no further --resume pass"; break; }
    [ -f $W/serve.stopped.json ] && { p "[$RUN] server stopped; no further pass"; break; }
    resume="--resume"
  done
  sleep 3; touch $W/monitor.stop; wait $mon
  touch $W/serve.stop
  for i in $(seq 1 90); do [ -f $W/serve.stopped.json ] && break; sleep 1; done
  GATE=$("${E[@]}" $PY -c "from forge_factory.workflow.builder import gate_cmd;print(gate_cmd('SWE.1','inspect'))")
  echo "$GATE" > $W/gate.cmd
  cd $I
  bash -c "cat .forge-run/lrtx/SWE.1/inspect-reply.json | $GATE" > $W/gate.stdout 2> $W/gate.stderr
  grc=$?
  echo "{\"rc\":$grc,\"at\":\"$(date -u +%FT%TZ)\"}" > $W/gate.exit.json
  p "[$RUN] INSPECT GATE rc $grc: $(head -c 300 $W/gate.stdout | tr '\n' ' ')"
  cd $G
done
p "RUN DONE"
