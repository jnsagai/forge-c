#!/usr/bin/env bash
# LRTX-T004 / ADR-0013: the existing Codex/Claude and legacy default execution line still behaves as at the preserved
# baseline 86f1f40; F011-T003: local-rtx-v1 still behaves as merged in PR #34 (2f4b9cf). Run from the checkout under
# test. Never refresh a fixture to accept a drift.
set -uo pipefail
cd "$(dirname "$0")/.."
. scripts/forge-env.sh
FIX=tests/compat/lrtx/baseline-86f1f40.json.gz
rc=0
step() { local name=$1; shift; if "$@"; then echo "PASS $name"; else echo "FAIL $name"; rc=1; fi; }
step workflow-fixtures python factory/python/forge_factory/lrtx/compat.py --src "$PWD" --compare "$FIX"
step v1-profile-fixtures python factory/python/forge_factory/lrtx/compat.py --src "$PWD" --set v1 \
  --compare tests/compat/lrtx/local-rtx-v1-2f4b9cf.json.gz
step acp-and-provider-tests env PYTHONPATH=factory/python python -m pytest -q -p no:cacheprovider \
  factory/python/tests/test_acp_gate.py factory/python/tests/test_acp_proxy.py \
  factory/python/tests/test_cre_capa_051.py factory/python/tests/test_cre_capa_052.py \
  factory/python/tests/test_timeout_scale.py factory/python/tests/test_lrtx_compat.py
step v0.1-baseline python3 -m unittest discover -s tests
step v0.3-packager python3 -m unittest discover -s factory/release-manager/tests -p 'test_*.py'
step design-check env PYTHONPATH=factory/python python tests/spec/validate_design.py
exit $rc
