"""Business verification precedes the final run summary; final acceptance requires it."""
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import office
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.datavalidation import DataValidation
from office_trace_bench.contracts import sha256, write_json
from office_trace_bench.verify import verify
from office_trace_bench.workbooks import workbook_snapshot


class VerificationCompletionTests(unittest.TestCase):
    def test_missing_final_summary_is_deferred_only_during_agent_business_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / 'workspace'
            (workspace / 'input').mkdir(parents=True)
            (workspace / 'output').mkdir()
            book = Workbook()
            data = book.active
            data.title = 'Data'
            data['A1'] = 7
            baseline = workbook_snapshot(book, ['Data'])
            seed = workspace / 'input/seed.xlsx'
            book.save(seed)
            summary = book.create_sheet('Overview', 0)
            summary['B5'] = '=Data!A1'
            summary['B12'] = 'Base'
            summary['B12'].font = Font(color='0000FF')
            summary['D13'] = 'Base'
            summary['E13'] = 1
            summary['F13'] = 1
            validation = DataValidation(type='list', formula1='"Base"')
            summary.add_data_validation(validation)
            validation.add(summary['B12'])
            summary.freeze_panes = 'A2'
            book.save(workspace / 'output/report.xlsx')
            book.close()
            write_json(root / 'expected.json', dict(baseline=baseline, cached_values={}))
            write_json(workspace / 'output/formula_recalc.json', dict(status='success', total_errors=0, total_formulas=1))
            manifest = dict(schema_version='office-dataset-v1', kind='xlsx', dataset_id='fixture', task='Inventory',
                workbook='seed.xlsx', output_workbook='report.xlsx', input_files={'input/seed.xlsx': sha256(seed)},
                expected_file='expected.json', expected_sha256=sha256(root / 'expected.json'), trace_rules=[],
                requirements=dict(summary_sheet='Overview', base_sheets=['Data'], raw_sheets=['Data'],
                    metrics=[dict(cell='B5', required_references=['Data!A1'])], minimum_formula_count=1,
                    scenario=dict(selector_cell='B12', default='Base', formula_metrics=[],
                        rows=[dict(name='Base', cells=dict(D13='Base', E13=1, F13=1))]),
                    charts=[], minimum_conditional_formats=0, minimum_comments=0),
                required_outputs=['report.xlsx', 'formula_recalc.json', 'xlsx_enhancement_summary.json'])
            # The fixture's assets and manifest are collocated, as in a real dataset.
            (root / 'input').symlink_to(workspace / 'input', target_is_directory=True)
            path = root / 'manifest.json'
            write_json(path, manifest)
            self.assertEqual(verify(path, workspace, deferred_outputs=('xlsx_enhancement_summary.json',))['status'], 'success')
            final = verify(path, workspace)
            self.assertEqual(final['failures'], ['deliverable:xlsx_enhancement_summary.json'])
            write_json(workspace / 'output/xlsx_enhancement_summary.json', {'final_verifier_status': 'success'})
            self.assertEqual(verify(path, workspace)['status'], 'success')


if __name__ == '__main__':
    unittest.main()
