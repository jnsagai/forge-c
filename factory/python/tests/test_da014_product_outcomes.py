"""Native success and capacity settlement must not leave failed products ACTIVE."""
# ruff: noqa: F811
import hashlib
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import local_agent, policy, product_job
from forge_factory.afo.execution_lifecycle import Executions
from test_afo_m3_reconcile import admitted  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_overnight_stall import product_setup


def setup(admitted, monkeypatch, *, package='BLOCKED'):
    store, oid, aid, ledger = product_setup(admitted, monkeypatch)
    monkeypatch.setattr(local_agent, 'authorized', lambda *a: True)
    job = product_job.prepare(store, store.order(oid), store.attempts(oid)[0], 'a' * 32,
                              {'model': 'fixture'}, policy.load())
    ex = Executions(store)
    ex.dispatch_intent(job['job_id'])
    ex.adopt(job['job_id'], ['native'])
    p = Path(job['workspace']) / '.forge-run/package.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    if package:
        arc = p.with_name('sealed.zip')
        with zipfile.ZipFile(arc, 'w') as z:
            z.writestr('manifest.json', json.dumps({'status': package, 'gaps': ['test gap'] if package == 'BLOCKED' else []}))
        p.write_text(json.dumps({'archive': str(arc), 'archive_sha256': hashlib.sha256(arc.read_bytes()).hexdigest(),
                                'package_status': package, 'gaps': ['test gap'] if package == 'BLOCKED' else []}))
    client = SimpleNamespace(get_run=lambda _: {'lifecycle': {'status': {'kind': 'SUCCEEDED'}}}, cancel=lambda _: 202)
    return store, oid, ledger, ex, job, client


@pytest.mark.parametrize('settled', [False, True])
def test_native_success_with_blocked_package_is_a_failed_product_even_after_release(admitted, monkeypatch, settled):
    store, oid, ledger, ex, job, client = setup(admitted, monkeypatch)
    if settled:
        assert ex.reconcile(job['job_id'], client)['resource_lease'] == 'RELEASED'
    before = ledger.snapshot('product')['charged_tokens']
    product_job.reconcile(store, policy.load(), client)
    result = ex.get(job['job_id'])
    assert result['task_outcome'] == 'BLOCKED' and result['resource_lease'] == 'RELEASED'
    assert ex._evidence(job['job_id'], 'PRODUCT_FAILURE')['verdict']['verdict'] == 'BLOCKED'
    product_job.reconcile(store, policy.load(), client)
    assert ex.get(job['job_id']) == result and ledger.snapshot('product')['charged_tokens'] == before


def test_failed_product_still_holds_inference_until_provider_request_is_quiet(admitted, monkeypatch):
    store, oid, ledger, ex, job, client = setup(admitted, monkeypatch)
    ledger.reserve_request('product', job['job_id'], 'lost', body_sha256='b' * 64,
                           input_tokens=1, output_cap=1, authorize=lambda: True)
    ledger.start_request('lost', authorize=lambda: True)
    ledger.reconcile_request('lost', quiescent=False)
    product_job.reconcile(store, policy.load(), client)
    result = ex.get(job['job_id'])
    assert result['task_outcome'] == 'BLOCKED' and result['resource_lease'] == 'HELD'
    ledger.reconcile_request('lost', quiescent=True, evidence_ref='independent-provider-proof')
    product_job.reconcile(store, policy.load(), client)
    assert ex.get(job['job_id'])['resource_lease'] == 'RELEASED'


@pytest.mark.parametrize('package', [None, 'READY_FOR_OFFLINE_REVIEW'])
def test_missing_or_ready_package_does_not_invent_verified_recovery(admitted, monkeypatch, package):
    store, oid, ledger, ex, job, client = setup(admitted, monkeypatch, package=package)
    product_job.reconcile(store, policy.load(), client)
    assert ex.get(job['job_id'])['task_outcome'] == 'ACTIVE'
    assert ex._evidence(job['job_id'], 'PRODUCT_FAILURE') is None


def test_terminal_order_blocks_unknown_execution_without_releasing_its_lease(admitted, monkeypatch):
    store, oid, ledger, ex, job, client = setup(admitted, monkeypatch, package=None)
    store.transition(oid, 'BLOCKED', 'bounded job failed', terminal_reason='bounded job failed')
    client.get_run = lambda _: {'lifecycle': {'status': {'kind': 'RUNNING'}}}
    product_job.reconcile(store, policy.load(), client)
    result = ex.get(job['job_id'])
    assert result['task_outcome'] == 'BLOCKED' and result['resource_lease'] == 'HELD'
