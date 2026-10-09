#!/usr/bin/env python3
"""Compare the historical, compact-prompt and restored-prompt real traces."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import read_json, sha256, write_json
from compare_baseline_traces import calls, compare, exec_steps, trace_stats


def helper_inventory(trace):
    rows = list(calls(trace))
    helpers = {}
    for step, call, result in rows:
        args = call['arguments']
        if call['function_name'] == 'write' and str(args.get('path', '')).endswith(('.py', '.sh')):
            name = Path(args['path']).name
            entry = helpers.setdefault(name, {'write_steps': [], 'exec_attempts': []})
            entry['write_steps'].append(step)
            body = args.get('content', '')
            entry.update(lines=len(body.splitlines()), bytes=len(body.encode()),
                         source_sha256=hashlib.sha256(body.encode()).hexdigest())
        if call['function_name'] != 'exec':
            continue
        for script in re.findall(r'\b(?:python3|bash|sh)\s+(\S+\.(?:py|sh))', args.get('command', '')):
            name = Path(script.strip(chr(34) + chr(39))).name
            if name not in helpers:
                continue
            details = (result or {}).get('extra', {}).get('details', {})
            final = details
            if details.get('status') == 'running' and details.get('sessionId'):
                for later_step, later, observation in rows:
                    if later_step <= step:
                        continue
                    later_details = (observation or {}).get('extra', {}).get('details', {})
                    if later_details.get('sessionId') == details['sessionId'] and later_details.get('status') in ('completed', 'failed'):
                        final = later_details
            helpers[name]['exec_attempts'].append({'step': step, 'status': final.get('status'),
                                                   'exit_code': final.get('exitCode')})
    return helpers


def prompt_equivalence(kind, run):
    original_workspace = {'xlsx': '/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01',
                          'pdf': '/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01'}[kind]
    old = (ROOT / 'legacy' / kind / 'task.prompt').read_text()
    path = run / 'task.prompt'
    text = path.read_text()
    normalized = text.replace(f'/runs/{run.name}/workspace', original_workspace)
    normalized = normalized.replace('inside a fresh trace-generation container.', 'inside a fresh VM.')
    normalized = normalized.replace('The container uses the installed openpyxl.', "The VM uses Ubuntu's packaged openpyxl.")
    return {'same_business_and_execution_text': old == normalized,
            'allowed_changes': ['workspace path', 'VM/container description', 'installed openpyxl description'],
            'rendered_sha256': sha256(path), 'old_word_count': len(old.split()), 'new_word_count': len(text.split())}


def inspect(kind, run):
    trace = read_json(run / 'trajectory.json')
    output = run / 'workspace/output'
    data = {'stats': trace_stats(run / 'trajectory.json'), 'helpers': helper_inventory(trace),
            'recalc_exec_steps': exec_steps(trace, r'\bpython3\s+\S*recalc\.py(?:\s|$)'),
            'source_framework_reference_steps': [], 'expected_file_reference_steps': []}
    for step, call, result in calls(trace):
        if call['function_name'] not in ('read', 'exec'):
            continue
        text = str(call['arguments'].get('path', '')) + str(call['arguments'].get('command', ''))
        if '/project/office_trace_bench' in text:
            data['source_framework_reference_steps'].append(step)
        if 'expected.json' in text:
            data['expected_file_reference_steps'].append(step)
    summary = 'xlsx_enhancement_summary.json' if kind == 'xlsx' else 'batch_summary.json'
    data['agent_summary'] = read_json(output / summary)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tlc', required=True)
    parser.add_argument('--opm', required=True)
    args = parser.parse_args()
    data = {'schema_version': 'office-prompt-restored-comparison-v2',
            'compared_at': datetime.now(timezone.utc).isoformat(), 'datasets': {}}
    for kind, dataset, run_id, previous in [
        ('xlsx', 'tlc', args.tlc, 'xlsx-tlc-20261008T115345Z-63218840'),
        ('pdf', 'opm', args.opm, 'pdf-opm-20261008T115600Z-aa170fa3')]:
        run = ROOT / 'runs' / run_id
        item = compare(kind, dataset, run_id)
        item['prompt'] = prompt_equivalence(kind, run)
        item['restored_run'] = inspect(kind, run)
        item['compact_prompt_run'] = inspect(kind, ROOT / 'runs' / previous)
        item['historical_helpers'] = helper_inventory(read_json(ROOT / 'legacy' / kind / 'trajectory.json'))
        if not item['prompt']['same_business_and_execution_text']:
            item['status'] = 'failed'
        if kind == 'xlsx':
            item['execution_discipline'] = {
                'observed_recalc_command_count': len(item['restored_run']['recalc_exec_steps']),
                'one_recalc': len(item['restored_run']['recalc_exec_steps']) == 1,
                'note': 'Additional recalc may be justified by a repair; inspect the retained trace, never substitute the summary count.'}
        else:
            summary = item['restored_run']['agent_summary']
            item['execution_discipline'] = {
                'reported_fill_script_invocations': summary.get('fill_script_invocations'),
                'reported_render_script_invocations': summary.get('render_script_invocations'),
                'expected_counts_reported': summary.get('fill_script_invocations') == 10 and summary.get('render_script_invocations') == 11,
                'note': 'These two counts are Agent-reported; retain helper sources, exec results and independently verified output inventory as supporting evidence.'}
        data['datasets'][dataset] = item
    data['status'] = 'success' if all(x['status'] == 'success' for x in data['datasets'].values()) else 'failed'
    write_json(ROOT / 'reports/prompt-restored-trace-comparison-v2.json', data)
    lines = ['# 恢复旧提示词后的真实运行对比', '',
             f"业务回归与提示词恢复检查：`{data['status']}`。", '',
             '历史 trace、第一轮简化提示词 trace 和本轮恢复提示词 trace 均保留；本轮使用同一个 runtime 镜像和同一个 DeepSeek 模型。', '',
             '| 用例 | 历史：steps / calls | 简化提示词：steps / calls | 恢复提示词：steps / calls | 新旧验收 |',
             '|---|---:|---:|---:|---|']
    for dataset, item in data['datasets'].items():
        old = item['trace']['old']; previous = item['compact_prompt_run']['stats']; new = item['trace']['new']
        lines.append(f"| {dataset.upper()} | {old['steps']} / {old['tool_calls']} | {previous['steps']} / {previous['tool_calls']} | {new['steps']} / {new['tool_calls']} | {item['status']} |")
    for dataset, item in data['datasets'].items():
        lines += ['', '## ' + dataset.upper(), '',
                  f"新运行：`runs/{item['run_id']}`。", '',
                  '恢复路径和环境措辞后，实际 task.prompt 与历史 prompt 的业务、执行和 QA 原文完全相同。原 verifier 作为冻结输入执行，通用验收在 Agent 结束后独立执行。', '',
                  '| helper | 历史 | 本轮 |', '|---|---|---|']
        for label, inventory in [('历史', item['historical_helpers']), ('本轮', item['restored_run']['helpers'])]:
            for name, helper in inventory.items():
                detail = f"{helper['lines']} 行；{len(helper['write_steps'])} 次写入；{len(helper['exec_attempts'])} 次启动命令"
                lines.append(f"| {name} | {detail if label == '历史' else ''} | {detail if label == '本轮' else ''} |")
        lines += ['', f"框架代码引用步骤：{item['restored_run']['source_framework_reference_steps']}；expected.json 引用步骤：{item['restored_run']['expected_file_reference_steps']}。",
                  f"非零退出或错误结果：{len(item['trace']['new']['command_failures'])} 个；主动终止进程：{len(item['trace']['new']['process_kill_steps'])} 个。完整调用及结果都在 trajectory.json/tool_events.json 中。"]
        if dataset == 'tlc':
            output = item['outputs']
            lines += ['', '本轮先尝试 time python3 enhance_workbook.py，因 time 不存在退出 127，Python 未启动；随后直接执行成功。',
                      '因此上表是两次启动命令、一次真正的 helper 执行；Agent 摘要也记录了这个失败启动。',
                      f"工具类型（历史 → 本轮）：exec {item['trace']['old']['tools'].get('exec', 0)} → {item['trace']['new']['tools'].get('exec', 0)}；process {item['trace']['old']['tools'].get('process', 0)} → {item['trace']['new']['tools'].get('process', 0)}。",
                      '本轮把部分检查、CSV 发布和验收合并到同一 exec，且原来的四次检查进程终止没有重现；调用减少不能解释为删除同等数量的业务操作。']
            lines += ['', f"重算实际命令次数：历史 {len(item['business_stage_exec_steps']['old']['recalculate'])}，简化提示词 {len(item['compact_prompt_run']['recalc_exec_steps'])}，本轮 {len(item['restored_run']['recalc_exec_steps'])}。",
                      f"公式数量：历史 {output['formula_counts']['old']}，本轮 {output['formula_counts']['new']}。核心 KPI 缓存值一致：{output['same_kpi_cached_values']}；两个 CSV 字节一致：{all(output['same_csv_bytes'].values())}。",
                      '', '公式差异：']
            lines += [f"- `{x['cell']}`：`{x['old']}` → `{x['new']}`" for x in output['formula_differences']] or ['- 无。']
        else:
            counts = item['outputs']['artifact_counts']['new']
            lines += ['', f"本轮 {counts['pdf']} 份 PDF、{counts['mapping']} 份映射、{counts['png']} 张 PNG。全部字段值及页码与历史一致：{all(item['outputs']['same_field_values_and_pages'].values())}。",
                      f"Agent 汇总填写/渲染次数：{item['execution_discipline']['reported_fill_script_invocations']} / {item['execution_discipline']['reported_render_script_invocations']}。"]
    lines += ['', '## 可比性边界', '',
              '恢复旧提示词消除了大幅重写任务约束这个变量，但独立 Agent 会话仍可能生成不同 helper、公式和检查步骤。',
              '后续审计发现背景 workspace 文件及 Skill 注册集合也与旧版不同；完整模型上下文尚未对齐，详见 agent-context-audit-v3.md。',
              '调用总数包含读取、检查、写文件、进程轮询和失败尝试；不能将它直接当作业务操作次数或资源消耗。',
              '本轮新 trace 仍是独立生成任务的证据。比较框架或操作系统性能时，应使用同一份固定 trace/helper，并另行保证运行环境一致。', '']
    (ROOT / 'reports/prompt-restored-trace-comparison-v2.md').write_text('\n'.join(lines))
    print(f"{data['status']}: reports/prompt-restored-trace-comparison-v2.md")
    return 0 if data['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
