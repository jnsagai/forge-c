#!/bin/bash
set -u
D=/mnt/data/forge-c/operations/swe1-ornith-20261031; W=$D/inspect-work; R=$D/repo; I=$D/inspect-ws; LOG=$D/progress.log
LAST_START=$(cat $W/last_pass_start_epoch)
p() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
for i in $(seq 1 900); do
  [ -f $W/gateway.ready ] && break
  { [ -f $W/serve.stopped.json ] || [ -f $W/serve.failed ]; } && { p "STEP2 INSPECTION NOT STARTED: server/gateway not ready"; exit 1; }
  sleep 1
done
[ -f $W/gateway.ready ] || { p "STEP2 INSPECTION NOT STARTED: gateway not ready in 900 s"; touch $W/serve.stop; exit 1; }
python3 $W/monitor.py > $W/monitor.log 2>&1 &
mon=$!
E=(env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY FORGE_LRTX_GATEWAY_URL=http://127.0.0.1:18594/v1
   FORGE_STATE_DIR=$D/inspect-state FORGE_DATA_ROOT=/mnt/data/forge-c PYTHONPATH=$R/factory/python
   FORGE_LRTX_PROFILE=local-rtx-v2-omniverse2-q38-delivery-first PYTHONDONTWRITEBYTECODE=1)
cd $R/factory/python
n=0; resume=""
while :; do
  n=$((n+1))
  p "STEP2 RUNNER PASS $n START (inspect SWE.1 --time-budget 1200 $resume)"
  t0=$(date +%s.%N)
  "${E[@]}" /mnt/data/forge-c/venv/bin/python -m forge_factory.lrtx.runner inspect --phase SWE.1 --workspace $I \
     --model qwen3.8:27b-q8_0 --time-budget 1200 $resume > $W/runner-pass$n.stdout 2> $W/runner-pass$n.stderr
  rc=$?
  st=$(python3 -c "import json;print(json.load(open('$I/.forge-run/lrtx/SWE.1/inspect-reply.json')).get('status'))" 2>/dev/null || echo MISSING)
  calls=$(tail -1 $I/.forge-run/lrtx/SWE.1/inspections.jsonl 2>/dev/null | python3 -c "import json,sys;print(json.loads(sys.stdin.read()).get('calls'))" 2>/dev/null)
  echo "{\"pass\":$n,\"rc\":$rc,\"status\":\"$st\",\"calls\":\"$calls\",\"wall_s\":$(python3 -c "print(round($(date +%s.%N)-$t0,1))"),\"at\":\"$(date -u +%FT%TZ)\"}" >> $W/passes.jsonl
  p "STEP2 RUNNER PASS $n FINISHED rc $rc status $st calls $calls wall $(tail -1 $W/passes.jsonl)"
  [ "$st" = CONTINUE ] || break
  [ $(date +%s) -lt $LAST_START ] || { p "STEP2 TIME LIMIT: no further --resume pass (last start allowed $(date -u -d @$LAST_START +%TZ))"; break; }
  [ -f $W/serve.stopped.json ] && { p "STEP2 server stopped; no further pass"; break; }
  resume="--resume"
done
touch $W/monitor.stop; wait $mon
touch $W/serve.stop
for i in $(seq 1 90); do [ -f $W/serve.stopped.json ] && break; sleep 1; done
GATE=$("${E[@]}" /mnt/data/forge-c/venv/bin/python -c "from forge_factory.workflow.builder import gate_cmd;print(gate_cmd('SWE.1','inspect'))")
echo "$GATE" > $W/gate.cmd
cd $I
bash -c "cat .forge-run/lrtx/SWE.1/inspect-reply.json | $GATE" > $W/gate.stdout 2> $W/gate.stderr
grc=$?
echo "{\"rc\":$grc,\"at\":\"$(date -u +%FT%TZ)\"}" > $W/gate.exit.json
p "STEP2 INSPECT GATE rc $grc: $(head -c 300 $W/gate.stdout | tr '\n' ' ')"
