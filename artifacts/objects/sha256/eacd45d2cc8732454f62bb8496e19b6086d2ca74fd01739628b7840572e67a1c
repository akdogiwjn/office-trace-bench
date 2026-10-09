"""Logical fingerprints survive ZIP metadata and insignificant float changes."""
import datetime
import hashlib
import json
import math
import re


def logical_value(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('non-finite spreadsheet value')
        return ['number', format(value, '.12g')]
    if isinstance(value, int) and not isinstance(value, bool):
        return ['number', str(value)]
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return ['datetime', value.isoformat()]
    return [type(value).__name__, value]


def sheet_digest(sheet):
    digest = hashlib.sha256()
    for row in sheet.iter_rows(values_only=True):
        digest.update(json.dumps([logical_value(v) for v in row], ensure_ascii=False,
                                 separators=(',', ':')).encode())
        digest.update(b'\n')
    return {'rows': sheet.max_row, 'columns': sheet.max_column, 'sha256': digest.hexdigest()}


def normalized_formula(value):
    return re.sub(r'\s+', '', str(value)).replace('$', '').replace("'", '').replace('_xlfn.', '').upper()


def chart_sources(chart):
    refs = []
    for series in chart.series:
        for attribute in ('val', 'cat', 'xVal', 'yVal', 'tx'):
            source = getattr(series, attribute, None)
            if source is None:
                continue
            for ref_type in ('numRef', 'strRef'):
                ref = getattr(source, ref_type, None)
                if ref is not None and getattr(ref, 'f', None):
                    refs.append(normalized_formula(ref.f))
    return sorted(set(refs))


def workbook_snapshot(workbook, raw_sheets):
    return {
        'sheet_order': workbook.sheetnames,
        'raw_sheets': {name: sheet_digest(workbook[name]) for name in raw_sheets},
        'formulas': {sheet.title: {cell.coordinate: normalized_formula(cell.value)
                    for row in sheet.iter_rows() for cell in row if cell.data_type == 'f'}
                    for sheet in workbook.worksheets if sheet.title not in raw_sheets},
        'values': {sheet.title: {cell.coordinate: logical_value(cell.value)
                   for row in sheet.iter_rows() for cell in row
                   if cell.value is not None and cell.data_type != 'f'}
                   for sheet in workbook.worksheets if sheet.title not in raw_sheets},
        'charts': {sheet.title: [chart_sources(chart) for chart in sheet._charts]
                   for sheet in workbook.worksheets},
    }
