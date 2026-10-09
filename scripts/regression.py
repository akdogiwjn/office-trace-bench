#!/usr/bin/env python3
"""Compare new and legacy verifiers on archived artifacts, without model calls."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import dataset_path, read_json, write_json
from office_trace_bench.runner import stage
from office_trace_bench.verify import verify


def main():
    reports = {}
    for kind, dataset in [('xlsx', 'tlc'), ('pdf', 'opm')]:
        print(f'checking archived {kind}/{dataset}', flush=True)
        with tempfile.TemporaryDirectory(prefix='office-regression-') as directory:
            workspace = Path(directory) / 'workspace'
            manifest_path = dataset_path(kind, dataset)
            stage(manifest_path, workspace)
            shutil.copytree(ROOT / 'legacy' / kind / 'output', workspace / 'output', dirs_exist_ok=True)
            report = verify(manifest_path, workspace, ROOT / 'reports' / f'{dataset}-archived-regression.json')
            if kind == 'xlsx':
                args = ['legacy/xlsx/verify_xlsx_enhanced.py', str(workspace / 'output/monthly_operations_report.xlsx'),
                        str(workspace / 'output/formula_recalc.json'), str(Path(directory) / 'legacy-report.json')]
            else:
                args = ['legacy/pdf/verify_pdf_batch.py', str(workspace / 'input/of306_aug2023.pdf'),
                        str(workspace / 'input/synthetic_applicants.json'), str(workspace / 'output'), str(Path(directory) / 'legacy-report.json')]
            # Execute via runpy in this process's bootstrapped dependency environment.
            code = 'import sys,runpy;import office;sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name="__main__")'
            result = subprocess.run([sys.executable, '-c', code, *args], cwd=ROOT, capture_output=True, text=True)
            legacy = read_json(Path(directory) / 'legacy-report.json') if (Path(directory) / 'legacy-report.json').exists() else {'status': 'error', 'error': result.stderr[-1000:]}
            reports[dataset] = {'new_verifier': report['status'], 'new_failures': report['failures'],
                                'legacy_verifier': legacy['status'], 'legacy_exit_code': result.returncode,
                                'legacy_failures': legacy.get('failures'), 'legacy_error': legacy.get('error')}
            print(json.dumps(reports[dataset]), flush=True)
    ok = all(r['new_verifier'] == r['legacy_verifier'] == 'success' and r['legacy_exit_code'] == 0 for r in reports.values())
    write_json(ROOT / 'reports/archived-regression-summary.json', {
        'status': 'success' if ok else 'failed', 'scope': 'Historical artifacts only; this does not prove a new generic-prompt Agent run succeeded.', 'datasets': reports})
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
