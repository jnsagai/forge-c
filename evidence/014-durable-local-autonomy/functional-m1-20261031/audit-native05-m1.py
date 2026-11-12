"""Derive a scoped external DF-M1 audit from preserved terminal evidence.

No model calls, candidate execution, job writes, owner signature or release grant.
"""
from pathlib import Path
from datetime import datetime, UTC
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET

A=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/incremental-m1-followup-20261029')
W=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/recovery-after-overnight-20261028')
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
facts_ref={"path":"/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/control/qualification-observations/native05/terminal-facts-c28b073a2ecf93a71e4778bfeaddcb8ecb82fb79e912b83acebf671299047ec4.json","sha256":"c28b073a2ecf93a71e4778bfeaddcb8ecb82fb79e912b83acebf671299047ec4"}
source_ref={"path":"/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/control/qualification-observations/native05/source-provenance-terminal-6f9453c9ba5e481350e9798b2b0deb44df08b5fcf57defe43886b516698a56e5.json","sha256":"6f9453c9ba5e481350e9798b2b0deb44df08b5fcf57defe43886b516698a56e5"}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
fp=A/'native05-terminal-facts.json';sp=A/'native05-terminal-source-audit.json'
assert sha(fp)==facts_ref['sha256'] and sha(sp)==source_ref['sha256']
f=json.loads(fp.read_text());s=json.loads(sp.read_text())
cohort=A/'repeatability-prepared-20261031-v4b'
frozen=json.loads((cohort/'frozen-contract.json').read_text())
assert f['native_status']=='SUCCEEDED'
assert f['source_revision']==frozen['producer_source_revision']=='0e342eef3c68786d29e5b9843606892c4ab68b60'
assert f['archived_preflight']['factory_revision']['commit']==f['source_revision']
assert not f['archived_preflight']['factory_revision']['dirty']
assert f['archived_preflight']['contract']==frozen['delivery_first']
assert f['archived_preflight']['inputs']==frozen['inputs'] and len(frozen['inputs'])==14
assert f['archived_report_declared_scope']==frozen['operation_scope']
assert f['archived_preflight']['candidate_initially_absent'] and not f['archived_preflight']['candidate_code_substituted']
candidate='9aa11db10b4547cc4f440f91e3d4e513f006906b83a1c1a77e26fbf9ebedf76e'
assert f['candidate_sha256']==f['archived_candidate_sha256']==candidate
assert s['status']=='VERIFIED_SOURCE_PROVENANCE'
assert s['native_evidence']['authorship']=='CONFIRMED_NATIVE_WRITE_EDIT_CHAIN'
assert s['candidate_hashes']==s['candidate_hashes_after']=={'software/ll/stm32n6xx_ll_crc.h':candidate}
assert s['candidate_unchanged_during_audit'] and s['runtime_source_unchanged']
assert s['auditor_factory_revision']['commit']=='30371da548bad2790a9f3c21dafc8964047ce06d'
assert s['producer_factory_revision']['commit']==f['source_revision']
assert not s['workspace_written_by_auditor'] and not s['candidate_executed_by_auditor']
assert s['model_generation_calls_by_auditor']==0
assert f['packaged_report']['model_profile']['local_profile']['models'][0]['status']=='MATCH'
assert f['packaged_report']['model_profile']['local_profile']['models'][0]['digest']=='8f5fb6b71ea00052cbe8545738c55ce61112c4e571cb60ca4dad00b131766039'
assert f['packaged_report']['model_profile']['local_profile']['enforcement']['network']['status']=='DENIED_VERIFIED'
report=f['packaged_report'];final=f['archived_final_receipt']
assert final['status']==report['functional_verification']=='PASS'
assert all(c['status']=='PASS' and c['exit_code']==0 for c in final['calls'])
assert final['candidate_unchanged_during_checks']
target=final['independent_target']
assert target['status']=='PASS' and target['resources_within_declared_limits']
assert all(target['outputs'][key]['status']=='PASS' for key in ['compile','simulation','cost','size','stack'])
assert target['outputs']['simulation']['metrics']['passed']==351
assert all(all(v.values()) for v in f['packaged_native_evidence']['phase_attempts'].values())
assert len(f['phase_files'])==6 and all(f['phase_files'].values())
assert f['external_steering_event_count']==0
assert report['execution']=='COMPLETED' and report['artifact_delivery']=='COMPLETE'
assert report['process_qualification']=='GAPS' and report['release_eligibility']=='BLOCKED'
assert f['archive_integrity']['integrity']=='PASS' and not report['integrity_issues']
assert all(f[k] for k in ['archived_final_receipt_present','archived_final_receipt_equals_live_bytes',
 'archived_report_has_same_final_receipt','archived_candidate_equals_live','archived_final_verification_node_observed'])
copy=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/inspection/feature014/2026-10-30-qwen/overnight-afo-delivery/native-01M67R1HNE9TKPWCYJ2SVKEPJS')
transfer=json.loads((copy/'transfer-verification.json').read_text())
assert sha(copy/'review.zip')==transfer['archive_sha256']==f['package']['archive_sha256']
assert transfer['integrity']=='PASS'
with zipfile.ZipFile(copy/'review.zip') as z:
 for rows in f['phase_files'].values():
  for r in rows:assert hashlib.sha256(z.read('evidence/'+r['path'])).hexdigest()==r['sha256']
 assert '630 checks, 0 failures' in z.read('evidence/verification/delivery-first/attempts/attempt-final/independent_behavior.stdout').decode()
 for item in frozen['inputs']:
  member='evidence/verification/delivery-first/attempts/attempt-final/independent-target/workspace/'+item['path']
  assert hashlib.sha256(z.read(member)).hexdigest()==item['sha256']
idx=A/'native05-negative-control-index.json'
negative=json.loads(idx.read_text())
xml=W/negative['receipt']['path']
assert sha(xml)==negative['receipt']['sha256']
suite=ET.parse(xml).getroot()
actual={r.attrib['name']:r for r in suite.iter('testcase')}
for rows in negative['groups'].values():
 assert rows
 for r in rows:
  row=actual[r['name']]
  assert all(row.find(k) is None for k in ['failure','error','skipped'])
remote_negative=E/'control/qualification-observations/native05/negative-controls'
negative_refs=[{'path':str(remote_negative/idx.name),'sha256':sha(idx)},
 {'path':str(remote_negative/xml.name),'sha256':sha(xml)}]
frozen_ref={'path':str(E/'control/repeatability-20261031-v4b/repeatability-prepared-20261031-v4b/frozen-contract.json'),'sha256':sha(cohort/'frozen-contract.json')}
def ref(pointer,kind='facts'):
 base=facts_ref if kind=='facts' else source_ref
 return {**base,'json_pointer':pointer}
conditions={
 '1':{'status':'PASS','basis':'New authorized AFO order; exact two-function scope,14 frozen inputs and independent oracle match archived initial preflight.',
      'evidence_refs':[ref('/archived_preflight'),frozen_ref,
       {'repository_path':'evidence/014-durable-local-autonomy/package-order-20261031/primary-scope-v4.json','primary_scope_sha256':'83c919dcc947cf003db192a2936dd093c19021ce0fa80c3702f8cfe68a2f1a34'}]},
 '2':{'status':'PASS','basis':'Actual local model digest/network binding; candidate initially absent; accepted native source write plus six edits reconstruct final archived bytes, no supplied vendor implementation.',
      'evidence_refs':[ref('/packaged_report/model_profile'),ref('/native_evidence','source'),ref('/archived_candidate_sha256')]},
 '3':{'status':'PASS','basis':'Declared host/target compilation,630 host assertions,351 simulated assertions, independent simulation cost and object/frame budgets pass for final candidate.',
      'evidence_refs':[ref('/archived_final_receipt'),frozen_ref]},
 '4':{'status':'PASS','basis':'All six author/inspector attempts recorded; available phase files3/8/9/3/3/3 are present with matching archive hashes; failed gates remain explicit.',
      'evidence_refs':[ref('/stage_outcomes'),ref('/phase_files'),ref('/packaged_phase_evidence')]},
 '5':{'status':'PASS','basis':'External session observation: no post-launch job steering, implementation/test fixes, input/model/source deployment or active-job administrative repair by operator/assistant was needed.',
      'evidence_refs':[ref('/external_steering_event_count'),ref('/source_revision'),ref('/workspace_written_by_auditor','source')],
      'observer_limit':'Session-scoped external observation, not a general tamper-proof human-activity detector. Read-only audits/local unactivated code work are disclosed; all engineering handoff fixes preceded launch.'},
 '6':{'status':'PASS','basis':'Sealed archive SHA/integrity passes; archived final receipt equals live bytes and report entry; candidate/source/model/profile/scope and full gaps preserved; private local transfer matches SHA.',
      'evidence_refs':[ref('/archive_integrity'),ref('/archived_final_receipt_sha256'),ref('/archived_report_has_same_final_receipt'),{'path':str(copy/'transfer-verification.json'),'sha256':sha(copy/'transfer-verification.json')}]},
 '7':{'status':'PASS','basis':'Process GAPS and strict release BLOCKED/25gaps remain; QM development demonstration only. Native success does not upgrade release.',
      'evidence_refs':[ref('/package'),ref('/packaged_report')]},
 '8':{'status':'PASS','basis':'Indexed actual synthetic framework negative controls reject compilation error, behavioral mutants, absent/changed evidence and tampered provenance. Functional verifier source identity matches producer0e and auditor303.',
      'evidence_refs':negative_refs+[{'repository_path':'evidence/014-durable-local-autonomy/repeatability-preregistration-20261031/prepared-cohort/functional-verifier-identity.json','sha256':sha(cohort/'functional-verifier-identity.json')}],
      'limit':'Framework fixture controls, not live Qwen capability tests; provenance controls reject source/milestone proof rather than pretending compilation itself fails.'},
 '9':{'status':'PASS','basis':'Exact identities,source/model/profile hashes,commands,timestamps,297request-ledger entries and provider-reported time/tokens retained. Reasoning breakdown remains UNKNOWN.',
      'evidence_refs':[ref('/actual_terminal_metrics'),ref('/stage_outcomes'),ref('/packaged_report/metrics'),source_ref]}
}
audit={'schema':'forge-c/delivery-first-external-m1-audit/1','at':datetime.now(UTC).isoformat(),
 'producer':'CODEX_EXTERNAL_OBSERVER_NOT_OWNER_RELEASE_AUTHORITY',
 'native_id':f['native_id'],'order_id':f['order']['order_id'],'work_order':'WO-AFO-ee4282b25001a15d-a1',
 'source_revision':f['source_revision'],'auditor_revision':s['auditor_factory_revision']['commit'],
 'candidate_sha256':candidate,'profile_sha256':'823942772335b7ef500f9f11926732405ac12dbff0dcc7f0ab39e345db3358e7',
 'milestone':'FUNCTIONAL_MILESTONE_PASS','scope':'ONLY_PREREGISTERED_TWO_FUNCTION_CRC_IDR_INCREMENT; NOT_FULL_LL_OR_HAL',
 'conditions':conditions,
 'archive':{'path':f['package']['archive'],'sha256':f['package']['archive_sha256']},
 'remote_artifact_refs':[facts_ref,source_ref,*negative_refs,frozen_ref],
 'metrics':f['actual_terminal_metrics'],
 'process_qualification':'GAPS','release_eligibility':'BLOCKED','gap_count':25,
 'internal_report_unchanged':{'authorship':'UNVERIFIED_EDIT_CHAIN','milestone':'NOT_PROVEN','human_interventions':'UNKNOWN_REQUIRES_EXTERNAL_OBSERVER'},
 'external_observation':{'post_launch_job_interventions':0,'source_provenance':'VERIFIED_SOURCE_PROVENANCE',
  'prelaunch_engineering_fixes':'Disclosed in package-order-20261031; not autonomous healing',
  'post_terminal_observer_recording_failure':'First terminal source-audit record wrapper lacked host import path; CLI audit itself completed. Fixed observer path and repeated read-only audit; no candidate/model/job change.'},
 'commands':{'terminal_bindings_collector':'E/venv/bin/python record-native05-terminal-bindings.py on remote host API32404',
  'source_audit':'E/venv/bin/python -m forge_factory.delivery_first --workspace WS --step source-provenance; inside actual holder namespace; PYTHONPATH=E/control/source-auditor-30371da5/factory/python',
  'negative_control_command_ref':'evidence/014-durable-local-autonomy/native-edit-provenance-20261031/source-qualification.json',
  'archive_validation':'Existing verify_archive; remote SHA, SCP SHA, member hashes and contained final receipt compared without candidate execution'},
 'remaining_claims_not_established':['three fresh repeatability trials','full LL/HAL delivery','clean process qualification','production release','assessed ASPICE compliance','safety','generic-driver qualification','model learning benefit','24/7 availability'],
 'deadline_utc':'2026-10-31T07:57:59Z','fresh_trials_submitted_by_this_audit':0,'model_calls_by_this_audit':0}
path=A/'native05-external-m1-audit.json'
if path.exists():
 prior=json.loads(path.read_text())
 assert {k:v for k,v in prior.items() if k!='at'}=={k:v for k,v in audit.items() if k!='at'},'EXISTING_M1_AUDIT_CHANGED'
else:
 with path.open('x') as stream:stream.write(json.dumps(audit,sort_keys=True,separators=(',',':')))
print(json.dumps({'path':str(path),'sha256':sha(path),'milestone':audit['milestone'],'conditions':len(conditions),'release':audit['release_eligibility'],'fresh_trials_submitted':0}))
