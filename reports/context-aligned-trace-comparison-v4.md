> 历史证据：本报告保留原实验及其契约，不代表当前冻结 suite。当前输入、trace 选择与来源边界见 [suite 审计](../docs/suite-audit-v2.md)。

# 共用模板与背景上下文回归

回归结果：`success`。

TLC/OPM 使用按类型共用的 xlsx.txt/pdf.txt。领域变量由 manifest 提供；渲染后旧业务、执行与 QA 原文保持一致。
本轮恢复六份必要背景说明、agent-browser，且仅注册当前 Office Skill；不导入历史任务、产物或会话。

| 用例 | 历史 steps / calls | 上轮仅恢复任务文本 | 本轮共用模板与上下文 | 业务回归 / 上下文审计 |
|---|---:|---:|---:|---|
| TLC | 35 / 41 | 18 / 19 | 20 / 25 | success / True |
| OPM | 19 / 25 | 19 / 26 | 16 / 21 | success / True |

## TLC

新运行：`runs/xlsx-tlc-20261008T150146Z-1742e186`。

任务文本一致性：True；背景文件前后未变：True。
Skill 注册文本哈希与历史一致：True。
工具类型（历史 / 本轮）：{'read': 1, 'exec': 27, 'process': 12, 'write': 1} / {'read': 6, 'exec': 11, 'process': 6, 'write': 2}。

| helper | 版本 | 行数 | 写入次数 | 启动命令次数 |
|---|---|---:|---:|---:|
| enhance_workbook.py | 历史 | 286 | 1 | 1 |
| xlsx_enhance_helper.py | 本轮 | 224 | 1 | 2 |

projectContext 字符（历史 / 本轮）：11727 / 11727；系统文本总字符：30179 / 30146。
系统动态文本未完整封存；总长度的剩余差异不能仅凭元数据定位，不能据此宣称全部系统文本一致。

本轮非零退出或错误结果：2；进程 kill：0。
expected.json 引用步骤：[]。

生成 helper 的源码哈希、每次启动及最终状态记录在 JSON 报告中；调用总数含读取、写入、轮询、失败和重试。

失败步骤 15（exit=127）：

```text
/usr/bin/sh: 1: time: not found

Command not found
```

失败步骤 17（exit=2）：

```text
total 12024
drwxr-xr-x. 2 root root     4096 Oct  8 15:06 .
drwxr-xr-x. 4 root root     4096 Oct  8 15:01 ..
-rw-r--r--. 1 root root 12283903 Oct  8 15:06 monthly_operations_report.xlsx
-rw-r--r--. 1 root root      580 Oct  8 15:06 monthly_operations_summary.csv
-rw-r--r--. 1 root root      322 Oct  8 15:06 reconciliation_summary.csv
-rw-r--r--. 1 root root    10066 Oct  8 15:05 xlsx_enhance_helper.py
--- running recalc ---
{
  "status": "success",
  "total_errors": 0,
  "error_summary": {},
  "total_formulas": 47
}
/usr/bin/sh: 1: Bad substitution

(Command exited with code 2)
```

time 未安装使启动命令退出 127，Python helper 尚未开始；成功执行次数另见完整 trace 与摘要。

重算命令输出后，/bin/sh 因不支持 Bash 的 PIPESTATUS 下标语法而退出 2。
这个辅助 shell 错误与重算 JSON、公式错误数和独立验收结果分别记录。

重算命令次数（历史 / 本轮）：2 / 1。
公式数量：45 / 47。核心 KPI 缓存一致：True；CSV 字节一致：True。

公式差异：
- `Executive_Summary!B13`：`=INDEX(E13:E15,MATCH(B12,D13:D15,0))` → `=VLOOKUP($B$12,$D$13:$F$15,2,FALSE())`
- `Executive_Summary!B14`：`=INDEX(F13:F15,MATCH(B12,D13:D15,0))` → `=VLOOKUP($B$12,$D$13:$F$15,3,FALSE())`
- `Executive_Summary!B17`：`None` → `=B16/B15`
- `Executive_Summary!B18`：`None` → `=B16-B6`

## OPM

新运行：`runs/pdf-opm-20261008T151503Z-e61d4442`。

任务文本一致性：True；背景文件前后未变：True。
Skill 注册文本哈希与历史一致：True。
工具类型（历史 / 本轮）：{'read': 10, 'exec': 12, 'write': 3} / {'read': 11, 'exec': 8, 'write': 2}。

| helper | 版本 | 行数 | 写入次数 | 启动命令次数 |
|---|---|---:|---:|---:|
| generate_and_run_batch.py | 历史 | 184 | 1 | 1 |
| run_batch_fill_render.py | 历史 | 52 | 1 | 1 |
| make_field_values.py | 本轮 | 162 | 1 | 1 |
| run_batch.py | 本轮 | 131 | 1 | 1 |

projectContext 字符（历史 / 本轮）：11727 / 11727；系统文本总字符：29663 / 29630。
系统动态文本未完整封存；总长度的剩余差异不能仅凭元数据定位，不能据此宣称全部系统文本一致。

本轮非零退出或错误结果：0；进程 kill：0。
expected.json 引用步骤：[]。

生成 helper 的源码哈希、每次启动及最终状态记录在 JSON 报告中；调用总数含读取、写入、轮询、失败和重试。

新产物清单：{'pdf': 10, 'png': 33, 'mapping': 10}。全部字段值和页码一致：True。
批次汇总是 Agent 自报计数；应结合保留的最终驱动、exec 结果、完整 trace 和独立产物清单阅读。

本轮批次运行日志的 RUN 条目：{'convert_pdf_to_images': 11, 'fill_fillable_fields': 10}；驱动在日志写入前使用 subprocess.run(check=True) 完成各调用。

## 可比性边界

本轮检查了历史注入文件长度、Skill 注册文本的准确哈希、工具 schema 长度、workspace 路径，并冻结当前背景文件的实际字节。
历史未记录完整背景文件和配置哈希，动态系统文本、日期及服务端模型状态也不能据此证明一致。因此不宣称完整历史模型输入逐字相同。
这些检查消除了已发现的 runner 上下文差异；仍不能保证独立模型生成相同脚本。业务通过与负载相同是两种验收。
新领域尚未实际生成 trace。下一阶段用同一模板接入新 manifest、输入与独立预期；离线 replay 镜像继续后置。
