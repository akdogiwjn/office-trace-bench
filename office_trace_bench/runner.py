"""Real Agent execution; each attempt retains its own inputs, logs and trace."""
import fnmatch
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .contracts import ROOT, dataset_path, load_manifest, read_json, sha256, write_json
from .trace import export_trace
from .verify import verify
from .prompts import render_prompt
from .context import load_profile, install_context, background_hashes, audit_context


def stage(manifest_path, workspace):
    manifest_path = Path(manifest_path).resolve()
    manifest = load_manifest(manifest_path)
    workspace = Path(workspace)
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError(f'workspace must be empty: {workspace}')
    workspace.mkdir(parents=True, exist_ok=True)
    for relative in manifest['input_files']:
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest_path.parent / relative, target)
    (workspace / 'output').mkdir(exist_ok=True)
    write_json(workspace / 'input/dataset_manifest.json', manifest)
    if not manifest.get('agent_verifier'):
        shutil.copy2(ROOT / 'runtime/verify_office.py', workspace / 'input/verify_office.py')
    return manifest


def sync_config(source, destination):
    source, destination = Path(source), Path(destination)
    if not (source / 'openclaw.json').is_file():
        raise ValueError('OpenClaw config directory has no openclaw.json')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('ephemeral OpenClaw config destination must be empty')
    excluded = ('agents/*/sessions', 'logs', 'cache', 'media', 'attachments',
                'generated_images', 'shell_snapshots', 'workspace', 'skills', 'tmp', '.tmp')
    def ignore(directory, names):
        base = Path(directory).relative_to(source)
        return {name for name in names if any(fnmatch.fnmatch((base / name).as_posix(), pattern) for pattern in excluded)}
    shutil.copytree(source, destination, symlinks=True, ignore=ignore, dirs_exist_ok=True)


def run_logged(command, run_dir, label, cwd=None, timeout=None):
    with (run_dir / (label + '.stdout.log')).open('w') as out, (run_dir / (label + '.stderr.log')).open('w') as err:
        process = subprocess.Popen(command, cwd=cwd, stdout=out, stderr=err, start_new_session=True)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            return 124


def capture_session(stdout_path, session_dir, target):
    data = read_json(stdout_path)
    meta = data.get('meta', {}).get('agentMeta', {})
    session_id = meta.get('sessionId')
    candidates = []
    if meta.get('sessionFile'):
        candidates.append(Path(meta['sessionFile']))
    if session_id:
        candidates.extend(Path(session_dir).glob(f'*/sessions/{session_id}.jsonl'))
    base = Path(session_dir).resolve()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.is_relative_to(base) and candidate.is_file():
            records = [json.loads(line) for line in candidate.read_text().splitlines() if line.strip()]
            header = next((r for r in records if r.get('type') == 'session'), None)
            if session_id and (header is None or header.get('id') != session_id):
                continue
            shutil.copy2(candidate, target)
            write_json(Path(target).with_name('session_capture.json'),
                       {'strategy': 'exact-agent-metadata', 'session_id': session_id,
                        'source': str(candidate), 'sha256': sha256(target)})
            return
    raise ValueError('no session matches the Agent stdout metadata; newest-session fallback is disabled')


def container_run(kind, dataset_id, run_dir, timeout, config_source, model=None):
    if os.environ.get('OFFICE_TRACE_CONTAINER') != '1' or not Path('/.dockerenv').exists():
        raise ValueError('internal Agent runner must execute in the disposable project container')
    run_dir = Path(run_dir)
    manifest_path = dataset_path(kind, dataset_id)
    manifest = load_manifest(manifest_path)
    workspace = run_dir / 'workspace'
    stage(manifest_path, workspace)
    logical_workspace = Path('/root/.openclaw/workspace/tool-modeling') / manifest.get('runtime_case', f'{kind}-{dataset_id}')
    prompt = render_prompt(manifest, logical_workspace, manifest_path)
    (run_dir / 'task.prompt').write_text(prompt)
    info = {'schema_version': 'office-run-v1', 'run_id': run_dir.name, 'kind': kind,
            'dataset_id': dataset_id, 'status': 'preparing', 'execution': 'real-openclaw-agent',
            'prompt_template': manifest.get('prompt_template', manifest['kind'] + '.txt'),
            'prompt_template_sha256': sha256(ROOT / 'prompts' / manifest.get('prompt_template', manifest['kind'] + '.txt')),
            'manifest_sha256': sha256(manifest_path), 'expected_sha256': manifest['expected_sha256'],
            'prompt_sha256': sha256(run_dir / 'task.prompt'),
            'started_at': datetime.now(timezone.utc).isoformat(), 'requested_model': model,
            'tool_versions': {}, 'input_hashes': manifest['input_files']}
    write_json(run_dir / 'run_manifest.json', info)
    start = time.monotonic()
    try:
        home = Path('/root/.openclaw')
        if home.exists():
            # Only the disposable container layer is changed; the host config is read-only.
            if home.is_symlink():
                raise ValueError('container OpenClaw state directory must not be a symlink')
            for child in home.iterdir():
                if child.is_symlink() or child.is_file():
                    child.unlink()
                else:
                    shutil.rmtree(child)
        sync_config(config_source, home)
        profile = install_context(manifest, home, ROOT)
        before = background_hashes(home)
        logical_workspace.parent.mkdir(parents=True, exist_ok=True)
        logical_workspace.symlink_to(workspace)
        info['prompt_workspace'] = str(logical_workspace)
        info['agent_context'] = manifest['agent_context']
        if model:
            code = run_logged(['openclaw', 'config', 'set', 'agents.defaults.model', model], run_dir, 'model_select', timeout=30)
            if code:
                raise RuntimeError('model configuration failed; see model_select logs')
        for tool, command in [('openclaw', ['openclaw', '--version']), ('node', ['node', '--version']), ('python', ['python3', '--version']), ('libreoffice', ['soffice', '--version']), ('poppler', ['pdftoppm', '-v'])]:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            info['tool_versions'][tool] = (result.stdout or result.stderr).strip().splitlines()[0]
        info['status'] = 'running'
        write_json(run_dir / 'run_manifest.json', info)
        if run_logged(['openclaw', 'config', 'validate'], run_dir, 'config_validate', timeout=60):
            raise RuntimeError('OpenClaw config validation failed; see config_validate logs')
        key = 'agent:main:' + manifest.get('runtime_case', f'office-{kind}-{dataset_id}')
        info['session_key'] = key
        agent_start = time.monotonic()
        code = run_logged(['openclaw', 'agent', '--local', '--agent', 'main', '--session-key', key,
                           '--timeout', str(timeout), '--message', prompt, '--json'],
                          run_dir, 'openclaw_agent', cwd=logical_workspace, timeout=timeout + 120)
        info['agent_seconds'] = round(time.monotonic() - agent_start, 3)
        info['agent_exit_code'] = code
        context_report = audit_context(manifest, profile, run_dir / 'openclaw_agent.stdout.log', before, background_hashes(home))
        write_json(run_dir / 'agent_context_audit.json', context_report)
        info['agent_context_matched'] = context_report['matched']
        # Capture unsuccessful attempts as well, when the Agent supplied metadata.
        capture_session(run_dir / 'openclaw_agent.stdout.log', home / 'agents', run_dir / 'openclaw_session.jsonl')
        info['trace'] = export_trace(run_dir / 'openclaw_session.jsonl', run_dir / 'trajectory.json',
                                    manifest, info['tool_versions']['openclaw'], run_dir.name)
        agent_report_path = workspace / 'output/business_verification.json'
        agent_report = read_json(agent_report_path) if agent_report_path.is_file() else {}
        info['agent_business_status'] = agent_report.get('status', 'missing')
        events = read_json(run_dir / 'tool_events.json')['events']
        info['verifier_called_in_trace'] = any(event['operation'] == 'verify_business' for event in events)
        validation_start = time.monotonic()
        report = verify(manifest_path, workspace, run_dir / 'independent_verification.json')
        info['verification_seconds'] = round(time.monotonic() - validation_start, 3)
        info['business_status'] = report['status']
        info['status'] = 'success' if (code == 0 and report['status'] == 'success'
            and agent_report.get('status') == 'success' and not agent_report.get('failures')
            and info['verifier_called_in_trace'] and info['agent_context_matched']) else 'failed'
    except Exception as exc:
        info['status'] = 'failed'
        info['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        info['elapsed_seconds'] = round(time.monotonic() - start, 3)
        info['finished_at'] = datetime.now(timezone.utc).isoformat()
        info['artifacts'] = {str(p.relative_to(run_dir)): sha256(p) for p in run_dir.rglob('*')
                             if p.is_file() and p.name != 'run_manifest.json' and not p.is_symlink()}
        write_json(run_dir / 'run_manifest.json', info)
    print(json.dumps({'run_id': run_dir.name, 'status': info['status'], 'error': info.get('error')}, ensure_ascii=False))
    return 0 if info['status'] == 'success' else 1


def launch(kind, dataset_id, image, config_dir, timeout=1800, model=None):
    manifest = load_manifest(dataset_path(kind, dataset_id))
    profile_source, _ = load_profile(manifest)
    # Fail malformed prompt parameters before starting a paid Agent session.
    render_prompt(manifest, '/validation/workspace', dataset_path(kind, dataset_id))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run_id = f'{kind}-{dataset_id}-{stamp}-{uuid.uuid4().hex[:8]}'
    runs = ROOT / 'runs'
    run_dir = runs / run_id
    run_dir.mkdir(parents=True)
    # Freeze runtime code and selected inputs; historical successful outputs are not exposed to the Agent.
    snapshot = ROOT / '.snapshots' / run_id
    snapshot.mkdir(parents=True)
    for name in ('office_trace_bench', 'prompts', 'vendor'):
        shutil.copytree(ROOT / name, snapshot / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(dataset_path(kind, dataset_id).parent, snapshot / 'datasets' / kind / dataset_id)
    shutil.copy2(ROOT / 'office.py', snapshot / 'office.py')
    shutil.copytree(profile_source.parent, snapshot / 'runtime_context/profiles' / manifest['agent_context']['profile'])
    shutil.copytree(ROOT / 'runtime', snapshot / 'runtime')
    source_hashes = {str(p.relative_to(snapshot)): sha256(p) for p in snapshot.rglob('*') if p.is_file()}
    write_json(run_dir / 'source_snapshot.json', {'timing': 'before-agent-execution', 'files': source_hashes})
    cmd = ['docker', 'run', '--rm', '--init', '--name', 'office-trace-' + run_id,
           '--env', 'OFFICE_TRACE_CONTAINER=1',
           '--env', 'OFFICE_TRACE_PROJECT=/workspace',
           '--mount', f'type=bind,src={snapshot},dst=/workspace,readonly',
           '--mount', f'type=bind,src={run_dir},dst=/runs/{run_id}',
           '--mount', f'type=bind,src={Path(config_dir).absolute()},dst=/host-openclaw,readonly',
           '--workdir', '/workspace', image, 'python3', '/workspace/office.py', '_container-run',
           '--kind', kind, '--dataset', dataset_id, '--run-dir', '/runs/' + run_id,
           '--timeout', str(timeout), '--config', '/host-openclaw']
    if model:
        cmd.extend(['--model', model])
    result = subprocess.run(cmd)
    info = read_json(run_dir / 'run_manifest.json') if (run_dir / 'run_manifest.json').exists() else {
        'schema_version': 'office-run-v1', 'run_id': run_id, 'kind': kind, 'dataset_id': dataset_id,
        'status': 'launch_failed', 'execution': 'real-openclaw-agent'}
    inspection = subprocess.run(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'], capture_output=True, text=True)
    info.update(runtime_image=image, runtime_image_id=inspection.stdout.strip(), container_exit_code=result.returncode)
    info['source_snapshot_sha256'] = sha256(run_dir / 'source_snapshot.json')
    actual_hashes = {str(p.relative_to(snapshot)): sha256(p) for p in snapshot.rglob('*') if p.is_file()}
    info['source_snapshot_unchanged'] = actual_hashes == source_hashes
    info['source_snapshot_path'] = str(snapshot)
    if not info['source_snapshot_unchanged']:
        info['status'] = 'invalidated'
        info['error'] = 'execution source snapshot changed during the run'
    write_json(run_dir / 'run_manifest.json', info)
    print(json.dumps({'run_dir': str(run_dir), 'status': info['status']}, ensure_ascii=False))
    return result.returncode if info['status'] != 'invalidated' else 1
