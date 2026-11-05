"""Private real namespace/capture/_in_ns witness. No models, GPU or canonical state."""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def need(ok,code):
    if not ok:raise RuntimeError(code)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def ns(pid):return {name:os.readlink(f'/proc/{pid}/ns/{name}') for name in ('user','net','mnt','pid')}


def main():
    a=argparse.ArgumentParser();a.add_argument('--source',type=Path,required=True);a.add_argument('--output',type=Path,required=True);x=a.parse_args()
    need(not any(os.environ.get(k) for k in ('FORGE_AGENT_ROLE','FORGE_WORKSPACE','FORGE_POLICY_BINDING','FORGE_OWNER_DEVELOPMENT_RECORD','FORGE_OWNER_DEVELOPMENT_SHA256')),'CLEAN_ENGINEERING_CALLER_REQUIRED')
    src=x.source.resolve();out=x.output.resolve();out.mkdir(mode=0o700,exist_ok=False)
    os.environ['FORGE_REPO_ROOT']=str(src);sys.path.insert(0,str(src/'factory/python'))
    from forge_factory.lrtx import stack,provider_process as P,pidfd
    need(Path(stack.__file__).resolve()==src/'factory/python/forge_factory/lrtx/stack.py','SOURCE_IMPORT_MISMATCH')
    need(Path(P.__file__).resolve()==src/'factory/python/forge_factory/lrtx/provider_process.py','CAPTURE_IMPORT_MISMATCH')
    revision=subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
    env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1'}
    children=[];instances=[];outer_child=None;rows=[]
    report=dict(schema='forge-c/private-namespace-entry-causal/1',source=revision,stack_module=str(Path(stack.__file__).resolve()),stack_sha256=sha(Path(stack.__file__)),capture_module=str(Path(P.__file__).resolve()),capture_sha256=sha(Path(P.__file__)),actual_model_calls=0,canonical_mutations=False,results=rows)
    backend=out/'report_namespaces.py'
    backend.write_text("import json,os,sys\nfrom pathlib import Path\np=Path('/proc/self')\nv={k:os.readlink(p/'ns'/k) for k in ['user','net','mnt','pid']}\nv.update(uid=os.getuid(),pid_local=os.getpid(),uid_map=Path('/proc/self/uid_map').read_text())\nPath(sys.argv[1]).write_text(json.dumps(v))\n")
    def collect(name,command):
        log=out/(name+'.log')
        with log.open('wb') as f:p=subprocess.Popen(command,env=env,stdout=f,stderr=subprocess.STDOUT,cwd=out,start_new_session=True)
        children.append(p);return p
    def wait_capture(p,name):
        until=time.monotonic()+5
        while time.monotonic()<until:
            need(p.poll() is None,'PRIVATE_PROVIDER_EARLY_EXIT:'+name)
            try:
                rec=P.capture(out,profile='private-kernel-entry-only',profile_sha256='a'*64,parent_pid=p.pid)
                P.validate(rec);instances.append((p,rec));return rec
            except Exception:
                time.sleep(.02)
        raise RuntimeError('PRIVATE_PROVIDER_CAPTURE_UNAVAILABLE:'+name)
    def own_signal(pid,sig):
        descriptor=pidfd.open_pid(pid)
        try:pidfd.send_signal(descriptor,sig)
        finally:os.close(descriptor)
    def run_case(name,call,expected):
        path=out/(name+'.json');log=out/(name+'.log')
        p=call(path,log);children.append(p);rc=p.wait(timeout=6)
        observed=json.loads(path.read_text()) if path.exists() else None
        text=log.read_text(errors='replace')
        value=dict(name=name,returncode=rc,observed=observed,expected=expected,log_sha256=sha(log),errno_hint='EPERM' if 'Operation not permitted' in text else 'EINVAL' if 'Invalid argument' in text else None)
        rows.append(value)
        if rc==0:need(observed is not None and all(observed[k]==v for k,v in expected.items()),'WRONG_NAMESPACE:'+name)
        return value
    try:
        outer=collect('outer-holder',['unshare','--user','--map-root-user','--net','--fork','sleep','infinity'])
        until=time.monotonic()+5
        while time.monotonic()<until:
            need(outer.poll() is None,'PRIVATE_OUTER_SETUP_FAILED')
            kids=Path(f'/proc/{outer.pid}/task/{outer.pid}/children').read_text().split()
            if kids:outer_child=int(kids[0]);break
            time.sleep(.02)
        need(outer_child is not None,'PRIVATE_OUTER_CHILD_MISSING')
        holder=outer_child;outer_ns=ns(holder);need(outer_ns['net']!=ns(os.getpid())['net'],'OUTER_NETWORK_NOT_PRIVATE')
        report['outer_holder']=dict(pid=holder,identity=P.identity(holder),namespaces=outer_ns,owner_view=P.owner_view(holder))
        def launch_provider(name,nested):
            if nested:
                command=['bwrap','--bind','/','/','--dev-bind','/dev','/dev','--unshare-user','--unshare-pid','--as-pid-1','--new-session','--die-with-parent','--proc','/proc','--','sleep','infinity']
            else:command=['unshare','--mount','--pid','--fork','--mount-proc','sleep','infinity']
            p=stack._in_ns(holder,command,env,out/(name+'-setup.log'),out)
            children.append(p);rec=wait_capture(p,name);info=ns(rec['init_pid'])
            need(info['net']==outer_ns['net'],'PROVIDER_DID_NOT_INHERIT_OUTER_NET')
            need((info['user']!=outer_ns['user'])==nested,'PROVIDER_USER_TOPOLOGY_MISMATCH')
            report[name]=dict(instance=rec,namespaces=info)
            return rec,info
        nested,nested_ns=launch_provider('nested-user-provider',True)
        same,same_ns=launch_provider('same-user-provider',False)
        def ordered(target,path,log,force_inner_user=False):
            inner=['nsenter','-t',str(target['init_pid'])]
            if force_inner_user or ns(target['init_pid'])['user']!=outer_ns['user']:inner+=['-U']
            inner+=['-m','-p','--preserve-credentials',sys.executable,str(backend),str(path)]
            with log.open('wb') as f:return subprocess.Popen(['nsenter','-t',str(holder),'-U','-n','--preserve-credentials',*inner],env=env,stdout=f,stderr=subprocess.STDOUT,cwd=out,start_new_session=True)
        control_nested=run_case('ordered-nested-control',lambda p,l:ordered(nested,p,l),nested_ns)
        need(control_nested['returncode']==0,'ORDERED_NESTED_CONTROL_FAILED')
        control_same=run_case('ordered-same-user-skip-control',lambda p,l:ordered(same,p,l),same_ns)
        need(control_same['returncode']==0,'ORDERED_SAME_USER_CONTROL_FAILED')
        same_bad=run_case('ordered-same-user-reentry-negative',lambda p,l:ordered(same,p,l,True),same_ns)
        need(same_bad['returncode']!=0 and same_bad['errno_hint']=='EINVAL','SAME_USER_REENTRY_NOT_REFUTED')
        nested_source=run_case('source-nested-provider',lambda p,l:stack._in_ns(holder,[sys.executable,str(backend),str(p)],env,l,out,serving=nested),nested_ns)
        same_source=run_case('source-same-user-provider',lambda p,l:stack._in_ns(holder,[sys.executable,str(backend),str(p)],env,l,out,serving=same),same_ns)
        normal_source=run_case('source-normal-outer',lambda p,l:stack._in_ns(holder,[sys.executable,str(backend),str(p)],env,l,out),{k:outer_ns[k] for k in ('user','net')})
        # Invoke actual source _in_ns from a process already in the outer USER/NET.
        inner_script=out/'same_current_user_source.py'
        inner_script.write_text("import os,sys\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1]+'/factory/python');os.environ['FORGE_REPO_ROOT']=sys.argv[1]\nfrom forge_factory.lrtx import stack\np=stack._in_ns(int(sys.argv[2]),[sys.executable,sys.argv[3],sys.argv[4]],dict(os.environ),Path(sys.argv[5]),Path(sys.argv[6]));raise SystemExit(p.wait(timeout=5))\n")
        same_current=run_case('source-normal-same-current-user',lambda p,l:collect('source-normal-same-current-user-launch',['nsenter','-t',str(holder),'-U','-n','--preserve-credentials',sys.executable,str(inner_script),str(src),str(holder),str(backend),str(p),str(l),str(out)]),{k:outer_ns[k] for k in ('user','net')})
        report['symptom_present']=nested_source['returncode']!=0 and nested_source['errno_hint']=='EPERM'
        report['same_current_user_source_failure']=same_current['returncode']!=0
        report['verdict']='BASELINE_SYMPTOM_PRESENT' if report['symptom_present'] else 'SOURCE_ENTRY_SUCCEEDED' if all(v['returncode']==0 for v in [nested_source,same_source,normal_source,same_current]) else 'OTHER_SOURCE_FAILURE'
    except BaseException as exc:
        report.update(verdict='PROBE_ERROR',error_type=type(exc).__name__,error_message=str(exc)[:400])
    finally:
        cleanup=[]
        for p,rec in reversed(instances):
            try:
                proof=P.stop(rec,fenced_effect=lambda effect:effect());need(proof is not None,'OWN_PROVIDER_QUIESCENCE_UNKNOWN');p.wait(timeout=5)
                cleanup.append(dict(init_pid=rec['init_pid'],quiet=proof['kind']))
            except Exception as exc:cleanup.append(dict(error_type=type(exc).__name__,init_pid=rec['init_pid']))
        if outer_child is not None:
            try:
                if P.identity(outer_child) is not None:own_signal(outer_child,signal.SIGKILL)
            except ProcessLookupError:pass
        for p in reversed(children):
            if p.poll() is None:
                # Only own freshly created process/session group, never a named host service.
                need(os.getpgid(p.pid)==p.pid,'OWN_SESSION_REBOUND')
                os.killpg(p.pid,signal.SIGKILL)
            p.wait(timeout=5)
        report['cleanup']=cleanup;report['own_process_handles_closed']=all(p.poll() is not None for p in children)
        save(out/'report.json',report)
    print(json.dumps(dict(verdict=report['verdict'],results=[{k:v for k,v in r.items() if k in ('name','returncode','errno_hint')}for r in rows],all_handles_closed=report['own_process_handles_closed'])))
    return 0 if report['verdict'] in ('BASELINE_SYMPTOM_PRESENT','SOURCE_ENTRY_SUCCEEDED') else 2


if __name__=='__main__':raise SystemExit(main())
