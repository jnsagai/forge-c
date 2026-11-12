"""External integrated verification, not a new Qwen generation or autonomous milestone."""
from pathlib import Path
import hashlib,json,os,sys,subprocess
R=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1')
Q=R/'source-verification-58ef89b7';REV='58ef89b7c798b7fdeb05aef08813f1b26a24a6a9'
ROOT=R/'independent-integrated-verification-58ef89b7'
for k in list(os.environ):
    if k.startswith('FORGE_'):os.environ.pop(k)
os.environ.update(FORGE_REPO_ROOT=str(Q),FORGE_DATA_ROOT=str(R),FORGE_STATE_DIR=str(ROOT/'state'),
                  FORGE_ARCHIVE_DIR=str(ROOT/'archives'),FORGE_FABRO_LIVE='0',PYTHONDONTWRITEBYTECODE='1')
os.environ['PATH']=':'.join(str(R/p) for p in ('toolchains/LLVM-19.1.7-Linux-X64/bin','toolchains/formal/bin','toolchains/renode/renode_1.17.0-portable'))+':/usr/local/bin:/usr/bin:/bin'
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory import workorder as W,delivery_first as D,development_execution as E
from forge_factory.release import finalize as F
from forge_factory.afo.durable import immutable_json
from forge_factory.common import sha256_file,utc_now
origin=json.loads((R/'launch.json').read_text());old=Path(origin['workspace'])
rel='software/ll/stm32n6xx_ll_crc.h'
source=old/'.forge-run/delivery-first/attempt-0/candidate'/rel
sha='511956a9345ca465b265a60214f16fb43c5d2395b18dfcf7fd4766a980cc29f5'
assert sha256_file(source)==sha
assert subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()==REV
assert not subprocess.check_output(['git','-C',str(Q),'status','--porcelain','--untracked-files=no'],text=True).strip()
ROOT.mkdir(mode=0o700,exist_ok=True)
assert not (ROOT/'intent.json').exists(),'PRESERVE_EXISTING_QUALIFICATION'
immutable_json(ROOT/'intent.json',{'at':utc_now(),'kind':'EXTERNAL_POST_HOC_INTEGRATED_VERIFICATION',
 'origin_native_id':origin['native_id'],'verifier_revision':REV,'new_model_calls':0,
 'active_workspace_modified':False,'simulation_oracle_preregistered_for_future_jobs_only':True})
ws,man=W.prepare(Q/'examples/0014g-st-crc-idr-qwen-delivery','WO-DF-EXTERNAL-VERIFY-58EF89B7',purpose='QM',execution_policy=E.DEMO)
D.preflight(ws);p=ws/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(source.read_bytes())
positive=D.verify(ws,0);report=D.report(ws)
package=F.finalize(ws,'EXTERNAL-VERIFY-58EF89B7-POSITIVE')
positive_integrity=F.verify_archive(Path(package['archive']))
assert positive['status']=='PASS' and report['functional_verification']=='PASS',(positive,report)
assert package['package_status']=='BLOCKED' and positive_integrity['integrity']=='PASS',package
assert report['milestone']=='NOT_PROVEN' and report['authorship']=='UNVERIFIED'
text=p.read_text();assert text.count('return CRCx->IDR;')==1
p.write_text(text.replace('return CRCx->IDR;','return CRCx->IDR & 0xFFU;'))
negative=D.verify(ws,'final');negative_report=D.report(ws)
negative_package=F.finalize(ws,'EXTERNAL-VERIFY-58EF89B7-FINAL-MUTANT')
negative_integrity=F.verify_archive(Path(negative_package['archive']))
assert negative['status']=='FAIL' and negative_report['functional_verification']=='FAIL'
assert negative['correction_count']==0 and negative_integrity['integrity']=='PASS'
assert sha256_file(old/rel)==sha,'ACTIVE_CANDIDATE_CHANGED_EXTERNALLY'
immutable_json(ROOT/'summary.json',{'at':utc_now(),'status':'PASS','verifier_revision':REV,
 'positive':{'status':positive['status'],'functional_verification':report['functional_verification'],
  'candidate_sha256':sha,'package_status':package['package_status'],'archive_sha256':sha256_file(Path(package['archive'])),
  'archive_integrity':positive_integrity['integrity'],'target_assertions':positive['independent_target']['outputs']['simulation']['metrics']['passed']},
 'final_mutant':{'status':negative['status'],'functional_verification':negative_report['functional_verification'],
  'correction_count':negative['correction_count'],'archive_integrity':negative_integrity['integrity']},
 'milestone':'NOT_PROVEN','new_model_calls':0,'active_workspace_modified':False,'origin_native_id':origin['native_id'],
 'workspace':str(ws),'kind':'EXTERNAL_POST_HOC_INTEGRATED_VERIFICATION'})
print((ROOT/'summary.json').read_text())

