#!/usr/bin/env python3
"""End-to-end build for the TLC enhanced report.

1. openpyxl build (original sheets preserved, two new sheets added)
2. recalc.py on a copy -> output/formula_recalc.json (JSON stdout)
3. inject cached values into the openpyxl build -> output/monthly_operations_report.xlsx
4. publish reference CSVs
5. write output/workbook_features.json
"""
import json, os, subprocess, sys, shutil
from pathlib import Path

WS = Path('/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01')
IN = WS / 'input/monthly_operations_template.xlsx'
OUT = WS / 'output'
SKILL = Path('/root/.openclaw/skills/xlsx/scripts')
OUT.mkdir(exist_ok=True)
BASE = Path('/tmp/report_base.xlsx')
RECALC = Path('/tmp/report_recalc.xlsx')

# 1. build
r = subprocess.run([sys.executable, str(WS / 'helpers/build_report.py'), str(IN), str(BASE)],
                   capture_output=True, text=True)
print('build rc', r.returncode, r.stdout.strip(), r.stderr.strip())

# 2. recalc
shutil.copyfile(BASE, RECALC)
r = subprocess.run([sys.executable, str(SKILL / 'recalc.py'), str(RECALC), '180'],
                   capture_output=True, text=True, cwd=str(SKILL))
json_text = r.stdout.strip()
(OUT / 'formula_recalc.json').write_text(json_text + '\n')
print('recalc rc', r.returncode, json_text.replace('\n', ' '))

# 3. inject
r = subprocess.run([sys.executable, str(WS / 'helpers/inject_caches.py'), str(BASE), str(RECALC),
                    str(OUT / 'monthly_operations_report.xlsx')], capture_output=True, text=True)
print('inject rc', r.returncode, r.stdout.strip(), r.stderr.strip())

# 4. publish reference files
for item in json.loads((WS / 'input/dataset_manifest.json').read_text())['publish_files']:
    src = WS / 'input' / item['input']
    shutil.copyfile(src, OUT / item['output'])
print('published:', [i['output'] for i in json.loads((WS / 'input/dataset_manifest.json').read_text())['publish_files']])

# 5. workbook_features.json
S = 'Executive_Dashboard'
features = {
    "summary_sheet": S,
    "metrics": {
        "total_trips": {"sheet": S, "cell": "B6"},
        "fare_revenue": {"sheet": S, "cell": "B7"},
        "average_fare": {"sheet": S, "cell": "B8"},
        "removal_rate": {"sheet": S, "cell": "B9"},
        "reconciliation_status": {"sheet": S, "cell": "B10"},
    },
    "scenario": {
        "selector": {"sheet": S, "cell": "B13"},
        "assumptions": {
            "Base": {"fare_multiplier": {"sheet": S, "cell": "B15"}, "trip_multiplier": {"sheet": S, "cell": "C15"}},
            "Upside": {"fare_multiplier": {"sheet": S, "cell": "B16"}, "trip_multiplier": {"sheet": S, "cell": "C16"}},
            "Downside": {"fare_multiplier": {"sheet": S, "cell": "B17"}, "trip_multiplier": {"sheet": S, "cell": "C17"}},
        },
        "projections": {
            "projected_trips": {"sheet": S, "cell": "B21"},
            "projected_fare": {"sheet": S, "cell": "B22"},
        },
    },
    "charts": {
        "daily_trips": {"sheet": "Charts", "index": 0},
        "payment_mix": {"sheet": "Charts", "index": 1},
    },
}
(OUT / 'workbook_features.json').write_text(json.dumps(features, indent=2) + '\n')
print('features written')
