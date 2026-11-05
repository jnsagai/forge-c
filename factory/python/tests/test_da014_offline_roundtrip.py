"""Actual CLI/manual-transfer integration in a kernel network namespace, using TEST keys only."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.reliability import isolation
from forge_factory.reliability.reproduce import _env


def test_export_replay_transfer_import_rejections_and_rollback_without_network():
    if isolation.backend() != "bubblewrap":
        pytest.skip("requires the scoped Bubblewrap verifier; no disconnected acceptance claimed")
    scratch = isolation.new_dir("offline-roundtrip")
    try:
        # OpenSSH needs account lookup metadata for its unchanged verifier UID.
        # The fixture is read-only inside this namespace; host /etc is untouched.
        passwd = scratch / "passwd"
        passwd.write_text(Path("/etc/passwd").read_text() +
                          "isolated-test-verifier:x:2001:2001:isolated TEST fixture:/tmp:/bin/sh\n")
        env = _env(REPO_ROOT, scratch)
        env["FIXTURE_PARENT_NETWORK_NAMESPACE"] = os.readlink("/proc/self/ns/net")
        script = REPO_ROOT / "factory/python/tests/fixtures/offline_roundtrip.py"
        args = isolation.bubblewrap_argv("verifier", [sys.executable, str(script)], cwd=scratch,
                                         env=env, writable=[scratch])
        at = args.index("--chdir")
        args[at:at] = ["--ro-bind", str(passwd), "/etc/passwd"]
        assert "--unshare-all" in args and "--share-net" not in args
        result = subprocess.run(args, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, (result.stdout[-1000:], result.stderr[-2000:])
        record = json.loads(result.stdout)
        assert record["network_namespace"] != env["FIXTURE_PARENT_NETWORK_NAMESPACE"]
        assert record["activation"] == "PATCH_OK" and record["rollback"] == "ROLLBACK_OK"
        assert len(record["rejected"]) == 7 and record["receipts"] == 9
        assert record["model_calls"] == 0
        print(json.dumps(record, sort_keys=True))
    finally:
        isolation.discard(scratch)
