from pathlib import Path
import sqlite3,json
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
p=E/'state/knowledge/lessons.sqlite3'
out={'path':str(p),'exists':p.exists(),'read_only':True,'model_calls':0,'candidate_execution':False}
if p.exists():
 with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as db:
  db.row_factory=sqlite3.Row
  tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if {'job_experience','learning_dispositions'}.issubset(tables):
   out['by_native']=[]
   for rid in ('01M67ETTPXS1Q73QPMQ98DNJX0','01M67R1HNE9TKPWCYJ2SVKEPJS','01M67ZJWDYS7H33828MPTK6E6D'):
    rows=[dict(r) for r in db.execute('SELECT e.phase,e.outcome,d.state,COUNT(*) AS observations FROM job_experience e LEFT JOIN learning_dispositions d USING(experience_id) WHERE e.execution_id=? GROUP BY e.phase,e.outcome,d.state ORDER BY e.phase,e.outcome,d.state',(rid,))]
    out['by_native'].append({'native_id':rid,'phase_outcome_dispositions':rows})
   out['all_dispositions']=[dict(r) for r in db.execute('SELECT state,COUNT(*) AS n FROM learning_dispositions GROUP BY state')]
  if 'lesson_qualifications' in tables:out['lesson_qualifications']=db.execute('SELECT COUNT(*) FROM lesson_qualifications').fetchone()[0]
  if 'lesson_transfers' in tables:out['lesson_transfers']=[dict(r) for r in db.execute('SELECT kind,COUNT(*) AS n FROM lesson_transfers GROUP BY kind')]
import os,sys,subprocess
os.environ.update(json.loads((E/'control/runtime-env-v6.json').read_text()));sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.common import utc_now,sha256_file
out['at']=utc_now();out['schema']='forge-c/ordinary-job-learning-observation/1'
out['source_revision']=subprocess.check_output(['git','-C',str(E/'source'),'rev-parse','HEAD'],text=True).strip()
out['limits']=['Factual capture/dispositions only; no qualified lesson/transfer or measured learning benefit','Multiple factual observations of one native phase are not extra jobs/outcomes/lessons','JOB SUCCEEDED native and JOB BLOCKED strict package are distinct facts, not conflicting release approval','DEFERRED_BUDGET here means default zero inference consolidation allowance, not proof of global mission exhaustion','No causal benefit or learning overhead comparison measured']
dest=E/'control/qualification-observations'/('ordinary-job-learning-'+digest(out)+'.json')
immutable_json(dest,out)
print(json.dumps({'path':str(dest),'sha256':sha256_file(dest),'source_revision':out['source_revision'],'dispositions':out.get('all_dispositions'),'qualified_lessons':out.get('lesson_qualifications'),'model_calls':0}))
