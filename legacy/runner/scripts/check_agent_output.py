#!/usr/bin/env python3
"""Fail unless the model-created business verification reports success."""

from __future__ import annotations

import json
import sys
from pathlib import Path

case_kind = sys.argv[1]
output = Path(sys.argv[2])
required = {
    "xlsx": [
        "monthly_operations_report.xlsx",
        "monthly_operations_summary.csv",
        "reconciliation_summary.csv",
        "formula_recalc.json",
        "business_verification.json",
        "xlsx_enhancement_summary.json",
    ],
    "pdf": [
        "form_field_info.json",
        "batch_summary.json",
        "business_verification.json",
    ],
}[case_kind]
missing = [name for name in required if not (output / name).is_file()]
if missing:
    raise SystemExit(f"missing required outputs: {missing}")
report = json.loads((output / "business_verification.json").read_text())
if report.get("status") != "success":
    raise SystemExit(
        f"business verification failed: {report.get('failures', ['unknown'])}"
    )
print(f"{case_kind}: model-created outputs verified successfully")

