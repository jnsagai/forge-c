
from pathlib import Path
import sys,os,json
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');Q=N/'source';os.environ['FORGE_REPO_ROOT']=str(Q);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.lrtx import profile,stack
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.afo.durable import immutable_json
d=json.loads((N/'launch.json').read_text())
with FabroClient(base_url='http://127.0.0.1:32401',token=load_token(str(N/'fabro/storage'))) as c:
 assert run_status(c.get_run(d['native_id'])) in ('FAILED','CANCELLED','CANCELED','SUCCEEDED')
prof=profile.load('local-rtx-v2-omniverse2-q38-qm-native-artifacts')
os.environ.update(stack.envmap({'profile':prof,'root':N,'ports':prof['deployment']['ports']}))
from forge_factory.release.finalize import finalize,verify_archive
r=finalize(Path(d['workspace']),d['work_order'],d['native_id'])
receipt={'classification':'EXTERNALLY_SUPERSEDED_STALLED_NATIVE_RCCC_NOT_ACCEPTED_PRODUCT',
 'package':r,'integrity':verify_archive(Path(r['archive'])),'original_source':d['source_revision']}
immutable_json(N/'delivery-first-handoff-v1/package.json',receipt)
print(json.dumps({'package_status':r['package_status'],'gaps':r['gap_count'],'archive_sha256':r['archive_sha256'],'integrity':receipt['integrity']['integrity']}))

