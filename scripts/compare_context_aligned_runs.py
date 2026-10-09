#!/usr/bin/env python3
"""Retain a separate comparison for the shared-template/context regression."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import read_json, write_json
from compare_baseline_traces import compare, calls
from compare_prompt_restored_runs import inspect, helper_inventory, prompt_equivalence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tlc', required=True)
    parser.add_argument('--opm', required=True)
    args = parser.parse_args()
    data = dict(schema_version='office-context-aligned-comparison-v4',
                compared_at=datetime.now(timezone.utc).isoformat(), datasets={})
    for kind, dataset, run_id, previous in [
        ('xlsx', 'tlc', args.tlc, 'xlsx-tlc-20261008T123533Z-e0fe46a7'),
        ('pdf', 'opm', args.opm, 'pdf-opm-20261008T124346Z-f0f172a6')]:
        run = ROOT / 'runs' / run_id
        item = compare(kind, dataset, run_id)
        item['prompt'] = prompt_equivalence(kind, run)
        item['agent_context'] = read_json(run / 'agent_context_audit.json')
        selection = read_json(run / 'workspace/input/dataset_manifest.json')['agent_context']
        profile = read_json(Path(read_json(run / 'run_manifest.json')['source_snapshot_path']) /
                            'runtime_context/profiles' / selection['profile'] / 'profile.json')
        historical_stdout = Path(profile['historical_references'][kind]['source_metadata'])
        if historical_stdout.is_file():
            item['historical_system_prompt'] = read_json(historical_stdout)['meta']['systemPromptReport']['systemPrompt']
        hashes = {Path(name).name: digest for name, digest in profile['files'].items()
                  if name.startswith('workspace/')}
        item['agent_context']['background_matches_profile'] = (
            item['agent_context']['background_hashes_before'] == item['agent_context']['background_hashes_after'] == hashes)
        item['context_aligned_run'] = inspect(kind, run)
        item['command_failure_diagnostics'] = []
        failed_steps = {f['step_id'] for f in item['trace']['new']['command_failures']}
        for step, call, result in calls(read_json(run / 'trajectory.json')):
            if step in failed_steps:
                item['command_failure_diagnostics'].append(dict(step=step,
                    command=call['arguments'].get('command'), result_tail=(result or {}).get('content', '')[-700:]))
        if kind == 'pdf':
            log = run / 'workspace/output/batch_run.log'
            if log.is_file():
                item['logged_bundled_script_invocations'] = dict(Counter(re.findall(
                    r'^RUN: .*?/(fill_fillable_fields|convert_pdf_to_images)\.py\b', log.read_text(), re.M)))
        item['previous_leaf_template_run'] = inspect(kind, ROOT / 'runs' / previous)
        item['historical_helpers'] = helper_inventory(read_json(ROOT / 'legacy' / kind / 'trajectory.json'))
        item['expected_file_reference_steps'] = [s for s, c, _ in calls(read_json(run / 'trajectory.json'))
            if c['function_name'] in ('read', 'exec') and 'expected.json' in str(c['arguments'])]
        if (not item['prompt']['same_business_and_execution_text'] or not item['agent_context']['matched']
                or not item['agent_context']['background_matches_profile']):
            item['status'] = 'failed'
        data['datasets'][dataset] = item
    data['status'] = 'success' if all(i['status'] == 'success' for i in data['datasets'].values()) else 'failed'
    write_json(ROOT / 'reports/context-aligned-trace-comparison-v4.json', data)
    lines = ['# 共用模板与背景上下文回归', '', f"回归结果：`{data['status']}`。", '',
        'TLC/OPM 使用按类型共用的 xlsx.txt/pdf.txt。领域变量由 manifest 提供；渲染后旧业务、执行与 QA 原文保持一致。',
        '本轮恢复六份必要背景说明、agent-browser，且仅注册当前 Office Skill；不导入历史任务、产物或会话。', '',
        '| 用例 | 历史 steps / calls | 上轮仅恢复任务文本 | 本轮共用模板与上下文 | 业务回归 / 上下文审计 |',
        '|---|---:|---:|---:|---|']
    for name, item in data['datasets'].items():
        old = item['trace']['old']; prev = item['previous_leaf_template_run']['stats']; new = item['trace']['new']
        lines.append(f"| {name.upper()} | {old['steps']} / {old['tool_calls']} | {prev['steps']} / {prev['tool_calls']} | {new['steps']} / {new['tool_calls']} | {item['status']} / {item['agent_context']['matched']} |")
    for name, item in data['datasets'].items():
        lines += ['', '## ' + name.upper(), '', f"新运行：`runs/{item['run_id']}`。", '',
            f"任务文本一致性：{item['prompt']['same_business_and_execution_text']}；背景文件前后未变：{item['agent_context']['background_unchanged']}。",
            f"Skill 注册文本哈希与历史一致：{item['agent_context']['skills']['hash'] == item['agent_context']['expected_skills']['hash']}。",
            f"工具类型（历史 / 本轮）：{item['trace']['old']['tools']} / {item['trace']['new']['tools']}。", '',
            '| helper | 版本 | 行数 | 写入次数 | 启动命令次数 |', '|---|---|---:|---:|---:|']
        for label, helpers in [('历史', item['historical_helpers']), ('本轮', item['context_aligned_run']['helpers'])]:
            for filename, helper in helpers.items():
                lines.append(f"| {filename} | {label} | {helper['lines']} | {len(helper['write_steps'])} | {len(helper['exec_attempts'])} |")
        if 'historical_system_prompt' in item:
            old_context, new_context = item['historical_system_prompt'], item['agent_context']['system_prompt']
            lines += ['', f"projectContext 字符（历史 / 本轮）：{old_context['projectContextChars']} / {new_context['projectContextChars']}；系统文本总字符：{old_context['chars']} / {new_context['chars']}。",
                '系统动态文本未完整封存；总长度的剩余差异不能仅凭元数据定位，不能据此宣称全部系统文本一致。']
        lines += ['', f"本轮非零退出或错误结果：{len(item['trace']['new']['command_failures'])}；进程 kill：{len(item['trace']['new']['process_kill_steps'])}。",
            f"expected.json 引用步骤：{item['expected_file_reference_steps']}。", '',
            '生成 helper 的源码哈希、每次启动及最终状态记录在 JSON 报告中；调用总数含读取、写入、轮询、失败和重试。']
        for failure in item['trace']['new']['command_failures']:
            diagnosis = next((d for d in item['command_failure_diagnostics'] if d['step'] == failure['step_id']), {})
            lines += ['', f"失败步骤 {failure['step_id']}（exit={failure['exit_code']}）：", '',
                      '```text', diagnosis.get('result_tail', failure['result_excerpt']), '```']
        if name == 'tlc':
            if any('time: not found' in d['result_tail'] for d in item['command_failure_diagnostics']):
                lines += ['', 'time 未安装使启动命令退出 127，Python helper 尚未开始；成功执行次数另见完整 trace 与摘要。']
            if any('Bad substitution' in d['result_tail'] and 'PIPESTATUS' in str(d['command'])
                   for d in item['command_failure_diagnostics']):
                lines += ['', '重算命令输出后，/bin/sh 因不支持 Bash 的 PIPESTATUS 下标语法而退出 2。',
                    '这个辅助 shell 错误与重算 JSON、公式错误数和独立验收结果分别记录。']
        if name == 'tlc':
            output = item['outputs']
            lines += ['', f"重算命令次数（历史 / 本轮）：{len(item['business_stage_exec_steps']['old']['recalculate'])} / {len(item['business_stage_exec_steps']['new']['recalculate'])}。",
                f"公式数量：{output['formula_counts']['old']} / {output['formula_counts']['new']}。核心 KPI 缓存一致：{output['same_kpi_cached_values']}；CSV 字节一致：{all(output['same_csv_bytes'].values())}。", '', '公式差异：']
            lines += [f"- `{d['cell']}`：`{d['old']}` → `{d['new']}`" for d in output['formula_differences']] or ['- 无。']
        else:
            lines += ['', f"新产物清单：{item['outputs']['artifact_counts']['new']}。全部字段值和页码一致：{all(item['outputs']['same_field_values_and_pages'].values())}。",
                '批次汇总是 Agent 自报计数；应结合保留的最终驱动、exec 结果、完整 trace 和独立产物清单阅读。']
            if 'logged_bundled_script_invocations' in item:
                lines += ['', f"本轮批次运行日志的 RUN 条目：{item['logged_bundled_script_invocations']}；驱动在日志写入前使用 subprocess.run(check=True) 完成各调用。"]
    lines += ['', '## 可比性边界', '',
        '本轮检查了历史注入文件长度、Skill 注册文本的准确哈希、工具 schema 长度、workspace 路径，并冻结当前背景文件的实际字节。',
        '历史未记录完整背景文件和配置哈希，动态系统文本、日期及服务端模型状态也不能据此证明一致。因此不宣称完整历史模型输入逐字相同。',
        '这些检查消除了已发现的 runner 上下文差异；仍不能保证独立模型生成相同脚本。业务通过与负载相同是两种验收。',
        '新领域尚未实际生成 trace。下一阶段用同一模板接入新 manifest、输入与独立预期；离线 replay 镜像继续后置。', '']
    (ROOT / 'reports/context-aligned-trace-comparison-v4.md').write_text('\n'.join(lines))
    print(data['status'] + ': reports/context-aligned-trace-comparison-v4.md')
    return 0 if data['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
