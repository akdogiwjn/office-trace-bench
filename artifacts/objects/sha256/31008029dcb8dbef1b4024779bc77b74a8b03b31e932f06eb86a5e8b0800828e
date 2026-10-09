"""Render the original task structure using domain parameters from each manifest."""
from .contracts import ROOT


def count_word(value):
    words = ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
             'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
             'seventeen', 'eighteen', 'nineteen')
    return words[value] if 0 <= value < len(words) else str(value)


def render_prompt(manifest, workspace, manifest_path, project=ROOT):
    template = manifest.get('prompt_template', manifest['kind'] + '.txt')
    context = dict(dataset_id=manifest['dataset_id'], workspace=workspace,
                   manifest=manifest_path, project=project)
    if manifest.get('prompt_contract') and template.startswith('legacy-'):
        context.update(parameters(manifest))
    return (ROOT / 'prompts' / template).read_text().format(**context)


def parameters(manifest):
    req, spec = manifest['requirements'], manifest['prompt_contract']
    context = dict(spec)
    context['verifier_filename'] = manifest.get('agent_verifier', 'verify_office.py')
    if manifest['kind'] == 'xlsx':
        scenario = req['scenario']
        rows = scenario['rows']
        dimensions = list(scenario['table_columns'])
        cell_names = [cell for row in rows for cell in row['cells']]
        first, last = cell_names[0], cell_names[-1]
        metrics = []
        for metric in req['metrics']:
            instruction = metric.get('prompt_instruction')
            if not instruction:
                refs = metric['required_references']
                instruction = ('cross-sheet formula linked to ' + refs[0] + '.' if len(refs) == 1 else
                               'formula: ' + metric['meaning'] + '; reference ' + ' and '.join(refs) + '.')
            metrics.append(f"   - {metric['cell']} {metric['name']}: {instruction}")
        scenario_metrics = []
        for metric in scenario['formula_metrics']:
            instruction = metric.get('prompt_instruction') or (
                metric['meaning'] + '; reference ' + ' and '.join(metric['required_references']) + '.')
            scenario_metrics.append(f"   - {metric['cell']} {metric['name']}: {instruction}")
        def dimension_value(row, column):
            values = [value for cell, value in row['cells'].items()
                      if cell.rstrip('0123456789') == column]
            if len(values) != 1:
                raise ValueError('each scenario row must have one cell per dimension')
            return values[0]
        scene_table = ', '.join(row['name'] + ' ' + '/'.join(
            f"{dimension_value(row, col):.2f}" for col in dimensions[1:]) for row in rows)
        lookups = [m for m in scenario['formula_metrics']
                   if m['required_references'] == [scenario['selector_cell']]]
        projected = [m for m in scenario['formula_metrics'] if m not in lookups]
        context.update(workbook=manifest['workbook'], output_workbook=manifest['output_workbook'],
                       base_sheet_count=count_word(len(req['base_sheets'])),
                       raw_count=f"{spec['raw_record_count']:,}", raw_sheet=', '.join(req['raw_sheets']),
                       summary_sheet=req['summary_sheet'], kpi_lines='\n'.join(metrics),
                       scenario_count=count_word(len(rows)), selector_cell=scenario['selector_cell'],
                       scenario_names=', '.join(r['name'] for r in rows), scenario_default=scenario['default'],
                       scenario_table_range=f'{first}:{last}', scenario_table=scene_table,
                       scenario_dimensions=' and '.join(scenario['table_columns'][c].lower().removesuffix(' multiplier') for c in dimensions[1:]),
                       scenario_formula_lines='\n'.join(scenario_metrics),
                       lookup_cells=' and '.join(m['cell'] for m in lookups),
                       projected_formula_lines='\n'.join(
                           f"   - {m['cell']} {m['name']} is a formula based on " +
                           (', '.join(m['required_references'][:-1]) + ', and ' + m['required_references'][-1]
                            if len(m['required_references']) > 2 else ' and '.join(m['required_references'])) + '.'
                           for m in projected),
                       chart_count=count_word(len(req['charts'])),
                       chart_descriptions=' and '.join(chart['description'] + ' using ' + ', '.join(chart['required_references']).replace('!', '') for chart in req['charts']),
                       original_chart_count=count_word(spec['original_chart_count']),
                       conditional_format_count=count_word(req['minimum_conditional_formats']),
                       comment_count=count_word(req['minimum_comments']), recalc_timeout=req['recalc_timeout'])
        published = manifest.get('publish_files', [])
        context.update(reference_files=' and '.join(p['input'] for p in published),
                       reference_count=count_word(len(published)),
                       metadata_files=' and '.join(spec['metadata_files']),
                       csv_publish_description=' and '.join('output/' + p['output'] for p in published),
                       output_list='\n'.join('- ' + p + (' with status=success' if p == 'business_verification.json' else '') for p in manifest['required_outputs']))
    else:
        records = req['record_count']
        pages = req['page_count']
        summary = [(k, v) for k, v in manifest['summary_contract'].items() if k != 'input_form']
        summary.sort(key=lambda item: isinstance(item[1], bool))
        fields = [k + '=' + (str(v).lower() if isinstance(v, bool) else str(v)) +
                  (f' (blank template plus {count_word(records)} outputs)' if k == 'rendered_page_count' else '')
                  for k, v in summary]
        context.update(form=manifest['form'], records=manifest['records'],
                       record_count=records, record_count_word=count_word(records),
                       page_count=pages, page_count_word=count_word(pages),
                       render_count=records + 1, render_count_word=count_word(records + 1),
                       rendered_pages=pages * (records + 1),
                       summary_fields=', '.join(fields[:-1]) + ', and ' + fields[-1])
    return context
