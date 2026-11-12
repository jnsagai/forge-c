from pathlib import Path
import json,os,sys,subprocess
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.durable import digest
from forge_factory.common import utc_now
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 with S.tx() as c:j=json.loads(c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id='afo-agent-61401956787984d8c097bc36'").fetchone()[0])
d=Path(j['case']).parent;case=json.loads(Path(j['case']).read_text());intent=json.loads((d/'submission-intent.json').read_text());src=Path(case['src'])
head=subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
actual=subprocess.check_output(['git','-C',str(src),'show','-s','--format=%P%n%T%n%B',head],text=True).strip().split('\n',2)
print(json.dumps({'at':utc_now(),'job_state':j['state'],'job_id':j['job_id'],'run_id':j['run_id'],'head':head,'parent_equal':actual[0]==intent['parent'],'tree_equal':actual[1]==intent['tree'],'message_equal':actual[2]==intent['message'],'expected_message_repr':repr(intent['message']),'actual_message_repr':repr(actual[2]),'expected_len':len(intent['message']),'actual_len':len(actual[2]),'trailing_space_only':actual[2]==intent['message'].rstrip(' '),'intent_sha256':digest(intent),'submission_receipt_exists':(d/'submission-receipt.json').exists(),'model_requests':0},indent=2))
