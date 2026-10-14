"""Test that the OSS demo and policy checker reject misleading evidence."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from check_oss_policy import validate as validate_policy
from verify_oss_demo import validate as validate_demo


class OSSPipelineTests(unittest.TestCase):
    def test_policy_rejects_cloud_api(self):
        policy = {'policy': {
            'allow_paid_api': True, 'allow_proprietary_static_analyzer': False,
            'allow_closed_source_models': False, 'local_inference_only': True,
            'safety_claim_requires_human_approval': True,
        }, 'core': [{'name': 'Fabro', 'license': 'MIT'}]}
        self.assertTrue(validate_policy(policy))

    def test_demo_rejects_fake_hardware_scope_and_modified_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / 'evidence' / 'oss-demo'
            base.mkdir(parents=True)
            artifacts = []
            for name in ('llvm-host.log', 'test.profdata'):
                path = base / name
                path.write_bytes(b'fixture-data')
                artifacts.append({'path': f'evidence/oss-demo/{name}',
                                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            record = {'scope': 'host-only-educational-demo',
                      'safety_status': 'NOT_ASIL_B_EVIDENCE',
                      'misra_status': 'NOT_ASSESSED',
                      'target_hardware_test': False, 'artifacts': artifacts}
            self.assertEqual(validate_demo(record, root), [])
            record['target_hardware_test'] = True
            self.assertTrue(validate_demo(record, root))
            record['target_hardware_test'] = False
            (base / 'llvm-host.log').write_text('tampered')
            self.assertTrue(validate_demo(record, root))


if __name__ == '__main__':
    unittest.main()
