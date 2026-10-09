#!/usr/bin/env python3
"""Inject LibreOffice-recalculated formula caches into the pristine openpyxl build.

The recalculated workbook is used only as a source of cached results; the original
worksheets in the output stay exactly as openpyxl serialized them from the source
workbook (which preserves source content).  We patch only <v/> placeholders in the
added sheet's XML, so nothing is re-saved through openpyxl (caches kept intact).
"""
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'build' / 'enhanced_base.xlsx'
RECALC = ROOT / 'build' / 'recalc_work.xlsx'
OUT = ROOT / 'output' / 'manufacturing_enhanced.xlsx'


def sheet_part(book_zip, sheet_name):
    wbxml = book_zip.read('xl/workbook.xml').decode('utf-8')
    rels = book_zip.read('xl/_rels/workbook.xml.rels').decode('utf-8')
    m = re.search(r'<sheet[^>]*name="%s"[^>]*r:id="(rId\d+)"' % re.escape(sheet_name), wbxml)
    rid = m.group(1)
    tag = re.search(r'<Relationship[^>]*\bId="%s"[^>]*>' % rid, rels).group(0)
    target = re.search(r'Target="([^"]+)"', tag).group(1).lstrip('/')
    return target if target.startswith('xl/') else 'xl/' + target


def cached_values(path, sheet):
    wb = load_workbook(path, data_only=True)
    try:
        ws = wb[sheet]
        return {c.coordinate: c.value for row in ws.iter_rows() for c in row
                if c.value is not None and c.data_type != 'f'}
    finally:
        wb.close()


def inject(sheet_xml, values, cells):
    def repl(match):
        whole, addr = match.group(0), match.group(1)
        if addr not in cells or '<f' not in whole:
            return whole
        val = values.get(addr)
        if val is None:
            return whole
        if isinstance(val, float) and val == int(val):
            val = int(val)
        return whole.replace('<v />', f'<v>{val}</v>').replace('<v/>', f'<v>{val}</v>')
    return re.sub(r'<c r="([A-Z]+\d+)"[^>]*>.*?</c>', repl, sheet_xml, flags=re.DOTALL)


def main():
    cells = ['B6', 'B7', 'B8', 'B9', 'B18', 'B22', 'B23', 'B26', 'B27', 'B28']
    values = cached_values(RECALC, 'Overview')
    with zipfile.ZipFile(BASE) as zb:
        part = sheet_part(zb, 'Overview')
        xml = zb.read(part).decode('utf-8')
        patched = inject(xml, values, set(cells))
        names = zb.namelist()
        blobs = {n: zb.read(n) for n in names}
    blobs[part] = patched.encode('utf-8')
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as zw:
        for n in names:
            zw.writestr(n, blobs[n])
    print(json.dumps({'output': str(OUT), 'part': part,
                      'patched': {c: values.get(c) for c in cells}}))


if __name__ == '__main__':
    main()
