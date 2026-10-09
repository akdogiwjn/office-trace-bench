#!/usr/bin/env python3
"""Reject deliberately damaged qualification outputs; preserve caches and originals."""
from pathlib import Path
from datetime import datetime
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import dataset_path, read_json, write_json
from office_trace_bench.verify import verify

NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def corrupt_xlsx(path, summary):
    with zipfile.ZipFile(path) as archive:
        files = {name:archive.read(name) for name in archive.namelist()}
    workbook = ET.fromstring(files['xl/workbook.xml'])
    relationships = {r.get('Id'):r.get('Target') for r in ET.fromstring(files['xl/_rels/workbook.xml.rels'])}
    for sheet in workbook.find('m:sheets', NS):
        if sheet.get('name') not in ('Raw_Data', summary):
            continue
        target = relationships[sheet.get('{'+NS['r']+'}id')]
        entry = target.lstrip('/') if target.startswith('/') else 'xl/'+target
        tree = ET.fromstring(files[entry])
        cell = tree.find('.//m:c[@r="'+('H2' if sheet.get('name')=='Raw_Data' else 'B5')+'"]', NS)
        if sheet.get('name') == 'Raw_Data':
            value = cell.find('m:v', NS); value.text = str(int(value.text)+1)
        else:
            cell.find('m:f', NS).text = 'Raw_Data!H2'
        files[entry] = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
    for entry, content in list(files.items()):
        if entry.startswith('xl/charts/chart') and entry.endswith('.xml'):
            tree = ET.fromstring(content)
            for node in tree.iter():
                if node.tag.endswith('}f') and node.text and '!' in node.text:
                    node.text = "'Raw_Data'!"+node.text.split('!',1)[1]
            files[entry] = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for entry, content in files.items(): archive.writestr(entry, content)


def main():
    records = []
    for kind, dataset in [('xlsx','retail'),('xlsx','manufacturing'),('xlsx','hr'),('pdf','irs_w4'),('pdf','sba1919')]:
        source = ROOT/'qualification'/f'{kind}-{dataset}'
        qualification = read_json(source/'qualification.json')
        assert qualification['status'] == 'success', (kind, dataset, qualification)
        path = dataset_path(kind, dataset); manifest = read_json(path)
        first_id = (read_json(source/'workspace/input'/manifest['records'])[manifest['records_key']][0]['id']
                    if kind == 'pdf' else None)
        workspace = ROOT/'qualification/failure-samples'/f'{kind}-{dataset}'/'workspace'
        if workspace.exists() and (workspace.parent/'verification.json').exists():
            report = read_json(workspace.parent/'verification.json')
            required = (['raw_preserved:Raw_Data','formula:B5',
                         *['chart_sources:'+s['id'] for s in manifest['requirements']['charts']]]
                        if kind=='xlsx' else ['mapping:'+first_id,'protected_blank:'+first_id])
            records.append(dict(kind=kind,dataset=dataset,
                expected_rejection=report['status']=='failed' and set(required)<=set(report['failures']),
                required_failures=required,actual_failures=report['failures'],positive_fixture_unchanged=True))
            print(kind,dataset,'retained completed rejection check',flush=True)
            continue
        if workspace.exists():
            workspace = workspace.parent.with_name(workspace.parent.name+'-retry-'+datetime.now().strftime('%Y%m%dT%H%M%S'))/'workspace'
        shutil.copytree(source/'workspace', workspace)
        if kind == 'xlsx':
            corrupt_xlsx(workspace/'output'/manifest['output_workbook'], manifest['requirements']['summary_sheet'])
            required = ['raw_preserved:Raw_Data','formula:B5',
                        *['chart_sources:'+s['id'] for s in manifest['requirements']['charts']]]
        else:
            record = read_json(workspace/'input'/manifest['records'])[manifest['records_key']][0]
            mapping = workspace/'output/field_values'/(record['id']+'.json')
            values = read_json(mapping); values[0]['value'] = 'WRONG-FIXTURE-VALUE'
            schema = read_json(workspace/'output/form_field_info.json')
            protected = next(field['field_id'] for field in schema if field['type']=='text'
                             and field['field_id'] in manifest['requirements']['protected_blank'])
            values.append(dict(field_id=protected,page=1,value='SHOULD-BE-BLANK'))
            write_json(mapping, values)
            required = ['mapping:'+record['id'],'protected_blank:'+record['id']]
        report = verify(path, workspace, workspace.parent/'verification.json')
        accepted = report['status']=='failed' and set(required) <= set(report['failures'])
        records.append(dict(kind=kind,dataset=dataset,expected_rejection=accepted,
                            required_failures=required,actual_failures=report['failures'],
                            positive_fixture_unchanged=True))
        print(kind,dataset,'rejected as expected:',accepted,flush=True)
    result = dict(status='success' if all(r['expected_rejection'] for r in records) else 'failed',
        scope='Independent positive fixtures and deliberate raw/KPI/chart or protected-field/mapping damage; original qualifications and real Agent runs remain untouched.',cases=records)
    write_json(ROOT/'reports/expansion-failure-samples-v1.json', result)
    return 0 if result['status']=='success' else 1


if __name__ == '__main__': raise SystemExit(main())
