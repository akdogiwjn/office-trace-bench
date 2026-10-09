#!/usr/bin/env bash
# Fill driver for SUB-MEM-PDF-SBA1919-01.
# One fill_fillable_fields.py invocation per supplied record (expected: 10).
set -euo pipefail
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SC="/root/.openclaw/skills/pdf/scripts"
IDS=$(python3 -c "import json,sys;print(' '.join(r['id'] for r in json.load(open('$WS/input/synthetic_applicants.json'))['applicants']))")
mkdir -p "$WS/output/filled"
for id in $IDS; do
  echo "== fill $id =="
  python3 "$SC/fill_fillable_fields.py" \
    "$WS/input/sba1919_2024.pdf" \
    "$WS/output/field_values/$id.json" \
    "$WS/output/filled/$id.pdf"
done
