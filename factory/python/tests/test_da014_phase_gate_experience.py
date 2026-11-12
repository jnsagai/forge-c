"""Learn factual blocked phase outcomes even when no inspector record exists."""
import json

import pytest
from forge_factory.knowledge import experience as E
from forge_factory.knowledge.store import LessonStore


@pytest.mark.parametrize('outcome', ['PASS', 'BLOCKED'])
def test_native_phase_gate_capture_is_deduplicated_with_a_durable_disposition(tmp_path, outcome):
    ws = tmp_path / 'ws'
    log = ws / '.forge-run/gates/gate-log.jsonl'
    log.parent.mkdir(parents=True)
    (log.parent.parent / 'manifest.json').write_text(json.dumps({'evaluation_holdout': True}))
    row = {'phase': 'SWE.1', 'step': 'route', 'ts': '2026-10-28T09:00:00Z',
           'gate': {'decision': outcome, 'reason': 'Private evidence is not copied into the learning record.'}}
    log.write_text(json.dumps(row) + '\n')
    memory = LessonStore(tmp_path / 'lessons.sqlite3')
    first = E.capture_workspace(memory, ws, 'native-one')
    assert len(first) == 1 and E.capture_workspace(memory, ws, 'native-one') == first
    with memory._conn() as c:
        record = json.loads(c.execute('SELECT record FROM job_experience').fetchone()[0])
        assert c.execute('SELECT count(*) FROM job_experience').fetchone()[0] == 1
        assert c.execute('SELECT state FROM learning_dispositions').fetchone()[0] == 'PENDING'
    assert record['phase'] == 'SWE.1' and record['outcome'] == outcome
    assert record['facts']['record_kind'] == 'NATIVE_PHASE_GATE'
    assert record['cohort']['evaluation_holdout'] is True
    assert 'Private evidence' not in json.dumps(record)
    E.consolidate(memory)
    assert E.report(memory)['dispositions'] == {'NO_NEW_LESSON' if outcome == 'PASS' else 'DEFERRED_BUDGET': 1}
    # A changed observation appends; the old event and its disposition remain.
    row['gate']['decision'] = 'BLOCKED' if outcome == 'PASS' else 'PASS'
    with log.open('a') as stream:
        stream.write(json.dumps(row) + '\n')
    E.capture_workspace(memory, ws, 'native-one')
    assert E.report(memory)['unique_experiences'] == 2


def test_unfinished_unknown_or_nonroute_rows_cannot_invent_a_phase_result(tmp_path):
    ws = tmp_path / 'ws'
    log = ws / '.forge-run/gates/gate-log.jsonl'
    log.parent.mkdir(parents=True)
    rows = [[], {'phase': 'SWE.9', 'step': 'route', 'gate': {'decision': 'PASS'}},
            {'phase': 'SWE.1', 'step': 'author', 'result': 'FROZEN'},
            {'phase': 'SWE.1', 'step': 'route', 'gate': {'decision': 'REINSPECT'}},
            {'phase': 'SWE.1', 'step': 'route', 'gate': {'phase': 'SWE.2', 'decision': 'PASS'}},
            {'phase': 'SWE.1', 'step': 'route', 'gate': 'PASS'}]
    prefix = ''.join(json.dumps(r) + '\n' for r in rows)
    log.write_text(prefix + '{"phase":')
    memory = LessonStore(tmp_path / 'lessons.sqlite3')
    assert E.capture_workspace(memory, ws, 'native-one') == []
    assert E.report(memory)['unique_experiences'] == 0
    log.write_text(prefix + json.dumps({'phase': 'SWE.1', 'step': 'route', 'gate': {'decision': 'BLOCKED'}}) + '\n')
    assert len(E.capture_workspace(memory, ws, 'native-one')) == 1
