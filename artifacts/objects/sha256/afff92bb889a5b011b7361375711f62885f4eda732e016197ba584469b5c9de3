# Helper provenance - SUB-MEM-OFFICE-01

Deliverables are produced by a three-stage pipeline. Original worksheets are
never modified; the two new sheets (Executive_Dashboard, Charts) are appended.

## Live helpers
- `build_report.py`  - openpyxl: loads the input template, appends the dashboard
  (metrics, scenario selector + assumptions + projections, notes, conditional
  formatting, freeze panes, comments) and the Charts sheet (daily trips bar,
  payment-mix pie). Writes a base workbook with formulas but no caches.
- `inject_caches.py` - copies LibreOffice-computed cached values from a
  recalculated copy into the openpyxl base (rewrites only formula `<v>` elements
  and adds `t="str"` for text results). This keeps byte-level style preservation
  of the original sheets while delivering live cached formula results.
- `run_pipeline.py`  - orchestrates build -> recalc.py -> inject -> publish CSVs
  -> workbook_features.json.
- `compare_preservation.py` - mimics the verifier's preservation logic to detect
  style/format/value drift between two workbooks.

## Rewritten helper versions (distinct files kept)
- `history/inject_caches_v1.py` - initial version; sheet-path mapping bug
  (`xl/xl/...`). Fixed in `inject_caches.py`.
- `history/build_report_v1.py`  - initial version; projections header/label row
  collision. Fixed in `build_report.py`.

## Recalc
recalc.py is run with the manifest timeout (180s). Final `formula_recalc.json`
reports status=success, total_errors=0, total_formulas=43.
