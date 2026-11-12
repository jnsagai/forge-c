"""Descriptive speed pilot report. Does not qualify capabilities or choose a deployment."""
from pathlib import Path
import argparse,hashlib,json,statistics
def summarize(root):
 root=Path(root);cohorts={}
 for effort in ('xhigh','medium'):
  E=root/effort;rows=[]
  for p in sorted((E/'metrics').glob('*.json')):
   if p.name.endswith('-start.json'):continue
   row=json.loads(p.read_text());row['metric_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();rows.append(row)
  measured=[r for r in rows if r.get('backend_decode_tokens_per_second') is not None]
  speeds=[r['backend_decode_tokens_per_second'] for r in measured]
  completed=json.loads((E/'completion.json').read_text()) if (E/'completion.json').exists() else None
  activation=json.loads((E/'activation.json').read_text()) if (E/'activation.json').exists() else {}
  cohorts[effort]={'complete':completed is not None,'expected_trials':8,'recorded_trials':len(rows),'decode_measured_trials':len(measured),'setup_no_generation':sum(not r['requests'] for r in rows),'expected_decision_matches':sum(r['observed']==r['expected'] for r in rows),'median_decode_tokens_per_second':statistics.median(speeds) if speeds else None,'load_and_control_start_seconds':activation.get('load_and_control_start_seconds'),'rows':[{k:r.get(k) for k in ('trial_id','observed','expected','completion_output_tokens','gateway_total_seconds','trial_wall_seconds','backend_decode_tokens_per_second','metric_sha256')} for r in rows]}
 base={r['trial_id']:r for r in cohorts['xhigh']['rows']};candidate={r['trial_id']:r for r in cohorts['medium']['rows']};pairs=[]
 for trial in base.keys() & candidate.keys():
  b=base[trial];c=candidate[trial]
  if b['backend_decode_tokens_per_second'] is not None and c['backend_decode_tokens_per_second'] is not None:
   pairs.append({'trial_id':trial,'xhigh_gateway_seconds':b['gateway_total_seconds'],'medium_gateway_seconds':c['gateway_total_seconds'],'latency_ratio_medium_over_xhigh':c['gateway_total_seconds']/b['gateway_total_seconds'],'both_match_expected':b['observed']==b['expected'] and c['observed']==c['expected']})
 return {'schema':'forge-c/descriptive-reasoning-speed-pilot/1','status':'COMPLETE_DESCRIPTIVE_PILOT' if all(c['complete'] for c in cohorts.values()) else 'IN_PROGRESS','runtime_revision':'37c0c354629312a70eb6a199989477036bb674d9','cohorts':cohorts,'paired_generated_cases':sorted(pairs,key=lambda p:p['trial_id']),'unsupported_high':True,'automatic_model_selection':False,'formal_controlled_comparison':'INCOMPLETE_INDEPENDENT_COMPARISON_MEASUREMENT_NOT_QUALIFIED','learning_overhead':'NOT_SEPARATELY_MEASURED','limitations':['Two initial xhigh cases had host setup refusals before inference, retained in denominator','Small diagnosis-only cohort; not author/inspector or pipeline qualification','Serial xhigh-first order and thermal/cache differences are recorded; not randomized','Model reasoning tokens included; no hidden reasoning content collected']}
def write(root):
 root=Path(root);r=summarize(root);(root/'speed-summary.json').write_text(json.dumps(r,indent=2)+'\n')
 def value(v):return 'NOT_RUN' if v is None else f'{v:.2f}' if isinstance(v,(int,float)) and not isinstance(v,bool) else str(v)
 lines=['# Qwen reasoning-speed pilot — '+r['status'],'','Driver pipeline remains owner-aborted; results below are diagnosis speed measurements.','', '| Effort | Recorded / 8 | Decode measured | Setup failures | Median decode tok/s | Expected decisions / 8 |','|---|---:|---:|---:|---:|---:|']
 for e,c in r['cohorts'].items():lines.append(f"| {e} | {c['recorded_trials']} | {c['decode_measured_trials']} | {c['setup_no_generation']} | {value(c['median_decode_tokens_per_second'])} | {c['expected_decision_matches']} |")
 lines+=['','High: UNSUPPORTED by the installed template; never mapped to medium.','','| Effort | Case | Output tokens | Gateway seconds | Native decode tok/s | Observed | Expected |','|---|---|---:|---:|---:|---|---|']
 for e,c in r['cohorts'].items():
  for row in c['rows']:lines.append('| '+ ' | '.join([e,row['trial_id'],value(row['completion_output_tokens']),value(row['gateway_total_seconds']),value(row['backend_decode_tokens_per_second']),row['observed'],row['expected']])+' |')
 lines+=['','No speed/quality winner or production capability is established. Missing runs, setup failures, job wall time and unknown usage are retained in raw metrics. Load/control startup is recorded separately in activation receipts. Formal controlled-comparison measurements and learning overhead remain unqualified.','','Runtime source: '+r['runtime_revision']+'.','',*['- '+x for x in r['limitations']],'']
 (root/'SPEED-REPORT.md').write_text('\n'.join(lines));return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();r=write(a.root);print(json.dumps({'status':r['status'],'report':str(a.root/'SPEED-REPORT.md')}))

