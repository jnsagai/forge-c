"""CRE-T049 — verifier and repair code run as separate OS identities (rootless Podman sub-UIDs, storage on loop10).

Kernel-enforced, observed on the real host: the sandbox UID cannot write the repository or the data root, cannot
read the owner's 0600 credentials, has no network, and every file it creates is owned by a sub-UID (not the owner).
"""
import os
import sys
from pathlib import Path

import pytest
from forge_factory.common import REPO_ROOT, data_root, state_dir
from forge_factory.reliability import isolation

pytestmark = pytest.mark.skipif(not isolation.available(), reason="rootless podman not available")

PROBE = r"""
import json, os, socket, sys
from pathlib import Path
repo, data, secret, scratch = (Path(a) for a in sys.argv[1:5])
r = {"uid": os.getuid(), "home": os.environ.get("HOME")}
for name, target in (("repo", repo / ".cre-isolation-probe"), ("data", data / ".cre-isolation-probe")):
    try:
        target.write_text("x"); r[f"write_{name}"] = "WROTE"
    except OSError as e:
        r[f"write_{name}"] = type(e).__name__
try:
    secret.read_bytes(); r["read_secret"] = "READ"
except OSError as e:
    r["read_secret"] = type(e).__name__
try:
    socket.create_connection(("1.1.1.1", 53), timeout=3); r["network"] = "CONNECTED"
except OSError as e:
    r["network"] = type(e).__name__
(scratch / "out.txt").write_text("ok"); r["write_scratch"] = "WROTE"
import forge_factory; r["imports"] = forge_factory.__file__
print(json.dumps(r))
"""


def _secret() -> Path:
    for p in (state_dir() / "supervisor/checkpoint.json", state_dir() / "supervisor/health.json"):
        if p.is_file() and (p.stat().st_mode & 0o077) == 0:
            return p
    pytest.skip("no 0600 owner file to probe")


@pytest.mark.parametrize("role,uid", [("verifier", 2001), ("repair", 2002)])
def test_role_runs_as_separate_os_identity_with_kernel_enforced_limits(role, uid, tmp_path):
    import json

    secret = _secret()
    scratch = isolation.new_dir(f"t049-{role}")
    try:
        (scratch / "probe.py").write_text(PROBE)
        isolation.hand_over(role, scratch)
        env = {"PATH": os.environ["PATH"], "PYTHONPATH": str(REPO_ROOT / "factory/python"),
               "PYTHONDONTWRITEBYTECODE": "1", "FORGE_DEV_TOKEN": "must-not-pass"}
        p = isolation.execute(role, [sys.executable, str(scratch / "probe.py"), str(REPO_ROOT), str(data_root()),
                                     str(secret), str(scratch)], cwd=scratch, env=env, writable=[scratch], timeout=120)
        assert p.returncode == 0, p.stderr.decode()[-400:]
        r = json.loads(p.stdout.decode().strip().splitlines()[-1])
        assert r["uid"] == uid and r["home"] == str(scratch)
        assert r["write_repo"] != "WROTE" and r["write_data"] != "WROTE"
        assert r["read_secret"] == "PermissionError"
        assert r["network"] != "CONNECTED"
        assert r["write_scratch"] == "WROTE" and r["imports"].startswith(str(REPO_ROOT))
        out = scratch / "out.txt"
        host_uid = out.stat().st_uid
        assert host_uid != os.getuid() and host_uid >= 100000  # a subordinate UID, not the owner account
        with pytest.raises(PermissionError):
            out.write_text("owner cannot modify the sandbox's output in place")
        assert not (REPO_ROOT / ".cre-isolation-probe").exists()
        assert "must-not-pass" not in " ".join(isolation.argv(role, ["true"], cwd=scratch, env=env, writable=[]))
    finally:
        isolation.discard(scratch)
    assert not scratch.exists()


def test_storage_and_worktrees_live_on_the_data_volume():
    assert isolation.base() == data_root() / "podman"
    assert isolation.SHORT.resolve() == isolation.base().resolve()
    d = isolation.new_dir("t049-loc")
    try:
        assert str(d).startswith(str(data_root()))
    finally:
        isolation.discard(d)
    assert isolation.level() == "podman-rootless-subuid"


def test_disable_switch_falls_back_to_plain_subprocess(monkeypatch, tmp_path):
    monkeypatch.setenv(isolation.MODE_ENV, "none")
    assert not isolation.available() and isolation.level().startswith("none")
    p = isolation.execute("verifier", [sys.executable, "-c", "import os; print(os.getuid())"], cwd=tmp_path,
                          env=dict(os.environ), writable=[tmp_path])
    assert int(p.stdout) == os.getuid()
