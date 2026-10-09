"""Selection, report protection and interrupted-checkpoint behavior without large workbooks."""
import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from scripts import verify_canonical_outputs as cli
from office_trace_bench.contracts import read_json,sha256


def successful(entry):
    return dict(dataset_id=entry['dataset_id'],kind=entry['kind'],
                verification=dict(status='success',failures=[]))


class CanonicalOutputCliTests(unittest.TestCase):
    def test_selection_deduplicates_and_keeps_frozen_report(self):
        frozen=cli.ROOT/'reports/canonical-output-regression-v2.json';before=sha256(frozen)
        with TemporaryDirectory() as tmp, patch.object(cli,'verify_entry',side_effect=successful) as verify, contextlib.redirect_stdout(io.StringIO()):
            target=Path(tmp)/'report.json'
            code=cli.main(['--dataset','retail','--dataset','retail','--report',str(target)])
            report=read_json(target)
            self.assertEqual(code,0);self.assertEqual(verify.call_count,1)
            self.assertEqual(verify.call_args.args[0]['dataset_id'],'retail')
            self.assertEqual(report['selection_scope'],'dataset_selection')
            self.assertEqual(report['selected_dataset_ids'],['retail'])
            self.assertTrue(report['selection_complete']);self.assertFalse(report['suite_complete'])
            self.assertEqual(sha256(frozen),before)

    def test_interruption_retains_completed_results_and_active_dataset(self):
        with TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            target=Path(tmp)/'report.json'
            def interrupt_second(entry):
                if entry['dataset_id']=='manufacturing':return successful(entry)
                checkpoint=read_json(target)
                self.assertEqual(checkpoint['status'],'in_progress')
                self.assertEqual(checkpoint['completed_dataset_count'],1)
                self.assertEqual(checkpoint['active_dataset'],'retail')
                raise KeyboardInterrupt
            with patch.object(cli,'verify_entry',side_effect=interrupt_second):
                code=cli.main(['--dataset','retail','--dataset','manufacturing','--report',str(target)])
            report=read_json(target)
            self.assertEqual(code,130);self.assertEqual(report['status'],'interrupted')
            self.assertEqual([d['dataset_id'] for d in report['datasets']],['manufacturing'])
            self.assertEqual(report['pending_dataset_ids'],['retail'])
            self.assertFalse(report['selection_complete']);self.assertFalse(report['suite_complete'])

    def test_error_returns_failure_and_keeps_other_suite_results(self):
        with TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            target=Path(tmp)/'report.json'
            def fail_one(entry):
                if entry['dataset_id']=='hr':raise ValueError('input binding mismatch')
                return successful(entry)
            with patch.object(cli,'verify_entry',side_effect=fail_one):
                code=cli.main(['--report',str(target)])
            report=read_json(target)
            self.assertEqual(code,1);self.assertEqual(report['status'],'failed')
            self.assertEqual(report['selection_scope'],'full_suite')
            self.assertEqual(report['completed_dataset_count'],7)
            self.assertTrue(report['selection_complete']);self.assertTrue(report['suite_complete'])
            self.assertEqual(next(d for d in report['datasets'] if d['dataset_id']=='hr')['verification']['status'],'error')

    def test_partial_report_cannot_overwrite_formal_suite_report(self):
        target=cli.ROOT/'reports/canonical-output-regression-v2.json';before=sha256(target)
        with patch.object(cli,'verify_entry') as verify, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                cli.main(['--dataset','retail','--report',str(target)])
            self.assertEqual(error.exception.code,2);verify.assert_not_called()
        self.assertEqual(sha256(target),before)
