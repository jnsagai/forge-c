#!/bin/bash
# ONE own llama-server (direct, no gateway) for qwen3-coder-next:q4_K_M with partial MoE offload, plus a 1 s watcher:
# guard (gpuq, foreign GPU processes, conductor heartbeat, intent hashes), VRAM + host RSS samples, wall deadline.
# Kills only its own server PID. Arg 1: server.argv file (one token per line).
set -u
D=/mnt/data/forge-c/operations/swe1-codernext-20261031; W=$D/work; LOG=$D/progress.log
PORT=18610
p() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
DEADLINE=$(cat $W/serve_deadline_epoch)
rm -f $W/server.ready $W/serve.stopped.json $W/serve.failed $W/serve.stop
pre=$(bash $W/guard.sh "")
if [ "$pre" != OK ]; then echo "$pre" > $W/serve.failed; p "GUARD ABORT before server start: $pre"; exit 1; fi
pgrep -u omniverse2 -x llama-server >/dev/null && { p "ABORT: a llama-server of ours exists"; echo OWN_SERVER_EXISTS > $W/serve.failed; exit 1; }
(echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && { p "ABORT: port $PORT open"; echo PORT_OPEN > $W/serve.failed; exit 1; }
mapfile -t argv < $1
L=/mnt/data/forge-c/ollama-0.34.0/lib/ollama
t0=$(date +%s.%N); date -u +%FT%T.%NZ > $W/server.started_at
env LD_LIBRARY_PATH=$L:$L/cuda_v13 GGML_BACKEND_PATH=$L/cuda_v13/libggml-cuda.so "${argv[@]}" > $W/server.log 2>&1 < /dev/null &
pid=$!; echo $pid > $W/server.pid
p "SERVER STARTING qwen3-coder-next:q4_K_M pid $pid port $PORT (argv $1: $(tr '\n' ' ' < $1 | sed 's#/mnt/data/forge-c/production-local-014/ollama-models/blobs/##'))"
ready=0; reason=""; peak=0; rpeak=0
vram() {
  local m r; m=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  r=$(awk '/^VmRSS/{a=$2}/^RssAnon/{b=$2}/^RssFile/{c=$2}END{print a","b","c}' /proc/$pid/status 2>/dev/null)
  echo "$(date +%s.%N),$m,${r:-,,}" >> $W/vram.csv; [ "$m" -gt "$peak" ] && peak=$m; echo $peak > $W/vram.peak
  local rk=${r%%,*}; [ -n "$rk" ] && [ "$rk" -gt "$rpeak" ] && rpeak=$rk; echo $rpeak > $W/rss.peak.kB
}
while :; do
  vram
  if [ $ready = 0 ] && curl -fsS -m 2 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q '"ok"'; then
    rt=$(python3 -c "print(round($(date +%s.%N)-$t0,2))"); echo $rt > $W/server.ready; ready=1
    p "SERVER UP pid $pid: health ok after ${rt}s; VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) MiB (baseline 936); host RSS $(awk '/^VmRSS/{print $2}' /proc/$pid/status) kB; $(grep -o 'n_ctx_slot = [0-9]*' $W/server.log | head -1)"
  fi
  [ -d /proc/$pid ] || { reason="SERVER_EXITED"; break; }
  [ -f $W/serve.stop ] && { reason="STOP_REQUESTED"; break; }
  [ $(date +%s) -ge $DEADLINE ] && { reason="WALL_DEADLINE"; p "WALL DEADLINE reached - stopping own server $pid"; break; }
  if [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)" -gt 46500 ]; then reason="VRAM_OVER_46500"; p "VRAM over 46500 MiB - stopping own server $pid"; break; fi
  g=$(bash $W/guard.sh $pid); echo "$(date -u +%FT%TZ) $g" > $W/server.guard
  [ "$g" = OK ] || { reason="GUARD_$g"; p "GUARD ABORT: $g - killing own server $pid"; echo "$(date -u +%FT%TZ) $g" >> $W/ABORT; break; }
  [ $ready = 0 ] && [ $(python3 -c "print(int($(date +%s.%N)-$t0))") -gt 900 ] && { reason="NOT_READY_900S"; break; }
  sleep 1
done
ks=$(date +%s.%N)
kill -TERM $pid 2>/dev/null; n=0
while [ -d /proc/$pid ] && [ $n -lt 30 ]; do sleep 1; n=$((n+1)); vram; done
sig=TERM; [ -d /proc/$pid ] && { kill -KILL $pid; sig=KILL; sleep 2; }
wait $pid 2>/dev/null; rc=$?
gone=no; [ -d /proc/$pid ] || gone=yes
m=0; while [ $m -lt 60 ]; do mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits); apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr '\n' ' '); [ "$mem" -le 1200 ] && [ -z "${apps// /}" ] && break; sleep 1; m=$((m+1)); done
po=no; (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && po=yes
cat > $W/serve.stopped.json <<J
{"reason":"$reason","pid":$pid,"signal":"$sig","exit_status":$rc,"process_gone":"$gone","stop_seconds":$(python3 -c "print(round($(date +%s.%N)-$ks,2))"),"vram_peak_MiB":$peak,"host_rss_peak_kB":$rpeak,"gpu_memory_used_MiB_after":$mem,"gpu_compute_apps_after":"${apps}","port_open_after":"$po","at":"$(date -u +%FT%TZ)"}
J
p "SERVER STOPPED ($reason) server $pid signal $sig exit $rc gone=$gone; GPU after ${mem} MiB apps [${apps}]; port $PORT open=$po; VRAM peak ${peak} MiB; host RSS peak ${rpeak} kB"
