from pathlib import Path
import sys,json,hashlib,ast
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');sys.path.insert(0,str(N/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token
from forge_factory.common import utc_now
with FabroClient(base_url='http://127.0.0.1:32401',token=load_token(str(N/'fabro/storage')),timeout=20) as c:
 es=list(c.iter_events('01M671YCDV672HSSY5QDGH4SNT'))
 for e in es:
  if e['event']!='agent.tool.started':continue
  t=((e.get('properties') or {}).get('event') or {}).get('ToolCallStarted',{})
  if t.get('tool_call_id')!='YGxb2KAqwHzk7Q4k9t7uUWTWsYXuGCNR':continue
  args=t['arguments'];args=json.loads(args) if isinstance(args,str) else args
  code=args['content'];assert args['file_path']=='/tmp/swe1_patch.py'
  tree=ast.parse(code)
  root=N/'private-proposals';root.mkdir(mode=0o700,exist_ok=True)
  target=root/'swe1_patch.py';target.write_text(code);target.chmod(0o600)
  imports=sorted({n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)} |
                 {a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names})
  string_paths=sorted({n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)
                      and (n.value.startswith('/') or n.value.endswith(('.md','.csv','.json','.reqif'))) and len(n.value)<500})
  writes=[{'method':n.func.attr,'line':n.lineno} for n in ast.walk(tree) if isinstance(n,ast.Call)
          and isinstance(n.func,ast.Attribute) and n.func.attr in ('write_text','write_bytes','unlink','rename','replace','mkdir')]
  result={'at':utc_now(),'native_call_id':t['tool_call_id'],'model_authored_artifact':True,'script_sha256':hashlib.sha256(code.encode()).hexdigest(),
          'script_bytes':len(code.encode()),'syntax':'PASS','imports':imports,'string_paths':string_paths,
          'write_call_sites':writes,'executed':False,'active_workspace_modified_by_capture':False,'new_model_calls':0,
          'private_script':str(target)}
  (N/'native-patch-helper-capture.json').write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps(result));break
 else:raise RuntimeError('ORIGINAL_MODEL_HELPER_NOT_FOUND')

