#!/usr/bin/env bash
set -euo pipefail
repo="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$repo"
evidence="evidence/014-durable-local-autonomy/typed-register-interface-b8ecd269"
sha256sum --check "$evidence/source-files.sha256"
data="${FORGE_DATA_ROOT:-/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c}"
if [[ "$(findmnt -no SOURCE --target "$data")" != /dev/loop10 ]]; then
    echo "This local reproduction requires project storage on loop10." >&2
    exit 2
fi
export FORGE_DATA_ROOT="$data"
export PATH="$data/toolchains/LLVM-19.1.7-Linux-X64/bin:$data/toolchains/formal/bin:$data/toolchains/renode/renode_1.17.0-portable:$PATH"
export FORGE_FABRO_BIN=/home/jefferson/.fabro/bin/fabro
export PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 FORGE_FABRO_LIVE=0
export PYTHONPATH="$repo/factory/python"
export TMPDIR="$(mktemp -d "$data/operations/feature014/typed-reproduce.XXXXXX")"
test_python="$data/venv/bin/python"
"$test_python" -m pytest -q factory/python/tests/test_typed_register_interface.py factory/python/tests/test_swe3_regmap.py factory/python/tests/test_swe3_implementation.py factory/python/tests/test_regmap_multi_instance.py factory/python/tests/test_guideline_check.py factory/python/tests/test_delivery_first.py factory/python/tests/test_delivery_first_scenario_contract.py factory/python/tests/test_delivery_first_package_order.py factory/python/tests/test_delivery_first_edit_provenance.py factory/python/tests/test_layer_split.py --junitxml="$TMPDIR/regression.xml"
"$test_python" -m ruff check factory/python/forge_factory/inspection/typed_registers.py factory/python/forge_factory/inspection/regmap.py factory/python/forge_factory/inspection/implementation.py factory/python/forge_factory/delivery_first.py factory/python/tests/test_typed_register_interface.py
"$test_python" specs/014-durable-local-autonomy/validate_spec.py
"$test_python" specs/014-durable-local-autonomy/contracts/validate_contracts.py
"$test_python" tests/spec/validate_design.py
echo "Retained local synthetic-fixture results: $TMPDIR"
