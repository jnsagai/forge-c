"""Append-only I25 evidence overlay; local preparation, no source changes, push or runtime effects."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,xml.etree.ElementTree as ET
B=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c');O=B/'ops/scratch'
OUT=O/'codex-integration25-exports';RUN=OUT/'evidence/v0.4/runs/CODEX-INTEGRATION25-20261105'
WT=B/'repos/forge-c-014-integration25';SRC=B/'repos/forge-c-014-line-service-boot-fencing-v3';QA=O/'line-service-boot-fencing-20261105'
BASE='99146ba27372737a8548205cf67458de0ac237a3';I='66d61cb1bb24f6db9a158cc9f040cf51c1517b71';C='8edd6a5657ff9c5f67b1c40c243532cb71d5bc69';PD='pd-f8860ecfd2e7a25ff728'
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
def copy(a,z):
 assert a.is_file() and not a.is_symlink() and not z.exists()
 raw=a.read_bytes()
 if a.suffix!='.bundle':scan(raw,str(a))
 z.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,z);assert sha(a)==sha(z)
def git(p,*args):return subprocess.check_output(['git','-C',str(p),*args],text=True).strip()
def ref(p):return dict(path=p.name,sha256=sha(p))
assert not OUT.exists() and not (O/'codex-integration25-qualified-index.json').exists()
assert git(WT,'rev-parse','HEAD')==I and not git(WT,'status','--porcelain')
assert git(SRC,'rev-parse','HEAD')==C and not git(SRC,'status','--porcelain')
paths=git(WT,'diff','--name-only',BASE,I).splitlines();assert len(paths)==5
source_rows=[]
for p in paths:
 assert (WT/p).read_bytes()==(SRC/p).read_bytes();source_rows.append(dict(path=p,sha256=sha(WT/p)))
inputs=json.loads((O/'codex-integration25-inputs-before-tests.json').read_text());assert inputs['integration_source']==I and inputs['all12_before_any_tests'] and len(inputs['files'])==12
for row in inputs['files']:assert sha(WT/row['path'])==row['sha256']
qualified=json.loads((QA/'qualified-index.json').read_text());assert qualified['candidate']==C and qualified['decision_id']==PD
component=json.loads((O/'line-service-boot-fencing-v3-exports/evidence/cre/protected-receipt-index.json').read_text());assert component['prevention_count']==175 and component['all_receipt_logs_hash_verified']
assert len(component['receipts'])==len({r['reproducer_id'] for r in component['receipts']})==175
for row in component['files']:
 p=O/'line-service-boot-fencing-v3-exports'/row['path'];assert sha(p)==row['sha256']
for p in sorted((O/'line-service-boot-fencing-v3-exports/evidence/cre').rglob('*')):
 if not p.is_file():continue
 relative=p.relative_to(O/'line-service-boot-fencing-v3-exports')
 target=(RUN/'independent-qualification/component-protected-receipt-index.json') if p.name=='protected-receipt-index.json' else OUT/relative
 copy(p,target)
for p in sorted(QA.rglob('*')):
 if not p.is_file():continue
 assert p.suffix in ('.log','.xml','.json','.py','.bundle')
 copy(p,RUN/'source-qa'/p.relative_to(QA))
for name in ('line-service-boot-fencing-v3-normal-change-20261105-decision.json','line-service-boot-fencing-v3-normal-change-20261105-worktrees-before-tests.json'):
 copy(O/name,RUN/'independent-qualification'/name)
for name in ('codex-integration25-inputs-before-tests.json','codex-integration25-design.log','codex-integration25-ruff.log'):
 copy(O/name,RUN/'root-review'/name)
copy(O/'package-codex-integration25.py',RUN/'package-codex-integration25.py')
d=json.loads((O/'line-service-boot-fencing-v3-normal-change-20261105-decision.json').read_text());assert d['decision_id']==PD and d['decision']=='ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result']=='PASS' or g['name']=='reproducer' and g['result']=='NOT_RUN' and g['reason_code']=='NOT_APPLICABLE_FOR_CHANGE' for g in d['hard_gates'])
suite=ET.parse(QA/'v3-affected.xml').getroot()[0];assert suite.attrib['tests']=='106' and suite.attrib['skipped']=='4' and suite.attrib['failures']==suite.attrib['errors']=='0'
skips=[dict(test=x.attrib['name'],reason=x.find('skipped').attrib['message'],status='NOT_RUN_HISTORICAL_REPLAY') for x in suite.findall('testcase') if x.find('skipped') is not None]
actual=json.loads((QA/'v3-systemd-private/report.json').read_text());assert actual['status']=='PASS' and len(actual['rows'])==4 and all(r['pass'] for r in actual['rows'])
write(RUN/'source-code-binding.json',dict(qualified_component=C,integration_source=I,published_base=BASE,source_paths=source_rows,all5_source_paths_byteidentical=True,unchanged_monitoring_changes_preserved=True,whole_integration_tree_CRE_claimed=False,existing_archives_unchanged=True,inputs_hashes_only_no_vendor_contents=True))
write(RUN/'validation.json',dict(schema='forge-c/integration25-publication-validation/1',status='LOCAL_SOURCE_QUALIFIED_COMPONENT_ROOT_REVIEW_ONLY',qualified_component=C,integration_source=I,decision_id=PD,component_CRE_baseline=d['baseline_revision'],evaluator=d['evaluator_id'],prevention=175,CHANGE_reproducer='NOT_APPLICABLE_FOR_CHANGE',affected=dict(tests=106,passed=102,failures=0,errors=0,skipped=4),skips=skips,local_disposable_systemd=dict(test_count=1,passed=1,outcome_rows=4,units=[r['unit'] for r in actual['rows'][::2]],scope=actual['scope'],production=False),component_design=14,component_ruff='4FILES_PASS',I25_design=14,I25_ruff='4FILES_PASS',legacy=16,packager=7,failures_and_prototypes='Preserved red/initial-green PROTOTYPE_NONIMMUTABLE plus frozenV2 lint failure; never relabeled as final passes.',counting_limit='Repeated source versions/CRE prevention/systemd rows are not additional product jobs or independent native competence.',source_task_checkbox_closure=False,installed_timer_CRE_recovery='NOT_RUN',Omniverse_boot_mount_dependency_faults='NOT_RUN',endurance_24_72_168h='NOT_RUN',signatures_policy_profiles_budgets='UNCHANGED',model_GPU_actions='NONE',publication_install='NONE_LOCAL_PREPARATION_ONLY',whole_I25_tree_CRE='NOT_CLAIMED_COMPONENT_BYTES_ONLY'))
# Check every destination before root applies the overlay: new paths only, no overwrite of existing archives.
files=[]
for p in sorted(OUT.rglob('*')):
 if not p.is_file():continue
 relative=p.relative_to(OUT);assert not (WT/relative).exists(),('EXISTING_ARCHIVE_OVERWRITE_REFUSED',relative)
 files.append(dict(path=str(relative),sha256=sha(p),bytes=p.stat().st_size))
write(O/'codex-integration25-qualified-index.json',dict(schema='forge-c/protected-publication-export-index/1',source=C,integration_source=I,published_base=BASE,exports=str(OUT),status='LOCAL_PREPARED_ROOT_REVIEW_REQUIRED',decisions=[PD],files=files,secret_line_header_scan_count=len(scanned),existing_archives_untouched=True))
print(json.dumps(dict(index=str(O/'codex-integration25-qualified-index.json'),index_sha256=sha(O/'codex-integration25-qualified-index.json'),files=len(files))))
