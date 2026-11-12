#!/bin/bash
# ONE own llama-server (factory llama_server_spec argv) + the factory gateway in front of it, with a 1 s watcher.
set -u
D=/mnt/data/forge-c/operations/swe1-ornith-20261031; W=$D/inspect-work; LOG=$D/progress.log; R=$D/repo
PORT=18593; GWPORT=18594
p() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
DEADLINE=$(cat $W/deadline_epoch)
pre=$(bash $D/work/guard.sh "")
if [ "$pre" != OK ]; then echo "$pre" > $W/serve.failed; p "STEP2 GUARD ABORT before server start: $pre"; exit 1; fi
pgrep -u omniverse2 -x llama-server >/dev/null && { p "STEP2 ABORT: a llama-server of ours exists"; echo OWN_SERVER_EXISTS > $W/serve.failed; exit 1; }
mapfile -t argv < <(python3 -c "import json;print('\n'.join(json.load(open('$W/llama.spec.json'))['argv']))")
printf '%s\n' "${argv[@]}" > $W/server.argv
L=/mnt/data/forge-c/production-local-014/ollama-0.34.0/lib/ollama
t0=$(date +%s.%N); date -u +%FT%T.%NZ > $W/server.started_at
env LD_LIBRARY_PATH=$L:$L/cuda_v13 GGML_BACKEND_PATH=$L/cuda_v13/libggml-cuda.so "${argv[@]}" > $W/server.log 2>&1 < /dev/null &
pid=$!; echo $pid > $W/server.pid
p "STEP2 SERVER STARTING qwen3.8:27b-q8_0 pid $pid port $PORT (factory llama_server_spec argv)"
mkdir -p $D/inspect-state/llm-gateway
gwpid=""; ready=0; gwready=0; reason=""; peak=0
vram() { local m; m=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits); echo "$(date +%s.%N),$m" >> $W/vram.csv; [ "$m" -gt "$peak" ] && peak=$m; echo $peak > $W/vram.peak; }
start_gw() {
  cd $R/factory/python
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
    PYTHONPATH=$R/factory/python PYTHONDONTWRITEBYTECODE=1 FORGE_STATE_DIR=$D/inspect-state FORGE_DATA_ROOT=/mnt/data/forge-c \
    FORGE_LRTX_PROFILE=local-rtx-v2-omniverse2-q38-delivery-first \
    FORGE_GATEWAY_MAX_INFLIGHT=1 FORGE_GATEWAY_MAX_QUEUE=8 FORGE_GATEWAY_MAX_WAIT_S=21600 FORGE_GATEWAY_SAMPLE_S=10 \
    FORGE_GATEWAY_REASONING='{"qwen3.8:27b-q8_0": {"effort": "medium", "extra_output_tokens": 8192, "role_efforts": {}, "system_message_order": "merge_first"}}' \
    FORGE_GATEWAY_REQUEST_MEASUREMENT='{"qwen3.8:27b-q8_0": "native_template_plus_serialized"}' \
    FORGE_GATEWAY_MEASURE_UNBOUND=1 FORGE_GATEWAY_NATIVE_CONTEXT_LIMIT=262144 FORGE_GATEWAY_REQUEST_TIMEOUT_S=21600 \
    FORGE_GATEWAY_DROP_RETRIES=0 FORGE_GATEWAY_ROUTES='{"qwen3.8:27b-q8_0": "http://127.0.0.1:18593"}' \
    /mnt/data/forge-c/venv/bin/python -m forge_factory.llm_gateway --port $GWPORT --upstream http://127.0.0.1:18595 \
    --meter $D/inspect-state/llm-gateway/usage.jsonl > $W/gateway.log 2>&1 < /dev/null &
  gwpid=$!; echo $gwpid > $W/gateway.pid; cd $W
}
while :; do
  vram
  if [ $ready = 0 ] && curl -fsS -m 2 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q '"ok"'; then
    rt=$(python3 -c "print(round($(date +%s.%N)-$t0,2))"); echo $rt > $W/server.ready; ready=1
    p "STEP2 SERVER UP pid $pid: health ok after ${rt}s; VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) MiB; n_ctx: $(grep -o 'n_ctx_slot = [0-9]*' $W/server.log | head -1)"
    start_gw
  fi
  if [ $ready = 1 ] && [ $gwready = 0 ] && curl -fsS -m 2 http://127.0.0.1:$GWPORT/health 2>/dev/null | grep -q '"ok"'; then
    gwready=1; date -u +%FT%TZ > $W/gateway.ready; p "STEP2 GATEWAY UP pid $gwpid port $GWPORT -> llama $PORT (profile reasoning: effort medium, extra_output_tokens 8192, role_efforts {})"
  fi
  [ -d /proc/$pid ] || { reason="SERVER_EXITED"; break; }
  [ -n "$gwpid" ] && ! [ -d /proc/$gwpid ] && { reason="GATEWAY_EXITED"; break; }
  [ -f $W/serve.stop ] && { reason="STOP_REQUESTED"; break; }
  [ $(date +%s) -ge $DEADLINE ] && { reason="WALL_DEADLINE"; break; }
  g=$(bash $D/work/guard.sh $pid); echo "$(date -u +%FT%TZ) $g" > $W/server.guard
  [ "$g" = OK ] || { reason="GUARD_$g"; p "STEP2 GUARD ABORT: $g - killing own server $pid and gateway $gwpid"; echo "$(date -u +%FT%TZ) $g" >> $W/ABORT; break; }
  [ $ready = 0 ] && [ $(python3 -c "print(int($(date +%s.%N)-$t0))") -gt 900 ] && { reason="NOT_READY_900S"; break; }
  sleep 1
done
ks=$(date +%s.%N)
[ -n "$gwpid" ] && kill -TERM $gwpid 2>/dev/null
kill -TERM $pid 2>/dev/null; n=0
while { [ -d /proc/$pid ] || { [ -n "$gwpid" ] && [ -d /proc/$gwpid ]; }; } && [ $n -lt 30 ]; do sleep 1; n=$((n+1)); vram; done
sig=TERM; [ -d /proc/$pid ] && { kill -KILL $pid; sig=KILL; sleep 2; }
[ -n "$gwpid" ] && [ -d /proc/$gwpid ] && { kill -KILL $gwpid; sleep 1; }
wait $pid 2>/dev/null; rc=$?
gone=no; [ -d /proc/$pid ] || gone=yes; gwgone=yes; [ -n "$gwpid" ] && [ -d /proc/$gwpid ] && gwgone=no
m=0; while [ $m -lt 60 ]; do mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits); apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr '\n' ' '); [ "$mem" -le 1200 ] && [ -z "${apps// /}" ] && break; sleep 1; m=$((m+1)); done
po=no; (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && po=yes; gpo=no; (echo > /dev/tcp/127.0.0.1/$GWPORT) 2>/dev/null && gpo=yes
cat > $W/serve.stopped.json <<J
{"reason":"$reason","pid":$pid,"gateway_pid":"$gwpid","signal":"$sig","exit_status":$rc,"process_gone":"$gone","gateway_gone":"$gwgone","stop_seconds":$(python3 -c "print(round($(date +%s.%N)-$ks,2))"),"vram_peak_MiB":$peak,"gpu_memory_used_MiB_after":$mem,"gpu_compute_apps_after":"${apps}","port_open_after":"$po","gateway_port_open_after":"$gpo","at":"$(date -u +%FT%TZ)"}
J
p "STEP2 SERVER+GATEWAY STOPPED ($reason) server $pid signal $sig exit $rc gone=$gone; gateway $gwpid gone=$gwgone; GPU after ${mem} MiB apps [${apps}]; ports $PORT open=$po $GWPORT open=$gpo; VRAM peak ${peak} MiB"
