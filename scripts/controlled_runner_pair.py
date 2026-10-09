#!/usr/bin/env python3
"""Run each actual runner once per baseline with frozen current conditions."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / 'legacy/runner'
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import load_manifest, read_json, sha256, write_json
from office_trace_bench.prompts import parameters

LEGACY_SCRIPTS = ('run_agent_case.sh', 'sync_openclaw_config.py', 'capture_openclaw_session.py',
                  'export_openclaw_atif.py', 'extract_key_operations.py', 'check_agent_output.py')


def tree_hashes(root):
    return {str(p.relative_to(root)): sha256(p) for p in root.rglob('*') if p.is_file()}


def prepare_snapshot(snapshot, kind, dataset):
    snapshot.mkdir(parents=True)
    for name in ('office_trace_bench', 'prompts', 'vendor', 'runtime', 'runtime_context'):
        shutil.copytree(ROOT / name, snapshot / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(ROOT / 'office.py', snapshot / 'office.py')
    source_dataset = LEGACY / 'cases' / kind
    shutil.copytree(source_dataset, snapshot / 'datasets' / kind / dataset)
    manifest = load_manifest(source_dataset / 'manifest.json')
    template = snapshot / 'prompts' / manifest['prompt_template']
    text = template.read_text().replace('inside a fresh trace-generation container.', 'inside a fresh VM.')
    text = text.replace('The container uses the installed openpyxl.', "The VM uses Ubuntu's packaged openpyxl.")
    # Reproduce the old Bash runner's actual --message value, including its newline behavior.
    template.write_text(text.rstrip('\n'))
    manifest['prompt_template_sha256'] = sha256(template)
    write_json(snapshot / 'datasets' / kind / dataset / 'manifest.json', manifest)
    logical = '/root/.openclaw/workspace/tool-modeling/' + manifest['runtime_case']
    rendered = template.read_text().format(workspace=logical, dataset_id=dataset,
        manifest=f'/workspace/datasets/{kind}/{dataset}/manifest.json', project='/workspace', **parameters(manifest))
    original = (LEGACY / 'cases' / kind / 'task.prompt').read_text()
    if rendered != original.rstrip('\n'):
        raise ValueError('controlled rendered task differs from the original actual task')
    case = snapshot / 'cases' / kind
    case.mkdir(parents=True)
    (case / 'output').mkdir()
    (case / 'agent_run').mkdir()
    shutil.copytree(LEGACY / 'cases' / kind / 'input', case / 'input',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (case / 'task.prompt').write_text(original)
    for relative, digest in manifest['input_files'].items():
        if sha256(case / relative) != digest:
            raise ValueError(f'old/new input asset differs: {relative}')
    if set(tree_hashes(case / 'input')) != {str(Path(k).relative_to('input')) for k in manifest['input_files']}:
        raise ValueError('old input inventory differs from new inputs')
    # Both variants see this same metadata file; it is not a historical output.
    write_json(case / 'input/dataset_manifest.json', manifest)
    (snapshot / 'scripts').mkdir()
    old_script_hashes = {}
    for name in LEGACY_SCRIPTS:
        shutil.copy2(LEGACY / 'scripts' / name, snapshot / 'scripts' / name)
        old_script_hashes[name] = sha256(snapshot / 'scripts' / name)
    for name in ('control_container_entry.py',):
        shutil.copy2(ROOT / 'scripts' / name, snapshot / 'scripts' / name)
    (snapshot / 'control-bin').mkdir()
    shutil.copy2(ROOT / 'scripts/control_openclaw.py', snapshot / 'control-bin/openclaw')
    (snapshot / 'control-bin/openclaw').chmod(0o755)
    skill = 'vendor/skills/' + kind
    legacy_skill = {k: v for k, v in tree_hashes(ROOT / skill).items()
                    if '__pycache__' not in Path(k).parts and not k.endswith('.pyc')}
    if tree_hashes(snapshot / skill) != legacy_skill:
        raise ValueError('Office Skill source differs across old/new')
    return dict(kind=kind, dataset=dataset, snapshot=str(snapshot),
                actual_task_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
                input_hashes=tree_hashes(case / 'input'), legacy_script_hashes=old_script_hashes,
                source_hashes=tree_hashes(snapshot),
                task_control='Old historical business text and actual trailing-newline behavior; only experimental snapshot templates are normalized. Active project prompts are unchanged.')


def prepare(experiment_id):
    experiment = ROOT / 'control_pairs' / experiment_id
    experiment.mkdir(parents=True)
    plan = dict(schema_version='office-controlled-runner-pair-v1', experiment_id=experiment_id,
                requested_model='deepseek/deepseek-v4-flash', image_tag='office-trace-bench:runtime',
                status='prepared', datasets={}, runs=[],
                scope='One current run per runner and dataset; tests current runner differences, not statistical variance.')
    for kind, dataset in [('xlsx', 'tlc'), ('pdf', 'opm')]:
        snapshot = ROOT / '.snapshots' / experiment_id / kind
        selection = prepare_snapshot(snapshot, kind, dataset)
        plan['datasets'][dataset] = selection
        for variant in ('old', 'new'):
            run_id = f'control-{variant}-{kind}-{dataset}-{experiment_id}'
            run = ROOT / 'runs' / run_id
            run.mkdir(parents=True)
            shutil.copytree(snapshot / 'cases' / kind, run / 'case')
            write_json(run / 'source_snapshot.json', dict(timing='before-agent-execution', files=selection['source_hashes']))
            plan['runs'].append(dict(kind=kind, dataset=dataset, variant=variant, run_id=run_id,
                                     run_dir=str(run), status='pending'))
    write_json(experiment / 'plan.json', plan)
    return experiment, plan


def run_experiment(experiment, plan):
    image_id = subprocess.run(['docker', 'image', 'inspect', plan['image_tag'], '--format', '{{.Id}}'],
                              check=True, capture_output=True, text=True).stdout.strip()
    volume = 'office-control-config-' + plan['experiment_id'].lower()
    subprocess.run(['docker', 'volume', 'create', volume], check=True, capture_output=True)
    plan.update(image_id=image_id, config_volume=volume, status='running')
    write_json(experiment / 'plan.json', plan)
    try:
        snapshot = plan['datasets']['tlc']['snapshot']
        subprocess.run(['docker', 'run', '--rm', '--init', '--hostname', 'office-trace-control',
            '--mount', f'type=bind,src={snapshot},dst=/workspace,readonly',
            '--mount', 'type=bind,src=/root/.openclaw,dst=/host-openclaw,readonly',
            '--mount', f'type=volume,src={volume},dst=/frozen-openclaw',
            '--mount', f'type=bind,src={experiment},dst=/public',
            '--workdir', '/workspace', image_id, 'python3', '/workspace/scripts/control_container_entry.py', '--freeze'], check=True)
        for item in plan['runs']:
            run = Path(item['run_dir'])
            selection = plan['datasets'][item['dataset']]
            snapshot = Path(selection['snapshot'])
            print(json.dumps(dict(starting=item['run_id'], variant=item['variant'], dataset=item['dataset'])), flush=True)
            item['status'] = 'running'
            write_json(experiment / 'plan.json', plan)
            command = ['docker', 'run', '--rm', '--init', '--name', 'office-' + item['run_id'],
                '--hostname', 'office-trace-control', '--env', 'OFFICE_TRACE_CONTAINER=1',
                '--env', 'OFFICE_TRACE_PROJECT=/workspace', '--env', 'OFFICE_CONTROL_RECORD=/runs/control',
                '--env', 'OFFICE_CONTROL_CASE=/root/.openclaw/workspace/tool-modeling/' +
                         read_json(snapshot / 'datasets' / item['kind'] / item['dataset'] / 'manifest.json')['runtime_case'],
                '--mount', f'type=bind,src={snapshot},dst=/workspace,readonly',
                '--mount', f'type=bind,src={run},dst=/runs/control',
                '--mount', f'type=bind,src={run / "case"},dst=/workspace/cases/{item["kind"]}',
                '--mount', f'type=volume,src={volume},dst=/host-openclaw,readonly',
                '--workdir', '/workspace', '--entrypoint', '/bin/bash', image_id, '-c',
                'export PATH=/workspace/control-bin:$PATH\nexec python3 /workspace/scripts/control_container_entry.py "$@"',
                'control', '--kind', item['kind'], '--variant', item['variant'], '--run-id', item['run_id']]
            with (run / 'container.stdout.log').open('w') as out, (run / 'container.stderr.log').open('w') as err:
                result = subprocess.run(command, stdout=out, stderr=err)
            info = read_json(run / 'run_manifest.json') if (run / 'run_manifest.json').is_file() else dict(status='launch_failed')
            unchanged = tree_hashes(snapshot) == selection['source_hashes']
            info.update(runtime_image=plan['image_tag'], runtime_image_id=image_id,
                source_snapshot_path=str(snapshot), source_snapshot_unchanged=unchanged,
                source_snapshot_sha256=sha256(run / 'source_snapshot.json'), container_exit_code=result.returncode,
                control_experiment_id=plan['experiment_id'])
            if not unchanged:
                info.update(status='invalidated', error='experimental source snapshot changed')
            write_json(run / 'run_manifest.json', info)
            item.update(status=info['status'], container_exit_code=result.returncode)
            write_json(experiment / 'plan.json', plan)
            print(json.dumps(dict(completed=item['run_id'], status=item['status'], trace=info.get('trace'))), flush=True)
        plan['status'] = 'success' if all(r['status'] == 'success' for r in plan['runs']) else 'failed'
    finally:
        removal = subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True, text=True)
        plan['private_config_volume_removed'] = removal.returncode == 0
        write_json(experiment / 'plan.json', plan)
    return 0 if plan['status'] == 'success' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--experiment-id')
    parser.add_argument('--resume-prepared', type=Path)
    args = parser.parse_args()
    if args.resume_prepared:
        experiment = args.resume_prepared.resolve()
        plan = read_json(experiment / 'plan.json')
        if plan['status'] != 'prepared':
            raise SystemExit('only an unexecuted prepared plan can start; no automatic model retries')
    else:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        experiment, plan = prepare(args.experiment_id or stamp + '-' + uuid.uuid4().hex[:8])
    print(json.dumps(dict(experiment=str(experiment), status=plan['status'])), flush=True)
    return 0 if args.prepare_only else run_experiment(experiment, plan)


if __name__ == '__main__':
    raise SystemExit(main())
