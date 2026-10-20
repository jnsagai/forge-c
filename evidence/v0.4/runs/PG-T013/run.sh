set -euo pipefail
cd /home/jefferson/forge-c-afo-t001
git checkout -q -- . && git clean -fdq evidence/ docs/ 2>/dev/null || true
git checkout -q --detach b2c4ab3
[ "$(git rev-parse --short HEAD)" = b2c4ab3 ] || { echo "WRONG HEAD"; exit 9; }
for f in /home/jefferson/forge-c/examples/0002-arm_55_rcc_st/inputs/*.md; do cp -p "$f" examples/0002-arm_55_rcc_st/inputs/; done
. scripts/forge-env.sh >/dev/null
export PYTHONPATH=$PWD/factory/python:$PWD/factory/python/tests FORGE_REPO_ROOT=$PWD
python tests/spec/validate_design.py >/dev/null 2>&1 && echo "design PASS"
for s in specs/005-autonomous-factory-operations specs/006-enhanced-ai-software-assurance; do python $s/validate_spec.py >/dev/null && echo "$s PASS"; done
ruff check --output-format concise factory/python/forge_factory | tail -1
timeout 6000 python -m forge_factory.assurance.regress --full --out /tmp/claude-1000/-home-jefferson-forge-c/1c0d4aec-d691-4be5-9acf-29be01f58966/scratchpad/regression-main-b2c4ab3.json >/dev/null 2>&1; echo "regress exit $?"
python3 -c "import json;d=json.load(open('/tmp/claude-1000/-home-jefferson-forge-c/1c0d4aec-d691-4be5-9acf-29be01f58966/scratchpad/regression-main-b2c4ab3.json'));print(d['status'],[(c['case_id'],c['status']) for c in d['cases']])"
git checkout -q -- . 
