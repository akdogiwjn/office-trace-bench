import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import office
from office_trace_bench import runner
from office_trace_bench.contracts import read_json


class RunIsolationTests(unittest.TestCase):
    def project(self, root):
        (root / 'office.py').write_text('# test entry point\n')
        for name in ('office_trace_bench', 'prompts', 'vendor', 'runtime'):
            (root / name).mkdir()
        (root / 'legacy').mkdir()
        (root / 'legacy/answer.txt').write_text('previous success must not be exposed')

    def fake_docker(self, command, mutate=False, **kwargs):
        if command[:2] == ['docker', 'run']:
            mounts = [command[i + 1] for i, arg in enumerate(command) if arg == '--mount']
            code = next(v for v in mounts if 'dst=/workspace,' in v)
            data = next(v for v in mounts if 'dst=/runs/' in v)
            self.assertIn('readonly', code)
            self.assertNotIn('dst=/runs,', ','.join(mounts))
            source = Path(code.split('src=', 1)[1].split(',', 1)[0])
            run_dir = Path(data.split('src=', 1)[1].split(',', 1)[0])
            self.assertFalse(source.is_relative_to(run_dir))
            self.assertFalse((source / 'legacy').exists())
            self.assertTrue((source / 'runtime_context/profiles/legacy-host-v1/profile.json').exists())
            self.assertTrue((source / 'datasets/pdf/opm/manifest.json').exists())
            self.assertFalse((source / 'datasets/xlsx').exists())
            (run_dir / 'run_manifest.json').write_text(json.dumps({'status': 'success'}))
            if mutate:
                (source / 'office.py').write_text('modified after launch')
        return subprocess.CompletedProcess(command, 0, stdout='sha256:test-image\n')

    def test_only_selected_inputs_and_own_results_are_mounted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.project(root)
            with patch.object(runner, 'ROOT', root), patch.object(runner.subprocess, 'run', side_effect=self.fake_docker):
                self.assertEqual(runner.launch('pdf', 'opm', 'test-image', '/fake-config'), 0)
            manifest = read_json(next((root / 'runs').glob('*/run_manifest.json')))
            self.assertTrue(manifest['source_snapshot_unchanged'])

    def test_source_changes_invalidate_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.project(root)
            def modified(command, **kwargs):
                return self.fake_docker(command, mutate=True, **kwargs)
            with patch.object(runner, 'ROOT', root), patch.object(runner.subprocess, 'run', side_effect=modified):
                self.assertEqual(runner.launch('pdf', 'opm', 'test-image', '/fake-config'), 1)
            manifest = read_json(next((root / 'runs').glob('*/run_manifest.json')))
            self.assertEqual(manifest['status'], 'invalidated')


if __name__ == '__main__':
    unittest.main()
