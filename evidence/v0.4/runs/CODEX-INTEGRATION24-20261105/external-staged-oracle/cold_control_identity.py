"""External staged public cold-control witness; own harmless CPU HTTP only."""
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

SIG='owner bootstrap cold control process cannot persist provider identity'


def main():
    from forge_factory.common import REPO_ROOT
    from forge_factory.lrtx import stack
    from forge_factory.lrtx import profile
    assert Path(stack.__file__).resolve()==REPO_ROOT/'factory/python/forge_factory/lrtx/stack.py'
    real_popen=subprocess.Popen
    processes=[]
    with tempfile.TemporaryDirectory(prefix='external-cold-control-') as temp:
        root=Path(temp)
        for name in ('run','logs','venv/bin','fabro/home','fabro/storage'):(root/name).mkdir(parents=True,exist_ok=True)
        (root/'venv/bin/python').symlink_to(sys.executable)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        binary=root/'private-cpu-fabro'
        binary.write_text('#!'+sys.executable+'\nimport os\nfrom http.server import BaseHTTPRequestHandler,HTTPServer\nfrom urllib.parse import urlsplit\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200);self.end_headers();self.wfile.write(b"PRIVATE_CPU_ONLY")\n def log_message(self,*a):pass\nHTTPServer(("127.0.0.1",urlsplit(os.environ["FORGE_FABRO_URL"]).port),H).serve_forever()\n')
        binary.chmod(0o700)
        prof=profile.load('local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104')
        settings=dict(root=root,profile=prof,ports={**prof['deployment']['ports'],'fabro':port})
        os.environ.update(FORGE_FABRO_BIN=str(binary),FORGE_DURABLE_AUTONOMY='1',FORGE_OPERATIONS_INTENT=str(root/'private-intent-not-production'))
        # Namespace entry and model-spec construction are explicit physical leaves.
        # Actual _start/_in_ns/Popen/probe/identity/persistence are unmodified.
        stack._nsenter=lambda _:[]
        stack.llama_server_spec=lambda *_:None
        stack.cloud_bridge=lambda _:None
        def tracked(argv,*args,**kwargs):
            if argv[:2]==['setsid','unshare']:
                p=real_popen(['sleep','infinity'],*args,**kwargs)
                (root/'run/holder.pid').write_text(str(p.pid))
            else:p=real_popen(argv,*args,**kwargs)
            processes.append(p);return p
        subprocess.Popen=tracked
        def guard():pass
        guard.bootstrap_binding=dict(intent_id='PRIVATE_EXTERNAL_FIXTURE',record_sha256='a'*64,control_ref={})
        present=False
        try:
            try:
                with stack.line_effect_guard(guard):result=stack._start(settings,recovery=True,control_only=True)
            except UnboundLocalError as exc:
                if "provider" not in str(exc):raise
                present=True
            if not present:
                saved=json.loads((root/'run/services.json').read_text())
                assert set(saved['processes'])=={'fabro'} and result['health']['fabro'] is True
                entry=saved['processes']['fabro']
                assert entry['identity']==stack.process_identity(entry['pid'])
                from forge_factory.lrtx.provider_process import owner_view
                assert entry['owner_view']==owner_view(entry['pid'])
                assert saved['owner_bootstrap_binding']==guard.bootstrap_binding
                assert not (root/'state/conductor/conductor.sqlite3').exists()
        finally:
            subprocess.Popen=real_popen
            for p in reversed(processes):
                if p.poll() is None:p.terminate()
                p.wait(timeout=5)
        print('SYMPTOM_PRESENT:'+SIG if present else 'SYMPTOM_ABSENT')
        return 1 if present else 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print('REPRODUCER_ERROR:'+type(exc).__name__)
        raise SystemExit(2)
