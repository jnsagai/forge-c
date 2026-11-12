"""External audit of fresh06 from immutable observations and transferred ZIP.

No candidate execution/model call. This does not grant release or factory control.
"""
from pathlib import Path
from datetime import datetime, UTC
import hashlib,json,zipfile,sys

A=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/incremental-m1-followup-20261029')
W=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/recovery-after-overnight-20261028')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
op=A/'native07-terminal-observation.json';sp=A/'native07-terminal-source-audit.json'
assert sha(op)=='e1c00a64bbc896cf93d5dfab462f5c73b958b916038848c92bc5360ec3b06709'
assert sha(sp)=='3558ebf279180737574f32b4b116d0e51ad30ab3e6a843348172f398cee83c61'
o=json.loads(op.read_text());s=json.loads(sp.read_text());a=o['attempts'][0]
cohort=A/'repeatability-prepared-20261031-v4b';c=json.loads((cohort/'cohort.json').read_text())
frozen=json.loads((cohort/'frozen-contract.json').read_text())
assert sha(cohort/'cohort.json')==o['cohort_sha256']=='a14bfe74a0365a47360a630e09cdaec0338b10385ecb8be7a1b4d3389d18e759'
assert o['order']['order_id']=='afo-f83452175591716f' and len(o['attempts'])==1
assert a['native_id']=='01M6855WHNYHGCV6PFB5HPHAVH' and a['native_status']=='SUCCEEDED'
assert o['producer_source_revision']==c['source_revision']=='0e342eef3c68786d29e5b9843606892c4ab68b60'
assert a['initial_preflight']['inputs']==frozen['inputs'] and a['initial_preflight']['contract']==frozen['delivery_first']
assert a['initial_preflight']['candidate_initially_absent'] and not a['initial_preflight']['candidate_code_substituted']
assert s['status']=='VERIFIED_SOURCE_PROVENANCE' and s['candidate_unchanged_during_audit'] and s['runtime_source_unchanged']
assert s['native_evidence']['native_id']==a['native_id']
assert s['auditor_factory_revision']['commit']==c['auditor_revision']=='30371da548bad2790a9f3c21dafc8964047ce06d'
assert s['auditor_module_sha256']=='8ceca6bdbe5d181b0e65f48b4cda3835540dc3ca587011ebc8e6e3879a304cd5'
assert s['candidate_hashes']==s['candidate_hashes_after']==a['candidate_hashes']==a['archived_candidate_hashes']
assert a['candidate_hashes']=={'software/ll/stm32n6xx_ll_crc.h':'70d5558762d299a8ce664dc0aa589b42c77425e969ec365e5430badbbaced689'}
assert not s['candidate_executed_by_auditor'] and not s['workspace_written_by_auditor'] and s['model_generation_calls_by_auditor']==0
r=a['packaged_report'];final=a['archived_final_receipt']
assert r['functional_verification']==final['status']=='PASS' and final['candidate_unchanged_during_checks']
assert final['candidate_hashes']==a['candidate_hashes'] and all(x['status']=='PASS' and x['exit_code']==0 for x in final['calls'])
target=final['independent_target'];assert target['status']=='PASS' and target['resources_within_declared_limits']
assert all(target['outputs'][k]['status']=='PASS' for k in ('compile','simulation','cost','size','stack'))
assert target['outputs']['simulation']['metrics']['passed']==351
assert r['factory_revision']['commit']==c['source_revision'] and not r['factory_revision']['dirty']
prof=r['model_profile']['local_profile'];assert prof['config_sha256']==c['profile_sha256']
assert prof['models'][0]['digest']==c['model_digest'] and prof['models'][0]['status']=='MATCH'
assert prof['enforcement']['network']['status']=='DENIED_VERIFIED'
assert all(all(v.values()) for v in r['native_evidence']['phase_attempts'].values())
assert len(a['phase_files'])==6 and all(a['phase_files'].values()) and a['archived_phase_hashes_match']
assert a['external_steering_events']==0
assert r['release_eligibility']=='BLOCKED' and r['process_qualification']=='GAPS' and a['package']['package_status']=='BLOCKED'
assert a['archive_integrity']['integrity']=='PASS' and not r['integrity_issues']
assert a['archived_final_receipt_present'] and a['archived_final_equals_live_bytes'] and a['archived_report_has_same_final_receipt']
assert all(e['execution_liveness']=='QUIESCENT' and e['resource_lease']=='RELEASED' and e['quiescence_evidence_ref'] for e in a['execution'])
copy=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/inspection/feature014/2026-10-30-qwen/overnight-afo-delivery/native-01M6855WHNYHGCV6PFB5HPHAVH')
archive=copy/'review.zip';transfer=copy/'transfer-verification.json'
assert sha(archive)==json.loads(transfer.read_text())['archive_sha256']==a['package']['archive_sha256']
sys.path.insert(0,str(W/'factory/python'))
from forge_factory.release.finalize import verify_archive
assert verify_archive(archive)['integrity']=='PASS'
with zipfile.ZipFile(archive) as z:
 report=json.loads(z.read('evidence/verification/delivery-first/report.json'))
 assert report['candidate_hashes']==a['candidate_hashes']
 assert any(x==final for x in report['attempts'])
 for item in frozen['inputs']:
  member='evidence/verification/delivery-first/attempts/attempt-final/independent-target/workspace/'+item['path']
  assert hashlib.sha256(z.read(member)).hexdigest()==item['sha256']
 for rows in a['phase_files'].values():
  for item in rows:assert hashlib.sha256(z.read('evidence/'+item['path'])).hexdigest()==item['sha256']
 assert '630 checks, 0 failures' in z.read('evidence/verification/delivery-first/attempts/attempt-final/independent_behavior.stdout').decode()
assert 'missing_or_empty_file:workproducts/SWE.6/software_verification_report.md' in a['package']['gaps']
assert all(any(x['node']==name and x['event']=='stage.failed' and '429' in str(x['failure']) for x in a['stage_outcomes']) for name in ('swe6_test_author','swe6_author'))
negative=A/'native05-negative-control-index.json';neg=json.loads(negative.read_text())
assert sha(W/neg['receipt']['path'])==neg['receipt']['sha256']
assert all(neg['groups'].values()) and neg['producer_revision']==c['source_revision']
facts_ref={'path':str(op),'sha256':sha(op)};source_ref={'path':str(sp),'sha256':sha(sp)}
conditions={str(i):{'status':'PASS','evidence_refs':[facts_ref,source_ref]} for i in range(1,10)}
conditions['4']['basis']='All six attempt outcomes recorded; SWE.6 author HTTP429 failures, trace-only available artifacts and missing report remain explicit gaps, not complete SWE.6 delivery.'
conditions['5']['basis']='External session observation: zero post-launch job interventions/steering. Administrative retry of07 occurred before07launch; retry08 after07terminal is separately disclosed.'
conditions['8']['evidence_refs'].append({'path':str(negative),'sha256':sha(negative)})
out={'schema':'forge-c/delivery-first-fresh-trial-audit/1','at':datetime.now(UTC).isoformat(),
 'producer':'CODEX_EXTERNAL_OBSERVER_NOT_OWNER_RELEASE_AUTHORITY','cohort_sha256':o['cohort_sha256'],
 'trial_request_id':'DF-AFO-CRC-IDR-20261030-07','order_id':o['order']['order_id'],'native_id':a['native_id'],
 'source_revision':c['source_revision'],'auditor_revision':c['auditor_revision'],
 'result':'FUNCTIONAL_MILESTONE_PASS','scope':'ONLY_PREREGISTERED_CRC_IDR_TWO_FUNCTIONS',
 'conditions':conditions,'archive':{'remote_path':a['package']['archive'],'sha256':sha(archive)},
 'candidate_hashes':a['candidate_hashes'],'process_qualification':'GAPS','release_eligibility':'BLOCKED',
 'gap_count':a['package']['gap_count'],'gates':{k:v['gate'] for k,v in r['phases'].items()},
 'phase_file_counts':{k:len(v) for k,v in a['phase_files'].items()},
 'metrics':{'native_usage':a['usage']['totals'],'request_ledger_entries':sum(v['n'] for v in a['request_states']),
 'reasoning_breakdown':'UNKNOWN; provider0 is not a measurement of hidden reasoning',
 'post_launch_job_interventions':0,'corrections':final['correction_count'],
 'author_role_output_tokens':r['metrics']['reported_author_output_tokens']},
 'cohort_status':'TWO_OF_THREE_QUALIFIED; ONE_OTHER_NOT_YET_QUALIFIED',
 'automatic_factory_handoff':'NOT_QUALIFIED; inherited capacity backoff required external administrative retries before07 and08',
 'observer_limits':'Session-scoped intervention observation, not a general tamper-proof detector',
 'remaining_claims_not_established':['full LL/HAL','strict release','production','assessed ASPICE','generic drivers','learning benefit','24/7 availability','three-run repeatability'],
 'phase_delivery_limits':['SWE.5 inspection record missing after stage timeout','SWE.6 authors attempted but HTTP429 blocked, no executed Robot verification/report; trace files only','All35strict gaps retained; no full pipeline artifact-completion claim'],
 'model_calls_by_auditor':0,'candidate_execution_by_auditor':False,'deadline_utc':c['deadline_utc']}
raw=json.dumps(out,sort_keys=True,separators=(',',':')).encode()
path=A/'cohort-audits'/('native07-'+hashlib.sha256(raw).hexdigest()+'.json');path.parent.mkdir(exist_ok=True)
if path.exists():assert path.read_bytes()==raw
else:
 with path.open('xb') as stream:stream.write(raw)
print(json.dumps({'path':str(path),'sha256':sha(path),'result':out['result'],'cohort_status':out['cohort_status'],'release':out['release_eligibility'],'gap_count':out['gap_count']}))
