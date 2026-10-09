# Helper execution log (OFFICE-XLSX-HR)

All helpers and intermediate artifacts kept under `helpers/` (and `helpers/revisions/`).

## Helper files
| file | purpose | attempts | outcome |
|------|---------|----------|---------|
| `build.py` (== `revisions/build_final.py`) | Load source workbook, add `OEWS Summary` + `Chart Data`, emit `workbook_features.json`, save `pre_recalc.xlsx` | 2 | both success (2nd run regenerated the clean pre-build after LibreOffice overwrote it during recalc) |
| `revisions/patch_v1_initial.py` | First cache-injection/assembly attempt | 1 | FAILED — `KeyError: 'rId1'` (relationship attr order) |
| `revisions/patch_v2_relsfix.py` | Fixed relationship parser | 1 | produced a file, but INVALID — string-valued INDEX caches written without `t="str"` (openpyxl could not re-read) |
| `patch.py` (== `revisions/patch_v3_final.py`) | Final assembly: inject numeric+string caches with correct cell typing, restore dropped empty-string cells | 1 | success |
| (skill) `scripts/recalc.py` | LibreOffice recalculation | 2 | success (diagnostic probe on a copy; then the real pre-build) |

## Intermediate artifacts
- `recalc_probe.xlsx` — diagnostic: raw source round-tripped through LibreOffice to measure preservation drift.
- `openpyxl_rt.xlsx` — diagnostic: raw source round-tripped through openpyxl only.
- `pre_recalc.xlsx` — clean openpyxl build (formulas, no caches).
- `rec_recalc.xlsx` — LibreOffice-recalculated build; source of the cached values.
- `recalc_out.json` / `recalc_err.txt` — stdout/stderr of the real recalc invocation (stdout also copied to `output/formula_recalc.json`).

## Preservation notes
- openpyxl's save drops the 2714 empty-string cells in `national_M2025_dl` columns AE/AF; `patch.py` re-inserts them as `<is><t></t></is>` while keeping their original style index, so `source:data` and `source:styles` both hold.
- The delivered workbook is the clean openpyxl build with LibreOffice-computed caches injected at the XML level, so original formatting/styles are byte-faithful while added-sheet formulas carry recalculated values.
