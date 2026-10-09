"""Layout-independent semantic checks, with source preservation checked separately."""
import gc
import re
from copy import copy
from itertools import zip_longest

from .contracts import read_json, sha256
from .workbooks import chart_sources, normalized_formula


def original_content(source, output, checks):
    """Compare each original occupied coordinate, not a global row/column template."""
    from openpyxl import load_workbook
    from .verify import preserved_value
    from .workbooks import logical_value
    a = load_workbook(source, read_only=True, data_only=False)
    b = load_workbook(output, read_only=True, data_only=False)
    try:
        original_names = a.sheetnames
        checks.add('source:worksheets', all(n in b for n in original_names), b.sheetnames)
        checks.add('source:relative_order', [n for n in b.sheetnames if n in original_names] == original_names)
        for name in original_names:
            if name not in b:
                continue
            missing, changed, formulas, format_changes = [], [], [], []
            for left, right in zip_longest(a[name].iter_rows(), b[name].iter_rows(), fillvalue=()):
                for old, new in zip_longest(left, right):
                    if old is None or old.value is None:
                        continue
                    address = old.coordinate
                    if new is None or new.value is None:
                        if len(missing) < 12: missing.append(address)
                    elif old.data_type == 'f':
                        if normalized_formula(old.value) != normalized_formula(new.value) and len(formulas) < 12:
                            formulas.append(address)
                    elif not preserved_value(new.value, logical_value(old.value)) and len(changed) < 12:
                        changed.append(address)
                    # Currency quoting and implicit General variations are serialization details.
                    fmt = lambda v: str(v).replace('"', '').replace('\\', '').replace(';@', '')
                    if new is not None and fmt(old.number_format) != fmt(new.number_format) and len(format_changes) < 12:
                        format_changes.append(address)
            checks.add('source:data:' + name, not missing and not changed, dict(missing=missing, changed=changed))
            checks.add('source:formulas:' + name, not formulas, formulas)
            checks.add('source:number_formats:' + name, not format_changes, format_changes)
    finally:
        a.close(); b.close()
    # Non-cell structures are small; load originals one time to inspect their object graph.
    a = load_workbook(source, data_only=False)
    b = load_workbook(output, data_only=False)
    try:
        for sheet in a:
            if sheet.title not in b: continue
            other = b[sheet.title]
            checks.add('source:merged_regions:' + sheet.title,
                       {str(r) for r in sheet.merged_cells.ranges} == {str(r) for r in other.merged_cells.ranges})
            sources = [chart_sources(c) for c in other._charts]
            wanted = [chart_sources(c) for c in sheet._charts]
            checks.add('source:charts:' + sheet.title, len(sources) >= len(wanted) and all(sources.count(s) >= wanted.count(s) for s in wanted), sources)
            # Style identity uses semantic objects, never style IDs, which engines reorder.
            differences = []
            for cell in sheet._cells.values():
                if not cell.has_style: continue
                new = other[cell.coordinate]
                for attr in ('font', 'fill', 'alignment', 'border', 'protection'):
                    if copy(getattr(cell, attr)) != copy(getattr(new, attr)):
                        if len(differences) < 12: differences.append(cell.coordinate + ':' + attr)
            checks.add('source:styles:' + sheet.title, not differences, differences)
        checks.add('source:defined_names', all(name in b.defined_names and str(b.defined_names[name].attr_text) == str(item.attr_text)
                    for name, item in a.defined_names.items()))
    finally:
        a.close(); b.close(); del a, b; gc.collect()


REF = re.compile(r"(?:(?:'((?:[^']|'')+)'|([A-Za-z_][A-Za-z0-9_. ]*))!)?(\$?[A-Z]{1,3}\$?\d+)(?::(\$?[A-Z]{1,3}\$?\d+))?")


def dependencies(book, location, seen=None):
    """Transitive references, allowing any formula implementation and helper sheets."""
    from openpyxl.utils.cell import range_boundaries, get_column_letter
    seen = set() if seen is None else seen
    name, address = location
    key = (name, address.replace('$', ''))
    if key in seen: return seen
    seen.add(key)
    if name not in book: return seen
    cell = book[name][key[1]]
    if cell.data_type != 'f': return seen
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
    if not path.is_file(): return
    source = workspace / 'input' / manifest['workbook']
    original_content(source, path, checks)
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
        if key in occupied: raise ValueError('duplicate feature location')
        occupied.add(key)
        cell = book[name][address]
        if formula: checks.add('feature:formula:' + name + '!' + address, cell.data_type == 'f')
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
                    if reference is None: linked = False; continue
                    text = reference.f
                    target, area = text.rsplit('!',1);target = target.strip("'").replace("''", "'")
                    area=area.replace('$','')
                    cells=[c for row in book[target][area] for c in row]
                    values=[cache[target][c.coordinate].value for c in cells]
                    series_values.append(values)
                    linked = linked and all(target in originals or any(n in originals for n,_ in dependencies(book,(target,c.coordinate))) for c in cells)
                wanted = expected.get('chart_values',{}).get(chart['id'])
                checks.add('semantic:chart:' + chart['id'], wanted is not None and any(len(v)==len(wanted) and all(same_number(a,b) for a,b in zip(v,wanted)) for v in series_values),series_values)
                checks.add('semantic:chart_dependency:' + chart['id'],linked)
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
    finally:
        book.close(); cache.close(); del book, cache; gc.collect()
