"""Input-only OOXML complexity; never injected into the Agent prompt."""
import posixpath
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .contracts import sha256

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def sheet_parts(archive):
    rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
    return {s.attrib['name']: (rels[s.attrib[RID]].lstrip('/') if rels[s.attrib[RID]].startswith('/')
            else posixpath.normpath(posixpath.join('xl', rels[s.attrib[RID]])))
            for s in ET.fromstring(archive.read('xl/workbook.xml')).find('s:sheets', NS)}


def inspect_workbook(path):
    path = Path(path)
    with ZipFile(path) as archive:
        sheets = []
        for name, part in sheet_parts(archive).items():
            stats = dict(name=name, used_cell_count=0, populated_cell_count=0, row_count=0,
                         column_count=0, formula_count=0, cross_sheet_formula_count=0,
                         styled_cell_count=0, merged_ranges=[], chart_count=0)
            with archive.open(part) as stream:
                for _, node in ET.iterparse(stream, events=('end',)):
                    tag = node.tag.rsplit('}', 1)[-1]
                    if tag == 'c':
                        stats['used_cell_count'] += 1
                        address = node.attrib['r']
                        letters, row = re.fullmatch(r'([A-Z]+)(\d+)', address).groups()
                        col = 0
                        for char in letters:
                            col = col * 26 + ord(char) - 64
                        stats['row_count'] = max(stats['row_count'], int(row))
                        stats['column_count'] = max(stats['column_count'], col)
                        if len(node):
                            stats['populated_cell_count'] += int(any(c.tag.rsplit('}', 1)[-1] in ('f', 'v', 'is') for c in node))
                        formula = node.find('s:f', NS)
                        if formula is not None:
                            stats['formula_count'] += 1
                            stats['cross_sheet_formula_count'] += int('!' in (formula.text or ''))
                        stats['styled_cell_count'] += int(node.attrib.get('s', '0') != '0')
                        node.clear()
                    elif tag == 'mergeCell':
                        stats['merged_ranges'].append(node.attrib['ref'])
                        node.clear()
                    elif tag == 'row':
                        node.clear()
            rel_path = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
            if rel_path in archive.namelist():
                for rel in ET.fromstring(archive.read(rel_path)):
                    if rel.attrib['Type'].endswith('/drawing'):
                        drawing = posixpath.normpath(posixpath.join(posixpath.dirname(part), rel.attrib['Target']))
                        if rel.attrib['Target'].startswith('/'):
                            drawing = rel.attrib['Target'].lstrip('/')
                        if drawing in archive.namelist():
                            stats['chart_count'] += sum(n.tag.endswith('}chart') for n in ET.fromstring(archive.read(drawing)).iter())
            stats['merged_range_count'] = len(stats['merged_ranges'])
            sheets.append(stats)
        styles = ET.fromstring(archive.read('xl/styles.xml')) if 'xl/styles.xml' in archive.namelist() else None
        return dict(schema_version='office-workbook-complexity-v1', input_sha256=sha256(path),
                    file_size_bytes=path.stat().st_size, compressed_xlsx_size_bytes=path.stat().st_size,
                    uncompressed_package_bytes=sum(i.file_size for i in archive.infolist()),
                    sheet_count=len(sheets), sheets=sheets,
                    used_cell_count=sum(s['used_cell_count'] for s in sheets),
                    populated_cell_count=sum(s['populated_cell_count'] for s in sheets),
                    formula_count=sum(s['formula_count'] for s in sheets),
                    chart_count=sum(s['chart_count'] for s in sheets),
                    style_count=len(styles.find('s:cellXfs', NS)) if styles is not None else 0,
                    merged_range_count=sum(s['merged_range_count'] for s in sheets),
                    has_shared_strings='xl/sharedStrings.xml' in archive.namelist(),
                    cross_sheet_formula_count=sum(s['cross_sheet_formula_count'] for s in sheets),
                    counting_method='OOXML c elements; populated excludes style-only cells; row/column counts are maximum serialized cell coordinates, per sheet')
