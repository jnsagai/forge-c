"""External native verification of a frozen real Qwen candidate, without inference."""
from pathlib import Path
import hashlib,json,os,shutil,sys,time
R=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1')
Q=R/'source-verification-d846ec82'
REV='d846ec82086e299f2acd88a24e1b2b6e234dc27f'
ROOT=R/'independent-first-candidate-v1'
for key in list(os.environ):
    if key.startswith('FORGE_'):
        os.environ.pop(key)
os.environ.update(FORGE_REPO_ROOT=str(Q),FORGE_DATA_ROOT=str(R),FORGE_STATE_DIR=str(ROOT/'state'),
                  FORGE_ARCHIVE_DIR=str(ROOT/'archives'),PYTHONDONTWRITEBYTECODE='1')
toolpaths=[R/'toolchains/LLVM-19.1.7-Linux-X64/bin',R/'toolchains/formal/bin',
           R/'toolchains/renode/renode_1.17.0-portable']
os.environ['PATH']=':'.join(map(str,toolpaths))+':/usr/local/bin:/usr/bin:/bin'
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo.durable import immutable_json,immutable_bytes
from forge_factory.common import utc_now
from forge_factory.mcp.sdk import ToolContext
from forge_factory.mcp.servers import build,sim
from forge_factory import simulation_performance as F
origin=json.loads((R/'launch.json').read_text())
original=Path(origin['workspace'])
header='software/ll/stm32n6xx_ll_crc.h'
source=original/'.forge-run/delivery-first/attempt-0/candidate'/header
assert hashlib.sha256(source.read_bytes()).hexdigest()=='511956a9345ca465b265a60214f16fb43c5d2395b18dfcf7fd4766a980cc29f5'
manifest=json.loads((original/'.forge-run/manifest.json').read_text())
oracle=(R/'native-first-candidate-target-oracle.c').read_bytes()
assert b'forge_measure_LL_CRC_Write_IDR' in oracle and b'forge_measure_LL_CRC_Read_IDR' in oracle
ROOT.mkdir(mode=0o700,exist_ok=True)
if (ROOT/'summary.json').exists():
    print((ROOT/'summary.json').read_text())
    raise SystemExit(0)
assert not (ROOT/'intent.json').exists(),'PRESERVE_PARTIAL_QUALIFICATION_AND_RECONCILE'
immutable_json(ROOT/'intent.json',{'at':utc_now(),'kind':'EXTERNAL_POST_HOC_NATIVE_VERIFICATION',
    'original_native_id':origin['native_id'],'original_source_revision':origin['source_revision'],
    'verifier_revision':REV,'new_model_calls':0,'active_workspace_modified':False,
    'oracle_basis':'DECLARED_REVIEWED_IDR_CONTRACT; TARGET_FIXTURE_AUTHORED_EXTERNALLY_AFTER_CANDIDATE',
    'target_oracle_sha256':hashlib.sha256(oracle).hexdigest()})

def run(name,read_mask=False,tight_budget=False):
    ws=ROOT/name/'workspace'
    assert not ws.exists(),'QUALIFICATION_ALREADY_STARTED:'+name
    (ws/'.forge-run').mkdir(parents=True)
    doc=json.loads(json.dumps(manifest))
    doc['external_qualification']={'case':name,'verifier_revision':REV,'new_model_execution':False,
        'origin_native_id':origin['native_id'],'candidate_kind':'CONTROLLED_MUTANT' if read_mask else 'FROZEN_REAL_QWEN_CANDIDATE'}
    if tight_budget:
        doc['simulation_performance']['instructions_per_call']=1
    for item in doc['inputs']:
        p=original/item['path'];raw=p.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==item['sha256'],item['path']
        dest=ws/item['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);dest.chmod(0o444)
    text=source.read_text()
    if read_mask:
        assert text.count('return CRCx->IDR;')==1
        text=text.replace('return CRCx->IDR;','return CRCx->IDR & 0xFFU;')
    dest=ws/header;dest.parent.mkdir(parents=True);dest.write_text(text);dest.chmod(0o444)
    test=ws/F.TEST;test.parent.mkdir(parents=True);test.write_bytes(oracle);test.chmod(0o444)
    (ws/'.forge-run/manifest.json').write_text(json.dumps(doc,indent=2)+'\n')
    ctx=ToolContext('forge-build-mcp','compile','external-verifier','SWE.3',ws,origin['native_id'])
    t0=time.monotonic()
    compile_result=build.compile_(ctx,build.CompileIn())
    outputs={'compile':compile_result}
    if compile_result['status']=='PASS':
        outputs['size']=build.measure_elf(ctx,build.ProfileIn())
        outputs['stack']=build.stack_usage(ctx,build.ProfileIn())
        sctx=ToolContext('forge-sim-mcp','run_renode','external-verifier','SWE.5',ws,origin['native_id'])
        outputs['simulation']=sim.run_renode(sctx,sim.SimIn())
        try:
            outputs['recomputed_performance']=F.verify_result(ws,outputs['simulation'])
        except (ValueError,OSError,KeyError,TypeError) as exc:
            outputs['recomputed_performance']={'status':'NOT_VERIFIED','reason':str(exc)}
    size=(outputs.get('size') or {}).get('metrics',{})
    stack=(outputs.get('stack') or {}).get('metrics',{})
    budget=doc['budgets']
    resources={'scope':'OBJECT_LEVEL_WITH_DECLARED_BUILD_PROBE_AND_MEASUREMENT_WRAPPERS; NOT_LINKED_FIRMWARE',
        'flash_bytes':size.get('flash_bytes'),'ram_bytes':size.get('ram_bytes'),
        'max_frame_bytes':stack.get('max_frame_bytes'),'call_graph_stack':'NOT_COMPUTED',
        'budget':budget}
    resources['within_object_and_frame_limits']=all([
        outputs.get('size',{}).get('status')=='PASS',outputs.get('stack',{}).get('status')=='PASS',
        size.get('flash_bytes',float('inf'))<=budget['flash_bytes'],
        size.get('ram_bytes',float('inf'))<=budget['static_ram_bytes'],
        stack.get('max_frame_bytes',float('inf'))<=budget['stack_bytes']])
    result={'at':utc_now(),'case':name,'verifier_revision':REV,'original_native_id':origin['native_id'],
        'candidate_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
        'model_authored_original':not read_mask,'controlled_mutant':read_mask,'controlled_cost_budget':tight_budget,
        'new_model_calls':0,'active_workspace_modified':False,'wall_ms':round((time.monotonic()-t0)*1000,1),
        'outputs':outputs,'resources':resources,'process_phase_acceptance':'NOT_ASSESSED',
        'release_eligibility':'BLOCKED','physical_hardware':'NOT_RUN'}
    immutable_json(ROOT/name/'result.json',result)
    print(json.dumps({'case':name,'compile':compile_result['status'],
        'simulation':outputs.get('simulation',{}).get('status'),
        'cost':outputs.get('recomputed_performance',{}).get('status'),'resources':resources}),flush=True)
    return result

positive=run('positive')
masked=run('read-mask-mutant',read_mask=True)
tight=run('one-instruction-budget',tight_budget=True)
checks={'positive_compilation':positive['outputs']['compile']['status']=='PASS',
    'positive_simulation':positive['outputs'].get('simulation',{}).get('status')=='PASS',
    'positive_cost':positive['outputs'].get('recomputed_performance',{}).get('status')=='PASS',
    'positive_resources':positive['resources']['within_object_and_frame_limits'],
    'wrong_read_rejected':masked['outputs'].get('simulation',{}).get('status')=='FAIL',
    'cost_pass_does_not_waive_wrong_read':masked['outputs'].get('recomputed_performance',{}).get('status')=='PASS',
    'tight_cost_rejected':tight['outputs'].get('recomputed_performance',{}).get('status')=='FAIL'}
summary={'at':utc_now(),'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,
    'scope':'FROZEN_FIRST_CANDIDATE_EXTERNAL_NATIVE_SIMULATION; NOT_AUTONOMOUS_PIPELINE_COMPLETION',
    'original_native_id':origin['native_id'],'verifier_revision':REV,'new_model_calls':0,
    'active_workspace_modified':False,'artifacts_preserved':True}
immutable_json(ROOT/'summary.json',summary)
print(json.dumps(summary))

