"""Exercise publication boundaries and project-prefix handling, not UI implementation."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generate = load('generate')
check = load('check_site')


class PublicationTests(unittest.TestCase):
    def test_recorded_replay_matches_evidence_and_video(self):
        root = Path(__file__).resolve().parents[2]
        media = root / 'website/public/media'
        raw = (media / 'recorded-run.json').read_bytes()
        replay = json.loads(raw)
        provenance = json.loads((media / 'video-provenance.json').read_text())
        self.assertEqual(len(replay['events']), 18)
        self.assertEqual(sum(event['outcome'] == 'REWORK' for event in replay['events']), 2)
        passed = {event['phase'] for event in replay['events'] if event['step'] == 'inspect' and event['outcome'] == 'PASS'}
        self.assertEqual(passed, {f'SWE.{i}' for i in range(1, 7)})
        self.assertEqual(replay['events'][-1]['outcome'], 'READY_FOR_OFFLINE_REVIEW')
        self.assertNotIn('/media/jefferson', raw.decode())
        self.assertNotIn('"archive":', raw.decode())
        for source, digest in replay['sources'].items():
            self.assertEqual(hashlib.sha256((root / source).read_bytes()).hexdigest(), digest)
        self.assertEqual(provenance['replay_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(provenance['video_sha256'], hashlib.sha256((media / 'workflow-replay.mp4').read_bytes()).hexdigest())
        screenshot_source = next(source for source in replay['sources'] if source.endswith('.png'))
        self.assertEqual((media / 'control-room.png').read_bytes(), (root / screenshot_source).read_bytes())
        self.assertEqual((media / 'workflow-replay.vtt').read_text().count(' --> '), 18)

    def test_cli_extraction_does_not_execute_source(self):
        source = '''raise RuntimeError("must not execute")
def main():
    ap.add_argument("--example", required=True)
    ap.add_argument("--provider", default="ollama", help="Model provider")
'''
        options = generate.command_options(source)
        self.assertEqual(options[0]['flags'], ['--example'])
        self.assertTrue(options[0]['required'])
        self.assertEqual(options[1]['default'], 'ollama')

    def test_example_does_not_read_or_publish_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'workorder.json'
            path.write_text('{"driver":"Demo","inputs":[{"path":"/absent/licensed-manual"}],"secret":"do not publish"}')
            info = generate.example_metadata(path)
            self.assertNotIn('inputs', info)
            self.assertNotIn('secret', info)
            self.assertEqual(info['driver'], 'Demo')

    def test_project_base_and_fragments(self):
        root = Path('/tmp/build-fixture')
        source = root / 'docs/index.html'
        target, fragment = check.resolve_path('/forge-c/docs/setup/#tools', source, root, '/forge-c/')
        self.assertEqual(target, root / 'docs/setup/index.html')
        self.assertEqual(fragment, 'tools')
        target, fragment = check.resolve_path('#local', source, root, '/forge-c/')
        self.assertEqual(target, source)
        self.assertEqual(fragment, 'local')

    def test_base_escape_and_traversal_are_rejected(self):
        root = Path('/tmp/build-fixture')
        source = root / 'index.html'
        for url in ['/docs/', '/forge-c/../../private', '../../private']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                check.resolve_path(url, source, root, '/forge-c/')

    def test_external_links_and_root_hosting(self):
        root = Path('/tmp/build-fixture')
        source = root / 'index.html'
        self.assertIsNone(check.resolve_path('https://github.com/jnsagai/forge-c', source, root, '/'))
        target, _ = check.resolve_path('/docs/', source, root, '/')
        self.assertEqual(target, root / 'docs/index.html')


if __name__ == '__main__':
    unittest.main()
