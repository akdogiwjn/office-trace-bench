#!/usr/bin/env python3
"""Offline audit against archived primary-source browser extracts and downloads."""
from collections import defaultdict
from datetime import datetime
import hashlib
from pathlib import Path
import re
import sys
import unicodedata
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from openpyxl import load_workbook
from pypdf import PdfReader
from office_trace_bench.contracts import read_json, sha256, write_json

FOLDER = ROOT/'sources/provenance-audit'


def archived_lines(pattern):
    lines = {}
    for path in sorted(FOLDER.glob(pattern)):
        for number, text in re.findall(r'^L(\d+)(?:@P\d+(?:-\d+)?)?: (.*)$',path.read_text(),re.M):
            index = int(number)
            if index in lines and lines[index] != text:
                raise ValueError(f'Conflicting primary extract line {index}: {path}')
            lines[index] = text
    return lines


def title_key(value):
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKC',value).lower())


def number(value):
    if value.startswith('('): return None
    cleaned = value.replace('$','').replace(',','')
    return float(cleaned) if '.' in cleaned else int(cleaned)


def bls_table():
    lines = archived_lines('bls-table1-web-*.txt')
    assert not set(range(180,1332))-set(lines), 'Incomplete primary-source table extract'
    pattern = re.compile(r'^(.*?)\s+([0-9,]+)\s+(\$?[0-9.]+|\(.\))\s+(\$?[0-9,]+|\(.\))\s+(\$?[0-9.]+|\(.\))\s*$')
    lookup = defaultdict(list); pending = []
    for index, text in sorted(lines.items()):
        if not 180 <= index <= 1331: continue
        match = pattern.match(text.strip())
        if match:
            title, employment, hourly_mean, annual_mean, hourly_median = match.groups()
            title = ' '.join([*pending, title]).rstrip('. ')
            # Wrapped names retain the indentation of their first line.
            indent = len(text)-len(text.lstrip()) if not pending else pending_indent
            pending = []
            lookup[title_key(title)].append(dict(title=title,line=index,indent=indent,
                TOT_EMP=number(employment),H_MEAN=number(hourly_mean),A_MEAN=number(annual_mean),H_MEDIAN=number(hourly_median)))
        elif text.strip():
            if not pending: pending_indent = len(text)-len(text.lstrip())
            pending.append(text.strip())
    assert len(lookup)>1000
    return lookup


def audit_hr():
    source = ROOT/'sources/xlsx/national_M2025_dl.xlsx'
    data = source.read_bytes()
    github_tree = read_json(ROOT/'sources/xlsx/oews_candidate_tree.json')
    entry = next(r for r in github_tree['tree'] if r['path']=='data/oesm25nat/national_M2025_dl.xlsx')
    local_blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    book = load_workbook(source,read_only=True,data_only=True)
    iterator = iter(book['national_M2025_dl'].values); headers = next(iterator)
    rows = [dict(zip(headers,v)) for v in iterator]; book.close()
    assert len(rows)==1401
    selected = [r for r in rows if str(r['AREA'])=='99' and str(r['NAICS'])=='000000'
                and str(r['OWN_CODE'])=='1235' and r['O_GROUP']=='detailed'
                and all(isinstance(r[k],(int,float)) and r[k]>0 for k in ['TOT_EMP','A_MEAN','A_MEDIAN'])]
    lookup = bls_table(); missing = []; conflicts = []; checked = defaultdict(int); matches = []
    for row in selected:
        candidates = lookup.get(title_key(row['OCC_TITLE']),[])
        if not candidates:
            missing.append(dict(soc=row['OCC_CODE'],title=row['OCC_TITLE'])); continue
        # Detailed vs aggregate names such as Cashiers are distinguished by the
        # PRIMARY table's hierarchy indentation, never by matching input values.
        candidate = max(candidates,key=lambda r:r['indent'])
        differences = {}
        for field in ['TOT_EMP','A_MEAN','H_MEAN','H_MEDIAN']:
            if candidate[field] is None: continue
            checked[field] += 1
            if row[field] != candidate[field]: differences[field]=dict(local=row[field],official=candidate[field])
        if differences:
            conflicts.append(dict(soc=row['OCC_CODE'],title=row['OCC_TITLE'],differences=differences))
        else:
            matches.append(dict(soc=row['OCC_CODE'],title=row['OCC_TITLE'],official_line=candidate['line']))
    overall = next(r for r in rows if r['OCC_CODE']=='00-0000')
    oracle = lookup[title_key('All occupations')][0]
    source_matches_manifest = sha256(source)==read_json(ROOT/'datasets/xlsx/hr/provenance.json')['sha256']
    assert len(selected)==825 and source_matches_manifest
    return dict(source_path=str(source.relative_to(ROOT)),sha256=sha256(source),bytes=len(data),
        source_matches_frozen_manifest=source_matches_manifest,
        github_blob_sha1=entry['sha'],computed_git_blob_sha1=local_blob,github_blob_matches=entry['sha']==local_blob,
        immutable_blob_url=entry['url'],cached_repository_tree_sha=github_tree['sha'],
        official_table_url='https://www.bls.gov/news.release/ocwage.t01.htm',official_reference_period='May 2025',
        source_rows=1401,selected_detailed_occupations=len(selected),matched_occupations=len(matches),
        checked_field_counts=dict(checked),missing_occupations=missing,conflicting_occupations=conflicts,
        matched_primary_rows=matches,
        headline_matches=all(overall[k]==oracle[k] for k in ['TOT_EMP','A_MEAN','H_MEAN','H_MEDIAN']),
        official_zip_download_http_status=403,official_byte_identity_verified=False,
        annual_median_directly_checked=False,
        reliability_assessment='Primary BLS values corroborate all selected occupations; third-party workbook provenance remains short of official byte identity and direct annual-median verification.',
        scope='GitHub blob identity plus direct primary BLS employment/mean wage/hourly median values. Official ZIP bytes and annual median values are not fully independently verified.',
        content_check_passed=not missing and not conflicts and len(matches)==825 and entry['sha']==local_blob)


def semantic_text(value):
    # Ignore layout, checkbox glyphs, punctuation and line-wrapping hyphens.
    # This comparison establishes word/digit sequence only, not PDF rendering,
    # annotations, field geometry, layout, signatures or byte equivalence.
    return ''.join(c.lower() for c in unicodedata.normalize('NFKC',value) if c.isalnum())


def audit_sba():
    original = ROOT/'sources/pdf/sba1919_2024.pdf'
    redownload = FOLDER/'sba1919-box-redownload.pdf'
    pdf = PdfReader(original)
    lines = archived_lines('sba-official-pdf-web-ref*.txt')
    assert set(range(418))<=set(lines),'Incomplete primary-source PDF text'
    official = '\n'.join(lines[i] for i in range(1,418))
    local = '\n'.join(page.extract_text() for page in pdf.pages)
    official_normalized = semantic_text(official); local_normalized = semantic_text(local)
    first_difference = next((i for i,(a,b) in enumerate(zip(official_normalized,local_normalized)) if a!=b),None)
    context = None
    if first_difference is not None:
        i = first_difference
        context = dict(index=i,official=official_normalized[max(0,i-35):i+70],local=local_normalized[max(0,i-35):i+70])
    return dict(source_path=str(original.relative_to(ROOT)),sha256=sha256(original),bytes=original.stat().st_size,
        source_matches_frozen_manifest=sha256(original)==read_json(ROOT/'datasets/pdf/sba1919/manifest.json')['source_provenance']['form_sha256'],
        redownload_sha256=sha256(redownload),redownload_byte_identical=original.read_bytes()==redownload.read_bytes(),
        public_box_url='https://sba.app.box.com/s/iud0tv5euaw4cdvv3itmbrc2tp2p7etf',
        box_declared_sha1='0e7cd9a8dfc50bccb8021b51597e58ce84d324ac',
        box_sha1_matches=hashlib.sha1(original.read_bytes()).hexdigest()=='0e7cd9a8dfc50bccb8021b51597e58ce84d324ac',
        official_form_url='https://legacy.sba.gov/sites/default/files/2024-07/Form1919%20%281%29.pdf',
        official_document_page='https://legacy.sba.gov/document/sba-form-1919-borrower-information-form',
        official_notice_url='https://legacy.sba.gov/document/information-notice-5000-857390-sba-form-1919-update-criminal-justice-reviews-final-rule',
        pages=len(pdf.pages),acroform_fields=len(pdf.get_fields() or {}),
        printed_version='SBA Form 1919 (04/2024)',
        metadata={k:str(pdf.metadata.get(k,'')) for k in ['/Author','/CreationDate','/ModDate','/Title']},
        official_normalized_text_sha256=hashlib.sha256(official_normalized.encode()).hexdigest(),
        local_normalized_text_sha256=hashlib.sha256(local_normalized.encode()).hexdigest(),
        official_normalized_text_chars=len(official_normalized),local_normalized_text_chars=len(local_normalized),
        all_seven_pages_normalized_text_identical=official_normalized==local_normalized,
        first_normalized_text_difference=context,
        direct_official_gov_backlink_to_exact_box_share_found=False,
        official_pdf_byte_identity_verified=False,
        reliability_assessment='Strong primary-content corroboration and repeatable Box bytes; exact SBA.gov PDF bytes and direct official backlink to this Box share are not verified.',
        scope='Re-download verifies Box file bytes. Complete normalized text compared against seven-page SBA.gov 2024 PDF; this does not verify official PDF bytes or prove Box account ownership.')


def main():
    hr = audit_hr(); sba = audit_sba()
    report = dict(schema_version='office-source-audit-v1',
        audited_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),hr=hr,sba1919=sba,
        status='content_checks_passed_with_provenance_limits' if hr['content_check_passed'] and sba['all_seven_pages_normalized_text_identical'] and sba['redownload_byte_identical'] else 'content_check_failed',
        raw_runs_and_frozen_dataset_inputs_modified=False,
        source_extracts={str(p.relative_to(ROOT)):sha256(p) for p in sorted(FOLDER.glob('*')) if p.is_file()})
    write_json(ROOT/'reports/hr-sba-source-reliability-v2.json',report)
    print('HR',hr['matched_occupations'],'/',hr['selected_detailed_occupations'],'missing',len(hr['missing_occupations']),
          'conflicts',len(hr['conflicting_occupations']),'field checks',hr['checked_field_counts'])
    print('SBA redownload identical:',sba['redownload_byte_identical'],'official normalized text identical:',
          sba['all_seven_pages_normalized_text_identical'],'difference',sba['first_normalized_text_difference'])
    return 0 if report['status']=='content_checks_passed_with_provenance_limits' else 1


if __name__=='__main__':raise SystemExit(main())
