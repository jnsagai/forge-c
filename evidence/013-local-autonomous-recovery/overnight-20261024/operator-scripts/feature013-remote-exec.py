#!/usr/bin/python3
import os,sys,subprocess
repo='/home/omniverse2/forge-c-remote/repos/forge-c-autonomy-36ed0fc'
root='/mnt/data/forge-c/lrtx-v2/state/operator-runs/feature013-v4'
py='/mnt/data/forge-c/venv/bin/python'
env=os.environ.copy()
env.update(FORGE_REPO_ROOT=repo,PYTHONPATH=repo+'/factory/python',FORGE_DATA_ROOT='/mnt/data/forge-c',FORGE_LRTX_PROFILE='local-rtx-v2-omniverse2',FORGE_FABRO_BIN='/mnt/data/forge-c/fabro-0.362.0/fabro-x86_64-unknown-linux-musl/fabro')
inner=['/usr/bin/env','FORGE_AFO_POLICY='+root+'/afo-policy.yaml','FORGE_AFO_AUTH_DIR='+root+'/authorizations','FORGE_AFO_ALLOWED_SIGNERS='+root+'/allowed-signers','FORGE_CRE_ISOLATION=bubblewrap','FORGE_CPU_JOBS=16']
if env.get('NOTIFY_SOCKET'):inner.append('NOTIFY_SOCKET='+env['NOTIFY_SOCKET'])
cmd=[py,'-m','forge_factory.lrtx.stack','exec','--']+inner+[py]+sys.argv[1:]
sys.exit(subprocess.call(cmd,cwd=repo+'/factory/python',env=env))
