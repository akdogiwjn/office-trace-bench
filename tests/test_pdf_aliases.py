"""Declared equivalent forms pass; unrelated and protected values remain rejected."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import office
from office_trace_bench.contracts import ROOT, dataset_path, read_json
from office_trace_bench.runner import stage
from office_trace_bench.verify import verify, pdf_field_matches


class PdfAliasTests(unittest.TestCase):
    def test_equivalence_is_field_specific_and_opt_in(self):
        rule = {'value_aliases': {'United States': ['United States of America']}}
        self.assertTrue(pdf_field_matches('United States of America', 'United States', rule))
        self.assertFalse(pdf_field_matches('United States of America', 'United States', {}))
        self.assertFalse(pdf_field_matches('Canada', 'United States', rule))
        self.assertFalse(pdf_field_matches('United States', 'Canada', rule))

    def test_real_old_attempt_passes_current_contract_without_output_changes(self):
        old = ROOT / 'legacy/pdf/output'
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / 'workspace'
            stage(dataset_path('pdf', 'opm'), workspace)
            shutil.copytree(old, workspace / 'output', dirs_exist_ok=True)
            mapping = workspace / 'output/field_values/applicant_01.json'
            aliases = read_json(mapping)
            next(v for v in aliases if v['field_id'] == 'Country of Citizenship')['value'] = 'United States of America'
            mapping.write_text(json.dumps(aliases))
            report = verify(dataset_path('pdf', 'opm'), workspace)
            self.assertEqual(report['failures'], [])
            summary_path = workspace / 'output/batch_summary.json'
            summary = read_json(summary_path)
            summary['input_form'] = '../../of306_aug2023.pdf'
            summary_path.write_text(json.dumps(summary))
            values_path = workspace / 'output/field_values/applicant_01.json'
            values = read_json(values_path)
            next(v for v in values if v['field_id'] == 'Country of Citizenship')['value'] = 'Canada'
            values.append({'field_id': 'Social Security Number', 'page': 1, 'value': 'invalid'})
            values_path.write_text(json.dumps(values))
            failures = verify(dataset_path('pdf', 'opm'), workspace)['failures']
            self.assertIn('mapping:applicant_01', failures)
            self.assertIn('protected_blank:applicant_01', failures)
            self.assertIn('summary:input_form', failures)


if __name__ == '__main__':
    unittest.main()
