"""Published independent findings reach rework intact; compact summaries are not the repair input."""
import json

from forge_factory.lrtx import review, visit
from forge_factory.lrtx import structured as S
from test_lrtx_p3 import Answers
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - inherited input guard and fixture
from test_lrtx_swe2 import ws1  # noqa: F401 - frozen independent workproduct fixture


def _publish(tmp_path, items, summaries):
    directory = tmp_path / 'inspection/SWE.1'
    directory.mkdir(parents=True)
    (directory / 'INS-SWE.1-001.json').write_text(json.dumps({
        'recorded_at': '2026-10-30T00:00:00Z', 'verdict': 'FAIL', 'items': items, 'findings': summaries,
    }))


def test_rework_reads_each_complete_published_finding(tmp_path):
    first = 'SWR-001: ' + 'first independent observation; ' * 20 + 'FIRST_END'
    second = 'SWR-002: distinct second issue requiring a different author obligation.'
    _publish(tmp_path, {'SWE1-02': {'verdict': 'FAIL', 'findings': [first, second]}},
             [{'id': 'SWE1-02', 'detail': first[:200]}])
    assert visit.rework_findings(tmp_path, 'SWE.1', '') == ['SWE1-02: ' + first, 'SWE1-02: ' + second]


def test_legacy_summary_and_additional_non_item_finding_remain_compatible(tmp_path):
    _publish(tmp_path, {}, [{'id': 'LEGACY', 'detail': 'The original complete legacy finding.'},
                            {'id': 'EXTERNAL', 'detail': 'A separately recorded observation.'}])
    assert visit.rework_findings(tmp_path, 'SWE.1', '') == [
        'LEGACY: The original complete legacy finding.', 'EXTERNAL: A separately recorded observation.']


def test_full_item_findings_do_not_bypass_pass_or_time_boundaries(tmp_path):
    _publish(tmp_path, {'SWE1-02': {'verdict': 'PASS', 'findings': ['untrusted extra field']}},
             [{'id': 'SWE1-02', 'detail': 'Retain the actual recorded failed finding.'}])
    assert visit.rework_findings(tmp_path, 'SWE.1', '') == [
        'SWE1-02: Retain the actual recorded failed finding.']
    assert visit.rework_findings(tmp_path, 'SWE.1', '2026-10-31T00:00:00Z') == []


def test_structured_inspector_publishes_complete_findings_through_existing_operation(ws1, monkeypatch):  # noqa: F811
    first = 'SWR-001 contains inconsistent named-field effects. ' + 'Inspect the stated bit operation. ' * 12 + 'FIRST_END'
    second = 'SWR-002 names an unsupported field in its requirement statement. SECOND_END'

    def answer(packet):
        item = packet['task'].rsplit(':', 1)[1]
        return {'verdict': 'FAIL' if item == 'SWE1-02' else 'PASS',
                'findings': [first, second] if item == 'SWE1-02' else [],
                'evidence_checked': ['workproducts/SWE.1/software_requirements.md']}

    monkeypatch.setattr(S, 'call', _scripted(Answers({}, answer), []))
    assert review.visit(ws1, 'SWE.1', 'synthetic')['status'] == 'REWORK'
    report = json.loads(sorted((ws1 / 'inspection/SWE.1').glob('INS-*.json'))[-1].read_text())
    assert report['verdict'] == 'FAIL'
    assert report['items']['SWE1-02']['findings'] == [first, second]
    feedback = visit.rework_findings(ws1, 'SWE.1', '')
    assert 'SWE1-02: ' + first in feedback and 'SWE1-02: ' + second in feedback
