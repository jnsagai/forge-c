"""Actual sandbox compiler scratch must stay in its writable loop10 workspace."""
import json
import os
import shutil
import sys

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.reliability import isolation as I


@pytest.mark.parametrize("role", ["verifier", "repair", "maintainer"])
def test_inherited_read_only_tmpdir_cannot_break_independent_compilation(role, tmp_path, monkeypatch):
    if not shutil.which("podman") or not shutil.which("clang"):
        pytest.skip("actual rootless Podman/compiler prerequisite unavailable")
    monkeypatch.setenv(I.MODE_ENV, "podman")
    scratch = I.new_dir("014-compiler-scratch")
    inherited = tmp_path / "owner-temp"
    inherited.mkdir()
    env = {"PATH": os.environ["PATH"], "FORGE_REPO_ROOT": str(REPO_ROOT), "TMPDIR": str(inherited)}
    code = '''import json,os,pathlib,subprocess,tempfile
root=pathlib.Path.cwd()
with tempfile.NamedTemporaryFile() as f: temporary=f.name
(root/'probe.c').write_text('int main(void) { return 0; }\\n')
compile=subprocess.run(['clang',str(root/'probe.c'),'-o',str(root/'probe')],capture_output=True,text=True)
run=subprocess.run([str(root/'probe')],capture_output=True) if compile.returncode==0 else None
print(json.dumps({'uid':os.getuid(),'tmpdir':os.environ['TMPDIR'],'temporary':temporary,
                 'compile':compile.returncode,'run':run.returncode if run else None,'stderr':compile.stderr}))
'''
    try:
        I.hand_over(role, scratch)
        p = I.execute(role, [sys.executable, "-c", code], cwd=scratch, env=env, writable=[scratch], timeout=60)
        assert p.returncode == 0, p.stderr.decode(errors="replace")
        result = json.loads(p.stdout)
        assert result["uid"] == I.ROLES[role]
        assert result["compile"] == result["run"] == 0, result["stderr"]
        assert result["tmpdir"] == str(scratch)
        assert result["temporary"].startswith(str(scratch) + "/")
        assert env["TMPDIR"] == str(inherited) and not list(inherited.iterdir())
    finally:
        I.discard(scratch)
