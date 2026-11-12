"""One explicit operator start of qualifiedf0c8fc5c same-new-guardian bootstrap. Default read-only."""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
import time
from pathlib import Path

F=Path('/mnt/data/forge-c/swe1-fabro-20261031')
R=F/'qualification/owner-profile-bootstrap-f0c8fc5c-review-20261105'
S=R/'newS'
DATA=R/'development-inputs'
BINDING_SHA='576c8af67548e57efb1363c8f80f117600ac4c067ffa9dbe6d60782237ef9733'
SOURCE='f0c8fc5c8ae83952a05cea578d41e0ff06324afd'
UNIT='forge-c-owner-development-f0c8fc5c-20261105.service'
OLD_UNIT='forge-c-owner-development-88782030-20261105.service'
INTENT=Path('/home/omniverse2/.config/forge-c/line-local/operations-intent.json')
OLD_R=F/'qualification/owner-development-dc27abba-review-20261105'
RETIREMENT=OLD_R/'legacy-retirement-live-r1/outcome.json'
FAILED_R=F/'qualification/owner-profile-bootstrap-214c9668-review-20261105'
HARDENING=FAILED_R/'runtime-run-hardening/verified-result.json'
CLEANUP=F/'qualification/owner-profile-bootstrap-88782030-review-20261105/partial-reconciliation-642-f0-r1/verified-result.json'
PARENT=INTENT.parent/'owner-supervised-development'


def need(ok,code):
    if not ok:raise RuntimeError(code)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def git(p,*a):return subprocess.check_output(['git','-C',str(p),*a],text=True,timeout=30).strip()
def emit(p,v):
    with p.open('x') as f:
        os.fchmod(f.fileno(),0o600);json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno())
def unit_view(name):
    out=subprocess.check_output(['systemctl','--user','show',name,'--property=LoadState','--property=ActiveState','--property=MainPID','--property=InvocationID','--property=ExecMainStartTimestampMonotonic'],text=True,timeout=10)
    return dict(line.split('=',1) for line in out.splitlines() if '=' in line)
def checked_json(path,h):
    need(re.fullmatch('[0-9a-f]{64}',h or '') and path.is_file() and not path.is_symlink(),'BOUND_RECEIPT_MISSING')
    raw=path.read_bytes();need(hashlib.sha256(raw).hexdigest()==h,'BOUND_RECEIPT_CHANGED');return json.loads(raw)



def require_issuing_unit(view,pid,invocation):
    need(view.get('LoadState')=='loaded' and view.get('ActiveState') in ('active','activating')
         and view.get('MainPID')==str(pid) and view.get('InvocationID')==invocation,
         'ISSUING_UNIT_CHANGED_DURING_PUBLICATION_CHECK')

def require_publication_deadline(until):
    need(time.monotonic()<until,'GUARDIAN_PUBLICATION_TIMEOUT_NO_RETRY')

def observe_issuing_record(parent, pid, dbpath, D, baseline, source, control_sha, profile_sha):
    """Pending publication is not authentication. Caller pins unit PID/invocation.

    Only the new private file may be incomplete; old records are immutable.
    A complete file needs its exact canonical issuer row before normal D.current.
    """
    new=[]
    for path in parent.glob('*.json'):
        if not re.fullmatch('[0-9a-f]{64}.json',path.name):continue
        D._private(path)
        if str(path) in baseline:
            need(sha(path)==baseline[str(path)],'OLD_RECORD_CHANGED_DURING_STARTUP')
            continue
        new.append(path)
    need(len(new)<=1,'AMBIGUOUS_NEW_GUARDIAN_PUBLICATION')
    if not new:return None
    path=new[0]
    try:record=json.loads(path.read_bytes())
    except json.JSONDecodeError:return None
    need(record.get('guardian_pid')==pid and digest(record)==path.stem and sha(path)==path.stem,'NEW_RECORD_PID_OR_CONTENT_REBOUND')
    need(record.get('source_revisions')==[source] and record['control_ref']['sha256']==control_sha and record['profile_sha256']==profile_sha,'NEW_GUARDIAN_SCOPE_CHANGED')
    need(D.guardian_alive(record),'NEW_ISSUER_KERNEL_UNPROVEN')
    with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True,timeout=3) as db:
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        row=db.execute('SELECT record,sha256 FROM afo_independent_decisions WHERE decision_id=? AND kind=?',('owner-development-'+path.stem,D.MODE)).fetchone()
    if row is None:return None
    need(row[1]==path.stem and json.loads(row[0])==record,'NEW_ISSUER_CANONICAL_ROW_CHANGED')
    sock=Path(record['guardian_socket']);st=sock.stat()
    need(dict(device=st.st_dev,inode=st.st_ino)==record['guardian_socket_identity'],'NEW_ISSUER_SOCKET_REBOUND')
    os.environ.update({D.FILE:str(path),D.SHA:path.stem})
    try:live=D.current()
    except Exception as exc:
        if getattr(exc,'code',None)=='OWNER_DEVELOPMENT_GUARDIAN_ATTESTATION_UNAVAILABLE':return None
        raise
    need(live==record,'NEW_CURRENT_RECORD_CHANGED')
    return path,live

def verify_reconciled_chain(db, live, binding, evidence_ref):
    """Read only exact current pending failure -> current issuer -> consumed INTENT."""
    from forge_factory.afo import owner_bootstrap_reconciliation as Q

    current_sha=digest(live);old_id=binding['reconciliation']['old_intent_id']
    request=dict(intent_id=old_id,result_sha256=binding['reconciliation']['old_result_sha256'],evidence_ref=evidence_ref)
    ack_id=old_id+'-reconciliation-'+digest(dict(request=request,issuer=current_sha))
    ack=Q._row(db,ack_id,Q.KIND)
    need(ack.get('request')==request and ack.get('reconciler_record_sha256')==current_sha
         and ack.get('reconciler_source_revisions')==[SOURCE], 'APPENDED_CURRENT_RECONCILIATION_NOT_PROVEN')
    need(ack.get('bindings',{}).get('old_intent_sha256')==binding['reconciliation']['old_intent_sha256'], 'CURRENT_OLD_INTENT_REBOUND')
    reconciler,successor_id,successor=Q._chain(db,live,old_id,ack)
    need(reconciler==live and successor_id=='owner-profile-bootstrap-'+current_sha, 'RECONCILIATION_SUCCESSOR_CHANGED')
    token=dict(decision_id=ack_id,sha256=digest(ack))
    consumed=Q._row(db,successor_id+'-reconciliation-consumed',Q.CONSUMED_KIND)
    need(successor.get('schema')=='forge-c/owner-profile-bootstrap-intent/2'
         and successor.get('reconciliation_ref')==token
         and consumed==Q._consumption_value(old_id,token,current=live,successor_id=successor_id,successor=successor),
         'CURRENT_RECONCILIATION_NOT_DURABLY_CONSUMED')
    return dict(reconciliation_id=ack_id,reconciliation_sha256=digest(ack),consumed_sha256=digest(consumed),successor_intent_id=successor_id,successor_intent_sha256=digest(successor))


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--start-reviewed',action='store_true');a.add_argument('--ticket',type=Path)
    a.add_argument('--ticket-sha256');a.add_argument('--retirement-sha256');a.add_argument('--hardening-sha256')
    a.add_argument('--metadata-receipt-sha256');a.add_argument('--cleanup-result-sha256');a.add_argument('--reconciliation-evidence-sha256');a.add_argument('--readiness-seconds',type=int,default=660)
    x=a.parse_args()
    if not x.start_reviewed:
        print(json.dumps(dict(state='READONLY_PLAN',effects=False,unit=UNIT,source=SOURCE)));return
    need(__debug__,'PYTHON_OPTIMIZATION_REFUSED')
    need(Path(__file__).resolve().parent==R/'owner-main-ops','WRONG_HELPER_LOCATION')
    need(not any(os.environ.get(k) for k in ('FORGE_AGENT_ROLE','FORGE_WORKSPACE','FORGE_POLICY_BINDING','FORGE_OWNER_DEVELOPMENT_RECORD','FORGE_OWNER_DEVELOPMENT_SHA256','FORGE_LINE_STACK_PAYLOAD','FORGE_LINE_STACK_PAYLOAD_SHA256','FORGE_STACK_LOCK_FD')),'CLEAN_EXTERNAL_OPERATOR_PROCESS_REQUIRED')
    need(os.getuid()==1000 and Path('/proc/self/uid_map').read_text().split()==['0','0','4294967295'],'INITIAL_HOST_REQUIRED')
    b=checked_json(Path(__file__).with_name('binding.json'),BINDING_SHA)
    need(git(S,'rev-parse','HEAD')==SOURCE and not git(S,'status','--porcelain'),'SOURCE_CHANGED')
    for name,h in b['files'].items():
        p=Path(name);need(p.is_file() and not p.is_symlink() and sha(p)==h,'INPUT_CHANGED:'+name)
    for row in b['inputs']+b['source_files']:need(sha(S/row['path'])==row['sha256'],'SOURCE_INPUT_CHANGED')
    native=Path(b['native_binary']);need(not native.is_symlink() and sha(native)==b['native_binary_sha256'],'NATIVE_BINARY_CHANGED')
    outcome=checked_json(RETIREMENT,x.retirement_sha256)
    need(outcome.get('status')==b['retirement_required_status'] and outcome.get('no_model_start_or_dispatch') is True and outcome.get('mission_or_queue_or_native_history_changed') is False,'RETIREMENT_NOT_PROVEN_SUCCESS')
    hard=checked_json(HARDENING,x.hardening_sha256)
    need(hard.get('schema')=='forge-c/owner-runtime-run-hardening/1' and hard.get('status')=='RUN_DIRECTORY_GROUP_WRITE_REMOVED' and hard.get('path')==str(F/'lrtx/run') and hard.get('uid')==os.getuid() and hard.get('mode_before')=='0o2775' and hard.get('mode_after')=='0o2755' and hard.get('models')==0 and all(hard.get(k) is False for k in ('services_content_changed','intent_changed','history_changed')),'HARDENING_NOT_PROVEN')
    run=F/'lrtx/run';st=run.stat();need(run.is_dir() and not run.is_symlink() and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o2755,'RUN_DIRECTORY_NOT_HARDENED')
    meta=checked_json(R/'metadata-f0-reviewed/result.json',x.metadata_receipt_sha256)
    need(meta['state']=='METADATA_APPENDED_NO_RUNTIME_START' and meta['source']==SOURCE and meta['binding_sha256']==BINDING_SHA,'METADATA_NOT_INSTALLED')
    need(git(DATA,'rev-parse','HEAD')==meta['data_commit'],'DATA_COMMIT_CHANGED')
    old=unit_view(OLD_UNIT);need(old.get('ActiveState') in ('inactive','failed') and old.get('MainPID')=='0' and old.get('InvocationID') in ('','f9f540f7d0aa44378913a47f9d3d4997'),'OLD_FAILED_UNIT_NOT_QUIET')
    need(unit_view(UNIT).get('LoadState')=='not-found','NEW_UNIT_ALREADY_EXISTS_NO_REPLAY')
    os.environ.update(FORGE_REPO_ROOT=str(S),FORGE_DATA_ROOT='/mnt/data/forge-c',FORGE_STATE_DIR=str(F/'lrtx/state'),FORGE_OPERATIONS_INTENT=str(INTENT))
    sys.path.insert(0,str(S/'factory/python'))
    from forge_factory.afo import owner_supervised_development as D
    from forge_factory.lrtx.provider_process import identity
    from forge_factory.afo.line_campaign import parse
    c=parse(DATA/'campaigns/finite-crc-swe6-owner-development.yaml',require_approval=True)
    need(c.commit==meta['data_commit'] and len(c.lineages)==1 and c.lineages[0].factory_revision==SOURCE,'CAMPAIGN_NOT_APPROVED_EXACT')
    D._private(PARENT,directory=True)
    for path in PARENT.glob('*.json'):
        if re.fullmatch('[0-9a-f]{64}.json',path.name):
            record=json.loads(path.read_text())
            seen=identity(record['guardian_pid'])
            need(seen is None or seen['boot_id']!=record['guardian']['boot_id'] or seen['start_ticks']!=record['guardian']['start_ticks'] or seen['state']=='Z','OTHER_ORIGINAL_GUARDIAN_LIFETIME_LIVE')
    baseline_records={str(path):sha(path) for path in PARENT.glob('*.json') if re.fullmatch('[0-9a-f]{64}.json',path.name)}
    need(x.ticket is not None and x.ticket.resolve().parent==R/'owner-main-ops','FRESH_TICKET_LOCATION_REQUIRED')
    ticket=checked_json(x.ticket,x.ticket_sha256);D.validate_expiry_ticket(ticket,1795057626.0)
    cleanup=checked_json(CLEANUP,x.cleanup_result_sha256)
    need(cleanup['status']=='EXACT_PARTIAL_LIFETIMES_QUIET_HISTORY_CONSERVED' and cleanup['old_UNKNOWN_unchanged'] is True and cleanup['no_charge_or_history_reset'] is True,'PARTIAL_CLEANUP_NOT_PROVEN')
    ep=Path(b['reconciliation']['evidence_path']);D._private(ep.parent,directory=True);D._private(ep)
    evidence=checked_json(ep,x.reconciliation_evidence_sha256)
    need(cleanup['evidence_ref']==dict(path=str(ep),sha256=x.reconciliation_evidence_sha256) and evidence['old_intent_id']==b['reconciliation']['old_intent_id'] and evidence['old_intent_sha256']==b['reconciliation']['old_intent_sha256'] and evidence['old_result_sha256']==b['reconciliation']['old_result_sha256'] and evidence['next_source_revisions']==[SOURCE] and evidence['whole_stack_quiet'] is True and evidence['unknown_occupants']==[],'RECONCILIATION_BINDING_CHANGED')
    need(not(F/'lrtx/run/holder.pid').exists(),'PARTIAL_HOLDER_NOT_REMOVED')
    for item in evidence['lifetimes']:
        seen=identity(item['pid']);need(seen is None or seen['boot_id']!=item['boot_id'] or seen['start_ticks']!=item['start_ticks'] or seen['state']=='Z','PARTIAL_ORIGINAL_LIFETIME_STILL_LIVE')
    def evidence_fresh():
        need(0<=time.monotonic()-evidence['observed_monotonic']<=60 and 0<=time.clock_gettime(time.CLOCK_BOOTTIME)-evidence['observed_boottime']<=60,'RECONCILIATION_EVIDENCE_STALE')
    evidence_fresh()
    env=dict(FORGE_REPO_ROOT=str(S),PYTHONPATH=str(S/'factory/python'),FORGE_DATA_ROOT='/mnt/data/forge-c',FORGE_STATE_DIR=str(F/'lrtx/state'),FORGE_AFO_QUEUE_SCOPE='line-local',FORGE_DURABLE_AUTONOMY='1',FORGE_DURABLE_NATIVE_HEADER='1',FORGE_OPERATIONS_INTENT=str(INTENT),FORGE_OPERATIONS_PROFILE=b['profile'],FORGE_LRTX_ROOT=str(F/'lrtx'),FORGE_AFO_POLICY=str(DATA/'afo-policy.proposed.yaml'),FORGE_LINE_POLICY=str(DATA/'line-policy.proposed.yaml'),FORGE_LINE_LAUNCH_DIR=str(F),FORGE_LINE_STACK_ROOT=str(F/'lrtx'),FORGE_LINE_ID='local',FORGE_LINE_FABRO_URL='http://127.0.0.1:32397/api/v1',FORGE_LINE_FABRO_STORAGE=str(F/'lrtx/fabro/storage'),FORGE_FABRO_BIN=str(native),FORGE_LINE_FABRO_BIN=str(native),PATH=str(F/'lrtx/venv/bin')+':/usr/local/bin:/usr/bin:/bin')
    unset='FORGE_OWNER_DEVELOPMENT_RECORD FORGE_OWNER_DEVELOPMENT_SHA256 FORGE_AGENT_ROLE FORGE_WORKSPACE FORGE_POLICY_BINDING FORGE_LINE_STACK_PAYLOAD FORGE_LINE_STACK_PAYLOAD_SHA256 FORGE_STACK_LOCK_FD'
    command=['systemd-run','--user','--no-block','--unit='+UNIT,'--collect','--property=Type=exec','--property=Restart=no','--property=KillMode=process','--property=NoNewPrivileges=yes','--property=UMask=0077','--property=WorkingDirectory='+str(S),'--property=Description=Forge-C owner developmentf0c8fc5c same guardian managed bootstrap','--property=UnsetEnvironment='+unset,*['--setenv='+k+'='+v for k,v in env.items()],str(F/'lrtx/venv/bin/python'),'-m','forge_factory.afo.owner_supervised_development','--control',str(DATA/'control/line-recovery-control.development.json'),'--runtime-policy',str(DATA/'afo-policy.proposed.yaml'),'--line-policy',str(DATA/'line-policy.proposed.yaml'),'--campaigns',str(DATA/'campaigns'),'--expiry-ticket',str(x.ticket),'--interval','30','--bootstrap-managed-profile','--reconcile-bootstrap-intent',b['reconciliation']['old_intent_id'],'--reconcile-bootstrap-result-sha256',b['reconciliation']['old_result_sha256'],'--reconcile-bootstrap-evidence',str(ep),'--reconcile-bootstrap-evidence-sha256',x.reconciliation_evidence_sha256]
    need(30<=x.readiness_seconds<=900,'READINESS_BOUND_REQUIRED')
    marker=R/'owner-main-start-attempt-f0.json'
    D.validate_expiry_ticket(ticket,1795057626.0) # final small fresh issuance check after file/host reads
    emit(marker,dict(state='START_REQUEST_INTENT_POSSIBLE_EFFECTS_NO_REPLAY',source=SOURCE,unit=UNIT,binding_sha256=BINDING_SHA,ticket_sha256=x.ticket_sha256,command=command))
    try:
        from forge_factory.afo import operations
        need(operations.configured(),'OPERATIONS_INTENT_CONFIGURATION_REQUIRED')
        def request_start():
            D.validate_expiry_ticket(ticket,1795057626.0);evidence_fresh()
            return subprocess.run(command,capture_output=True,text=True,timeout=10)
        reply=operations.fenced_call(evidence['intent_epoch'],request_start)
        emit(R/'owner-main-systemd-request-f0.json',dict(returncode=reply.returncode,stdout=reply.stdout,stderr=reply.stderr))
        need(reply.returncode==0,'SYSTEMD_REQUEST_FAILED_NO_RETRY')
        until=time.monotonic()+x.readiness_seconds
        publishing_until=min(until,time.monotonic()+30)
        issuer_unit=None
        established=None
        while time.monotonic()<until:
            view=unit_view(UNIT);pid=int(view.get('MainPID','0'))
            if pid==0 and time.monotonic()<until-x.readiness_seconds+2:
                time.sleep(0.1);continue
            need(view.get('ActiveState') in ('active','activating') and pid>1,'MAIN_STOPPED_OR_FAILED_INSPECT_ONLY')
            identity_pair=(pid,view.get('InvocationID'))
            need(identity_pair[1] and (issuer_unit is None or identity_pair==issuer_unit),'ISSUING_UNIT_PID_OR_INVOCATION_CHANGED')
            issuer_unit=identity_pair
            if established is None:
                need(time.monotonic()<publishing_until,'GUARDIAN_PUBLICATION_TIMEOUT_NO_RETRY')
                found=observe_issuing_record(PARENT,pid,F/'lrtx/state/supervisor/line-queue.sqlite3',D,baseline_records,SOURCE,b['files'][str(DATA/'control/line-recovery-control.development.json')],b['profile_sha256'])
                require_issuing_unit(unit_view(UNIT),pid,issuer_unit[1])
                require_publication_deadline(publishing_until)
                if found is None:
                    time.sleep(0.1);continue
                established=found
            if established:
                path,record=established
                need(sha(path)==path.stem and digest(record)==path.stem,'ESTABLISHED_RECORD_CHANGED')
                os.environ.update({D.FILE:str(path),D.SHA:path.stem})
                live=D.current()  # No warm-up suppression after established authority.
                need(live==record,'ESTABLISHED_AUTHORITY_CHANGED')
                uri=(F/'lrtx/state/supervisor/line-queue.sqlite3').as_uri()+'?mode=ro'
                with sqlite3.connect(uri,uri=True,timeout=5) as db:
                    db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
                    from forge_factory.afo import owner_bootstrap_reconciliation as Q
                    result_id='owner-profile-bootstrap-'+digest(live)+'-result'
                    exists=db.execute('SELECT 1 FROM afo_independent_decisions WHERE decision_id=?',(result_id,)).fetchone()
                    result=Q._row(db,result_id,Q.RESULT_KIND) if exists else None
                    if result:
                        need(result['record_sha256']==digest(live) and result['status']=='READY','BOOTSTRAP_UNKNOWN_NO_RETRY')
                        chain=verify_reconciled_chain(db,live,b,dict(path=str(ep),sha256=x.reconciliation_evidence_sha256))
                if result:
                    need(unit_view(UNIT)==view and D.current()==live,'NEW_UNIT_OR_GUARDIAN_CHANGED')
                    ready=dict(state='NEW_MAIN_GUARDIAN_RECONCILED_BOOTSTRAP_READY_PLACING_SCOPE_UNACCEPTED',unit=UNIT,systemd=view,record_ref=dict(path=str(path),sha256=sha(path)),bootstrap_result=result,reconciliation_chain=chain,source=SOURCE,role_competence='NOT_ESTABLISHED_BY_STARTUP',native_or_product_progress='Inspect normal producer/Fabro separately; startup is not phase PASS',no_automatic_retry=True)
                    emit(R/'owner-main-readiness-f0.json',ready);print(json.dumps(ready));return
            time.sleep(1)
        raise RuntimeError('READINESS_OBSERVATION_TIMEOUT_WORKER_LEFT_INTACT')
    except BaseException as exc:
        emit(R/'owner-main-unknown-f0.json',dict(state='UNKNOWN_REQUIRES_RECONCILIATION',possible_effects=True,no_retry=True,no_rollback_or_stop=True,error_type=type(exc).__name__))
        raise


if __name__=='__main__':main()
