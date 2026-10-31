"""Read-only terminal facts for external DF-M1 review. No acceptance, launch or model call."""
from pathlib import Path
import os,sys,json,hashlib,sqlite3,zipfile,subprocess
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
os.environ.update(json.loads((E/'control/runtime-env-v6.json').read_text()))
sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.common import utc_now,sha256_file
from forge_factory.release.finalize import verify_archive
ws=E/'state/workorders/WO-AFO-ee4282b25001a15d-a1/workspace'
rid='01M67R1HNE9TKPWCYJ2SVKEPJS'
db=sqlite3.connect('file:'+str(E/'state/conductor/conductor.sqlite3')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
with FabroClient(base_url='http://127.0.0.1:32404',token=load_token(str(E/'fabro/storage')),timeout=15) as c:
 native=c.get_run(rid);events=list(c.iter_events(rid));usage=c.usage(rid)
out={'at':utc_now(),'native_id':rid,'native_status':run_status(native),'read_only':True,'model_calls':0,
 'order':dict(db.execute('SELECT order_id,state,terminal_reason FROM afo_work_orders WHERE order_id=?',('afo-ee4282b25001a15d',)).fetchone()),
 'source_revision':subprocess.check_output(['git','-C',str(E/'source'),'rev-parse','HEAD'],text=True).strip(),
 'stage_outcomes':[{'event':e['event'],'node':e.get('node_id'),'at':e.get('ts'),'failure':(e.get('properties') or {}).get('failure')} for e in events if e['event'] in ('stage.started','stage.completed','stage.failed')],
 'external_steering_event_count':sum('steer' in e['event'] for e in events),
 'request_states':[dict(r) for r in db.execute('SELECT state,COUNT(*) AS n FROM afo_request_ledger WHERE job_id=? GROUP BY state',('afo-product-0fbf506c5889f9f7faa87f04',))],
 'execution':[{k:v.get(k) for k in ('job_id','execution_liveness','resource_lease','task_outcome','native_run_ids','quiescence_evidence_ref')} for v in (json.loads(r[0]) for r in db.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?',('afo-product-0fbf506c5889f9f7faa87f04',)))],
 'phase_files':{f'SWE.{i}':[{'path':str(p.relative_to(ws)),'bytes':p.stat().st_size,'sha256':sha256_file(p)} for p in sorted((ws/f'workproducts/SWE.{i}').rglob('*')) if p.is_file()] for i in range(1,7)},
 'candidate_sha256':sha256_file(ws/'software/ll/stm32n6xx_ll_crc.h'),
 'attempt_results':[{'path':str(p.relative_to(ws)),'sha256':sha256_file(p),'result':json.loads(p.read_text())} for p in sorted((ws/'.forge-run/delivery-first').glob('attempt-*/result.json'))],
 'usage':usage,'milestone':'REQUIRES_EXTERNAL_REVIEW; NOT_INFERRED_FROM_NATIVE_STATUS'}
p=ws/'.forge-run/package.json'
if p.is_file() and out['native_status'] in {'SUCCEEDED','FAILED','CANCELLED','CANCELED'}:
 package=json.loads(p.read_text());archive=Path(package['archive'])
 assert archive.resolve().is_relative_to(E/'archives') and not archive.is_symlink()
 out['package']={k:package.get(k) for k in ('archive','archive_sha256','package_status','gap_count','gaps')}
 assert sha256_file(archive)==package['archive_sha256']
 out['archive_integrity']=verify_archive(archive)
 with zipfile.ZipFile(archive) as z:
  raw=z.read('evidence/verification/delivery-first/report.json')
  report=json.loads(raw)
  out['packaged_report_sha256']=hashlib.sha256(raw).hexdigest()
  out['packaged_report']={k:report.get(k) for k in ('factory_revision','local_profile','model_profile','execution','artifact_delivery','functional_verification','slice_behavior_and_compile','integrity_issues','final_candidate_matches_last_verification','process_qualification','release_eligibility','authorship','milestone','metrics','unrun')}
  out['packaged_native_evidence']={k:report['native_evidence'].get(k) for k in ('status','native_id','native_status','authorship','write_evidence','phase_attempts','node_failures','external_guidance_events')}
  out['packaged_phase_evidence']=report['phases']
  out['archive_members']=z.namelist()
else:out['terminal_package']='NOT_YET_AVAILABLE'
# Additional archive/live binding observations; no candidate execution or acceptance inference.
if 'archive_members' in out:
 with zipfile.ZipFile(Path(out['package']['archive'])) as z:
  final_member='evidence/verification/delivery-first/attempts/attempt-final/result.json'
  out['archived_final_receipt_present']=final_member in z.namelist()
  if out['archived_final_receipt_present']:
   raw_final=z.read(final_member);final=json.loads(raw_final)
   live_final=ws/'.forge-run/delivery-first/attempt-final/result.json'
   out['archived_final_receipt_sha256']=hashlib.sha256(raw_final).hexdigest()
   out['archived_final_receipt_equals_live_bytes']=raw_final==live_final.read_bytes()
   out['archived_final_receipt']=final
   out['archived_report_has_same_final_receipt']=any(r==final for r in report.get('attempts',[]))
  candidate_member='evidence/software/ll/stm32n6xx_ll_crc.h'
  out['archived_candidate_sha256']=hashlib.sha256(z.read(candidate_member)).hexdigest()
  out['archived_candidate_equals_live']=out['archived_candidate_sha256']==out['candidate_sha256']
  out['archived_report_candidate_hashes']=report.get('candidate_hashes')
  out['archived_report_declared_scope']=report.get('declared_scope')
  out['archived_preflight']=json.loads(z.read('evidence/verification/delivery-first/attempts/initial.json'))
  out['archived_final_verification_node_observed']=any(e.get('node_id')=='df_final_verify' and e['event']=='stage.completed' for e in events)
  out['actual_terminal_metrics']={'tokens':usage.get('totals',{}).get('usage',{}).get('tokens',{}),
   'timing':usage.get('totals',{}).get('timing',{}),
   'requests_from_ledger':sum(r['n'] for r in out['request_states']),
   'native_requests':usage.get('totals',{}).get('usage',{}).get('requests','UNKNOWN_NOT_REPORTED'),
   'reasoning_token_breakdown':'UNKNOWN; provider zero does not measure hidden reasoning'}

if 'archive_members' not in out:
 print(json.dumps({'status':'NOT_TERMINAL_NO_PACKET_WRITTEN','native_status':out['native_status'],'at':out['at']}))
else:
 from forge_factory.afo.durable import digest,immutable_json
 packet=E/'control/qualification-observations/native05'/('terminal-facts-'+digest(out)+'.json')
 immutable_json(packet,out)
 print(json.dumps({'path':str(packet),'sha256':sha256_file(packet),'at':out['at'],
  'native_status':out['native_status'],'order':out['order'],
  'archive':out['package'],'archive_integrity':out['archive_integrity'],
  'candidate_sha256':out['candidate_sha256'],
  'archived_final_receipt_present':out['archived_final_receipt_present'],
  'archived_final_receipt_equals_live_bytes':out.get('archived_final_receipt_equals_live_bytes'),
  'archived_report_has_same_final_receipt':out.get('archived_report_has_same_final_receipt'),
  'archived_candidate_equals_live':out['archived_candidate_equals_live'],
  'functional_verification':out['packaged_report'].get('functional_verification'),
  'execution':out['execution'],'external_steering_event_count':out['external_steering_event_count']}))
