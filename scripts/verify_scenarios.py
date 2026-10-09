#!/usr/bin/env python3
"""Functional post-run QA: recalculate every allowed scenario, without an Agent or LLM."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import office
from openpyxl import load_workbook
from office_trace_bench.contracts import read_json,write_json,sha256
from office_trace_bench.complexity import sheet_parts,NS
from office_trace_bench.verify import same_number

def set_selector(path,location,value):
    with ZipFile(path) as z:
        part=sheet_parts(z)[location['sheet']];parts={name:z.read(name) for name in z.namelist()}
    tree=ET.fromstring(parts[part]);cell=next(c for c in tree.findall('.//s:c',NS) if c.attrib['r']==location['cell'])
    for node in list(cell):cell.remove(node)
    cell.attrib['t']='inlineStr';inline=ET.SubElement(cell,'{'+NS['s']+'}is');ET.SubElement(inline,'{'+NS['s']+'}t').text=value
    parts[part]=ET.tostring(tree)
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)

def check(run,destination,snapshot):
    info=read_json(run/'run_manifest.json');root=snapshot/'datasets/xlsx'/info['dataset_id'];m=read_json(root/'manifest.json');expected=read_json(root/m['expected_file'])
    features=read_json(run/'workspace/output/workbook_features.json');source=run/'workspace/output'/m['output_workbook'];destination.mkdir(parents=True,exist_ok=True)
    results=[]
    for row in m['requirements']['scenario']['rows']:
        folder=destination/row['name'];folder.mkdir(exist_ok=True);book=folder/source.name;shutil.copyfile(source,book)
        set_selector(book,features['scenario']['selector'],row['name'])
        process=subprocess.run(['python3',str(snapshot/'vendor/skills/xlsx/scripts/recalc.py'),str(book),str(m['requirements']['recalc_timeout'])],capture_output=True,text=True,timeout=m['requirements']['recalc_timeout']+60)
        (folder/'recalc.stdout.json').write_text(process.stdout);(folder/'recalc.stderr.log').write_text(process.stderr)
        try: report=read_json(folder/'recalc.stdout.json')
        except Exception:report={}
        b=load_workbook(book,data_only=True,read_only=True);checks={}
        for id,location in features['scenario']['projections'].items():
            actual=b[location['sheet']][location['cell']].value;want=expected['scenario_values'][row['name']][id]
            checks[id]=dict(actual=actual,expected=want,ok=same_number(actual,want))
        for id,location in features['metrics'].items():
            actual=b[location['sheet']][location['cell']].value;want=expected['metric_values'][id]
            checks['base_metric:'+id]=dict(actual=actual,expected=want,ok=same_number(actual,want))
        b.close();results.append(dict(scenario=row['name'],recalc_status=report.get('status'),checks=checks,
            passed=process.returncode==0 and report.get('status')=='success' and all(c['ok'] for c in checks.values())))
    result=dict(schema_version='office-scenario-qualification-v1',dataset_id=info['dataset_id'],run_id=info['run_id'],
        source_trace_sha256=sha256(run/'trajectory.json'),source_workbook_sha256=sha256(source),expected_sha256=m['expected_sha256'],
        status='success' if all(r['passed'] for r in results) else 'failed',scenarios=results,
        scope='Functional scenario QA on disposable copies after Agent execution. No LLM, no CPU/OS replay or performance measurements. These recalc calls are not original Agent tool events.')
    write_json(destination/'report.json',result);print(result['status'],info['dataset_id']);return 0 if result['status']=='success' else 1

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path);parser.add_argument('--inside',action='store_true');args=parser.parse_args()
    if args.inside:return check(args.run,Path('/qualification'),Path('/snapshot'))
    run=args.run.resolve();info=read_json(run/'run_manifest.json');output=ROOT/'qualification/scenarios'/info['run_id'];output.mkdir(parents=True,exist_ok=True)
    cmd=['docker','run','--rm','--init','--network','none','--mount',f'type=bind,src={ROOT},dst=/workspace,readonly',
         '--mount',f'type=bind,src={run},dst=/run,readonly','--mount',f'type=bind,src={info["source_snapshot_path"]},dst=/snapshot,readonly',
         '--mount',f'type=bind,src={output},dst=/qualification','--workdir','/workspace',info['runtime_image_id'],
         'python3','/workspace/scripts/verify_scenarios.py','/run','--inside']
    result=subprocess.run(cmd)
    if (output/'report.json').exists():shutil.copyfile(output/'report.json',ROOT/'reports'/('scenario-'+info['dataset_id']+'-v2.json'))
    return result.returncode

if __name__=='__main__':raise SystemExit(main())
