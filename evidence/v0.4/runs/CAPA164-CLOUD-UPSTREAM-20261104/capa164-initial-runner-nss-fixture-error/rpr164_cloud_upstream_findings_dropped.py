"""Independent normal signed-placement control, synthetic host/transport only; zero real model calls."""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from forge_factory.afo import line_cloud as C
from forge_factory.afo import line_orders as O
from forge_factory.common import REPO_ROOT
from forge_factory.inspection import defects as D

sys.path.insert(0, str(REPO_ROOT / 'factory/python/tests'))
import test_line_conductor_m3 as M
from test_cloud_line_scheduler import cloud

SIGNATURE = 'cloud upstream route drops the failed inspection and owning defect context'


def main():
    scratch = Path(os.environ['FORGE_STATE_DIR'])
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rpr164-', dir=scratch) as td, pytest.MonkeyPatch.context() as mp:
        env = M.env.__wrapped__(Path(td), mp)
        placer = cloud(env)
        line = env['line']
        for _ in range(3):
            placer.cycle()
            placer.cycle()
            for order in list(line.launched):
                ws = line.workspace(order['wo'])
                rid = (ws / '.forge-run/fabro_run_id').read_text()
                if line.fabro[rid] == 'running':
                    line.finish(order['wo'])
        placer.cycle()
        placer.cycle()
        source_wo = 'WO-F014-CMP-SWE4-CRCHAL-20261104-T1'
        source = line.workspace(source_wo)
        reqs = source / 'workproducts/SWE.1/software_requirements.md'
        reqs.parent.mkdir(parents=True, exist_ok=True)
        reqs.write_text('- **SWR-001** The driver shall preserve state.\n')
        defect = D.report(source, detected_phase='SWE.4', reported_by='swe4-author', kind='ARCHITECTURE',
            summary='The architecture assumes an unsupported physical state preservation behavior.',
            requirement_ids=['SWR-001'], test_files=[], evidence_refs=['workproducts/SWE.2/software_architecture.md:1'],
            requirement_quote='The driver shall preserve state.')
        line.finish(source_wo, ['REQUIRED_TOOL_NOT_PASS:run_unit:FAIL'])
        path = source / 'inspection/SWE.3/INS-SWE.3-002.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'phase': 'SWE.3', 'inspection_id': 'INS-SWE.3-002', 'verdict': 'FAIL',
            'inspector_role': 'swe3-inspector', 'author_role': 'swe3-author',
            'items': {'SWE3-02': {'verdict': 'FAIL', 'findings': ['Review the unsupported physical assumption.'],
                                 'evidence_refs': ['workproducts/SWE.2/software_architecture.md:1']}},
            'findings': [{'id': 'SWE3-02', 'severity': 'major', 'detail': 'Review the unsupported physical assumption.'}]}))
        gates = source / '.forge-run/gates/gate-log.jsonl'
        with gates.open('a') as stream:
            stream.write(json.dumps({'phase': 'SWE.3', 'step': 'inspect', 'gate': {'decision': 'REWORK'}})+'\n')
        before = {p: p.read_bytes() for p in source.rglob('*') if p.is_file()}
        count = len(line.launched)
        placer.cycle()
        assert len(line.launched) == count + 1, 'normal upstream admission did not proceed'
        resumed = line.launched[-1]
        assert resumed['--stop-after'] == 'SWE.2' and resumed['--resume-from'] == source_wo
        spec = O._load(O.supervisor_dir() / 'line-orders' / (resumed['wo']+'.json'))
        assert spec['kind'] == 'UPSTREAM' and spec['digest'] == O._digest(spec)
        assert all(p.read_bytes() == data for p, data in before.items()), 'source history mutated'
        context = spec.get('rework_context')
        if not context:
            print('SYMPTOM_PRESENT:'+SIGNATURE)
            return 1
        assert context['source_work_order'] == source_wo and context['phase'] == 'SWE.2'
        assert context['source_phase'] == 'SWE.4'
        args = C.context_arguments(spec)
        assert args[args.index('--rework-source-phase')+1] == 'SWE.4'
        from forge_factory import rework_context as R
        snapshot = R.upstream_snapshot(source, 'SWE.2', 'SWE.4')
        assert snapshot['defects'][0]['record'] == defect
        assert snapshot['failed_reviews']['SWE.3']['inspection']['failed_items']['SWE3-02']['findings'] == [
            'Review the unsupported physical assumption.']
        print('SYMPTOM_ABSENT:'+SIGNATURE)
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
