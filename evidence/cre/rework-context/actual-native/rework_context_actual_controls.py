"""Prepare real retained cloud cases read-only; do not install, render a workflow or launch a model."""
from pathlib import Path
import datetime
import json
import subprocess
from forge_factory import rework_context as C
from forge_factory.common import sha256_file, REPO_ROOT, state_dir

b=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
assert state_dir() == b/'lrtx-cloud-bridge/state'
out=b/'ops/scratch/rework-context-qualification-v2'
out.mkdir(exist_ok=True)
results=[]
for tag,n in (('CRCHAL',3),('WWDGHAL',4)):
    source=f'WO-F014-CMP-SWE{n}-{tag}-20261104-T1E'
    base=f'WO-F014-CMP-SWE{n-1}-{tag}-20261104-T1E'
    src=state_dir()/'workorders'/source/'workspace'
    dst=state_dir()/'workorders'/base/'workspace'
    phase=f'SWE.{n}'
    m=json.loads((dst/'.forge-run/manifest.json').read_text())
    m.update(work_order=f'WO-QUAL-REWORK-{tag}',resumed_from={'source_work_order':base})
    inspections=sorted((src/'inspection'/phase).glob('INS*'))
    req={'source_work_order':source,'phase':phase,
         'gate_log_sha256':sha256_file(src/'.forge-run/gates/gate-log.jsonl'),
         'inspection_sha256':sha256_file(inspections[-1]) if inspections else 'ABSENT'}
    doc=C.prepare(dst,m,req,phase)
    p=out/(tag+'-prepared-data.json')
    p.write_text(json.dumps(doc,indent=2)+'\n')
    try:
        C.prepare(dst,m,{**req,'gate_log_sha256':'0'*64},phase)
        raise AssertionError('bad gate hash accepted')
    except C.ReworkRefused as exc:
        negative=str(exc)
    results.append({'tag':tag,'status':'PASS','request':req,'inspection_state':doc['inspection_state'],
                    'gate_record_count':len(doc['gate_records']),
                    'failed_inspection_items':list((doc['inspection'] or {}).get('failed_items',{})),
                    'negative':negative,'prepared_data':str(p),'prepared_sha256':sha256_file(p),
                    'complete_bytes':p.stat().st_size,'complete_lines':len(p.read_text().splitlines()),
                    'target_writes':False})
report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'mode':'READ_ONLY_ACTUAL_SOURCE_PREPARE_NO_INSTALL_OR_LAUNCH',
        'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO_ROOT,text=True).strip(),
        'module_sha256':sha256_file(Path(C.__file__)),
        'model_calls':0,'results':results}
(out/'actual-source-controls.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,separators=(',',':')))
