#!/bin/bash
# ONE standalone llama-server (S3 form, 64K) + 1 s watcher: guard, VRAM samples, deadline. Kills only its own PID.
set -u
D=/mnt/data/forge-c/operations/swe1-ornith-20261031; W=$D/work; LOG=$D/progress.log
L=/mnt/data/forge-c/ollama-0.34.0/lib/ollama
BLOB=/mnt/data/forge-c/production-local-014/ollama-models/blobs/sha256-de46c4baf4b4dd85ea438bb0f757f21c38841a353506579979bba114311658c3
PORT=18592
p() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
export LD_LIBRARY_PATH=$L:$L/cuda_v13 GGML_BACKEND_PATH=$L/cuda_v13/libggml-cuda.so
DEADLINE=$(cat $W/deadline_epoch)
pre=$(bash $W/guard.sh "")
if [ "$pre" != OK ]; then echo "$pre" > $W/server.failed; p "GUARD ABORT before server start: $pre"; exit 1; fi
pgrep -u omniverse2 -x llama-server >/dev/null && { p "ABORT before start: a llama-server of ours exists"; echo OWN_SERVER_EXISTS > $W/server.failed; exit 1; }
argv=($L/llama-server --model $BLOB --alias ornith-1.5-35b-a3b-q8 --host 127.0.0.1 --port $PORT --no-webui --offline
      -c 65536 -np 1 --jinja --reasoning off --cache-type-k f16 --cache-type-v f16 --flash-attn on --gpu-layers all
      -b 2048 -ub 2048 --spec-type none --fit off --metrics)
printf '%s\n' "${argv[@]}" > $W/server.argv
t0=$(date +%s.%N); date -u +%FT%T.%NZ > $W/server.started_at
"${argv[@]}" > $W/server.log 2>&1 < /dev/null &
pid=$!; echo $pid > $W/server.pid
p "SERVER STARTING pid $pid port $PORT"
ready=0; reason=""; peak=0
vram() { local m; m=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits); echo "$(date +%s.%N),$m" >> $W/vram.csv; [ "$m" -gt "$peak" ] && peak=$m; echo $peak > $W/vram.peak; }
while :; do
  vram
  if [ $ready = 0 ] && curl -fsS -m 2 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q '"ok"'; then
    rt=$(python3 -c "print(round($(date +%s.%N)-$t0,2))"); echo $rt > $W/server.ready; ready=1
    p "SERVER STARTED pid $pid: health ok after ${rt}s; VRAM now $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) MiB (baseline 936)"
  fi
  [ -d /proc/$pid ] || { reason="SERVER_EXITED"; break; }
  [ -f $W/server.stop ] && { reason="STOP_REQUESTED"; break; }
  [ $(date +%s) -ge $DEADLINE ] && { reason="WALL_DEADLINE"; break; }
  g=$(bash $W/guard.sh $pid); echo "$(date -u +%FT%TZ) $g" > $W/server.guard
  [ "$g" = OK ] || { reason="GUARD_$g"; p "GUARD ABORT: $g - killing own server $pid"; echo "$(date -u +%FT%TZ) $g" >> $W/ABORT; break; }
  [ $ready = 0 ] && [ $(python3 -c "print(int($(date +%s.%N)-$t0))") -gt 900 ] && { reason="NOT_READY_900S"; break; }
  sleep 1
done
ks=$(date +%s.%N); kill -TERM $pid 2>/dev/null; n=0
while [ -d /proc/$pid ] && [ $n -lt 30 ]; do sleep 1; n=$((n+1)); vram; done
sig=TERM; [ -d /proc/$pid ] && { kill -KILL $pid; sig=KILL; sleep 2; }
wait $pid 2>/dev/null; rc=$?
gone=no; [ -d /proc/$pid ] || gone=yes
m=0; while [ $m -lt 60 ]; do mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits); apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr '\n' ' '); [ "$mem" -le 1200 ] && [ -z "${apps// /}" ] && break; sleep 1; m=$((m+1)); done
port_open=no; (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && port_open=yes
cat > $W/server.stopped.json <<J
{"reason":"$reason","pid":$pid,"signal":"$sig","exit_status":$rc,"process_gone":"$gone","stop_seconds":$(python3 -c "print(round($(date +%s.%N)-$ks,2))"),"vram_peak_MiB":$peak,"gpu_memory_used_MiB_after":$mem,"gpu_compute_apps_after":"${apps}","port_open_after":"$port_open","at":"$(date -u +%FT%TZ)"}
J
p "SERVER STOPPED ($reason) pid $pid signal $sig exit $rc; process_gone=$gone; GPU after ${mem} MiB, compute apps [${apps}]; port $PORT open=$port_open; VRAM peak ${peak} MiB"
