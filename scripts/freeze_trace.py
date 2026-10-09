#!/usr/bin/env python3
"""Publish an immutable accepted execution trace pack; never executes replay."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import office
from office_trace_bench.canonical import freeze_trace,validate_pack
from office_trace_bench.contracts import write_json,read_json,sha256

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('path',type=Path);p.add_argument('--validate',action='store_true');args=p.parse_args()
    if args.validate:
        data=validate_pack(args.path);print(data['original_run_id'],'canonical objects and bindings: OK')
    else:print(freeze_trace(args.path))

if __name__=='__main__':main()
