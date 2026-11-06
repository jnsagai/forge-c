"""The provider sandbox must outlive the process that started it; real prepare, bwrap and capture.

L90D lost its last attempt to this: the launcher's `stack start` subprocess exited and took the
providers with it. Harmless `sleep` payload only; no model, GPU or service effect.
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from forge_factory.afo import owner_development_view as V
from forge_factory.lrtx import provider_process as P

pytestmark = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bwrap required")

SHORT_LIVED_STARTER = r"""
import json,os,subprocess,sys,time
from pathlib import Path
from forge_factory.afo import owner_development_view as V, owner_supervised_development as D
from forge_factory.lrtx import provider_process as P
D.guardian_alive=lambda record:True
root=Path(sys.argv[1]);record=json.loads(Path(sys.argv[2]).read_text())
command,_,handles=V.prepare(root,record)
process=subprocess.Popen(command,start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,pass_fds=handles,cwd=root)
for fd in handles:os.close(fd)
until=time.monotonic()+5
while True:
    try:
        instance=P.capture(root,profile='fixture',profile_sha256='a'*64,parent_pid=process.pid);break
    except Exception:
        assert time.monotonic()<until;time.sleep(.02)
print(json.dumps(instance),flush=True)
os._exit(0)
"""


@pytest.fixture
def fixture_record(tmp_path):
    root = Path(os.path.realpath(tmp_path))
    (root / "state/supervisor").mkdir(parents=True)
    store = root / "state/supervisor/q.sqlite3"
    store.write_text("")
    path = root / "g.sock"
    guardian = socket.socket(socket.AF_UNIX)
    guardian.bind(str(path))
    st = path.stat()
    record = dict(guardian_pid=os.getpid(), guardian_socket=str(path), guardian_socket_identity=dict(device=st.st_dev, inode=st.st_ino),
                  store_path=str(store), store_identity=dict(device=store.stat().st_dev, inode=store.stat().st_ino))
    (root / "record.json").write_text(json.dumps(record))
    yield root
    guardian.close()


def start(root):
    env = dict(os.environ, PYTHONPATH=str(Path(V.__file__).resolve().parents[2]))
    done = subprocess.run([sys.executable, "-c", SHORT_LIVED_STARTER, str(root), str(root / "record.json")],
                          capture_output=True, text=True, timeout=20, env=env)
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_provider_sandbox_survives_short_lived_starter_then_retires_by_exact_instance(fixture_record):
    instance = start(fixture_record)
    time.sleep(0.5)
    try:
        assert P.quiet(instance) is None
        P.require_live_instance(instance)
        proof = P.stop(instance, fenced_effect=lambda effect: effect())
        assert proof and proof["kind"] == "PROVIDER_PRIVATE_PID_NAMESPACE_ENDED" and P.quiet(instance)
    finally:
        actual = P.identity(instance["init_pid"])
        if actual and actual["start_ticks"] == instance["init"]["start_ticks"]:
            os.kill(instance["init_pid"], signal.SIGKILL)


def test_view_never_ties_provider_lifetime_to_its_starter():
    source = Path(V.__file__).read_text()
    arguments = [line.strip() for line in source.splitlines() if line.strip().startswith('"--')]
    assert '"--die-with-parent",' not in arguments and '"--as-pid-1",' in arguments
