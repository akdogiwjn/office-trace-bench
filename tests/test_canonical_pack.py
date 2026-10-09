from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from office_trace_bench.canonical import validate_pack
from office_trace_bench.contracts import ROOT,read_json,sha256
from scripts.freeze_suite_index import SCOPE,validate_scenario,validate_evidence

class CanonicalPackTests(unittest.TestCase):
    def test_all_selected_trace_bindings_and_real_verifier_evidence(self):
        suite=read_json(ROOT/'artifacts/suite.json')
        validate_evidence(suite)
        self.assertEqual(len(suite['datasets']),7)
        self.assertEqual({(e['kind'],e['dataset_id']) for e in suite['datasets']},SCOPE)
        for entry in suite['datasets']:
            path=ROOT/'artifacts'/entry['canonical_path'];data=validate_pack(path)
            self.assertEqual(sha256(path/'canonical.json'),entry['canonical_sha256'])
            self.assertEqual(sha256(ROOT/entry['manifest_path']),data['manifest_sha256'])
            self.assertTrue(data['revision_capture']['present']);self.assertFalse(data['executable_replay_recipe']);self.assertFalse(data['replay_requires_llm'])
            validate_scenario(entry,data)
    def test_modified_trace_is_rejected(self):
        entry=read_json(ROOT/'artifacts/suite.json')['datasets'][0]
        original=ROOT/'artifacts'/entry['canonical_path']
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'canonical';shutil.copytree(original,path)
            (path/'trajectory.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'canonical file hash mismatch'):
                validate_pack(path)
            shutil.copyfile(original/'trajectory.json',path/'trajectory.json')
            from office_trace_bench.contracts import write_json
            data=read_json(path/'canonical.json');data['prompt_sha256']='0'*64;write_json(path/'canonical.json',data)
            with self.assertRaisesRegex(ValueError,'broken binding: task.prompt'):
                validate_pack(path)
