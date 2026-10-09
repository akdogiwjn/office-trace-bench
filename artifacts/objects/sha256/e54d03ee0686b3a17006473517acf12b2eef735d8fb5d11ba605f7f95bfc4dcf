import argparse
import json
from pathlib import Path

from .contracts import ROOT, dataset_path, load_manifest


def main():
    parser = argparse.ArgumentParser(description='Office tasks: manifests, verification, real Agent traces')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    for name in ('validate', 'prepare', 'run', '_container-run'):
        p = commands.add_parser(name)
        p.add_argument('--kind', choices=('xlsx', 'pdf'), required=True)
        p.add_argument('--dataset', required=True)
        if name == 'prepare':
            p.add_argument('--workspace', type=Path, required=True)
        if name in ('run', '_container-run'):
            p.add_argument('--timeout', type=int, default=1800)
            p.add_argument('--model', help='Explicit model override; otherwise preserve the provided OpenClaw config')
            p.add_argument('--config', default='/root/.openclaw' if name == 'run' else '/host-openclaw')
            if name == 'run':
                p.add_argument('--image', default='office-trace-bench:runtime')
            else:
                p.add_argument('--run-dir', type=Path, required=True)
    p = commands.add_parser('verify')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--report', type=Path)
    p = commands.add_parser('export')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--session', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--agent-version', default='unknown')
    p.add_argument('--run-id')
    args = parser.parse_args()
    try:
        if args.command == 'list':
            for path in sorted((ROOT / 'datasets').glob('*/*/manifest.json')):
                data = load_manifest(path)
                print(json.dumps({'kind': data['kind'], 'dataset_id': data['dataset_id'], 'task': data['task']}, ensure_ascii=False))
        elif args.command == 'validate':
            load_manifest(dataset_path(args.kind, args.dataset))
            print('manifest and frozen asset hashes: OK')
        elif args.command == 'prepare':
            from .runner import stage
            stage(dataset_path(args.kind, args.dataset), args.workspace)
            print(args.workspace)
        elif args.command == 'verify':
            from .verify import verify
            report = verify(args.manifest, args.workspace, args.report)
            print(json.dumps({'status': report['status'], 'failures': report['failures']}, ensure_ascii=False))
            return 0 if report['status'] == 'success' else 1
        elif args.command == 'export':
            from .trace import export_trace
            print(json.dumps(export_trace(args.session, args.output, load_manifest(args.manifest), args.agent_version, args.run_id)))
        elif args.command == 'run':
            from .runner import launch
            if args.timeout <= 0:
                raise ValueError('timeout must be positive')
            return launch(args.kind, args.dataset, args.image, args.config, args.timeout, args.model)
        elif args.command == '_container-run':
            from .runner import container_run
            return container_run(args.kind, args.dataset, args.run_dir, args.timeout, args.config, args.model)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'error: {exc}\n')
    return 0
