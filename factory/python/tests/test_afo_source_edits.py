"""Localized edits preserve unrelated Qwen bytes and obey the existing broker/sealing boundary."""
# ruff: noqa: F811
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from forge_factory.afo import maintainer as M
from forge_factory.mcp.servers import maintainer as server
from forge_factory.registry.agents import preflight
from test_afo_m5_maintainer import factory  # noqa: F401


@pytest.fixture
def case(factory):
    return M.prepare('mnt-edits-a1', 'HEAD', {'reason': 'Synthetic source edit fixture'}, factory)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def test_exact_edit_preserves_crlf_unicode_and_unrelated_bytes(case):
    rel = 'factory/python/forge_factory/calc.py'
    raw = b'# caf\xc3\xa9\r\ndef answer():\r\n    return 1\r\n# untouched\r\n'
    path = Path(case['src']) / rel
    path.write_bytes(raw)
    result = M.edit_source(case, rel, sha(raw), 'return 1', 'return 2')
    expected = raw.replace(b'return 1', b'return 2')
    assert path.read_bytes() == expected and result == sha(expected)
    assert not list(path.parent.glob('.afo-source-*'))
    with pytest.raises(M.MaintainerDenied, match='SOURCE_EDIT_STALE'):
        M.edit_source(case, rel, sha(raw), 'return 1', 'return 2')
    assert path.read_bytes() == expected


@pytest.mark.parametrize('old,new,code', [
    ('', 'x', 'INVALID'), ('return', 'return', 'INVALID'), ('missing', 'x', 'ANCHOR_NOT_UNIQUE'),
    ('x' * 8193, 'y', 'INVALID'), ('return', '\u00e9' * 4097, 'INVALID')])
def test_invalid_edit_is_side_effect_free(case, old, new, code):
    rel = 'factory/python/forge_factory/calc.py'
    path = Path(case['src']) / rel
    raw = path.read_bytes()
    with pytest.raises(M.MaintainerDenied, match=code):
        M.edit_source(case, rel, sha(raw), old, new)
    assert path.read_bytes() == raw


def test_repeated_anchor_is_not_guessed_and_deletion_is_exact(case):
    rel = 'factory/python/forge_factory/calc.py'
    path = Path(case['src']) / rel
    path.write_bytes(b'keep\nremove\nkeep\n')
    raw = path.read_bytes()
    with pytest.raises(M.MaintainerDenied, match='ANCHOR_NOT_UNIQUE'):
        M.edit_source(case, rel, sha(raw), 'keep', 'other')
    M.edit_source(case, rel, sha(raw), 'remove\n', '')
    assert path.read_bytes() == b'keep\nkeep\n'


@pytest.mark.parametrize('rel', ['factory/python/forge_factory/afo/policy.py',
                                'tests/reliability/reproducers/manifest.yaml', '../escape.py'])
def test_edit_cannot_expand_existing_source_scope(case, rel):
    with pytest.raises(M.MaintainerDenied):
        M.edit_source(case, rel, 'a' * 64, 'x', 'y')


def test_edit_refuses_symlink_and_size_overflow(case):
    rel = 'factory/python/forge_factory/link.py'
    (Path(case['src']) / rel).symlink_to('calc.py')
    with pytest.raises(M.MaintainerDenied, match='SYMLINK'):
        M.edit_source(case, rel, 'a' * 64, 'x', 'y')
    rel = 'factory/python/forge_factory/calc.py'
    path = Path(case['src']) / rel
    raw = b'a' * (M.MAX_FILE_BYTES - 1) + b'X'
    path.write_bytes(raw)
    with pytest.raises(M.MaintainerDenied, match='FILE_TOO_LARGE'):
        M.edit_source(case, rel, sha(raw), 'X', 'YZ')
    assert path.read_bytes() == raw


def test_sealed_submission_freezes_both_edit_interfaces(case):
    directory = M.case_dir(case['proposal_id'])
    (directory / 'submission-intent.json').write_text('{}')
    rel = 'factory/python/forge_factory/calc.py'
    raw = (Path(case['src']) / rel).read_bytes()
    for operation in (lambda: M.write_source(case, rel, 'other'),
                      lambda: M.edit_source(case, rel, sha(raw), 'return', 'yield')):
        with pytest.raises(M.MaintainerDenied, match='CASE_ALREADY_SUBMITTED'):
            operation()
    assert (Path(case['src']) / rel).read_bytes() == raw


def test_compare_and_replace_has_only_one_effective_concurrent_writer(case):
    rel = 'factory/python/forge_factory/calc.py'
    path = Path(case['src']) / rel
    raw = path.read_bytes()
    barrier = Barrier(2)

    def edit(value):
        barrier.wait()
        try:
            return M.edit_source(case, rel, sha(raw), 'return a - b', value)
        except M.MaintainerDenied as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, ['return a + b', 'return a * b']))
    assert sum(len(x) == 64 for x in results) == 1
    assert any(x in ('SOURCE_EDIT_STALE', 'SOURCE_EDIT_BUSY') for x in results)
    assert path.read_bytes() in (raw.replace(b'return a - b', b'return a + b'),
                                raw.replace(b'return a - b', b'return a * b'))


def test_atomic_write_failure_preserves_original_bytes(case, monkeypatch):
    rel = 'factory/python/forge_factory/calc.py'
    path = Path(case['src']) / rel
    raw = path.read_bytes()

    def fail(*args):
        raise OSError('SYNTHETIC_REPLACE_FAILURE')

    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(OSError, match='SYNTHETIC_REPLACE_FAILURE'):
        M.edit_source(case, rel, sha(raw), 'return a - b', 'return a + b')
    assert path.read_bytes() == raw and not list(path.parent.glob('.afo-source-*'))


def test_tool_schema_and_role_registration_are_consistent():
    from forge_factory.registry.skillgen import ROLE_SPECIFIC

    assert 'edit_source' in ' '.join(ROLE_SPECIFIC['afo-factory-maintainer'])
    schema = server.EditIn.model_json_schema()['properties']
    assert schema['expected_sha256']['pattern'] == '^[0-9a-f]{64}$'
    assert schema['old_text']['minLength'] == 1 and schema['new_text']['maxLength'] == 8192
    assert preflight(['afo-factory-maintainer'], include_afo=True)['status'] == 'PASS'
