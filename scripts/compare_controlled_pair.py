#!/usr/bin/env python3
"""Compare current old/new runs and keep historical reference results separate."""
import argparse
import ast
import difflib
from datetime import datetime, timezone
import hashlib
import re
from pathlib import Path
import sys
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from office_trace_bench.contracts import read_json, sha256, write_json
from compare_baseline_traces import calls, coverage, output_comparison, trace_stats
from compare_prompt_restored_runs import helper_inventory
from controlled_runner_pair import tree_hashes


def audit_run(item):
    """Audit successful and failed attempts without changing generated outputs."""
    run = Path(item['run_dir'])
    info = read_json(run / 'run_manifest.json')
    workspace = run / 'workspace'
    target = run / 'legacy_verification.json'
    if item['kind'] == 'xlsx':
        args = ['legacy/xlsx/verify_xlsx_enhanced.py', str(workspace / 'output/monthly_operations_report.xlsx'),
                str(workspace / 'output/formula_recalc.json'), str(target)]
    else:
        args = ['legacy/pdf/verify_pdf_batch.py', str(workspace / 'input/of306_aug2023.pdf'),
                str(workspace / 'input/synthetic_applicants.json'), str(workspace / 'output'), str(target)]
    code = 'import sys,runpy;import office;sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name="__main__")'
    result = subprocess.run([sys.executable, '-c', code, *args], cwd=ROOT, capture_output=True, text=True)
    legacy = read_json(target) if target.exists() else dict(status='error', failures=[result.stderr[-1000:]])
    agent = read_json(workspace / 'output/business_verification.json')
    independent = read_json(run / 'independent_verification.json')
    context = read_json(run / 'agent_context_audit.json')
    unchanged = tree_hashes(Path(info['source_snapshot_path'])) == read_json(run / 'source_snapshot.json')['files']
    events = read_json(run / 'tool_events.json')['events']
    historical = [e['step_id'] for e in events if '/legacy/' in json.dumps(e['tool_call']['arguments'])
                  or '/openclaw-trace-bench/cases/' in json.dumps(e['tool_call']['arguments'])]
    called = any(e['operation'] == 'verify_business' for e in events)
    accepted = (info['status'] == 'success' and unchanged and context['matched'] and called and not historical
                and result.returncode == 0 and all(r.get('status') == 'success' and not r.get('failures')
                                                  for r in (agent, independent, legacy)))
    audit = dict(source_snapshot_unchanged=unchanged, context_accepted=context['matched'],
                 historical_artifact_reference_steps=historical, verifier_called_in_trace=called,
                 agent_verifier=agent['status'], independent_verifier=independent['status'],
                 legacy_verifier=legacy['status'], independent_failures=independent.get('failures'),
                 legacy_failures=legacy.get('failures'), failed_attempt_retained=info['status'] != 'success')
    write_json(run / 'baseline_acceptance.json', dict(accepted=accepted, audit=audit))
    info.update(baseline_accepted=accepted, baseline_acceptance_audit=audit)
    write_json(run / 'run_manifest.json', info)
    print(f"audited {item['run_id']}: accepted={accepted}", flush=True)


def final_helpers(run):
    root = run / 'workspace'
    result = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix not in ('.py', '.sh') or 'input' in path.relative_to(root).parts:
            continue
        body = path.read_text()
        entry = dict(path=str(path.relative_to(root)), sha256=sha256(path), lines=len(body.splitlines()), functions=[])
        if path.suffix == '.py':
            try:
                tree = ast.parse(body)
                entry['functions'] = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                entry['ast_sha256'] = hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
            except SyntaxError:
                entry['syntax_error'] = True
        result.append(entry)
    return result


def inspect_run(item):
    run = Path(item['run_dir'])
    info = read_json(run / 'run_manifest.json')
    stdout = read_json(run / 'openclaw_agent.stdout.log')
    system = stdout['meta']['systemPromptReport']
    trace = read_json(run / 'trajectory.json')
    initial = read_json(run / 'pre_agent_state.json')
    user = next(step for step in trace['steps'] if step.get('source') == 'user')
    # ATIF versions may store the user text under message rather than content.
    text = user.get('message', user.get('content', ''))
    checks = dict(actual_prompt_matches_recorded=hashlib.sha256(text.encode()).hexdigest() == initial['actual_prompt_sha256'])
    masked = []
    failures = []
    stages = coverage(trace, item['kind'])
    stages['verify'] = [s for s, c, _ in calls(trace) if c['function_name'] == 'exec'
                        and re.search(r'\bpython3\s+(?:\S*/)?verify_(?:xlsx_enhanced|pdf_batch)\.py\b',
                                      c['arguments'].get('command', ''))]
    for step, call, result in calls(trace):
        detail = (result or {}).get('extra', {}).get('details', {})
        content = (result or {}).get('content', '')
        if (call['function_name'] in ('exec', 'process') and detail.get('exitCode') == 0
                and re.search(r'^(?:/usr/bin/|/bin/)?(?:sh|bash):.*(?:not found|Bad substitution)', content, re.M)):
            masked.append(dict(step=step, exit_code=0, command=call['arguments'].get('command'), result_tail=content[-500:]))
        if detail.get('exitCode') not in (None, 0):
            failures.append(dict(step=step, exit_code=detail['exitCode'], command=call['arguments'].get('command'),
                                 result_tail=content[-1000:]))
    return dict(run_id=item['run_id'], status=info['status'], info=info,
                pre_agent=initial, system_report=system, trace_stats=trace_stats(run / 'trajectory.json'),
                authored_helpers=helper_inventory(trace), final_helpers=final_helpers(run),
                stages=stages, context_audit=read_json(run / 'agent_context_audit.json'),
                verification=read_json(run / 'baseline_acceptance.json'), checks=checks,
                shell_errors_masked_by_zero_exit=masked,
                nonzero_exit_details=failures,
                framework_reference_steps=[s for s, c, _ in calls(trace) if c['function_name'] in ('read', 'exec')
                    and ('/workspace/office_trace_bench' in str(c['arguments']) or '/workspace/scripts' in str(c['arguments']))])


def compare(experiment):
    plan = read_json(experiment / 'plan.json')
    data = dict(schema_version='office-controlled-comparison-v6', experiment_id=plan['experiment_id'],
                compared_at=datetime.now(timezone.utc).isoformat(), execution_plan=plan,
                scope='One old/new pair per dataset under current frozen conditions; not a variance estimate or historical model-version reproduction.', datasets={})
    for kind, dataset in [('xlsx', 'tlc'), ('pdf', 'opm')]:
        selected = {r['variant']: r for r in plan['runs'] if r['dataset'] == dataset}
        for item in selected.values():
            if not (Path(item['run_dir']) / 'baseline_acceptance.json').exists():
                audit_run(item)
        runs = {variant: inspect_run(item) for variant, item in selected.items()}
        old, new = runs['old'], runs['new']
        a, b = old['pre_agent'], new['pre_agent']
        sa, sb = old['system_report'], new['system_report']
        controls = dict(
            same_image_id=old['info']['runtime_image_id'] == new['info']['runtime_image_id'],
            same_tool_versions=old['info']['tool_versions'] == new['info']['tool_versions'],
            same_actual_task=a['actual_prompt_sha256'] == b['actual_prompt_sha256'] == plan['datasets'][dataset]['actual_task_sha256'],
            actual_task_captured_correctly=all(r['checks']['actual_prompt_matches_recorded'] for r in runs.values()),
            same_visible_inputs=a['input_hashes'] == b['input_hashes'],
            same_background_bytes=a['background_hashes'] == b['background_hashes'],
            same_config_semantics=a['config_semantic_sha256'] == b['config_semantic_sha256'],
            same_private_config_file_hashes=a['private_config_hashes'] == b['private_config_hashes'],
            same_project_source_snapshot=old['info']['source_snapshot_sha256'] == new['info']['source_snapshot_sha256'],
            same_process_environment=a['environment'] == b['environment'],
            same_skill_registry=sa['skills'] == sb['skills'],
            same_tool_registry_metadata=sa['tools'] == sb['tools'],
            same_workspace_injection=sa['injectedWorkspaceFiles'] == sb['injectedWorkspaceFiles'],
            same_full_initial_system_prompt=sa['systemPrompt']['hash'] == sb['systemPrompt']['hash'],
            same_actual_model=sa['provider'] == sb['provider'] and sa['model'] == sb['model'],
            same_agent_and_thinking=old['trace_stats']['agent'] == new['trace_stats']['agent'],
            same_bootstrap_limits=all(sa.get(k) == sb.get(k) for k in ('bootstrapMaxChars', 'bootstrapTotalMaxChars', 'bootstrapTruncation')),
            sources_unchanged=all(r['info']['source_snapshot_unchanged'] for r in runs.values()),
            context_audits_passed=all(r['context_audit']['matched'] for r in runs.values()),
            all_tool_results_captured=all(not r['trace_stats']['missing_tool_results'] for r in runs.values()),
        )
        old_output = Path(selected['old']['run_dir']) / 'workspace/output'
        new_output = Path(selected['new']['run_dir']) / 'workspace/output'
        outputs = output_comparison(kind, old_output, new_output)
        if kind == 'pdf':
            differences = []
            for path in sorted((old_output / 'field_values').glob('*.json')):
                a_fields = {x['field_id']: {'value': x['value'], 'page': x['page']} for x in read_json(path)}
                b_fields = {x['field_id']: {'value': x['value'], 'page': x['page']}
                            for x in read_json(new_output / 'field_values' / path.name)}
                for field in sorted(set(a_fields) | set(b_fields)):
                    if a_fields.get(field) != b_fields.get(field):
                        differences.append(dict(applicant=path.stem, field_id=field,
                                                old=a_fields.get(field), new=b_fields.get(field)))
            outputs['mapping_differences'] = differences
        helper_pairs = [('enhance_workbook.py', 'enhance_workbook.py')] if kind == 'xlsx' else [
            ('gen_field_values.py', 'build_field_values.py'), ('run_batch.py', 'run_batch.sh')]
        diff_text = []
        for old_name, new_name in helper_pairs:
            diff_text += list(difflib.unified_diff((old_output.parent / old_name).read_text().splitlines(keepends=True),
                             (new_output.parent / new_name).read_text().splitlines(keepends=True),
                             fromfile='old/' + old_name, tofile='new/' + new_name))
        (experiment / (dataset + '-helpers.diff')).write_text(''.join(diff_text))
        history = ROOT / 'legacy' / kind
        historical_trace = read_json(history / 'trajectory.json')
        historical_helpers = helper_inventory(historical_trace)
        last_historical_hashes = {h['source_sha256'] for h in historical_helpers.values()}
        old_current_hashes = {h['source_sha256'] for h in old['authored_helpers'].values()}
        results_ok = all(r['status'] == 'success' and r['verification']['accepted'] for r in runs.values())
        data['datasets'][dataset] = dict(kind=kind, controls=controls, runs=runs,
            controls_passed=all(controls.values()), results_passed=results_ok, outputs=outputs,
            historical_trace_stats=trace_stats(history / 'trajectory.json'), historical_helpers=historical_helpers,
            current_old_helper_writes_match_historical=old_current_hashes == last_historical_hashes,
            current_old_vs_historical_outputs=output_comparison(kind, history / 'output', old_output),
            full_system_hash_equal=sa['systemPrompt']['hash'] == sb['systemPrompt']['hash'],
            all_private_config_file_hashes_equal=a['private_config_hashes'] == b['private_config_hashes'],
            filesystem_difference=dict(old_process_cwd=a['process_cwd'], new_process_cwd=b['process_cwd'],
                old_real_case=a['real_case'], new_real_case=b['real_case'],
                old_case_symlink=a['case_is_symlink'], new_case_symlink=b['case_is_symlink']),
            helper_diff=str((experiment / (dataset + '-helpers.diff')).relative_to(ROOT)))
    data['controls_status'] = 'success' if all(d['controls_passed'] for d in data['datasets'].values()) else 'review_needed'
    data['strict_regression_status'] = 'success' if all(d['results_passed'] for d in data['datasets'].values()) else 'failed'
    data['status'] = 'comparison_complete' if data['controls_status'] == 'success' else 'review_needed'
    write_json(experiment / 'comparison.json', data)
    write_json(ROOT / 'reports/controlled-runner-pair-v6.json', data)
    lines = ['# 当前环境下旧、新 runner 各一次对照', '', f"对照：`{data['status']}`；控制项：`{data['controls_status']}`；严格业务回归：`{data['strict_regression_status']}`。", '',
        f"实验：`{plan['experiment_id']}`；TLC/OPM 各旧、新一次，共四次实际 Agent 生成。", '',
        '使用同一个固定镜像 ID、同一次冻结的当前配置、相同输入、必要背景文件和逐字相同的旧任务文本。',
        '新旧入口看到同一份只读实验项目快照，包含两套运行代码和当前输入，不包含历史成功产物或生成 helper。',
        '旧 run_agent_case.sh 及依赖源码保持不变；仅实验快照中的模板环境措辞和末尾换行按旧实际任务统一，正式项目模板未改。',
        '配置凭据只保存在临时 Docker volume；实验结束后删除，项目内只保存指纹。', '',
        '| 用例 | 历史旧版 steps / calls | 今天旧 runner | 今天新 runner | 新旧验收 / 控制项 |',
        '|---|---:|---:|---:|---|']
    for dataset, item in data['datasets'].items():
        h=item['historical_trace_stats']; a=item['runs']['old']['trace_stats']; b=item['runs']['new']['trace_stats']
        lines.append(f"| {dataset.upper()} | {h['steps']} / {h['tool_calls']} | {a['steps']} / {a['tool_calls']} | {b['steps']} / {b['tool_calls']} | {item['results_passed']} / {item['controls_passed']} |")
    for dataset, item in data['datasets'].items():
        lines += ['', '## ' + dataset.upper(), '', '| 控制项 | 匹配 |', '|---|---|']
        lines += [f'| {k} | {v} |' for k,v in item['controls'].items()]
        lines += ['', f"完整系统文本哈希相同：{item['full_system_hash_equal']}；全部配置文件字节哈希相同：{item['all_private_config_file_hashes_equal']}。", '',
            '| helper | 版本 | 行数 | 启动命令次数 |', '|---|---|---:|---:|']
        for label, helpers in [('历史',item['historical_helpers']),('今天旧',item['runs']['old']['authored_helpers']),('今天新',item['runs']['new']['authored_helpers'])]:
            for name,h in helpers.items():lines.append(f"| {name} | {label} | {h['lines']} | {len(h['exec_attempts'])} |")
        lines += ['', f"今天旧 runner 的 helper 写入哈希集合与历史相同：{item['current_old_helper_writes_match_historical']}。", '',
            f"完整 helper 源码差异：[查看 diff](../{item['helper_diff']})。", '',
            f"保留的目录差异：{item['filesystem_difference']}。", '',
            '旧入口使用真实任务目录，新入口用逻辑目录指向本轮输出目录。这是被测 runner 行为，未强行改成同一种目录实现。']
        for variant,run in item['runs'].items():
            audit = run['verification']['audit']
            lines += ['', f"{variant}：`runs/{run['run_id']}/trajectory.json`。",
                f"原版 verifier：{audit['legacy_verifier']}；通用 verifier：{audit['independent_verifier']}；最终接受：{run['verification']['accepted']}。",
                f"工具类型：{run['trace_stats']['tools']}；错误/非零退出：{len(run['trace_stats']['command_failures'])}；进程 kill：{len(run['trace_stats']['process_kill_steps'])}。",
                f"另外，总退出码为 0 但包含 shell 错误的结果：{len(run['shell_errors_masked_by_zero_exit'])}。",
                f"实际业务命令步骤（启动尝试数，包含未成功启动的命令）：{run['stages']}。",
                f"读取框架源码的步骤：{run['framework_reference_steps']}。"]
            if audit.get('independent_failures'):
                lines += ['', '通用验收失败（保持原始产物）：', '', '```json',
                          json.dumps(audit['independent_failures'], ensure_ascii=False, indent=2), '```']
            for failure in run['nonzero_exit_details']:
                lines += ['', f"失败步骤 {failure['step']}（exit={failure['exit_code']}），结果尾部：", '', '```text', failure['result_tail'], '```']
            for failure in run['shell_errors_masked_by_zero_exit']:
                lines += ['', f"步骤 {failure['step']}：总体 exit=0，结果中仍有 shell 错误（例如管道尾部掩盖前面命令失败）。", '',
                          '```text', failure['result_tail'], '```']
        output=item['outputs']
        if dataset=='tlc':
            lines += ['', f"本次旧/新公式数：{output['formula_counts']['old']} / {output['formula_counts']['new']}；KPI 缓存相同：{output['same_kpi_cached_values']}；CSV 字节相同：{all(output['same_csv_bytes'].values())}。", '', '公式差异：']
            lines += [f"- `{d['cell']}`：`{d['old']}` → `{d['new']}`" for d in output['formula_differences']] or ['- 无。']
        else:
            lines += ['', f"本次旧/新清单：{output['artifact_counts']}；所有字段值与页码相同：{all(output['same_field_values_and_pages'].values())}。"]
            if not item['results_passed']:
                lines += ['', '旧 OPM 的 10 份映射均使用国籍文本 `United States of America`，通用规则期望 `United States`；',
                          '旧摘要中的 input_form 为 `input/of306_aug2023.pdf`，通用规则期望 `of306_aug2023.pdf`。',
                          '两类字面差异导致 21 项失败（10 份映射和 10 份 PDF 字段值，加 1 项摘要）；原版 verifier 允许这些表达并通过。',
                          '新 OPM 两种验收均通过。本轮不调整规则或产物，保留失败 trace。']
    lines += ['', '## 解释范围', '',
        '本次真实执行两套入口，没有用冻结历史 helper 代替模型生成。',
        '如果今天旧 runner 也生成了不同于历史的 helper，说明相同旧入口在当前条件下也能出现变化；单凭历史/新版差异不能认定新 runner 是唯一原因。',
        '各一轮不能估计哪一版更稳定，也不能定位服务端模型、采样或目录实现各自造成多少变化。',
        '本轮每个新旧配对的完整初始系统文本哈希相同；这只证明本轮初始提示输入相同，不证明后续工具观察相同或与历史环境完全相同。',
        '旧入口仍有模型预检，新入口没有；真实目录/软链接和实际进程 cwd 有差异，已保留在证据中。两轮均未读取框架源码。',
        '调用数包含检查、读取、命令合并、等待轮询、失败和重试，不能单独代表业务处理量或性能。', '']
    markdown='\n'.join(lines)
    (experiment / 'comparison.md').write_text(markdown)
    (ROOT / 'reports/controlled-runner-pair-v6.md').write_text(markdown)
    print(data['status'] + ': reports/controlled-runner-pair-v6.md')
    return data


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment', type=Path)
    compare(parser.parse_args().experiment.resolve())
