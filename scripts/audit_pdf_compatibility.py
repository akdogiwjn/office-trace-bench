#!/usr/bin/env python3
"""Recheck retained OPM outputs under the explicit current alias contract."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import dataset_path, read_json, sha256, write_json
from office_trace_bench.verify import verify


def main():
    manifest = dataset_path('pdf', 'opm')
    runs = [ROOT / 'runs' / ('control-' + variant + '-pdf-opm-20261008T163759Z-90a05c03')
            for variant in ('old', 'new')]
    rows = []
    for run in runs:
        before = {str(p.relative_to(run / 'workspace/output')): sha256(p)
                  for p in (run / 'workspace/output').rglob('*') if p.is_file()}
        target = ROOT / 'reports' / (run.name + '-current-contract.json')
        result = verify(manifest, run / 'workspace', target)
        after = {str(p.relative_to(run / 'workspace/output')): sha256(p)
                 for p in (run / 'workspace/output').rglob('*') if p.is_file()}
        rows.append(dict(run_id=run.name, original_status=read_json(run / 'run_manifest.json')['status'],
                         current_contract_status=result['status'], failures=result['failures'],
                         outputs_unchanged=before == after, report=str(target.relative_to(ROOT))))
    ok = all(r['current_contract_status'] == 'success' and r['outputs_unchanged'] for r in rows)
    write_json(ROOT / 'reports/pdf-contract-compatibility-v7.json', dict(
        status='success' if ok else 'failed', manifest_sha256=sha256(manifest),
        verifier_sha256=sha256(ROOT / 'office_trace_bench/verify.py'), runs=rows,
        scope='Post hoc revalidation under explicitly declared equivalence; original attempts and v6 audits remain unchanged.'))
    print(rows)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
