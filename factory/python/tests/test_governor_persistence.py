"""Real multiprocess budget persistence; no model calls or production counters."""
import fcntl
import json
import multiprocessing
import os
from pathlib import Path

import pytest


def _writer(root, barrier, queue):
    from forge_factory.policy import governor as G
    os.environ['FORGE_STATE_DIR'] = str(root)
    original = G.fcntl.flock
    def flock(fd, mode):
        original(fd, mode)
        if mode == fcntl.LOCK_UN:
            barrier.wait(timeout=8)
    G.fcntl.flock = flock
    try:
        G._update('fixture', lambda state: state.update(calls=state.get('calls', 0) + 1))
        queue.put({'ok': True})
    except Exception as exc:
        queue.put({'ok': False, 'error': type(exc).__name__})


def _many(root, start, queue, writer):
    from forge_factory.policy import governor as G
    os.environ['FORGE_STATE_DIR'] = str(root)
    start.wait(timeout=8)
    seen = []
    try:
        for _ in range(12):
            def change(state):
                if writer:
                    state['calls'] = state.get('calls', 0) + 1
                return state.get('calls', 0)
            seen.append(G._update('fixture', change))
        queue.put({'ok': True, 'seen': seen})
    except Exception as exc:
        queue.put({'ok': False, 'error': type(exc).__name__})


def _finish(processes, queue):
    try:
        for process in processes:
            process.join(timeout=12)
        assert all(not process.is_alive() and process.exitcode == 0 for process in processes)
        return [queue.get(timeout=2) for _ in processes]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        queue.close()


def test_four_writers_cannot_append_after_unlock_before_buffer_close(tmp_path):
    context = multiprocessing.get_context('fork')
    barrier, queue = context.Barrier(4), context.Queue()
    workers = [context.Process(target=_writer, args=(tmp_path, barrier, queue)) for _ in range(4)]
    for worker in workers:
        worker.start()
    outcomes = _finish(workers, queue)
    assert all(row['ok'] for row in outcomes), outcomes
    # The old code produces multiple complete JSON documents at this real unlocked-close boundary.
    state = json.loads((tmp_path / 'governor/fixture.json').read_text())
    assert state == {'calls': 4}


def test_four_writers_and_four_readers_keep_every_debit_and_monotonic_snapshots(tmp_path):
    context = multiprocessing.get_context('fork')
    start, queue = context.Barrier(8), context.Queue()
    workers = [context.Process(target=_many, args=(tmp_path, start, queue, index < 4)) for index in range(8)]
    for worker in workers:
        worker.start()
    outcomes = _finish(workers, queue)
    assert all(row['ok'] for row in outcomes), outcomes
    assert all(row['seen'] == sorted(row['seen']) for row in outcomes)
    assert json.loads((tmp_path / 'governor/fixture.json').read_text()) == {'calls': 48}


def test_flush_and_fsync_happen_under_the_owning_exclusive_lock(tmp_path, monkeypatch):
    from forge_factory.policy import governor as G
    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path))
    original = os.fsync
    seen = []
    def fsync(fd):
        path = tmp_path / 'governor/fixture.json'
        with path.open() as other:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert json.loads(path.read_text()) == {'calls': 1}
        seen.append(fd)
        original(fd)
    monkeypatch.setattr(G.os, 'fsync', fsync)
    G._update('fixture', lambda state: state.update(calls=1))
    assert len(seen) == 1
    with (tmp_path / 'governor/fixture.json').open() as other:
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_corrupt_existing_counter_refuses_and_is_never_reset(tmp_path, monkeypatch):
    from forge_factory.policy import governor as G
    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path))
    path = tmp_path / 'governor/fixture.json'
    path.parent.mkdir()
    original = b'{"calls":1}{"calls":2}'
    path.write_bytes(original)
    with pytest.raises(json.JSONDecodeError):
        G._update('fixture', lambda state: state.clear())
    assert path.read_bytes() == original


def test_fsync_failure_refuses_after_debit_without_refill(tmp_path, monkeypatch):
    from forge_factory.policy import governor as G
    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path))
    G._update('fixture', lambda state: state.update(calls=3))
    def refused(_fd):
        raise OSError('FIXTURE_FSYNC_REFUSED')
    monkeypatch.setattr(G.os, 'fsync', refused)
    with pytest.raises(OSError, match='FIXTURE_FSYNC_REFUSED'):
        G._update('fixture', lambda state: state.update(calls=state['calls'] + 1))
    assert json.loads((tmp_path / 'governor/fixture.json').read_text()) == {'calls': 4}


def test_turn_limits_inspection_reservations_and_explicit_node_reset_are_unchanged(tmp_path, monkeypatch):
    from forge_factory.policy import governor as G
    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path))
    monkeypatch.setattr(G, 'turn_limit', lambda *_: 6)
    for count in range(1, 7):
        assert G.count_tool_call('fixture', 'run', 'author', 'swe6-author') == (True, count, 6, False)
    assert G.count_tool_call('fixture', 'run', 'author', 'swe6-author') == (False, 7, 6, False)
    for count in (1, 2):
        assert G.count_tool_call('fixture', 'run', 'inspector', 'swe6-inspector') == (True, count, 6, False)
    assert G.count_tool_call('fixture', 'run', 'inspector', 'swe6-inspector') == (False, 2, 6, True)
    assert G.count_tool_call('fixture', 'run', 'inspector', 'swe6-inspector', G.RESERVED_TOOLS[0]) == (True, 3, 6, False)
    G.reset_node('fixture', 'run', 'author')
    state = json.loads((tmp_path / 'governor/fixture.json').read_text())
    assert state['run:author'] == 0 and state['run:inspector'] == 3
