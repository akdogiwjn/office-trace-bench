#!/usr/bin/env python3
"""Explicit, one-time native-input suite revision authorized by the repository owner."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import read_json, write_json, sha256, load_manifest
from office_trace_bench.complexity import inspect_workbook
from scripts.native_xlsx_oracle import calculate

SOURCES = {
    'retail': ('mrtssales92-present.xlsx', '6b2cb26926ba0a438f2b45c4b38b218045273f63a674c11b1cbb7bf1cf9a7956',
               'https://www.census.gov/retail/mrts/www/mrtssales92-present.xlsx'),
    'manufacturing': ('text.xlsx', '3a675ad4067e5463600ba46237c1f38123a4b83519035d1450b511496c130e43',
                      'https://www.census.gov/manufacturing/m3/bench/text.xlsx'),
    'hr': ('national_M2025_dl.xlsx', '852250997ceff9b721ff68f63e877d818f9c1ec8b1b69dd367958faedd5282b2',
           'https://www.bls.gov/oes/special-requests/oesm25nat.zip')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir', type=Path, required=True)
    p.add_argument('--official-redownload-dir', type=Path, required=True)
    p.add_argument('--download-date', required=True)
    args = p.parse_args()
    archive = ROOT/'legacy/suite-v2-transcription'
    if archive.exists():
        raise ValueError('native suite revision is already frozen; refusing to overwrite inputs')
    manifests = {name: load_manifest(ROOT/'datasets/xlsx'/name/'manifest.json') for name in SOURCES}
    for name, (filename, digest, _) in SOURCES.items():
        if sha256(args.input_dir/filename) != digest:
            raise ValueError('unexpected user-provided bytes: ' + name)
        if name != 'hr':
            if sha256(args.official_redownload_dir/filename) != digest:
                raise ValueError('official redownload differs: ' + name)
            if read_json(ROOT/'datasets/xlsx'/name/'provenance.json')['input_class'] != 'official_table_transcription':
                raise ValueError('expected prior transcription input: ' + name)
        elif manifests[name]['input_files']['input/'+filename] != digest:
            raise ValueError('HR changed; this migration cannot retain its existing trace')
    oracles = {name: calculate(name, args.input_dir/SOURCES[name][0]) for name in ('retail', 'manufacturing')}
    archive.mkdir(parents=True)
    for name in ('retail', 'manufacturing'):
        shutil.copytree(ROOT/'datasets/xlsx'/name, archive/'datasets/xlsx'/name)
    for filename in ['artifacts/suite.json', 'docs/status.json', 'reports/current-agent-regression-v2.json',
                     'reports/self-contained-tests-v2.json', 'reports/canonical-output-regression-v2.json',
                     'reports/scenario-retail-v2.json', 'reports/scenario-manufacturing-v2.json']:
        dest = archive/filename; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT/filename, dest)
    now = datetime.now(timezone.utc).isoformat()
    evidence = dict(schema_version='office-official-download-evidence-v1', checked_at=now,
        acquisition_date=args.download_date, acquisition_method='Owner downloaded official files and supplied URLs; Agent independently redownloaded Census files with curl -fL.',
        datasets={})
    for name in ('retail', 'manufacturing'):
        root = ROOT/'datasets/xlsx'/name; m = manifests[name]; filename, digest, url = SOURCES[name]
        old_workbook = root/'input'/m['workbook']
        shutil.copyfile(args.input_dir/filename, root/'input'/filename)
        old_workbook.unlink()  # archived above; excluded from the new Agent input snapshot
        m.update(workbook=filename, input_files={'input/'+filename:digest}, suite_revision='native-xlsx-v3')
        if name == 'retail':
            m['task'] = 'Analyze the frozen native Census MRTS historical workbook, focusing on July 2026 adjusted sales'
            meanings = [
                'Published total retail and food services seasonally adjusted sales for July 2026. Use the total, not a sum of overlapping categories.',
                'Relative change in adjusted total sales from June to July 2026; compute from sales levels.',
                'Relative change in adjusted total sales from July 2025 to July 2026; compute from sales levels.']
            m['requirements']['charts'][0]['meaning'] = 'May, June and July 2026 adjusted total retail and food services sales in chronological order'
            release = 'MRTS historical estimates 1992–2026; 2026 monthly data through July (preliminary). Exact release date not embedded in supplied file.'
            period = 'July 2026; historical annual worksheets 1992–2026'
        else:
            m['task'] = 'Analyze the frozen native Census M3 benchmark workbook, focusing on March 2025 shipments'
            meanings = [
                'All manufacturing industries seasonally adjusted March 2025 shipments. Do not sum overlapping industry hierarchy rows.',
                'Relative change in all-manufacturing adjusted shipments February to March 2025 computed from levels.',
                'Durable-goods March 2025 adjusted shipments as a fraction of all manufacturing shipments.',
                'Published nondurable-goods March 2025 seasonally adjusted shipments.']
            m['requirements']['charts'][0]['meaning'] = 'Compare March 2025 seasonally adjusted durable versus nondurable shipments, excluding subordinate rows'
            m['requirements']['charts'][1]['meaning'] = 'All-manufacturing seasonally adjusted shipments January, February and March 2025 in chronological order'
            release = 'M3 Benchmark Report, May 16, 2025 (source note inside workbook)'
            period = 'January–March 2025'
        for metric, meaning in zip(m['requirements']['metrics'], meanings): metric['meaning'] = meaning
        write_json(root/'expected.json', oracles[name]); m['expected_sha256'] = sha256(root/'expected.json')
        write_json(root/'complexity.json', inspect_workbook(root/'input'/filename))
        evidence['datasets'][name] = dict(official_url=url, filename=filename, local_sha256=digest,
            official_redownload_sha256=sha256(args.official_redownload_dir/filename), byte_identity_verified=True,
            release=release, period=period, download_date=args.download_date, conversion='None; unmodified full native workbook')
        provenance = dict(schema_version='office-input-provenance-v3', dataset_id=name, filename=filename,
            sha256=digest, frozen_at=now, task=m['task'], input_class='official_native_spreadsheet', native_xlsx=True,
            official_byte_identity_verified=True, official_url=url, actual_download_source=url,
            source_filename=filename, release=release, period=period, download_date=args.download_date,
            acquisition_method='Owner-supplied official download; independent official redownload is byte-identical',
            synthetic_expansion=False, conversion='None. All original worksheet names, data, styles and other content retained unchanged.',
            replaces=dict(workbook=read_json(archive/'datasets/xlsx'/name/'manifest.json')['workbook'],
                          manifest_sha256=sha256(archive/'datasets/xlsx'/name/'manifest.json')),
            limitations=['The URL may change over time; the frozen SHA256 defines the input version.'],
            verification_evidence='reports/official-native-input-provenance-v3.json')
        write_json(root/'provenance.json', provenance)
        m['analysis_metadata'] = {n:sha256(root/n) for n in ('provenance.json','complexity.json')}
        write_json(root/'manifest.json', m); load_manifest(root/'manifest.json')
    filename, digest, url = SOURCES['hr']
    evidence['datasets']['hr'] = dict(official_url=url, archive_member=filename, local_sha256=digest,
        repository_input_sha256=sha256(ROOT/'datasets/xlsx/hr/input'/filename), byte_identity_verified=True,
        verification_method='Local byte-for-byte and SHA256 equality against owner-supplied file reported downloaded/extracted from the official ZIP.',
        official_download_attested_by='repository owner', independent_official_redownload=False,
        independent_retry_result='HTTP 403', download_date=args.download_date,
        limitation='Official ZIP bytes and extraction were not independently observed by the Agent; no ZIP hash is available.')
    write_json(ROOT/'reports/official-native-input-provenance-v3.json', evidence)
    hr_entry = next(e for e in read_json(ROOT/'artifacts/suite.json')['datasets'] if e['dataset_id']=='hr')
    write_json(ROOT/'datasets/xlsx/hr/provenance-supplement.json', dict(
        schema_version='office-input-provenance-supplement-v1', dataset_id='hr', input_sha256=digest,
        original_provenance_sha256=sha256(ROOT/'datasets/xlsx/hr/provenance.json'),
        manifest_sha256=sha256(ROOT/'datasets/xlsx/hr/manifest.json'), canonical_sha256=hr_entry['canonical_sha256'],
        evidence_path='reports/official-native-input-provenance-v3.json',
        evidence_sha256=sha256(ROOT/'reports/official-native-input-provenance-v3.json'),
        official_download=SOURCES['hr'][2], download_date=args.download_date,
        decision='Preserve the existing manifest, original cache provenance and canonical trace; owner-supplied official bytes are identical.',
        independent_official_redownload=False))
    write_json(archive/'README.json', dict(status='superseded_by_native_xlsx_v3', archived_at=now,
        reason='Owner authorized adoption of complete native Census workbooks; old canonical packs remain immutable in artifacts/canonical.'))
    print('Adopted native Retail/Manufacturing; HR manifest and trace unchanged. New real runs required before publishing the current suite index.')


if __name__ == '__main__': main()
