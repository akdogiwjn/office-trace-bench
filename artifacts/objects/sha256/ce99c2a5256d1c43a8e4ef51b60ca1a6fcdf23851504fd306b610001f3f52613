"""Freeze execution evidence. No LLM call and no executable replay claim."""
import hashlib
import json
from pathlib import Path
import re
import shutil

from .contracts import ROOT, read_json, sha256, safe_relative, write_json

SECRET = re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b')


def freeze_trace(run, destination=None):
    run = Path(run).resolve(); info=read_json(run/'run_manifest.json')
    acceptance=read_json(run/'baseline_acceptance.json')
    if info.get('status')!='success' or not acceptance.get('accepted'):
        raise ValueError('only successful independently accepted runs can be canonical')
    snapshot=Path(info['source_snapshot_path'])
    original=read_json(run/'source_snapshot.json')['files']
    actual={str(p.relative_to(snapshot)):sha256(p) for p in snapshot.rglob('*') if p.is_file()}
    if actual!=original: raise ValueError('frozen execution source mismatch')
    artifacts=Path(destination) if destination else ROOT/'artifacts'
    target=artifacts/'canonical'/info['kind']/info['dataset_id']/info['run_id']
    if target.exists(): raise ValueError('canonical trace is immutable; refusing overwrite')
    source_manifest='datasets/'+info['kind']+'/'+info['dataset_id']+'/manifest.json'
    manifest=read_json(snapshot/source_manifest)
    if sha256(snapshot/source_manifest)!=info['manifest_sha256']:raise ValueError('run/manifest mismatch')
    for name,digest in manifest['input_files'].items():
        if sha256(run/'workspace'/safe_relative(name))!=digest:raise ValueError('run input mismatch: '+name)
    for name in ('trajectory.json','tool_events.json','task.prompt','independent_verification.json'):
        if info['artifacts'].get(name)!=sha256(run/name):raise ValueError('run artifact mismatch: '+name)
    events=read_json(run/'tool_events.json')
    if events['source_trajectory_sha256']!=sha256(run/'trajectory.json'):raise ValueError('trace/event binding mismatch')
    inventory={}
    sources=[('source/'+name,snapshot/name,'frozen_execution_source') for name in original]
    sources.extend((str(p.relative_to(run)),p,'execution_artifact') for p in sorted(run.rglob('*'))
                   if p.is_file() and not p.is_symlink())
    # No transient container configuration, credentials, or unrelated runs are collected.
    for relative,path,role in sources:
        if path.name=='.env' or relative.startswith('project_snapshot/'):
            continue
        data=path.read_bytes()
        if SECRET.search(data):raise ValueError('credential pattern in artifact; publication blocked: '+relative)
        digest=hashlib.sha256(data).hexdigest()
        inventory[relative]=dict(sha256=digest,size=len(data),role=role)
    target.mkdir(parents=True)
    objects=artifacts/'objects/sha256';objects.mkdir(parents=True,exist_ok=True)
    for relative,path,_ in sources:
        if relative not in inventory:continue
        digest=inventory[relative]['sha256']; blob=objects/digest
        if blob.exists():
            if sha256(blob)!=digest:raise ValueError('content-addressed object corruption')
        else:shutil.copyfile(path,blob)
    for name in ('trajectory.json','tool_events.json'):
        shutil.copyfile(run/name,target/name)
    context_sources={p: h for p,h in original.items() if p.startswith(('vendor/skills/','runtime_context/'))}
    trace=read_json(run/'trajectory.json')
    revisions=read_json(run/'artifact_revisions/revisions.json') if (run/'artifact_revisions/revisions.json').exists() else None
    classification=[]
    for event in events['events']:
        args=json.dumps(event['tool_call'].get('arguments',{}),ensure_ascii=False)
        label=('verification' if event['operation']=='verify_business' else
               'inspection' if event['operation'] in ('inspect_workbook','extract_field_schema','check_fillability') else
               'helper_edit' if event['tool_call'].get('tool_name') in ('write','edit') or re.search(r'cat\s+.*>|write_text|write_bytes',args) else 'execution_or_control')
        classification.append(dict(step_id=event['step_id'],tool_call_id=event['tool_call']['tool_call_id'],label=label,
                                   result_present=event.get('result') is not None))
    write_json(target/'segmentation.json',dict(schema_version='office-trace-segmentation-v1',events=classification,
        agent_tool_chain=[c['tool_call_id'] for c in classification], final_effective_selection=None,
        final_effective_status='requires dependency reconstruction and review; all retries/rewrites remain available',
        classification_method='heuristic analysis labels; not a replay recipe'))
    canonical=dict(schema_version='office-canonical-trace-v1',kind=info['kind'],dataset_id=info['dataset_id'],
        original_run_id=info['run_id'],trace_sha256=sha256(target/'trajectory.json'),tool_events_sha256=sha256(target/'tool_events.json'),
        segmentation_sha256=sha256(target/'segmentation.json'),manifest_sha256=info['manifest_sha256'],
        input_hashes=info['input_hashes'],prompt_sha256=info['prompt_sha256'],prompt_template_sha256=info['prompt_template_sha256'],
        model=trace.get('agent',{}),agent_runtime_versions=info['tool_versions'],runtime_image_id=info['runtime_image_id'],
        skill_and_context_hashes=context_sources,skill_version_policy='Frozen source tree hashes; no invented upstream version number',
        source_snapshot_sha256=sha256(run/'source_snapshot.json'),verifier_result=dict(status='success',accepted=True,
            independent_sha256=sha256(run/'independent_verification.json'),acceptance_sha256=sha256(run/'baseline_acceptance.json')),
        artifact_inventory=inventory,revision_capture=dict(present=revisions is not None,gaps=revisions.get('gaps',[]) if revisions else ['historical run has no live revision capture']),
        execution_trace=True,executable_replay_recipe=False,replay_requires_llm=False,
        replay_scopes=['agent_trajectory_tool_chain','final_effective_tool_execution'],
        limitations=['Tool events do not by themselves establish an executable recipe. Final-effective slicing requires reconstructing reads/writes, helper revisions, environment and success dependencies. Filesystem capture is not a syscall trace.'])
    write_json(target/'canonical.json',canonical)
    return dict(path=str(target.relative_to(artifacts)),canonical_sha256=sha256(target/'canonical.json'),run_id=info['run_id'])


def validate_pack(path, artifacts=None):
    path=Path(path);data=read_json(path/'canonical.json')
    artifacts=Path(artifacts) if artifacts else ROOT/'artifacts'
    for name in ('trajectory','tool_events','segmentation'):
        if sha256(path/(name+'.json'))!=data[name+'_sha256']:raise ValueError('canonical file hash mismatch: '+name)
    for relative,spec in data['artifact_inventory'].items():
        safe_relative(relative)
        digest=spec['sha256']
        if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('invalid object hash')
        blob=artifacts/'objects/sha256'/digest
        if not blob.is_file() or blob.stat().st_size!=spec['size'] or sha256(blob)!=digest:
            raise ValueError('missing/corrupt canonical object: '+relative)
    files=data['artifact_inventory']
    def require(relative,digest):
        if files.get(relative,{}).get('sha256')!=digest:raise ValueError('broken binding: '+relative)
    manifest_path='source/datasets/'+data['kind']+'/'+data['dataset_id']+'/manifest.json'
    require(manifest_path,data['manifest_sha256']); require('task.prompt',data['prompt_sha256'])
    require('trajectory.json',data['trace_sha256']);require('tool_events.json',data['tool_events_sha256'])
    for name,digest in data['input_hashes'].items():require('workspace/'+name,digest)
    for name,digest in data['skill_and_context_hashes'].items():require('source/'+name,digest)
    require('independent_verification.json',data['verifier_result']['independent_sha256'])
    require('baseline_acceptance.json',data['verifier_result']['acceptance_sha256'])
    return data
