"""Independent placement boundary control; explicit host/admission fixtures, no model/signing.

Real test-signed admission/native transport are separate source tests. This oracle isolates the handoff before
admission; it neither needs an OS passwd identity nor substitutes for production authorization.
"""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as S

import pytest
from forge_factory.afo import line_cloud as C
from forge_factory.afo import line_orders as O
from forge_factory.inspection import defects as D

SIGNATURE = 'cloud upstream route drops the failed inspection and owning defect context'


def main():
    scratch = Path(os.environ['FORGE_STATE_DIR'])
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rpr164-', dir=scratch) as td, pytest.MonkeyPatch.context() as mp:
        source = Path(td) / 'workorders/WO-SOURCE/workspace'
        def write(rel, value):
            path = source / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value if isinstance(value, str) else json.dumps(value))
            return path
        write('.forge-run/manifest.json', {'work_order': 'WO-SOURCE', 'phase_scope': {'stop_after': 'SWE.4'}})
        write('.forge-run/fabro_run_id', 'RUN-SOURCE\n')
        write('workproducts/SWE.1/software_requirements.md', '- **SWR-001** The driver shall preserve state.\n')
        defect = D.report(source, detected_phase='SWE.4', reported_by='swe4-author', kind='ARCHITECTURE',
            summary='The architecture assumes unsupported physical state preservation behavior.',
            requirement_ids=['SWR-001'], test_files=[], evidence_refs=['workproducts/SWE.2/software_architecture.md:1'],
            requirement_quote='The driver shall preserve state.')
        write('.forge-run/gates/gate-log.jsonl', json.dumps({'phase': 'SWE.4', 'step': 'author',
              'result': 'REJECTED', 'status': 'INCOMPLETE', 'issues': ['REQUIRED_TOOL_NOT_PASS:run_unit:FAIL']})+'\n'
              +json.dumps({'phase': 'SWE.3', 'step': 'inspect', 'gate': {'decision': 'REWORK'}})+'\n')
        write('inspection/SWE.3/INS-SWE.3-002.json', {'phase': 'SWE.3', 'inspection_id': 'INS-SWE.3-002',
            'verdict': 'FAIL', 'inspector_role': 'swe3-inspector', 'author_role': 'swe3-author',
            'items': {'SWE3-02': {'verdict': 'FAIL', 'findings': ['Review the unsupported physical assumption.'],
                                 'evidence_refs': ['workproducts/SWE.2/software_architecture.md:1']}},
            'findings': [{'id': 'SWE3-02', 'severity': 'major', 'detail': 'Review the unsupported physical assumption.'}]})
        before = {p: p.read_bytes() for p in source.rglob('*') if p.is_file()}
        plan = S(current=S(phase='SWE.4', rid='RUN-SOURCE', wo='WO-SOURCE'),
                 lineage=S(profile=C.PROFILE), action='PLACE', sweep=False,
                 order={'wo': 'WO-TARGET', 'phase': 'SWE.2', 'stop_after': 'SWE.2', 'kind': 'UPSTREAM',
                        'resume_from': 'WO-SOURCE', 'run_model': 'gpt-6.1-terra'})
        line = S(workspace=lambda wo: source,
                 ended_run=lambda wo, rid: wo == 'WO-SOURCE' and rid == 'RUN-SOURCE')
        # Observe the handoff before parent admission, whose exact input is captured unchanged.
        mp.setattr(O.Placer, '_execute', lambda self, plan, *args, **kwargs: plan.order)
        order = C.CloudPlacer(line, policy_path='UNUSED-FIXTURE')._execute(plan, None, None, [], 0, execute=False)
        assert all(p.read_bytes() == data for p, data in before.items()), 'source history mutated'
        context = order.get('rework_context')
        if not context:
            print('SYMPTOM_PRESENT:'+SIGNATURE)
            return 1
        assert context['source_work_order'] == 'WO-SOURCE' and context['phase'] == 'SWE.2'
        assert context['source_phase'] == 'SWE.4'
        args = C.context_arguments(order)
        assert args[args.index('--rework-source-phase')+1] == 'SWE.4'
        from forge_factory import rework_context as R
        snapshot = R.upstream_snapshot(source, 'SWE.2', 'SWE.4')
        assert snapshot['defects'][0]['record'] == defect
        assert snapshot['failed_reviews']['SWE.3']['inspection']['failed_items']['SWE3-02']['findings'] == [
            'Review the unsupported physical assumption.']
        print('SYMPTOM_ABSENT')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
