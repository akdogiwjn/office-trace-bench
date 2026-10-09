#!/usr/bin/env python3
"""Independent known-input Skill qualification; never an Agent trace or measured run."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import dataset_path, read_json, write_json
from office_trace_bench.runner import stage
from office_trace_bench.verify import expected_pdf_fields, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    path = dataset_path('pdf', args.dataset)
    manifest = stage(path, workspace)
    output = workspace / 'output'
    scripts = ROOT / 'vendor/skills/pdf/scripts'
    form = workspace / 'input' / manifest['form']
    records_data = read_json(workspace / 'input' / manifest['records'])
    records = records_data[manifest['records_key']]
    schema_path = output / 'form_field_info.json'
    with (output / 'check_fillable_fields.log').open('w') as stream:
        subprocess.run([sys.executable, str(scripts / 'check_fillable_fields.py'), str(form)], stdout=stream, check=True)
    subprocess.run([sys.executable, str(scripts / 'extract_form_field_info.py'), str(form), str(schema_path)], check=True)
    schema = {x['field_id']: x for x in read_json(schema_path)}
    def render(source, target):
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(scripts / 'convert_pdf_to_images.py'), str(source), str(target)], check=True)
    render(form, output / 'rendered/template')
    (output / 'field_values').mkdir()
    (output / 'filled').mkdir()
    for record in records:
        fields = expected_pdf_fields(record, records_data, manifest['requirements']['field_rules'])
        values = [dict(field_id=fid, page=schema[fid]['page'], description='Independent qualification fixture', value=value)
                  for fid, value in fields.items()]
        mapping = output / 'field_values' / (record['id'] + '.json')
        write_json(mapping, values)
        target = output / 'filled' / (record['id'] + '.pdf')
        subprocess.run([sys.executable, str(scripts / 'fill_fillable_fields.py'), str(form), str(mapping), str(target)], check=True)
        render(target, output / 'rendered' / record['id'])
    write_json(output / 'batch_summary.json', manifest['summary_contract'])
    report = verify(path, workspace, output / 'business_verification.json')
    write_json(workspace.parent / 'qualification.json', dict(status=report['status'], failures=report['failures'],
        execution='independent-fixture-qualification; not an Agent trace', dataset=args.dataset,
        record_count=len(records), report='workspace/output/business_verification.json'))
    print('qualification', report['status'], report['failures'])
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
