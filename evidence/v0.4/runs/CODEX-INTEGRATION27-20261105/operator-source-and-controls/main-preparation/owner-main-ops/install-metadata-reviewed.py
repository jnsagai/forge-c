"""Reviewed OS-operator metadata append only. Default is read-only; no runtime start."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

F=Path('/mnt/data/forge-c/swe1-fabro-20261031')
R=F/'qualification/owner-profile-bootstrap-f0c8fc5c-review-20261105'
S=R/'newS'
DATA=R/'development-inputs'
BINDING_SHA='576c8af67548e57efb1363c8f80f117600ac4c067ffa9dbe6d60782237ef9733'
SOURCE='f0c8fc5c8ae83952a05cea578d41e0ff06324afd'


def need(ok,code):
    if not ok: raise RuntimeError(code)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(p,*args):
    return subprocess.check_output(['git','-C',str(p),*args],text=True,timeout=60).strip()
def repo_view(p):
    q=Path(git(p,'rev-parse','--git-path','FETCH_HEAD'));q=q if q.is_absolute() else p/q
    return dict(head=git(p,'rev-parse','HEAD'),refs=git(p,'for-each-ref','--format=%(refname) %(objectname)'),status=git(p,'status','--porcelain'),fetch_head_sha256=sha(q) if q.is_file() else 'ABSENT')
def emit(p,v):
    with p.open('x') as f:
        os.fchmod(f.fileno(),0o600);json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno())


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--install-reviewed',action='store_true');x=a.parse_args()
    if not x.install_reviewed:
        print(json.dumps(dict(state='READONLY_PLAN',effects=False,source=SOURCE)));return
    need(__debug__,'PYTHON_OPTIMIZATION_REFUSED')
    need(Path(__file__).resolve().parent==R/'owner-main-ops','WRONG_HELPER_LOCATION')
    bp=Path(__file__).with_name('binding.json');need(sha(bp)==BINDING_SHA,'BINDING_CHANGED');b=json.loads(bp.read_text())
    need(not any(os.environ.get(k) for k in ('FORGE_AGENT_ROLE','FORGE_WORKSPACE','FORGE_POLICY_BINDING')),'EXTERNAL_OWNER_ONLY')
    need(git(S,'rev-parse','HEAD')==SOURCE and not git(S,'status','--porcelain'),'SOURCE_CHANGED')
    for name,h in b['files'].items():
        p=Path(name);need(p.is_file() and not p.is_symlink() and sha(p)==h,'METADATA_CHANGED:'+name)
    for row in b['inputs']+b['source_files']:need(sha(S/row['path'])==row['sha256'],'SOURCE_INPUT_CHANGED')
    need(not (DATA/'.git').exists(),'DATA_REPO_ALREADY_EXISTS_NO_REPLAY')
    out=R/'metadata-f0-reviewed';out.mkdir(mode=0o700,exist_ok=False)
    canonical=F/'repo';before=repo_view(canonical)
    emit(out/'intent.json',dict(state='APPEND_METADATA_ATTEMPT_NO_AUTOMATIC_REPLAY',source=SOURCE,canonical_before=before))
    # Import objects only; no branch, HEAD, index, working-tree or FETCH_HEAD writes in canonical repo.
    subprocess.run(['git','-C',str(canonical),'fetch','--no-tags','--no-write-fetch-head',str(S),SOURCE],check=True,timeout=60)
    need(git(canonical,'cat-file','-t',SOURCE)=='commit' and repo_view(canonical)==before,'CANONICAL_REPOSITORY_CHANGED')
    os.environ.update(FORGE_REPO_ROOT=str(S),FORGE_DATA_ROOT='/mnt/data/forge-c',FORGE_STATE_DIR=str(F/'lrtx/state'))
    sys.path.insert(0,str(S/'factory/python'))
    from forge_factory.afo import line_recovery_control as C
    from forge_factory.afo import owner_supervised_development as D
    from forge_factory.afo.durable import digest
    control=C.read(dict(path=str(DATA/'control/line-recovery-control.development.json'),sha256=sha(DATA/'control/line-recovery-control.development.json')))
    need(control['source_revision']==SOURCE and control['mission']['limits']['deadline']==1795057626,'CONTROL_SCOPE_CHANGED')
    installed=[]
    for ref in control['product_role_trials'].values():
        src=DATA/'trial-assets'/ref['path'];raw=src.read_bytes();need(digest(json.loads(raw))==ref['sha256'],'TRIAL_DIGEST_CHANGED')
        dest=F/'lrtx/state'/ref['path'];need(dest.parent.is_dir() and not dest.parent.is_symlink(),'CANONICAL_TRIAL_DIRECTORY_UNKNOWN')
        if dest.exists():need(not dest.is_symlink() and dest.read_bytes()==raw,'EXISTING_TRIAL_CONFLICT')
        else:
            with dest.open('xb') as f:
                os.fchmod(f.fileno(),0o444);f.write(raw);f.flush();os.fsync(f.fileno())
        installed.append(dict(path=str(dest),sha256=sha(dest),canonical_sha256=ref['sha256']))
    D._trial_envelopes(control)  # Real canonical immutable role lookup; never issues a guardian.
    # Only the campaign is committed; no policy, authorization, trial or code is declared owner-approved by this commit.
    subprocess.run(['git','-c','core.hooksPath=/dev/null','init',str(DATA)],check=True,timeout=30)
    subprocess.run(['git','-C',str(DATA),'add','--','campaigns/finite-crc-swe6-owner-development.yaml'],check=True,timeout=30)
    subprocess.run(['git','-C',str(DATA),'-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','-c','user.name=Codex operator review','-c','user.email=codex@localhost','commit','-m','Bind qualifiedf0c8fc5c finite owner-development campaign under existing owner directive'],check=True,timeout=30)
    from forge_factory.afo.line_campaign import parse
    campaign=parse(DATA/'campaigns/finite-crc-swe6-owner-development.yaml',require_approval=True)
    need(len(campaign.lineages)==1 and campaign.lineages[0].factory_revision==SOURCE,'CAMPAIGN_SOURCE_CHANGED')
    need(repo_view(canonical)==before,'CANONICAL_REPOSITORY_CHANGED')
    result=dict(state='METADATA_APPENDED_NO_RUNTIME_START',source=SOURCE,binding_sha256=BINDING_SHA,canonical_before=before,canonical_after=repo_view(canonical),trial_assets=installed,data_commit=git(DATA,'rev-parse','HEAD'),campaign_sha256=sha(DATA/'campaigns/finite-crc-swe6-owner-development.yaml'),guardian_issued=False,mission_or_queue_opened_or_changed=False,services_or_models_started=False)
    emit(out/'result.json',result);print(json.dumps(result))


if __name__=='__main__': main()
