"""Actual private-PID kernel view controls; no model, GPU, production state or service."""

# ruff: noqa: F811 - shared private fixture imported for pytest
import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from forge_factory.afo import owner_development_view as V
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import digest, immutable_json
from forge_factory.lrtx import provider_process as P
from test_owner_supervised_development import supervised  # noqa:F401


@contextlib.contextmanager
def private_provider(supervised, tmp_path, monkeypatch, *, fake_proc=False, fake_socket=False):
    root = Path(supervised["store"].path).parents[2]
    record = D.current(store=supervised["store"])
    command, view, handles = V.prepare(root, record)
    handles = list(handles)
    if fake_proc:
        spoof = tmp_path / "fake-uid-map"
        spoof.write_text("0 0 4294967295\n")
        i = command.index(view["files"]["uid_map"]) - 1
        fake_fd = os.open(spoof, os.O_RDONLY)
        handles.append(fake_fd)
        command[i] = str(fake_fd)
    socket_server = None
    if fake_socket:
        import socket

        socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        fake = tmp_path / "fake.sock"
        # Use short /proc/self/fd address for a legitimate private fixture socket.
        with D._unix_path(fake) as address:
            socket_server.bind(address)
        socket_server.listen(1)
        i = command.index(view["files"]["socket"]) - 1
        fake_fd = os.open(fake, os.O_PATH)
        handles.append(fake_fd)
        command[i] = str(fake_fd)
    from forge_factory.lrtx.stack import _in_ns

    holder = subprocess.Popen(
        ["unshare", "--user", "--map-root-user", "--net", "sleep", "infinity"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    until = time.monotonic() + 3
    while time.monotonic() < until:
        if holder.poll() is not None:
            raise AssertionError(holder.communicate()[1].decode())
        if os.readlink(f"/proc/{holder.pid}/ns/user") != os.readlink("/proc/self/ns/user"):
            break
        time.sleep(0.01)
    output = tmp_path / "private-provider.log"
    try:
        proc = _in_ns(holder.pid, command, os.environ.copy(), output, root, pass_fds=tuple(handles))
    finally:
        V.close_handles(handles)
    instance = None
    try:
        until = time.monotonic() + 5
        while time.monotonic() < until:
            if proc.poll() is not None:
                raise AssertionError(output.read_text())
            try:
                instance = P.capture(
                    root, profile=record["profile"], profile_sha256=record["profile_sha256"], parent_pid=proc.pid
                )
                break
            except ValueError:
                time.sleep(0.02)
        assert instance is not None, "PRIVATE_PROVIDER_CAPTURE_TIMEOUT"
        instance["owner_development_view"] = view
        immutable_json(root / "run/provider-instances" / (digest(instance) + ".json"), instance)
        from forge_factory.lrtx.stack import _save_services

        _save_services(root, dict(serving_instance=instance))
        monkeypatch.setenv("FORGE_LRTX_ROOT", str(root))
        monkeypatch.setenv("FORGE_OPERATIONS_PROFILE", record["profile"])
        monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
        yield record, instance, view
    finally:
        if proc.poll() is None:
            if instance is not None:
                # Fixture owns this exact private PID namespace; no production PIDs.
                assert P.stop(instance, fenced_effect=lambda effect: effect())
            else:
                proc.terminate()
        proc.communicate(timeout=5)
        holder.terminate()
        holder.communicate(timeout=5)
        if socket_server is not None:
            socket_server.close()


def consumer(instance, code, *, env=None):
    args = ["nsenter", "-t", str(instance["init_pid"]), "-U", "-m", "-p", "--preserve-credentials", sys.executable, "-c", code]
    return subprocess.run(args, text=True, capture_output=True, timeout=10, env=env)


PRELUDE = """
import os,json
from pathlib import Path
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo import line_recovery_control as C
from forge_factory.afo.durable import Refused
record=json.loads(Path(os.environ[D.FILE]).read_text())
C.revision=lambda:dict(commit=record['source_revisions'][0],dirty=False) # Explicit source leaf only; no authority mock.
"""


def test_actual_private_pid_accepts_only_pinned_kernel_and_store_view(supervised, tmp_path, monkeypatch):
    with private_provider(supervised, tmp_path, monkeypatch) as (record, instance, view):
        r = consumer(
            instance,
            PRELUDE
            + """
assert not Path('/proc/'+str(record['guardian_pid'])).exists(), 'HOST_PROCESS_NOT_HIDDEN'
assert D.current()['acceptance']=='UNACCEPTED'
print('REAL_NESTED_PID_KERNEL_VIEW_PASS')
""",
        )
        assert r.returncode == 0, (r.stderr, r.stdout)
        assert r.stdout.strip() == "REAL_NESTED_PID_KERNEL_VIEW_PASS"


def test_actual_fake_proc_mount_refuses_in_private_pid(supervised, tmp_path, monkeypatch):
    with private_provider(supervised, tmp_path, monkeypatch, fake_proc=True) as (_, instance, _):
        r = consumer(
            instance,
            PRELUDE
            + """
try:D.current()
except Refused as e:
 assert e.code=='OWNER_DEVELOPMENT_VIEW_PROC_IDENTITY_CHANGED',e.code
 print('FAKE_PROC_REFUSED')
else:raise AssertionError('FAKE_PROC_ACCEPTED')
""",
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "FAKE_PROC_REFUSED"


def test_actual_fake_socket_inode_refuses_in_private_pid(supervised, tmp_path, monkeypatch):
    with private_provider(supervised, tmp_path, monkeypatch, fake_socket=True) as (_, instance, _):
        r = consumer(
            instance,
            PRELUDE
            + """
try:D.current()
except Refused as e:
 assert e.code=='OWNER_DEVELOPMENT_VIEW_SOCKET_NODE_REBOUND',e.code
 print('FAKE_SOCKET_REFUSED')
else:raise AssertionError('FAKE_SOCKET_ACCEPTED')
""",
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "FAKE_SOCKET_REFUSED"


def test_copied_store_even_with_exact_authority_rows_cannot_replace_canonical(supervised, tmp_path, monkeypatch):
    import sqlite3

    from forge_factory.afo.queue import Store

    target = tmp_path / "copied.sqlite3"
    with (
        contextlib.closing(sqlite3.connect(supervised["store"].path)) as source,
        contextlib.closing(sqlite3.connect(target)) as dest,
    ):
        source.backup(dest)
    with pytest.raises(ValueError, match="CANONICAL_STORE_REBOUND"):
        D.current(store=Store(target, must_exist=True))


def test_guardian_shutdown_refuses_private_pid_without_new_authority(supervised, tmp_path, monkeypatch):
    with private_provider(supervised, tmp_path, monkeypatch) as (_, instance, _):
        D.close_guardian(supervised["ref"])
        r = consumer(
            instance,
            PRELUDE
            + """
try:D.current()
except Refused as e:
 assert e.code=='OWNER_DEVELOPMENT_GUARDIAN_ATTESTATION_UNAVAILABLE',e.code
 print('GUARDIAN_CLOSED_REFUSED')
else:raise AssertionError('DEAD_GUARDIAN_ACCEPTED')
""",
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "GUARDIAN_CLOSED_REFUSED"


def test_actual_mapped_app_host_pid_path_is_authorized(supervised):
    code = (
        PRELUDE
        + """
assert not D.guardian_alive(record)
assert D.mapped_host_guardian_alive(record)
assert D.current()['acceptance']=='UNACCEPTED'
print('MAPPED_APP_HOST_PID_PASS')
"""
    )
    r = subprocess.run(
        ["unshare", "--user", "--map-root-user", "--net", sys.executable, "-c", code], text=True, capture_output=True, timeout=10
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert r.stdout.strip() == "MAPPED_APP_HOST_PID_PASS"


def test_actual_mapped_fake_guardian_count1_reaches_kernel_extent_refusal(supervised):
    code = (
        PRELUDE
        + """
from forge_factory.lrtx.provider_process import identity
fake=dict(record)
fake['guardian_pid']=os.getpid()
fake['guardian']={k:v for k,v in identity(os.getpid()).items()if k!='state'}
fake['guardian']['uid']=record['guardian']['uid']
assert [list(map(int,x.split()))for x in Path('/proc/self/uid_map').read_text().splitlines()]==[[0,record['guardian']['uid'],1]]
assert os.readlink('/proc/self/ns/pid')==fake['guardian']['pid_namespace']
assert not D.mapped_host_guardian_alive(fake)
print('ACTUAL_COUNT1_FAKE_REFUSED_AT_KERNEL_PROOF')
"""
    )
    r = subprocess.run(
        ["unshare", "--user", "--map-root-user", sys.executable, "-c", code], text=True, capture_output=True, timeout=10
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "ACTUAL_COUNT1_FAKE_REFUSED_AT_KERNEL_PROOF"


def test_another_pid_namespace_cannot_use_mapped_host_branch(supervised):
    code = (
        PRELUDE
        + """
assert os.readlink('/proc/self/ns/pid')!=record['guardian']['pid_namespace']
assert not D.mapped_host_guardian_alive(record)
print('OTHER_PID_NAMESPACE_REFUSED')
"""
    )
    r = subprocess.run(
        ["unshare", "--user", "--map-root-user", "--mount", "--pid", "--fork", "--mount-proc", sys.executable, "-c", code],
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "OTHER_PID_NAMESPACE_REFUSED"


def test_same_guardian_normal_provider_recreation_keeps_accounting(supervised, tmp_path, monkeypatch):
    from forge_factory.afo.mission_ledger import MissionLedger

    before = MissionLedger(supervised["store"]).snapshot(D.MISSION)
    identities = []
    for _ in range(2):
        with private_provider(supervised, tmp_path, monkeypatch) as (_, instance, _):
            identities.append(instance["init"]["start_ticks"] + ":" + str(instance["init_pid"]))
            r = consumer(instance, PRELUDE + "assert D.current()['acceptance']=='UNACCEPTED'\n")
            assert r.returncode == 0, r.stderr
    assert len(set(identities)) == 2
    assert MissionLedger(supervised["store"]).snapshot(D.MISSION) == before
