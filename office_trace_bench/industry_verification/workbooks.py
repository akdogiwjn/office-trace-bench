"""Logical fingerprints for the replay-private semantic verifier.

`normalized_formula` only applies explicitly supported serialization
equivalences. It tokenizes the formula into:
  - double-quoted string literals (preserved verbatim, including whitespace and
    case),
  - single-quoted sheet/workbook identifiers (content preserved after unescaping
    doubled single quotes; the quoting itself is serialization),
  - plain tokens (whitespace is collapsed only when adjacent to structural
    characters, `$` and `_xlfn.` removed, case folded).

Whitespace between two identifiers is Excel's reference-intersection operator
and is preserved, so distinct references such as `'A B'!A1` and `AB!A1` are
never merged.
"""
import datetime
import hashlib
import json
import math
import re

_LITERAL_OR_IDENT = re.compile(r'"(?:[^"]|"")*"|\'(?:[^\']|\'\')*\'')
_STRUCTURAL = set('()+-*/^&=<>%,:;!~')


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


def _collapse_whitespace(text):
    """Remove whitespace only when it is adjacent to structural characters or
    a token edge; keep a single space between two identifiers (Excel's
    reference-intersection operator)."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            before = text[i - 1] if i > 0 else None
            after = text[j] if j < n else None
            if before is None or after is None or before in _STRUCTURAL or after in _STRUCTURAL:
                i = j
                continue
            out.append(' ')
            i = j
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _clean_formula_tokens(text):
    text = _collapse_whitespace(text)
    return text.replace('$', '').replace('_xlfn.', '').upper()


def normalized_formula(value):
    text = str(value)
    out = []
    pos = 0
    for match in _LITERAL_OR_IDENT.finditer(text):
        out.append(_clean_formula_tokens(text[pos:match.start()]))
        token = match.group(0)
        if token.startswith('"'):
            out.append(token)  # double-quoted string literal, verbatim
        else:
            # single-quoted identifier: preserve meaningful whitespace,
            # punctuation and escaped quotes; the quoting is serialization.
            out.append(token[1:-1].replace("''", "'"))
        pos = match.end()
    out.append(_clean_formula_tokens(text[pos:]))
    return ''.join(out)


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
