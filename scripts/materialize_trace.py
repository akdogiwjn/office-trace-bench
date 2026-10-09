#!/usr/bin/env python3
"""Restore hash-verified evidence files, without running any saved command/helper."""
import argparse
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from office_trace_bench.canonical import validate_pack
from office_trace_bench.contracts import safe_relative,sha256,write_json

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('canonical_pack',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args();data=validate_pack(args.canonical_pack)
    destination=args.destination.resolve()
    if destination.exists():raise ValueError('destination must be new; evidence restore never overwrites files')
    destination.mkdir(parents=True)
    for name,spec in data['artifact_inventory'].items():
        target=destination/safe_relative(name);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'artifacts/objects/sha256'/spec['sha256'],target)
    for name in ('canonical.json','trajectory.json','tool_events.json','segmentation.json'):
        shutil.copyfile(args.canonical_pack/name,destination/name)
    write_json(destination/'materialization.json',dict(original_run_id=data['original_run_id'],
        canonical_sha256=sha256(args.canonical_pack/'canonical.json'),file_count=len(data['artifact_inventory']),
        executable_recipe=False,scope='Evidence restoration only. Historical absolute paths in metadata are not followed; no LLM, helper, shell or saved command is executed.'))
    print(data['original_run_id'],'evidence restored to',destination)

if __name__=='__main__':main()
