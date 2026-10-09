import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import office
from office_trace_bench import context
from office_trace_bench.contracts import dataset_path, load_manifest, write_json


class ContextProfileTests(unittest.TestCase):
    def test_only_background_files_are_frozen(self):
        manifest = load_manifest(dataset_path('xlsx', 'tlc'))
        path, profile = context.load_profile(manifest)
        assets = {str(p.relative_to(path.parent)) for p in path.parent.rglob('*') if p.is_file()}
        self.assertEqual(assets, set(profile['files']) | {'profile.json'})
        self.assertEqual(set(profile['files']), {f'workspace/{name}' for name in context.BACKGROUND} |
                         {'skills/agent-browser/SKILL.md'})

    def test_added_bootstrap_or_changed_registry_fails_audit(self):
        manifest = load_manifest(dataset_path('xlsx', 'tlc'))
        _, profile = context.load_profile(manifest)
        expected = profile['historical_references']['xlsx']
        report = dict(injectedWorkspaceFiles=[dict(name=k, rawChars=v) for k, v in expected['workspace_files'].items()],
                      skills=expected['skills'], tools=dict(schemaChars=expected['tool_schema_chars']),
                      workspaceDir=expected['workspace_dir'])
        hashes = {Path(name).name: digest for name, digest in profile['files'].items()
                  if name.startswith('workspace/')}
        with tempfile.TemporaryDirectory() as tmp:
            stdout = Path(tmp) / 'stdout.json'
            def audit():
                write_json(stdout, dict(meta=dict(systemPromptReport=report)))
                return context.audit_context(manifest, profile, stdout, hashes, hashes)['matched']
            self.assertTrue(audit())
            report['injectedWorkspaceFiles'].append(dict(name='BOOTSTRAP.md', rawChars=1510))
            self.assertFalse(audit())
            report['injectedWorkspaceFiles'].pop()
            report['skills'] = dict(hash='changed')
            self.assertFalse(audit())


if __name__ == '__main__':
    unittest.main()
