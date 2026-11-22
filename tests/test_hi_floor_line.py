"""Feature 023: the forge-c-hi floor line turns conductor records into the floor page's shape (read-only)."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from hi_floor_line import floor, hall_id, parse_projects  # noqa: E402

NOW = time.time()


def ts(ago):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(NOW - ago))


def project(root: Path, events, active=None, open_points=()):
    (root / '.hi/runs/r1').mkdir(parents=True)
    (root / '.hi/project.json').write_text(json.dumps({
        'project_id': 'demo', 'profile': 'generic', 'integrity_level': 'HI-2', 'stages': ['sys-req', 'sw-req'],
        'roles': {'author': {'harness': 'claude-code', 'model': 'sonnet', 'model_family': 'claude'},
                  'inspector': {'harness': 'codex', 'model': 'gpt-6.1-terra', 'model_family': 'gpt'}}}))
    (root / '.hi/runs/r1/events.jsonl').write_text(''.join(json.dumps(dict(e, run_id='r1')) + '\n' for e in events))
    if active:
        (root / '.hi/active-role.json').write_text(json.dumps(dict(active, run_id='r1')))
    (root / 'hi/sys-req/inspection').mkdir(parents=True)
    (root / 'hi/sys-req/requirements.json').write_text(json.dumps({'items': [{}, {}], 'open_points': list(open_points)}))
    (root / 'hi/sys-req/inspection/item-r1.json').write_text(json.dumps({'findings': [
        {'target_id': 'SYS-A-001', 'severity': 'blocking'}, {'target_id': 'SYS-A-002', 'severity': 'major'},
        {'target_id': 'SYS-A-003', 'severity': 'blocking', 'blocked_by': 'OP-SYS-001'}]}))


START = [
    {'step': 'stage-start', 'stage': 'sys-req', 'ts': ts(600)},
    {'step': 'role', 'role': 'author', 'phase': 'create', 'stage': 'sys-req', 'duration_s': 300, 'ts': ts(300)},
    {'step': 'gate', 'stage': 'sys-req', 'verdict': 'PASS', 'gates': {'quality': 'PASS', 'trace': 'PASS'}, 'ts': ts(300)},
    {'step': 'role', 'role': 'inspector', 'phase': 'item', 'stage': 'sys-req', 'duration_s': 200, 'ts': ts(100)},
    {'step': 'findings', 'phase': 'item', 'round': 1, 'findings': 3, 'stage': 'sys-req', 'ts': ts(100)},
    {'step': 'role', 'role': 'author', 'phase': 'rework', 'round': 1, 'stage': 'sys-req', 'duration_s': 60, 'ts': ts(40)},
]


class HiFloorLine(unittest.TestCase):
    def test_running_rework_is_measured_per_item(self):
        with tempfile.TemporaryDirectory() as d:
            project(Path(d), START, active={'role': 'author', 'stage': 'sys-req', 'set_utc': ts(30)},
                    open_points=[{'id': 'OP-SYS-001', 'blocks': True}])
            f = floor(parse_projects([f'demo={d}']), now=NOW)
        self.assertEqual(f['schema'], 'forge-c/factory-floor/1')
        self.assertEqual([h['id'] for h in f['halls']], ['SYS.REQ', 'SW.REQ'])
        hall = f['halls'][0]
        self.assertEqual(hall['state'], 'working')
        cells = {c['id']: c for c in hall['cells']}
        # two rework findings without blocked_by; one item done, the second at work
        self.assertEqual(cells['author']['bar'], {'kind': 'measured', 'done': 1, 'total': 2,
                                                  'unit': 'items reworked (round 1)', 'sub': 'one item per call'})
        self.assertEqual(cells['author']['state'], 'rework')
        self.assertIn('Claude Sonnet', cells['author']['tag'])
        self.assertIn('gpt-6.1-terra', cells['inspector']['tag'])
        self.assertEqual(dict(cells['desk']['counters'])['blocking'], 1)
        self.assertEqual(f['orders'][0]['state'], 'RUNNING')
        self.assertEqual(f['orders'][0]['route'], {'SYS.REQ': 'run', 'SW.REQ': 'pending'})
        self.assertEqual(f['kpis']['station']['account_models'], {'author': 'Claude Sonnet', 'inspector': 'gpt-6.1-terra'})

    def test_blocked_and_interrupted_runs(self):
        blocked = START + [{'step': 'stage-end', 'stage': 'sys-req', 'outcome': 'BLOCKED', 'reason': 'open points',
                            'ts': ts(20)}]
        with tempfile.TemporaryDirectory() as d:
            project(Path(d), blocked)
            f = floor(parse_projects([f'demo={d}']), now=NOW)
        self.assertEqual(f['orders'][0]['state'], 'STOPPED')
        self.assertIn('BLOCKED in sys-req', f['orders'][0]['note'])
        self.assertEqual(f['orders'][0]['route']['SYS.REQ'], 'no')
        self.assertEqual(f['halls'][0]['stopped'], 1)
        with tempfile.TemporaryDirectory() as d:
            project(Path(d), START)  # no active role, last event 40 s ago: still between two roles
            self.assertEqual(floor(parse_projects([f'demo={d}']), now=NOW)['orders'][0]['state'], 'RUNNING')
            self.assertEqual(floor(parse_projects([f'demo={d}']), now=NOW + 3600)['orders'][0]['state'], 'STOPPED')

    def test_hall_ids_follow_page_hash_navigation(self):
        self.assertEqual(hall_id('sys-req'), 'SYS.REQ')
        self.assertEqual(hall_id('unit-verif'), 'UNIT.VERIF')


if __name__ == '__main__':
    unittest.main()
