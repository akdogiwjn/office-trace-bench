#!/usr/bin/env python3
"""Restore canonical outputs and reverify with current code; never execute helpers."""
from datetime import datetime,timezone
import argparse
from pathlib import Path
import shutil
import sys
import tempfile
import time
import uuid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import office
from office_trace_bench.canonical import validate_pack
from office_trace_bench.contracts import read_json,sha256,safe_relative,write_json
from office_trace_bench.runner import stage
from office_trace_bench.verify import verify

def verify_entry(entry):
    pack=ROOT/'artifacts'/entry['canonical_path'];canonical=validate_pack(pack)
    manifest=ROOT/entry['manifest_path']
    if sha256(manifest)!=canonical['manifest_sha256']:raise ValueError('current manifest differs from canonical input contract')
    with tempfile.TemporaryDirectory(prefix='office-canonical-output-') as tmp:
        workspace=Path(tmp);stage(manifest,workspace)
        outputs={}
        for name,spec in canonical['artifact_inventory'].items():
            if name.startswith('workspace/output/'):
                relative=safe_relative(name.removeprefix('workspace/'));target=workspace/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/'artifacts/objects/sha256'/spec['sha256'],target)
                outputs[str(relative)]=spec['sha256']
        print(entry['dataset_id'], 'verifying restored outputs',flush=True)
        report=verify(manifest,workspace)
        return dict(dataset_id=entry['dataset_id'],kind=entry['kind'],run_id=canonical['original_run_id'],
            trace_sha256=canonical['trace_sha256'],manifest_sha256=canonical['manifest_sha256'],output_hashes=outputs,verification=report)


def main(argv=None):
    suite=read_json(ROOT/'artifacts/suite.json')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',action='append',choices=[e['dataset_id'] for e in suite['datasets']],
                        help='Verify only this dataset; may be repeated. Default: all datasets.')
    parser.add_argument('--report',type=Path,help='Explicit report path. Default: a new report under qualification/canonical-verification/.')
    args=parser.parse_args(argv)
    selected=set(args.dataset or [e['dataset_id'] for e in suite['datasets']])
    entries=[e for e in suite['datasets'] if e['dataset_id'] in selected]
    full_suite=len(entries)==len(suite['datasets'])
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=args.report or ROOT/'qualification/canonical-verification'/f'{stamp}-{uuid.uuid4().hex[:8]}.json'
    if not full_suite and target.resolve()==(ROOT/'reports/canonical-output-regression-v2.json').resolve():
        parser.error('a dataset-selection report cannot overwrite the formal full-suite report')
    source_hashes={str(p.relative_to(ROOT)):sha256(p) for p in (ROOT/'office_trace_bench').glob('*.py')}
    source_hashes[str(Path(__file__).relative_to(ROOT))]=sha256(__file__)
    results=[]
    def checkpoint(status,active=None):
        completed={r['dataset_id'] for r in results}
        write_json(target,dict(schema_version='office-canonical-output-regression-v1',
            checked_at=datetime.now(timezone.utc).isoformat(),status=status,verifier_source_hashes=source_hashes,datasets=results,
            selection_scope='full_suite' if full_suite else 'dataset_selection',
            selected_dataset_ids=[e['dataset_id'] for e in entries],suite_dataset_count=len(suite['datasets']),
            completed_dataset_count=len(results),active_dataset=active,
            pending_dataset_ids=[e['dataset_id'] for e in entries if e['dataset_id'] not in completed],
            selection_complete=len(results)==len(entries),suite_complete=full_suite and len(results)==len(entries),
            scope='Current verifier on restored hash-bound canonical input/output artifacts. No model, helper execution, regeneration, recalc, performance measurements or ignored runs.'))
    print('Report:',target,flush=True)
    checkpoint('in_progress')
    try:
        for index,entry in enumerate(entries,1):
            name=entry['dataset_id'];checkpoint('in_progress',name)
            print(f'[{index}/{len(entries)}] {name} start: validate pack and restore outputs',flush=True)
            start=time.monotonic()
            try:
                result=verify_entry(entry)
            except Exception as exc:
                result=dict(dataset_id=name,kind=entry['kind'],verification=dict(status='error',failures=[f'{type(exc).__name__}: {exc}']))
            result['elapsed_seconds']=round(time.monotonic()-start,3);results.append(result)
            checkpoint('in_progress')
            print(name,result['verification']['status'],result['verification']['failures'],f"elapsed={result['elapsed_seconds']:.3f}s",flush=True)
    except KeyboardInterrupt:
        checkpoint('interrupted',name)
        print('Interrupted; completed results retained in',target,flush=True)
        return 130
    status='success' if all(r['verification']['status']=='success' for r in results) else 'failed'
    checkpoint(status)
    return 0 if status=='success' else 1

if __name__=='__main__':raise SystemExit(main())
