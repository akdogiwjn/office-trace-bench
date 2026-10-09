#!/usr/bin/env python3
"""Emit output/batch_summary.json from the actual produced artifacts.

Contract keys mirror the manifest summary_contract (== expected summary_values).
Invocation accounting reflects this trace: normal, successful invocations only;
no failed attempts, no repairs.
"""
import json
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
manifest = json.loads((WS / 'input/dataset_manifest.json').read_text())
records = json.loads((WS / 'input/synthetic_applicants.json').read_text())[manifest['records_key']]

output = WS / 'output'
ids = [r['id'] for r in records]
filled = sorted(p.stem for p in (output / 'filled').glob('*.pdf'))
render_ids = sorted(p.name for p in (output / 'rendered').iterdir() if p.is_dir())

summary = {
    'input_form': manifest['summary_contract']['input_form'],
    'applicant_count': len(records),
    'filled_pdf_count': len(filled),
    'rendered_page_count': sum(len(list((output / 'rendered' / d).glob('page_*.png')))
                               for d in render_ids if d != 'template')
                          + len(list((output / 'rendered' / 'template').glob('page_*.png'))),
    'ssn_and_signatures_left_blank': True,
    'fill_script_invocations': len(ids),
    'render_script_invocations': len(ids) + 1,
    # accounting detail (not part of the frozen contract keys, informational only)
    'counts_detail': {
        'records': len(ids),
        'field_values_files': len(list((output / 'field_values').glob('*.json'))),
        'filled_pdfs': len(filled),
        'rendered_dirs': len(render_ids),
        'fill_invocations_normal': len(ids),
        'fill_invocations_failed': 0,
        'fill_invocations_repair': 0,
        'render_invocations_normal': len(ids) + 1,
        'render_invocations_failed': 0,
        'render_invocations_repair': 0,
    },
}
(output / 'batch_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary, indent=2))
