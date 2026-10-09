import tempfile
import copy
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import office
from office_trace_bench import contracts
from office_trace_bench.runner import render_prompt


class PromptCompatibilityTests(unittest.TestCase):
    def test_domains_change_through_manifest_without_template_forks(self):
        path = contracts.dataset_path('xlsx', 'tlc')
        manifest = copy.deepcopy(contracts.load_manifest(path))
        manifest['prompt_contract'].update(task_subject='Retail inventory workbook', raw_record_count=250,
                                           original_chart_count=1, metadata_files=['inventory_sources.md'])
        manifest['workbook'] = 'inventory_seed.xlsx'
        manifest['output_workbook'] = 'inventory_report.xlsx'
        manifest['requirements']['summary_sheet'] = 'Inventory_Overview'
        manifest['requirements']['raw_sheets'] = ['Inventory_Rows']
        manifest['requirements']['metrics'] = [dict(name='Total Stock', cell='C7', required_references=['Stock!C3'])]
        prompt = render_prompt(manifest, '/run', path)
        for phrase in ('Retail inventory workbook', '250-row', 'Inventory_Overview', 'C7 Total Stock', 'Stock!C3'):
            self.assertIn(phrase, prompt)
        for phrase in ('NYC TLC', '100,000', 'Raw_Sample', 'B5 Total Trips'):
            self.assertNotIn(phrase, prompt)
        path = contracts.dataset_path('pdf', 'opm')
        manifest = copy.deepcopy(contracts.load_manifest(path))
        manifest['prompt_contract'].update(task_subject='Synthetic payroll fillable PDF', record_noun='employees',
            record_singular='employee', first_record_name='employee_01', record_pattern='employee_XX',
            form_description='a five-page payroll form', fill_description='employee payroll fields',
            safe_answer_description='use the synthetic payroll answers', protected_description='Certification fields')
        manifest['requirements'].update(page_count=5, record_count=4)
        manifest['form'] = 'payroll.pdf'
        manifest['records'] = 'employees.json'
        manifest['summary_contract'] = dict(input_form='payroll.pdf', record_count=4, filled_pdf_count=4,
            rendered_page_count=25, fill_script_invocations=4, render_script_invocations=5, certification_blank=True)
        prompt = render_prompt(manifest, '/run', path)
        for phrase in ('four synthetic training employees', 'exactly four times', 'exactly five times',
                       'page_5.png', '25 rendered PNG pages', 'employee_XX.pdf'):
            self.assertIn(phrase, prompt)
        for phrase in ('OPM', 'Selective Service', 'applicant_', '33 rendered', 'Social Security Number'):
            self.assertNotIn(phrase, prompt)

    def test_original_task_and_execution_instructions_are_preserved(self):
        for kind, dataset, original_workspace in (
            ('xlsx', 'tlc', '/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01'),
            ('pdf', 'opm', '/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01'),
        ):
            manifest_path = contracts.dataset_path(kind, dataset)
            manifest = contracts.load_manifest(manifest_path)
            prompt = render_prompt(manifest, '/new/workspace', manifest_path)
            original = (contracts.ROOT / 'legacy' / kind / 'task.prompt').read_text()
            normalized = prompt.replace('/new/workspace', original_workspace)
            normalized = normalized.replace('inside a fresh trace-generation container.', 'inside a fresh VM.')
            normalized = normalized.replace('The container uses the installed openpyxl.', "The VM uses Ubuntu's packaged openpyxl.")
            self.assertEqual(original, normalized)
            self.assertNotIn('/project/', prompt)
            self.assertNotIn('expected.json', prompt)

    def test_modified_prompt_cannot_pass_frozen_manifest_validation(self):
        path = contracts.dataset_path('pdf', 'opm')
        manifest = contracts.load_manifest(path)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'prompts').mkdir()
            (root / 'prompts' / manifest['prompt_template']).write_text('unrecorded prompt change')
            with patch.object(contracts, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'prompt template hash mismatch'):
                    contracts.load_manifest(path)


if __name__ == '__main__':
    unittest.main()
