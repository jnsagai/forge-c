"""Offline harness for the qualification-window commands (feature 017 T072): no line, no host writes, temporary paths.
Run: <venv>/bin/python test_window.py [module-file]   (default: autodeploy.py next to this file)"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).parent
src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'autodeploy.py'
spec = importlib.util.spec_from_file_location('autodeploy_under_test', src)
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
EVENTS, RESULTS = [], []
A.log = lambda ev, **kw: EVENTS.append((ev, kw))


def check(name, ok, detail=''):
    RESULTS.append(bool(ok))
    print(('PASS ' if ok else 'FAIL ') + name + (': ' + str(detail) if detail and not ok else ''))


def run(*a, **kw):
    return subprocess.run(list(a), check=True, capture_output=True, text=True, **kw).stdout.strip()


tmp = Path(tempfile.mkdtemp(prefix='t072-'))
# a private repository standing in for repo.git, with the branch of record
repo = tmp / 'repo'
run('git', 'init', '-q', '-b', A.BRANCH, str(repo))
(repo / 'f.txt').write_text('live tree\n')
run('git', '-C', str(repo), 'add', '-A')
run('git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'live')
live = run('git', '-C', str(repo), 'rev-parse', 'HEAD')
A.W = repo
for name in ('STATE', 'LOG', 'LATCH', 'LOCK', 'WINDOW'):
    setattr(A, name, tmp / {'STATE': 'state.json', 'LOG': 'log.jsonl', 'LATCH': 'FAILED_LATCHED.json', 'LOCK': 'deploy.lock',
                            'WINDOW': 'WINDOW.json'}[name])
A.STATE.write_text(json.dumps({'live': {'commit': live, 'pid': '1', 'inv': 'i', 'ref': 'r', 'guard': 'g'}, 'deploys': []}))

# 1. same-tree commit: identical tree, parent = tip, branch moves by CAS; refused when a candidate is pending
rev = A.make_same_tree(live, 'w1')
check('same-tree commit has the live tree', run('git', '-C', str(repo), 'rev-parse', rev + '^{tree}') ==
      run('git', '-C', str(repo), 'rev-parse', live + '^{tree}'))
check('same-tree commit sits on the live commit', run('git', '-C', str(repo), 'rev-parse', rev + '^') == live)
A.drop_same_tree(rev, live)
check('an aborted release leaves the branch at the live commit', run('git', '-C', str(repo), 'rev-parse', A.BRANCH) == live)
(repo / 'f.txt').write_text('pending candidate\n')
run('git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qam', 'candidate')
try:
    A.make_same_tree(live, 'w2')
    check('refused while a candidate is pending', False)
except A.Refused as e:
    check('refused while a candidate is pending', 'WINDOW_REFUSED_PENDING_DEPLOY' in str(e), e)
run('git', '-C', str(repo), 'update-ref', f'refs/heads/{A.BRANCH}', live)

# 2. release refuses before any change: open window, latch, bad id
A.WINDOW.write_text('{}')
for label, call in (('open window', lambda: A.window_release('w3abcd', time.time() + 3600)),):
    try:
        call()
        check(f'release refused with an {label}', False)
    except A.Refused as e:
        check(f'release refused with an {label}', 'WINDOW_ALREADY_OPEN' in str(e), e)
A.WINDOW.unlink()
A.LATCH.write_text('{}')
try:
    A.window_release('w4abcd', time.time() + 3600)
    check('release refused while latched', False)
except A.Refused as e:
    check('release refused while latched', 'FAILED_LATCHED' in str(e), e)
A.LATCH.unlink()
try:
    A.window_release('bad id!', time.time() + 3600)
    check('release refuses a malformed window id', False)
except A.Refused as e:
    check('release refuses a malformed window id', 'WINDOW_ID_INVALID' in str(e), e)
check('no lock left behind', not A.LOCK.exists())

# 3. release aborted before the stop: hold released (via restore_after_abort), no commit left, no window recorded
calls = []
A.rate_ok = lambda st: None
A.observer_active = lambda: True
A.live_identity = lambda c: {'commit': live, 'pid': '1', 'inv': 'i', 'ref': 'r', 'guard': 'g'}
A.rollback_evidence = lambda rev, good: 'pd-test'
A.gen_stop_tooling = lambda st, lv: tmp / 'stop'
A.gen_package = lambda *a, **k: tmp / 'pkg'
A.stage = lambda pkg, rev: str(tmp / 'R')
A.quiesce = lambda *a, **k: (_ for _ in ()).throw(A.Refused('LINE_NOT_QUIET_BEFORE_DEADLINE'))
A.restore_after_abort = lambda lv, cand, err: calls.append(('restore_after_abort', cand)) or True
try:
    A.window_release('w5abcd', time.time() + 3600)
    check('release aborted before the stop raises', False)
except A.Refused:
    check('release aborted before the stop raises', True)
check('hold released after the abort', calls and calls[0][0] == 'restore_after_abort', calls)
check('no window commit left on the branch', run('git', '-C', str(repo), 'rev-parse', A.BRANCH) == live)
check('no window recorded', not A.WINDOW.exists() and 'window' not in json.loads(A.STATE.read_text()))
check('lock released', not A.LOCK.exists())

# 4. auto(): an open window is skipped; an abandoned one is restored by the timer itself; never "recover"
A.latch_retry_due = lambda: False
A.import_proposals = lambda st: (_ for _ in ()).throw(AssertionError('auto must not import while a window is open'))
A.recover = lambda st: (_ for _ in ()).throw(AssertionError('auto must not recover a lane stopped by a window'))
A.WINDOW.write_text(json.dumps({'id': 'w6abcd', 'deadline': time.time() + 3600}))
out = []
import builtins  # noqa: E402
_print = builtins.print
builtins.print = lambda *a, **k: out.append(' '.join(map(str, a)))
try:
    A.auto()
finally:
    builtins.print = _print
check('auto skips an open window', out == ['SKIP window_open'], out)
restored = []
A.window_restore = lambda locked=False: restored.append(True) or 'WINDOW_RESTORED'
A.WINDOW.write_text(json.dumps({'id': 'w7abcd', 'deadline': time.time() - A.WINDOW_GRACE_S - 60}))
out.clear()
builtins.print = lambda *a, **k: out.append(' '.join(map(str, a)))
try:
    A.auto()
finally:
    builtins.print = _print
check('auto restores an abandoned window itself', restored == [True] and out == ['WINDOW_RESTORED'], (restored, out))
check('the abandonment is logged', any(e == 'window_abandoned' for e, _ in EVENTS))

print(json.dumps({'passed': sum(RESULTS), 'total': len(RESULTS)}))
sys.exit(0 if all(RESULTS) else 1)
