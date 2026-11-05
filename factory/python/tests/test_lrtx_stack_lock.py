"""Autonomous line M2 (owner 2026-11-03): the stack-level lock of lrtx/stack.py. One lifecycle action (start/stop) per
stack root at a time: a raced start or stop is refused STACK_LOCK_HELD before any process action; the holder hands
its descriptor (FORGE_STACK_LOCK_FD) to the start/stop it runs itself; an uninitialised root is never created."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from forge_factory.lrtx import stack as ST


def test_stack_lock_refuses_a_raced_start_and_stop(tmp_path, monkeypatch):
    s = {"root": tmp_path / "root"}
    (s["root"] / "run").mkdir(parents=True)  # an initialised root (init creates run/)
    called = []
    monkeypatch.setattr(ST, "_locked_start", lambda s, recovery=False: called.append("start") or {"ok": 1})
    monkeypatch.setattr(ST, "_locked_stop", lambda s: called.append("stop") or {"stopped": []})
    with ST.stack_lock(s["root"]):  # the start that got there first
        with pytest.raises(ST.StackLockHeld):
            ST.start(s)
        with pytest.raises(ST.StackLockHeld):
            ST.stop(s)
        monkeypatch.setattr(ST, "settings", lambda profile: s)
        assert ST.main(["start"]) == 3
    assert called == []
    assert ST.start(s) == {"ok": 1} and ST.stop(s) == {"stopped": []} and called == ["start", "stop"]
    # a root that was never initialised (or is moved aside) is not created by the lock: start refuses it as before
    bare = {"root": tmp_path / "bare"}
    ST.start(bare)
    assert not bare["root"].exists() and called[-1] == "start"


def test_the_holder_hands_its_descriptor_to_its_own_start_only(tmp_path):
    root = tmp_path / "root"
    (root / "run").mkdir(parents=True)
    probe = ("import sys;from forge_factory.lrtx import stack as S\n"
             "try:\n    cm=S.stack_lock(sys.argv[1]);cm.__enter__();print('ACQUIRED')\n"
             "except S.StackLockHeld:\n    print('REFUSED')\n")
    env = {**os.environ, "PYTHONPATH": str(Path(ST.__file__).resolve().parents[2])}
    env.pop(ST.LOCK_FD_ENV, None)

    def run(fd):
        e = {**env, **({ST.LOCK_FD_ENV: str(fd)} if fd is not None else {})}
        return subprocess.run([sys.executable, "-c", probe, str(root)], env=e, pass_fds=(fd,) if fd is not None else (),
                              capture_output=True, text=True, timeout=60).stdout.strip()

    other = os.open(tmp_path / "other.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        with ST.stack_lock(root):
            assert run(None) == "REFUSED"
            assert run(other) == "REFUSED"  # a descriptor of another file is no pass
        fd = os.open(ST.lock_path(root), os.O_RDWR)
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
            assert run(fd) == "ACQUIRED"  # the holder's own start
            assert run(None) == "REFUSED"
        finally:
            os.close(fd)
        assert run(None) == "ACQUIRED"  # released with the holder
    finally:
        os.close(other)
