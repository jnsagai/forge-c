#!/usr/bin/env bash
# T003: reproducible, offline-capable bootstrap of the Forge-C factory Python environment.
# Uses only OSS packages from a hash-pinned lockfile; no paid services, no cloud APIs.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
venv="${1:-${FORGE_VENV:-$root/.venv}}"
command -v uv >/dev/null || { echo "MISSING: uv (https://github.com/astral-sh/uv, MIT/Apache-2.0)" >&2; exit 2; }
uv venv --python "${FORGE_PYTHON:-3.13}" "$venv" >/dev/null
uv pip install --python "$venv/bin/python" --require-hashes -r "$root/requirements/forge-factory.lock" -q
uv pip install --python "$venv/bin/python" --no-deps -e "$root" -q
"$venv/bin/python" -c "import forge_factory, mcp, fastapi, jsonschema, yaml; print('BOOTSTRAP PASS', forge_factory.__version__)"
