"""Append-only protected publication overlay; no source/Git/runtime mutation or tests."""
from pathlib import Path
from contextlib import closing
from collections import Counter
import hashlib,json,re,shutil,sqlite3,subprocess,xml.etree.ElementTree as ET
B=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c');OPS=B/'ops/scratch'
OUT=OPS/'codex-integration23-exports';RUN=OUT/'evidence/v0.4/runs/CODEX-INTEGRATION23-20261105';CRE=OUT/'evidence/cre'
C='dc27abba601e5f6713f30e6027cb0bbd64241528';BASE='74e44a1f23b01f3200350436df1691249b441292';I23='c541a3b44db25a26cbbd784485d9938c361ca3bd'
NATIVE=B/'repos/forge-c-014-owner-supervised-development';WT=B/'repos/forge-c-014-integration23';PROOF=OPS/'owner-development-dc27abba-omniverse-prospective-proof'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
# Match actual complete credential lines, not scanner source literals or quoted test assertions.
private_header=re.compile(rb'^\s*-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----\s*$')
credential_assignment=re.compile(rb'^\s*(?:export\s+)?(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|FORGE_FABRO_TOKEN|FABRO_API_TOKEN|FORGE_LINE_AUTH_TOKEN)\s*=\s*[^\s]+\s*$')
auth_header=re.compile(rb'^\s*Authorization:\s*Bearer\s+\S+\s*$',re.I)
scanned=[]
def scan(data,label):
 hits=[]
 for no,line in enumerate(data.splitlines(),1):
  if private_header.fullmatch(line) or credential_assignment.fullmatch(line) or auth_header.fullmatch(line):hits.append(no)
 assert not hits,('SECRET_HEADER_OR_ASSIGNMENT_REFUSED',label,hits)
 scanned.append(label)
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);data=(json.dumps(x,indent=2,sort_keys=True)+'\n').encode();scan(data,str(p.relative_to(OUT)))
 with p.open('xb') as f:f.write(data)
def copy(a,p,expected=None):
 assert a.is_file() and not a.is_symlink(),str(a)
 if expected is not None:assert sha(a)==expected,str(a)
 if a.suffix!='.bundle':scan(a.read_bytes(),str(a))
 assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,p);assert sha(a)==sha(p)

def xml_cases(p):
 out={}
 for t in ET.parse(p).getroot().iter('testcase'):
  key=t.get('classname','')+'::'+t.get('name','')
  assert key not in out,('DUPLICATE_CASE',p,key)
  out[key]='ERROR' if list(t.iter('error')) else 'FAIL' if list(t.iter('failure')) else 'SKIP' if list(t.iter('skipped')) else 'PASS'
 return out
assert not OUT.exists() and not (OPS/'codex-integration23-qualified-index.json').exists()
for tree,rev in [(NATIVE,C),(WT,I23)]:
 assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()==rev
 assert not subprocess.check_output(['git','-C',str(tree),'status','--porcelain'],text=True)
sip=OPS/'owner-supervised-development-source-review-index.json';assert sha(sip)=='ea1328f14202156ff1078b3a156444ca11dd6e36802e77c4f7f86768437c222d';si=json.loads(sip.read_text());assert si['source']['commit']==C and si['source']['baseline']==BASE and len(si['source']['files'])==29 and len(si['evidence'])==54
source_rows=[]
for r in si['source']['files']:
 p=Path(r['path']);rel=p.relative_to(NATIVE);assert sha(p)==r['sha256'] and sha(WT/rel)==r['sha256'];source_rows.append({'path':str(rel),'sha256':r['sha256']})
assert sorted(r['path'] for r in source_rows)==sorted(subprocess.check_output(['git','-C',str(WT),'diff','--name-only',I23+'^',I23],text=True).splitlines())
for r in si['evidence']:
 p=Path(r['path']);assert p.parent==OPS and p.is_file() and sha(p)==r['sha256'] and p.stat().st_size==r['bytes']
 assert p.name!='runtime-inputs.tar' and p.suffix!='.tar'
 if p.suffix!='.bundle':scan(p.read_bytes(),str(p))
correction=OPS/'owner-supervised-development-iwdg-observation-correction.json';assert sha(correction)=='e718cf55df026cea1fdfe9cddc2450a309251ac7851daded30c7a8423c6e6e8f'
diagnosis=OPS/'iwdg-assurance-readonly-diagnosis-20261105.json';assert sha(diagnosis)=='226741015a0b0d882656a417291f443addb435572ffba76afe90e447f1ff00d7'
inputs=OPS/'codex-integration23-inputs-before-tests.json';assert sha(inputs)=='580031ebcc2bd45264e77a7fa0cac134ca2b2d50ff8faa9bb62622ef1ba7daf8';inp=json.loads(inputs.read_text());assert inp['all12_unique_inputs_verified_before_any_tests'] and len(inp['files'])==12
for row in inp['files']:assert sha(WT/row['path'])==row['sha256']
checks=json.loads((OPS/'codex-integration23-checks-r1/results.json').read_text());assert checks['tested_revision']==I23 and checks['runtime_candidate']==C and all(r['exit_code']==0 for r in checks['results'])
for r in checks['results']:assert sha(Path(r['log']))==r['sha256']
rootcases=xml_cases(OPS/'codex-integration23-checks-r1/integration.xml');assert len(rootcases)==90 and set(rootcases.values())=={'PASS'}
latest={}
for name in ['owner-supervised-development-affected-r23.xml','owner-supervised-development-final-r24.xml','owner-supervised-development-envelope-r25.xml','owner-supervised-development-final-r26.xml']:latest.update(xml_cases(OPS/name))
assert len(latest)==209 and Counter(latest.values())==Counter({'PASS':208,'FAIL':1})
remaining=[k for k,v in latest.items() if v=='FAIL'];assert remaining==['factory.python.tests.test_peripheral_assurance::test_iwdg_unit_test_verifiers_run']
pi=PROOF/'prospective-export-index.json';assert sha(pi)=='35661a9f2aab9741922b52ad1f7cae4804072496a91e02b58c78e9bbae4c5013';proof=json.loads(pi.read_text());assert proof['source']==C and proof['namespace_tests']==56 and proof['model_calls']==0 and proof['production_mutations'] is False and len(proof['files'])==9
allowed={'staging-receipt.json','transport-receipt.json','probe-summary.json','cpu-preflight/preflight.json','authority-namespace-controls.xml','authority-namespace-controls.stdout.log','native-header/measurement.json','stage.stdout.log','stage-v2.stdout.log'}
assert {r['path'] for r in proof['files']}==allowed
for r in proof['files']:assert sha(PROOF/r['path'])==r['sha256'] and (PROOF/r['path']).stat().st_size==r['bytes']
remote_cases=xml_cases(PROOF/'authority-namespace-controls.xml');assert len(remote_cases)==56 and set(remote_cases.values())=={'PASS'}
measurement=json.loads((PROOF/'native-header/measurement.json').read_text());assert sha(PROOF/'native-header/measurement.json')=='f653472b2224344b33cb35b908739d32e242febb0917e67bb659b7f10161f0e9';assert measurement['source_revision']==C and measurement['verdict']=='PASS' and measurement['native_run_id']=='01M6P56T88AT55C4701SJEG46A' and measurement['fixture_terminal_confirmed'] and measurement['own_server_stopped'] and measurement['production_mutations'] is False
bundle=OPS/'owner-supervised-development-source.bundle';assert any(Path(r['path'])==bundle for r in si['evidence'])
heads=subprocess.check_output(['git','-C',str(NATIVE),'bundle','list-heads',str(bundle)],text=True).splitlines();assert heads and all(line.split()[0]==C for line in heads)
verify=subprocess.run(['git','-C',str(NATIVE),'bundle','verify',str(bundle)],capture_output=True,text=True);assert verify.returncode==0
# The bundle's sole revision delta is exactly the29 declared source/test/ADR paths, no vendor or live data.
assert sorted(subprocess.check_output(['git','-C',str(NATIVE),'diff','--name-only',BASE,C],text=True).splitlines())==sorted(r['path'] for r in source_rows)
for row in source_rows:
 p=row['path'];assert not any(x in p.split('/') for x in ['inputs','.env','credentials','auth']) and not p.endswith(('.sig','.key','.pem','.tar'))

decision_path=OPS/'owner-development-dc27-normal-change-root-r1-decision.json';d=json.loads(decision_path.read_text());assert d['decision_id']=='pd-a628033c80b802774a4d' and d['candidate_revision']==C and d['baseline_revision']==BASE and d['decision']=='ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result']=='PASS' or g['name']=='reproducer' and g['result']=='NOT_RUN' and g['reason_code']=='NOT_APPLICABLE_FOR_CHANGE' for g in d['hard_gates'])
refs=next(g['evidence_refs'] for g in d['hard_gates'] if g['name']=='prevention');assert len(refs)==len(set(refs))==175
rrs=[];bench=[]
with closing(sqlite3.connect((B/'state/supervisor/incidents.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
 db.row_factory=sqlite3.Row;dr=dict(db.execute('SELECT * FROM cre_promotion_decisions WHERE decision_id=?',(d['decision_id'],)).fetchone());assert dr['candidate']==C and dr['baseline']==BASE and json.loads(dr['record'])=={k:v for k,v in d.items() if k not in ('candidate_revision','baseline_revision')}
 for ref in refs:
  rid=ref.split(':',1)[1];row=dict(db.execute('SELECT * FROM cre_reproducer_runs WHERE run_id=?',(rid,)).fetchone());assert row['revision']==C and row['verdict']=='SYMPTOM_ABSENT';log=B/'state/reliability/reproducers'/(rid+'.log');assert sha(log)==row['log_sha256'];scan(log.read_bytes(),str(log));rrs.append((row,log))
 for gate in d['hard_gates']:
  for ref in gate['evidence_refs']:
   if ref.startswith('benchmark-run:'):
    rid=ref.split(':',1)[1];row=dict(db.execute('SELECT * FROM cre_benchmark_runs WHERE run_id=?',(rid,)).fetchone());assert row['revision'] in (BASE,C);bench.append(row)
assert len(bench)==4 and len({r['run_id'] for r in bench})==4
# All inputs checked above before the first publication write. Nothing is applied to Git/source.
write(CRE/'decisions'/(d['decision_id']+'.json'),d);write(CRE/'decisions'/(d['decision_id']+'-db-row.json'),dr)
for row,log in rrs:
 copy(log,CRE/'reproducers'/log.name,row['log_sha256']);write(CRE/'reproducers'/(row['run_id']+'.json'),row)
for row in bench:write(CRE/'benchmarks'/(row['run_id']+'.json'),row)
for r in si['evidence']:copy(Path(r['path']),RUN/'source-qa'/Path(r['path']).name,r['sha256'])
copy(sip,RUN/'source-review-index.json',sha(sip));copy(correction,RUN/correction.name,sha(correction));copy(diagnosis,RUN/diagnosis.name,sha(diagnosis))
copy(inputs,RUN/'integration-inputs-before-tests.json',sha(inputs))
for p in sorted((OPS/'codex-integration23-checks-r1').iterdir()):assert p.is_file();copy(p,RUN/'integration-checks'/p.name,sha(p))
for p in [decision_path,OPS/'owner-development-dc27-normal-change-root-r1-worktrees-before-tests.json',OPS/'owner-development-dc27-normal-change-root-r1.log',OPS/'owner-development-normal-change-root.py']:copy(p,RUN/'independent-change'/p.name,sha(p))
for r in proof['files']:copy(PROOF/r['path'],RUN/'prospective-omniverse'/r['path'],r['sha256'])
copy(pi,RUN/'prospective-omniverse/prospective-export-index.json',sha(pi))
for name in ['owner-development-dc27abba-stage-v2-correction.json','owner-development-dc27abba-stage-remote-v2.py','owner-development-dc27abba-transfer-recovery.json']:copy(OPS/name,RUN/'staging-provenance'/name,sha(OPS/name))
copy(Path(__file__),RUN/Path(__file__).name,sha(Path(__file__)))
write(RUN/'source-code-binding.json',{'qualified_native_revision':C,'qualified_native_baseline':BASE,'integration_code_revision':I23,'source_paths':source_rows,'all29_source_files_byte_identical_to_I23':True,'whole_integration_tree_CRE_claimed':False,'bundle_heads':heads,'bundle_verified':True,'bundle_is_exact29_file_source_delta_only':True,'source_git_and_worktrees_untouched':True})
write(RUN/'source-qa-composite-by-node.json',{'cases':latest,'counts':dict(Counter(latest.values())),'distinct_cases':len(latest),'merge_order':['affected-r23','final-r24','envelope-r25','final-r26'],'description':'Latest same-node focused result supersedes earlier source QA; no fresh full final-tree209-case run is claimed.','remaining_baseline_identical_failure':remaining,'detailed_failure_reason':'UNVERIFIED; authoritative append-only correction included. Static fixture diagnosis is distinct from a reproduced detailed failure.'})
validation={'schema':'forge-c/integration23-publication-validation/1','status':'SOURCE_ELIGIBLE_OFFLINE_PLUS_PROSPECTIVE_CPU_STUB_ONLY','qualified_source':C,'qualified_baseline':BASE,'integration_source':I23,'decision_id':d['decision_id'],'hard_gates':{g['name']:g['result'] for g in d['hard_gates']},'prevention':{'rows':175,'all_symptom_absent':True,'all_raw_logs_sha256_verified':True},'benchmark_rows':4,'causal':'NOT_RUN_NOT_APPLICABLE_FOR_CHANGE','source_binding':'29source/test/ADRfiles byte-identical between qualifieddc27 and integrationc541; exactI23whole-tree CRE is not asserted','source_QA':{'distinct_cases':209,'PASS':208,'FAIL':1,'baseline_identical_NOT_RUN_assertion_preserved':True,'detailed_failure_reason':'UNVERIFIED; see correction and read-only static diagnosis','failure_not_waived':True},'root_integration_QA':{'PASS':90,'SKIP':0,'v01_make_test':'PASS','v03_packager':'PASS','design':14},'prospective_omniverse':{'scope':'NEW_PRIVATE_CPU_KERNEL_AND_DETERMINISTIC_NATIVE_STUB_ONLY','cpu_preflight':'PASS_PROSPECTIVE_ONLY','namespace_authority_tests':56,'namespace_skip':0,'native_stub_run_id':measurement['native_run_id'],'native_stub_terminal':'SUCCEEDED','own_stub_server_stopped':True,'actual_model_calls':0,'owner_record_issued':False,'production_mission_or_services_mutated':False},'counting_limit':'Source209distinct/208PASS+1FAIL, root90PASS and remote56PASS overlap; never sum as355distinct. Earlier failed QA runs are retained, not recast as final passes.','new_source_only_task_ticks':0,'production_ACT':False,'actual_native_role_competence':'NOT_RUN','endurance_acceptance':'NOT_RUN','actual_models_or_GPU_inference':0,'publication_scope':'OPS overlay only; root independently reviews/applies/commits. No source/Git/policy/grant/ledger edits or push.','excluded':['runtime-inputs.tar','outer transport.tar','vendor text/source inputs','whole private Fabro server tree','.env/credentials/private owner keys','live telemetry payloads'],'preserved':['all54 source QA artifacts including failures','baseline-identical IWDG assertion + append-only reason correction','stage no-refs failure log + exact safe v2 correction/script','transfer-recovery JSON; archives themselves excluded'],'limitations':['Signature-free development source qualification does not activate a live mission or authorize a job by itself.','A transport STUB validates wire/header/control plumbing, not Ornith/Qwen inference or role competence.','Human review/safety and production signature guards remain independent.','No certification, production release, main merge, new task acceptance or M9 endurance claim.']}
write(RUN/'validation.json',validation)
write(RUN/'publication-safety-check.json',{'line_header_scanned_items':len(scanned),'private_key_full_line_pattern':'checked','actual_secret_assignment_and_Bearer_header_lines':'checked','binary_bundle_handling':'Verified Git bundle solehead and exact29 source/test/ADR file delta; not treated as a plaintext secret log.','source_path_allowlist_count':29,'QA_index_count':54,'prospective_file_allowlist_count':9,'prospective_index_plus_files':10,'forbidden_archives_excluded':True,'vendor_contents_excluded':True,'effects':False})
files=[{'path':str(p.relative_to(OUT)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file()]
index=OPS/'codex-integration23-qualified-index.json';index_data={'schema':'forge-c/protected-publication-export-index/1','source':C,'baseline':BASE,'integration_source':I23,'exports':str(OUT),'status':validation['status'],'decision_id':d['decision_id'],'prevention_records':175,'benchmark_rows':4,'files':files}
with index.open('x') as f:json.dump(index_data,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'files':len(files),'index':str(index),'index_sha256':sha(index),'prevention':175,'benchmarks':4,'source_QA':validation['source_QA'],'status':validation['status']}))
