"""Private kernel/process/SQLite controls; not native/model role competence."""
import contextlib
import copy
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from forge_factory.afo import owner_bootstrap_history as H
from forge_factory.afo import owner_profile_bootstrap as B
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused, canonical, digest
from forge_factory.afo.line_launcher import LineConfig, ShellHost
from forge_factory.afo.line_orders import Placer
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.lrtx import stack
from test_owner_supervised_development import supervised  # noqa: F401 - real private guardian fixture


def native_database(path, statuses=("succeeded", "failed")):
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as c:
        for table, columns in H.TABLE_COLUMNS.items():
            parts = ['"'+name+'" '+kind for name, kind, _ in columns]
            pk = [name for name, _, k in sorted(columns, key=lambda x: x[2]) if k]
            if pk:
                parts += ['PRIMARY KEY('+','.join('"'+name+'"' for name in pk)+')']
            c.execute('CREATE TABLE "'+table+'"('+','.join(parts)+')')
        c.execute('INSERT INTO legacy_run_history_activation(singleton) VALUES(1)')
        for n, status in enumerate(statuses):
            c.execute('INSERT INTO runs(id,status) VALUES(?,?)', ('PRIVATE-'+str(n), status))


class NativeClient:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def _get(self, _, **params):
        if params.get('status') == 'removing':
            return {'data': [], 'meta': {'total': 0, 'has_more': False}}
        with sqlite3.connect(self.path) as c:
            data = [{'id': rid, 'lifecycle': {'status': {'kind': status}}}
                    for rid, status in c.execute('SELECT id,status FROM runs ORDER BY id')]
        offset = params['page[offset]']
        return {'data': data[offset:offset+100], 'meta': {'total': len(data), 'has_more': offset+100 < len(data)}}


@pytest.fixture
def boot(supervised, tmp_path, monkeypatch):
    store = supervised['store']
    root = store.path.parents[2]
    (root/'run').mkdir()
    lock = root/'gpu.lock'
    lock.write_text('')
    lock.chmod(0o600)
    native = root/'fabro/storage/db/fabro.sqlite3'
    native_database(native)
    monkeypatch.setenv('FORGE_LRTX_ROOT', str(root))
    monkeypatch.setenv('FORGE_OPERATIONS_PROFILE', D.PROFILE)
    monkeypatch.setenv('FORGE_DURABLE_AUTONOMY', '1')
    # Only the external volume and fixed deployment path leaves are private TEST layout.
    monkeypatch.setattr('forge_factory.afo.host.preflight', lambda: {'ok': True})
    monkeypatch.setattr(B, 'GPU_LOCK', lock)
    cfg = LineConfig(launch_dir=root, stack_root=root, gpu_lock=lock)
    monkeypatch.setattr(LineConfig, 'from_env', classmethod(lambda cls: cfg))
    monkeypatch.setattr(ShellHost, '_client', lambda self: NativeClient(native))
    placer = Placer(object(), policy_path=supervised['line'], owner_supervised_development=True)
    children, effects = [], []

    def start(settings, *, recovery, control_only=False):
        assert settings['root'] == root and recovery
        stack._guard_effect()
        # An actual owned harmless process marks the physical effect boundary.
        p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        children.append(p)
        effects.append('control' if control_only else 'provider')
        return {'health': {'fabro': True}}

    monkeypatch.setattr(stack, '_start', start)
    monkeypatch.setattr(stack, 'expose_api', lambda *_: {'api_bridge': 'UP'})
    monkeypatch.setattr(stack, 'status', lambda _: {'health': dict.fromkeys(['fabro','ollama','gateway','llama_server'], True)})
    record = D.current()
    instance = {'root': str(root), 'profile': D.PROFILE, 'profile_sha256': D.PROFILE_SHA,
                'owner_development_view': {'record_sha256': digest(record),
                  'socket_identity': record['guardian_socket_identity'], 'store_identity': record['store_identity'],
                  'store_path': record['store_path']}}
    monkeypatch.setattr(stack, 'serving_instance', lambda _: instance)
    yield dict(store=store, placer=placer, root=root, native=native, effects=effects, children=children,
               original=supervised, instance=instance, lock=lock)
    if placer._act_lock:
        placer._act_lock.close()
    for p in children:
        if p.poll() is None:
            p.terminate()
        p.wait(timeout=3)


def test_supported_bootstrap_canonical_store_real_locks_guardian_and_processes(boot):
    store, placer = boot['store'], boot['placer']
    before = MissionLedger(store).snapshot(D.MISSION)
    result = B.bootstrap(store, placer)
    assert result['status'] == 'READY' and result['model_calls'] == result['placed_jobs'] == 0
    assert boot['effects'] == ['control', 'provider'] and all(p.poll() is None for p in boot['children'])
    assert MissionLedger(store).snapshot(D.MISSION) == before
    assert placer._act_lock and not (boot['root']/'state/conductor/conductor.sqlite3').exists()
    assert not store.orders() and not store.commands()
    with store.tx() as c:
        assert c.execute('SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?',(B.INTENT_KIND,)).fetchone()[0] == 1
        assert c.execute('SELECT COUNT(*) FROM afo_independent_decisions WHERE kind=?',(B.RESULT_KIND,)).fetchone()[0] == 1
    fd = os.open(boot['lock'],os.O_RDWR)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)  # temporary GPU fence released, ACT retained
    finally:
        os.close(fd)


@pytest.mark.parametrize('status',['UNKNOWN','PENDING','IN_FLIGHT','UNRECOGNIZED'])
def test_all_uncertain_command_states_refuse_without_effects(boot,status):
    with boot['store'].tx() as c:
        # Exact outbox columns use a copied normal row shape (no execution fabricated).
        columns=[r[1] for r in c.execute('PRAGMA table_info(afo_commands_outbox)')]
        row={k:'' for k in columns}
        row.update(command_id='private-uncertain',order_id='historical',attempt_id='old',kind='OTHER_KIND',state=status)
        c.execute('INSERT INTO afo_commands_outbox('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',
                  [row[k] for k in columns])
    with pytest.raises(Refused,match='COMMAND_OUTCOME_UNRESOLVED'):
        B.bootstrap(boot['store'],boot['placer'])
    assert boot['effects']==[]


@pytest.mark.parametrize('status',['ACKED','FAILED','QUARANTINED'])
def test_inactive_history_is_preserved_not_cancelled_or_reset(boot,status):
    from test_afo_m2_queue import _env
    repo=boot['root']/'repo';(repo/'afo-manifests').mkdir(parents=True)
    oid,_=boot['store'].submit(_env(repo),repo=repo,max_queued=10)
    boot['store'].transition(oid,'PAUSED','Historical inactive order')
    with boot['store'].tx() as c:
        cols=[r[1] for r in c.execute('PRAGMA table_info(afo_commands_outbox)')]
        row={k:'' for k in cols};row.update(command_id='private-ended',order_id=oid,attempt_id='old',kind='FABRO_LAUNCH',state=status)
        c.execute('INSERT INTO afo_commands_outbox('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',[row[k] for k in cols])
    before=boot['store'].order(oid),boot['store'].commands()
    assert B.bootstrap(boot['store'],boot['placer'])['status']=='READY'
    assert (boot['store'].order(oid),boot['store'].commands())==before


@pytest.mark.parametrize('status',['running','queued','removing','aborted','dead','timeout','error',None])
def test_unknown_or_active_native_refuses_before_any_start(boot,status):
    with sqlite3.connect(boot['native']) as c:c.execute('UPDATE runs SET status=? WHERE id=?',(status,'PRIVATE-0'))
    with pytest.raises(Refused,match='NATIVE_NOT_TERMINAL'):
        B.bootstrap(boot['store'],boot['placer'])
    assert boot['effects']==[]


def test_missing_native_db_never_becomes_empty_history(boot):
    boot['native'].unlink()
    with pytest.raises(Refused,match='NATIVE_DB_MISSING'):
        B.bootstrap(boot['store'],boot['placer'])
    assert boot['effects']==[] and not boot['native'].exists()


def test_partial_control_start_writes_unknown_and_revokes_without_retry(boot,monkeypatch):
    def failure(*_,**__):
        stack._guard_effect()
        boot['effects'].append('possible-control-effect')
        raise OSError('PRIVATE simulated post-spawn transport failure')
    monkeypatch.setattr(stack,'_start',failure)
    with pytest.raises(OSError):B.bootstrap(boot['store'],boot['placer'])
    with boot['store'].tx() as c:
        rows=[json.loads(r[0]) for r in c.execute('SELECT record FROM afo_independent_decisions WHERE kind=?',(B.RESULT_KIND,))]
    assert rows[0]['status']=='UNKNOWN_REQUIRES_RECONCILIATION' and rows[0]['no_retry']
    with pytest.raises(Refused):D.current()
    assert boot['effects']==['possible-control-effect'] and not boot['placer']._act_lock


def test_native_change_during_control_start_blocks_provider_before_load(boot,monkeypatch):
    def start(*_,**kwargs):
        stack._guard_effect();boot['effects'].append('control')
        with sqlite3.connect(boot['native']) as c:c.execute("INSERT INTO run_events(run_id,seq) VALUES('PRIVATE-0',1)")
    monkeypatch.setattr(stack,'_start',start)
    with pytest.raises(Refused,match='NATIVE_HISTORY_CHANGED'):B.bootstrap(boot['store'],boot['placer'])
    assert boot['effects']==['control']


def test_control_cancellation_prevents_next_physical_effect(boot,monkeypatch):
    stopped=[False]
    def start(*_,**kwargs):
        stack._guard_effect();boot['effects'].append('control');stopped[0]=True
    monkeypatch.setattr(stack,'_start',start)
    with pytest.raises(Refused,match='CANCELLED'):
        B.bootstrap(boot['store'],boot['placer'],cancelled=lambda:stopped[0])
    assert boot['effects']==['control']


def test_guard_catches_cancel_during_blocking_authorization_before_spawn(boot,monkeypatch):
    from forge_factory.afo import line_recovery_control as C
    original=C.configuration;stopped=[False];calls=[0]
    def delayed(*args,**kw):
        result=original(*args,**kw);calls[0]+=1
        if calls[0]>=4:stopped[0]=True
        return result
    monkeypatch.setattr(C,'configuration',delayed)
    with pytest.raises(Refused):B.bootstrap(boot['store'],boot['placer'],cancelled=lambda:stopped[0])
    assert 'provider' not in boot['effects']


def test_initial_intent_lock_is_nonblocking_and_does_not_change_intent(boot):
    from forge_factory.afo.operations import Intent
    before=Intent().read()
    with Intent().lock():
        with pytest.raises(Refused,match='OPERATIONS_INTENT_BUSY'):
            B.bootstrap(boot['store'],boot['placer'])
    assert Intent().read()==before and not boot['effects']
