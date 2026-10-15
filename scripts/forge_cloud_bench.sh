#!/usr/bin/env bash
# User-authorized CLOUD BENCHMARK stack (2026-10-15): DeepSeek API behind an isolated Fabro server + gateway.
#   gateway :11437 -> https://api.deepseek.com (reasoning stripped, cost-capped, metered to its own JSONL)
#   fabro   :32291 (own storage/home under $FORGE_DATA_ROOT/fabro-cloud; never ~/.fabro, never the local :32290)
# The API key is read from FORGE_DEEPSEEK_ENV (default ~/.config/sesn/deepseek.env) and stored only in the isolated
# server's vault (POST /api/v1/secrets); never in the repository, logs or meters. `purge-key` deletes it from the
# vault. Usage: start|stop|status|env|purge-key
set -euo pipefail
. "$(dirname "$0")/forge-env.sh"
ROOT="$FORGE_DATA_ROOT/fabro-cloud"; LOG="$FORGE_DATA_ROOT/logs"; mkdir -p "$ROOT/storage" "$ROOT/home/.fabro" "$LOG"
KEYFILE="${FORGE_DEEPSEEK_ENV:-$HOME/.config/sesn/deepseek.env}"
CAP="${FORGE_CLOUD_COST_CAP_USD:-2.00}"
CFG="$ROOT/settings.toml"
write_config() {
  cat > "$CFG" <<EOF
_version = 1
# Forge-C CLOUD BENCHMARK Fabro server (isolated; user-authorized DeepSeek API use).
[server.listen]
type = "tcp"
address = "127.0.0.1:32291"
[server.api]
url = "http://127.0.0.1:32291/api/v1"
[server.web]
enabled = false
url = "http://127.0.0.1:32291"
[server.auth]
methods = ["dev-token"]
[server.storage]
root = "$ROOT/storage"
[server.artifacts]
provider = "local"
prefix = "artifacts"
[server.artifacts.local]
root = "$ROOT/storage/objects"
[server.scheduler]
max_concurrent_runs = 1
[server.sandbox.providers.local]
enabled = true

[llm.providers.deepseek]
enabled = true
base_url = "http://127.0.0.1:11437"

[run.model]
name = "deepseek-flash"
provider = "deepseek"
[run.environment]
id = "local"
EOF
  printf '_version = 1\n[cli.target]\ntype = "http"\nurl = "http://127.0.0.1:32291/api/v1"\n' > "$ROOT/home/.fabro/settings.toml"
}
case "${1:-status}" in
  start)
    [ -r "$KEYFILE" ] || { echo "missing $KEYFILE" >&2; exit 2; }
    write_config
    if [ ! -s "$ROOT/storage/server.env" ]; then  # fresh isolated server secrets (0600), like the local server
      ( umask 077; printf 'SESSION_SECRET=%s\nFABRO_DEV_TOKEN=fabro_dev_%s\n' "$(openssl rand -hex 32)" \
          "$(openssl rand -hex 32)" > "$ROOT/storage/server.env" )
    fi
    ( umask 077; "$FORGE_VENV/bin/python" - "$ROOT" <<'PY'
import json, sys, datetime, pathlib
root = pathlib.Path(sys.argv[1])
tok = [l.split("=", 1)[1].strip() for l in (root / "storage/server.env").read_text().splitlines()
       if l.startswith("FABRO_DEV_TOKEN=")][0]
auth = {"servers": {"http://127.0.0.1:32291": {"kind": "dev-token", "token": tok,
        "logged_in_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}}}
(root / "home/.fabro/auth.json").write_text(json.dumps(auth))
PY
    )
    if ! curl -s -m 2 127.0.0.1:11437/health >/dev/null; then
      FORGE_GATEWAY_COST_CAP_USD="$CAP" FORGE_GATEWAY_PRICE_MISS_PER_M=0.14 FORGE_GATEWAY_PRICE_HIT_PER_M=0.0028 \
      FORGE_GATEWAY_PRICE_OUT_PER_M=0.28 PYTHONPATH="$FORGE_REPO_ROOT/factory/python" setsid nohup \
        "$FORGE_VENV/bin/python" -m forge_factory.llm_gateway --port 11437 --upstream https://api.deepseek.com \
        --meter "$FORGE_STATE_DIR/llm-gateway/usage-cloud-deepseek.jsonl" >"$LOG/llm-gateway-cloud.log" 2>&1 </dev/null &
    fi
    if ! curl -s -m 2 127.0.0.1:32291/health >/dev/null; then
      ( cd "$ROOT" && setsid nohup "$FORGE_FABRO_BIN" server start --foreground --no-web \
          --no-upgrade-check --config "$CFG" --storage-dir "$ROOT/storage" >"$LOG/fabro-cloud.log" 2>&1 </dev/null & )
    fi
    sleep 6
    PYTHONPATH="$FORGE_REPO_ROOT/factory/python" "$FORGE_VENV/bin/python" -m forge_factory.fabro.vault store \
      --url http://127.0.0.1:32291/api/v1 --storage "$ROOT/storage" --env-file "$KEYFILE"
    "$0" status ;;
  stop) pkill -f "fabro server start --foreground --no-web --no-upgrade-check --config $CFG" || true
        pkill -f "forge_factory.llm_gateway --port 11437" || true ;;
  env)  # export for a cloud-benchmark work order: . <(scripts/forge_cloud_bench.sh env)
        echo "export FORGE_FABRO_URL=http://127.0.0.1:32291/api/v1 FORGE_FABRO_HOME=$ROOT/home FORGE_FABRO_STORAGE=$ROOT/storage FORGE_FABRO_CONFIG=$CFG" ;;
  purge-key) PYTHONPATH="$FORGE_REPO_ROOT/factory/python" "$FORGE_VENV/bin/python" -m forge_factory.fabro.vault purge \
      --url http://127.0.0.1:32291/api/v1 --storage "$ROOT/storage" ;;
  status) for u in 127.0.0.1:11437/health 127.0.0.1:32291/health; do printf '%-32s %s\n' "$u" "$(curl -s -m 2 $u || echo DOWN)"; done ;;
  *) echo "usage: $0 start|stop|status|env|purge-key" >&2; exit 2 ;;
esac
