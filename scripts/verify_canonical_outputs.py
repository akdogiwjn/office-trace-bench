#!/usr/bin/env python3
"""Restore canonical outputs and reverify with current code; never execute helpers."""
from datetime import datetime,timezone
from pathlib import Path
import shutil
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import office
from office_trace_bench.canonical import validate_pack
from office_trace_bench.contracts import read_json,sha256,safe_relative,write_json
from office_trace_bench.runner import stage
from office_trace_bench.verify import verify

def main():
    suite=read_json(ROOT/'artifacts/suite.json');results=[]
    for entry in suite['datasets']:
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
            report=verify(manifest,workspace)
            results.append(dict(dataset_id=entry['dataset_id'],kind=entry['kind'],run_id=canonical['original_run_id'],
                trace_sha256=canonical['trace_sha256'],manifest_sha256=canonical['manifest_sha256'],output_hashes=outputs,verification=report))
            print(entry['dataset_id'],report['status'],report['failures'],flush=True)
    source_hashes={str(p.relative_to(ROOT)):sha256(p) for p in (ROOT/'office_trace_bench').glob('*.py')}
    source_hashes[str(Path(__file__).relative_to(ROOT))]=sha256(__file__)
    status='success' if len(results)==7 and all(r['verification']['status']=='success' for r in results) else 'failed'
    write_json(ROOT/'reports/canonical-output-regression-v2.json',dict(schema_version='office-canonical-output-regression-v1',
        checked_at=datetime.now(timezone.utc).isoformat(),status=status,verifier_source_hashes=source_hashes,datasets=results,
        scope='Current verifier on restored hash-bound canonical input/output artifacts. No model, helper execution, regeneration, recalc, performance measurements or ignored runs.'))
    return 0 if status=='success' else 1

if __name__=='__main__':raise SystemExit(main())
