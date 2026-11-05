"""Frozen actual four-process append-after-unlock exposure; private counters only."""
import fcntl
import json
import multiprocessing
import os
import tempfile
from pathlib import Path


def writer(root, barrier, outcomes):
    from forge_factory.policy import governor as G
    os.environ['FORGE_STATE_DIR'] = str(root)
    original = G.fcntl.flock
    def flock(fd, mode):
        original(fd, mode)
        if mode == fcntl.LOCK_UN:
            # A legitimate scheduling boundary after lock release, before buffered file close.
            barrier.wait(timeout=8)
    G.fcntl.flock = flock
    try:
        G._update('fixture', lambda state: state.update(calls=state.get('calls', 0) + 1))
        outcomes.put({'ok': True})
    except Exception as exc:
        outcomes.put({'ok': False, 'error': type(exc).__name__})


def stress(root, barrier, outcomes, is_writer):
    from forge_factory.policy import governor as G
    os.environ['FORGE_STATE_DIR'] = str(root)
    try:
        barrier.wait(timeout=8)
        snapshots = []
        for _ in range(12):
            if is_writer:
                def change(state):
                    state['calls'] = state.get('calls', 0) + 1
                    return state['calls']
                snapshots.append(G._update('fixture', change))
            else:
                with (root / 'governor/fixture.json').open() as stream:
                    fcntl.flock(stream, fcntl.LOCK_SH)
                    snapshots.append(json.load(stream)['calls'])
        outcomes.put({'ok': True, 'monotonic': snapshots == sorted(snapshots)})
    except Exception as exc:
        outcomes.put({'ok': False, 'error': type(exc).__name__})


def finish(workers, outcomes):
    try:
        for process in workers:
            process.join(timeout=12)
        if any(process.is_alive() or process.exitcode != 0 for process in workers):
            raise RuntimeError('OWN_FIXTURE_WORKER_NOT_TERMINAL')
        return [outcomes.get(timeout=2) for _ in workers]
    finally:
        for process in workers:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        outcomes.close()


def main():
    from forge_factory.policy import governor as G
    context = multiprocessing.get_context('fork')
    with tempfile.TemporaryDirectory(prefix='rpr162-private-counters-') as temporary:
        root = Path(temporary)
        barrier, outcomes = context.Barrier(4), context.Queue()
        workers = [context.Process(target=writer, args=(root, barrier, outcomes)) for _ in range(4)]
        for process in workers:
            process.start()
        rows = finish(workers, outcomes)
        if not all(row['ok'] for row in rows):
            raise RuntimeError('OWN_FIXTURE_WRITER_ERROR:' + json.dumps(rows))
        path = root / 'governor/fixture.json'
        try:
            state = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            if exc.msg != 'Extra data':
                raise
            print('SYMPTOM_PRESENT:buffered concurrent governor closes append multiple JSON snapshots')
            return 1
        if state != {'calls': 4}:
            print('SYMPTOM_PRESENT:concurrent governor update loses a debit')
            return 1
        start, outcomes = context.Barrier(8), context.Queue()
        workers = [context.Process(target=stress, args=(root, start, outcomes, index < 4)) for index in range(8)]
        for process in workers:
            process.start()
        rows = finish(workers, outcomes)
        if any(row.get('error') == 'JSONDecodeError' for row in rows):
            print('SYMPTOM_PRESENT:locked readers observe an invalid governor snapshot')
            return 1
        if not all(row['ok'] and row['monotonic'] for row in rows):
            raise RuntimeError('OWN_FIXTURE_STRESS_ERROR:' + json.dumps(rows))
        if json.loads(path.read_text()) != {'calls': 52}:
            print('SYMPTOM_PRESENT:concurrent governor update loses a debit')
            return 1
        # Malformed historical state remains a refusal, never an automatic allowance refill.
        malformed = b'{"calls":1}{"calls":2}'
        path.write_bytes(malformed)
        os.environ['FORGE_STATE_DIR'] = str(root)
        try:
            G._update('fixture', lambda state: state.clear())
        except json.JSONDecodeError:
            if path.read_bytes() != malformed:
                raise RuntimeError('CORRUPT_COUNTER_WAS_CHANGED') from None
        else:
            raise RuntimeError('CORRUPT_COUNTER_WAS_ACCEPTED_OR_RESET')
    print('SYMPTOM_ABSENT')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('REPRODUCER_ERROR:' + type(exc).__name__ + ':' + str(exc)[:250])
        raise SystemExit(2) from None
