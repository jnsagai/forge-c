import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOME / "scripts"))
from build_review_package import build, sha256

POLICY = HOME / "policies" / "release-package-policy.json"


class ReviewPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root, self.out = base / 'workspace', base / 'archive'
        self.root.mkdir()
        self.policy = json.loads(POLICY.read_text(encoding='utf-8'))

    def fill_demo_fixture(self):
        # Completely synthetic test fixture, not product safety evidence.
        for sec in self.policy['required_sections']:
            d = self.root / sec
            d.mkdir(parents=True, exist_ok=True)
            (d / 'FIXTURE.txt').write_text('SYNTHETIC PACKAGER TEST ONLY\n', encoding='utf-8')
        for req in self.policy.get('required_files', []):
            f = self.root / req
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text('SYNTHETIC WORKPRODUCT - NOT SAFETY EVIDENCE\n', encoding='utf-8')
        for pat in self.policy.get('required_patterns', []):
            f = self.root / pat.replace('*', 'fixture')
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b'SYNTHETIC NOT AN ELF OR TARGET RESULT\n')
        quality = self.root / self.policy['quality_report']
        quality.parent.mkdir(parents=True, exist_ok=True)
        quality.write_text(json.dumps({'run_status': 'COMPLETED',
                                       'checks': {c: True for c in self.policy['required_quality_checks']},
                                       'open_findings': []}), encoding='utf-8')
        return quality

    def examine(self, result):
        self.assertTrue(Path(result['archive']).is_file())
        self.assertTrue(Path(result['archive']+'.sha256').is_file())
        self.assertEqual(result['archive_sha256'], sha256(Path(result['archive']).read_bytes()))
        with zipfile.ZipFile(result['archive']) as z:
            self.assertEqual(z.testzip(), None)
            manifest = json.loads(z.read('manifest.json'))
            self.assertIn('SHA256SUMS.txt', z.namelist())
            listed = dict(line.split('  ',1) for line in z.read('SHA256SUMS.txt').decode().splitlines())
            for digest, name in listed.items():
                self.assertEqual(digest, sha256(z.read(name)))
            self.assertEqual(manifest['status'], result['package_status'])
            self.assertEqual(manifest['scope'], 'OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED')
        return manifest

    def test_empty_workspace_still_delivers_blocked_package(self):
        r = build(self.root, self.out, 'missing-evidence', POLICY)
        m = self.examine(r)
        self.assertEqual(r['package_status'], 'BLOCKED')
        self.assertGreater(r['gap_count'], 20)
        self.assertTrue(any('missing_quality_report' in s for s in m['gaps']))

    def test_synthetic_complete_fixture_passes_mechanical_check(self):
        self.fill_demo_fixture()
        r = build(self.root, self.out, 'synthetic-fixture', POLICY)
        m = self.examine(r)
        self.assertEqual(r['package_status'], 'READY_FOR_OFFLINE_REVIEW')
        self.assertEqual(m['gap_count'], 0)
        self.assertIn('NOT_SAFETY_APPROVED', m['scope'])

    def test_open_finding_remains_blocked(self):
        quality = self.fill_demo_fixture()
        info = json.loads(quality.read_text())
        info['open_findings'] = [{'id':'SWE3-009', 'severity':'major'}]
        quality.write_text(json.dumps(info),encoding='utf-8')
        r = build(self.root, self.out, 'open-finding', POLICY)
        m = self.examine(r)
        self.assertEqual(r['package_status'], 'BLOCKED')
        self.assertIn('unresolved_finding:SWE3-009',m['gaps'])

    def test_failed_quality_gate_blocks(self):
        quality = self.fill_demo_fixture()
        info = json.loads(quality.read_text())
        info['checks']['resource_budgets'] = False
        quality.write_text(json.dumps(info),encoding='utf-8')
        r = build(self.root, self.out, 'memory-overrun', POLICY)
        m = self.examine(r)
        self.assertEqual(r['package_status'], 'BLOCKED')
        self.assertIn('failed_or_missing_quality_check:resource_budgets',m['gaps'])

    def test_symlink_is_marked_blocking_not_followed(self):
        self.fill_demo_fixture()
        (self.root/'outside').symlink_to('/etc/passwd')
        r = build(self.root, self.out, 'symlink-check', POLICY)
        m = self.examine(r)
        self.assertIn('symlink_not_allowed:outside',m['gaps'])
        self.assertEqual(r['package_status'], 'BLOCKED')

    def test_reproducible_package_bytes_for_same_input(self):
        self.fill_demo_fixture()
        r1 = build(self.root, self.out, 'repeatable', POLICY)
        hash1 = r1['archive_sha256']
        r2 = build(self.root, self.out, 'repeatable', POLICY)
        self.assertEqual(hash1, r2['archive_sha256'])

    def test_output_must_not_be_inside_workspace(self):
        with self.assertRaisesRegex(ValueError, 'not be inside'):
            build(self.root, self.root/'archive', 'recursive', POLICY)


if __name__ == '__main__':
    unittest.main()
