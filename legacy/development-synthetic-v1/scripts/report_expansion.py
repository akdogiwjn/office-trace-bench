#!/usr/bin/env python3
"""Summarize completed real traces and qualifications without rewriting raw runs."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import load_manifest, read_json, sha256, write_json

CASES = [('xlsx','retail'),('xlsx','manufacturing'),('xlsx','hr'),('pdf','irs_w4'),('pdf','sba1919')]


def main():
    failures = read_json(ROOT/'reports/expansion-failure-samples-v1.json')
    assert failures['status'] == 'success'
    compatibility = read_json(ROOT/'reports/pdf-contract-compatibility-v7.json')
    assert compatibility['status'] == 'success'
    records = []
    for kind, dataset in CASES:
        path = ROOT/'datasets'/kind/dataset/'manifest.json'; manifest = load_manifest(path)
        qualification_path = ROOT/'qualification'/f'{kind}-{dataset}'/'qualification.json'
        qualification = read_json(qualification_path); assert qualification['status'] == 'success'
        accepted = []
        for candidate in (ROOT/'runs').glob(f'{kind}-{dataset}-*/run_manifest.json'):
            run = read_json(candidate)
            if run.get('status') == 'success' and run.get('baseline_accepted'):
                accepted.append((run['started_at'], candidate, run))
        assert accepted, (kind, dataset, 'No accepted real trace')
        _, run_path, run = max(accepted)
        assert run['manifest_sha256'] == sha256(path)
        assert run['prompt_template_sha256'] == sha256(ROOT/'prompts'/manifest['prompt_template'])
        folder = run_path.parent; events = read_json(folder/'tool_events.json')
        error_events = [e['step_id'] for e in events['events'] if (e.get('result') or {}).get('extra',{}).get('is_error')]
        traceback_events = [e['step_id'] for e in events['events']
                            if 'Traceback (most recent call last)' in (e.get('result') or {}).get('content','')]
        record = dict(kind=kind,dataset=dataset,status='success',run_id=run['run_id'],
            trace_steps=run['trace']['steps'],tool_calls=run['trace']['tool_calls'],
            agent_seconds=run['agent_seconds'],agent_context_matched=run['agent_context_matched'],
            baseline_accepted=True, source_snapshot_unchanged=run['source_snapshot_unchanged'],
            original_verifier='not_applicable',runtime_image_id=run['runtime_image_id'],
            prompt_template=manifest['prompt_template'],prompt_template_sha256=run['prompt_template_sha256'],
            input_hashes=run['input_hashes'],source_provenance=manifest['source_provenance'],
            qualification_report=str(qualification_path.relative_to(ROOT)),
            trace_file=str((folder/'trajectory.json').relative_to(ROOT)),trace_sha256=sha256(folder/'trajectory.json'),
            tool_events_sha256=sha256(folder/'tool_events.json'),
            independent_verification=str((folder/'independent_verification.json').relative_to(ROOT)),
            acceptance_report=str((folder/'baseline_acceptance.json').relative_to(ROOT)),
            analytical_operation_labels=dict(Counter(e['operation'] for e in events['events'])),
            operation_label_scope='Command substring classification includes reading scripts and batched helper calls; counts do not measure actual helper invocations.',
            tool_is_error_steps=error_events,
            traceback_observation_steps=traceback_events,
            error_scope='Final business acceptance can pass after exploratory command failures; raw observations, failures and retries are retained. A shell can exit zero despite an earlier failed subcommand.',
            helper_artifacts={name:digest for name,digest in run['artifacts'].items()
                              if name.startswith('workspace/') and '/input/' not in name and name.endswith('.py')})
        if kind == 'xlsx':
            template = read_json(path.parent/'input/template_manifest.json')
            record['workload'] = dict(raw_rows=template['raw_count'],raw_columns=16,
                base_sheets=len(template['base_sheets']),original_charts=template['existing_chart_count'],
                original_formulas=template['existing_formula_count'],
                input_workbook_bytes=(path.parent/'input'/manifest['workbook']).stat().st_size,
                completed_recalc=read_json(folder/'workspace/output/formula_recalc.json'))
        else:
            record['workload'] = dict(records=manifest['requirements']['record_count'],
                pages=manifest['requirements']['page_count'],fields=manifest['requirements']['field_count'],
                fill_rules=len(manifest['requirements']['field_rules']),
                actual_rendered_pngs=len(list((folder/'workspace/output/rendered').rglob('*.png'))))
        records.append(record)
    report = dict(schema_version='office-expansion-report-v1',status='success',
        reported_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),new_real_traces=5,
        total_supported_instances=7,scope='Five new independently qualified datasets, each accepted after a real Agent run; TLC/OPM regression evidence retained separately. No replay recipe or image produced.',
        common_prompts_unchanged=True,fixed_agent_helpers_introduced=False,
        cases=records,pdf_contract_compatibility='reports/pdf-contract-compatibility-v7.json',
        negative_samples='reports/expansion-failure-samples-v1.json',
        source_limitations=[
            'Retail and manufacturing Census series obtained through FRED; frozen 2023–2024 selected observations, 100k synthetic partitions, not observed transactions or firms.',
            'HR uses the publicly cached 2025 national OEWS workbook; official byte identity has not been independently verified. Selected detailed occupations only; weighted occupation median is a proxy.',
            'SBA uses the native fillable 2024 PDF distributed by SBA Box; the current 2025 official download was unavailable. A 2025 bank mirror was nonfillable and excluded.'],
        original_failed_runs_preserved=True,performance_claim='No repeated replay measurements; tool counts and Agent wall time do not establish performance or generation stability.')
    write_json(ROOT/'reports/new-dataset-expansion-v8.json',report)
    lines = ['# 新数据与真实 trace 验证（v8）','',
        '五个新实例完成独立正样本、破坏样本检查和真实 Agent 验收。保留 TLC/OPM 后，共七个可运行实例。',
        '两份正式共用提示词未改；Agent 继续自行生成 helper。用于复现 trace 的 recipe 和镜像尚未构建。','',
        '| 实例 | 真实 trace | 步数 / 工具调用 | 验收 |','|---|---|---:|---|']
    for r in records:
        lines.append(f"| {r['kind']}/{r['dataset']} | [{r['run_id']}](../{r['trace_file']}) | {r['trace_steps']} / {r['tool_calls']} | Agent、独立验收、背景与隔离检查通过 |")
    lines += ['', '三个新 XLSX 均为 100,000 行、16 列、7 张基础表、2 个原有图表；仅保留官方观测汇总，并明确标记合成工作量分片。',
        'W-4 为 5 页、48 个叶字段、10 份填写结果和 55 张 PNG；SBA 为 7 页、127 个叶字段、10 份结果和 77 张 PNG。','',
        '来源边界：Retail/M3 通过 FRED 获取 Census 序列。HR 使用公开仓库的 2025 OEWS 工作簿缓存，尚未核验与官方 ZIP 的字节一致性；仅使用选定详细职业，“中位工资”为职业中位数的就业加权代理值。',
        'SBA 使用 SBA 官方公开 Box 分发的 2024 原生可填写版，文件与公开 Box SHA-1 相符；不称为当前 2025 版。当前版官方原文件下载失败，下载到的银行副本没有 AcroForm，已排除。','',
        'OPM 国籍与摘要路径改为 manifest 中的明确别名；同一旧产物通过当前验收，无输出改写。原 v6 失败记录保留，见 [兼容性审计](pdf-contract-compatibility-v7.json)。',
        '五个新实例的破坏样本全部拒绝，见 [负样本检查](expansion-failure-samples-v1.json)。',
        '具体规模、输入/trace/helper 哈希、来源与全部证据路径见 [完整报告](new-dataset-expansion-v8.json)。','',
        '每实例这轮仅生成一次，不能据此证明多次生成稳定性。操作标签会包含读取脚本和批处理调用，不能直接视为 helper 调用次数；本轮没有 CPU/OS 性能结论。','']
    lines.insert(-1, 'W-4 与制造业 trace 包含探索性 import 探测的 ModuleNotFoundError，随后通过提供的验收入口完成验收；这些观察没有删除。最终验收通过不表示每条探索命令都成功。')
    (ROOT/'reports/new-dataset-expansion-v8.md').write_text('\n'.join(lines))
    status = read_json(ROOT/'docs/status.json')
    status.update(current_phase='all_selected_datasets_have_accepted_real_traces',
                  next_phase='freeze_selected_successful_trajectories_and_design_replay_recipe_when_requested; replay_image_deferred',
                  new_datasets={dataset:'independently_qualified_and_real_trace_accepted' for _,dataset in CASES})
    status['evidence'].update(new_dataset_expansion='reports/new-dataset-expansion-v8.json',
                              expansion_negative_samples='reports/expansion-failure-samples-v1.json')
    status['generalization_scope']['new_domain_trace_validation']='five_new_domains_passed; same_family_prompts_and_verifier'
    status['source_limitations']=report['source_limitations']
    for r in records:
        status['real_agent_regression'][r['dataset']]={key:r[key] for key in
            ['status','run_id','baseline_accepted','agent_context_matched','trace_steps','tool_calls','acceptance_report']}
        status['real_agent_regression'][r['dataset']]['scope']='New dataset; common family prompt and generic verifier; no original historical verifier.'
    write_json(ROOT/'docs/status.json',status)
    print('expansion success: five accepted new traces; seven supported instances; replay image deferred',flush=True)


if __name__ == '__main__': main()
