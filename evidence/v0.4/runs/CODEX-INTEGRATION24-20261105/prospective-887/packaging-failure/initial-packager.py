"""Append only root-whitelisted887 CPU/kernel/STUB proof. Never transfers or runs it."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,tarfile,xml.etree.ElementTree as ET
B=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c');O=B/'ops/scratch'
OLD=O/'codex-integration24-exports-v2';OUT=O/'codex-integration24-exports-v3';WT=B/'repos/forge-c-014-integration24'
RUN=OUT/'evidence/v0.4/runs/CODEX-INTEGRATION24-20261105/prospective-887'
C='887820300340dcc31a03f3dc46c31107e9aef9f3';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
patterns=[re.compile(rb'^\s*-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----\s*$'),re.compile(rb'^\s*(?:export\s+)?(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|FORGE_FABRO_TOKEN|FABRO_API_TOKEN|FORGE_LINE_AUTH_TOKEN)\s*=\s*\S+\s*$'),re.compile(rb'^\s*Authorization:\s*Bearer\s+\S+\s*$',re.I)]
def scan(raw,label):assert not [(i+1) for i,s in enumerate(raw.splitlines()) if any(p.fullmatch(s) for p in patterns)],label
def cp(a,z,h=None):
 assert a.is_file() and not a.is_symlink() and not z.exists()
 if h:assert sha(a)==h,a
 if a.suffix!='.bundle':scan(a.read_bytes(),str(a))
 z.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,z);assert sha(a)==sha(z)
def emit(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);raw=(json.dumps(v,indent=2,sort_keys=True)+'\n').encode();scan(raw,str(p))
 with p.open('xb') as f:f.write(raw)
assert not OUT.exists() and not (O/'codex-integration24-qualified-index-v3.json').exists()
oldpath=O/'codex-integration24-qualified-index-v2.json';assert sha(oldpath)=='34471d8d43ae9c9b2e317fec1abcbba008db688dc114aed753de55b5c9a12435';old=json.loads(oldpath.read_text());assert len(old['files'])==841
for row in old['files']:cp(OLD/row['path'],OUT/row['path'],row['sha256'])
reviewpath=O/'owner-profile-bootstrap-887-export-root-verification-r1.json';assert sha(reviewpath)=='b0d2be6bd954556920b3ec5589970f8d118277d331d4b28ae2ba5c5b60eadbf9';review=json.loads(reviewpath.read_text());assert review['source']==C and review['all7member_hashes_verified'] and review['native_fixture_terminal_and_own_server_stopped'] and review['model_calls']==0 and review['actual_driver_jobs_started']==0
archive=O/'owner-profile-bootstrap-887-actual-prospective-proof.tar';assert sha(archive)==review['archive_sha256']=='755f7bc43c046c8a9b72c4ebdf245aa9e37b1c1747e8d9f76defb3d350f0c77c'
allowed={'staging-receipt.json','probe-summary.json','bootstrap-affected-controls.xml','bootstrap-affected-controls.stdout.log','cpu-preflight/preflight.json','native-header/measurement.json','prospective-proof-export-index.json'}
with tarfile.open(archive) as t:
 members=t.getmembers();assert len(members)==7 and {m.name for m in members}==allowed and all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
 raw={m.name:t.extractfile(m).read() for m in members}
pi=json.loads(raw['prospective-proof-export-index.json']);assert hashlib.sha256(raw['prospective-proof-export-index.json']).hexdigest()==review['index_sha256']=='f79e90f15928d3fbe6d6103819ca4224382917ecd446dc9b0b8c01f43dc8d52f'
assert pi['source']==C and len(pi['files'])==6 and pi['credentials_prompts_vendor_contents_exported'] is False
for row in pi['files']:assert hashlib.sha256(raw[row['path']]).hexdigest()==row['sha256'] and len(raw[row['path']])==row['bytes']
tests=list(ET.fromstring(raw['bootstrap-affected-controls.xml']).iter('testcase'));assert len(tests)==185 and not any(list(t.iter(k)) for t in tests for k in ('failure','error','skipped'))
measurement=json.loads(raw['native-header/measurement.json']);assert measurement['source_revision']==C and measurement['verdict']=='PASS' and measurement['fixture_terminal_confirmed'] and measurement['own_server_stopped'] and measurement['production_mutations'] is False and measurement['native_run_id']=='01M6PKR21GZG3Y4WK1QG362MM1' and hashlib.sha256(raw['native-header/measurement.json']).hexdigest()==review['measurement_sha256']=='de7a39c7c637ee3717410fbb0933a16d1aae8c3c5ef4e1ecc25dd2c3da39a9da'
stage=json.loads(raw['staging-receipt.json']);probe=json.loads(raw['probe-summary.json']);cpu=json.loads(raw['cpu-preflight/preflight.json']);assert stage['source']==C and stage['all12_inputs_before_any_tests'] and stage['prior_repository_guardian_intent_unchanged'];assert probe['source']==C and probe['status']=='PASS_PROSPECTIVE_ONLY' and probe['actual_model_calls']==0 and probe['production_mutations'] is False and probe['prior_repository_guardian_intent_unchanged'];assert cpu['verdict']=='PASS_PROSPECTIVE_ONLY'
for name,data in raw.items():
 scan(data,name);p=RUN/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(data)
for n in ['owner-profile-bootstrap-887-export-root-verification-r1.json','owner-profile-bootstrap-887-actual-stage-r1.json','owner-profile-bootstrap-887-actual-private-probes-r1.json','owner-profile-bootstrap-887-actual-transfer-r1.json']:
 cp(O/n,RUN/'root-receipts'/n)
emit(RUN/'scope-and-binding.json',dict(schema='forge-c/integration24-prospective887-validation/1',source=C,archive_hash_only_no_tar_published=sha(archive),member_count=7,all_member_hashes_verified=True,affected=dict(tests=185,failures=0,errors=0,skipped=0),cpu_preflight='PASS_PROSPECTIVE_ONLY',native_stub=dict(run_id=measurement['native_run_id'],binary_version=measurement['binary_version'],binary_sha256=measurement['binary_sha256'],terminal_status=measurement['terminal_status'],own_server_stopped=True,measurement_sha256=review['measurement_sha256'],scope='TRANSPORT_ONLY_DETERMINISTIC_STUB_NO_ROLE_QUALIFICATION'),current_loaded_models_or_actual_role_competence='NOT_VERIFIED_BY_THIS_PROOF',actual_cleanup_or_new_canonical_guardian_or_driver_jobs='NOT_STARTED_BY_THIS_PROOF',actual_model_inference_calls=0,private_state_and_namespace_only=True,prior_repositories_guardian_intent_preserved=True,overlap='Remote185 is a repetition of final local185 controls on Omniverse; do not sum them as370 distinct cases.',source_only_task_ticks=0,production_ACT=False,exclusions=['Private input/transport archives','Vendor reference contents','Server environment/auth/credentials','Whole private Fabro tree','Raw model prompts/responses','Existing failed214 UNKNOWN remains unchanged; no repair verdict inherited']))
text='''# Actual Omniverse prospective proof for corrected source887

This separate append-only path contains exactly the seven root-whitelisted proof members and the root stage/probe/transfer/export receipts. The private tar itself is excluded. All member hashes were independently rechecked, including the actual 185-case XML with no failures, errors or skips and the new source-bound Fabro0.362 deterministic STUB measurement.

The private CPU/compiler/backend preflight passed. The own native STUB run completed and its own server stopped. The repositories, historical guardian facts and Intent were preserved. These checks ran in the separate prospective namespace and made no actual model inference calls, issued no new canonical guardian, started no driver job and performed no real cleanup.

The remote185 controls repeat the final local185 case population on Omniverse; they are not370 distinct tests. A successful deterministic transport STUB does not demonstrate Ornith/Qwen role competence, GPU allocation, product phase acceptance or endurance. Existing source214 failure and UNKNOWN evidence remains unchanged in the earlier archive. Publication does not activate corrected source887 or change production authority, history or human review status.
'''
p=RUN/'README.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
cp(Path(__file__),RUN/'package-codex-integration24-prospective887-addendum.py')
for row in old['files']:assert sha(OLD/row['path'])==sha(OUT/row['path'])==row['sha256']
files=[dict(path=str(p.relative_to(OUT)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(OUT.rglob('*')) if p.is_file()]
q=O/'codex-integration24-qualified-index-v3.json';emit(q,dict(schema='forge-c/protected-publication-export-index/1',status='LOCAL_FROZEN_APPEND_ONLY_887_PROSPECTIVE_ADDITION_ROOT_REVIEW_REQUIRED',source=C,integration_source='2ec54d20f66fb908788a1cec97b1dc92a7488f18',exports=str(OUT),prior_index=dict(path=str(oldpath),sha256=sha(oldpath),files_preserved=841),files=files,new_files=len(files)-841,source_or_authority_or_runtime_changed=False,push=False))
assert subprocess.check_output(['git','-C',str(WT),'rev-parse','HEAD'],text=True).strip()=='2ec54d20f66fb908788a1cec97b1dc92a7488f18'
new=[]
for row in files:
 src=OUT/row['path'];p=WT/row['path']
 if p.exists():assert sha(p)==row['sha256']
 else:p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,p);new.append(row['path'])
for row in old['files']:assert sha(WT/row['path'])==row['sha256']
src=B/'repos/forge-c-014-owner-profile-bootstrap-v7';paths=subprocess.check_output(['git','-C',str(src),'diff','--name-only','dc27abba601e5f6713f30e6027cb0bbd64241528',C],text=True).splitlines();assert len(paths)==11 and all((WT/n).read_bytes()==(src/n).read_bytes() for n in paths)
receipt=O/'codex-integration24-prospective887-local-overlay-receipt.json';emit(receipt,dict(index_v3_sha256=sha(q),all841_oldfiles_unchanged=True,new_paths=new,all11_source_files_byteidentical_to_qualified887=True,source_HEAD_unchanged=True,commit_or_push=False,remote_effects=False))
print(json.dumps(dict(index=str(q),index_sha256=sha(q),files=len(files),added=len(new),receipt_sha256=sha(receipt))))
