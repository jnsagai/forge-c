"""Append-only sanitized I24 publication overlay. No runtime effects, source edits or push."""
from pathlib import Path
from contextlib import closing
import hashlib,json,re,shutil,sqlite3,subprocess,tarfile,xml.etree.ElementTree as ET
B=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c');O=B/'ops/scratch'
OUT=O/'codex-integration24-exports';RUN=OUT/'evidence/v0.4/runs/CODEX-INTEGRATION24-20261105';CRE=OUT/'evidence/cre'
WT=B/'repos/forge-c-014-integration24';SRC=B/'repos/forge-c-014-owner-profile-bootstrap-v7'
I='2ec54d20f66fb908788a1cec97b1dc92a7488f18';C='887820300340dcc31a03f3dc46c31107e9aef9f3';V4='214c9668c605a5bad690820cb1f6601bf9ccb935'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
private=re.compile(rb'^\s*-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----\s*$')
secret=re.compile(rb'^\s*(?:export\s+)?(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|FORGE_FABRO_TOKEN|FABRO_API_TOKEN|FORGE_LINE_AUTH_TOKEN)\s*=\s*[^\s]+\s*$')
bearer=re.compile(rb'^\s*Authorization:\s*Bearer\s+\S+\s*$',re.I)
scanned=[]
def scan(raw,label):
 assert not [n for n,line in enumerate(raw.splitlines(),1) if private.fullmatch(line) or secret.fullmatch(line) or bearer.fullmatch(line)],('SECRET_HEADER_REFUSED',label)
 scanned.append(label)
def write(p,v):
 raw=(json.dumps(v,indent=2,sort_keys=True)+'\n').encode();scan(raw,str(p));p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(raw)
def copy(a,z,expected=None):
 assert a.is_file() and not a.is_symlink() and not z.exists()
 if expected:assert sha(a)==expected
 raw=a.read_bytes()
 if a.suffix!='.bundle':scan(raw,str(a))
 z.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,z);assert sha(a)==sha(z)
def git(p,*a):return subprocess.check_output(['git','-C',str(p),*a],text=True).strip()
assert not OUT.exists() and not (O/'codex-integration24-qualified-index.json').exists()
assert git(WT,'rev-parse','HEAD')==I and not git(WT,'status','--porcelain')
assert git(SRC,'rev-parse','HEAD')==C and not git(SRC,'status','--porcelain')
si=json.loads((O/'owner-profile-bootstrap-v7-final-source-index.json').read_text());assert si['source']==C and si['affected']['tests']=='185' and all(si['affected'][k]=='0' for k in ('failures','errors','skipped'))
source_paths=git(SRC,'diff','--name-only','dc27abba601e5f6713f30e6027cb0bbd64241528',C).splitlines();assert len(source_paths)==11
source_rows=[]
for n in source_paths:
 assert (SRC/n).read_bytes()==(WT/n).read_bytes();assert not any(x in n.split('/') for x in ('inputs','auth','.env','credentials'))
 source_rows.append(dict(path=n,sha256=sha(SRC/n)))
assert set(git(WT,'diff','--name-only','32e03f5c326330ac1056560dcc0b44451cfed523',I).splitlines())==set(source_paths)
inputs=json.loads((O/'codex-integration24-inputs-before-tests.json').read_text());assert inputs['all12_before_any_tests'] and len(inputs['files'])==12
for r in inputs['files']:assert sha(WT/r['path'])==r['sha256']
# Independent normal decisions and exact canonical records/logs, including the external staged causal pair.
decisions=[]
with closing(sqlite3.connect((B/'state/supervisor/incidents.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
 db.row_factory=sqlite3.Row
 for label,name,expected in [('initial214','owner-profile-bootstrap-v4-normal-change-root-r1-decision.json','pd-6f7f93b58fbd8f787e01'),('fixed887','owner-profile-bootstrap-v7-normal-fix-root-r1-decision.json','pd-732407cf0b292029816c')]:
  p=O/name;d=json.loads(p.read_text());assert d['decision_id']==expected and d['decision']=='ELIGIBLE_FOR_OFFLINE_REVIEW'
  assert all(g['result']=='PASS' or label=='initial214' and g['name']=='reproducer' and g['result']=='NOT_RUN' and g['reason_code']=='NOT_APPLICABLE_FOR_CHANGE' for g in d['hard_gates'])
  refs=next(g['evidence_refs'] for g in d['hard_gates'] if g['name']=='prevention');assert len(refs)==len(set(refs))==175
  dr=dict(db.execute('SELECT * FROM cre_promotion_decisions WHERE decision_id=?',(expected,)).fetchone());assert dr['candidate']==d['candidate_revision'] and dr['baseline']==d['baseline_revision'] and json.loads(dr['record'])=={k:v for k,v in d.items() if k not in ('candidate_revision','baseline_revision')}
  write(CRE/'decisions'/(expected+'.json'),d);write(CRE/'decisions'/(expected+'-db-row.json'),dr)
  rrs=[];bench=[]
  for g in d['hard_gates']:
   for ref in g['evidence_refs']:
    kind,_,rid=ref.partition(':')
    if kind=='reproducer-run':
     row=dict(db.execute('SELECT * FROM cre_reproducer_runs WHERE run_id=?',(rid,)).fetchone());log=B/'state/reliability/reproducers'/(rid+'.log');assert sha(log)==row['log_sha256']
     if g['name']=='prevention':assert row['revision']==d['candidate_revision'] and row['verdict']=='SYMPTOM_ABSENT'
     elif row['revision']==d['baseline_revision']:assert row['verdict']=='SYMPTOM_PRESENT'
     else:assert row['revision']==d['candidate_revision'] and row['verdict']=='SYMPTOM_ABSENT'
     copy(log,CRE/'reproducers'/log.name,row['log_sha256']);write(CRE/'reproducers'/(rid+'.json'),row);rrs.append(rid)
    if kind=='benchmark-run':
     row=dict(db.execute('SELECT * FROM cre_benchmark_runs WHERE run_id=?',(rid,)).fetchone());assert row['revision'] in (d['candidate_revision'],d['baseline_revision']);write(CRE/'benchmarks'/(rid+'.json'),row);bench.append(rid)
  assert len(bench)==len(set(bench))==4 and len(rrs)==(177 if label=='fixed887' else 175)
  decisions.append(dict(label=label,decision_id=expected,candidate=d['candidate_revision'],baseline=d['baseline_revision'],prevention=175,causal='PASS_EXTERNAL_STAGED_FIX' if label=='fixed887' else'NOT_RUN_CHANGE',reproducer_records=len(rrs),benchmark_records=4))
  for suffix in ('decision.json','worktrees-before-tests.json','log'):
   src=O/(name.removesuffix('-decision.json')+'.log' if suffix=='log' else name.removesuffix('decision.json')+suffix);copy(src,RUN/'independent-qualification'/src.name)
# Keep every local development QA result and earlier failure, never recast them as final passes.
qa=[]
for f in sorted(O.glob('owner-profile-bootstrap-*')):
 if not f.is_file() or f.suffix not in ('.log','.xml','.json'):continue
 if not (f.name.startswith(tuple('owner-profile-bootstrap-v'+str(i)+'-' for i in range(1,8))) or f.name in ('owner-profile-bootstrap-first.log','owner-profile-bootstrap-first.xml','owner-profile-bootstrap-inputs-before-tests.json')):continue
 # Decisions/worktree receipts are independently handled above; actual live payloads are never selected.
 if '-normal-' in f.name:continue
 qa.append(f)
for f in qa:copy(f,RUN/'source-qa'/f.name)
for f in sorted((O/'owner-bootstrap-cold-external-oracle').iterdir()):
 if f.is_file():copy(f,RUN/'external-staged-oracle'/f.name)
for name in ('owner-profile-bootstrap-cold-source-pinned.py','owner-bootstrap-external-oracle-root-bwrap-r1.json','owner-bootstrap-external-oracle-root-bwrap-r1-worktrees-before-tests.json','owner-profile-bootstrap-v7-normal-fix-root-r1-verified.json','owner-profile-bootstrap-214-export-root-verification-r1.json','owner-bootstrap-partial-cleanup-v2-root-review-r1.json','owner-bootstrap-collected-unit-actual-systemd-r1.json','codex-integration24-inputs-before-tests.json'):
 copy(O/name,RUN/'root-review'/name)
# Whitelisted prospective CPU/kernel/STUB archive only. Do not publish tar or private server/storage/auth tree.
archive=O/'owner-profile-bootstrap-214-actual-prospective-proof.tar';verify=json.loads((O/'owner-profile-bootstrap-214-export-root-verification-r1.json').read_text());assert sha(archive)==verify['archive_sha256']
allowed={'staging-receipt.json','probe-summary.json','bootstrap-affected-controls.xml','bootstrap-affected-controls.stdout.log','cpu-preflight/preflight.json','native-header/measurement.json','prospective-proof-export-index.json'}
with tarfile.open(archive) as t:
 members=t.getmembers();assert {m.name for m in members}==allowed and len(members)==7 and all(m.isfile() for m in members)
 raw={m.name:t.extractfile(m).read() for m in members};pi=json.loads(raw['prospective-proof-export-index.json']);assert hashlib.sha256(raw['prospective-proof-export-index.json']).hexdigest()==verify['index_sha256']
 # Root independently verified the archive/index and all listed hashes. Check actual member metadata as well.
 for row in pi['files']:
  assert hashlib.sha256(raw[row['path']]).hexdigest()==row['sha256']
 for name,data in raw.items():
  scan(data,name);target=RUN/'prospective-214'/name;target.parent.mkdir(parents=True,exist_ok=True)
  with target.open('xb') as f:f.write(data)
# Publish only selected factual failure metadata. Full /proc inventories/environment/private records are excluded.
failure_path=O/'owner-profile-bootstrap-214-partial-readonly.json';failure=json.loads(failure_path.read_text());ledger_path=O/'owner-profile-bootstrap-214-partial-ledger-readonly.json';ledger=json.loads(ledger_path.read_text())
write(RUN/'actual214-failure-sanitized.json',dict(schema='forge-c/bootstrap-actual-failure-sanitized/1',source=V4,source_observation_refs=[dict(path=failure_path.name,sha256=sha(failure_path)),dict(path=ledger_path.name,sha256=sha(ledger_path))],unit=failure['unit'],journal_filtered=failure['journal_filtered'],canonical_bootstrap_metadata=failure['queue_bootstrap_metadata'],resource_counts=failure['resource_counts'],native_history_equal_original=failure['native_history_equal_original'],mission_all_tables_exactly_unchanged=ledger['mission_all_tables_exactly_unchanged'],model_calls=failure['model_calls'],unknown_outcome='PRESERVED_NOT_READY_NOT_RELABELED',live_retry_or_cleanup='NOT_CLAIMED_BY_THIS_PUBLICATION',excluded=['full private issuer record','raw environment/argv','foreign process inventories','live telemetry payloads']))
for n,head,prereq in [('owner-profile-bootstrap-v4-source.bundle',V4,'dc27abba601e5f6713f30e6027cb0bbd64241528'),('owner-profile-bootstrap-v7-source.bundle',C,V4)]:
 p=O/n;heads=git(SRC,'bundle','list-heads',str(p)).splitlines();assert heads and all(x.split()[0]==head for x in heads)
 delta=git(SRC,'diff','--name-only',prereq,head).splitlines();assert set(delta)<=set(source_paths)
 copy(p,RUN/'source-bundles'/n)
copy(O/'package-codex-integration24-v2.py',RUN/'package-codex-integration24-v2.py')
copy(O/'integration24-packaging-initial-syntax-error.json',RUN/'integration24-packaging-initial-syntax-error.json')
copy(O/'owner-bootstrap-reconciliation-publication-rationale.md',RUN/'README.md')
write(RUN/'source-code-binding.json',dict(qualified_runtime=C,integration_source=I,published_base='32e03f5c326330ac1056560dcc0b44451cfed523',source_paths=source_rows,all11_source_paths_byteidentical=True,whole_integration_tree_CRE_claimed=False,existing_archives_unchanged=True,inputs_hashes_only_no_vendor_contents=True))
write(RUN/'validation.json',dict(schema='forge-c/integration24-publication-validation/1',status='SOURCE_FIX_ELIGIBLE_OFFLINE_REVIEW_ONLY',qualified_source=C,integration_source=I,decisions=decisions,final_private_affected_tests=dict(tests=185,failures=0,errors=0,skipped=0),design=14,legacy=16,packager=7,ruff='PASS',counting_limit='185 final private cases overlap earlier22/71/149/151 runs and214 remote149; do not sum repetitions or distinct CRE gate records as new product tests.',actual214_start='FAILED_UnboundLocalError_UNKNOWN_PRESERVED',actual887_bootstrap_or_cleanup='NOT_RUN_BY_COMPONENT_AGENT',role_competence='NOT_RUN',actual_product_phase_or_MISRA_acceptance='NOT_CLAIMED',permanent_reproducer_registration='NOT_CLAIMED_EXTERNAL_STAGED_ONLY',source_only_task_ticks=0,production_ACT=False,models_or_GPU_inference_by_component=0,publication_scope='New append-only sanitized evidence overlay and local integration source; root reviews/applies/commits. No push/main merge/runtime activation.'))
files=[dict(path=str(p.relative_to(OUT)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(OUT.rglob('*')) if p.is_file()]
q=O/'codex-integration24-qualified-index.json';write(q,dict(schema='forge-c/protected-publication-export-index/1',source=C,integration_source=I,exports=str(OUT),status='LOCAL_PREPARED_ROOT_REVIEW_REQUIRED',decisions=[x['decision_id'] for x in decisions],files=files,secret_line_header_scan_count=len(scanned),existing_archives_untouched=True))
print(json.dumps(dict(index=str(q),index_sha256=sha(q),files=len(files))))
