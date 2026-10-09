import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r'^[a-z][a-z0-9_-]*$')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value):
    path = Path(value)
    if not isinstance(value, str) or not value or path.is_absolute() or '..' in path.parts:
        raise ValueError(f'unsafe relative asset path: {value!r}')
    return path


def load_manifest(path, check_assets=True):
    path = Path(path).resolve()
    data = read_json(path)
    if data.get('schema_version') != 'office-dataset-v1':
        raise ValueError('unsupported dataset manifest schema')
    if data.get('kind') not in ('xlsx', 'pdf'):
        raise ValueError('kind must be xlsx or pdf')
    if not ID.fullmatch(data.get('dataset_id', '')):
        raise ValueError('invalid dataset_id')
    for key in ('task', 'input_files', 'requirements', 'expected_file', 'trace_rules'):
        if key not in data:
            raise ValueError(f'missing manifest field: {key}')
    if not isinstance(data['input_files'], dict) or not data['input_files']:
        raise ValueError('input_files must be a non-empty path/hash map')
    safe_relative(data['expected_file'])
    if data.get('prompt_template'):
        template = ROOT / 'prompts' / safe_relative(data['prompt_template'])
        if check_assets and (not template.is_file() or sha256(template) != data.get('prompt_template_sha256')):
            raise ValueError('prompt template hash mismatch')
    if data.get('agent_context') and check_assets:
        from .context import load_profile
        load_profile(data)
    if data.get('runtime_case') and not re.fullmatch(r'[A-Za-z0-9_-]+', data['runtime_case']):
        raise ValueError('invalid runtime_case')
    if data.get('agent_verifier'):
        filename = safe_relative(data['agent_verifier'])
        if str(Path('input') / filename) not in data['input_files']:
            raise ValueError('agent_verifier must be a frozen input')
    if data['kind'] == 'xlsx':
        safe_relative(data['workbook'])
        safe_relative(data['output_workbook'])
        required = ('summary_sheet', 'base_sheets', 'raw_sheets', 'metrics', 'scenario', 'charts')
    else:
        safe_relative(data['form'])
        safe_relative(data['records'])
        required = ('page_count', 'field_count', 'record_count', 'field_rules', 'protected_blank')
    for key in required:
        if key not in data['requirements']:
            raise ValueError(f'missing {data["kind"]} requirement: {key}')
    for relative, expected_hash in data['input_files'].items():
        asset = path.parent / safe_relative(relative)
        if check_assets and (not asset.is_file() or sha256(asset) != expected_hash):
            raise ValueError(f'input hash mismatch: {relative}')
    if check_assets:
        expected = path.parent / data['expected_file']
        if not expected.is_file() or sha256(expected) != data.get('expected_sha256'):
            raise ValueError('expected results hash mismatch')
    return data


def dataset_path(kind, dataset_id):
    if kind not in ('xlsx', 'pdf') or not ID.fullmatch(dataset_id):
        raise ValueError('invalid dataset selection')
    return ROOT / 'datasets' / kind / dataset_id / 'manifest.json'
