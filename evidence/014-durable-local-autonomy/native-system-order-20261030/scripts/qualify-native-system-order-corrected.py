
from pathlib import Path
import subprocess,json,sys,os,hashlib
import httpx
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');Q=N/'source-gateway-71906039'
rev='719060396f3b9172465af7fab2d81e9987024842'
if not (Q/'.git').exists():
 subprocess.run(['git','clone','--shared','--no-checkout',str(N/'source'),str(Q)],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['git','-C',str(Q),'fetch',str(N/'native-system-order-factory.bundle'),'HEAD'],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['git','-C',str(Q),'checkout','--detach',rev],check=True,stdout=subprocess.DEVNULL)
assert subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()==rev
os.environ.update(FORGE_REPO_ROOT=str(Q),FORGE_DATA_ROOT=str(N),PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory import llm_gateway as gw
from forge_factory.lrtx import profile,stack
from forge_factory.common import canonical_json,utc_now,sha256_file
p=profile.load('local-rtx-v2-omniverse2-q38-qm-native-artifacts')
model=p['models']['default'];pol=json.loads(stack.gateway_reasoning(p))
messages=[{'role':'system','content':'Synthetic system contract α; preserve all evidence.'},
 {'role':'user','content':'Synthetic engineering task.'},
 {'role':'assistant','content':'Synthetic prior response.'},
 {'role':'system','content':'Synthetic compacted memory Ω; unresolved finding remains.'},
 {'role':'user','content':'Continue the same task.'}]
body={'model':model,'messages':messages,'reasoning_effort':'medium','max_tokens':16}
fixed=gw.sanitize_request(body,policy=pol)
with httpx.Client(base_url='http://127.0.0.1:11457',timeout=20) as c:
 before=c.post('/apply-template',json=body)
 after=c.post('/apply-template',json=fixed)
assert before.status_code in (400,500) and 'System message must be at the beginning' in before.text,(before.status_code,before.text[:100])
after.raise_for_status();prompt=after.json()['prompt']
assert messages[0]['content'] in prompt and messages[3]['content'] in prompt
assert [m for m in fixed['messages'] if m['role']!='system']==[m for m in messages if m['role']!='system']
assert body['messages']==messages
result={'at':utc_now(),'source_revision':rev,'profile_version':p['version'],'gateway_source_sha256':sha256_file(Q/'factory/python/forge_factory/llm_gateway.py'),
 'native_endpoint':'/apply-template','generation_endpoints_called':0,'fixture':'synthetic text-only late-system compaction shape',
 'initial_probe_guard':{'expected_http':400,'observed_http':500,'correction':'accept actual native template rejection; no candidate/source change'},'baseline_http':before.status_code,'baseline_error':'System message must be at the beginning',
 'candidate_http':after.status_code,'all_synthetic_system_text_retained':True,'non_system_order_and_content_unchanged':True,
 'baseline_body_sha256':hashlib.sha256(canonical_json(body)).hexdigest(),'candidate_body_sha256':hashlib.sha256(canonical_json(fixed)).hexdigest(),
 'native_template_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'result':'PASS','live_run_restarted':False,
 'source_clean_after':not bool(subprocess.check_output(['git','-C',str(Q),'status','--porcelain','--untracked-files=no'],text=True).strip())}
(N/'native-system-order-qualification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

