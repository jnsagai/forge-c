#!/bin/bash
# Explicit OS-owner host guard artifact; never selected implicitly by production.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
: "${FORGE_LINE_PYTHON:?qualified runtime Python must be explicitly selected}"
exec "$FORGE_LINE_PYTHON" "$here/owner_launch_guard.py" --own-pid "${1:-}"
