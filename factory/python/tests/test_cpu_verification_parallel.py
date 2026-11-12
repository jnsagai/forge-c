"""Parallel verification preserves all cases, their results, isolation and failure visibility."""
import threading
import time

import pytest
from forge_factory.reliability import parallel as P
from forge_factory.reliability import reproduce as R


def test_omniverse_capacity_keeps_cpu_and_memory_headroom():
    assert P.capacity(16, cpus=24, available_mb=106496) == 16
    assert P.capacity(32, cpus=24, available_mb=106496) == 16
    assert P.capacity(16, cpus=24, available_mb=32768) == 4
    assert P.capacity(16, cpus=8, available_mb=106496) == 1
    with pytest.raises(ValueError):
        P.capacity(0, cpus=24, available_mb=106496)


def test_real_concurrent_execution_keeps_input_order_and_the_worker_bound(monkeypatch):
    monkeypatch.setattr(P, "capacity", lambda n: n)
    lock, active, maximum = threading.Lock(), 0, 0

    def task(n):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.02 * (4 - n % 4))
        with lock:
            active -= 1
        return (n, "FAIL" if n == 3 else "PASS")

    assert P.ordered_map(task, range(8), jobs=3) == [(n, "FAIL" if n == 3 else "PASS") for n in range(8)]
    assert 1 < maximum <= 3


def test_worker_exception_is_never_converted_into_a_pass(monkeypatch):
    monkeypatch.setattr(P, "capacity", lambda n: n)

    def task(n):
        if n == 1:
            raise RuntimeError("verification failed")
        return n

    with pytest.raises(RuntimeError, match="verification failed"):
        P.ordered_map(task, range(5), jobs=3)


def test_reproducer_batch_prepares_source_once_and_preserves_every_case(monkeypatch):
    monkeypatch.setattr(P, "capacity", lambda n: n)
    prepared = []

    class Pool:
        def get(self, rev):
            prepared.append(rev)

    calls = []

    def run(store, policy, rid, revision, role, pool, manifest):
        assert prepared == ["REV"]
        calls.append(rid)
        return {"reproducer_id": rid, "verdict": "SYMPTOM_PRESENT" if rid == "R2" else "SYMPTOM_ABSENT"}

    monkeypatch.setattr(R, "run", run)
    results = R.run_many(None, None, ["R3", "R1", "R2"], "REV", "PREVENTION", Pool(), {}, jobs=3)
    assert sorted(calls) == ["R1", "R2", "R3"]
    assert [r["reproducer_id"] for r in results] == ["R1", "R2", "R3"]
    assert results[1]["verdict"] == "SYMPTOM_PRESENT"
