#!/usr/bin/env python3
"""Audit a new run and check its outputs against the original baseline verifier."""
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import read_json, sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    info = read_json(run / 'run_manifest.json')
    if info['status'] != 'success' or info.get('baseline_accepted') is False:
        raise SystemExit('only successful, non-excluded runs can be accepted')
    snapshot_info = read_json(run / 'source_snapshot.json')
    snapshot = Path(info.get('source_snapshot_path', run / 'project_snapshot'))
    unchanged = snapshot.is_dir() and {str(p.relative_to(snapshot)): sha256(p)
        for p in snapshot.rglob('*') if p.is_file()} == snapshot_info['files']
    events = read_json(run / 'tool_events.json')['events']
    historical = [event['step_id'] for event in events if '/legacy/' in json.dumps(event['tool_call']['arguments'])
                  or '/openclaw-trace-bench/cases/' in json.dumps(event['tool_call']['arguments'])]
    verifier_called = any(event['operation'] == 'verify_business' for event in events)
    agent_report = read_json(run / 'workspace/output/business_verification.json')
    independent = read_json(run / 'independent_verification.json')
    workspace = run / 'workspace'
    frozen_manifest = read_json(workspace / 'input/dataset_manifest.json')
    context_required = bool(frozen_manifest.get('agent_context'))
    context_audit = read_json(run / 'agent_context_audit.json') if (run / 'agent_context_audit.json').is_file() else {}
    context_ok = not context_required
    if context_required:
        profile = read_json(snapshot / 'runtime_context/profiles' /
                            frozen_manifest['agent_context']['profile'] / 'profile.json')
        expected = {Path(name).name: digest for name, digest in profile['files'].items()
                    if name.startswith('workspace/')}
        context_ok = bool(info.get('agent_context_matched') and context_audit.get('matched') and
                          context_audit.get('background_hashes_before') == context_audit.get('background_hashes_after') == expected)
    kind = info['kind']
    target = run / 'legacy_verification.json'
    if kind == 'xlsx' and info['dataset_id'] == 'tlc':
        command_args = ['legacy/xlsx/verify_xlsx_enhanced.py', str(workspace / 'output/monthly_operations_report.xlsx'),
                        str(workspace / 'output/formula_recalc.json'), str(target)]
    elif kind == 'pdf' and info['dataset_id'] == 'opm':
        command_args = ['legacy/pdf/verify_pdf_batch.py', str(workspace / 'input/of306_aug2023.pdf'),
                        str(workspace / 'input/synthetic_applicants.json'), str(workspace / 'output'), str(target)]
    else:
        command_args = None
    code = 'import sys,runpy;import office;sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name="__main__")'
    if command_args:
        result = subprocess.run([sys.executable, '-c', code, *command_args], cwd=ROOT, capture_output=True, text=True)
        legacy = read_json(target) if target.exists() else {'status': 'error', 'failures': [result.stderr[-1000:]]}
        legacy_ok = result.returncode == 0 and legacy.get('status') == 'success' and not legacy.get('failures')
    else:
        legacy = {'status': 'not_applicable', 'reason': 'New dataset has no historical verifier; frozen manifest/expected provide acceptance.', 'failures': []}
        write_json(target, legacy)
        legacy_ok = True
    accepted = (unchanged and not historical and verifier_called and context_ok and legacy_ok
                and all(r.get('status') == 'success' and not r.get('failures') for r in (agent_report, independent)))
    audit = {'source_snapshot_unchanged': unchanged, 'historical_artifact_reference_steps': historical,
             'verifier_called_in_trace': verifier_called, 'agent_verifier': agent_report['status'],
             'independent_verifier': independent['status'], 'legacy_verifier': legacy['status'],
             'context_required': context_required, 'context_accepted': context_ok,
             'legacy_failures': legacy.get('failures')}
    audit['scope'] = 'legacy-compatible business regression' if command_args else 'new-dataset manifest/expected acceptance; no historical comparator'
    info['baseline_accepted'] = accepted
    info['baseline_acceptance_audit'] = audit
    write_json(run / 'run_manifest.json', info)
    write_json(run / 'baseline_acceptance.json', {'accepted': accepted, 'audit': audit})
    print(json.dumps({'run_id': info['run_id'], 'accepted': accepted, 'audit': audit}, ensure_ascii=False))
    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
