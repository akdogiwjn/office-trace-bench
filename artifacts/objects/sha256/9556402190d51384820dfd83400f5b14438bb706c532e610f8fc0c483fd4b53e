#!/usr/bin/env python3
"""Build the enhanced workbook: preserve originals, append an 'Overview' sheet
with formula-linked metrics, a scenario selector, projections and chart data."""
import json
import shutil
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'input' / 'text.xlsx'
BUILD = ROOT / 'build'
BUILD.mkdir(exist_ok=True)
BASE = BUILD / 'enhanced_base.xlsx'

ARIAL = 'Arial'
GREEN = Font(name=ARIAL, color='008000')            # cross-sheet formula
GREEN_B = Font(name=ARIAL, color='008000', bold=True)
BLUE = Font(name=ARIAL, color='0000FF')             # editable input
BLUE_B = Font(name=ARIAL, color='0000FF', bold=True)
BLACK = Font(name=ARIAL, color='000000')            # local formula
BLACK_B = Font(name=ARIAL, bold=True)
TITLE = Font(name=ARIAL, bold=True, size=14, color='000000')
SUB = Font(name=ARIAL, italic=True, size=9, color='595959')
HDR = Font(name=ARIAL, bold=True, color='FFFFFF')
HDRFILL = PatternFill('solid', start_color='1F4E78')
SEC = Font(name=ARIAL, bold=True, size=11, color='1F4E78')
SIDE = Side(style='thin', color='BFBFBF')
BOX = Border(left=SIDE, right=SIDE, top=SIDE, bottom=SIDE)


def build():
    wb = load_workbook(SRC)                       # preserves all originals
    ws = wb.create_sheet('Overview')

    ws['A1'] = "Manufacturers' Shipments Analysis \u2014 March 2025"
    ws['A1'].font = TITLE
    ws['A2'] = ("Source: U.S. Census Bureau, M3 Survey Benchmark Report (May 16, 2025). "
                "Values are published aggregate estimates, in USD millions. "
                "Suppression / missing markers in the source (e.g. '(X)') are retained unchanged.")
    ws['A2'].font = SUB
    ws.merge_cells('A2:E2')

    ws['A4'] = 'Key Metrics \u2014 March 2025 (seasonally adjusted)'
    ws['A4'].font = SEC
    headers = ['Metric', 'Value', 'Unit', 'Source (original cell)']
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=5, column=i, value=h)
        c.font = HDR
        c.fill = HDRFILL
        c.border = BOX
        c.alignment = Alignment(horizontal='center')

    # --- Metrics: cross-sheet formulas linked to Table 1 (green) ---
    ws['A6'] = 'Total shipments'
    ws['B6'] = "='Table 1'!C12"
    ws['C6'] = 'USD million'
    ws['D6'] = "'Table 1'!C12"
    ws['A7'] = 'Monthly change (Feb\u2192Mar)'
    ws['B7'] = "=('Table 1'!C12-'Table 1'!D12)/'Table 1'!D12"
    ws['C7'] = 'fraction'
    ws['D7'] = "'Table 1'!C12, D12"
    ws['A8'] = 'Durable goods share'
    ws['B8'] = "='Table 1'!C17/'Table 1'!C12"
    ws['C8'] = 'fraction'
    ws['D8'] = "'Table 1'!C17 / C12"
    ws['A9'] = 'Nondurable shipments'
    ws['B9'] = "='Table 1'!C72"
    ws['C9'] = 'USD million'
    ws['D9'] = "'Table 1'!C72"
    for r in range(6, 10):
        ws.cell(row=r, column=2).font = GREEN_B
        ws.cell(row=r, column=2).border = BOX
        for col in (1, 3, 4):
            ws.cell(row=r, column=col).border = BOX
    ws['B6'].number_format = '#,##0'
    ws['B7'].number_format = '0.0%'
    ws['B8'].number_format = '0.0%'
    ws['B9'].number_format = '#,##0'

    # --- Scenario analysis ---
    ws['A11'] = 'Scenario Analysis'
    ws['A11'].font = SEC
    ws['A12'] = 'Select scenario:'
    ws['B12'] = 'Base'                                     # selector (editable, blue)
    ws['B12'].font = BLUE_B
    ws['B12'].fill = PatternFill('solid', start_color='FFF2CC')
    ws['B12'].border = BOX
    dv = DataValidation(type='list', formula1='"Base,Expansion,Contraction"', allow_blank=False)
    dv.prompt = 'Choose a scenario (hypothetical, not an official forecast).'
    dv.promptTitle = 'Scenario'
    ws.add_data_validation(dv)
    dv.add(ws['B12'])

    ws['A13'] = 'Assumption: shipments multiplier (hypothetical; not an official forecast)'
    ws['A13'].font = SUB
    ws['A14'] = 'Scenario'
    ws['B14'] = 'shipments_multiplier'
    for addr in ('A14', 'B14'):
        ws[addr].font = HDR
        ws[addr].fill = HDRFILL
        ws[addr].border = BOX
        ws[addr].alignment = Alignment(horizontal='center')
    rows = [('Base', 1), ('Expansion', 1.03), ('Contraction', 0.97)]
    for i, (name, mult) in enumerate(rows):
        r = 15 + i
        ws.cell(row=r, column=1, value=name).border = BOX
        mc = ws.cell(row=r, column=2, value=mult)           # editable input (blue)
        mc.font = BLUE
        mc.number_format = '0.00'
        mc.border = BOX
        mc.fill = PatternFill('solid', start_color='FFF2CC')

    ws['A18'] = 'Projected shipments (selected scenario)'
    ws['A18'].font = BLACK_B
    ws['B18'] = '=B6*VLOOKUP($B$12,$A$15:$B$17,2,FALSE)'    # local formula (black)
    ws['B18'].font = BLACK
    ws['B18'].number_format = '#,##0'
    ws['B18'].border = BOX
    ws['C18'] = 'USD million'
    ws['C18'].font = BLACK

    # --- Chart data blocks (formula-linked to source, green) ---
    ws['A20'] = 'Chart data (formula-linked to Table 1)'
    ws['A20'].font = SEC
    ws['A21'] = 'Category'
    ws['B21'] = 'March 2025 shipments (USD million)'
    ws['A22'] = 'Durable goods'
    ws['B22'] = "='Table 1'!C17"
    ws['A23'] = 'Nondurable goods'
    ws['B23'] = "='Table 1'!C72"
    ws['A25'] = 'Month'
    ws['B25'] = 'All-manufacturing shipments (USD million)'
    ws['A26'] = 'January 2025'
    ws['B26'] = "='Table 1'!E12"
    ws['A27'] = 'February 2025'
    ws['B27'] = "='Table 1'!D12"
    ws['A28'] = 'March 2025'
    ws['B28'] = "='Table 1'!C12"
    for addr in ('A21', 'B21', 'A25', 'B25'):
        ws[addr].font = BLACK_B
        ws[addr].border = BOX
    for r in (22, 23, 26, 27, 28):
        ws.cell(row=r, column=1).border = BOX
        cc = ws.cell(row=r, column=2)
        cc.font = GREEN                                  # cross-sheet formula (green)
        cc.number_format = '#,##0'
        cc.border = BOX

    # --- Comments (source / assumption documentation) ---
    ws['B6'].comment = Comment(
        "Total March 2025 seasonally adjusted shipments for all manufacturing industries.\n"
        "Source: Table 1, cell C12 (U.S. Census Bureau, M3 Survey Benchmark Report, May 16, 2025).\n"
        "Do not sum overlapping industry-hierarchy rows; use the published aggregate.", "Analyst")
    ws['B12'].comment = Comment(
        "Editable scenario selector (data-validation dropdown). Default = 'Base'.\n"
        "Scenarios are hypothetical multipliers and are NOT an official forecast.", "Analyst")
    ws['B15'].comment = Comment(
        "Editable assumption: shipments multiplier by scenario.\n"
        "Base=1.00, Expansion=1.03, Contraction=0.97 (hypothetical).", "Analyst")

    # --- Conditional formatting (>=2 rules) ---
    ws.conditional_formatting.add('B7', CellIsRule(
        operator='lessThan', formula=['0'],
        font=Font(name=ARIAL, color='9C0006'),
        fill=PatternFill('solid', start_color='FFC7CE')))
    ws.conditional_formatting.add('B6:B9', ColorScaleRule(
        start_type='min', start_color='FFFFFF', end_type='max', end_color='63BE7B'))
    ws.conditional_formatting.add('B22:B23', DataBarRule(
        start_type='num', start_value=0, end_type='max', color='638EC6'))
    ws.conditional_formatting.add('B26:B28', DataBarRule(
        start_type='num', start_value=0, end_type='max', color='A9D08E'))

    # --- Charts (durability_mix index 0, shipment_trend index 1) ---
    ch1 = BarChart()
    ch1.type = 'col'
    ch1.title = 'March 2025 Seasonally Adjusted Shipments: Durable vs Nondurable'
    ch1.y_axis.title = 'USD million'
    ch1.x_axis.title = 'Goods category'
    data1 = Reference(ws, min_col=2, min_row=22, max_row=23)
    cats1 = Reference(ws, min_col=1, min_row=22, max_row=23)
    ch1.add_data(data1, titles_from_data=False)
    ch1.set_categories(cats1)
    ch1.series[0].tx = None
    ch1.height = 8
    ch1.width = 15
    ws.add_chart(ch1, 'D11')

    ch2 = LineChart()
    ch2.title = 'All-Manufacturing Shipments, Jan\u2013Mar 2025 (Seasonally Adjusted)'
    ch2.y_axis.title = 'USD million'
    ch2.x_axis.title = 'Month'
    data2 = Reference(ws, min_col=2, min_row=26, max_row=28)
    cats2 = Reference(ws, min_col=1, min_row=26, max_row=28)
    ch2.add_data(data2, titles_from_data=False)
    ch2.set_categories(cats2)
    ch2.series[0].tx = None
    ch2.series[0].graphicalProperties.line.width = 20000
    ch2.height = 8
    ch2.width = 15
    ws.add_chart(ch2, 'D27')

    # --- Formatting / panes / widths ---
    ws.freeze_panes = 'A5'
    ws.column_dimensions['A'].width = 34
    ws.column_dimensions['B'].width = 24
    ws.column_dimensions['C'].width = 14
    ws.column_dimensions['D'].width = 22
    ws.column_dimensions['E'].width = 14

    wb.save(BASE)
    print(json.dumps({'built': str(BASE), 'sheets': wb.sheetnames}))


if __name__ == '__main__':
    build()
