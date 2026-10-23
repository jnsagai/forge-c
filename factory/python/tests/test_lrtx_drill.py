"""F011-T040 (F011-AT-033): the v2 shutdown/rollback drill. The rollback and the fingerprint run on real files and the
real stack start; the full drill runs with a scripted stack; the interrupted engine runs on the real pinned engine."""
from __future__ import annotations

import socket

import pytest
from forge_factory.lrtx import drill, stack
from test_safec_bridge_m2 import _engine, needs_engine


def _settings(tmp_path):
    s = stack.settings("local-rtx-v2")
    root = tmp_path / "lrtx-v2"
    (root / "state").mkdir(parents=True)
    (root / "state/keep.json").write_text("{}")
    return {**s, "root": root}


def test_rollback_moves_the_root_aside_refuses_start_and_restores(tmp_path):
    s = _settings(tmp_path)
    rec = drill.rollback(s)
    assert rec["ok"] and rec["moved_aside"] and rec["restored"] and rec["leftovers"] == []
    assert "run `init` first" in rec["start_refused"]
    assert (s["root"] / "state/keep.json").read_text() == "{}"
    assert not (tmp_path / "lrtx-v2.t040-rollback").exists()


def test_rollback_restores_the_root_on_an_unexpected_error(tmp_path, monkeypatch):
    s = _settings(tmp_path)
    monkeypatch.setattr(stack, "start", lambda s: (_ for _ in ()).throw(KeyError("boom")))
    with pytest.raises(KeyError):
        drill.rollback(s)
    assert (s["root"] / "state/keep.json").is_file() and not (tmp_path / "lrtx-v2.t040-rollback").exists()


def test_rollback_keeps_state_a_start_created_under_the_missing_root(tmp_path, monkeypatch):
    s = _settings(tmp_path)

    def start(s):
        (s["root"] / "run").mkdir(parents=True)
        raise RuntimeError("partial")

    monkeypatch.setattr(stack, "start", start)
    rec = drill.rollback(s)
    assert not rec["ok"] and rec["leftovers"] == ["run"] and (tmp_path / "lrtx-v2.t040-leftovers/run").is_dir()
    assert (s["root"] / "state/keep.json").is_file()


def test_listeners_reports_only_the_forbidden_ports_in_use():
    with socket.socket() as a:
        a.bind(("127.0.0.1", 0))
        a.listen()
        port = a.getsockname()[1]
        assert drill.listeners([port, 1]) == [port]


def _scripted(monkeypatch, healthy=True):
    state = {"up": True}

    def status(s):
        return {"status": "UP", "health": {"ollama": healthy, "gateway": True, "fabro": True}} if state["up"] \
            else {"status": "DOWN"}

    def stop(s):
        state["up"] = False
        return {"stopped": ["ollama", "gateway", "fabro"]}

    def start(s):
        if not (s["root"] / "state").is_dir():
            raise RuntimeError("run `init` first")
        state["up"] = True

    monkeypatch.setattr(stack, "status", status)
    monkeypatch.setattr(stack, "stop", stop)
    monkeypatch.setattr(stack, "start", start)
    monkeypatch.setattr(drill, "interrupted_engine", lambda pin, work: {"ok": True})


def test_the_drill_passes_when_only_v2_state_moves(tmp_path, monkeypatch):
    s = _settings(tmp_path)
    monkeypatch.setattr(stack, "settings", lambda pid: s)
    _scripted(monkeypatch)
    keep = tmp_path / "archives"
    keep.mkdir()
    (keep / "a.zip").write_bytes(b"zip")
    rec = drill.drill("local-rtx-v2", [keep], tmp_path / "work")
    assert rec["status"] == "PASS", rec["steps"]
    assert set(rec["steps"]) == {"fingerprint_before", "interrupted_engine", "running_before", "stop", "restart",
                                 "rollback", "restart_after_rollback", "fingerprint_after", "no_promotion"}


def test_the_drill_fails_when_a_protected_file_changes_or_a_service_is_unhealthy(tmp_path, monkeypatch):
    s = _settings(tmp_path)
    monkeypatch.setattr(stack, "settings", lambda pid: s)
    keep = tmp_path / "archives"
    keep.mkdir()
    (keep / "a.zip").write_bytes(b"zip")
    _scripted(monkeypatch)
    real_rollback = drill.rollback

    def tamper(s):
        (keep / "a.zip").write_bytes(b"changed")
        return real_rollback(s)

    monkeypatch.setattr(drill, "rollback", tamper)
    rec = drill.drill("local-rtx-v2", [keep], tmp_path / "w1")
    assert rec["status"] == "FAIL" and rec["steps"]["fingerprint_after"]["changed"] == ["protected"]
    monkeypatch.setattr(drill, "rollback", real_rollback)
    _scripted(monkeypatch, healthy=False)
    rec = drill.drill("local-rtx-v2", [keep], tmp_path / "w2")
    assert rec["status"] == "FAIL" and not rec["steps"]["restart"]["ok"]


@needs_engine
def test_an_interrupted_engine_leaves_nothing_admissible_and_recovers(tmp_path):
    rec = drill.interrupted_engine(_engine(), tmp_path / "eng")
    assert rec["ok"], rec
    assert rec["interrupted"]["issues"] == ["CANCELLED"] and not rec["interrupted"]["sealed_finalized"]
    assert rec["after"]["issues"] == []
