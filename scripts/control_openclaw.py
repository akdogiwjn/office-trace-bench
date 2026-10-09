#!/usr/bin/env python3
"""Observe both runners immediately before exec'ing the real OpenClaw binary."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if sys.argv[1:2] == ['agent']:
    record = Path(os.environ['OFFICE_CONTROL_RECORD'])
    record.mkdir(parents=True, exist_ok=True)
    arguments = sys.argv[1:]
    prompt = arguments[arguments.index('--message') + 1]
    (record / 'actual_task.prompt').write_text(prompt)
    home = Path('/root/.openclaw')
    workspace = home / 'workspace'
    case = Path(os.environ['OFFICE_CONTROL_CASE'])
    config = home / 'openclaw.json'
    config_data = json.loads(config.read_text())
    # Hash all credential-bearing configuration; never emit its values.
    private = [config, home / '.env']
    private += list((home / 'agents/main/agent').glob('*'))
    state = dict(
        actual_prompt_sha256=digest(record / 'actual_task.prompt'),
        background_hashes={p.name: digest(p) for p in workspace.glob('*.md') if p.is_file()},
        input_hashes={str(p.relative_to(case)): digest(p) for p in (case / 'input').rglob('*') if p.is_file()},
        private_config_hashes={str(p.relative_to(home)): digest(p) for p in private if p.is_file()},
        config_semantic_sha256=hashlib.sha256(json.dumps(
            {k: v for k, v in config_data.items() if k not in ('meta', 'wizard')},
            sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        process_cwd=os.getcwd(), logical_case=str(case), real_case=str(case.resolve()),
        case_is_symlink=case.is_symlink(),
        environment={k: os.environ.get(k) for k in ('PATH', 'SHELL', 'LANG', 'LC_ALL', 'TZ')},
    )
    (record / 'pre_agent_state.json').write_text(json.dumps(state, indent=2) + '\n')

own = Path(__file__).resolve().parent
search = os.pathsep.join(p for p in os.environ.get('PATH', '').split(os.pathsep)
                         if p and Path(p).resolve() != own)
binary = shutil.which('openclaw', path=search)
if not binary:
    raise SystemExit('real OpenClaw binary not found')
os.execv(binary, [binary, *sys.argv[1:]])
