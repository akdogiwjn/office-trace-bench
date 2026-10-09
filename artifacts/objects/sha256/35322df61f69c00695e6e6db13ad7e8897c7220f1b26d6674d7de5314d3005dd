"""Shared structural checks plus manifest-defined business expectations."""
import gc
import json
import math
import sys
from pathlib import Path

from .contracts import ROOT, load_manifest, read_json, sha256, write_json
from .workbooks import chart_sources, logical_value, normalized_formula, sheet_digest

ERRORS = {'#REF!', '#DIV/0!', '#VALUE!', '#N/A', '#NAME?', '#NUM!', '#NULL!'}


class Checks:
    def __init__(self, manifest):
        self.data = {'schema_version': 'office-verification-v1', 'dataset_id': manifest['dataset_id'],
                     'kind': manifest['kind'], 'status': 'failed', 'checks': {}, 'failures': []}

    def add(self, name, ok, detail=None):
        self.data['checks'][name] = {'ok': bool(ok), 'detail': detail}
        if not ok:
            self.data['failures'].append(name)

    def finish(self):
        self.data['status'] = 'failed' if self.data['failures'] else 'success'
        return self.data


def same_number(actual, expected):
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-6)
    return actual == expected


def color(cell, required):
    value = cell.font.color
    return value is not None and value.type == 'rgb' and str(value.rgb).upper().endswith(required.upper())


def normalized_number_format(value):
    # LibreOffice quotes literal currency symbols when serializing OOXML.
    return str(value).replace('"', '').replace('\\', '')


def preserved_value(actual, expected):
    logical = logical_value(actual)
    if logical[0] == expected[0] == 'number':
        # Exact integer values; tolerate only the serialization noise of decimals.
        if str(expected[1]).lstrip('-').isdigit():
            return float(logical[1]) == float(expected[1])
        return math.isclose(float(logical[1]), float(expected[1]), rel_tol=1e-10, abs_tol=1e-10)
    return logical == expected


def verify_xlsx(manifest, expected, workspace, checks, deferred_outputs=()):
    from openpyxl import load_workbook
    req = manifest['requirements']
    path = workspace / 'output' / manifest['output_workbook']
    checks.add('workbook_file', path.is_file() and path.stat().st_size >= req.get('minimum_bytes', 1))
    if not path.is_file():
        return
    book = load_workbook(path, data_only=False)
    try:
        name = req['summary_sheet']
        checks.add('sheet_order', book.sheetnames == [name, *req['base_sheets']], book.sheetnames)
        if name not in book:
            return
        sheet = book[name]
        for raw_name, baseline in expected['baseline']['raw_sheets'].items():
            actual = sheet_digest(book[raw_name]) if raw_name in book else None
            checks.add('raw_preserved:' + raw_name, actual == baseline, actual)
        for original, formulas in expected['baseline']['formulas'].items():
            unchanged = original in book and all(normalized_formula(book[original][cell].value) == formula for cell, formula in formulas.items())
            checks.add('original_formulas:' + original, unchanged)
        for original, values in expected['baseline'].get('values', {}).items():
            unchanged = original in book and all(preserved_value(book[original][cell].value, value) for cell, value in values.items())
            checks.add('original_values:' + original, unchanged)
        for original, charts in expected['baseline']['charts'].items():
            available = [chart_sources(chart) for chart in book[original]._charts] if original in book else []
            remaining = list(available)
            for source in charts:
                if source in remaining:
                    remaining.remove(source)
                else:
                    checks.add('original_charts:' + original, False, available)
                    break
            else:
                checks.add('original_charts:' + original, True, available)
        cells = [*req['metrics'], *req['scenario']['formula_metrics']]
        for metric in cells:
            cell = sheet[metric['cell']]
            formula = normalized_formula(cell.value)
            checks.add('formula:' + cell.coordinate, cell.data_type == 'f' and all(normalized_formula(ref) in formula for ref in metric.get('required_references', [])), cell.value)
            if 'font_color' in metric:
                checks.add('color:' + cell.coordinate, color(cell, metric['font_color']))
            if 'number_format' in metric:
                checks.add('number_format:' + cell.coordinate, normalized_number_format(cell.number_format) == normalized_number_format(metric['number_format']), cell.number_format)
        formula_count = sum(cell.data_type == 'f' for s in book.worksheets if s.title not in req['raw_sheets'] for row in s.iter_rows() for cell in row)
        checks.add('formula_count', formula_count >= req['minimum_formula_count'], formula_count)
        scenario = req['scenario']
        control = scenario['selector_cell']
        checks.add('scenario_default', sheet[control].value == scenario['default'])
        choices = ','.join(item['name'] for item in scenario['rows'])
        checks.add('scenario_dropdown', any(v.type == 'list' and control in v.sqref and str(v.formula1).strip('"') == choices for v in sheet.data_validations.dataValidation))
        for row in scenario['rows']:
            checks.add('scenario_table:' + row['name'], all(same_number(sheet[cell].value, value) for cell, value in row['cells'].items()))
        checks.add('scenario_input_color', color(sheet[control], '0000FF'))
        sources = [chart_sources(chart) for chart in sheet._charts]
        checks.add('executive_chart_count', len(sources) >= len(req['charts']), len(sources))
        for spec in req['charts']:
            checks.add('chart_sources:' + spec['id'], any(all(any(normalized_formula(ref) in found for found in source) for ref in spec['required_references']) for source in sources), sources)
        checks.add('conditional_formatting', len(sheet.conditional_formatting) >= req['minimum_conditional_formats'])
        checks.add('comments', sum(cell.comment is not None for row in sheet.iter_rows() for cell in row) >= req['minimum_comments'])
        checks.add('freeze_panes', sheet.freeze_panes is not None)
        checks.add('no_external_links', not book._external_links)
    finally:
        book.close()
        del book
        gc.collect()
    cached = load_workbook(path, data_only=True, read_only=True)
    try:
        for cell, value in expected['cached_values'].items():
            actual = cached[req['summary_sheet']][cell].value
            checks.add('cached_value:' + cell, same_number(actual, value), {'actual': actual, 'expected': value})
        errors = [f'{s.title}!{cell.coordinate}' for s in cached.worksheets if s.title not in req['raw_sheets'] for row in s.iter_rows() for cell in row if cell.data_type == 'e' or (isinstance(cell.value, str) and cell.value in ERRORS)]
        checks.add('zero_formula_errors', not errors, errors)
    finally:
        cached.close()
    recalc = read_json(workspace / 'output/formula_recalc.json')
    checks.add('recalc_report', recalc.get('status') == 'success' and recalc.get('total_errors') == 0 and int(recalc.get('total_formulas') or 0) >= req['minimum_formula_count'], recalc)
    for item in manifest.get('publish_files', []):
        published = workspace / 'output' / item['output']
        checks.add('published:' + item['output'], published.is_file() and sha256(published) == item['sha256'])
    for filename in manifest['required_outputs']:
        if filename == 'business_verification.json' or filename in deferred_outputs:
            continue  # This invocation creates the verification report after its checks.
        checks.add('deliverable:' + filename, (workspace / 'output' / filename).is_file())


def pdf_value(value):
    return '' if value is None else str(value).lstrip('/')


def pdf_field_matches(actual, expected, rule):
    """Allow only explicitly declared equivalent values for this field."""
    variants = [expected, *rule.get('value_aliases', {}).get(str(expected), [])]
    return pdf_value(actual) in [pdf_value(value) for value in variants]


def expected_pdf_fields(record, records, rules):
    values = {}
    for rule in rules:
        if 'constant' in rule:
            value = rule['constant']
        else:
            data = records if rule.get('source') == 'shared' else record
            for part in rule['value_from'].split('.'):
                data = data[part]
            value = data
        if 'choices' in rule:
            key = str(value).lower() if isinstance(value, bool) else str(value)
            value = rule['choices'][key]
        values[rule['field_id']] = value
    return values


def verify_pdf(manifest, expected, workspace, checks):
    from pypdf import PdfReader
    from PIL import Image, ImageChops
    sys.path.insert(0, str(ROOT / 'vendor/skills/pdf/scripts'))
    from extract_form_field_info import get_field_info
    req = manifest['requirements']
    records_data = read_json(workspace / 'input' / manifest['records'])
    records = records_data[manifest['records_key']]
    reader = PdfReader(workspace / 'input' / manifest['form'])
    field_schema = get_field_info(reader)
    checks.add('template_form', len(reader.pages) == req['page_count'] and len(field_schema) == req['field_count'])
    inspection = read_json(workspace / 'output/form_field_info.json')
    checks.add('field_inspection', inspection == field_schema)
    checks.add('record_count', len(records) == req['record_count'] and len({r['id'] for r in records}) == len(records))
    def check_images(directory, label):
        paths = list(directory.glob('page_*.png'))
        required = {f'page_{n}.png' for n in range(1, req['page_count'] + 1)}
        ok = {p.name for p in paths} == required
        for p in paths:
            try:
                with Image.open(p) as image:
                    image.verify()
                ok = ok and p.stat().st_size >= req.get('minimum_png_bytes', 1)
            except (OSError, ValueError):
                ok = False
        checks.add('render:' + label, ok, len(paths))
    output = workspace / 'output'
    template_dir = output / 'rendered/template'
    check_images(template_dir, 'template')
    for record in records:
        record_id = record['id']
        values_path = output / 'field_values' / (record_id + '.json')
        pdf_path = output / 'filled' / (record_id + '.pdf')
        values = read_json(values_path)
        by_id = {v['field_id']: v for v in values}
        fields = PdfReader(pdf_path).get_fields() or {}
        checks.add('pages:' + record_id, len(PdfReader(pdf_path).pages) == req['page_count'])
        checks.add('pdf_size:' + record_id, pdf_path.stat().st_size >= req.get('minimum_pdf_bytes', 1))
        wanted = expected_pdf_fields(record, records_data, req['field_rules'])
        rules_by_id = {rule['field_id']: rule for rule in req['field_rules']}
        checks.add('mapping:' + record_id, len(by_id) == len(values) and set(by_id) == set(wanted) and all(pdf_field_matches(by_id[fid].get('value'), v, rules_by_id[fid]) for fid, v in wanted.items()))
        checks.add('field_values:' + record_id, all(pdf_field_matches(fields.get(fid, {}).get('/V'), v, rules_by_id[fid]) for fid, v in wanted.items()))
        schema_ids = {v['field_id']: v for v in field_schema}
        checks.add('mapping_pages:' + record_id, all(fid in schema_ids and item['page'] == schema_ids[fid]['page'] for fid, item in by_id.items()))
        protected = req['protected_blank']
        checks.add('protected_blank:' + record_id, not set(by_id).intersection(protected) and all(pdf_value(fields.get(fid, {}).get('/V')) in ('', 'Off') for fid in protected))
        check_images(output / 'rendered' / record_id, record_id)
        for spec in req.get('visible_changes', []):
            filename = f'page_{spec["page"]}.png'
            with Image.open(template_dir / filename) as a, Image.open(output / 'rendered' / record_id / filename) as b:
                if a.size == b.size:
                    diff = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).convert('L')
                    changed = sum(v > spec.get('pixel_threshold', 12) for v in diff.getdata())
                else:
                    changed = 0
            checks.add(f'visible_change:{record_id}:{spec["page"]}', changed > spec['minimum_changed_pixels'], changed)
    ids = {r['id'] for r in records}
    checks.add('exact_pdf_inventory', {p.stem for p in (output / 'filled').glob('*.pdf')} == ids)
    checks.add('exact_mapping_inventory', {p.stem for p in (output / 'field_values').glob('*.json')} == ids)
    summary = read_json(output / 'batch_summary.json')
    for key, value in expected['summary_values'].items():
        allowed = [value, *manifest.get('summary_aliases', {}).get(key, [])]
        checks.add('summary:' + key, summary.get(key) in allowed, summary.get(key))
    for filename in manifest['required_outputs']:
        if filename == 'business_verification.json':
            continue
        checks.add('deliverable:' + filename, (output / filename).exists())


def verify(manifest_path, workspace, report_path=None, *, deferred_outputs=()):
    manifest = load_manifest(manifest_path)
    expected = read_json(Path(manifest_path).parent / manifest['expected_file'])
    workspace = Path(workspace)
    checks = Checks(manifest)
    try:
        for relative, digest in manifest['input_files'].items():
            p = workspace / relative
            checks.add('input:' + relative, p.is_file() and sha256(p) == digest)
        if checks.data['failures']:
            return checks.finish()
        if manifest['kind'] == 'xlsx':
            if manifest.get('workload_contract') == 'spreadsheet-semantic-v2':
                from .spreadsheet import verify_semantic_xlsx
                verify_semantic_xlsx(manifest, expected, workspace, checks, deferred_outputs)
            else:
                verify_xlsx(manifest, expected, workspace, checks, deferred_outputs)
        else:
            verify_pdf(manifest, expected, workspace, checks)
    except Exception as exc:
        checks.add('verification_exception', False, f'{type(exc).__name__}: {exc}')
    finally:
        report = checks.finish()
        if report_path is not None:
            write_json(report_path, report)
    return report
