#!/usr/bin/env python3
"""Test the exact staged Git tree in isolation, without runs or a sibling repo."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def inside(report):
    sys.path.insert(0,str(ROOT))
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    counts=dict(total=result.testsRun,passed=result.testsRun-len(result.skipped)-len(result.failures)-len(result.errors)-len(result.expectedFailures)-len(result.unexpectedSuccesses),
                skipped=len(result.skipped),failed=len(result.failures),errors=len(result.errors),expected_failures=len(result.expectedFailures),unexpected_successes=len(result.unexpectedSuccesses))
    Path(report).write_text(json.dumps(dict(counts=counts,successful=result.wasSuccessful(),
        skips=[dict(test=str(test),reason=reason) for test,reason in result.skipped],
        failures=[dict(test=str(test),detail=detail) for test,detail in result.failures+result.errors]),indent=2)+'\n')
    return 0 if result.wasSuccessful() else 1

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inside-report',type=Path);args=parser.parse_args()
    if args.inside_report:return inside(args.inside_report)
    tree=subprocess.check_output(['git','write-tree'],cwd=ROOT,text=True).strip()
    environment=dict(os.environ);environment.pop('PYTHONPATH',None)
    with tempfile.TemporaryDirectory(prefix='office-independent-') as tmp:
        folder=Path(tmp)/'checkout';folder.mkdir();archive=Path(tmp)/'tree.tar'
        subprocess.run(['git','archive',tree,'--output',str(archive)],cwd=ROOT,check=True)
        with tarfile.open(archive) as stream:stream.extractall(folder,filter='data')
        for name in ('runs','.snapshots','qualification'):
            if (folder/name).exists():raise ValueError('ephemeral runtime directory in publication tree')
        results=[]
        commands=[[sys.executable,'scripts/check_self_contained.py','--inside-report',str(Path(tmp)/'unit.json')],
                  ['make','regression'],[sys.executable,'scripts/freeze_suite_index.py','--validate'],
                  [sys.executable,'scripts/verify_canonical_outputs.py','--report','qualification/canonical-output-regression-current.json']]
        for command in commands:
            print('Isolated check:',command[1] if command[0]==sys.executable else 'make regression',flush=True)
            process=subprocess.run(command,cwd=folder,env=environment,capture_output=True,text=True)
            results.append(dict(check='unit_tests' if '--inside-report' in command else 'legacy_regression' if command[0]=='make' else 'canonical_outputs' if 'scripts/verify_canonical_outputs.py' in command else 'canonical_suite',
                                exit_code=process.returncode,stdout=process.stdout,stderr=process.stderr))
            print(process.stdout,flush=True)
            if process.returncode:print(process.stderr,flush=True)
        unit=json.loads((Path(tmp)/'unit.json').read_text())
        restored_report=folder/'qualification/canonical-output-regression-current.json'
        if restored_report.exists():
            import shutil
            shutil.copyfile(restored_report,ROOT/'reports/canonical-output-regression-v2.json')
        report=dict(schema_version='office-independent-checks-v2',checked_at=datetime.now(timezone.utc).isoformat(),
            publication_tree_sha1=tree,checkout_method='git archive of staged tree; no sibling repository, Git history, runs, snapshots or qualification directories',
            python_version=sys.version.split()[0],status='success' if all(r['exit_code']==0 for r in results) else 'failed',
            unit_tests=unit,checks=results,scope='Self-contained unit/integration, frozen legacy artifact regression, and canonical/hash/scenario verification. No Agent or LLM calls; no CPU/OS replay.')
        target=ROOT/'reports/self-contained-tests-v2.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(status=report['status'],counts=unit['counts'],report=str(target.relative_to(ROOT)))))
        return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
