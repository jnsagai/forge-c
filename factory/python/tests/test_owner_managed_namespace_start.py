"""Real managed startup and kernel namespaces; only backend executables are CPU health fixtures.

No model/GPU/native execution, production services or whole-start replacement.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused
from forge_factory.lrtx import pidfd, stack
from forge_factory.lrtx import provider_process as P
from test_owner_profile_bootstrap import boot  # noqa:F401
from test_owner_supervised_development import supervised  # noqa:F401

REAL_START, REAL_SERVING = stack._start, stack.serving_instance

CPU_HEALTH = '''import os,sys,json
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlsplit
from pathlib import Path
port=int(sys.argv[1]) if len(sys.argv)>1 and sys.argv[1].isdigit() else (urlsplit(os.environ['FORGE_FABRO_URL']).port if 'fabro' in sys.argv[0] else int(os.environ['OLLAMA_HOST'].rsplit(':',1)[1]))
alias=sys.argv[sys.argv.index('--alias')+1] if '--alias' in sys.argv else 'PRIVATE-HEALTH-ONLY'
class Health(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'ok':True,'data':[{'id':alias}]}).encode())
 def do_POST(self):
  raise AssertionError('NO_INFERENCE_REQUESTS_ALLOWED')
 def log_message(self,*args):pass
Path(os.environ['FORGE_LRTX_ROOT'],'private-cpu-'+str(port)+'.json').write_text(json.dumps({n:os.readlink('/proc/self/ns/'+n) for n in ['user','net','pid','mnt']}))
HTTPServer(('127.0.0.1',port),Health).serve_forever()
'''


@pytest.fixture
def managed_cpu(boot, monkeypatch):  # noqa:F811
    root = boot["root"]
    (root / "logs").mkdir()
    # Reuse the actual pinned TEST venv, including pyvenv.cfg/site-packages.
    # A lone Python symlink resolves to the base interpreter and loses httpx.
    (root / "venv").symlink_to(Path(sys.prefix), target_is_directory=True)
    (root / "ollama-0.34.0/bin").mkdir(parents=True)
    fabro = root / "private-fabro-health"
    ollama = root / "ollama-0.34.0/bin/ollama"
    llama = root / "private-llama-server-health.py"
    for path in (fabro, ollama, llama):
        path.write_text("#!" + sys.executable + "\n" + CPU_HEALTH)
        path.chmod(0o700)
    monkeypatch.setenv("FORGE_FABRO_BIN", str(fabro))
    settings = stack.settings(D.PROFILE)
    # New private NET namespace makes these local ports independent of host ports.
    settings["ports"] = dict(settings["ports"], fabro=32391, ollama=32435, gateway=32436, llama=32437)
    monkeypatch.setattr(stack, "settings", lambda _: settings)
    monkeypatch.setattr(stack, "_start", REAL_START)
    monkeypatch.setattr(stack, "serving_instance", REAL_SERVING)
    monkeypatch.setattr(stack, "llama_server_spec", lambda r, prof, ports, env: (
        [sys.executable, str(llama), str(ports["llama"]), "--alias", D.RUN_MODEL], env,
        "http://127.0.0.1:" + str(ports["llama"]) + "/health", [D.RUN_MODEL],
    ))
    expected_record = D.current()
    calls = []

    def guard():
        assert D.current() == expected_record
        calls.append("FRESH_PRIVATE_GUARD")

    guard.bootstrap_binding = {"record_sha256": os.environ[D.SHA], "private_cpu_fixture": True}
    try:
        yield settings, guard, calls
    finally:
        # Only lifetimes created by this private fixture; no production signal path.
        path = root / "run/services.json"
        rec = json.loads(path.read_text()) if path.exists() else {}
        serving = rec.get("serving_instance")
        if serving is not None and not P.quiet(serving):
            assert P.stop(serving, fenced_effect=lambda effect: effect())
        for pr in rec.get("processes", {}).values():
            actual = P.identity(pr["pid"])
            if actual and actual.get("state") != "Z":
                expected = pr.get("identity")
                assert expected is not None
                assert actual["start_ticks"] == expected["start_ticks"]
                fd = pidfd.open_pid(pr["pid"])
                try:
                    pidfd.send_signal(fd, signal.SIGKILL)
                finally:
                    os.close(fd)
        holder = rec.get("holder_pid")
        if holder:
            actual = P.identity(holder)
            parent = int(Path(f"/proc/{holder}/stat").read_text().rsplit(")", 1)[1].split()[1]) if actual else None
            if actual and actual.get("state") != "Z":
                assert actual["start_ticks"] == rec["holder_identity"]["start_ticks"]
                fd = pidfd.open_pid(holder)
                try:
                    pidfd.send_signal(fd, signal.SIGKILL)
                finally:
                    os.close(fd)
            if parent:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and P.identity(parent) is not None:
                    try:
                        os.waitpid(parent, os.WNOHANG)
                    except ChildProcessError:
                        pass
                    time.sleep(0.02)


def test_real_cold_control_then_full_managed_nested_namespace_cpu_health(managed_cpu):
    settings, guard, calls = managed_cpu
    root = settings["root"]
    with stack.line_effect_guard(guard):
        control = stack._start(settings, recovery=True, control_only=True)
        assert control["health"] == {"fabro": True}
        result = stack._start(settings, recovery=True)
    assert all(result["health"].values()) and set(result["health"]) == {"fabro", "ollama", "gateway", "llama_server"}
    serving = REAL_SERVING(settings)
    holder = result["holder_pid"]
    assert os.readlink(f"/proc/{serving['init_pid']}/ns/user") != os.readlink(f"/proc/{holder}/ns/user")
    assert os.readlink(f"/proc/{serving['init_pid']}/ns/net") == os.readlink(f"/proc/{holder}/ns/net")
    for name in ("ollama", "llama_server"):
        port = settings["ports"]["ollama" if name == "ollama" else "llama"]
        observed = json.loads((root / ("private-cpu-" + str(port) + ".json")).read_text())
        assert observed == {n: os.readlink(f"/proc/{serving['init_pid']}/ns/{n}") for n in ("user", "net", "pid", "mnt")}
    worker = result["processes"]["llama_server"]["worker"]
    assert worker["pid"] != result["processes"]["llama_server"]["pid"]
    assert serving["schema"] == "forge-c/managed-provider-instance/2"
    # Real model-swap primitive runs in the outer Fabro USER/NET, just as graph
    # script nodes do. Only CPU transport and VRAM measurement leaves differ.
    cfg = root / "private-start-settings.json"
    cfg.write_text(json.dumps({**settings, "root": str(root)}))
    script = root / "private-outer-model-swap.py"
    script.write_text('''import json,sys,os,copy
from pathlib import Path
from forge_factory.lrtx import stack,provider_process as P
from forge_factory.afo.durable import Refused
from forge_factory.common import REPO_ROOT
assert str(REPO_ROOT)==sys.argv[2]
s=json.loads(Path(sys.argv[1]).read_text());s['root']=Path(s['root']);r=s['root'];ports=s['ports']
instance=stack.serving_instance(s);P.require_live_instance(instance)
negative=[]
for field in ['pid','start_ticks','mapping','user_namespace','net_namespace','missing_outer']:
 bad=copy.deepcopy(instance)
 if field=='pid':bad['outer_holder']['pid']=os.getpid()
 elif field=='start_ticks':bad['outer_holder']['identity']['start_ticks']='1'
 elif field=='mapping':bad['outer_holder']['owner_view']['uid_map']=[[0,instance['init']['uid']+1,1]]
 elif field=='user_namespace':bad['outer_holder']['owner_view']['user_namespace']='user:[1]'
 elif field=='net_namespace':bad['outer_holder']['net_namespace']='net:[1]'
 else:
  bad['schema']='forge-c/managed-provider-instance/1';del bad['outer_holder']
 try:P.require_live_instance(bad)
 except Refused:negative.append(field)
 else:raise AssertionError('FOREIGN_OUTER_VIEW_ACCEPTED:'+field)
assert len(negative)==6
stack._vram_free_mib=lambda:999999 # explicit private CPU resource-measurement leaf
stack.llama_server_spec=lambda root,prof,p,env,model=None:([sys.executable,str(root/'private-llama-server-health.py'),str(p['llama']),'--alias',model],env,'http://127.0.0.1:'+str(p['llama'])+'/health',[model])
out=stack._serve_model(s,'qwen3.8:27b-q8_0',serving=instance)
assert out['result']=='SWAPPED',out
Path(r/'private-outer-swap-result.json').write_text(json.dumps(out))
Path(r/'private-outer-provenance-negatives.json').write_text(json.dumps(negative))
''')
    env = stack.envmap(settings)
    process = subprocess.run(stack._nsenter(holder) + [sys.executable, str(script), str(cfg), str(stack.REPO_ROOT)],
                             env=env, capture_output=True, text=True, timeout=25)
    assert process.returncode == 0, process.stderr[-3000:]
    assert len(json.loads((root / "private-outer-provenance-negatives.json").read_text())) == 6
    latest = json.loads((root / "run/services.json").read_text())
    mapped = latest["processes"]["llama_server"]
    assert mapped["worker"]["identity"]["uid"] == 0
    assert mapped["worker"]["observer_user_namespace"] == serving["outer_holder"]["owner_view"]["user_namespace"]
    # A proof captured as mapped0 must NEVER become host UID0 authority.
    with pytest.raises(Refused, match="WORKER_BINDING_CHANGED"):
        P.signal_worker(serving, mapped["worker"], mapped["argv"], signal.SIGTERM, fenced_effect=lambda f:f())
    host_worker = P.capture_worker(serving, mapped["pid"], mapped["argv"])
    assert host_worker["identity"]["uid"] == os.getuid()
    assert P.stop(serving, fenced_effect=lambda f:f())
    assert P.quiet(serving)
    assert calls and not (root / "state/conductor/conductor.sqlite3").exists()
