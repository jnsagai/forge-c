"""Operational gate evidence and deterministic refusals remain distinct from product defects."""
import json

import pytest
from forge_factory.afo import diagnosis_packet as D
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import visit as V


@pytest.mark.parametrize('phase', ['SWE.1', 'SWE.2', 'SWE.6'])
def test_missing_inspection_is_a_hash_bound_operational_objective(tmp_path, monkeypatch, phase):
    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path / 'state'))
    ws = tmp_path / 'ws'
    log = ws / '.forge-run/gates/gate-log.jsonl'
    log.parent.mkdir(parents=True)
    rows = [{'result': 'FROZEN'}, {'phase': phase, 'step': 'inspect', 'agent_status': 'FAILED',
             'gate': {'phase': phase, 'decision': 'REINSPECT', 'reason': 'NO_INSPECTION_FOR_CURRENT_BASELINE'}},
            {'phase': phase, 'step': 'route', 'gate': {'phase': phase, 'decision': 'BLOCKED',
             'reason': 'rework budget exhausted'}}]
    log.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    bundle = dict(bundle_id='incident', order_id='order', attempt_id='attempt', phase=phase, fingerprint='failed')
    packet = D.load(D.build(ws, bundle))
    assert packet['complete'] and len(packet['obligations']) == 2
    assert {f['detail'] for f in packet['findings']} == {'NO_INSPECTION_FOR_CURRENT_BASELINE', 'rework budget exhausted'}
    assert all(f['category'] == 'NATIVE_GATE_STATE' for f in packet['findings'])
    for finding in packet['findings']:
        artifact = next(a for a in packet['artifacts'] if a['path'] == finding['source_ref'])
        assert artifact['sha256'] == finding['source_sha256']
        assert 'NO_INSPECTION_FOR_CURRENT_BASELINE' in D.evidence(packet, artifact['ref'], role=packet['role'], phase=phase)


def packet(*_):
    return {'input_hash': 'frozen', 'model': 'fixture', 'accounting': {}}


@pytest.mark.parametrize('error,expected_calls', [
    ('CALL_REFUSED:JOB_TOKEN_ENVELOPE_EXHAUSTED', 1),
    ('CALL_REFUSED:MISSION_REQUESTS_EXHAUSTED', 1),
    ('CALL_REFUSED:REQUEST_NOT_AUTHORIZED', 1),
    ('CALL_REFUSED:INFERENCE_REQUEST_BUSY', 3),
])
def test_administrative_refusals_are_not_repaired_as_model_answers(tmp_path, monkeypatch, error, expected_calls):
    seen = []
    monkeypatch.setattr(S, 'schema_mode_for', lambda _: ('json_schema', 'fixture'))

    def call(*a, **kw):
        seen.append(1)
        return dict(doc=None, errors=[error], usage=None, wall_ms=0, finish_reason=None)

    monkeypatch.setattr(S, 'call', call)
    budget = dict(calls=0, max_calls=10)
    result = V.run_task(tmp_path, 'SWE.1', 'inspect:one', packet, lambda _: [], budget)
    assert len(seen) == expected_calls == budget['calls']
    assert result['status'] == 'INVALID' and result['errors'] == [error]
    assert json.loads(V._ckpt(tmp_path, 'SWE.1', 'inspect:one').read_text()) == result
    # A large rejected packet does not prove a smaller subsequent packet unfit.
    V.run_task(tmp_path, 'SWE.1', 'inspect:other', packet, lambda _: [], budget)
    assert len(seen) == expected_calls * 2


def test_a_transport_failure_is_an_outage_not_a_repair_attempt(tmp_path, monkeypatch):
    """CAPA-122: CALL_FAILED (nothing answered) is waited out and retried on the bounded outage schedule; it is no
    visit call, the checkpoint is untouched and the visit ends on INFRA_UNAVAILABLE:MODEL_CALLS_REFUSED."""
    from forge_factory.inspection import outage

    seen, slept = [], []
    monkeypatch.setattr(S, 'schema_mode_for', lambda _: ('json_schema', 'fixture'))
    monkeypatch.setattr(V.time, 'sleep', slept.append)
    monkeypatch.setattr(S, 'call', lambda *a, **kw: seen.append(1) or dict(
        doc=None, errors=['CALL_FAILED:temporary network failure'], usage=None, wall_ms=0, finish_reason=None))
    budget = dict(calls=0, max_calls=10)
    result = V.run_task(tmp_path, 'SWE.1', 'inspect:one', packet, lambda _: [], budget)
    assert len(seen) == 1 + len(outage.wait_steps()) and slept == outage.wait_steps() and budget['calls'] == 0
    assert result['status'] == 'INVALID' and outage.all_outage(result['errors'])
    assert not V._ckpt(tmp_path, 'SWE.1', 'inspect:one').exists()
    V.run_task(tmp_path, 'SWE.1', 'inspect:other', packet, lambda _: [], budget)
    assert len(seen) == 1 + len(outage.wait_steps())  # no further call once the visit declared the outage
