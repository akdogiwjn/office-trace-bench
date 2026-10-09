#!/usr/bin/env python3
"""Run the unmodified old/new entry points in the same experimental snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import office
from office_trace_bench.contracts import dataset_path, load_manifest, read_json, sha256, write_json
from office_trace_bench.context import audit_context, background_hashes, load_profile
from office_trace_bench.runner import capture_session, container_run, run_logged, sync_config
from office_trace_bench.trace import export_trace
from office_trace_bench.verify import verify


def freeze(source, destination, public_report):
    """Store credentials only in a private ephemeral Docker volume."""
    sync_config(source, destination)
    path, profile = load_profile(load_manifest(dataset_path('xlsx', 'tlc')))
    workspace = destination / 'workspace'
    workspace.mkdir()
    for relative in profile['files']:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path.parent / relative, target)
    config_path = destination / 'openclaw.json'
    config = read_json(config_path)
    config.setdefault('agents', {}).setdefault('defaults', {})['model'] = 'deepseek/deepseek-v4-flash'
    write_json(config_path, config)
    files = {str(p.relative_to(destination)): sha256(p)
             for p in destination.rglob('*') if p.is_file()}
    tree_hash = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    write_json(public_report, dict(files=files, tree_sha256=tree_hash,
        requested_model='deepseek/deepseek-v4-flash', credentials_in_project=False,
        scope='Current config frozen once for both variants; historical config identity is not claimed.'))
    destination.chmod(0o700)


def old_run(manifest, run, case_id):
    started = time.monotonic()
    code = run_logged(['bash', str(PROJECT / 'scripts/run_agent_case.sh'), case_id, manifest['kind']],
                      run, 'old_runner', cwd=PROJECT, timeout=3900)
    case = PROJECT / 'cases' / manifest['kind']
    agent = case / 'agent_run'
    for p in agent.glob('*'):
        if p.is_file():
            target = run / p.name
            if p.name == 'openclaw_agent.stdout.json':
                target = run / 'openclaw_agent.stdout.log'
            elif p.name == 'openclaw_agent.stderr.log':
                target = run / 'openclaw_agent.stderr.log'
            shutil.copy2(p, target)
    runtime = Path('/root/.openclaw/workspace/tool-modeling') / case_id
    if runtime.exists():
        shutil.copytree(runtime, run / 'workspace')
    info = dict(schema_version='office-run-v1', execution='real-openclaw-agent',
                kind=manifest['kind'], dataset_id=manifest['dataset_id'], status='failed',
                runner_exit_code=code, input_hashes=manifest['input_files'])
    if (run / 'openclaw_agent.stdout.log').is_file():
        capture_session(run / 'openclaw_agent.stdout.log', Path('/root/.openclaw/agents'), run / 'openclaw_session.jsonl')
        version = subprocess.run(['openclaw', '--version'], capture_output=True, text=True, check=True).stdout.strip().splitlines()[0]
        info['trace'] = export_trace(run / 'openclaw_session.jsonl', run / 'trajectory.json', manifest, version, 'control')
        _, profile = load_profile(manifest)
        before = read_json(run / 'pre_agent_state.json')['background_hashes']
        audit = audit_context(manifest, profile, run / 'openclaw_agent.stdout.log', before,
                              background_hashes('/root/.openclaw'))
        write_json(run / 'agent_context_audit.json', audit)
        info['agent_context_matched'] = audit['matched']
        report = verify(dataset_path(manifest['kind'], manifest['dataset_id']), run / 'workspace',
                        run / 'independent_verification.json')
        agent_report = read_json(run / 'workspace/output/business_verification.json')
        info['business_status'] = report['status']
        info['agent_business_status'] = agent_report.get('status')
        info['verifier_called_in_trace'] = any(e['operation'] == 'verify_business'
            for e in read_json(run / 'tool_events.json')['events'])
        info['status'] = 'success' if (code == 0 and audit['matched'] and report['status'] == 'success'
            and agent_report.get('status') == 'success' and not agent_report.get('failures')
            and info['verifier_called_in_trace']) else 'failed'
        if (run / 'task_window.json').is_file():
            info['agent_seconds'] = read_json(run / 'task_window.json')['duration_seconds']
    info['elapsed_seconds'] = round(time.monotonic() - started, 3)
    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--kind', choices=['xlsx', 'pdf'], default='xlsx')
    parser.add_argument('--variant', choices=['old', 'new'])
    parser.add_argument('--run-id')
    args = parser.parse_args()
    if args.freeze:
        freeze(Path('/host-openclaw'), Path('/frozen-openclaw'), Path('/public/config_fingerprint.json'))
        print('configuration frozen; no credential values emitted', flush=True)
        return 0
    dataset = {'xlsx': 'tlc', 'pdf': 'opm'}[args.kind]
    manifest = load_manifest(dataset_path(args.kind, dataset))
    run = Path('/runs/control')
    tools = {}
    for name, command in [('openclaw', ['openclaw', '--version']), ('node', ['node', '--version']),
                          ('python', ['python3', '--version']), ('libreoffice', ['soffice', '--version']),
                          ('poppler', ['pdftoppm', '-v'])]:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        tools[name] = (result.stdout or result.stderr).strip().splitlines()[0]
    info = {}
    try:
        if args.variant == 'old':
            info = old_run(manifest, run, manifest['runtime_case'])
        else:
            container_run(args.kind, dataset, run, 3600, '/host-openclaw')
            info = read_json(run / 'run_manifest.json')
        if (run / 'actual_task.prompt').is_file():
            shutil.copy2(run / 'actual_task.prompt', run / 'task.prompt')
    except Exception as exc:
        info.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    finally:
        info.update(run_id=args.run_id, internal_run_id='control', control_variant=args.variant,
                    kind=args.kind, dataset_id=dataset, tool_versions=tools, agent_context=manifest['agent_context'])
        write_json(run / 'run_manifest.json', info)
    print(json.dumps(dict(run_id=args.run_id, status=info['status'], trace=info.get('trace'), error=info.get('error'))), flush=True)
    return 0 if info['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
