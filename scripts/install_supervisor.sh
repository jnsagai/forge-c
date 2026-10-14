#!/usr/bin/env bash
# Install/start the Forge-C supervisor as a user systemd service (no sudo). Usage: install_supervisor.sh [--no-dispatch]
set -euo pipefail
. "$(dirname "$0")/forge-env.sh"
unit="$HOME/.config/systemd/user/forge-supervisor.service"
mkdir -p "$(dirname "$unit")"
sed -e "s|@VENV@|$FORGE_VENV|g" -e "s|@REPO@|$FORGE_REPO_ROOT|g" -e "s|@DATA@|$FORGE_DATA_ROOT|g" \
    -e "s|@PATH@|$PATH|g" -e "s|@EXTRA_ARGS@|${1:-}|g" "$FORGE_REPO_ROOT/deploy/systemd/forge-supervisor.service.in" > "$unit"
systemctl --user daemon-reload
systemctl --user enable --now forge-supervisor.service
systemctl --user --no-pager status forge-supervisor.service | head -5
