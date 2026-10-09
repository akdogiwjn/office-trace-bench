#!/usr/bin/env python3
"""Preserve SBA's native fillable 2024 Box-distributed form for training traces."""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from pypdf import PdfReader
from office_trace_bench.contracts import read_json, sha256, write_json
from office_trace_bench.prompts import render_prompt
sys.path.insert(0, str(ROOT/'vendor/skills/pdf/scripts'))
from extract_form_field_info import get_field_info


def build():
    target = ROOT/'datasets/pdf/sba1919'
    if (target/'manifest.json').exists():
        raise ValueError('SBA dataset exists; refusing to overwrite frozen inputs')
    folder = target/'input'; folder.mkdir(parents=True, exist_ok=True)
    form = folder/'sba1919_2024.pdf'
    shutil.copy2(ROOT/'sources/pdf/sba1919_2024.pdf', form)
    fields = get_field_info(PdfReader(form))
    assert len(fields) == 127
    rules = []
    mapping = {
        'business_name':'applicantname', 'operating_name':'operatingnbusname', 'trade_name':'dba',
        'industry_code':'PrimarIndustry', 'phone':'busphone', 'operation_year':'yearbeginoperations',
        'business_address':'Business Address', 'project_address':'Project Address',
        'contact_name':'Primary Contact Name', 'contact_email':'Primary Contact Email Address',
        'existing_employees':' of existing employees including owners all parttime fulltime and all employees of domestic and foreign Affiliates  do not convert to FTE',
        'retained_jobs':' of FTE jobs savedretained because of the loan including owners',
        'new_jobs':' of new FTE jobs created because of the loan including owners',
        'owner_name':'Owners Legal Name First name Last nameRow1', 'owner_title':'TitleRow1',
        'owner_percentage':'Ownership Row1', 'owner_address':'Home Address Street City State Zip Code No PO BoxRow1',
        'working_capital_amount':'Working Capital amount'}
    for semantic, field_id in mapping.items():
        rules.append(dict(semantic=semantic, field_id=field_id, value_from=semantic))
    by_id = {f['field_id']:f for f in fields}
    for field_id in ['OC','EPC','soleprop','partnership','ccorp','scorp','llc','etother','working capital']:
        schema = by_id[field_id]
        rules.append(dict(semantic='flag_'+field_id, field_id=field_id, value_from='flags.'+field_id,
                          choices={'true':schema['checked_value'], 'false':schema['unchecked_value']}))
    for number in range(1, 14):
        for answer in ('yes','no'):
            field_id = str(number)+answer; schema = by_id[field_id]
            rules.append(dict(semantic='question_'+field_id, field_id=field_id,
                value_from='answers.'+field_id,
                choices={'true':schema['checked_value'], 'false':schema['unchecked_value']}))
    used = {r['field_id'] for r in rules}; assert used <= set(by_id)
    records = []
    for number in range(1, 11):
        name = f'Example Training Business {number:02d} LLC'
        records.append(dict(id=f'applicant_{number:02d}', business_name=name, operating_name=name,
            trade_name=f'Training {number:02d}', industry_code='541511', phone=f'202-555-{100+number:04d}',
            operation_year=str(2010+number), business_address=f'{100+number} Example Lane, Example City, CA 90001',
            project_address=f'{100+number} Example Lane, Example City, CA 90001', contact_name=f'Training Owner {number:02d}',
            contact_email=f'training{number:02d}@example.invalid', existing_employees=str(10+number),
            retained_jobs=str(5+number), new_jobs=str(number), owner_name=f'Training Owner {number:02d}',
            owner_title='Training Manager', owner_percentage='100', owner_address='1 Example Lane, Example City, CA 90001',
            working_capital_amount=str(10000+number*1000),
            flags={field_id:field_id in ('OC','llc','working capital') for field_id in
                   ['OC','EPC','soleprop','partnership','ccorp','scorp','llc','etother','working capital']},
            answers={str(n)+answer:answer=='no' for n in range(1,14) for answer in ('yes','no')}))
    write_json(folder/'synthetic_applicants.json', dict(applicants=records,
        provenance='Fictional unsubmitted performance fixtures; supplied answers do not assert real borrower eligibility.'))
    url = 'https://sba.app.box.com/s/iud0tv5euaw4cdvv3itmbrc2tp2p7etf'
    (folder/'pdf_dataset_sources.md').write_text('# SBA 1919 native fillable benchmark\n\n'
        'Frozen version: SBA Form 1919 04.2024.pdf, seven pages, 127 leaf fields.\n'
        'Public SBA Box source: '+url+'\nOriginal downloaded PDF bytes are preserved.\n'
        'The current 2025 official PDF download returned 403. A downloaded 2025 bank mirror has no AcroForm; neither is used here.\n'
        'This is a version-pinned training benchmark, not a current loan application. Ten fictional businesses are supplied.\n'
        'Read input/dataset_manifest.json for exact semantic field rules and checkbox export states.\n'
        'Copy only supplied business, owner, workforce, working-capital and yes/no answers.\n'
        'Keep every other field blank, including all business/owner TINs, Unique Entity ID, optional demographics,\n'
        'initials, signatures, dates and the certification print-name/title fields. Do not add overlays, certifications or identifiers.\n')
    summary = dict(input_form=form.name, applicant_count=10, filled_pdf_count=10,
        rendered_page_count=77, ssn_and_signatures_left_blank=True, fill_script_invocations=10,
        render_script_invocations=11)
    write_json(target/'expected.json', dict(summary_values=summary,
        oracle_provenance='Unmodified native PDF schema and independently declared synthetic record-to-field mappings.'))
    manifest = dict(schema_version='office-dataset-v1', kind='pdf', dataset_id='sba1919', domain='business_finance_training',
        task='Batch-fill and render version-pinned SBA Form 1919 using fictional business records',
        form=form.name, records='synthetic_applicants.json', records_key='applicants',
        requirements=dict(page_count=7, field_count=127, record_count=10, field_rules=rules,
            protected_blank=sorted(set(by_id)-used), minimum_pdf_bytes=100000, minimum_png_bytes=10000,
            visible_changes=[dict(page=1,minimum_changed_pixels=500,pixel_threshold=12),
                             dict(page=2,minimum_changed_pixels=100,pixel_threshold=12),
                             dict(page=3,minimum_changed_pixels=50,pixel_threshold=12)]),
        summary_contract=summary, summary_aliases={'input_form':['input/'+form.name]},
        required_outputs=['check_fillable_fields.log','form_field_info.json','field_values','filled','rendered',
                          'batch_summary.json','business_verification.json'],
        input_files={str(p.relative_to(target)):sha256(p) for p in sorted(folder.iterdir()) if p.is_file()},
        expected_file='expected.json', expected_sha256=sha256(target/'expected.json'),
        prompt_template='pdf.txt', prompt_template_sha256=sha256(ROOT/'prompts/pdf.txt'),
        prompt_contract=dict(task_subject='the version-pinned SBA Form 1919 2024 fillable PDF',record_noun='applicants',
            record_singular='applicant',first_record_name='applicant_01',record_pattern='applicant_XX',
            form_description='the unmodified seven-page SBA Form 1919 04.2024 native fillable form',
            metadata_file='pdf_dataset_sources.md',
            fill_description='the supplied business and owner names/addresses, business type, workforce counts, working-capital amount and question answers using semantic field rules in input/dataset_manifest.json',
            safe_answer_description='copy the supplied fictional values and checkbox answers verbatim; do not infer borrower eligibility',
            protected_description='all business/owner TINs, Unique Entity ID, demographics, initials, signatures/dates, certification print-name/title and all undeclared fields'),
        runtime_case='SUB-MEM-PDF-SBA1919-01',agent_context=read_json(ROOT/'datasets/pdf/opm/manifest.json')['agent_context'],
        trace_rules=read_json(ROOT/'datasets/pdf/irs_w4/manifest.json')['trace_rules'],
        source_provenance=dict(url=url,file_name='SBA Form 1919 04.2024.pdf',form_sha256=sha256(form),
            public_box_file_id='1584063031191',public_box_sha1='0e7cd9a8dfc50bccb8021b51597e58ce84d324ac',
            public_box_sha1_matches=hashlib_sha1(form)=='0e7cd9a8dfc50bccb8021b51597e58ce84d324ac',
            latest_2025_download_available=False,official_form_modified=False,records='synthetic; not submitted forms'))
    assert manifest['source_provenance']['public_box_sha1_matches']
    write_json(target/'manifest.json',manifest)
    render_prompt(manifest,'/validation/workspace',target/'manifest.json')
    print('sba1919: 7 pages, 127 fields,',len(rules),'fill rules, 10 records, 77 expected PNGs',flush=True)


def hashlib_sha1(path):
    import hashlib
    return hashlib.sha1(path.read_bytes()).hexdigest()


if __name__ == '__main__':
    build()
