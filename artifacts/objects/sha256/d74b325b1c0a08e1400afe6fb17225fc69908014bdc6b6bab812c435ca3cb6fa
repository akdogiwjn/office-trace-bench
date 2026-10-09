"""Build the enhanced retail workbook: add an Overview sheet with live formulas,
scenario selector, assumptions, projection, chart, formatting. Original sheets are
preserved by openpyxl; empty-string cells and recalculated caches are restored by a
separate XML patch step."""
import sys
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, FormulaRule
from openpyxl.chart import LineChart, Reference

SRC = '/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL/input/mrtssales92-present.xlsx'
BUILD = '/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL/work/build.xlsx'

GREEN = 'FF008000'   # cross-sheet formulas
BLUE = 'FF0000FF'    # editable inputs
FONT = 'Arial'

GREEN_FONT = Font(name=FONT, size=10, color=GREEN)
BLUE_FONT = Font(name=FONT, size=10, color=BLUE)
BLACK_FONT = Font(name=FONT, size=10)
BOLD = Font(name=FONT, size=10, bold=True)
TITLE = Font(name=FONT, size=12, bold=True)
HEADER_FILL = PatternFill('solid', fgColor='FFD9E1F2')
THIN = Side(style='thin', color='FFBFBFBF')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

RED_FILL = PatternFill('solid', fgColor='FFFFC7CE')
GRN_FILL = PatternFill('solid', fgColor='FFC6EFCE')


def build():
    wb = load_workbook(SRC)
    ws = wb.create_sheet('Overview')
    ws.sheet_view.showGridLines = False

    widths = {'A': 46, 'B': 18, 'C': 14, 'D': 14, 'E': 3, 'F': 12, 'G': 12}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    def put(ref, value, font=BLACK_FONT, numfmt=None, align=None, fill=None):
        c = ws[ref]
        c.value = value
        c.font = font
        if numfmt:
            c.number_format = numfmt
        if align:
            c.alignment = align
        if fill:
            c.fill = fill
        return c

    put('A1', 'Retail and Food Services \u2014 July 2026 Analysis', TITLE)
    put('A2', 'Live formulas linked to the Census MRTS source sheets in this workbook. '
              'Adjusted = seasonally adjusted (not price adjusted).')

    # ---- Key metrics ----
    put('A4', 'Key Metrics', BOLD)
    put('A5', 'Metric', BOLD, fill=HEADER_FILL)
    put('B5', 'Value', BOLD, fill=HEADER_FILL)
    put('C5', 'Unit', BOLD, fill=HEADER_FILL)
    put('A6', 'Adjusted retail and food services sales (Jul 2026)')
    put('B6', "='2026'!I72", GREEN_FONT, '#,##0')
    put('C6', 'USD million')
    put('A7', 'Month-over-month growth (Jun\u2192Jul 2026)')
    put('B7', "=('2026'!I72-'2026'!H72)/'2026'!H72", GREEN_FONT, '0.0%')
    put('C7', 'fraction')
    put('A8', 'Year-over-year growth (Jul 2025\u2192Jul 2026)')
    put('B8', "=('2026'!I72-'2025'!I72)/'2025'!I72", GREEN_FONT, '0.0%')
    put('C8', 'fraction')
    for r in (6, 7, 8):
        ws.cell(r, 1).border = BORDER
        ws.cell(r, 2).border = BORDER
        ws.cell(r, 3).border = BORDER

    # ---- Scenario ----
    put('A10', 'Scenario Analysis', BOLD)
    put('A11', 'Selected scenario')
    put('B11', 'Base', BLUE_FONT, align=Alignment(horizontal='left'))
    ws['B11'].border = BORDER

    put('A12', 'Scenario assumptions (editable inputs)', BOLD)
    put('A13', 'Scenario', BOLD, fill=HEADER_FILL)
    put('B13', 'sales_multiplier', BOLD, fill=HEADER_FILL)
    put('A14', 'Base')
    put('B14', 1, BLUE_FONT, '0.00')
    put('A15', 'Higher')
    put('B15', 1.04, BLUE_FONT, '0.00')
    put('A16', 'Lower')
    put('B16', 0.96, BLUE_FONT, '0.00')
    for r in (14, 15, 16):
        ws.cell(r, 1).border = BORDER
        ws.cell(r, 2).border = BORDER

    put('A18', 'Projection', BOLD)
    put('A19', 'Projected adjusted sales (USD million)')
    put('B19', '=$B$6*INDEX($B$14:$B$16,MATCH($B$11,$A$14:$A$16,0))', BLACK_FONT, '#,##0')
    ws['A19'].border = BORDER
    ws['B19'].border = BORDER

    # ---- Chart data block ----
    put('A21', 'Chart data: adjusted total retail & food services sales', BOLD)
    put('A22', 'Month', BOLD)
    put('B22', 'May 2026')
    put('C22', 'Jun 2026')
    put('D22', 'Jul 2026')
    put('A23', 'Adjusted sales (USD million)', BOLD)
    put('B23', "='2026'!G72", GREEN_FONT, '#,##0')
    put('C23', "='2026'!H72", GREEN_FONT, '#,##0')
    put('D23', "='2026'!I72", GREEN_FONT, '#,##0')
    for ref in ('B22', 'C22', 'D22', 'B23', 'C23', 'D23'):
        ws[ref].border = BORDER

    # ---- Data validation dropdown (scenario selector) ----
    dv = DataValidation(type='list', formula1='"Base,Higher,Lower"', allow_blank=False,
                        showDropDown=False, promptTitle='Scenario', prompt='Choose Base, Higher or Lower')
    ws.add_data_validation(dv)
    dv.add(ws['B11'])

    # ---- Conditional formatting (3 distinct ranges) ----
    ws.conditional_formatting.add('B7', CellIsRule(operator='lessThan', formula=['0'],
                                   fill=RED_FILL, font=Font(name=FONT, size=10, color='FF9C0006')))
    ws.conditional_formatting.add('B8', CellIsRule(operator='greaterThan', formula=['0'],
                                   fill=GRN_FILL, font=Font(name=FONT, size=10, color='FF006100')))
    ws.conditional_formatting.add('B23:D23', ColorScaleRule(
        start_type='min', start_color='FFF8696B',
        mid_type='percentile', mid_value=50, mid_color='FFFFEB84',
        end_type='max', end_color='FF63BE7B'))
    ws.conditional_formatting.add('B19', FormulaRule(formula=['$B$11="Base"'], fill=HEADER_FILL))

    # ---- Comments ----
    ws['B6'].comment = Comment(
        'Source: U.S. Census Bureau, Monthly Retail Trade Survey (MRTS) historical workbook '
        "(input file 'mrtssales92-present.xlsx'). '2026' sheet, ADJUSTED section, row 72 "
        "'Retail and food services sales, total', column I = Jul. 2026(p) = 729,538 USD million.", 'Analyst')
    ws['B14'].comment = Comment(
        'Editable assumption: hypothetical sales-level multiplier (Base = 1.00; Higher = 1.04; '
        'Lower = 0.96). These are NOT Census forecasts.', 'Analyst')
    ws['B19'].comment = Comment(
        'Projection = Adjusted July 2026 sales (B6) \u00d7 multiplier selected by the scenario '
        'dropdown (B11) from the assumption table B14:B16 via INDEX/MATCH.', 'Analyst')

    # ---- Freeze panes ----
    ws.freeze_panes = 'B3'

    # ---- Chart ----
    chart = LineChart()
    chart.title = 'Adjusted total retail & food services sales (May\u2013Jul 2026)'
    chart.y_axis.title = 'USD million'
    chart.x_axis.title = 'Month'
    chart.height = 8
    chart.width = 16
    data = Reference(ws, min_col=2, max_col=4, min_row=23, max_row=23)
    cats = Reference(ws, min_col=2, max_col=4, min_row=22, max_row=22)
    chart.add_data(data, titles_from_data=False, from_rows=True)
    chart.set_categories(cats)
    ws.add_chart(chart, 'F4')

    wb.save(BUILD)
    print('built', BUILD, 'sheets', len(wb.sheetnames), 'last', wb.sheetnames[-1])


if __name__ == '__main__':
    build()
