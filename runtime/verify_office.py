#!/usr/bin/env python3
"""Agent-facing verifier for manifests without a historical custom verifier."""
import os
from pathlib import Path
import sys

project = Path(os.environ.get('OFFICE_TRACE_PROJECT', '/workspace'))
sys.path.insert(0, str(project))
import office
from office_trace_bench.contracts import dataset_path, read_json
from office_trace_bench.verify import verify

if __name__ == '__main__':
    workspace = Path(__file__).resolve().parents[1]
    selection = read_json(workspace / 'input/dataset_manifest.json')
    # Accept the family's positional invocation; verification uses the staged workspace.
    report = verify(dataset_path(selection['kind'], selection['dataset_id']), workspace,
                    workspace / 'output/business_verification.json',
                    deferred_outputs=('xlsx_enhancement_summary.json',) if selection['kind'] == 'xlsx' else ())
    print(report['status'])
    raise SystemExit(0 if report['status'] == 'success' else 1)
