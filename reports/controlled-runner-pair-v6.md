> 历史证据：本报告保留原实验及其契约，不代表当前冻结 suite。当前输入、trace 选择与来源边界见 [suite 审计](../docs/suite-audit-v2.md)。

# 当前环境下旧、新 runner 各一次对照

对照：`comparison_complete`；控制项：`success`；严格业务回归：`failed`。

实验：`20261008T163759Z-90a05c03`；TLC/OPM 各旧、新一次，共四次实际 Agent 生成。

使用同一个固定镜像 ID、同一次冻结的当前配置、相同输入、必要背景文件和逐字相同的旧任务文本。
新旧入口看到同一份只读实验项目快照，包含两套运行代码和当前输入，不包含历史成功产物或生成 helper。
旧 run_agent_case.sh 及依赖源码保持不变；仅实验快照中的模板环境措辞和末尾换行按旧实际任务统一，正式项目模板未改。
配置凭据只保存在临时 Docker volume；实验结束后删除，项目内只保存指纹。

| 用例 | 历史旧版 steps / calls | 今天旧 runner | 今天新 runner | 新旧验收 / 控制项 |
|---|---:|---:|---:|---|
| TLC | 35 / 41 | 25 / 30 | 22 / 27 | True / True |
| OPM | 19 / 25 | 17 / 23 | 18 / 25 | False / True |

## TLC

| 控制项 | 匹配 |
|---|---|
| same_image_id | True |
| same_tool_versions | True |
| same_actual_task | True |
| actual_task_captured_correctly | True |
| same_visible_inputs | True |
| same_background_bytes | True |
| same_config_semantics | True |
| same_private_config_file_hashes | True |
| same_project_source_snapshot | True |
| same_process_environment | True |
| same_skill_registry | True |
| same_tool_registry_metadata | True |
| same_workspace_injection | True |
| same_full_initial_system_prompt | True |
| same_actual_model | True |
| same_agent_and_thinking | True |
| same_bootstrap_limits | True |
| sources_unchanged | True |
| context_audits_passed | True |
| all_tool_results_captured | True |

完整系统文本哈希相同：True；全部配置文件字节哈希相同：True。

| helper | 版本 | 行数 | 启动命令次数 |
|---|---|---:|---:|
| enhance_workbook.py | 历史 | 286 | 1 |
| enhance_workbook.py | 今天旧 | 230 | 2 |
| enhance_workbook.py | 今天新 | 208 | 2 |

今天旧 runner 的 helper 写入哈希集合与历史相同：False。

完整 helper 源码差异：[查看 diff](../control_pairs/20261008T163759Z-90a05c03/tlc-helpers.diff)。

保留的目录差异：{'old_process_cwd': '/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01', 'new_process_cwd': '/runs/control/workspace', 'old_real_case': '/root/.openclaw/workspace/tool-modeling/SUB-MEM-OFFICE-01', 'new_real_case': '/runs/control/workspace', 'old_case_symlink': False, 'new_case_symlink': True}。

旧入口使用真实任务目录，新入口用逻辑目录指向本轮输出目录。这是被测 runner 行为，未强行改成同一种目录实现。

old：`runs/control-old-xlsx-tlc-20261008T163759Z-90a05c03/trajectory.json`。
原版 verifier：success；通用 verifier：success；最终接受：True。
工具类型：{'read': 7, 'exec': 14, 'process': 7, 'write': 2}；错误/非零退出：0；进程 kill：0。
另外，总退出码为 0 但包含 shell 错误的结果：1。
实际业务命令步骤（启动尝试数，包含未成功启动的命令）：{'inspect_input': [4, 6, 8, 12, 18], 'build_workbook': [16, 17], 'recalculate': [20], 'publish_csv': [22], 'verify': [22]}。
读取框架源码的步骤：[]。

步骤 16：总体 exit=0，结果中仍有 shell 错误（例如管道尾部掩盖前面命令失败）。

```text
/usr/bin/sh: 1: time: not found
```

new：`runs/control-new-xlsx-tlc-20261008T163759Z-90a05c03/trajectory.json`。
原版 verifier：success；通用 verifier：success；最终接受：True。
工具类型：{'read': 8, 'exec': 11, 'process': 6, 'write': 2}；错误/非零退出：0；进程 kill：0。
另外，总退出码为 0 但包含 shell 错误的结果：1。
实际业务命令步骤（启动尝试数，包含未成功启动的命令）：{'inspect_input': [5, 7, 9, 11], 'build_workbook': [14, 15], 'recalculate': [18], 'publish_csv': [14], 'verify': [19]}。
读取框架源码的步骤：[]。

步骤 14：总体 exit=0，结果中仍有 shell 错误（例如管道尾部掩盖前面命令失败）。

```text
/usr/bin/sh: 1: time: not found
EXIT=127
total 16
drwxr-xr-x. 2 root root 4096 Oct  8 16:48 .
drwxr-xr-x. 4 root root 4096 Oct  8 16:48 ..
-rw-r--r--. 1 root root  580 Oct  8 16:48 monthly_operations_summary.csv
-rw-r--r--. 1 root root  322 Oct  8 16:48 reconciliation_summary.csv
```

本次旧/新公式数：45 / 45；KPI 缓存相同：True；CSV 字节相同：True。

公式差异：
- `Executive_Summary!B13`：`=INDEX($E$13:$E$15,MATCH($B$12,$D$13:$D$15,0))` → `=VLOOKUP($B$12,$D$13:$F$15,2,FALSE())`
- `Executive_Summary!B14`：`=INDEX($F$13:$F$15,MATCH($B$12,$D$13:$D$15,0))` → `=VLOOKUP($B$12,$D$13:$F$15,3,FALSE())`
- `Executive_Summary!B15`：`=$B$5*$B$14` → `=B5*B14`
- `Executive_Summary!B16`：`=$B$6*$B$13*$B$14` → `=B6*B13*B14`

## OPM

| 控制项 | 匹配 |
|---|---|
| same_image_id | True |
| same_tool_versions | True |
| same_actual_task | True |
| actual_task_captured_correctly | True |
| same_visible_inputs | True |
| same_background_bytes | True |
| same_config_semantics | True |
| same_private_config_file_hashes | True |
| same_project_source_snapshot | True |
| same_process_environment | True |
| same_skill_registry | True |
| same_tool_registry_metadata | True |
| same_workspace_injection | True |
| same_full_initial_system_prompt | True |
| same_actual_model | True |
| same_agent_and_thinking | True |
| same_bootstrap_limits | True |
| sources_unchanged | True |
| context_audits_passed | True |
| all_tool_results_captured | True |

完整系统文本哈希相同：True；全部配置文件字节哈希相同：True。

| helper | 版本 | 行数 | 启动命令次数 |
|---|---|---:|---:|
| generate_and_run_batch.py | 历史 | 184 | 1 |
| run_batch_fill_render.py | 历史 | 52 | 1 |
| gen_field_values.py | 今天旧 | 88 | 1 |
| run_batch.py | 今天旧 | 50 | 1 |
| build_field_values.py | 今天新 | 116 | 1 |
| run_batch.sh | 今天新 | 25 | 1 |

今天旧 runner 的 helper 写入哈希集合与历史相同：False。

完整 helper 源码差异：[查看 diff](../control_pairs/20261008T163759Z-90a05c03/opm-helpers.diff)。

保留的目录差异：{'old_process_cwd': '/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01', 'new_process_cwd': '/runs/control/workspace', 'old_real_case': '/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01', 'new_real_case': '/runs/control/workspace', 'old_case_symlink': False, 'new_case_symlink': True}。

旧入口使用真实任务目录，新入口用逻辑目录指向本轮输出目录。这是被测 runner 行为，未强行改成同一种目录实现。

old：`runs/control-old-pdf-opm-20261008T163759Z-90a05c03/trajectory.json`。
原版 verifier：success；通用 verifier：failed；最终接受：False。
工具类型：{'read': 9, 'exec': 11, 'write': 3}；错误/非零退出：1；进程 kill：0。
另外，总退出码为 0 但包含 shell 错误的结果：0。
实际业务命令步骤（启动尝试数，包含未成功启动的命令）：{'check_fields': [6], 'extract_schema': [7], 'render_template': [10], 'execute_batch': [12], 'verify': [15]}。
读取框架源码的步骤：[]。

通用验收失败（保持原始产物）：

```json
[
  "mapping:applicant_01",
  "field_values:applicant_01",
  "mapping:applicant_02",
  "field_values:applicant_02",
  "mapping:applicant_03",
  "field_values:applicant_03",
  "mapping:applicant_04",
  "field_values:applicant_04",
  "mapping:applicant_05",
  "field_values:applicant_05",
  "mapping:applicant_06",
  "field_values:applicant_06",
  "mapping:applicant_07",
  "field_values:applicant_07",
  "mapping:applicant_08",
  "field_values:applicant_08",
  "mapping:applicant_09",
  "field_values:applicant_09",
  "mapping:applicant_10",
  "field_values:applicant_10",
  "summary:input_form"
]
```

失败步骤 12（exit=2），结果尾部：

```text
nclaw/workspace/tool-modeling/SUB-MEM-PDF-01/input/of306_aug2023.pdf /root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output/field_values/applicant_10.json /root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output/filled/applicant_10.pdf
+ /usr/bin/python3 /root/.openclaw/skills/pdf/scripts/convert_pdf_to_images.py /root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output/filled/applicant_10.pdf /root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output/rendered/applicant_10
Saved page 1 as /root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output/rendered/applicant_10/page_1.png (size: (772, 1000))
Saved page 2 as /root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output/rendered/applicant_10/page_2.png (size: (772, 1000))
Saved page 3 as /root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output/rendered/applicant_10/page_3.png (size: (772, 1000))
Converted 3 pages to PNG images
Batch complete.
/usr/bin/sh: 1: Bad substitution

(Command exited with code 2)
```

new：`runs/control-new-pdf-opm-20261008T163759Z-90a05c03/trajectory.json`。
原版 verifier：success；通用 verifier：success；最终接受：True。
工具类型：{'read': 10, 'exec': 12, 'write': 3}；错误/非零退出：0；进程 kill：0。
另外，总退出码为 0 但包含 shell 错误的结果：0。
实际业务命令步骤（启动尝试数，包含未成功启动的命令）：{'check_fields': [6], 'extract_schema': [7], 'render_template': [9], 'execute_batch': [13], 'verify': [16]}。
读取框架源码的步骤：[]。

本次旧/新清单：{'old': {'pdf': 10, 'png': 33, 'mapping': 10}, 'new': {'pdf': 10, 'png': 33, 'mapping': 10}}；所有字段值与页码相同：False。

旧 OPM 的 10 份映射均使用国籍文本 `United States of America`，通用规则期望 `United States`；
旧摘要中的 input_form 为 `input/of306_aug2023.pdf`，通用规则期望 `of306_aug2023.pdf`。
两类字面差异导致 21 项失败（10 份映射和 10 份 PDF 字段值，加 1 项摘要）；原版 verifier 允许这些表达并通过。
新 OPM 两种验收均通过。本轮不调整规则或产物，保留失败 trace。

## 解释范围

本次真实执行两套入口，没有用冻结历史 helper 代替模型生成。
如果今天旧 runner 也生成了不同于历史的 helper，说明相同旧入口在当前条件下也能出现变化；单凭历史/新版差异不能认定新 runner 是唯一原因。
各一轮不能估计哪一版更稳定，也不能定位服务端模型、采样或目录实现各自造成多少变化。
本轮每个新旧配对的完整初始系统文本哈希相同；这只证明本轮初始提示输入相同，不证明后续工具观察相同或与历史环境完全相同。
旧入口仍有模型预检，新入口没有；真实目录/软链接和实际进程 cwd 有差异，已保留在证据中。两轮均未读取框架源码。
调用数包含检查、读取、命令合并、等待轮询、失败和重试，不能单独代表业务处理量或性能。
