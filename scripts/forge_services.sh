#!/usr/bin/env bash
# Start/stop/status the Forge-C local runtime stack (no sudo). Each service is isolated from other projects.
#   ollama (standalone 0.34.0, :11435, models on FORGE_DATA_ROOT) -> llm-gateway (:11436) -> fabro server (:32290)
set -euo pipefail
. "$(dirname "$0")/forge-env.sh"
LOG="$FORGE_DATA_ROOT/logs"; mkdir -p "$LOG"
OLLAMA="$FORGE_DATA_ROOT/ollama-0.34.0/bin/ollama"
start_ollama() {
  curl -s -m 2 127.0.0.1:11435/api/version >/dev/null && return 0
  # 24k context (SWE.3 code generation exceeded 16k, ADR-0005): tool schemas + skill + section excerpts must fit (4k default truncated tools; see ADR-0005).
  OLLAMA_HOST=127.0.0.1:11435 OLLAMA_MODELS="$FORGE_DATA_ROOT/ollama-models" OLLAMA_CONTEXT_LENGTH=24576 \
  OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
    setsid nohup "$OLLAMA" serve >"$LOG/ollama-11435.log" 2>&1 </dev/null &
}
start_gateway() {
  curl -s -m 2 127.0.0.1:11436/health >/dev/null && return 0
  PYTHONPATH="$FORGE_REPO_ROOT/factory/python" setsid nohup "$FORGE_VENV/bin/python" -m forge_factory.llm_gateway \
    --port 11436 >"$LOG/llm-gateway.log" 2>&1 </dev/null &
}
start_fabro() {
  curl -s -m 2 127.0.0.1:32290/health >/dev/null && return 0
  (cd "$FORGE_DATA_ROOT" && setsid nohup "$FORGE_FABRO_BIN" server start --foreground --no-web --no-upgrade-check \
    --config "$FORGE_FABRO_CONFIG" --storage-dir "$FORGE_FABRO_STORAGE" >"$LOG/fabro-server.log" 2>&1 </dev/null &)
}
stop_one() { pkill -f "$1" || true; }
case "${1:-status}" in
  start) start_ollama; start_gateway; start_fabro; sleep 6; "$0" status ;;
  stop) stop_one "fabro server start --foreground --no-web --no-upgrade-check --config $FORGE_FABRO_CONFIG"
        stop_one "forge_factory.llm_gateway --port 11436"; stop_one "$OLLAMA serve" ;;
  restart-ollama) stop_one "$OLLAMA serve"; sleep 2; start_ollama; sleep 4; "$0" status ;;
  restart-gateway) stop_one "forge_factory.llm_gateway --port 11436"; sleep 1; start_gateway; sleep 3; "$0" status ;;
  status) for u in 127.0.0.1:11435/api/version 127.0.0.1:11436/health 127.0.0.1:32290/health; do
            printf '%-32s %s\n' "$u" "$(curl -s -m 3 "$u" || echo DOWN)"; done ;;
  *) echo "usage: $0 start|stop|restart-ollama|restart-gateway|status" >&2; exit 2 ;;
esac
