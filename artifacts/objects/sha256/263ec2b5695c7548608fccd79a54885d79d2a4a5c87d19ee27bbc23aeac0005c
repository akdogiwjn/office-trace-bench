#!/usr/bin/env bash
# Render driver for SUB-MEM-PDF-SBA1919-01.
# One convert_pdf_to_images.py invocation per filled record (expected: 10).
# The blank template was rendered separately (total render invocations: 11).
set -euo pipefail
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SC="/root/.openclaw/skills/pdf/scripts"
IDS=$(python3 -c "import json,sys;print(' '.join(r['id'] for r in json.load(open('$WS/input/synthetic_applicants.json'))['applicants']))")
for id in $IDS; do
  echo "== render $id =="
  mkdir -p "$WS/output/rendered/$id"
  python3 "$SC/convert_pdf_to_images.py" \
    "$WS/output/filled/$id.pdf" \
    "$WS/output/rendered/$id"
done
