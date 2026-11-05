"""Append exact reviewed reproducer and private-cleanup QA evidence; no effects or source changes."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess
B=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c');O=B/'ops/scratch'
OLD=O/'codex-integration24-exports';OUT=O/'codex-integration24-exports-v2';WT=B/'repos/forge-c-014-integration24'
RUN=OUT/'evidence/v0.4/runs/CODEX-INTEGRATION24-20261105/reproducibility'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
patterns=[re.compile(rb'^\s*-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----\s*$'),re.compile(rb'^\s*(?:export\s+)?(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|FORGE_FABRO_TOKEN|FABRO_API_TOKEN|FORGE_LINE_AUTH_TOKEN)\s*=\s*\S+\s*$'),re.compile(rb'^\s*Authorization:\s*Bearer\s+\S+\s*$',re.I)]
def scan(raw,name):assert not [(i+1) for i,s in enumerate(raw.splitlines()) if any(p.fullmatch(s) for p in patterns)],name
def cp(a,z,h=None):
 assert a.is_file() and not a.is_symlink() and not z.exists()
 if h:assert sha(a)==h,a
 if a.suffix!='.bundle':scan(a.read_bytes(),str(a))
 z.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,z);assert sha(a)==sha(z)
def emit(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);raw=(json.dumps(v,indent=2,sort_keys=True)+'\n').encode();scan(raw,str(p))
 with p.open('xb') as f:f.write(raw)
assert not OUT.exists() and not (O/'codex-integration24-qualified-index-v2.json').exists()
original_index=O/'codex-integration24-qualified-index.json';assert sha(original_index)=='adfdcc83a24ece96c4027dac2e8d13017c616daa91d0c70b95fcf65e6e889b46';old=json.loads(original_index.read_text());assert len(old['files'])==814
for r in old['files']:cp(OLD/r['path'],OUT/r['path'],r['sha256'])
runner=O/'owner-profile-bootstrap-causal-fix-root-v1.py';cp(runner,RUN/'fix/owner-profile-bootstrap-causal-fix-root-v1.py','b2d6476004a94c28e787d899d59ea179800563f98f7b846049779e3386ea2d4f')
caller=B/'repos/forge-c-014-local-gen36';assert subprocess.check_output(['git','-C',str(caller),'rev-parse','HEAD'],text=True).strip()=='74e44a1f23b01f3200350436df1691249b441292'
cp(caller/'scripts/forge-env.sh',RUN/'fix/forge-env.sh')
cp(O/'owner-supervised-development-inputs-before-tests.json',RUN/'fix/caller-private-input-HASH-receipt.json')
command=dict(schema='forge-c/root-fix-reproduction-command/1',provenance='Root-confirmed source/arguments and frozen runner-enforced environment; shell layout below reconstructs the invocation rather than dumping the actual environment.',root_session=62129,terminal_exit_code=0,caller_revision='74e44a1f23b01f3200350436df1691249b441292',cwd=str(caller),shell_steps=['source scripts/forge-env.sh','export PYTHONPATH="$FORGE_REPO_ROOT/factory/python"','export FORGE_CRE_ISOLATION=bubblewrap','export FORGE_CPU_JOBS=1','unset FORGE_OWNER_DEVELOPMENT_RECORD FORGE_OWNER_DEVELOPMENT_SHA256'],argv=[str(B/'venv/bin/python'),str(runner),'--candidate-worktree',str(B/'repos/forge-c-014-owner-profile-bootstrap-v7'),'--candidate','887820300340dcc31a03f3dc46c31107e9aef9f3','--receipt-prefix','owner-profile-bootstrap-v7-normal-fix-root-r1'],staged_manifest=dict(path=str(O/'owner-bootstrap-cold-external-oracle/manifest.yaml'),sha256='ea6b4fac04f94d0f9bfef58fc7e6e5a9bf00246b57e5c97293b1017b31a785c3'),requirements=['Use an unchanged clean qualified caller and clean final candidate.','Provision all12 owner-supplied reference files with published hashes before any tests in caller/candidate/pooled baseline and candidate. No vendor text is distributed.','Preserve frozen protected manifests and scripts. The additional AFO reproducer remains external staged; no permanent registration is asserted.','Output prefixes are exclusive; a repeated evaluation requires a fresh audited prefix, not deletion or overwriting existing records.','Python environment must use the locked qualified dependencies and supported actual bubblewrap isolation. No model or production runtime is part of this command.'])
emit(RUN/'fix/command-and-required-environment.json',command)
cleanup=O/'owner-bootstrap-partial-cleanup-v2-review-20261105';ci_path=O/'owner-bootstrap-partial-cleanup-v2-review-index.json';ci=json.loads(ci_path.read_text());assert ci['private_controls']['PASS']==32 and ci['private_controls']['FAIL']==0
assert ci['helper']['sha256']=='6062de07287087f669ae52064f84ba7ddda4ed433e56b57db67d74912ca5df33'
expectation=cleanup/'exact-partial-expectation.json';expect=json.loads(expectation.read_text());assert sha(expectation)=='07bf5790f02faccbb68ada34fbff224e6515b81ddbb27348c52260bde2f75322'
# Inspect actual companion structure: full environment/argv and payload/text records are absent.
for item in expect['processes'].values():
 assert 'env_sha256' in item and 'argv_sha256' in item
 assert not any(k in item for k in ('environ','environment','env','argv','raw_argv','payload','prompt','response'))
def forbid_payload(x):
 if isinstance(x,dict):
  assert not set(x)&{'raw_environment','environ','payload','raw_payload','prompt','raw_prompt','response','raw_response','vendor_text','private_key'}
  for z in x.values():forbid_payload(z)
 elif isinstance(x,list):
  for z in x:forbid_payload(z)
forbid_payload(expect);scan(expectation.read_bytes(),str(expectation))
for r in ci['files']:
 p=Path(r['path']);assert p.parent==cleanup and sha(p)==r['sha256'];cp(p,RUN/'cleanup-v2'/p.name,r['sha256'])
cp(ci_path,RUN/'cleanup-v2/component-review-index.json')
cp(O/'owner-bootstrap-partial-cleanup-v2-root-review-r1.json',RUN/'cleanup-v2/root-independent-review.json')
emit(RUN/'cleanup-v2/child-readonly-review-extract.json',dict(provenance='Exact extract from frozen component index; no separate child test run or standalone report is fabricated.',component_index_sha256=sha(ci_path),independent_readonly_review=ci['independent_readonly_review']))
# Controls import only pure kernel/argv functions from this exact dependency; export source, not its private live companions.
v9=O/'owner-development-legacy-retirement-v9/retire-legacy-v9-DRAFT.py';cp(v9,RUN/'cleanup-v2/dependencies/retire-legacy-v9-DRAFT.py','54d75f613cce2c72fff4291f3cc0281d2419b1317e08871efa8ae21267aa95b5')
v1_path=O/'owner-bootstrap-partial-cleanup-v1-preserved-index.json';v1=json.loads(v1_path.read_text());cp(v1_path,RUN/'cleanup-v1-preserved/component-preserved-index.json')
for r in v1['files']:
 p=Path(r['path']);assert p.is_file() and sha(p)==r['sha256'];cp(p,RUN/'cleanup-v1-preserved'/p.name,r['sha256'])
report=json.loads((cleanup/'private-controls-r1.json').read_text());assert report['PASS']==32 and report['FAIL']==0 and report['all_private_handles_closed'] is True
emit(RUN/'cleanup-v2/scope-and-reproduction.json',dict(schema='forge-c/cleanup-private-control-publication/1',helper_sha256=ci['helper']['sha256'],expectation_sha256=sha(expectation),expectation_publication='EXACT_METADATA_ONLY_COMPANION_HASH_VERIFIED_NO_SANITIZED_HASH_SUBSTITUTION',expectation_contents='PID/start/boot/namespace/FD inode, process argv/environment HASHES ONLY, Intent/source/unit metadata, ledger/native HASHES ONLY; no environment bytes, credential, vendor text, request or model payload.',test_report=dict(PASS=32,FAIL=0,sha256=sha(cleanup/'private-controls-r1.json')),test_scope=report['fixture_overlays'],command=[str(B/'venv/bin/python'),str(cleanup/'check-private-controls.py')],command_provenance='Frozen script entrypoint supporting supplied actual raw report; original shell formatting is not claimed captured.',frozen_absolute_layout_dependencies=[dict(original=str(v9),published='dependencies/retire-legacy-v9-DRAFT.py',sha256=sha(v9)),dict(original=str(B/'repos/forge-c-014-owner-profile-bootstrap-v4'),source_revision='214c9668c605a5bad690820cb1f6601bf9ccb935',published_source='Source bundle in original I24 export, prerequisite dc27; owner inputs distributed as hashes only')],private_live_dependencies_not_exported=['Original private issuer/control/policy records and canonical runtime DB are intentionally not distributed. They are not necessary to run the harmless private32 controls but are required for any real cleanup.','Original v9 inactive-history live companion and other original VM artifacts are not part of a portable cleanup authorization.'],authority='Publication is reproducibility evidence only. Does not authorize real cleanup/start, create a guardian or claim native/model competence.',source_control_scripts_unchanged=True,actual_remote_cleanup_claimed=False))
text='''# Reproducibility addendum

This append-only addendum preserves the first 814-file I24 export unchanged. It adds the exact frozen independent full-FIX driver, its required command/environment, and the cleanup V2 helper, 32-case raw report/log, control script, child-review extract, root review, preservation proof and metadata-only companion. V1 controls, the original failed case and its blocking review are preserved separately.

The companion is exported byte-for-byte under its original SHA256. It contains process/environment/argv hashes, kernel and Intent metadata and history fingerprints; no raw environment, credential, vendor text or model request/response payload is present. The helper/control script hashes are not rewritten to claim portability. Their original absolute source/dependency paths are recorded, and the exact v9 pure-function source dependency is included. Reproduction needs those reviewed paths restored or a separately reviewed launcher adaptation; no new run is claimed here.

Owner-supplied private reference inputs are represented only by hashes. Real cleanup additionally depends on private original VM/issuer/control/database facts that are intentionally absent from this publication. The public private-fixture controls do not replace those facts or grant permission to execute the cleanup helper. The independent child review is an exact extract from its supplied frozen component index, not an invented separate test report.

The root-confirmed FIX process completed with all seven gates passing. This remains source eligibility for offline review. The 32 cleanup controls and 185 affected source tests have separate scopes; do not sum overlapping or different evidence populations into a product-acceptance total. No deployment, actual cleanup, model-role competence, production ACT, human review, certification or endurance acceptance is inferred.
'''
p=RUN/'README.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
cp(Path(__file__),RUN/'package-codex-integration24-repro-addendum.py')
for r in old['files']:assert sha(OLD/r['path'])==sha(OUT/r['path'])==r['sha256']
files=[dict(path=str(p.relative_to(OUT)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(OUT.rglob('*')) if p.is_file()]
index=O/'codex-integration24-qualified-index-v2.json';emit(index,dict(schema='forge-c/protected-publication-export-index/1',status='LOCAL_FROZEN_APPEND_ONLY_REPRODUCIBILITY_ADDITION_ROOT_REVIEW_REQUIRED',source='887820300340dcc31a03f3dc46c31107e9aef9f3',integration_source='2ec54d20f66fb908788a1cec97b1dc92a7488f18',exports=str(OUT),prior_index=dict(path=str(original_index),sha256=sha(original_index),files_preserved=814),files=files,new_files=len(files)-814,source_paths_unchanged=True,push_or_remote_effects=False))
# Apply only new paths to the unconsumed local I24 review worktree; preserve every old archive hash.
assert subprocess.check_output(['git','-C',str(WT),'rev-parse','HEAD'],text=True).strip()=='2ec54d20f66fb908788a1cec97b1dc92a7488f18'
added=[]
for r in files:
 p=WT/r['path'];src=OUT/r['path']
 if p.exists():assert sha(p)==r['sha256']
 else:p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,p);added.append(r['path'])
for r in old['files']:assert sha(WT/r['path'])==r['sha256']
receipt=O/'codex-integration24-repro-addendum-local-receipt.json';emit(receipt,dict(index_sha256=sha(index),old814_preserved=True,new_paths=added,existing_archives_overwritten=False,source_or_git_HEAD_changed=False,commit_or_push=False))
print(json.dumps(dict(index=str(index),index_sha256=sha(index),files=len(files),added=len(added),receipt_sha256=sha(receipt))))
