"""Actual finite CPU wall and persisted queue controls; no model/role qualification."""
import time
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_maintenance_coordinator as C
from forge_factory.afo.durable import Refused
from forge_factory.afo.verification_job import VerificationJobs
from test_line_maintenance_coordinator import scoped  # noqa: F401


def shorter_mission(scoped, seconds):
    mission = 'mission-earlier-deadline-fixture'
    deadline = time.time() + seconds
    C.MissionLedger(scoped.store).register(mission, mission, {
        'max_attempts': 0, 'max_jobs': 0, 'max_requests': 0, 'max_tokens': 0,
        'max_tools': 0, 'max_corrections': 0, 'deadline': deadline,
    }, 'ISOLATED_CPU_FIXTURE', authorize=lambda *a: True)
    scoped.job['mission_id'] = mission
    return deadline


def test_actual_review_alarm_ends_work_at_earlier_mission_wall(scoped, monkeypatch):
    from forge_factory.afo import completion_receipt, policy
    from forge_factory.reliability import policy as cre_policy

    monkeypatch.setattr(completion_receipt.Context, 'from_job', lambda *a: None)
    monkeypatch.setattr(policy, 'load', lambda: SimpleNamespace())
    monkeypatch.setattr(cre_policy, 'load', lambda: SimpleNamespace())
    monkeypatch.setattr(C.Store, 'proposal', lambda *a: None)
    completed = []

    def work(*a, **k):
        time.sleep(2)
        completed.append(True)
        return {'outcome': 'ELIGIBLE_FOR_OFFLINE_REVIEW', 'auto_deployment_allowed': False}

    monkeypatch.setattr(C.M, 'process', work)
    mission_deadline = shorter_mission(scoped, 1)
    started = time.time()
    with pytest.raises(TimeoutError, match='REVIEW_DEADLINE'):
        C.review(scoped.store, scoped.job, SimpleNamespace(), fence=lambda: True, client=scoped.client)
    assert completed == [] and time.time() - started < 1.75
    assert C._review_deadline(scoped.store, scoped.job) == mission_deadline


def test_preexisting_cpu_queue_wall_is_narrowed_without_reset_or_extension(scoped, monkeypatch):
    deadline = shorter_mission(scoped, 30)
    queue = VerificationJobs(scoped.store)
    queue.ensure(scoped.job['job_id'], scoped.job['case_sha256'], deadline_epoch=scoped.job['deadline_epoch'])
    spawned = []
    monkeypatch.setattr(C.subprocess, 'Popen', lambda *a, **k: spawned.append(a))
    monkeypatch.setattr(C.L, 'execution_context', lambda *a: {})
    C._dispatch_review(scoped.store, scoped.job)
    row = queue.get(scoped.job['job_id'])
    assert row['record']['deadline_epoch'] == deadline and row['record']['dispatches'] == 1
    epoch = row['epoch']
    queue.ensure(scoped.job['job_id'], scoped.job['case_sha256'], deadline_epoch=deadline + 60, cap_deadline=True)
    assert queue.get(scoped.job['job_id']) == row  # no extension, new dispatch or allowance reset
    queue.claim(scoped.job['job_id'], epoch)
    queue.finish(scoped.job['job_id'], epoch, {'status': 'FIXTURE_COMPLETE'})
    completed = queue.get(scoped.job['job_id'])
    queue.ensure(scoped.job['job_id'], scoped.job['case_sha256'], deadline_epoch=deadline - 1, cap_deadline=True)
    assert queue.get(scoped.job['job_id']) == completed  # completed evidence remains historical


@pytest.mark.parametrize('value', [None, True, '2030', float('nan'), float('inf')])
def test_invalid_deadline_never_creates_an_unbounded_capped_verifier(scoped, value):
    queue = VerificationJobs(scoped.store)
    with pytest.raises(Refused, match='DEADLINE_INVALID'):
        queue.ensure(scoped.job['job_id'], scoped.job['case_sha256'], deadline_epoch=value, cap_deadline=True)
    assert queue.get(scoped.job['job_id']) is None


def test_existing_earlier_queue_wall_remains_an_independent_limit(scoped):
    queue = VerificationJobs(scoped.store)
    earlier = time.time() + 0.1
    queue.ensure(scoped.job['job_id'], scoped.job['case_sha256'], deadline_epoch=earlier)
    assert C._review_deadline(scoped.store, scoped.job) == earlier
