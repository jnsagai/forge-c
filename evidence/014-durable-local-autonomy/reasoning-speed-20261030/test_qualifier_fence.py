"""Actual owned child processes test the prepared verifier's cancellation fence."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


def runner():
    p = Path(__file__).with_name("qualify-native.py")
    tree = ast.parse(p.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_fenced")
    namespace = {"os": os, "time": time, "subprocess": subprocess}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(p), "exec"), namespace)
    return namespace["run_fenced"]


def test_completed_owned_verifier_is_reaped_and_keeps_log(tmp_path):
    r = runner()([sys.executable, "-c", "print('verified-child')"], tmp_path / "output",
                 lambda: {"mode": "PAUSED", "epoch": 73}, 73, timeout_s=3, poll_s=0.01)
    assert r["code"] == 0 and r["termination_reason"] is None
    assert "verified-child" in (tmp_path / "output").read_text()
    with pytest.raises(ChildProcessError):
        os.waitpid(r["child_pid"], os.WNOHANG)


@pytest.mark.parametrize("mode", ["RUNNING", "STOPPED"])
def test_new_operator_intent_terminates_only_the_owned_verifier(tmp_path, mode):
    r = runner()([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path / "output",
                 lambda: {"mode": mode, "epoch": 74}, 73, timeout_s=3, poll_s=0.01)
    assert r["code"] == 125 and r["termination_reason"] == "OPERATOR_INTENT_SUPERSEDED"
    with pytest.raises(ChildProcessError):
        os.waitpid(r["child_pid"], os.WNOHANG)


def test_verifier_wall_timeout_terminates_and_reaps_the_owned_child(tmp_path):
    r = runner()([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path / "output",
                 lambda: {"mode": "PAUSED", "epoch": 73}, 73, timeout_s=0.1, poll_s=0.01)
    assert r["code"] == 124 and r["termination_reason"] == "VERIFIER_WALL_TIMEOUT"
    with pytest.raises(ChildProcessError):
        os.waitpid(r["child_pid"], os.WNOHANG)


def test_unobservable_operator_intent_cancels_and_reaps_the_owned_child(tmp_path):
    def unavailable():
        raise OSError("synthetic unreadable operator record")
    r = runner()([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path / "output",
                 unavailable, 73, timeout_s=3, poll_s=0.01)
    assert r["code"] == 125 and r["termination_reason"] == "OPERATOR_INTENT_UNOBSERVABLE"
    with pytest.raises(ChildProcessError):
        os.waitpid(r["child_pid"], os.WNOHANG)

