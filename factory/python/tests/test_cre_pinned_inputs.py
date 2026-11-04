"""CAPA-156: required dependencies remain readable without exposing factory state."""
import hashlib
import json
import os
import shutil
import sys

import pytest
from forge_factory.reliability import isolation


@pytest.mark.parametrize("linked", [False, True])
def test_pinned_input_is_readable_but_immutable_in_real_namespace(tmp_path, monkeypatch, linked):
    if not shutil.which("bwrap"):
        pytest.skip("Bubblewrap not installed")
    data = tmp_path / "runtime"
    data.mkdir()
    inputs = data / "inputs"
    if linked:
        shared = tmp_path / "shared-inputs"
        shared.mkdir()
        inputs.symlink_to(shared, target_is_directory=True)
    else:
        inputs.mkdir()
    body = b"pinned synthetic dependency\n"
    header = inputs / "driver.h"
    header.write_bytes(body)
    state = data / "state"
    state.mkdir()
    private = state / "owner-fixture"
    private.write_text("private synthetic fixture")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setenv("FORGE_DATA_ROOT", str(data))
    monkeypatch.setenv(isolation.MODE_ENV, "bubblewrap")
    code = '''import hashlib,json,pathlib,sys
header,private=map(pathlib.Path,sys.argv[1:])
r={"sha256":hashlib.sha256(header.read_bytes()).hexdigest(),"write":False,"state":False}
try:header.write_bytes(b"changed");r["write"]=True
except OSError:pass
try:private.read_bytes();r["state"]=True
except OSError:pass
pathlib.Path("scratch-output").write_text("allowed")
print(json.dumps(r))
'''
    p = isolation.execute("verifier", [sys.executable, "-c", code, str(header), str(private)], cwd=scratch,
                          env={"PATH": os.environ["PATH"], "FORGE_REPO_ROOT": str(source)},
                          writable=[scratch], timeout=15)
    assert p.returncode == 0, p.stderr.decode(errors="replace")
    assert json.loads(p.stdout) == {"sha256": hashlib.sha256(body).hexdigest(), "write": False, "state": False}
    assert header.read_bytes() == body
    assert (scratch / "scratch-output").read_text() == "allowed"


def test_absent_input_directory_does_not_expose_parent_storage(tmp_path, monkeypatch):
    data = tmp_path / "runtime"
    data.mkdir()
    monkeypatch.setenv("FORGE_DATA_ROOT", str(data))
    a = isolation.bubblewrap_argv("verifier", [sys.executable, "-V"], cwd=tmp_path,
                                 env={"FORGE_REPO_ROOT": str(tmp_path / "source")}, writable=[])
    mounts = [a[n + 1] for n, value in enumerate(a[:-1]) if value == "--ro-bind"]
    assert str(data) not in mounts and str(data.parent) not in mounts
    assert str(data / "inputs") not in mounts
