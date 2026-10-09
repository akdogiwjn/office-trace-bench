#!/usr/bin/env python3
"""Pre-fill dry run: replicate the verifier's mapping contract WITHOUT invoking
the fill script, so the normal fill invocations never fail or need repair.

Checks, per record:
  * the emitted field-id set exactly equals the manifest rule field-id set
  * each item's page equals the actual schema page
  * no protected field is present
  * each value matches the manifest-derived expectation (leading '/' ignored)
"""
import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))
MANIFEST = WS / 'input/dataset_manifest.json'
RECORDS = WS / 'input/synthetic_applicants.json'
FIELD_INFO = WS / 'output/form_field_info.json'
VALUES = WS / 'output/field_values'


def pv(value):
    return '' if value is None else str(value).lstrip('/')


def expected_pdf_fields(record, records_data, rules):
    values = {}
    for rule in rules:
        if 'constant' in rule:
            value = rule['constant']
        else:
            data = records_data if rule.get('source') == 'shared' else record
            for part in rule['value_from'].split('.'):
                data = data[part]
            value = data
        if 'choices' in rule:
            key = str(value).lower() if isinstance(value, bool) else str(value)
            value = rule['choices'][key]
        values[rule['field_id']] = value
    return values


def main():
    manifest = json.loads(MANIFEST.read_text())
    req = manifest['requirements']
    records_data = json.loads(RECORDS.read_text())
    records = records_data[manifest['records_key']]
    schema = {f['field_id']: f for f in json.loads(FIELD_INFO.read_text())}
    rules_by_id = {r['field_id']: r for r in req['field_rules']}
    protected = set(req['protected_blank'])

    failures = []
    for record in records:
        rid = record['id']
        values = json.loads((VALUES / (rid + '.json')).read_text())
        by_id = {v['field_id']: v for v in values}
        wanted = expected_pdf_fields(record, records_data, req['field_rules'])
        if len(by_id) != len(values):
            failures.append(f'{rid}: duplicate field ids')
        if set(by_id) != set(wanted):
            failures.append(f'{rid}: field set mismatch '
                            f'missing={sorted(set(wanted) - set(by_id))} '
                            f'extra={sorted(set(by_id) - set(wanted))}')
        for fid, exp in wanted.items():
            item = by_id.get(fid)
            if item is None:
                continue
            if pv(item.get('value')) != pv(exp):
                failures.append(f'{rid}: value mismatch {fid!r} {item.get("value")!r} != {exp!r}')
            if item['page'] != schema[fid]['page']:
                failures.append(f'{rid}: page mismatch {fid!r} {item["page"]} != {schema[fid]["page"]}')
        if set(by_id) & protected:
            failures.append(f'{rid}: protected fields present {sorted(set(by_id) & protected)}')

    if failures:
        print('DRY RUN FAILED')
        for f in failures:
            print(' -', f)
        sys.exit(1)
    print(f'DRY RUN OK: {len(records)} records, '
          f'{len(req["field_rules"])} mapped fields each, 0 protected fields')


if __name__ == '__main__':
    main()
