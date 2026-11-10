"""Bounded onboarding authoring, fixed subjects and independent hash-bound inspection. No model calls."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from forge_factory.common import REPO_ROOT, canonical_json, sha256_bytes
from forge_factory.mcp.sdk import ToolContext, ToolDenied
from forge_factory.mcp.servers.docs import OnboardingReadIn, read_onboarding_input
from forge_factory.onboarding import authoring as A
from forge_factory.onboarding import facts as F
from forge_factory.onboarding import model_tool as T
from forge_factory.policy.authz import Authorizer, Binding
from forge_factory.registry.agents import load_agents, preflight

MODEL = '# RM test register: fixed reset 7, read-only.\nMODEL_LIMITS = []\nif request.IsRead:\n    request.Value = 7\n'


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path / 'state'))
    ws = tmp_path / 'ws'
    (ws / 'inputs').mkdir(parents=True)
    (ws / 'onboarding/model').mkdir(parents=True)
    pkg = F.assemble('test-case', [{'path': 'inputs/rm.md', 'role': 'rm', 'sha256': '1' * 64}], 'abcdef1', 'LL',
                     [F.derived('register_prefix', 'CRC', 'test', F.Source('doc', 'rm.md'))], [], [], {'derived_from': {}}, {}, [])
    (ws / 'inputs/onboarding-package.json').write_text(json.dumps(pkg))
    (ws / 'inputs/platform.repl').write_text('CRC_MODEL_PATH')
    files = [{'path': 'inputs/' + p.name, 'sha256': sha256_bytes(p.read_bytes())} for p in (ws / 'inputs').iterdir()]
    record = {'key': 'test-case', 'subject': 'a' * 64, 'package_sha256': pkg['sha256'], 'input_files': files,
              'hide_model': 'crc'}
    (ws / 'inputs/case.json').write_text(json.dumps(record))
    (ws / 'onboarding/model/model.py').write_text(MODEL)
    monkeypatch.setattr(T, 'check', lambda *a, **k: {'verdict': 'PASS', 'findings': [], 'limits': [], 'version': 'test'})
    return ws, pkg


def ctx(ws, inspector=False):
    return ToolContext('forge-sim-mcp', 'check_model', A.ROLES[int(inspector)], None, ws, 'test')


def reply(digest, status='PASS'):
    return json.dumps({'status': status, 'artifacts': ['model:sha256:' + digest], 'issues': [], 'next_action': 'next'})


def test_roles_are_opt_in_and_write_scopes_enforced(tmp_path):
    core, _ = load_agents()
    assert len(core) == 20 and not any(r.id in A.ROLES for r in core)
    assert preflight(list(A.ROLES), include_onboarding=True)['status'] == 'PASS'
    az = Authorizer(Binding('onb', str(tmp_path), {'a': {'role': A.ROLES[0]}, 'i': {'role': A.ROLES[1]},
                                                 's': {'role': 'swe3-author', 'phase': 'SWE.3'}}))
    assert az.decide('a', 'write_file', {'path': 'onboarding/model/model.py'}).allow
    for path in ('inputs/a.md', 'onboarding/gate.json', 'onboarding/inspection-model.py', '../model.py'):
        assert not az.decide('a', 'write_file', {'path': path}).allow
    assert not az.decide('i', 'write_file', {'path': 'onboarding/model/model.py'}).allow
    for node in ('a', 'i'):
        assert az.decide(node, 'mcp__forge_sim_mcp__check_model', {}).allow
        assert not az.decide(node, 'shell', {'command': 'true'}).allow
    assert not az.decide('s', 'mcp__forge_sim_mcp__check_model', {}).allow


def test_graph_has_three_distinct_author_gate_inspector_attempts(tmp_path):
    dot, nodes = A.graph(tmp_path)
    assert len(nodes) == 6 and dot.count('backend="acp"') == 6
    for i in range(1, 4):
        assert nodes[f'model_author_{i}']['role'] == A.ROLES[0]
        assert nodes[f'model_inspector_{i}']['role'] == A.ROLES[1]
        assert f'model_author_{i} -> model_gate_{i}' in dot
        assert f'model_gate_{i} -> model_inspector_{i} [condition="outcome=succeeded"]' in dot
    assert '--agent codex' in dot and '--agent claude' in dot
    assert 'model_author_4' not in dot
    binary = os.environ.get('FORGE_FABRO_BIN') or shutil.which('fabro')
    if binary:
        path = tmp_path / 'workflow.fabro'
        path.write_text(dot)
        proc = subprocess.run([binary, 'validate', str(path)], capture_output=True, text=True, timeout=60,
                              env={**os.environ, 'FABRO_NO_UPGRADE_CHECK': '1'})
        assert 'Validation: OK' in proc.stdout + proc.stderr, (proc.stdout + proc.stderr)[-1600:]


def test_author_probe_cannot_replace_frozen_inspection_snapshot(case):
    ws, _ = case
    assert T.run(ctx(ws), freeze=True)['status'] == 'PASS'
    (ws / 'onboarding/model/model.py').write_text(MODEL + '# changed\n')
    T.run(ctx(ws))
    assert (ws / 'onboarding/inspection-model.py').read_text() == MODEL
    assert T.run(ctx(ws, True))['metrics']['model_sha256'] == sha256_bytes(MODEL.encode())


def test_gate_freezes_the_same_bytes_actually_checked(case, monkeypatch):
    ws, _ = case
    def check(*args, model_paths, **kwargs):
        assert model_paths[0].read_text() == MODEL
        (ws / 'onboarding/model/model.py').write_text('# replaced during execution\n')
        return {'verdict': 'PASS', 'findings': [], 'limits': []}
    monkeypatch.setattr(T, 'check', check)
    T.run(ctx(ws), freeze=True)
    assert (ws / 'onboarding/inspection-model.py').read_text() == MODEL


@pytest.mark.parametrize('tamper', ['package', 'platform', 'key', 'snapshot'])
def test_fixed_subject_tampering_is_refused(case, tamper):
    ws, _ = case
    T.run(ctx(ws), freeze=True)
    if tamper == 'snapshot':
        (ws / 'onboarding/inspection-model.py').write_text('# replaced\n')
    else:
        path = ws / ('inputs/platform.repl' if tamper == 'platform' else 'inputs/onboarding-package.json'
                     if tamper == 'package' else 'inputs/case.json')
        if tamper == 'key':
            item = json.loads(path.read_text())
            item['key'] = '../outside'
            path.write_text(json.dumps(item))
        else:
            path.write_text('{}')
    with pytest.raises((ValueError, KeyError)):
        T.run(ctx(ws, tamper == 'snapshot'))


def test_hidden_hand_model_probe_is_refused(case):
    with pytest.raises(ValueError, match='MODEL_HIDDEN'):
        T.run(ctx(case[0]), candidate=False)


@pytest.mark.parametrize('text', ['prose', reply('0' * 64), reply('0' * 64, 'BLOCKED')])
def test_inspector_cannot_accept_prose_wrong_hash_or_blocked_reply(case, text):
    ws, _ = case
    T.run(ctx(ws), freeze=True)
    assert not A.step_inspect(ws, 1, text)
    assert not (ws / 'onboarding/result.json').exists()


def test_inspection_accepts_exact_hash_and_accepted_bundle_is_verified(case):
    ws, pkg = case
    T.run(ctx(ws), freeze=True)
    assert A.step_inspect(ws, 2, reply(sha256_bytes(MODEL.encode())))
    record = json.loads((ws / 'onboarding/result.json').read_text())
    item = record['item']
    assert item['status'] == 'ACCEPTED' and not item['reused'] and item['attempts'] == 2
    F.write_package(ws / 'schema-check', {**pkg, 'authored': [item],
                                         'sha256': F.canonical_hash({**pkg, 'authored': [item]})})
    model, repl = A.artifact_paths({**pkg, 'authored': [item]})
    assert model.read_text() == MODEL and repl.read_text() == 'CRC_MODEL_PATH'
    assert A.finish(ws)['item']['status'] == 'ACCEPTED'  # terminal cleanup cannot downgrade an acceptance
    model.chmod(0o644)
    model.write_text('# altered\n')
    with pytest.raises(ValueError, match='MODEL_CHANGED'):
        A.artifact_paths({**pkg, 'authored': [item]})


def test_three_failed_gates_end_as_named_gap(case):
    ws, _ = case
    for attempt in range(1, 4):
        assert not A.step_gate(ws, attempt, 'invalid author reply')
    record = A.finish(ws)
    assert record['item']['attempts'] == 3 and record['item']['status'] == 'GAP'
    assert record['item']['gate']['verdict'] == 'FAIL'
    assert len(list((ws / 'onboarding/history').glob('*-gate.json'))) == 3


def test_docs_reader_bounds_output_and_refuses_escape(case, tmp_path):
    ws, _ = case
    path = ws / 'inputs/rm.md'
    path.write_text('a' * 5000)
    context = ToolContext('forge-docs-mcp', 'read_onboarding_input', A.ROLES[0], None, ws, 'test')
    r = read_onboarding_input(context, OnboardingReadIn(path='inputs/rm.md', offset=30))
    assert len(canonical_json(r)) <= 2048 and r['metrics']['next_offset'] == 830
    assert len(r['metrics']['excerpt']) == 800 and r['metrics']['sha256']
    outside = tmp_path / 'outside.md'
    outside.write_text('secret')
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(ToolDenied):
        read_onboarding_input(context, OnboardingReadIn(path='inputs/rm.md'))


def test_no_live_order_or_profile_fallback_model_calls(case, monkeypatch):
    ws, pkg = case
    monkeypatch.setattr(A, '_live_swe', lambda: True)
    with pytest.raises(ValueError, match='DEFERRED_ACTIVE_SWE'):
        A.author(REPO_ROOT / 'examples/0014c-st-cube-crc', 'test-case', pkg)
    with pytest.raises(ValueError, match='PROFILE_NOT_QUALIFIED'):
        A.author(Path('.'), 'test-case', pkg, profile='codex-only')


@pytest.mark.parametrize('mode', ['existing', 'missing', 'no-author', 'hidden-gap', 'authored'])
def test_derive_selects_reuse_or_explicit_authoring_without_hidden_model_reads(tmp_path, monkeypatch, mode):
    from types import SimpleNamespace

    from forge_factory import onboarding as OB
    from forge_factory.onboarding import api, behaviour, identity, model_gate, texts

    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path / 'state'))
    (tmp_path / 'x.c').write_text('int x;')
    simulation = tmp_path / 'sim'
    simulation.mkdir()
    model, repl = simulation / 'crc_model.py', simulation / 'stm32n6_crc.repl'
    if mode in ('existing', 'hidden-gap'):
        model.write_text('# HAND MODEL MUST STAY HIDDEN\n')
        repl.write_text('')
    monkeypatch.setattr(model_gate, 'SIM_DIR', simulation)
    monkeypatch.setattr(identity, 'context', lambda _: SimpleNamespace(source=tmp_path))
    facts = [F.derived('register_prefix', 'CRC', 'test', F.Source('doc', 'rm.md')),
             F.derived('driver_style', 'LL', 'test', F.Source('workorder', 'workorder.json'))]
    monkeypatch.setattr(identity, 'derive', lambda _: (facts, {}))
    monkeypatch.setattr(identity, 'input_records', lambda _: [])
    monkeypatch.setattr(behaviour, 'derive', lambda *a: ([], [], {'files': [{'from': 'x.c', 'to': 'software/ll/x.c'}]}))
    monkeypatch.setattr(api, 'api', lambda *a: F.derived('api', {}, 'test', F.Source('file', 'x.c')))
    monkeypatch.setattr(OB, '_revision', lambda: 'abcdef1')
    calls = []
    monkeypatch.setattr(OB, 'model_item', lambda *a: calls.append('reuse'))
    monkeypatch.setattr(A, 'cached', lambda *a: None)
    item = {'id': 'model', 'role': A.ROLES[0], 'path': 'onboarding/model/model.py', 'attempts': 3,
            'gate': {'verdict': 'FAIL', 'findings': ['missing semantics']},
            'inspection': {'verdict': 'FAIL', 'findings': ['not inspected'], 'inspector_role': A.ROLES[1]},
            'limits': [], 'reused': False, 'status': 'GAP'}
    if mode == 'authored':
        item.update(status='ACCEPTED', gate={'verdict': 'PASS', 'findings': []},
                    inspection={'verdict': 'PASS', 'findings': [], 'inspector_role': A.ROLES[1]})
    monkeypatch.setattr(A, 'author', lambda *a: calls.append('author') or item)
    monkeypatch.setattr(A, 'artifact_paths', lambda *a: (tmp_path / 'authored.py', tmp_path / 'platform.repl'))
    monkeypatch.setattr(texts, 'generate', lambda *a, model_path=None: calls.append(('texts', model_path)) or {})
    pkg = OB.derive(tmp_path, 'test-case', author_missing=mode != 'no-author',
                    hide_model='crc' if mode == 'hidden-gap' else None)
    if mode == 'existing':
        assert 'reuse' in calls and 'author' not in calls
    elif mode == 'no-author':
        assert not calls and pkg['status'] == 'BLOCKED'
    elif mode == 'authored':
        assert calls == ['author', ('texts', tmp_path / 'authored.py')]
        assert pkg['authored'][0]['status'] == 'ACCEPTED'
    else:
        assert calls == ['author'] and pkg['status'] == 'BLOCKED' and pkg['authored'][0]['status'] == 'GAP'
    if mode == 'hidden-gap':
        assert pkg['profile']['model_authoring'] == {'hide_model': 'crc', 'test_only': True}


def test_target_execution_rejects_changed_authored_bytes_before_renode(case, monkeypatch):
    from forge_factory import layer
    from forge_factory.mcp.servers import sim

    ws, _ = case
    model = ws / 'onboarding/model/model.py'
    platform = ws / 'inputs/platform.repl'
    monkeypatch.setattr(layer, 'profile', lambda _: {'sim': {'model': str(model), 'platform': str(platform)},
                        'register_prefix': 'CRC', 'derived_from': {'model_sha256': '0' * 64,
                        'platform_sha256': sha256_bytes(platform.read_bytes())}})
    res, out = sim.run_image('must-not-be-executed', ws / 'unused.elf', 'default', ws, ws)
    assert res is None and out == b'ONBOARDING_AUTHORED_MODEL_CHANGED'


def test_model_gate_never_falls_back_to_hidden_model(case, monkeypatch):
    from forge_factory.onboarding import model_gate

    ws, pkg = case
    pkg['profile']['model_authoring'] = {'hide_model': 'crc', 'test_only': True}
    monkeypatch.setattr(A, 'artifact_paths', lambda _: None)
    report = model_gate.check('test-case', pkg=pkg)
    assert report['verdict'] == 'FAIL' and report['findings'] == ['MODEL_HIDDEN_NO_ACCEPTED_CANDIDATE']


@pytest.mark.parametrize('entered', [0, 1, 2])
def test_interrupted_runs_report_observed_attempts_instead_of_three(case, entered):
    ws, _ = case
    for attempt in range(1, entered + 1):
        assert A.main(['--workspace', str(ws), '--step', 'begin', '--attempt', str(attempt)]) == 0
    record = A.finish(ws)
    assert record['item']['status'] == 'GAP' and record['item']['attempts'] == entered


def test_declared_limits_are_retained_even_without_a_gate_mismatch(case):
    ws, _ = case
    model = MODEL.replace('MODEL_LIMITS = []', 'MODEL_LIMITS = ["CRC_SR.VALUE"]')
    (ws / 'onboarding/model/model.py').write_text(model)
    T.run(ctx(ws), freeze=True)
    assert A.step_inspect(ws, 1, reply(sha256_bytes(model.encode())))
    result = json.loads((ws / 'onboarding/result.json').read_text())
    assert result['item']['limits'] == ['CRC_SR.VALUE']


def test_non_string_model_limits_cannot_pass_to_owner_review(case):
    ws, _ = case
    (ws / 'onboarding/model/model.py').write_text(MODEL.replace('MODEL_LIMITS = []', 'MODEL_LIMITS = [1]'))
    with pytest.raises(ValueError, match='MODEL_LIMITS_NOT_STRINGS'):
        T.run(ctx(ws), freeze=True)
