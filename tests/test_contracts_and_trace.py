import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import office
from office_trace_bench.contracts import dataset_path, load_manifest, safe_relative
from office_trace_bench.runner import stage, capture_session, render_prompt
from office_trace_bench.trace import export_trace


class ContractTests(unittest.TestCase):
    def test_unsafe_paths_rejected(self):
        for value in ('../other', '/etc/passwd', 'input/../../other'):
            with self.assertRaises(ValueError):
                safe_relative(value)
        with self.assertRaises(ValueError):
            dataset_path('pdf', '../../opm')

    def test_stage_preserves_seed_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / 'workspace'
            manifest = stage(dataset_path('pdf', 'opm'), workspace)
            self.assertTrue((workspace / 'input/of306_aug2023.pdf').is_file())
            self.assertTrue((workspace / 'input/verify_pdf_batch.py').is_file())
            self.assertEqual(manifest['dataset_id'], 'opm')
            with self.assertRaises(ValueError):
                stage(dataset_path('pdf', 'opm'), workspace)
            prompt = render_prompt(manifest, workspace, dataset_path('pdf', 'opm'))
            self.assertIn(str(workspace), prompt)
            self.assertNotIn('38 fields', prompt)

    def test_unrelated_newest_session_is_never_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'main/sessions').mkdir(parents=True)
            (root / 'main/sessions/unrelated.jsonl').write_text('{"type":"session","id":"unrelated"}\n')
            stdout = root / 'stdout.json'
            stdout.write_text(json.dumps({'meta': {'agentMeta': {'sessionId': 'expected'}}}))
            with self.assertRaises(ValueError):
                capture_session(stdout, root, root / 'captured.jsonl')

    def test_historical_trace_export_retains_every_call_and_result(self):
        root = Path(__file__).resolve().parents[1]
        manifest = load_manifest(dataset_path('pdf', 'opm'))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'trajectory.json'
            result = export_trace(root / 'legacy/pdf/openclaw_session.jsonl', target, manifest, 'historical-test')
            trajectory = json.loads(target.read_text())
            events = json.loads(target.with_name('tool_events.json').read_text())['events']
            count = sum(len(s.get('tool_calls', [])) for s in trajectory['steps'])
            self.assertEqual(count, len(events))
            self.assertEqual(result['tool_calls'], count)
            self.assertTrue(all(e['result'] is not None for e in events))
            self.assertEqual(len({e['tool_call']['tool_call_id'] for e in events}), count)


if __name__ == '__main__':
    unittest.main()
