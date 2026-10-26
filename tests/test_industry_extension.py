"""Validate the additional Agent evidence without executing the large workbook."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import office
from office_trace_bench.canonical import validate_pack
from office_trace_bench.contracts import ROOT, load_manifest, read_json, sha256
from office_trace_bench.context import load_profile
from office_trace_bench.verify import verify


class IndustryExtensionTests(unittest.TestCase):
    def test_extension_binds_real_trace_input_and_historical_suite(self):
        index = read_json(ROOT / 'artifacts/extensions.json')
        baseline = index['historical_suite']
        self.assertEqual(sha256(ROOT / baseline['path']), baseline['sha256'])
        self.assertEqual(len(read_json(ROOT / baseline['path'])['datasets']), 7)
        self.assertEqual(len(index['datasets']), 1)
        entry = index['datasets'][0]
        manifest_path = ROOT / entry['manifest_path']
        manifest = load_manifest(manifest_path)
        load_profile(manifest)
        path = ROOT / entry['canonical_path']
        canonical = validate_pack(path)
        self.assertEqual(sha256(path / 'canonical.json'), entry['canonical_sha256'])
        self.assertEqual(sha256(manifest_path), entry['manifest_sha256'])
        self.assertEqual(entry['manifest_sha256'], canonical['manifest_sha256'])
        self.assertEqual(entry['run_id'], canonical['original_run_id'])
        self.assertEqual(entry['input_hashes'], manifest['input_files'])
        self.assertEqual(entry['trace_sha256'], canonical['trace_sha256'])
        self.assertTrue(canonical['verifier_result']['accepted'])
        handoff = index['replay_handoff']
        self.assertEqual(handoff['industry_parent_canonical_sha256'], entry['canonical_sha256'])
        self.assertEqual(handoff['manual_adaptations_without_agent_trace'],
                         ['hr_metro', 'retail_online'])

    def test_independent_scope_rejects_changed_workspace_input(self):
        manifest = ROOT / 'datasets/xlsx/industry_productivity/manifest.json'
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / 'input').mkdir()
            (workspace / 'input/labor-productivity-detailed-industries.xlsx').write_bytes(b'changed')
            report_path = workspace / 'report.json'
            report = verify(manifest, workspace, report_path, scope='independent')
            self.assertEqual(report['status'], 'failed')
            self.assertIn('input:input/labor-productivity-detailed-industries.xlsx', report['failures'])
            self.assertNotIn('verification_exception', report['failures'])
            self.assertEqual(read_json(report_path), report)

    def test_invalid_scope_is_rejected_before_loading_assets(self):
        with self.assertRaisesRegex(ValueError, 'scope'):
            verify('missing-manifest.json', '.', scope='invalid')

    def test_dataset_verifier_sources_match_published_modules(self):
        frozen = ROOT / 'datasets/xlsx/industry_productivity/input/loop_contract'
        active = ROOT / 'office_trace_bench/industry_verification'
        for name in ('contracts.py', 'spreadsheet.py', 'verify.py', 'workbooks.py'):
            with self.subTest(name=name):
                self.assertEqual(sha256(frozen / name), sha256(active / name))


if __name__ == '__main__':
    unittest.main()
