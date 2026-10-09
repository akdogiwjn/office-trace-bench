#!/usr/bin/env python3
"""Build frozen synthetic W-4 inputs; keep the downloaded official form unchanged."""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import read_json, sha256, write_json
from office_trace_bench.prompts import render_prompt
from pypdf import PdfReader
sys.path.insert(0, str(ROOT / 'vendor/skills/pdf/scripts'))
from extract_form_field_info import get_field_info


def build_w4():
    target = ROOT / 'datasets/pdf/irs_w4'
    if (target / 'manifest.json').exists():
        raise ValueError('W-4 dataset already exists; refusing to overwrite frozen inputs')
    folder = target / 'input'
    folder.mkdir(parents=True, exist_ok=True)
    form = folder / 'fw4_2026.pdf'
    shutil.copy2(ROOT / 'sources/pdf/fw4_2026.pdf', form)
    fields = get_field_info(PdfReader(form))
    prefix = 'topmostSubform[0].Page1[0].'
    rules = []
    names = [('first_name', 'Step1a[0].f1_01[0]'), ('last_name', 'Step1a[0].f1_02[0]'),
             ('address', 'Step1a[0].f1_03[0]'), ('city_state_zip', 'Step1a[0].f1_04[0]'),
             ('children_credit', 'Step3_ReadOrder[0].f1_06[0]'),
             ('other_dependents_credit', 'Step3_ReadOrder[0].f1_07[0]'),
             ('total_credit', 'f1_08[0]'), ('other_income', 'f1_09[0]'),
             ('deductions', 'f1_10[0]'), ('extra_withholding', 'f1_11[0]')]
    for semantic, suffix in names:
        rules.append(dict(semantic=semantic, field_id=prefix + suffix, value_from=semantic))
    for i, semantic in enumerate(('single', 'married', 'head_of_household')):
        rules.append(dict(semantic='filing_' + semantic, field_id=prefix + f'c1_1[{i}]',
                          value_from='filing_flags.' + semantic,
                          choices={'true': '/' + str(i + 1), 'false': '/Off'}))
    rules.append(dict(semantic='multiple_jobs', field_id=prefix + 'c1_2[0]',
                      value_from='multiple_jobs', choices={'true': '/1', 'false': '/Off'}))
    used = {r['field_id'] for r in rules}
    assert used <= {f['field_id'] for f in fields}
    records = []
    for i in range(1, 11):
        status = ('single', 'married', 'head_of_household')[(i - 1) % 3]
        records.append(dict(id=f'employee_{i:02d}', first_name=f'Training{i:02d}', last_name='Example',
            address=f'{100 + i} Example Lane', city_state_zip='Example City, CA 90001',
            filing_flags={name: name == status for name in ('single', 'married', 'head_of_household')},
            multiple_jobs=i % 2 == 0, children_credit='0', other_dependents_credit='0', total_credit='0',
            other_income=str(i * 100), deductions='0', extra_withholding=str(i * 5)))
    write_json(folder / 'synthetic_employees.json', {'employees': records,
        'provenance': 'Deterministic fictional performance fixtures; amounts are supplied input values, not tax advice or computed eligibility.'})
    metadata = folder / 'pdf_dataset_sources.md'
    metadata.write_text('''# IRS W-4 training fixture

Source: https://www.irs.gov/pub/irs-pdf/fw4.pdf (2026, five pages).
Official form bytes are preserved. Ten fictional employee profiles are deterministic benchmark fixtures.
Names, addresses and amounts do not represent real people or tax recommendations.
Read input/dataset_manifest.json: requirements.field_rules associates business semantics with exact PDF field IDs.
Fill only those 14 declared fields. Select exactly one filing-status checkbox; use each checkbox's declared checked value.
Copy the supplied amounts verbatim. Social Security Number, exemption certification, employer identifiers,
employer dates, signatures and all page-3/page-4 worksheet fields must remain blank.
Signature/date lines are not AcroForm fields; never overlay text onto them or certify this form.
Keep all five original pages. Do not calculate withholding or add personal data.
''')
    summary = dict(input_form=form.name, applicant_count=10, filled_pdf_count=10,
                   rendered_page_count=55, ssn_and_signatures_left_blank=True,
                   fill_script_invocations=10, render_script_invocations=11)
    expected = target / 'expected.json'
    write_json(expected, dict(summary_values=summary,
        oracle_provenance='Official unmodified PDF schema and independently declared synthetic record-to-field rules.'))
    manifest = dict(schema_version='office-dataset-v1', kind='pdf', dataset_id='irs_w4', domain='payroll_training',
        task='Batch-fill and render the official 2026 IRS W-4 using supplied fictional employee fixtures',
        form=form.name, records='synthetic_employees.json', records_key='employees',
        requirements=dict(page_count=5, field_count=len(fields), record_count=10, field_rules=rules,
                          protected_blank=sorted(f['field_id'] for f in fields if f['field_id'] not in used),
                          minimum_pdf_bytes=100000, minimum_png_bytes=10000,
                          visible_changes=[dict(page=1, minimum_changed_pixels=500, pixel_threshold=12)]),
        summary_contract=summary, summary_aliases={'input_form':['input/' + form.name]},
        required_outputs=['check_fillable_fields.log', 'form_field_info.json', 'field_values', 'filled', 'rendered',
                          'batch_summary.json', 'business_verification.json'],
        input_files={str(p.relative_to(target)): sha256(p) for p in sorted(folder.iterdir()) if p.is_file()},
        expected_file='expected.json', expected_sha256=sha256(expected),
        prompt_template='pdf.txt', prompt_template_sha256=sha256(ROOT / 'prompts/pdf.txt'),
        prompt_contract=dict(task_subject='the official 2026 IRS W-4 fillable PDF', record_noun='employees',
            record_singular='employee', first_record_name='employee_01', record_pattern='employee_XX',
            form_description='the unmodified official five-page 2026 IRS W-4 fillable form',
            metadata_file=metadata.name,
            fill_description='the first and last names, address, filing-status and multiple-jobs checkboxes, and the supplied Step 3/4 amounts, using the semantic field rules in input/dataset_manifest.json',
            safe_answer_description='copy supplied synthetic amounts verbatim and select the supplied filing status; do not infer tax eligibility or calculate withholding',
            protected_description='Social Security Number, exemption certification, signatures/dates, employer name/dates/EIN and all worksheet fields on pages 3 and 4'),
        runtime_case='SUB-MEM-PDF-IRSW4-01',
        agent_context=read_json(ROOT / 'datasets/pdf/opm/manifest.json')['agent_context'],
        trace_rules=[dict(pattern=r'\bverify_office\.py\b',operation='verify_business'),
                     dict(pattern=r'check_fillable_fields\.py',operation='check_fillability'),
                     dict(pattern=r'extract_form_field_info\.py',operation='extract_field_schema'),
                     dict(pattern=r'fill_fillable_fields\.py',operation='fill_form'),
                     dict(pattern=r'convert_pdf_to_images\.py',operation='render_pdf')],
        source_provenance=dict(url='https://www.irs.gov/pub/irs-pdf/fw4.pdf', form_sha256=sha256(form),
                               records='synthetic; not submitted forms', official_form_modified=False))
    write_json(target / 'manifest.json', manifest)
    render_prompt(manifest, '/validation/workspace', target / 'manifest.json')
    print(f'prepared irs_w4: 5 pages, {len(fields)} fields, 10 records, 14 fill rules, 55 expected PNGs')


if __name__ == '__main__':
    build_w4()
