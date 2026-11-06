"""CONTROL current known-authority loss; signed TEST M3 grant and no inference.

The external host-readiness leaf is a private fixture. It represents a healthy
volume with just the previously initialized queue lost. This is not a live
fault, service drill, restore, namespace or role qualification.
"""
import hashlib
import sqlite3

import pytest
from forge_factory.afo import host
from forge_factory.afo.durable import digest
from forge_factory.afo.queue import QueueError, Store

from test_line_conductor_m3 import env, grant, placer  # noqa: F401


def test_durable_empty_campaign_cycle_cannot_reinitialize_a_lost_known_queue(env, monkeypatch):
    queue = env['tmp'] / 'state/supervisor/line-queue.sqlite3'
    original = Store(queue)
    with original.tx() as c:
        c.execute('INSERT INTO afo_independent_decisions VALUES (?,?,?,?)',
                  ('CONTROL_OLD_AUTHORITY', 'CONTROL', '{}', digest({})))
    grant(env)  # normal generated TEST key and actual signature verification
    actor = placer(env)
    monkeypatch.setenv('FORGE_DURABLE_AUTONOMY', '1')
    monkeypatch.setattr(host, 'preflight', lambda: {'ok': True})  # CONTROL volume/host leaf, not authority
    queue.unlink()  # private storage loss only, no production path or mutation
    result = actor.cycle()
    assert not env['line'].launched
    assert result['mode'] in {'ACTING', 'OBSERVING'}
    assert not queue.exists(), 'known durable authority loss was silently replaced by an empty Store'


@pytest.mark.parametrize('durable', [False, True])
def test_known_queue_loss_is_not_a_new_bootstrap_even_if_runtime_flag_changes(env, monkeypatch, durable):
    queue = env['tmp'] / 'state/supervisor/line-queue.sqlite3'
    Store(queue)
    actor = placer(env)
    grant(env)
    monkeypatch.setattr(host, 'preflight', lambda: {'ok': True})  # CONTROL readiness leaf
    if durable:
        monkeypatch.setenv('FORGE_DURABLE_AUTONOMY', '1')
    queue.unlink()
    before = set(env['tmp'].rglob('*'))
    result = actor.cycle()
    assert result['mode'] == 'OBSERVING' and result['error'] == 'AUTHORITATIVE_DATABASE_UNAVAILABLE'
    assert result['storage'] == {'status': 'BLOCKED', 'initialized': False}
    assert result['gpu']['busy'] is True and result['gpu']['reason'] == 'AUTHORITATIVE_STORAGE_UNKNOWN'
    assert not queue.exists() and set(env['tmp'].rglob('*')) == before
    assert not env['line'].launched


def test_fresh_durable_consumer_cannot_initialize_missing_authority(env, monkeypatch):
    grant(env)
    monkeypatch.setenv('FORGE_DURABLE_AUTONOMY', '1')
    monkeypatch.setattr(host, 'preflight', lambda: {'ok': True})  # CONTROL readiness leaf
    actor = placer(env)
    result = actor.cycle()
    assert result['error'] == 'AUTHORITATIVE_DATABASE_UNAVAILABLE'
    assert not actor.queue_path.exists() and not env['line'].launched


def test_rebound_valid_empty_store_is_not_the_original_authority(env):
    queue = env['tmp'] / 'state/supervisor/line-queue.sqlite3'
    old = Store(queue)
    with old.tx() as c:
        c.execute('INSERT INTO afo_independent_decisions VALUES (?,?,?,?)',
                  ('CONTROL_ORIGINAL', 'CONTROL', '{}', digest({})))
    actor = placer(env)
    preserved = queue.with_name('preserved-original.sqlite3')
    queue.rename(preserved)
    original = hashlib.sha256(preserved.read_bytes()).hexdigest()
    Store(queue)  # deliberate private wrong-inode counterexample, not a repair API
    replacement = hashlib.sha256(queue.read_bytes()).hexdigest()
    grant(env)
    result = actor.cycle()
    assert result['error'] == 'AUTHORITATIVE_DATABASE_IDENTITY_CHANGED'
    assert hashlib.sha256(queue.read_bytes()).hexdigest() == replacement
    assert hashlib.sha256(preserved.read_bytes()).hexdigest() == original
    with sqlite3.connect(preserved) as c:
        assert c.execute('SELECT record FROM afo_independent_decisions WHERE decision_id=?',
                         ('CONTROL_ORIGINAL',)).fetchone() == ('{}',)
    assert not env['line'].launched


def test_corrupt_known_file_is_not_migrated_into_new_authority(env):
    queue = env['tmp'] / 'state/supervisor/line-queue.sqlite3'
    Store(queue)
    actor = placer(env)
    queue.write_bytes(b'CONTROL_CORRUPT_STORAGE')
    grant(env)
    result = actor.cycle()
    assert result['error'] == 'AUTHORITATIVE_DATABASE_UNAVAILABLE'
    assert queue.read_bytes() == b'CONTROL_CORRUPT_STORAGE' and not env['line'].launched


def test_loss_after_initial_cycle_readiness_cannot_reinitialize_at_learning(env, monkeypatch):
    queue = env['tmp'] / 'state/supervisor/line-queue.sqlite3'
    Store(queue)
    grant(env)
    actor = placer(env)
    records = actor._records

    def lose_during_observation(*args):
        result = records(*args)
        queue.unlink()  # private storage failure after the initial fence
        return result

    monkeypatch.setattr(actor, '_records', lose_during_observation)
    result = actor.cycle()
    assert result['mode'] == 'ACTING'  # historical cycle decision, not a successful learning claim
    assert not queue.exists() and not env['line'].launched
    import json
    learning = json.loads((queue.parent / 'line-learning.json').read_bytes())
    assert learning['status'] == 'CAPTURE_FAILED' and learning['code'] == 'AUTHORITATIVE_DATABASE_UNAVAILABLE'


def test_explicit_legacy_first_bootstrap_still_uses_normal_store(env):
    grant(env)
    actor = placer(env)
    assert not actor.queue_path.exists()
    result = actor.cycle()
    assert result['mode'] == 'ACTING' and actor.queue_path.exists()
    assert not env['line'].launched
    with actor._store().tx() as c:
        assert c.execute('SELECT COUNT(*) FROM afo_work_orders').fetchone()[0] == 0
        assert c.execute('SELECT COUNT(*) FROM afo_missions').fetchone()[0] == 0


def test_observe_only_first_cycle_never_initializes_authority(env):
    actor = placer(env)  # no TEST grant
    result = actor.cycle()
    assert result['mode'] == 'OBSERVING'
    assert not actor.queue_path.exists() and not env['line'].launched


def test_volume_refusal_preserves_existing_database_and_creates_no_fallback(env, monkeypatch):
    queue = env['tmp'] / 'state/supervisor/line-queue.sqlite3'
    Store(queue)
    before = hashlib.sha256(queue.read_bytes()).hexdigest()
    grant(env)
    actor = placer(env)
    monkeypatch.setenv('FORGE_DURABLE_AUTONOMY', '1')
    monkeypatch.setattr(host, 'preflight', lambda: {'ok': False, 'issues': ['CONTROL_READ_ONLY_OR_MISSING']})
    result = actor.cycle()
    assert result['error'] == 'DURABLE_DATA_VOLUME_NOT_READY'
    assert hashlib.sha256(queue.read_bytes()).hexdigest() == before
    assert not (queue.parent / 'act.lock').exists() and not env['line'].launched


def test_normal_intake_transaction_rechecks_cached_identity(env):
    queue = env['tmp'] / 'state/supervisor/line-queue.sqlite3'
    Store(queue)
    actor = placer(env)
    consumer = actor._store()
    queue.unlink()
    with pytest.raises(QueueError, match='AUTHORITATIVE_DATABASE_UNAVAILABLE'):
        # The actual existing Store's connection fence is still active; this
        # does not authorize new accounting, intake or a replacement queue.
        with consumer.tx():
            pytest.fail('lost authority must refuse before a writer exists')
    assert not queue.exists()
