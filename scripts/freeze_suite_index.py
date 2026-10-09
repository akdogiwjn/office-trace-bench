#!/usr/bin/env python3
"""Bind exactly seven current dataset contracts to accepted canonical execution traces."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import office
from office_trace_bench.contracts import load_manifest,read_json,sha256,write_json
from office_trace_bench.canonical import validate_pack

SCOPE={('xlsx',name) for name in ('tlc','retail','manufacturing','hr')} | {('pdf',name) for name in ('opm','irs_w4','sba1919')}

def provenance_evidence():
    paths=list((ROOT/'sources/provenance-audit').glob('*'))
    paths += [ROOT/'reports'/name for name in ('hr-formal-kpi-provenance-v2.json','hr-sba-source-reliability-v1.json','hr-sba-source-reliability-v2.json')]
    return {str(path.relative_to(ROOT)):sha256(path) for path in sorted(paths) if path.is_file()}

def validate_evidence(suite):
    evidence=suite['provenance_evidence']
    if not evidence:raise ValueError('missing frozen source corroboration evidence')
    for name,digest in evidence.items():
        if sha256(ROOT/name)!=digest:raise ValueError('provenance evidence hash mismatch: '+name)
    for name in ('reports/hr-sba-source-reliability-v1.json','reports/hr-sba-source-reliability-v2.json'):
        record=read_json(ROOT/name)
        for extract,digest in record.get('source_extracts',{}).items():
            if evidence.get(extract)!=digest:raise ValueError('source corroboration/extract binding mismatch')
    for entry in suite['datasets']:
        root=(ROOT/entry['manifest_path']).parent;source=read_json(root/'provenance.json')
        if source.get('source_evidence'):
            if evidence.get(source['source_evidence'])!=source['source_evidence_sha256']:raise ValueError('official table evidence binding mismatch')
        if entry['dataset_id']=='hr':
            report=read_json(ROOT/source['formal_kpi_verification'])
            if report['status']!='success' or report['input_sha256']!=source['sha256']:raise ValueError('HR corroboration/input binding mismatch')
    qualification=suite['agent_qualification']
    if sha256(ROOT/qualification['path'])!=qualification['sha256']:raise ValueError('Agent qualification report hash mismatch')
    report=read_json(ROOT/qualification['path'])
    rows={(r['kind'],r['dataset_id']):r for r in report['datasets']}
    if report['status']!='success' or len(rows)!=7 or set(rows)!=SCOPE:raise ValueError('Agent qualification suite mismatch')
    for entry in suite['datasets']:
        row=rows[(entry['kind'],entry['dataset_id'])]
        if row['canonical_sha256']!=entry['canonical_sha256'] or row['manifest_sha256']!=entry['manifest_sha256']:
            raise ValueError('Agent qualification/canonical binding mismatch')
    if report['tlc_legacy_semantic_regression']['status']!='success' or report['opm_legacy_regression']['status']!='success':
        raise ValueError('legacy business qualification failed')

def validate_scenario(entry,canonical):
    if entry['kind']!='xlsx':return
    report_path=ROOT/entry['scenario_qualification']['path']
    if sha256(report_path)!=entry['scenario_qualification']['sha256']:raise ValueError('scenario report hash mismatch')
    report=read_json(report_path)
    inventory=canonical['artifact_inventory']
    frozen=read_json(ROOT/'artifacts/objects/sha256'/canonical['manifest_sha256'])
    workbook=inventory['workspace/output/'+frozen['output_workbook']]['sha256']
    if (report['status']!='success' or report['run_id']!=canonical['original_run_id']
        or report['source_trace_sha256']!=canonical['trace_sha256'] or report['source_workbook_sha256']!=workbook
        or report['expected_sha256']!=frozen['expected_sha256']
        or [s['scenario'] for s in report['scenarios']]!=[r['name'] for r in frozen['requirements']['scenario']['rows']]
        or not all(s['passed'] for s in report['scenarios'])):
        raise ValueError('scenario qualification binding mismatch')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--validate',action='store_true');args=parser.parse_args()
    target=ROOT/'artifacts/suite.json'
    if args.validate:
        suite=read_json(target)
        if len(suite['datasets'])!=7 or {(e['kind'],e['dataset_id']) for e in suite['datasets']}!=SCOPE:raise ValueError('suite must bind exactly the seven selected datasets')
        if suite['replay_ready'] is not False:raise ValueError('this suite has no executable replay qualification')
        validate_evidence(suite)
        for entry in suite['datasets']:
            path=ROOT/'artifacts'/entry['canonical_path'];canonical=validate_pack(path)
            if sha256(path/'canonical.json')!=entry['canonical_sha256']:raise ValueError('suite/canonical binding mismatch')
            manifest=ROOT/entry['manifest_path'];load_manifest(manifest)
            if sha256(manifest)!=canonical['manifest_sha256']:raise ValueError('active dataset differs from canonical trace')
            if sha256(manifest)!=entry['manifest_sha256']:raise ValueError('suite/manifest binding mismatch')
            validate_scenario(entry,canonical)
        print('7/7 current datasets, canonical objects and provenance links: OK');return
    entries=[]
    qualification_path=ROOT/'reports/current-agent-regression-v2.json'
    qualification_report=read_json(qualification_path)
    selections={(row['kind'],row['dataset_id']):row for row in qualification_report['datasets']}
    if len(selections)!=7 or set(selections)!=SCOPE:raise ValueError('explicit canonical selections must cover exactly seven datasets')
    for path in sorted((ROOT/'datasets').glob('*/*/manifest.json')):
        manifest=load_manifest(path);selection=selections[(manifest['kind'],manifest['dataset_id'])]
        chosen=ROOT/selection['canonical_path'];data=validate_pack(chosen)
        if (data['manifest_sha256']!=sha256(path) or data['original_run_id']!=selection['run_id']
            or sha256(chosen/'canonical.json')!=selection['canonical_sha256']):raise ValueError('explicit selection does not match current canonical/manifest')
        entry=dict(kind=manifest['kind'],dataset_id=manifest['dataset_id'],manifest_path=str(path.relative_to(ROOT)),
            manifest_sha256=sha256(path),canonical_path=str(chosen.relative_to(ROOT/'artifacts')),canonical_sha256=sha256(chosen/'canonical.json'))
        if manifest['kind']=='xlsx':
            report=ROOT/'reports'/('scenario-'+manifest['dataset_id']+'-v2.json')
            entry['scenario_qualification']=dict(path=str(report.relative_to(ROOT)),sha256=sha256(report))
            validate_scenario(entry,validate_pack(chosen))
        entries.append(entry)
    if len(entries)!=7 or {(e['kind'],e['dataset_id']) for e in entries}!=SCOPE:raise ValueError('suite scope must remain exactly seven datasets')
    qualification=ROOT/'reports/current-agent-regression-v2.json'
    suite=dict(schema_version='office-frozen-suite-v2',datasets=entries,replay_ready=False,provenance_evidence=provenance_evidence(),
        agent_qualification=dict(path=str(qualification.relative_to(ROOT)),sha256=sha256(qualification)),
        research_scope='Agent/tool workload characterization with workbook complexity; future frozen tool replay without LLM.',
        source_limits='Retail/M3 official-table transcriptions; HR unexpanded cached native XLSX with partial official corroboration. See per-input provenance.',
        replay_gate='Executable recipe compilation, dependency review and isolated tool replay validation are a later explicitly separate phase.')
    validate_evidence(suite);write_json(target,suite)
    print('Published artifacts/suite.json; canonical run identities are machine-bound.')

if __name__=='__main__':main()
