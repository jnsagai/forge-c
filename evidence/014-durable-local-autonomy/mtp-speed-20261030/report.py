"""Descriptive speed pilot report. Does not qualify capabilities or choose a deployment."""
from pathlib import Path
import argparse,hashlib,json,statistics
def summarize(root):
 root=Path(root);cohorts={}
 for effort in ('draft3','draft2','draft4','draft6'):
  E=root/effort;rows=[]
  for p in sorted((E/'metrics').glob('*.json')):
   if p.name.endswith('-start.json'):continue
   row=json.loads(p.read_text());row['metric_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();rows.append(row)
  measured=[r for r in rows if r.get('backend_decode_tokens_per_second') is not None]
  speeds=[r['backend_decode_tokens_per_second'] for r in measured]
  completed=json.loads((E/'completion.json').read_text()) if (E/'completion.json').exists() else None
  activation=json.loads((E/'activation.json').read_text()) if (E/'activation.json').exists() else {}
  cohorts[effort]={'complete':completed is not None,'expected_trials':8,'recorded_trials':len(rows),'decode_measured_trials':len(measured),'setup_no_generation':sum(not r['requests'] for r in rows),'expected_decision_matches':sum(r['observed']==r['expected'] for r in rows),'median_decode_tokens_per_second':statistics.median(speeds) if speeds else None,'load_and_control_start_seconds':activation.get('load_and_control_start_seconds'),'rows':[{k:r.get(k) for k in ('trial_id','observed','expected','completion_output_tokens','gateway_total_seconds','trial_wall_seconds','backend_decode_tokens_per_second','metric_sha256')} for r in rows]}
 comparisons={}
 baseline={r['trial_id']:r for r in cohorts['draft3']['rows']}
 for variant in ('draft2','draft4','draft6'):
  paired=[]
  for row in cohorts[variant]['rows']:
   base=baseline.get(row['trial_id'])
   if base and base['gateway_total_seconds'] and row['gateway_total_seconds']:
    paired.append({'trial_id':row['trial_id'],'baseline_gateway_seconds':base['gateway_total_seconds'],'candidate_gateway_seconds':row['gateway_total_seconds'],'both_match_expected':base['observed']==base['expected'] and row['observed']==row['expected']})
  x=sum(p['baseline_gateway_seconds'] for p in paired);y=sum(p['candidate_gateway_seconds'] for p in paired)
  comparisons[variant]={'paired_generated_cases':paired,'aggregate_gateway_speedup':x/y if y else None}
 return {'schema':'forge-c/descriptive-mtp-speed-pilot/1','status':'COMPLETE_DESCRIPTIVE_PILOT' if all(c['complete'] for c in cohorts.values()) else 'IN_PROGRESS','runtime_revision':'a9b2ddfccc326bdcf8287c95a4310c0408429ccb','cohorts':cohorts,'comparisons':comparisons,'fixed':{'model':'Qwen3.8-27B Q8_0','kv':'f16','reasoning':'xhigh','context_tokens':262144,'one_inference':True},'automatic_model_selection':False,'formal_controlled_comparison':'NOT_QUALIFIED_RUNTIME_FACTOR_OUTSIDE_ROLE_IDENTITY','learning_overhead':'NOT_SEPARATELY_MEASURED','limitations':['Eight frozen diagnosis cases per setting; not authors/inspectors or full pipeline','Serial3/2/4/6 order, thermal/cache effects recorded, not randomized','Failed, rejected, blocked and unknown-usage outcomes remain in denominator','No hidden reasoning collected; designated semantic proposals retained']}

def write(root):
 root=Path(root);r=summarize(root);(root/'speed-summary.json').write_text(json.dumps(r,indent=2)+'\n')
 def value(v):return 'NOT_RUN' if v is None else f'{v:.2f}' if isinstance(v,(int,float)) and not isinstance(v,bool) else str(v)
 lines=['# Qwen MTP draft-speed pilot — '+r['status'],'','Driver pipeline remains owner-aborted. Q8/f16/xhigh/262144 fixed; only MTP draft length changes.','', '| MTP variant | Recorded / 8 | Decode measured | Setup failures | Median decode tok/s | Expected decisions / 8 |','|---|---:|---:|---:|---:|---:|']
 for e,c in r['cohorts'].items():lines.append(f"| {e} | {c['recorded_trials']} | {c['decode_measured_trials']} | {c['setup_no_generation']} | {value(c['median_decode_tokens_per_second'])} | {c['expected_decision_matches']} |")
 lines+=['','| MTP variant | Case | Output tokens | Gateway seconds | Native decode tok/s | Observed | Expected |','|---|---|---:|---:|---:|---|---|']
 for e,c in r['cohorts'].items():
  for row in c['rows']:lines.append('| '+ ' | '.join([e,row['trial_id'],value(row['completion_output_tokens']),value(row['gateway_total_seconds']),value(row['backend_decode_tokens_per_second']),row['observed'],row['expected']])+' |')
 lines+=['','No speed/quality winner or production capability is established. Missing runs, setup failures, job wall time and unknown usage are retained in raw metrics. Load/control startup is recorded separately in activation receipts. Formal controlled-comparison measurements and learning overhead remain unqualified.','','Runtime source: '+r['runtime_revision']+'.','',*['- '+x for x in r['limitations']],'']
 (root/'SPEED-REPORT.md').write_text('\n'.join(lines));return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();r=write(a.root);print(json.dumps({'status':r['status'],'report':str(a.root/'SPEED-REPORT.md')}))

