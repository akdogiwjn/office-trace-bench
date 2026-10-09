"""Assemble the final deliverable: inject recalculated caches into the clean
openpyxl build and restore source empty-string cells that openpyxl drops.

Source content stays semantically identical; only added-sheet formula caches
and the dropped empty strings are patched, at the raw XML level.

REVISION v1 (initial). Known defect: the workbook relationship parser assumed
Id precedes Target, which raised KeyError('rId1') on openpyxl-serialized rels
(Target precedes Id). Superseded by v2.
"""
import re
import shutil
import zipfile
from pathlib import Path
import openpyxl

ROOT = Path('/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-HR')
PRE = ROOT / 'helpers/pre_recalc.xlsx'     # clean openpyxl build (formulas, no caches)
REC = ROOT / 'helpers/rec_recalc.xlsx'     # LibreOffice-recalculated (has caches)
FINAL = ROOT / 'output/hr_enhanced.xlsx'
SRC = ROOT / 'input/national_M2025_dl.xlsx'
ORIGINALS = {'national_M2025_dl', 'Field Descriptions', 'UpdateTime', 'Filler'}

# --- gather caches for added-sheet formula cells -----------------------------
wb = openpyxl.load_workbook(PRE, data_only=False)
rw = openpyxl.load_workbook(REC, data_only=True)
added = [s for s in wb.sheetnames if s not in ORIGINALS]
caches = {}   # sheet -> {coord: value}
for name in added:
    m = {}
    for row in wb[name].iter_rows():
        for cell in row:
            if cell.data_type == 'f':
                m[cell.coordinate] = rw[name][cell.coordinate].value
    caches[name] = m

def num(v):
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return format(v, '.15g')
    return str(v)

# --- dropped empty source cells ---------------------------------------------
orphans = {}
for name in ORIGINALS:
    miss = []
    s = wb[name]
    for row in s.iter_rows():
        for cell in row:
            pass
# compute from source vs PRE directly
swb = openpyxl.load_workbook(SRC)
for name in ORIGINALS:
    miss = []
    for row in swb[name].iter_rows():
        for old in row:
            if old.value is None:
                continue
            if wb[name][old.coordinate].value is None:
                miss.append(old.coordinate)
    if miss:
        orphans[name] = miss

# --- map sheet names to parts ------------------------------------------------
zin = zipfile.ZipFile(PRE)
parts = {n: zin.read(n) for n in zin.namelist()}
wbxml = parts['xl/workbook.xml'].decode('utf-8')
relxml = parts['xl/_rels/workbook.xml.rels'].decode('utf-8')
rels = dict(re.findall(r'<Relationship[^>]*Id="([^"]+)"[^>]*Target="([^"]+)"', relxml))
sheets = re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wbxml)
name2part = {}
for nm, rid in sheets:
    tgt = rels[rid].lstrip('/')
    if not tgt.startswith('xl/'):
        tgt = 'xl/' + tgt
    name2part[nm] = tgt
print('sheet parts', name2part)

patched = 0
for name, m in caches.items():
    part = name2part[name]
    xml = parts[part].decode('utf-8')
    for coord, value in m.items():
        if value is None:
            continue
        val = num(value)
        pat = re.compile(r'(<c r="' + re.escape(coord) + r'"[^>]*>\s*<f>.*?</f>)\s*<v\s*/>', re.S)
        new_xml, n = pat.subn(lambda mo: mo.group(1) + '<v>' + val + '</v>', xml, count=1)
        if n == 0:
            # no empty <v/> present: append <v> after the formula
            pat2 = re.compile(r'(<c r="' + re.escape(coord) + r'"[^>]*>\s*<f>.*?</f>)', re.S)
            new_xml, n = pat2.subn(lambda mo: mo.group(1) + '<v>' + val + '</v>', xml, count=1)
        if n == 0:
            print('WARN no formula cell for', name, coord)
        xml = new_xml
        patched += 1
    parts[part] = xml.encode('utf-8')

restored = 0
for name, coords in orphans.items():
    part = name2part[name]
    xml = parts[part].decode('utf-8')
    for coord in coords:
        pat = re.compile(r'<c r="' + re.escape(coord) + r'"([^>]*?)/>')
        xml, n = pat.subn(lambda mo: '<c r="' + coord + '"' + mo.group(1) + '><is><t></t></is></c>', xml, count=1)
        restored += n
    parts[part] = xml.encode('utf-8')

with zipfile.ZipFile(FINAL, 'w', zipfile.ZIP_DEFLATED) as zout:
    for n in zin.namelist():
        zout.writestr(n, parts[n])
zin.close()
print('patched formula caches:', patched, '| restored empty cells:', restored)
print('wrote', FINAL, FINAL.stat().st_size)
