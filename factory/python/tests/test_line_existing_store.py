"""Consumers of prior M3 authority cannot initialize or replace its database."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace

import pytest


def runtime_contrast(root):
    from forge_factory.afo import line_recovery_worker as W, line_recovery_runtime as R
    from forge_factory.afo import line_recovery_product as P
    from forge_factory.afo import line_maintenance_coordinator as M
    from forge_factory.afo.durable import Refused
    from forge_factory.afo.queue import Store

    old_state = os.environ.get('FORGE_STATE_DIR')
    old_scope = os.environ.get('FORGE_AFO_QUEUE_SCOPE')
    old_durable = os.environ.pop('FORGE_DURABLE_AUTONOMY', None)
    cid = 'afo-cmd-' + 'a' * 20
    observations = {}
    try:
        for name in ('bootstrap', 'step', 'refusal', 'authorize', 'native_job', 'product_claim',
                     'product_context', 'product_parameters', 'maintainer_review', 'implicit_native_store'):
            stack = root / name / 'stack'
            state = stack / 'state'
            os.environ['FORGE_STATE_DIR'] = str(state)
            os.environ['FORGE_AFO_QUEUE_SCOPE'] = 'line-local'
            cfg = SimpleNamespace(stack_root=stack)
            old_validate, old_payload = P.validate_launch_order, P.payload
            # Immutable payload/argument parsing is an explicit leaf fixture;
            # actual queue construction and subsequent binding refusal are used.
            P.validate_launch_order = lambda *_: {'job_id': 'fixture-job'}
            P.payload = lambda *_: {'job_id': 'fixture-job', 'order': {'fixture': True}}
            calls = {
                'bootstrap': lambda: W.bootstrap(cid, cfg=cfg),
                'step': lambda: W.step(cid),
                'refusal': lambda: W.record_refusal(cid, Refused('ISOLATED_FIXTURE_ONLY')),
                'authorize': lambda: R.authorize({'order_id': 'unregistered'}),
                'native_job': lambda: R.native_job('unregistered', 'fixture-job'),
                'product_claim': lambda: P.claim_for_launch(cfg, object()),
                'product_context': lambda: P.execution_context(object()),
                'product_parameters': lambda: P.native_parameters('fixture', 'a' * 64, {'fixture': True}),
                'maintainer_review': lambda: M.main(['review', '--job', 'fixture-job', '--epoch', '1']),
                'implicit_native_store': lambda: Store(),
            }
            try:
                returned = calls[name]()
                reason = 'RETURNED_FALSE' if returned is False else 'RETURNED_WITHOUT_EXCEPTION'
            except Exception as exc:
                reason = getattr(exc, 'code', type(exc).__name__)
            finally:
                P.validate_launch_order, P.payload = old_validate, old_payload
            path = state / 'supervisor/line-queue.sqlite3'
            observations[name] = {'created_database': path.exists(), 'reason': reason}
    finally:
        for key, value in [('FORGE_STATE_DIR', old_state), ('FORGE_AFO_QUEUE_SCOPE', old_scope),
                           ('FORGE_DURABLE_AUTONOMY', old_durable)]:
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return observations


def test_actual_runtime_consumers_refuse_before_creation(tmp_path):
    result = runtime_contrast(tmp_path)
    assert all(not item['created_database'] for item in result.values()), result
    assert all(item['reason'].startswith('AUTHORITATIVE_DATABASE_') for item in result.values()), result


def test_explicit_m3_initialization_then_existing_consumer_preserves_records(tmp_path):
    from forge_factory.afo.queue import Store

    path = tmp_path / 'line-queue.sqlite3'
    initial = Store(path)
    with initial.tx() as c:
        c.execute('CREATE TABLE fixture_marker(value TEXT)')
        c.execute("INSERT INTO fixture_marker VALUES ('retained prior M3 authority')")
    reader = Store(path, must_exist=True)
    with reader.tx() as c:
        assert c.execute('SELECT value FROM fixture_marker').fetchone()[0] == 'retained prior M3 authority'
    assert reader.schema_version() == initial.schema_version()


@pytest.mark.parametrize('kind', ['missing', 'symlink', 'empty', 'foreign_sqlite'])
def test_no_migration_or_initialization_of_unavailable_store(tmp_path, kind):
    import sqlite3
    from forge_factory.afo.queue import Store, QueueError

    path = tmp_path / 'nested/queue.sqlite3'
    if kind != 'missing':
        path.parent.mkdir()
    if kind == 'symlink':
        path.symlink_to(tmp_path / 'missing-target.sqlite3')
    elif kind == 'empty':
        path.touch()
    elif kind == 'foreign_sqlite':
        c = sqlite3.connect(path)
        c.execute('CREATE TABLE unrelated(value TEXT)')
        c.commit()
        c.close()
    prior = path.read_bytes() if path.is_file() and not path.is_symlink() else None
    with pytest.raises(QueueError, match='AUTHORITATIVE_DATABASE_'):
        Store(path, must_exist=True)
    if kind == 'missing':
        assert not path.parent.exists()
    if kind == 'symlink':
        assert not path.resolve().exists()
    if prior is not None:
        assert path.read_bytes() == prior


def test_every_connection_refuses_removed_or_replaced_identity(tmp_path):
    from forge_factory.afo.queue import Store, QueueError

    path = tmp_path / 'queue.sqlite3'
    Store(path)
    reader = Store(path, must_exist=True)
    path.rename(tmp_path / 'original.sqlite3')
    with pytest.raises(QueueError, match='AUTHORITATIVE_DATABASE_'):
        reader.connect()
    assert not path.exists()
    Store(path)
    with pytest.raises(QueueError, match='AUTHORITATIVE_DATABASE_IDENTITY_CHANGED'):
        reader.connect()


def test_loss_between_precheck_and_sqlite_open_cannot_create(tmp_path, monkeypatch):
    from forge_factory.afo import queue

    path = tmp_path / 'queue.sqlite3'
    queue.Store(path)
    reader = queue.Store(path, must_exist=True)
    connect = queue.sqlite3.connect

    def removed(*args, **kwargs):
        path.unlink()
        return connect(*args, **kwargs)

    monkeypatch.setattr(queue.sqlite3, 'connect', removed)
    with pytest.raises(queue.QueueError, match='AUTHORITATIVE_DATABASE_UNAVAILABLE'):
        reader.connect()
    assert not path.exists()


def main():
    with tempfile.TemporaryDirectory(prefix='rpr157-line-authority-') as temporary:
        result = runtime_contrast(Path(temporary))
        print(json.dumps({'fixture_only': True, 'model_calls': 0, 'runtime_consumers': result}))
        if any(item['created_database'] for item in result.values()):
            print('SYMPTOM_PRESENT:line recovery consumers create missing authoritative M3 database')
            return 1
        if not all(item['reason'].startswith('AUTHORITATIVE_DATABASE_') for item in result.values()):
            print('REPRODUCER_ERROR:actual consumer construction was not reached')
            return 2
    print('SYMPTOM_ABSENT')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
