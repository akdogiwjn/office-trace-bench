"""Build hr_enhanced.xlsx (pre-recalc) from the source workbook.

Adds analysis/presentation sheets only; never modifies original sheets.
Also emits workbook_features.json recording chosen feature locations.
"""
import json
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, DataBarRule
from openpyxl.chart import BarChart, Reference

ROOT = Path('/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-HR')
SRC = ROOT / 'input/national_M2025_dl.xlsx'
OUT = ROOT / 'output'
OUT.mkdir(exist_ok=True)
PRE = ROOT / 'helpers/pre_recalc.xlsx'

SRC_SHEET = 'national_M2025_dl'
SUMMARY = 'OEWS Summary'
CHART_SHEET = 'Chart Data'

wb = openpyxl.load_workbook(SRC)

# ---- discover source layout -------------------------------------------------
src = wb[SRC_SHEET]
last = src.max_row
# rows holding the cross-industry all-ownerships majors (o_group == 'major')
major_rows = []
for r in range(2, last + 1):
    if str(src.cell(r, 11).value) == 'major':
        major_rows.append(r)
# the single all-occupations total row (o_group == 'total')
total_row = next(r for r in range(2, last + 1) if str(src.cell(r, 11).value) == 'total')

M = f"'{SRC_SHEET}'"
def gref(col, row):
    return f"{M}!${col}${row}"

# ---- styles -----------------------------------------------------------------
CAL = 'Calibri'
GREEN = 'FF008000'
BLUE = 'FF0000FF'
BLACK = 'FF000000'
hdr_fill = PatternFill('solid', fgColor='FFD9E1F2')
sec_fill = PatternFill('solid', fgColor='FFB4C6E7')
in_fill = PatternFill('solid', fgColor='FFFFF2CC')
thin = Side(style='thin', color='FFBFBFBF')
box = Border(left=thin, right=thin, top=thin, bottom=thin)
bold = Font(name=CAL, bold=True)
title_f = Font(name=CAL, bold=True, size=14)
green_f = Font(name=CAL, color=GREEN)
blue_f = Font(name=CAL, color=BLUE)
black_f = Font(name=CAL, color=BLACK)
italic_f = Font(name=CAL, italic=True, size=9)

# ---- summary sheet ----------------------------------------------------------
ws = wb.create_sheet(SUMMARY)
ws['A1'] = 'May 2025 OEWS National Analysis'
ws['A1'].font = title_f
ws['A2'] = ('Source: national_M2025_dl.xlsx — BLS Occupational Employment and Wage '
            'Statistics, May 2025 (U.S., cross-industry, all ownerships).')
ws['A2'].font = italic_f

ws['A4'] = 'Published National Totals (All Occupations)'
ws['A4'].font = bold
ws['A4'].fill = sec_fill
for c in 'BCD':
    ws[f'{c}4'].fill = sec_fill

headers = ['Metric', 'Value', 'Unit', 'Source / method']
for i, h in enumerate(headers):
    cell = ws.cell(5, 1 + i, h)
    cell.font = bold
    cell.fill = hdr_fill
    cell.border = box

metrics = [
    ('total_employment', 'National employment (all occupations)', 'employees',
     f'=INDEX({M}!$L$2:$L${last},MATCH("total",{M}!$K$2:$K${last},0))', '#,##0'),
    ('annual_mean_wage', 'Annual mean wage (all occupations)', 'USD per year',
     f'=INDEX({M}!$S$2:$S${last},MATCH("total",{M}!$K$2:$K${last},0))', '$#,##0'),
    ('hourly_median_wage', 'Hourly median wage (all occupations)', 'USD per hour',
     f'=INDEX({M}!$W$2:$W${last},MATCH("total",{M}!$K$2:$K${last},0))', '$#,##0.00'),
]
metric_cells = {}
src_notes = {
    'total_employment': f'Source: {SRC_SHEET}!L{total_row} (TOT_EMP, All Occupations, o_group=total).',
    'annual_mean_wage': f'Source: {SRC_SHEET}!S{total_row} (A_MEAN, All Occupations).',
    'hourly_median_wage': f'Source: {SRC_SHEET}!W{total_row} (H_MEDIAN, All Occupations).',
}
for i, (mid, label, unit, formula, nf) in enumerate(metrics):
    r = 6 + i
    ws.cell(r, 1, label).font = Font(name=CAL)
    vc = ws.cell(r, 2, formula)
    vc.font = green_f
    vc.number_format = nf
    vc.border = box
    ws.cell(r, 3, unit)
    note = ws.cell(r, 4, src_notes[mid])
    note.font = italic_f
    vc.comment = Comment(src_notes[mid] + ' Published aggregate estimate (not a sum of records).', 'Analyst')
    metric_cells[mid] = vc.coordinate

# ---- scenario section -------------------------------------------------------
ws['A10'] = 'Scenario Analysis'
ws['A10'].font = bold
ws['A10'].fill = sec_fill
ws['B10'].fill = sec_fill

ws['A11'] = 'Scenario'
ws['A11'].font = bold
sel = ws['B11']
sel.value = 'Base'
sel.font = blue_f
sel.fill = in_fill
sel.border = box
sel.comment = Comment('Editable scenario selector (Base / Increase). Drives the wage multiplier assumption.', 'Analyst')

ws['A13'] = 'Assumptions — wage multiplier'
ws['A13'].font = bold
ws['B13'] = 'Wage multiplier'
ws['B13'].font = bold
ws['B13'].fill = hdr_fill

ws['A14'] = 'Base'
base_cell = ws['B14']
base_cell.value = 1
base_cell.font = blue_f
base_cell.fill = in_fill
base_cell.number_format = '0.00'
base_cell.border = box

ws['A15'] = 'Increase'
inc_cell = ws['B15']
inc_cell.value = 1.05
inc_cell.font = blue_f
inc_cell.fill = in_fill
inc_cell.number_format = '0.00'
inc_cell.border = box

ws['A17'] = 'Selected wage multiplier'
ws['A17'].font = bold
mult = ws['B17']
mult.value = f'=INDEX($B$14:$B$15,MATCH($B$11,$A$14:$A$15,0))'
mult.font = black_f
mult.number_format = '0.00"x"'
mult.border = box

ws['A18'] = 'Projected annual mean wage (selected scenario)'
ws['A18'].font = bold
proj = ws['B18']
proj.value = f'={metric_cells["annual_mean_wage"]}*$B$17'
proj.font = black_f
proj.number_format = '$#,##0'
proj.border = box
proj.comment = Comment('Projection = published all-occupations annual mean wage × selected wage multiplier. Illustrative; no new employment records.', 'Analyst')

ws['A20'] = 'Notes'
ws['A20'].font = bold
ws['A21'] = ('Published aggregate estimates only. Suppressed / unavailable values are kept as source markers: '
             '"*" wage not available, "**" employment not available, "#" wage >= $115.00/hr or $239,200/yr, "~" <0.5% reporting.')
ws['A21'].font = italic_f
ws['A22'] = 'Original worksheets, data, formulas, charts, merged regions and formatting are preserved unchanged.'
ws['A22'].font = italic_f

# data validation dropdown for the selector
dv = DataValidation(type='list', formula1='"Base,Increase"', allow_blank=False)
dv.prompt = 'Choose Base or Increase'
dv.promptTitle = 'Scenario'
ws.add_data_validation(dv)
dv.add(sel)

# conditional formatting (>=2 on added sheets)
ws.conditional_formatting.add('B14:B15',
    CellIsRule(operator='greaterThan', formula=['1'], fill=PatternFill('solid', fgColor='FFFCE4D6')))
ws.conditional_formatting.add('B18',
    CellIsRule(operator='greaterThan', formula=['$B$14*0'], fill=PatternFill('solid', fgColor='FFE2EFDA')))

widths = {'A': 44, 'B': 16, 'C': 16, 'D': 58}
for col, w in widths.items():
    ws.column_dimensions[col].width = w
ws.freeze_panes = 'A5'

# ---- chart data sheet -------------------------------------------------------
cs = wb.create_sheet(CHART_SHEET)
cs['A1'] = 'Five largest major occupational groups by employment'
cs['A1'].font = title_f
cs['A2'] = ('National, cross-industry, all ownerships; major groups only '
            '(totals and detailed/broad/minor rows excluded).')
cs['A2'].font = italic_f

for i, h in enumerate(['SOC Code', 'Major occupation group', 'Employment']):
    cell = cs.cell(3, 1 + i, h)
    cell.font = bold
    cell.fill = hdr_fill
    cell.border = box
for k, r in enumerate(major_rows):
    rr = 4 + k
    code = cs.cell(rr, 1, f'={gref("I", r)}')
    code.font = green_f
    title = cs.cell(rr, 2, f'={gref("J", r)}')
    title.font = green_f
    emp = cs.cell(rr, 3, f'={gref("L", r)}')
    emp.font = green_f
    emp.number_format = '#,##0'

n_major = len(major_rows)
first_helper = 4
last_helper = 3 + n_major  # = 3 + 22 = 25
emp_range = f'$C${first_helper}:$C${last_helper}'
title_range = f'$B${first_helper}:$B${last_helper}'
code_range = f'$A${first_helper}:$A${last_helper}'

cs['A27'] = 'Rank'
cs['B27'] = 'SOC Code'
cs['C27'] = 'Major occupation group'
cs['D27'] = 'Employment'
for c in 'ABCD':
    cell = cs[f'{c}27']
    cell.font = bold
    cell.fill = hdr_fill
    cell.border = box

top_cells = []
for k in range(5):
    rr = 28 + k
    cs.cell(rr, 1, k + 1).font = bold
    emp = cs.cell(rr, 4, f'=LARGE({emp_range},{k + 1})')
    emp.font = black_f
    emp.number_format = '#,##0'
    emp.border = box
    title = cs.cell(rr, 3, f'=INDEX({title_range},MATCH(D{rr},{emp_range},0))')
    title.font = black_f
    code = cs.cell(rr, 2, f'=INDEX({code_range},MATCH(D{rr},{emp_range},0))')
    code.font = black_f
    top_cells.append(emp.coordinate)

cs.conditional_formatting.add(f'D28:D32', DataBarRule(start_type='min', end_type='max', color='FF638EC6'))

chart = BarChart()
chart.type = 'col'
chart.style = 10
chart.title = 'Top 5 major occupational groups by employment (May 2025 OEWS)'
chart.y_axis.title = 'Employment (employees)'
chart.x_axis.title = 'Major occupational group'
data = Reference(cs, min_col=4, min_row=27, max_row=32)
cats = Reference(cs, min_col=3, min_row=28, max_row=32)
chart.add_data(data, titles_from_data=True)
chart.set_categories(cats)
chart.width = 24
chart.height = 12
cs.add_chart(chart, 'F3')

cs.column_dimensions['A'].width = 12
cs.column_dimensions['B'].width = 46
cs.column_dimensions['C'].width = 18
cs.freeze_panes = 'A4'

wb.save(PRE)
print('saved', PRE)

features = {
    'summary_sheet': SUMMARY,
    'metrics': {
        'total_employment': {'sheet': SUMMARY, 'cell': metric_cells['total_employment']},
        'annual_mean_wage': {'sheet': SUMMARY, 'cell': metric_cells['annual_mean_wage']},
        'hourly_median_wage': {'sheet': SUMMARY, 'cell': metric_cells['hourly_median_wage']},
    },
    'scenario': {
        'selector': {'sheet': SUMMARY, 'cell': sel.coordinate},
        'assumptions': {
            'Base': {'wage_multiplier': {'sheet': SUMMARY, 'cell': base_cell.coordinate}},
            'Increase': {'wage_multiplier': {'sheet': SUMMARY, 'cell': inc_cell.coordinate}},
        },
        'projections': {
            'projected_mean_wage': {'sheet': SUMMARY, 'cell': proj.coordinate},
        },
    },
    'charts': {
        'major_employment': {'sheet': CHART_SHEET, 'index': 0},
    },
}
(OUT / 'workbook_features.json').write_text(json.dumps(features, indent=2) + '\n')
print('wrote workbook_features.json')
