#!/usr/bin/env python3
"""Build the enhanced TLC monthly operations report (base workbook, no caches yet).

HISTORY: v1 - projections section had a stray label/header collision at row 19.
Corrected in the live helper (projects header on row 20, values on rows 21-22).

Adds two sheets: Executive_Dashboard and Charts. Original sheets are never touched.
"""
import sys
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.comments import Comment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, DataBarRule

IN = sys.argv[1] if len(sys.argv) > 1 else 'input/monthly_operations_template.xlsx'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/tmp/report_base.xlsx'

wb = load_workbook(IN)

ARIAL = 'Arial'
GREEN = Font(name=ARIAL, color='FF008000')
BLUE = Font(name=ARIAL, color='FF0000FF')
TITLE = Font(name=ARIAL, size=14, bold=True, color='FF1F3864')
SUB = Font(name=ARIAL, size=9, italic=True, color='FF595959')
SECTION = Font(name=ARIAL, size=11, bold=True, color='FFFFFFFF')
SECFILL = PatternFill('solid', fgColor='FF2F5496')
LABEL = Font(name=ARIAL, bold=True)
HDR = Font(name=ARIAL, bold=True, color='FFFFFFFF')
HDRFILL = PatternFill('solid', fgColor='FF8EAADB')
thin = Side(style='thin', color='FFBFBFBF')
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

dash = wb.create_sheet('Executive_Dashboard')
dash.sheet_view.showGridLines = False

def sec(row, text, span=3):
    c = dash.cell(row=row, column=1, value=text)
    c.font = SECTION
    c.fill = SECFILL
    c.alignment = Alignment(horizontal='left', vertical='center')
    for col in range(2, span + 1):
        dash.cell(row=row, column=col).fill = SECFILL
    return c

dash['A1'] = 'NYC TLC - January 2024 Operations Dashboard'
dash['A1'].font = TITLE
dash['A2'] = 'Full-population estimates from monthly_operations_template.xlsx (source data preserved unchanged).'
dash['A2'].font = SUB

# ---------------- Metrics ----------------
sec(4, 'Full-Population Metrics', 3)
for col, h in enumerate(['Metric', 'Value', 'Unit'], start=1):
    c = dash.cell(row=5, column=col, value=h)
    c.font = HDR; c.fill = HDRFILL; c.border = BORDER
    c.alignment = Alignment(horizontal='center')

metrics = [
    ('Total trips', '=Hourly_Summary!B29', '#,##0', 'trips',
     'Source: Hourly_Summary!B29 (SUM of hourly full-population trip counts).'),
    ('Fare revenue', '=Hourly_Summary!B32', '$#,##0', 'USD',
     'Source: Hourly_Summary!B32 (SUM of hourly full-population fare revenue).'),
    ('Average fare', '=Hourly_Summary!B34', '$#,##0.00', 'USD per trip',
     'Source: Hourly_Summary!B34 (overall average fare from population summaries).'),
    ('Removal rate', '=Reconciliation!B4/Reconciliation!B2', '0.0%', 'fraction',
     'Source: Reconciliation!B4 / Reconciliation!B2 (records removed / raw records).'),
    ('Reconciliation status',
     '=IF(AND(Reconciliation!B24="YES - Consistent",Reconciliation!B25="YES - Consistent"),"PASS","REVIEW")',
     'General', 'text',
     'Source: Reconciliation!B24 and B25; PASS only when both checks are consistent.'),
]
METRIC_CELL = {}
for i, (name, formula, numfmt, unit, note) in enumerate(metrics):
    r = 6 + i
    dash.cell(row=r, column=1, value=name).font = LABEL
    vc = dash.cell(row=r, column=2, value=formula)
    vc.font = GREEN
    vc.number_format = numfmt
    vc.border = BORDER
    vc.alignment = Alignment(horizontal='right')
    dash.cell(row=r, column=3, value=unit).font = Font(name=ARIAL, italic=True)
    vc.comment = Comment(note, 'Spreadsheet Agent')
METRIC_CELL['total_trips'] = 'B6'
METRIC_CELL['fare_revenue'] = 'B7'
METRIC_CELL['average_fare'] = 'B8'
METRIC_CELL['removal_rate'] = 'B9'
METRIC_CELL['reconciliation_status'] = 'B10'

# ---------------- Scenario ----------------
sec(12, 'Scenario Analysis', 3)
dash.cell(row=13, column=1, value='Selected scenario').font = LABEL
sel = dash.cell(row=13, column=2, value='Base')
sel.font = BLUE
sel.fill = PatternFill('solid', fgColor='FFFFF2CC')
sel.border = BORDER
sel.alignment = Alignment(horizontal='center')
sel.comment = Comment('Editable scenario selector. Dropdown: Base / Upside / Downside. '
                      'Drives the projections below via INDEX/MATCH.', 'Spreadsheet Agent')

for col, h in enumerate(['Scenario', 'Fare multiplier', 'Trip multiplier'], start=1):
    c = dash.cell(row=14, column=col, value=h)
    c.font = HDR; c.fill = HDRFILL; c.border = BORDER
    c.alignment = Alignment(horizontal='center')

assumptions = [('Base', 1.0, 1.0), ('Upside', 1.08, 1.05), ('Downside', 0.93, 0.95)]
ASSUMP_CELL = {}
for i, (nm, fm, tm) in enumerate(assumptions):
    r = 15 + i
    dash.cell(row=r, column=1, value=nm).font = LABEL
    for col, val in ((2, fm), (3, tm)):
        c = dash.cell(row=r, column=col, value=val)
        c.font = BLUE
        c.number_format = '0.00'
        c.border = BORDER
        c.alignment = Alignment(horizontal='center')

dv = DataValidation(type='list', formula1='"Base,Upside,Downside"', allow_blank=False,
                    showDropDown=False)
dv.error = 'Choose Base, Upside or Downside.'
dv.prompt = 'Select a scenario'
dash.add_data_validation(dv)
dv.add(sel)

sec(19, 'Projections (formula-driven by selected scenario)', 3)
for col, h in enumerate(['Projection', 'Value', 'Unit'], start=1):
    c = dash.cell(row=20, column=col, value=h)
    c.font = HDR; c.fill = HDRFILL; c.border = BORDER
    c.alignment = Alignment(horizontal='center')

proj_trips = ("=Hourly_Summary!B29*INDEX($C$15:$C$17,MATCH($B$13,$A$15:$A$17,0))")
proj_fare = ("=Hourly_Summary!B32*INDEX($B$15:$B$17,MATCH($B$13,$A$15:$A$17,0))"
             "*INDEX($C$15:$C$17,MATCH($B$13,$A$15:$A$17,0))")
projs = [('Projected trips', proj_trips, '#,##0', 'trips'),
         ('Projected fare', proj_fare, '$#,##0', 'USD')]
PROJ_CELL = {}
for i, (nm, formula, numfmt, unit) in enumerate(projs):
    r = 21 + i
    dash.cell(row=r, column=1, value=nm).font = LABEL
    c = dash.cell(row=r, column=2, value=formula)
    c.font = GREEN; c.number_format = numfmt; c.border = BORDER
    c.alignment = Alignment(horizontal='right')
    c.comment = Comment('Population value scaled by the selected scenario multipliers '
                        '(INDEX/MATCH on the assumption table).', 'Spreadsheet Agent')
    dash.cell(row=r, column=3, value=unit).font = Font(name=ARIAL, italic=True)
PROJ_CELL['projected_trips'] = 'B21'
PROJ_CELL['projected_fare'] = 'B22'

# ---------------- Notes ----------------
dash.cell(row=25, column=1, value='Notes').font = Font(name=ARIAL, bold=True)
notes = [
    'Published aggregates (full population) are kept separate from the 100,000-row Raw_Sample.',
    'Original worksheets, formulas, charts, formats and suppression/missing markers are preserved.',
    'Blue cells are editable inputs; green cells pull from other worksheets.',
]
for i, t in enumerate(notes):
    c = dash.cell(row=26 + i, column=1, value='- ' + t)
    c.font = Font(name=ARIAL, size=9, color='FF595959')

# Conditional formatting (>= 2 rules)
dash.conditional_formatting.add('B10', CellIsRule(
    operator='equal', formula=['"PASS"'], fill=PatternFill('solid', fgColor='FFC6EFCE'),
    font=Font(name=ARIAL, color='FF006100')))
dash.conditional_formatting.add('B10', CellIsRule(
    operator='equal', formula=['"REVIEW"'], fill=PatternFill('solid', fgColor='FFFFC7CE'),
    font=Font(name=ARIAL, color='FF9C0006')))
dash.conditional_formatting.add('B9', CellIsRule(
    operator='greaterThan', formula=['0.05'], fill=PatternFill('solid', fgColor='FFFFEB9C')))
dash.conditional_formatting.add('B21:B22', DataBarRule(start_type='min', end_type='max',
                                                       color='FF638EC6'))

widths = {'A': 26, 'B': 20, 'C': 14}
for k, v in widths.items():
    dash.column_dimensions[k].width = v
dash.freeze_panes = 'A6'

# ---------------- Charts ----------------
ch = wb.create_sheet('Charts')
daily = wb['Daily_Summary']
pay = wb['Payment_Summary']

bar = BarChart()
bar.type = 'col'
bar.title = 'Daily Full-Population Trips - Jan 2024'
bar.y_axis.title = 'Trips'
bar.x_axis.title = 'Date'
bar.add_data(Reference(daily, min_col=3, min_row=1, max_row=32), titles_from_data=True)
bar.set_categories(Reference(daily, min_col=1, min_row=2, max_row=32))
bar.height = 9; bar.width = 26
ch.add_chart(bar, 'A1')

pie = PieChart()
pie.title = 'Payment-Method Mix - Jan 2024 (trips)'
pie.add_data(Reference(pay, min_col=2, min_row=1, max_row=5), titles_from_data=True)
pie.set_categories(Reference(pay, min_col=1, min_row=2, max_row=5))
pie.height = 9; pie.width = 16
ch.add_chart(pie, 'A22')

wb.save(OUT)
print('base written', OUT, 'sheets:', wb.sheetnames)
