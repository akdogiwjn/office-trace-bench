#!/usr/bin/env python3
"""Project-local entry point; pure Python wheels work without modifying the host."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
for wheel in sorted((ROOT / 'vendor/wheels').glob('*.whl')):
    if wheel.name.endswith(('py3-none-any.whl', 'py2.py3-none-any.whl')):
        sys.path.insert(0, str(wheel))

from office_trace_bench.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
