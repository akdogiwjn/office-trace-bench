"""Lossless tool-call inventory: classification never discards unknown calls."""
import re
from pathlib import Path

from . import atif
from .contracts import read_json, sha256, write_json


def classify(call, manifest):
    name = call['function_name']
    args = call['arguments']
    if name == 'process':
        return 'process_control'
    if name == 'read':
        return 'inspect_output' if '/output/' in str(args.get('path', '')) else 'read_guidance_or_input'
    if name in ('write', 'edit'):
        path = str(args.get('path', args.get('file_path', '')))
        return 'author_helper' if path.endswith('.py') else 'write_artifact'
    if name != 'exec':
        return 'unclassified'
    command = str(args.get('command', ''))
    if re.search(r'\bverify_office\.py\b', command):
        return 'verify_business'
    for rule in manifest['trace_rules']:
        if re.search(rule['pattern'], command):
            return rule['operation']
    return 'execute_command'


def export_trace(session, target, manifest, agent_version='unknown', run_id=None):
    trajectory = atif.convert(atif.load_records(Path(session)), 'openclaw', agent_version)
    atif.validate(trajectory)
    trajectory['extra'].update(dataset_id=manifest['dataset_id'], kind=manifest['kind'], run_id=run_id)
    write_json(target, trajectory)
    events = []
    for step in trajectory['steps']:
        results = {r['source_call_id']: r for r in step.get('observation', {}).get('results', [])}
        for call in step.get('tool_calls', []):
            events.append({'step_id': step['step_id'], 'timestamp': step.get('timestamp'),
                           'operation': classify(call, manifest), 'tool_call': call,
                           'result': results.get(call['tool_call_id'])})
    result = {'schema_version': 'office-tool-events-v1', 'dataset_id': manifest['dataset_id'],
              'kind': manifest['kind'], 'run_id': run_id, 'session_id': trajectory['session_id'],
              'source_session_sha256': sha256(session), 'source_trajectory_sha256': sha256(target),
              'tool_call_count': len(events), 'events': events,
              'scope': 'All original tool calls and results, including retries and process controls. Analytical labels; not an executable replay recipe.'}
    write_json(Path(target).with_name('tool_events.json'), result)
    return {'session_id': trajectory['session_id'], 'steps': len(trajectory['steps']), 'tool_calls': len(events)}
