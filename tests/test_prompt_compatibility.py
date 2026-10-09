import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import office
from office_trace_bench import contracts
from office_trace_bench.prompts import render_prompt

class PromptCompatibilityTests(unittest.TestCase):
    def test_common_prompts_have_no_dataset_layout_or_business_literals(self):
        for kind, forbidden in [('xlsx',['Raw_Data','Raw_Sample','Reconciliation','Total Trips','Fare Revenue','Retail Sales','Shipments','Mean Wage','Median Wage','B5','100,000','INDEX','MATCH']),('pdf',['OF-306','Selective Service','citizenship','38 fields','3 pages','33 PNG','exactly ten','exactly eleven'])]:
            text=(contracts.ROOT/'prompts'/f'{kind}.txt').read_text()
            for phrase in forbidden:self.assertNotIn(phrase,text)
            for path in (contracts.ROOT/'datasets'/kind).glob('*/manifest.json'):
                m=contracts.load_manifest(path)
                prompt=render_prompt(m,'/any/workspace',path)
                self.assertIn('input/dataset_manifest.json',prompt)
                alternate=copy.deepcopy(m);alternate['dataset_id']='unseen';alternate['requirements']={}
                self.assertEqual(prompt,render_prompt(alternate,'/any/workspace',path))
    def test_historical_tasks_are_frozen_in_repository_fixtures(self):
        for name,digest in contracts.read_json(contracts.ROOT/'legacy/fixture_index.json')['files'].items():
            self.assertEqual(contracts.sha256(contracts.ROOT/name),digest,name)
        for kind in ('xlsx','pdf'):
            path=contracts.ROOT/'legacy/runner/cases'/kind/'manifest.json'
            m=contracts.load_manifest(path)
            workspace='/root/.openclaw/workspace/tool-modeling/'+m['runtime_case']
            rendered=render_prompt(m,workspace,path).replace('inside a fresh trace-generation container.','inside a fresh VM.').replace('The container uses the installed openpyxl.',"The VM uses Ubuntu's packaged openpyxl.")
            self.assertEqual(rendered,(contracts.ROOT/'legacy'/kind/'task.prompt').read_text())
    def test_modified_prompt_cannot_pass_frozen_manifest_validation(self):
        path=contracts.dataset_path('pdf','opm');m=contracts.load_manifest(path)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'prompts').mkdir();(root/'prompts'/m['prompt_template']).write_text('changed')
            with patch.object(contracts,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'prompt template hash mismatch'):contracts.load_manifest(path)
