import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from controlled_runner_pair import ROOT, LEGACY, LEGACY_SCRIPTS, prepare_snapshot, tree_hashes
from office_trace_bench.contracts import read_json, sha256


class ControlledPairTests(unittest.TestCase):
    def test_legacy_runner_is_unchanged_and_no_historical_outputs_are_imported(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / 'snapshot'
            info = prepare_snapshot(snapshot, 'xlsx', 'tlc')
            for name in LEGACY_SCRIPTS:
                self.assertEqual(sha256(snapshot / 'scripts' / name), sha256(LEGACY / 'scripts' / name))
            self.assertFalse((snapshot / 'legacy').exists())
            self.assertEqual(list((snapshot / 'cases/xlsx/output').iterdir()), [])
            self.assertEqual(list((snapshot / 'cases/xlsx/agent_run').iterdir()), [])
            self.assertFalse((snapshot / 'datasets/pdf').exists())
            source = read_json(snapshot / 'datasets/xlsx/tlc/manifest.json')
            visible = read_json(snapshot / 'cases/xlsx/input/dataset_manifest.json')
            self.assertEqual(source, visible)
            self.assertEqual(info['source_hashes'], tree_hashes(snapshot))

    def test_pdf_task_matches_actual_old_message_and_active_prompts_are_unchanged(self):
        original_hash = sha256(ROOT / 'prompts/pdf.txt')
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / 'snapshot'
            info = prepare_snapshot(snapshot, 'pdf', 'opm')
            import hashlib
            message = (LEGACY / 'cases/pdf/task.prompt').read_text().rstrip('\n')
            self.assertEqual(info['actual_task_sha256'], hashlib.sha256(message.encode()).hexdigest())
            self.assertEqual(sha256(ROOT / 'prompts/pdf.txt'), original_hash)
            self.assertNotIn('__pycache__', str(list((snapshot / 'cases/pdf/input').rglob('*'))))


if __name__ == '__main__':
    unittest.main()
