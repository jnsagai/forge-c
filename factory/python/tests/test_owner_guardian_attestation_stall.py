"""A slow heartbeat fsync must not stall guardian attestation (found by the private launch rehearsal)."""
import json
import os
import socket
import threading
import time
from types import SimpleNamespace

import pytest
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import canonical, digest


def challenge(path):
    nonce = "a" * 64
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(2)
        client.connect(str(path))
        client.sendall(canonical(dict(record_sha256=digest(RECORD), nonce=nonce)))
        return json.loads(client.recv(4097)), nonce


RECORD = dict(fixture="guardian-attestation-stall")


@pytest.fixture
def guardian(tmp_path, monkeypatch):
    os.chdir(tmp_path)  # Relative bind: pytest tmp paths can exceed the AF_UNIX limit.
    server = socket.socket(socket.AF_UNIX)
    server.bind("g.sock")
    clock = [1000.0]
    calls, finished = [], threading.Event()
    monkeypatch.setattr(D, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    def publish(record):
        calls.append(threading.current_thread().name)
        if len(calls) > 1:
            time.sleep(3)  # Longer than the 2 second attestation timeout.
            finished.set()

    monkeypatch.setattr(D, "_publish_heartbeat", publish)
    D._serve_guardian(RECORD, server)
    yield tmp_path / "g.sock", clock, calls, finished
    stop = D._GUARDIANS.pop(digest(RECORD))
    stop[1].set()
    server.close()
    stop[2].join(timeout=2)


def test_first_challenge_publishes_before_acknowledging(guardian):
    path, _, calls, _ = guardian
    reply, nonce = challenge(path)
    assert reply["nonce"] == nonce and calls == ["owner-development-guardian"]


def test_later_slow_heartbeat_runs_aside_and_attestation_answers_in_time(guardian):
    path, clock, calls, finished = guardian
    challenge(path)
    clock[0] += 16
    started = time.perf_counter()
    reply, nonce = challenge(path)
    assert reply["nonce"] == nonce and time.perf_counter() - started < 1.5
    second, _ = challenge(path)  # Answered while the slow publication is still running.
    assert second["scope"] == D.MODE and not finished.is_set()
    assert finished.wait(5) and calls == ["owner-development-guardian", "owner-development-heartbeat"]


def test_only_one_background_publication_runs_at_a_time(guardian):
    path, clock, calls, finished = guardian
    challenge(path)
    clock[0] += 16
    challenge(path)
    clock[0] += 16
    challenge(path)
    assert len(calls) == 2
    assert finished.wait(5)
