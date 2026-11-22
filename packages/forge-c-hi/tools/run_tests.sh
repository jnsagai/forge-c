#!/bin/sh
# Run the forge-c-hi test suite in an isolated environment.
#   FORGE_HI_PY  python interpreter with pytest (default: python3)
# PYTHONPATH is cleared so host-wide plugins (e.g. ROS launch_testing) do not load.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$here"
exec env -u PYTHONPATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "${FORGE_HI_PY:-python3}" -m pytest "$@"
