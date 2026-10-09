#!/usr/bin/env python3
"""Select two explicitly accepted native-input traces; retain the other five identities."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import office
from office_trace_bench.canonical import validate_pack
from office_trace_bench.contracts import load_manifest,read_json,write_json,sha256


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--retail-run',required=True)
    p.add_argument('--manufacturing-run',required=True)
    args=p.parse_args()
    report=read_json(ROOT/'reports/current-agent-regression-v2.json')
    replacements={};superseded=[]
    for name,run_id in [('retail',args.retail_run),('manufacturing',args.manufacturing_run)]:
        if Path(run_id).name!=run_id:raise ValueError('run ID must be a single path component')
        run=ROOT/'runs'/run_id;info=read_json(run/'run_manifest.json')
        path=ROOT/'artifacts/canonical/xlsx'/name/run_id;canonical=validate_pack(path)
        manifest_path=ROOT/'datasets/xlsx'/name/'manifest.json';m=load_manifest(manifest_path)
        if (info['dataset_id']!=name or info['status']!='success' or info['baseline_accepted'] is not True
            or canonical['manifest_sha256']!=sha256(manifest_path) or canonical['original_run_id']!=run_id):
            raise ValueError('not an accepted current native run: '+name)
        previous=next(row for row in report['datasets'] if row['kind']=='xlsx' and row['dataset_id']==name)
        superseded.append(previous['run_id'])
        trajectory=read_json(path/'trajectory.json');events=read_json(path/'tool_events.json')
        replacements[name]=dict(dataset_id=name,kind='xlsx',run_id=run_id,status='success',accepted=True,
            canonical_path=str(path.relative_to(ROOT)),canonical_sha256=sha256(path/'canonical.json'),
            trace_sha256=canonical['trace_sha256'],manifest_sha256=canonical['manifest_sha256'],
            input_hashes=canonical['input_hashes'],prompt_template_sha256=canonical['prompt_template_sha256'],
            agent=canonical['model'],runtime_image_id=canonical['runtime_image_id'],
            trace_steps=len(trajectory['steps']),tool_calls=len(events['events']),
            verifier_result=canonical['verifier_result'],provenance_sha256=m['analysis_metadata']['provenance.json'],
            revision_capture=dict(present=canonical['revision_capture']['present'],gaps=canonical['revision_capture']['gaps']),
            agent_seconds=info['agent_seconds'],independent_verification_seconds=info['verification_seconds'])
    report['datasets']=[replacements.get(row['dataset_id'],row) if row['kind']=='xlsx' else row for row in report['datasets']]
    report['generated_at']=datetime.now(timezone.utc).isoformat()
    report['suite_revision']='native-xlsx-v3'
    report['superseded_successes']=list(dict.fromkeys(report.get('superseded_successes',[])+superseded))
    report['native_input_evidence']=dict(path='reports/official-native-input-provenance-v3.json',sha256=sha256(ROOT/'reports/official-native-input-provenance-v3.json'))
    report['hr_trace_retention']=dict(reason='Input bytes, Prompt, task manifest and canonical unchanged; official acquisition supplement is hash-bound separately.',
        evidence_path='datasets/xlsx/hr/provenance-supplement.json',evidence_sha256=sha256(ROOT/'datasets/xlsx/hr/provenance-supplement.json'))
    report['source_identity_scope']='Retail/M3 independently redownloaded official native XLSX, exact input SHA256 match. HR owner-supplied official extraction matches existing cache bytes; independent official ZIP fetch returns 403. Other historical source limits retained.'
    write_json(ROOT/'reports/current-agent-regression-v2.json',report)
    print('Selected explicit native Retail/Manufacturing traces; other five selected identities retained.')


if __name__=='__main__':main()
