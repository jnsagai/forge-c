"""Git message cleanup cannot strand an already-committed, hash-bound model submission."""
# ruff: noqa: F811
import json
from pathlib import Path

import pytest
from forge_factory.afo import maintainer as M
from test_afo_m5_maintainer import SIG, _case, _good_candidate, _head, factory  # noqa: F401

SUMMARY = 'word ' * 40 + 'TAIL'
REPRO = M.CANDIDATE_TESTS + 'rpr_calc.py'


@pytest.mark.parametrize('summary', [SUMMARY, ' ' * 16])
def test_truncating_a_model_summary_at_a_space_still_commits_exactly_once(factory, summary):
    case = _case(factory)
    _good_candidate(case)
    sub = M.submit(case, summary, REPRO, SIG)
    intent = json.loads((M.case_dir(case['proposal_id']) / 'submission-intent.json').read_text())
    assert not intent['message'].endswith(' ')
    assert sub['candidate'] == _head(Path(case['src']))
    assert M.submit(case, summary, REPRO, SIG) == sub
    assert M._git('rev-list', '--count', case['base'] + '..HEAD', cwd=Path(case['src'])).strip() == '1'


def pending_after_commit(factory, monkeypatch):
    case = _case(factory)
    _good_candidate(case)
    original = M._git

    def fail_after_commit(*args, **kw):
        if args[:2] == ('show', '-s'):
            raise OSError('SYNTHETIC_COMMIT_OBSERVATION_FAILURE')
        return original(*args, **kw)

    with monkeypatch.context() as stopped:
        stopped.setattr(M, '_git', fail_after_commit)
        with pytest.raises(OSError, match='SYNTHETIC_COMMIT_OBSERVATION_FAILURE'):
            M.submit(case, SUMMARY, REPRO, SIG)
    path = M.case_dir(case['proposal_id']) / 'submission-intent.json'
    intent = json.loads(path.read_text())
    # Exact legacy serialization: normalized summary clipped at200 ended in one space.
    intent['message'] = intent['message'].rstrip(' ') + ' '
    path.chmod(0o600)
    path.write_text(json.dumps(intent))
    path.chmod(0o400)
    return case, path, intent


def test_legacy_committed_intent_is_reconciled_without_rewrite_or_second_commit(factory, monkeypatch):
    case, path, intent = pending_after_commit(factory, monkeypatch)
    before = path.read_bytes()
    head = _head(Path(case['src']))
    assert not (path.parent / 'submission-receipt.json').exists()
    sub = M.submit(case, SUMMARY, REPRO, SIG)
    assert sub['candidate'] == head and _head(Path(case['src'])) == head
    assert path.read_bytes() == before and json.loads(before) == intent
    assert M.submission(case, require_receipt=True)[0] == sub
    assert M.submit(case, SUMMARY, REPRO, SIG) == sub
    with pytest.raises(M.MaintainerDenied, match='SUBMISSION_REPLAY_CHANGED'):
        M.submit(case, SUMMARY + ' changed', REPRO, SIG)


@pytest.mark.parametrize('field', ['parent', 'tree', 'message'])
def test_normalization_does_not_accept_changed_parent_tree_or_message_content(factory, monkeypatch, field):
    case, path, intent = pending_after_commit(factory, monkeypatch)
    intent[field] = '0' * 40 if field != 'message' else intent['message'].replace('candidate', 'forged candidate', 1)
    path.chmod(0o600)
    path.write_text(json.dumps(intent))
    before = _head(Path(case['src']))
    with pytest.raises(M.MaintainerDenied, match='SUBMISSION_COMMIT_MISMATCH'):
        M.submit(case, SUMMARY, REPRO, SIG)
    assert _head(Path(case['src'])) == before
    assert not (path.parent / 'submission-receipt.json').exists()
