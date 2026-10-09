#!/usr/bin/env python3
"""Compare two workbooks using the verifier's preservation logic; report differences."""
import sys, gc
from copy import copy
from itertools import zip_longest
from openpyxl import load_workbook
sys.path.insert(0, '/workspace')
from office_trace_bench.verify import preserved_value
from office_trace_bench.workbooks import logical_value, normalized_formula, chart_sources

src, out = sys.argv[1], sys.argv[2]
fmt = lambda v: str(v).replace('"', '').replace('\\', '').replace(';@', '')
a = load_workbook(src, read_only=True, data_only=False)
b = load_workbook(out, read_only=True, data_only=False)
try:
    for name in a.sheetnames:
        missing, changed, formulas, format_changes = [], [], [], []
        for left, right in zip_longest(a[name].iter_rows(), b[name].iter_rows(), fillvalue=()):
            for old, new in zip_longest(left, right):
                if old is None or old.value is None:
                    continue
                addr = old.coordinate
                if new is None or new.value is None:
                    missing.append(addr)
                elif old.data_type == 'f':
                    if normalized_formula(old.value) != normalized_formula(new.value):
                        formulas.append((addr, old.value, new.value))
                elif not preserved_value(new.value, logical_value(old.value)):
                    changed.append((addr, old.value, new.value))
                if new is not None and fmt(old.number_format) != fmt(new.number_format):
                    format_changes.append((addr, old.number_format, new.number_format))
        print(f'== {name}: missing={len(missing)} changed={len(changed)} formulas={len(formulas)} fmt={len(format_changes)}')
        for x in missing[:5]: print('   MISS', x)
        for x in changed[:5]: print('   CHG', x)
        for x in formulas[:5]: print('   FRM', x)
        for x in format_changes[:5]: print('   FMT', x)
finally:
    a.close(); b.close()

a = load_workbook(src, data_only=False); b = load_workbook(out, data_only=False)
try:
    for sheet in a:
        other = b[sheet.title]
        if {str(r) for r in sheet.merged_cells.ranges} != {str(r) for r in other.merged_cells.ranges}:
            print('MERGED DIFF', sheet.title)
        sources = [chart_sources(c) for c in other._charts]
        wanted = [chart_sources(c) for c in sheet._charts]
        if not (len(sources) >= len(wanted) and all(sources.count(s) >= wanted.count(s) for s in wanted)):
            print('CHART DIFF', sheet.title, wanted, sources)
        diffs = []
        compared = {}
        for cell in sheet._cells.values():
            if not cell.has_style: continue
            new = other[cell.coordinate]
            pair = (cell.style_id, new.style_id)
            if pair not in compared:
                compared[pair] = [attr for attr in ('font','fill','alignment','border','protection') if copy(getattr(cell,attr)) != copy(getattr(new,attr))]
            for attr in compared[pair]:
                if len(diffs) < 20: diffs.append(cell.coordinate+':'+attr)
        print(f'== styles {sheet.title}: {len(diffs)} diffs')
        for d in diffs[:10]: print('   STY', d)
finally:
    a.close(); b.close(); del a,b; gc.collect()
