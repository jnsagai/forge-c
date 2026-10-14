#!/usr/bin/env bash
# Forge-C runtime environment. Source this file: `. scripts/forge-env.sh`
# Large/mutable data (venv, caches, models, Fabro storage, state, archives) lives on the
# data volume, not the repository/root disk. Override FORGE_DATA_ROOT to relocate.
# Isolate from host Python injections (e.g. ROS PYTHONPATH plugins).
unset PYTHONPATH
export FORGE_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export FORGE_DATA_ROOT="${FORGE_DATA_ROOT:-/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c}"
export FORGE_VENV="${FORGE_VENV:-$FORGE_DATA_ROOT/venv}"
export FORGE_STATE_DIR="${FORGE_STATE_DIR:-$FORGE_DATA_ROOT/state}"
export FORGE_ARCHIVE_DIR="${FORGE_ARCHIVE_DIR:-$FORGE_DATA_ROOT/archives}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$FORGE_DATA_ROOT/cache/uv}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$FORGE_DATA_ROOT/cache/pip}"
export FORGE_OLLAMA_URL="${FORGE_OLLAMA_URL:-http://127.0.0.1:11435}"
export FORGE_FABRO_BIN="${FORGE_FABRO_BIN:-$HOME/.fabro/bin/fabro}"
export FORGE_FABRO_URL="${FORGE_FABRO_URL:-http://127.0.0.1:32290/api/v1}"
export FORGE_FABRO_CONFIG="${FORGE_FABRO_CONFIG:-$FORGE_DATA_ROOT/fabro/settings.toml}"
export FORGE_FABRO_STORAGE="${FORGE_FABRO_STORAGE:-$FORGE_DATA_ROOT/fabro/storage}"
# Isolated CLI home so Forge-C never edits the shared ~/.fabro/{settings,auth}.json of other projects.
export FORGE_FABRO_HOME="${FORGE_FABRO_HOME:-$FORGE_DATA_ROOT/fabro/home}"
forge_fabro() { HOME="$FORGE_FABRO_HOME" FABRO_NO_UPGRADE_CHECK=1 "$FORGE_FABRO_BIN" "$@"; }
export FORGE_LLVM_BIN="${FORGE_LLVM_BIN:-$FORGE_DATA_ROOT/toolchains/LLVM-19.1.7-Linux-X64/bin}"
if [ -x "$FORGE_LLVM_BIN/clang" ]; then
  export PATH="$FORGE_LLVM_BIN:$PATH"
fi
if [ -x "$FORGE_VENV/bin/python" ]; then
  export PATH="$FORGE_VENV/bin:$PATH"
fi
