"""spreadsheet-semantic-v3: layout-independent semantic checks with diagnostics.

The original-content comparison classifies damage from serialization noise:

  FAIL (strict, business meaning):
    source:worksheets / relative order, source:data (missing, changed or added
    real values), source:formulas (formula cells must stay formulas and only the
    explicitly supported serialization equivalences are accepted), source:charts,
    source:defined_names (a name is missing), source:defined_names_damaged (a
    name's target is invalid or broken, e.g. #REF!), source:merged_regions_removed
    (a source merge disappears), source:number_formats_meaning (a change that
    alters the unit expression).

  DIAGNOSTIC (recorded, not failing):
    empty-string cells normalized to empty cells on sheets declared by the
    manifest's empty_strings_policy, number-format serialization that keeps the
    unit expression, font/fill/alignment/border/protection representation,
    merged-region additions, defined-name attribute-text serialization whose
    target remains valid.

No extra full-table scans are introduced; the existing passes over each original
sheet feed both the strict checks and the diagnostic statistics.
"""
import gc
import re
from copy import copy
from itertools import zip_longest

from .contracts import read_json, sha256
from .workbooks import chart_sources, normalized_formula


def format_meaning(value):
    """Unit-expression template of a number format.

    None / General resolve to the same empty template (the read_only-mode
    artifact). Format codes (`0 # ? , . @ _ *`) and bracket expressions
    (colors, locale) are stripped; the remaining literal text (currency symbols,
    percent, unit suffixes) is the unit expression. A difference in this
    template changes how a value is expressed and must fail.
    """
    if value is None or str(value).strip() in ('General', ''):
        return ''
    text = str(value).replace('"', '').replace('\\', '').replace(';@', '')
    text = re.sub(r'[0#?,@_.*]+', '', text)
    text = re.sub(r'\[[^\]]*\]', '', text)
    text = re.sub(r'\s+', '', text)
    return text


def _collect_names(book):
    """{(name, scope): DefinedName}; scope None=workbook-global or a sheet title."""
    names = {}
    for name, item in book.defined_names.items():
        names[(name, None)] = item
    for ws in book.worksheets:
        local = getattr(ws, 'defined_names', None)
        if not local:
            continue
        for name, item in local.items():
            names[(name, ws.title)] = item
    return names


_DN_SHEET_REF = re.compile(
    r"(?:'((?:[^']|'')+)'|([^!]+))!"
    r"(\$?[A-Z]{1,3}\$?\d+|\$?[A-Z]{1,3}|\$?[1-9]\d*)"
    r"(?::(\$?[A-Z]{1,3}\$?\d+|\$?[A-Z]{1,3}|\$?[1-9]\d*))?")
# Bare (no-sheet) target: a cell/row always has a digit; a column range has a
# colon. A single bare column letter is ambiguous with a name and is left to
# the name-reference branch.
_DN_BARE_RANGE = re.compile(
    r"\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?"
    r"|\$?[1-9]\d*(?::\$?[1-9]\d*)?"
    r"|\$?[A-Z]{1,3}:\$?[A-Z]{1,3}")
_DN_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_DN_NUMBER = re.compile(r'^[+-]?(\d+(\.\d*)?|\.\d+)([Ee][+-]?\d+)?$')
_DN_STRING = re.compile(r'^"(?:[^"]|"")*"$')
_DN_BOOL = re.compile(r'^(TRUE|FALSE)$', re.I)
_BROKEN_TOKENS = ('#REF!', '#NAME?', '#VALUE!', '#DIV/0!', '#N/A', '#NULL!')


def _name_is_broken(item):
    return any(tok in str(getattr(item, 'attr_text', '')) for tok in _BROKEN_TOKENS)


def _normalize_range(r1, r2=None):
    first = r1.replace('$', '').upper()
    second = r2.replace('$', '').upper() if r2 else None
    return first + (':' + second if second else '')


def _resolve_referenced(name, scope, book, names, seen):
    """Resolve a defined-name reference, with cycle detection."""
    binding = _lookup_name(name, scope, names)
    if binding is None:
        return None  # referenced name does not exist
    found_key, target = binding
    if found_key in seen:
        return ('cycle', name)
    seen.add(found_key)
    return _resolve_name_meaning(target, book, names, found_key[1], seen)


def _resolve_name_meaning(item, book, names, scope, seen):
    """Canonical meaning of a defined-name target, or None if unresolvable."""
    text = str(getattr(item, 'attr_text', '')).strip()
    if text.startswith('='):
        text = text[1:]
    if any(tok in text for tok in _BROKEN_TOKENS):
        return ('broken', text)
    match = _DN_SHEET_REF.fullmatch(text)
    if match:
        sheet = match.group(1) or match.group(2)
        sheet = sheet.replace("''", "'")
        if sheet not in book:
            return None  # missing sheet
        return ('range', sheet, _normalize_range(match.group(3), match.group(4)))
    if _DN_BARE_RANGE.fullmatch(text):
        # relative range; resolved in the name's own scope
        return ('range', scope, _normalize_range(text))
    if _DN_NAME.fullmatch(text):
        return _resolve_referenced(text, scope, book, names, seen)
    if _DN_NUMBER.fullmatch(text):
        return ('const', 'number', format(float(text), '.12g'))
    if _DN_STRING.fullmatch(text):
        return ('const', 'string', text[1:-1].replace('""', '"'))
    if _DN_BOOL.fullmatch(text):
        return ('const', 'bool', text.upper())
    # function/complex expression: only an explicitly supported serialization
    # equivalence is accepted; anything changed is rejected.
    return ('expr', normalized_formula(text))


def _lookup_name(name, scope, names):
    """Excel names are case-insensitive; worksheet-local names take priority."""
    for wanted_scope in dict.fromkeys((scope, None)):
        for key, item in names.items():
            if key[1] == wanted_scope and key[0].casefold() == name.casefold():
                return key, item
    return None


def _shadowed_formula_names(formulas, source, output, src_names, out_names):
    """Reject additions that change name resolution in original formulas.

    Inspect RANGE operands, so string literals and function names do not count
    as name uses. Unused additions and equivalent bindings remain permitted.
    """
    from openpyxl.formula import Tokenizer
    from openpyxl.formula.tokenizer import TokenizerError

    source_keys = {(name.casefold(), scope) for name, scope in src_names}
    additions = {(name.casefold(), scope) for name, scope in out_names
                 if (name.casefold(), scope) not in source_keys}
    if not additions:
        return []
    changed = []
    for sheet, address, formula in formulas:
        try:
            tokens = Tokenizer(formula).items
        except TokenizerError:
            if any(scope in (None, sheet) for _, scope in additions):
                changed.append(f'{sheet}!{address}: cannot resolve formula names')
            continue
        for token in tokens:
            if token.type != 'OPERAND' or token.subtype != 'RANGE':
                continue
            scope, name = sheet, token.value
            if '!' in name:
                scope, name = name.rsplit('!', 1)
                if scope.startswith("'") and scope.endswith("'"):
                    scope = scope[1:-1].replace("''", "'")
            if not any((name.casefold(), s) in additions for s in (scope, None)):
                continue
            before = _lookup_name(name, scope, src_names)
            after = _lookup_name(name, scope, out_names)
            if before is None or after is None:
                changed.append(f'{sheet}!{address}: {token.value}')
                continue
            old_key, old_item = before
            new_key, new_item = after
            if old_key == new_key:
                continue  # Existing binding preservation is checked separately.
            old_meaning = _resolve_name_meaning(old_item, source, src_names, old_key[1], {old_key})
            new_meaning = _resolve_name_meaning(new_item, output, out_names, new_key[1], {new_key})
            if (old_meaning is None or new_meaning is None or old_meaning != new_meaning
                    or old_meaning[0] in ('expr', 'broken', 'cycle')):
                changed.append(f'{sheet}!{address}: {token.value}')
    return changed


def original_content(source, output, checks, empty_string_policy=None):
    """Compare each original occupied coordinate, not a global row/column template."""
    from openpyxl import load_workbook
    from .verify import preserved_value
    from .workbooks import logical_value
    allowed_empty = set()
    if isinstance(empty_string_policy, dict):
        allowed_empty = set(empty_string_policy.get('sheets', []))
    a = load_workbook(source, read_only=True, data_only=False)
    b = load_workbook(output, read_only=True, data_only=False)
    try:
        original_names = a.sheetnames
        checks.add('source:worksheets', all(n in b for n in original_names), b.sheetnames)
        checks.add('source:relative_order', [n for n in b.sheetnames if n in original_names] == original_names)
        for name in original_names:
            if name not in b:
                continue
            missing, changed, formulas, added = [], [], [], []
            empty_string, numfmt, unit_diffs = [], [], []
            for left, right in zip_longest(a[name].iter_rows(), b[name].iter_rows(), fillvalue=()):
                for old, new in zip_longest(left, right):
                    if old is None or old.value is None:
                        if new is not None and new.value not in (None, '') and len(added) < 12:
                            added.append(new.coordinate)
                        continue
                    address = old.coordinate
                    if new is None or new.value is None:
                        if old.value == '':
                            # Empty-string markers become empty cells after
                            # openpyxl/LibreOffice serialization. Only sheets
                            # declared by the manifest policy are eligible.
                            if name in allowed_empty:
                                if len(empty_string) < 24:
                                    empty_string.append(address)
                            elif len(missing) < 12:
                                missing.append(address)
                        elif len(missing) < 12:
                            missing.append(address)
                    elif old.value == '':
                        if new.value != '' and len(changed) < 12:
                            changed.append(address)
                    elif old.data_type == 'f':
                        # A formula must remain a formula cell with the same
                        # formula; only supported serialization equivalences are
                        # accepted and string literals are compared verbatim.
                        if new.data_type != 'f' or normalized_formula(old.value) != normalized_formula(new.value):
                            if len(formulas) < 12:
                                formulas.append(address)
                    elif not preserved_value(new.value, logical_value(old.value)) and len(changed) < 12:
                        changed.append(address)
                    if new is not None:
                        old_unit = format_meaning(old.number_format)
                        new_unit = format_meaning(new.number_format)
                        if old_unit != new_unit:
                            if len(unit_diffs) < 24:
                                unit_diffs.append(address)
                        elif str(old.number_format) != str(new.number_format):
                            if len(numfmt) < 24:
                                numfmt.append(address)
            checks.add('source:data:' + name, not missing and not changed and not added,
                       dict(missing=missing, changed=changed, added=added))
            checks.add('source:formulas:' + name, not formulas, formulas)
            checks.add('source:number_formats_meaning:' + name, not unit_diffs, unit_diffs)
            checks.diag('source:number_formats:' + name, numfmt)
            checks.diag('source:empty_string_normalized:' + name, empty_string)
    finally:
        a.close(); b.close()
    # Non-cell structures are small; load originals one time to inspect their object graph.
    a = load_workbook(source, data_only=False)
    b = load_workbook(output, data_only=False)
    try:
        original_formulas = []
        for sheet in a:
            if sheet.title not in b:
                continue
            other = b[sheet.title]
            merged = {str(r) for r in sheet.merged_cells.ranges}
            merged_other = {str(r) for r in other.merged_cells.ranges}
            removed = sorted(merged - merged_other)
            added_merge = sorted(merged_other - merged)
            # Removed source merges are structure damage; additions are
            # representation noise (data checks guard any content loss).
            checks.add('source:merged_regions_removed:' + sheet.title, not removed, removed)
            checks.diag('source:merged_regions:' + sheet.title, added_merge)
            sources = [(type(c).__name__, chart_sources(c)) for c in other._charts]
            wanted = [(type(c).__name__, chart_sources(c)) for c in sheet._charts]
            checks.add('source:charts:' + sheet.title, len(sources) >= len(wanted) and all(sources.count(s) >= wanted.count(s) for s in wanted), sources)
            # Style identity uses semantic objects, never style IDs, which engines reorder.
            differences = []
            compared_styles = {}
            for cell in sheet._cells.values():
                if cell.data_type == 'f':
                    original_formulas.append((sheet.title, cell.coordinate, cell.value))
                new = other[cell.coordinate]
                # IDs are only a cache key scoped to these two books. Compare the
                # underlying objects once per pair, never IDs across workbooks.
                pair = (cell.style_id, new.style_id)
                if pair not in compared_styles:
                    compared_styles[pair] = [attr for attr in ('font', 'fill', 'alignment', 'border', 'protection')
                                             if copy(getattr(cell, attr)) != copy(getattr(new, attr))]
                for attr in compared_styles[pair]:
                    if len(differences) < 24:
                        differences.append(cell.coordinate + ':' + attr)
            checks.diag('source:styles:' + sheet.title, differences)
        missing_names, damaged_names, serialized_names, added_names = [], [], [], []
        src_names = _collect_names(a)
        out_names = _collect_names(b)
        for (name, scope) in src_names:
            label = f'{name}@{scope or "global"}'
            if (name, scope) not in out_names:
                missing_names.append(label)
                continue
            old_item = src_names[(name, scope)]
            new_item = out_names[(name, scope)]
            if _name_is_broken(old_item):
                # A name already broken in the source is only a historical
                # state when its content stays byte-identical.
                if str(old_item.attr_text) != str(new_item.attr_text):
                    damaged_names.append(label)
                continue
            old_meaning = _resolve_name_meaning(old_item, a, src_names, scope, set())
            new_meaning = _resolve_name_meaning(new_item, b, out_names, scope, set())
            if old_meaning is None or new_meaning is None or old_meaning != new_meaning:
                damaged_names.append(label)
            elif str(old_item.attr_text) != str(new_item.attr_text):
                serialized_names.append(label)
        for (name, scope) in out_names:
            if (name, scope) not in src_names:
                added_names.append(f'{name}@{scope or "global"}')
        checks.add('source:defined_names', not missing_names, missing_names)
        checks.add('source:defined_names_damaged', not damaged_names, damaged_names)
        shadowed = _shadowed_formula_names(original_formulas, a, b, src_names, out_names)
        checks.add('source:defined_name_shadowing', not shadowed, shadowed[:12])
        checks.diag('source:defined_names_serialization', serialized_names)
        checks.diag('source:defined_names_added', added_names)
    finally:
        a.close(); b.close(); del a, b; gc.collect()


REF = re.compile(r"(?:(?:'((?:[^']|'')+)'|([A-Za-z_][A-Za-z0-9_. ]*))!)?(\$?[A-Z]{1,3}\$?\d+)(?::(\$?[A-Z]{1,3}\$?\d+))?")


def dependencies(book, location, seen=None):
    """Transitive references, allowing any formula implementation and helper sheets."""
    from openpyxl.utils.cell import range_boundaries, get_column_letter
    seen = set() if seen is None else seen
    name, address = location
    key = (name, address.replace('$', ''))
    if key in seen:
        return seen
    seen.add(key)
    if name not in book:
        return seen
    cell = book[name][key[1]]
    if cell.data_type != 'f':
        return seen
    # Ignore literal strings (e.g. INDIRECT text is not accepted as proven dependency).
    formula = re.sub(r'"(?:[^"]|"")*"', '""', str(cell.value))
    for match in REF.finditer(formula):
        target = (match[1] or match[2] or name).replace("''", "'")
        start, end = match[3].replace('$', ''), (match[4] or match[3]).replace('$', '')
        lo, bottom, hi, top = range_boundaries(start + ':' + end)
        # Large source ranges establish a sheet dependency without enumerating millions of cells.
        if (hi - lo + 1) * (top - bottom + 1) > 5000:
            seen.add((target, '*')); continue
        for row in range(bottom, top + 1):
            for col in range(lo, hi + 1):
                dependencies(book, (target, get_column_letter(col) + str(row)), seen)
    return seen


def verify_semantic_xlsx(manifest, expected, workspace, checks, deferred_outputs=()):
    from openpyxl import load_workbook
    from .verify import same_number, color, ERRORS
    req = manifest['requirements']; output = workspace / 'output'
    path = output / manifest['output_workbook']
    checks.add('workbook_file', path.is_file())
    if not path.is_file():
        return
    source = workspace / 'input' / manifest['workbook']
    original_content(source, path, checks,
                     empty_string_policy=req.get('empty_strings_policy'))
    book = load_workbook(path, data_only=False)
    cache = load_workbook(path, data_only=True)
    src = load_workbook(source, read_only=True)
    originals = set(src.sheetnames); src.close()
    features = read_json(output / 'workbook_features.json')
    occupied = set()
    def locate(spec, formula=False):
        name, address = spec['sheet'], spec['cell']
        if name in originals or name not in book or not re.fullmatch(r'[A-Z]{1,3}[1-9]\d*', address):
            raise ValueError('feature must address one cell on an added sheet')
        key = (name, address)
        if key in occupied:
            raise ValueError('duplicate feature location')
        occupied.add(key)
        cell = book[name][address]
        if formula:
            checks.add('feature:formula:' + name + '!' + address, cell.data_type == 'f')
        return cell, key
    try:
        name = features['summary_sheet']
        checks.add('overview_added', name in book and name not in originals)
        checks.add('metric_inventory', set(features['metrics']) == {m['id'] for m in req['metrics']})
        for metric in req['metrics']:
            cell, key = locate(features['metrics'][metric['id']], True)
            checks.add('semantic:metric:' + metric['id'], same_number(cache[key[0]][key[1]].value, expected['metric_values'][metric['id']]))
            deps = dependencies(book, key)
            checks.add('semantic:source_dependency:' + metric['id'], any(n in originals for n, _ in deps))
            checks.add('feature:metric_color:' + metric['id'], color(cell, '008000'))
        scene = features['scenario']; cell, selector = locate(scene['selector'])
        spec = req['scenario']; names = [r['name'] for r in spec['rows']]
        checks.add('scenario:default', cell.value == spec['default'])
        dropdowns = [v for v in book[selector[0]].data_validations.dataValidation if v.type == 'list' and selector[1] in v.sqref]
        valid = False
        for v in dropdowns:
            expression = str(v.formula1).strip('=')
            if expression.startswith('"'):
                choices = expression.strip('"').split(',')
            else:
                sheet_name, area = (expression.rsplit('!', 1) if '!' in expression else (selector[0], expression))
                choices = [c.value for row in book[sheet_name.strip("'")][area.replace('$', '')] for c in row]
            valid = valid or choices == names
        checks.add('scenario:dropdown', valid)
        checks.add('scenario:selector_color', color(cell, '0000FF'))
        checks.add('scenario:inventory', set(scene['assumptions']) == set(names))
        assumption_locations = []
        for row in spec['rows']:
            supplied = scene['assumptions'][row['name']]
            checks.add('scenario:dimension_inventory:' + row['name'], set(supplied) == set(row['assumptions']))
            for dim, value in row['assumptions'].items():
                c, key = locate(supplied[dim]); assumption_locations.append(key)
                checks.add('scenario:assumption:' + row['name'] + ':' + dim, same_number(c.value, value) and c.data_type != 'f' and color(c, '0000FF'))
        checks.add('projection_inventory', set(scene['projections']) == {p['id'] for p in spec['projections']})
        for projection in spec['projections']:
            c, key = locate(scene['projections'][projection['id']], True)
            deps = dependencies(book, key)
            checks.add('semantic:projection:' + projection['id'], same_number(cache[key[0]][key[1]].value, expected['scenario_values'][spec['default']][projection['id']]))
            checks.add('semantic:scenario_dependency:' + projection['id'], selector in deps and any(p in deps for p in assumption_locations))
        checks.add('chart_inventory', set(features['charts']) == {c['id'] for c in req['charts']})
        chart_locations = set()
        for chart in req['charts']:
            loc = features['charts'][chart['id']]; s = loc['sheet']; i = loc['index']
            ok = s in book and s not in originals and isinstance(i, int) and 0 <= i < len(book[s]._charts) and (s, i) not in chart_locations
            chart_locations.add((s, i))
            if ok:
                references = chart_sources(book[s]._charts[i])
                ok = bool(references) and all('[' not in r for r in references)
                checks.add('chart:references:' + chart['id'], ok, references)
                series_values = []
                linked = True
                for series in book[s]._charts[i].series:
                    reference = getattr(getattr(series, 'val', None), 'numRef', None)
                    if reference is None:
                        reference = getattr(getattr(series, 'yVal', None), 'numRef', None)
                    if reference is None:
                        linked = False; continue
                    text = reference.f
                    target, area = text.rsplit('!', 1); target = target.strip("'").replace("''", "'")
                    area = area.replace('$', '')
                    cells = [c for row in book[target][area] for c in row]
                    values = [cache[target][c.coordinate].value for c in cells]
                    series_values.append(values)
                    linked = linked and all(target in originals or any(n in originals for n, _ in dependencies(book, (target, c.coordinate))) for c in cells)
                wanted = expected.get('chart_values', {}).get(chart['id'])
                checks.add('semantic:chart:' + chart['id'], wanted is not None and any(len(v) == len(wanted) and all(same_number(a, b) for a, b in zip(v, wanted)) for v in series_values), series_values)
                checks.add('semantic:chart_dependency:' + chart['id'], linked)
            checks.add('chart:' + chart['id'], ok)
        added = [s for s in book if s.title not in originals]
        checks.add('format:conditional_rules', sum(len(s.conditional_formatting) for s in added) >= req['minimum_conditional_formats'])
        checks.add('format:comments', sum(c.comment is not None for s in added for c in s._cells.values()) >= req['minimum_comments'])
        checks.add('format:freeze_panes', name in book and book[name].freeze_panes is not None)
        checks.add('no_external_links', not book._external_links)
        errors = [s.title + '!' + c.coordinate for s in cache for c in s._cells.values() if c.data_type == 'e' or (isinstance(c.value, str) and c.value in ERRORS)]
        checks.add('zero_formula_errors', not errors, errors[:12])
        recalc = read_json(output / 'formula_recalc.json')
        checks.add('recalc_report', recalc.get('status') == 'success' and recalc.get('total_errors') == 0)
        for item in manifest.get('publish_files', []):
            p = output / item['output']; checks.add('published:' + item['output'], p.is_file() and sha256(p) == item['sha256'])
        for filename in manifest['required_outputs']:
            if filename not in ('business_verification.json', *deferred_outputs):
                checks.add('deliverable:' + filename, (output / filename).is_file())
        for filename, refs in (('metrics.csv', features['metrics']),
                               ('scenario.csv', scene['projections'])):
            csv_path = output / filename
            try:
                import csv
                with csv_path.open(newline='', encoding='utf-8') as stream:
                    rows = list(csv.reader(stream))
                wanted_ids = list(refs)
                csv_ok = bool(rows) and rows[0] == ['metric', 'value']
                actual_rows = rows[1:] if csv_ok else []
                csv_ok = csv_ok and [row[0] for row in actual_rows if row] == wanted_ids
                for ident, row in zip(wanted_ids, actual_rows):
                    expected_value = cache[refs[ident]['sheet']][refs[ident]['cell']].value
                    try:
                        actual_value = float(row[1])
                    except (IndexError, TypeError, ValueError):
                        csv_ok = False
                        continue
                    csv_ok = csv_ok and same_number(actual_value, expected_value)
                checks.add('csv_matches_workbook:' + filename, csv_ok,
                           {'rows': len(actual_rows), 'expected_rows': len(wanted_ids)})
            except (OSError, UnicodeError, ValueError) as exc:
                checks.add('csv_matches_workbook:' + filename, False,
                           f'{type(exc).__name__}: {exc}')
    finally:
        book.close(); cache.close(); del book, cache; gc.collect()


def verify_semantic_xlsx_loop(manifest, expected, workspace, checks, deferred_outputs=()):
    """Run the versioned per-iteration business checks inside the benchmark ROI.

    This deliberately matches the old XLSX verifier's scope: workbook and base
    sheet presence/scale, task features, cached values/errors, and deliverables.
    Source-cell equality, formula/name/chart protection, and recursive audits
    remain in ``verify_semantic_xlsx`` and run only during independent acceptance.
    """
    from openpyxl import load_workbook
    from .verify import same_number, color, ERRORS

    req = manifest['requirements']
    output = workspace / 'output'
    path = output / manifest['output_workbook']
    checks.add('workbook_file', path.is_file() and path.stat().st_size >= req.get('minimum_bytes', 1))
    if not path.is_file():
        return

    book = load_workbook(path, data_only=False)
    cache = load_workbook(path, data_only=True, read_only=True)
    try:
        original_names = list(req['base_sheets'])
        checks.add('base_sheets_present', all(name in book for name in original_names), book.sheetnames)
        checks.add('base_sheet_order', [name for name in book.sheetnames if name in original_names] == original_names,
                   [name for name in book.sheetnames if name in original_names])
        source_dimensions = req['base_dimensions']
        for sheet_name in original_names:
            dst = book[sheet_name] if sheet_name in book else None
            src_size = tuple(source_dimensions[sheet_name])
            dst_size = ((dst.max_row or 0), (dst.max_column or 0)) if dst else (0, 0)
            checks.add('base_sheet_scale:' + sheet_name,
                       dst is not None and dst_size[0] >= src_size[0] and dst_size[1] >= src_size[1],
                       {'source': src_size, 'output': dst_size})

        features = read_json(output / 'workbook_features.json')
        occupied = set()
        def locate(spec, formula=False):
            name, address = spec['sheet'], spec['cell']
            if name in original_names or name not in book or not re.fullmatch(r'[A-Z]{1,3}[1-9]\d*', address):
                raise ValueError('feature must address one cell on an added sheet')
            key = (name, address)
            if key in occupied:
                raise ValueError('duplicate feature location')
            occupied.add(key)
            cell = book[name][address]
            if formula:
                checks.add('feature:formula:' + name + '!' + address, cell.data_type == 'f')
            return cell, key

        name = features['summary_sheet']
        checks.add('overview_added', name in book and name not in original_names)
        checks.add('metric_inventory', set(features['metrics']) == {m['id'] for m in req['metrics']})
        for metric in req['metrics']:
            cell, key = locate(features['metrics'][metric['id']], True)
            checks.add('semantic:metric:' + metric['id'],
                       same_number(cache[key[0]][key[1]].value, expected['metric_values'][metric['id']]))
            deps = dependencies(book, key)
            checks.add('semantic:source_dependency:' + metric['id'], any(n in original_names for n, _ in deps))
            checks.add('feature:metric_color:' + metric['id'], color(cell, '008000'))

        scene = features['scenario']
        cell, selector = locate(scene['selector'])
        spec = req['scenario']
        scenario_names = [row['name'] for row in spec['rows']]
        checks.add('scenario:default', cell.value == spec['default'])
        dropdowns = [v for v in book[selector[0]].data_validations.dataValidation
                     if v.type == 'list' and selector[1] in v.sqref]
        valid = False
        for validation in dropdowns:
            expression = str(validation.formula1).strip('=')
            if expression.startswith('"'):
                choices = expression.strip('"').split(',')
            else:
                sheet_name, area = (expression.rsplit('!', 1) if '!' in expression
                                    else (selector[0], expression))
                choices = [c.value for row in book[sheet_name.strip("'")][area.replace('$', '')] for c in row]
            valid = valid or choices == scenario_names
        checks.add('scenario:dropdown', valid)
        checks.add('scenario:selector_color', color(cell, '0000FF'))
        checks.add('scenario:inventory', set(scene['assumptions']) == set(scenario_names))
        assumption_locations = []
        for row in spec['rows']:
            supplied = scene['assumptions'][row['name']]
            checks.add('scenario:dimension_inventory:' + row['name'],
                       set(supplied) == set(row['assumptions']))
            for dimension, value in row['assumptions'].items():
                c, key = locate(supplied[dimension])
                assumption_locations.append(key)
                checks.add('scenario:assumption:' + row['name'] + ':' + dimension,
                           same_number(c.value, value) and c.data_type != 'f' and color(c, '0000FF'))
        checks.add('projection_inventory', set(scene['projections']) == {p['id'] for p in spec['projections']})
        for projection in spec['projections']:
            c, key = locate(scene['projections'][projection['id']], True)
            deps = dependencies(book, key)
            checks.add('semantic:projection:' + projection['id'],
                       same_number(cache[key[0]][key[1]].value,
                                   expected['scenario_values'][spec['default']][projection['id']]))
            checks.add('semantic:scenario_dependency:' + projection['id'],
                       selector in deps and any(point in deps for point in assumption_locations))

        checks.add('chart_inventory', set(features['charts']) == {chart['id'] for chart in req['charts']})
        chart_locations = set()
        for chart in req['charts']:
            location = features['charts'][chart['id']]
            sheet_name, index = location['sheet'], location['index']
            ok = (sheet_name in book and sheet_name not in original_names
                  and isinstance(index, int) and 0 <= index < len(book[sheet_name]._charts)
                  and (sheet_name, index) not in chart_locations)
            chart_locations.add((sheet_name, index))
            if ok:
                references = chart_sources(book[sheet_name]._charts[index])
                ok = bool(references) and all('[' not in ref for ref in references)
                checks.add('chart:references:' + chart['id'], ok, references)
                values, linked = [], True
                for series in book[sheet_name]._charts[index].series:
                    reference = getattr(getattr(series, 'val', None), 'numRef', None)
                    if reference is None:
                        reference = getattr(getattr(series, 'yVal', None), 'numRef', None)
                    if reference is None:
                        linked = False
                        continue
                    target, area = reference.f.rsplit('!', 1)
                    target, area = target.strip("'").replace("''", "'"), area.replace('$', '')
                    cells = [item for row in book[target][area] for item in row]
                    values.append([cache[target][item.coordinate].value for item in cells])
                    linked = linked and all(target in original_names or any(
                        original in original_names for original, _ in dependencies(book, (target, item.coordinate)))
                        for item in cells)
                wanted = expected.get('chart_values', {}).get(chart['id'])
                checks.add('semantic:chart:' + chart['id'], wanted is not None and any(
                    len(series_values) == len(wanted) and all(same_number(a, b) for a, b in zip(series_values, wanted))
                    for series_values in values), values)
                checks.add('semantic:chart_dependency:' + chart['id'], linked)
            checks.add('chart:' + chart['id'], ok)

        added = [sheet for sheet in book if sheet.title not in original_names]
        formula_count = sum(cell.data_type == 'f' for sheet in added
                            for row in sheet.iter_rows() for cell in row)
        checks.add('added_formula_count', formula_count >= req.get('minimum_formula_count', 1), formula_count)
        checks.add('format:conditional_rules',
                   sum(len(sheet.conditional_formatting) for sheet in added) >= req['minimum_conditional_formats'])
        checks.add('format:comments',
                   sum(cell.comment is not None for sheet in added for cell in sheet._cells.values()) >= req['minimum_comments'])
        checks.add('format:freeze_panes', name in book and book[name].freeze_panes is not None)
        checks.add('no_external_links', not book._external_links)
        errors = [sheet.title + '!' + cell.coordinate for sheet in added
                  for row in cache[sheet.title].iter_rows() for cell in row
                  if cell.data_type == 'e' or (isinstance(cell.value, str) and cell.value in ERRORS)]
        checks.add('zero_formula_errors', not errors, errors[:12])
        recalc = read_json(output / 'formula_recalc.json')
        checks.add('recalc_report', recalc.get('status') == 'success' and recalc.get('total_errors') == 0)
        for item in manifest.get('publish_files', []):
            published = output / item['output']
            checks.add('published:' + item['output'], published.is_file() and sha256(published) == item['sha256'])
        for filename in manifest['required_outputs']:
            if filename not in ('business_verification.json', *deferred_outputs):
                checks.add('deliverable:' + filename, (output / filename).is_file())
        for filename, refs in (('metrics.csv', features['metrics']),
                               ('scenario.csv', scene['projections'])):
            csv_path = output / filename
            try:
                import csv
                with csv_path.open(newline='', encoding='utf-8') as stream:
                    rows = list(csv.reader(stream))
                wanted_ids = list(refs)
                csv_ok = bool(rows) and rows[0] == ['metric', 'value']
                actual_rows = rows[1:] if csv_ok else []
                csv_ok = csv_ok and [row[0] for row in actual_rows if row] == wanted_ids
                for ident, row in zip(wanted_ids, actual_rows):
                    expected_value = cache[refs[ident]['sheet']][refs[ident]['cell']].value
                    try:
                        actual_value = float(row[1])
                    except (IndexError, TypeError, ValueError):
                        csv_ok = False
                        continue
                    csv_ok = csv_ok and same_number(actual_value, expected_value)
                checks.add('csv_matches_workbook:' + filename, csv_ok,
                           {'rows': len(actual_rows), 'expected_rows': len(wanted_ids)})
            except (OSError, UnicodeError, ValueError) as exc:
                checks.add('csv_matches_workbook:' + filename, False,
                           f'{type(exc).__name__}: {exc}')
    finally:
        book.close()
        cache.close()
        del book, cache
        gc.collect()
