#!/bin/sh
# F011-T037 / F011-AT-031: the CAPA-068 route fix (branch fix/route-progress-extension-inspections) against the ACP/v1
# lines. Fixtures compared from the fix tree; ACP/provider tests on the fix tree AND on the main baseline; the one
# known pre-existing failure (hostsnap backup refusal, fixed only on the F011 branch by ac7ec8d) is excluded on both.
R=/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-fix-route
B=/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-baseline-2f4b9cf
KNOWN=factory/python/tests/test_lrtx_compat.py::test_backup_inside_a_repository_is_refused
TESTS="factory/python/tests/test_acp_gate.py factory/python/tests/test_acp_proxy.py factory/python/tests/test_cre_capa_051.py factory/python/tests/test_cre_capa_052.py factory/python/tests/test_timeout_scale.py factory/python/tests/test_lrtx_compat.py"
set -e
echo fix_branch_head=$(git -C $R rev-parse HEAD) baseline=$(git -C $B rev-parse HEAD)
python factory/python/forge_factory/lrtx/compat.py --src $R --compare tests/compat/lrtx/baseline-86f1f40.json.gz
python factory/python/forge_factory/lrtx/compat.py --src $R --set v1 --compare tests/compat/lrtx/local-rtx-v1-2f4b9cf.json.gz
for T in $R $B; do echo "== ACP/provider tests on $T (without the known pre-existing test)"; (cd $T && PYTHONPATH=factory/python python -m pytest -q -p no:cacheprovider $TESTS --deselect $KNOWN | tail -1); done
echo "excluded on both trees: $KNOWN - pre-existing on main (hostsnap accepts a backup under a not-yet-created build/ dir); fixed on the F011 branch by ac7ec8d with its own regression test"
echo "== route regressions on the fix tree"; (cd $R && PYTHONPATH=factory/python python -m pytest -q -p no:cacheprovider factory/python/tests/test_rework_progress_extension.py factory/python/tests/test_t009_workflow_gates.py factory/python/tests/test_loopbacks.py | tail -1)
(cd $R && PYTHONPATH=factory/python python tests/reliability/reproducers/rpr072_route_extension_inspections.py)
(cd $B && PYTHONPATH=factory/python python $R/tests/reliability/reproducers/rpr072_route_extension_inspections.py) || echo "baseline exit $? (symptom expected)"
