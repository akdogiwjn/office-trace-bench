#!/usr/bin/env python3
"""Batch mapping builder for SUB-MEM-PDF-SBA1919-01.

Reads the frozen manifest, the supplied records and the ACTUAL extracted field
schema (output/form_field_info.json) and writes one field_values/<id>.json per
record. Field IDs and page numbers come from the real inspection; only the
manifest's field_rules are populated. Protected fields are never emitted.
"""
import json
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
MANIFEST = WS / 'input/dataset_manifest.json'
RECORDS = WS / 'input/synthetic_applicants.json'
FIELD_INFO = WS / 'output/form_field_info.json'
OUT = WS / 'output/field_values'


def derive_value(rule, record, records_data):
    data = records_data if rule.get('source') == 'shared' else record
    for part in rule['value_from'].split('.'):
        data = data[part]
    value = data
    if 'choices' in rule:
        key = str(value).lower() if isinstance(value, bool) else str(value)
        value = rule['choices'][key]
    return value


def main():
    manifest = json.loads(MANIFEST.read_text())
    records_data = json.loads(RECORDS.read_text())
    records = records_data[manifest['records_key']]
    field_info = json.loads(FIELD_INFO.read_text())
    schema_page = {f['field_id']: f['page'] for f in field_info}

    rules = manifest['requirements']['field_rules']
    protected = set(manifest['requirements']['protected_blank'])
    OUT.mkdir(parents=True, exist_ok=True)

    mapping_report = {}
    for record in records:
        items = []
        for rule in rules:
            fid = rule['field_id']
            if fid not in schema_page:
                raise SystemExit(f'field id {fid!r} missing from actual schema')
            if fid in protected:
                raise SystemExit(f'refusing to populate protected field {fid!r}')
            items.append({
                'field_id': fid,
                'description': rule['semantic'],
                'page': schema_page[fid],
                'value': derive_value(rule, record, records_data),
            })
        out_path = OUT / (record['id'] + '.json')
        out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + '\n')
        mapping_report[record['id']] = len(items)

    print(f'wrote {len(mapping_report)} field_values files '
          f'({sorted(set(mapping_report.values()))} fields each) to {OUT}')


if __name__ == '__main__':
    main()
