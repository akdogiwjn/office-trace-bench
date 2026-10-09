"""Freeze the necessary Agent background without importing historical task data."""
from pathlib import Path
import shutil

from .contracts import ROOT, ID, read_json, safe_relative, sha256

BACKGROUND = {'AGENTS.md', 'SOUL.md', 'TOOLS.md', 'IDENTITY.md', 'USER.md', 'HEARTBEAT.md'}


def profile_path(manifest):
    selection = manifest.get('agent_context', {})
    name = selection.get('profile', '')
    if not ID.fullmatch(name):
        raise ValueError('invalid Agent context profile')
    return ROOT / 'runtime_context/profiles' / name / 'profile.json'


def load_profile(manifest):
    path = profile_path(manifest)
    if not path.is_file() or sha256(path) != manifest['agent_context'].get('sha256'):
        raise ValueError('Agent context profile hash mismatch')
    data = read_json(path)
    if data.get('schema_version') != 'office-agent-context-v1':
        raise ValueError('unsupported Agent context profile')
    allowed = {f'workspace/{name}' for name in BACKGROUND} | {'skills/agent-browser/SKILL.md'}
    if set(data['files']) != allowed:
        raise ValueError('Agent context must contain only the allowlisted background and Skill files')
    for name, digest in data['files'].items():
        asset = path.parent / safe_relative(name)
        if asset.is_symlink() or not asset.is_file() or sha256(asset) != digest:
            raise ValueError(f'Agent background hash mismatch: {name}')
    return path, data


def install_context(manifest, home, project):
    path, data = load_profile(manifest)
    home = Path(home)
    workspace = home / 'workspace'
    config = read_json(home / 'openclaw.json')
    configured = config.get('agents', {}).get('defaults', {}).get('workspace', str(workspace))
    if configured != data['workspace_dir'] or str(workspace) != data['workspace_dir']:
        raise ValueError('configured Agent workspace differs from frozen context')
    workspace.mkdir(exist_ok=True)
    for name in BACKGROUND:
        shutil.copy2(path.parent / 'workspace' / name, workspace / name)
    for name in data['absent_workspace_files']:
        if (workspace / name).exists():
            raise ValueError(f'unexpected Agent background file: {name}')
    skills = home / 'skills'
    skills.mkdir(exist_ok=True)
    shutil.copytree(path.parent / 'skills/agent-browser', skills / 'agent-browser')
    # Match the historical registry: shared extra Skill plus only this case's Office Skill.
    (skills / manifest['kind']).symlink_to(Path(project) / 'vendor/skills' / manifest['kind'])
    return data


def background_hashes(home):
    workspace = Path(home) / 'workspace'
    return {name: sha256(workspace / name) for name in sorted(BACKGROUND)
            if (workspace / name).is_file()}


def audit_context(manifest, profile, stdout, before, after):
    report = read_json(stdout).get('meta', {}).get('systemPromptReport', {})
    expected = profile['historical_references'][manifest['kind']]
    files = {f['name']: f['rawChars'] for f in report.get('injectedWorkspaceFiles', []) if not f.get('missing')}
    skills = report.get('skills', {})
    expected_hashes = {Path(name).name: digest for name, digest in profile['files'].items()
                       if name.startswith('workspace/')}
    matched = (files == expected['workspace_files'] and skills.get('hash') == expected['skills']['hash']
               and report.get('tools', {}).get('schemaChars') == expected['tool_schema_chars']
               and report.get('workspaceDir') == expected['workspace_dir'] and before == after == expected_hashes)
    return {'schema_version': 'office-agent-context-audit-v1', 'matched': matched,
            'profile': profile['profile_id'], 'workspace_files': files,
            'expected_workspace_files': expected['workspace_files'],
            'skills': skills, 'expected_skills': expected['skills'],
            'tool_schema_chars': report.get('tools', {}).get('schemaChars'),
            'expected_tool_schema_chars': expected['tool_schema_chars'],
            'system_prompt': report.get('systemPrompt'),
            'background_hashes_before': before, 'background_hashes_after': after,
            'background_matches_profile': before == after == expected_hashes,
            'background_unchanged': before == after,
            'scope': 'Historical injected-file lengths, exact Skill registry text hash and tool-schema length checked; current background bytes frozen and unchanged. Historical full background hashes and dynamic system text were not frozen.'}
