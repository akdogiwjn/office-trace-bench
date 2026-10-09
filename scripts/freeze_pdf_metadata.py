#!/usr/bin/env python3
"""Freeze form revisions and fictional-record schemas without changing input bytes."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import office
from office_trace_bench.contracts import read_json,sha256,write_json
from office_trace_bench import records
from pypdf import PdfReader

def schema(value):
    if isinstance(value,dict):return dict(type='object',required=sorted(value),additionalProperties=False,properties={k:schema(v) for k,v in value.items()})
    if isinstance(value,list):return dict(type='array',items=schema(value[0]) if value else {},minItems=len(value),maxItems=len(value))
    return dict(type='boolean' if isinstance(value,bool) else 'integer' if isinstance(value,int) else 'number' if isinstance(value,float) else 'string')

def main():
    revisions={'opm':'OF-306, August 2023','irs_w4':'Form W-4, 2026','sba1919':'SBA Form 1919, 04/2024; expires 2027-06-30'}
    for dataset in revisions:
        manifest=read_json(ROOT/'datasets/pdf'/dataset/'manifest.json')
        if manifest.get('provenance_sha256') or manifest.get('records_contract_sha256'):
            raise ValueError('PDF suite is already frozen; publish a new revision instead of relabelling or replacing inputs')
    urls={'opm':'https://www.opm.gov/forms/pdf_fill/of306.pdf','irs_w4':'https://www.irs.gov/pub/irs-pdf/fw4.pdf','sba1919':'https://sba.app.box.com/s/iud0tv5euaw4cdvv3itmbrc2tp2p7etf'}
    for dataset in revisions:
        root=ROOT/'datasets/pdf'/dataset;m=read_json(root/'manifest.json');form=root/'input'/m['form'];path=root/'input'/m['records'];data=read_json(path)
        if dataset!='opm':assert data==getattr(records,'w4' if dataset=='irs_w4' else 'sba')()
        contract=dict(schema_version='office-fictional-record-contract-v1',records_file=m['records'],records_sha256=sha256(path),records_key=m['records_key'],record_count=len(data[m['records_key']]),
            schema=schema(data),synthetic=True,contains_real_sensitive_data=False,random_seed=None,
            generation_method='Hand-authored frozen fictional fixture; reproduce byte-for-byte from legacy/runner/cases/pdf/input/synthetic_applicants.json' if dataset=='opm' else 'Deterministic ordinal loop, no random inputs',
            generator='legacy/runner/cases/pdf/input/synthetic_applicants.json' if dataset=='opm' else 'office_trace_bench/records.py',
            generator_sha256=sha256(ROOT/('legacy/runner/cases/pdf/input/synthetic_applicants.json' if dataset=='opm' else 'office_trace_bench/records.py')),
            generator_function=None if dataset=='opm' else ('w4' if dataset=='irs_w4' else 'sba'),
            privacy='All fixture identities are invented; reserved 555 phone numbers/example.invalid emails where present; SSNs/TINs/signatures excluded. Public birthplaces/addresses can coincide with real places without representing real persons.',
            update_policy='Input byte changes require a new suite revision and new canonical trace; never replace silently.')
        write_json(root/'records_contract.json',contract)
        provenance=dict(schema_version='office-input-provenance-v2',filename=m['form'],revision=revisions[dataset],sha256=sha256(form),
            page_count=len(PdfReader(form).pages),field_count=m['requirements']['field_count'],official_source=urls[dataset],
            actual_download_source=urls[dataset],download_date='2026-10-09' if dataset!='opm' else 'Historical import; precise acquisition date not recorded',
            official_byte_identity_verified=dataset=='irs_w4',records_contract_sha256=sha256(root/'records_contract.json'))
        if dataset=='sba1919':
            provenance.update(official_source='https://legacy.sba.gov/sites/default/files/2024-07/Form1919%20%281%29.pdf',
                actual_download_source=urls[dataset],reason_for_revision='Native fillable 04/2024 form enables frozen Skill batch filling; not the latest form.',
                current_2025_exclusion='Official 2025 download failed (403). Only the downloaded bank mirror was observed to have no AcroForm; this does not prove the inaccessible official 2025 original is non-fillable.',
                corroboration='Fresh Box download byte-identical; all seven pages normalized letters/digits match official 2024 PDF web extract. No exact share backlink or official byte identity claimed.',
                evidence='reports/hr-sba-source-reliability-v1.json')
            sources=root/'input/pdf_dataset_sources.md';text=sources.read_text().replace('Public SBA Box source:','SBA-named public Box share (official backlink unverified):');sources.write_text(text)
            m['input_files']['input/pdf_dataset_sources.md']=sha256(sources)
            m['source_provenance']=dict(actual_download_source=urls[dataset],revision=revisions[dataset],official_byte_identity_verified=False,evidence='provenance.json')
        m['revision']=revisions[dataset];m['records_contract_sha256']=sha256(root/'records_contract.json');m['prompt_template_sha256']=sha256(ROOT/'prompts/pdf.txt')
        write_json(root/'provenance.json',provenance);m['provenance_sha256']=sha256(root/'provenance.json');write_json(root/'manifest.json',m)
    print('PDF revisions, records JSON hashes and deterministic generators frozen; form/record bytes unchanged.')

if __name__=='__main__':main()
