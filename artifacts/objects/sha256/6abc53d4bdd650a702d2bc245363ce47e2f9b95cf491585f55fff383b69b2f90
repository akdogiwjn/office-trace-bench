#!/usr/bin/env bash
# End-to-end pipeline: build -> recalc -> assemble.
# Records every invocation in work/pipeline_log.jsonl
set -u
BASE=/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-RETAIL
LOG=$BASE/work/pipeline_log.jsonl
mkdir -p "$BASE/work" "$BASE/output"

log() { printf '%s\n' "$1" >> "$LOG"; }

# 1) build
if python3 "$BASE/helpers/build_enhance.py"; then
  log "{\"step\":\"build\",\"helper\":\"build_enhance.py\",\"status\":\"ok\"}"
else
  log "{\"step\":\"build\",\"helper\":\"build_enhance.py\",\"status\":\"fail\"}"; exit 1
fi

cp "$BASE/work/build.xlsx" "$BASE/work/recalc_input.xlsx"

# 2) recalculate with the Skill's bundled LibreOffice bridge
cd /root/.openclaw/skills/xlsx/scripts
if timeout 220 python3 recalc.py "$BASE/work/recalc_input.xlsx" 180 > "$BASE/output/formula_recalc.json" 2> "$BASE/work/recalc_stderr.txt"; then
  log "{\"step\":\"recalc\",\"helper\":\"recalc.py\",\"status\":\"ok\"}"
else
  log "{\"step\":\"recalc\",\"helper\":\"recalc.py\",\"status\":\"fail\"}"; exit 1
fi

# 3) assemble final workbook (restore empty cells + inject caches)
cd "$BASE"
if python3 "$BASE/helpers/assemble_output.py"; then
  log "{\"step\":\"assemble\",\"helper\":\"assemble_output.py\",\"status\":\"ok\"}"
else
  log "{\"step\":\"assemble\",\"helper\":\"assemble_output.py\",\"status\":\"fail\"}"; exit 1
fi
echo "pipeline complete"
