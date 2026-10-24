"""Real kernel confinement for hosts without subordinate-UID Podman; no model or GPU calls."""
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.reliability import isolation as I


def test_bubblewrap_scopes_namespace_uid_files_network_and_credentials(tmp_path, monkeypatch):
    if not shutil.which("bwrap"):
        pytest.skip("Bubblewrap not installed on this host")
    monkeypatch.setenv(I.MODE_ENV, "bubblewrap")
    secret = tmp_path / "owner-secret"
    secret.write_text("private fixture; never a real credential")
    secret.chmod(0o600)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    # Probe source/read-only behaviour with its own small source tree, never change production source.
    source = tmp_path / "source"
    source.mkdir()
    (source / "module.py").write_text("x = 1\n")
    code = '''import json,os,pathlib,socket
checks={"uid":os.getuid(),"secret_read":False,"source_write":False,"network":False,"gpu":False}
try:pathlib.Path(os.environ["PROBE_PRIVATE_PATH"]).read_text();checks["secret_read"]=True
except OSError:pass
try:pathlib.Path(os.environ["PROBE_SOURCE"]).write_text("bad");checks["source_write"]=True
except OSError:pass
try:
 socket.create_connection(("1.1.1.1",443),timeout=0.3).close();checks["network"]=True
except OSError:pass
checks["gpu"]=any(pathlib.Path("/dev").glob("nvidia*"))
checks["credential_env"]="API_KEY" in os.environ or "SSH_AUTH_SOCK" in os.environ
pathlib.Path("written.json").write_text(json.dumps(checks))
print(json.dumps(checks))
'''
    env = {"PATH": os.environ["PATH"], "FORGE_REPO_ROOT": str(source),
           "PROBE_PRIVATE_PATH": str(secret), "PROBE_SOURCE": str(source / "module.py"),
           "API_KEY": "fixture-only-not-a-credential", "SSH_AUTH_SOCK": "/unexposed/fixture-agent"}
    p = I.execute("maintainer", [sys.executable, "-c", code], cwd=scratch, env=env, writable=[scratch], timeout=20)
    if p.returncode and b"No permissions to create" in p.stderr:
        pytest.skip("Host kernel forbids unprivileged Bubblewrap; production activation must refuse this backend")
    assert p.returncode == 0, p.stderr.decode(errors="replace")
    checks = json.loads(p.stdout)
    assert checks == {"uid": 2003, "secret_read": False, "source_write": False,
                      "network": False, "gpu": False, "credential_env": False}
    assert json.loads((scratch / "written.json").read_text()) == checks
    assert (source / "module.py").read_text() == "x = 1\n"
    assert secret.read_text() == "private fixture; never a real credential"


def test_bubblewrap_never_mounts_the_factory_state_or_owner_home(monkeypatch, tmp_path):
    monkeypatch.setenv(I.MODE_ENV, "bubblewrap")
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path / "data"))
    scratch = tmp_path / "scratch"
    args = I.bubblewrap_argv("verifier", [sys.executable, "-V"], cwd=scratch,
                             env={"FORGE_REPO_ROOT": str(REPO_ROOT)}, writable=[scratch])
    sources = [args[n+1] for n, x in enumerate(args[:-1]) if x == "--ro-bind"]
    assert str(Path.home()) not in sources
    assert str(tmp_path / "data") not in sources
    assert str(tmp_path / "data/state") not in sources
    assert "--unshare-all" in args and "--cap-drop" in args
