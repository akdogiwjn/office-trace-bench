import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import office
from office_trace_bench.contracts import ROOT, dataset_path, read_json
from office_trace_bench.runner import stage
from office_trace_bench.verify import verify


class VerificationFailureTests(unittest.TestCase):
    def test_input_mutation_is_rejected_before_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / 'workspace'
            stage(dataset_path('pdf', 'opm'), workspace)
            (workspace / 'input/synthetic_applicants.json').write_text('{}')
            report_path = Path(tmp) / 'report.json'
            result = verify(dataset_path('pdf', 'opm'), workspace, report_path)
            self.assertEqual(result['status'], 'failed')
            self.assertIn('input:input/synthetic_applicants.json', result['failures'])
            self.assertEqual(read_json(report_path)['status'], 'failed')

    def test_protected_field_and_wrong_value_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / 'workspace'
            stage(dataset_path('pdf', 'opm'), workspace)
            shutil.copytree(ROOT / 'legacy/pdf/output', workspace / 'output', dirs_exist_ok=True)
            mapping = workspace / 'output/field_values/applicant_01.json'
            values = read_json(mapping)
            values.append({'field_id': 'Social Security Number', 'page': 1, 'value': 'synthetic-invalid'})
            values[0]['value'] = 'wrong-name'
            mapping.write_text(json.dumps(values))
            result = verify(dataset_path('pdf', 'opm'), workspace)
            self.assertEqual(result['status'], 'failed')
            self.assertIn('protected_blank:applicant_01', result['failures'])
            self.assertIn('mapping:applicant_01', result['failures'])


if __name__ == '__main__':
    unittest.main()
