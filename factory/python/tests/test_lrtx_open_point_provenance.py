"""A local input note stays scoped and its independent finding reaches its original obligation."""
import copy
import json

from forge_factory.common import sha256_bytes
from forge_factory.lrtx import swe1, visit
from forge_factory.lrtx import structured as S
from test_incremental_delivery import imported, prepared  # noqa: F401 - validated provided-input fixture
from test_lrtx_swe1 import ANSWERS, _scripted, pytestmark, ws  # noqa: F401 - inherited input guard and fixture


def _map():
    return {'swr': {'SWR-006': {'task': 'requirements:TEST_RSTR', 'key': 'assert_reset'}}, 'case': {},
            'open_points': {'OP-0123456789abcdef': {'task': 'requirements:TEST_ENR', 'register': 'TEST_ENR',
                                                'text': 'This input section does not define TEST_RSTR bits.'}}}


def test_open_point_finding_routes_to_note_owner_and_referenced_requirement():
    finding = 'Open points says the TEST_ENR input does not define TEST_RSTR, but SWR-006 specifies reset assertion.'
    routed = visit.route_findings([finding], _map(), 'requirements:crosscutting')
    assert set(routed) == {'requirements:TEST_ENR', 'requirements:TEST_RSTR'}


def test_explicit_open_point_id_reaches_original_obligation():
    routed = visit.route_findings(['OP-0123456789abcdef is inconsistent with SWR-006.'],
                                  _map(), 'requirements:crosscutting')
    assert set(routed) == {'requirements:TEST_ENR', 'requirements:TEST_RSTR'}


def test_unscoped_open_point_finding_covers_known_note_origins_and_legacy_maps_still_work():
    finding = 'The Open points section contradicts the declared scope.'
    assert set(visit.route_findings([finding], _map(), 'requirements:crosscutting')) == {'requirements:TEST_ENR'}
    assert visit.route_findings([finding], {'swr': {}, 'case': {}}, 'requirements:crosscutting') == {
        'requirements:crosscutting': [finding]}


def test_assembly_keeps_note_text_with_stable_source_scope_and_packet_identity(ws, monkeypatch):  # noqa: F811
    note = 'This prescaler input section does not define reload register fields.'
    answers = copy.deepcopy(ANSWERS)
    answers['requirements:IWDG_PR']['open_points'] = [note]
    monkeypatch.setattr(S, 'call', _scripted(answers, []))
    assert swe1.visit(ws, 'synthetic')['status'] == 'PASS'
    amap = json.loads((ws / '.forge-run/lrtx/SWE.1/assembly.json').read_text())
    entries = [(key, value) for key, value in amap['open_points'].items() if value['text'] == note]
    assert len(entries) == 1
    ident, value = entries[0]
    record = json.loads((ws / '.forge-run/lrtx/SWE.1/packets/requirements__IWDG_PR.json').read_text())
    assert value['task'] == 'requirements:IWDG_PR' and value['register'] == 'IWDG_PR'
    assert value['text_sha256'] == sha256_bytes(note.encode()) and value['packet_input_hash'] == record['base_hash']
    text = (ws / swe1.REQS).read_text()
    assert ident in text and 'input scope: IWDG_PR' in text and note in text


def test_reviewed_provided_input_has_its_actual_hash_without_inventing_a_model_packet(prepared):  # noqa: F811
    workspace, manifest = imported(prepared)
    assembly = json.loads((workspace / '.forge-run/lrtx/SWE.1/assembly.json').read_text())
    assert assembly['open_points']
    for origin in assembly['open_points'].values():
        assert origin['packet_input_hash'] is None
        assert len(origin['record_sha256']) == 64
        assert origin['provided_input_sha256'] == manifest['provided_requirements']['sha256']
