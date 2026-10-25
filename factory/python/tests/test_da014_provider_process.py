"""Real kernel provider-lifetime controls; no model, GPU, live stack or deployment."""

import copy
import os
import signal
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from forge_factory.afo.durable import Refused
from forge_factory.lrtx import provider_process as P


@contextmanager
def provider(tmp_path, name, *, network=False):
    root = tmp_path / name
    root.mkdir()
    log = (root / "namespace.log").open("wb")
    proc = subprocess.Popen(
        [
            "unshare",
            "--user",
            "--map-root-user",
            *(["--net"] if network else []),
            "--mount",
            "--pid",
            "--fork",
            "--mount-proc",
            "--kill-child=SIGKILL",
            "sh",
            "-c",
            "sleep 60 & wait",
        ],
        start_new_session=True,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        until = time.monotonic() + 3
        while True:
            if proc.poll() is not None:
                log.flush()
                text = (root / "namespace.log").read_text()
                if "Operation not permitted" in text or "Permission denied" in text:
                    pytest.skip("host kernel refuses unprivileged private PID namespace; live qualification remains required")
                pytest.fail(text)
            try:
                instance = P.capture(root, profile="fixture", profile_sha256="a" * 64, parent_pid=proc.pid)
                break
            except Refused:
                if time.monotonic() >= until:
                    raise
                time.sleep(0.02)
        yield instance
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
        log.close()


def test_retiring_exact_provider_kills_descendants_and_preserves_other_provider(tmp_path):
    with provider(tmp_path, "first") as first, provider(tmp_path, "other") as other:
        assert P.quiet(first) is None and P.quiet(other) is None
        init = first["init_pid"]
        children = [int(p) for p in Path(f"/proc/{init}/task/{init}/children").read_text().split()]
        proof = P.stop(first, fenced_effect=lambda effect: effect())
        assert proof and proof["kind"] == "PROVIDER_PRIVATE_PID_NAMESPACE_ENDED"
        assert P.quiet(other) is None
        for pid in children:
            observed = P.identity(pid)
            assert observed is None or observed["state"] == "Z"


def test_stale_operator_fence_prevents_signal(tmp_path):
    with provider(tmp_path, "fenced") as instance:

        def stale(effect):
            raise Refused("OPERATIONS_START_FENCED")

        with pytest.raises(Refused, match="OPERATIONS_START_FENCED"):
            P.stop(instance, fenced_effect=stale)
        assert P.quiet(instance) is None


def test_non_init_or_global_init_identity_is_never_signaled(tmp_path):
    with provider(tmp_path, "identity") as instance:
        for key, value in [("init_pid", 1), ("init_pid", os.getpid())]:
            changed = copy.deepcopy(instance)
            changed[key] = value
            if value == os.getpid():
                changed["init"]["namespace_pid"] = os.getpid()
            with pytest.raises(Refused, match="MANAGED_PROVIDER_IDENTITY_INVALID"):
                P.stop(changed, fenced_effect=lambda effect: pytest.fail("invalid identity reached effect"))
        assert P.quiet(instance) is None


def test_pid_reuse_observation_never_signals_the_newer_process(tmp_path, monkeypatch):
    with provider(tmp_path, "reused") as instance:
        real = P.identity
        newer = {**real(instance["init_pid"]), "start_ticks": "different"}
        monkeypatch.setattr(P, "identity", lambda pid: newer)
        monkeypatch.setattr(os, "pidfd_open", lambda pid: pytest.fail("reused PID was opened for signaling"))
        proof = P.stop(instance, fenced_effect=lambda effect: pytest.fail("newer process reached effect"))
        assert proof["kind"] == "PROVIDER_PRIVATE_PID_NAMESPACE_ENDED"


def test_unreadable_provider_identity_is_not_quiescence(tmp_path, monkeypatch):
    with provider(tmp_path, "unreadable") as instance:

        def unreadable(pid):
            raise Refused("PROVIDER_PROCESS_OBSERVATION_UNAVAILABLE")

        monkeypatch.setattr(P, "identity", unreadable)
        with pytest.raises(Refused, match="PROVIDER_PROCESS_OBSERVATION_UNAVAILABLE"):
            P.quiet(instance)


@pytest.mark.parametrize("bad", [None, [], {}, {"init": []}, {"profile_sha256": 3}, {"root": False}])
def test_malformed_instance_is_typed_refusal(bad):
    with pytest.raises(Refused, match="MANAGED_PROVIDER_IDENTITY_INVALID"):
        P.validate(bad)


def test_regular_legacy_process_is_not_adopted_as_private_provider(tmp_path):
    proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
    try:
        with pytest.raises(Refused, match="PROVIDER_PRIVATE_PID_NAMESPACE_REQUIRED"):
            P.capture(tmp_path, profile="fixture", profile_sha256="a" * 64, parent_pid=proc.pid)
        assert proc.poll() is None
    finally:
        proc.terminate()
        proc.wait(timeout=5)


@pytest.mark.parametrize(
    "field,value",
    [
        ("start_ticks", 3),
        ("start_ticks", "bad"),
        ("boot_id", None),
        ("pid_namespace", "unknown"),
        ("uid", False),
        ("namespace_pid", "1"),
    ],
)
def test_corrupt_kernel_identity_does_not_become_a_quiescence_proof(tmp_path, field, value):
    with provider(tmp_path, "corrupt") as instance:
        bad = copy.deepcopy(instance)
        bad["init"][field] = value
        with pytest.raises(Refused, match="MANAGED_PROVIDER_IDENTITY_INVALID"):
            P.quiet(bad)
        assert P.quiet(instance) is None
