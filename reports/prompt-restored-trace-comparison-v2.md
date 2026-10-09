> 历史证据：本报告保留原实验及其契约，不代表当前冻结 suite。当前输入、trace 选择与来源边界见 [suite 审计](../docs/suite-audit-v2.md)。

# 恢复旧提示词后的真实运行对比

业务回归与提示词恢复检查：`success`。

历史 trace、第一轮简化提示词 trace 和本轮恢复提示词 trace 均保留；本轮使用同一个 runtime 镜像和同一个 DeepSeek 模型。

| 用例 | 历史：steps / calls | 简化提示词：steps / calls | 恢复提示词：steps / calls | 新旧验收 |
|---|---:|---:|---:|---|
| TLC | 35 / 41 | 32 / 36 | 18 / 19 | success |
| OPM | 19 / 25 | 16 / 27 | 19 / 26 | success |

## TLC

新运行：`runs/xlsx-tlc-20261008T123533Z-e0fe46a7`。

恢复路径和环境措辞后，实际 task.prompt 与历史 prompt 的业务、执行和 QA 原文完全相同。原 verifier 作为冻结输入执行，通用验收在 Agent 结束后独立执行。

| helper | 历史 | 本轮 |
|---|---|---|
| enhance_workbook.py | 286 行；1 次写入；1 次启动命令 |  |
| enhance_workbook.py |  | 263 行；1 次写入；2 次启动命令 |

框架代码引用步骤：[]；expected.json 引用步骤：[]。
非零退出或错误结果：1 个；主动终止进程：0 个。完整调用及结果都在 trajectory.json/tool_events.json 中。

本轮先尝试 time python3 enhance_workbook.py，因 time 不存在退出 127，Python 未启动；随后直接执行成功。
因此上表是两次启动命令、一次真正的 helper 执行；Agent 摘要也记录了这个失败启动。
工具类型（历史 → 本轮）：exec 27 → 11；process 12 → 3。
本轮把部分检查、CSV 发布和验收合并到同一 exec，且原来的四次检查进程终止没有重现；调用减少不能解释为删除同等数量的业务操作。

重算实际命令次数：历史 2，简化提示词 1，本轮 1。
公式数量：历史 45，本轮 48。核心 KPI 缓存值一致：True；两个 CSV 字节一致：True。

公式差异：
- `Executive_Summary!B13`：`=INDEX(E13:E15,MATCH(B12,D13:D15,0))` → `=VLOOKUP($B$12,$D$13:$F$15,2,FALSE())`
- `Executive_Summary!B14`：`=INDEX(F13:F15,MATCH(B12,D13:D15,0))` → `=VLOOKUP($B$12,$D$13:$F$15,3,FALSE())`
- `Executive_Summary!B19`：`None` → `=Reconciliation!B4`
- `Executive_Summary!B20`：`None` → `=Hourly_Summary!B33`
- `Executive_Summary!B21`：`None` → `=Payment_Summary!H2`

## OPM

新运行：`runs/pdf-opm-20261008T124346Z-f0f172a6`。

恢复路径和环境措辞后，实际 task.prompt 与历史 prompt 的业务、执行和 QA 原文完全相同。原 verifier 作为冻结输入执行，通用验收在 Agent 结束后独立执行。

| helper | 历史 | 本轮 |
|---|---|---|
| generate_and_run_batch.py | 184 行；1 次写入；1 次启动命令 |  |
| run_batch_fill_render.py | 52 行；1 次写入；1 次启动命令 |  |
| gen_field_values.py |  | 74 行；1 次写入；1 次启动命令 |
| run_batch.sh |  | 29 行；1 次写入；1 次启动命令 |

框架代码引用步骤：[]；expected.json 引用步骤：[]。
非零退出或错误结果：0 个；主动终止进程：0 个。完整调用及结果都在 trajectory.json/tool_events.json 中。

本轮 10 份 PDF、10 份映射、33 张 PNG。全部字段值及页码与历史一致：True。
Agent 汇总填写/渲染次数：10 / 11。

## 可比性边界

恢复旧提示词消除了大幅重写任务约束这个变量，但独立 Agent 会话仍可能生成不同 helper、公式和检查步骤。
后续审计发现背景 workspace 文件及 Skill 注册集合也与旧版不同；完整模型上下文尚未对齐，详见 agent-context-audit-v3.md。
调用总数包含读取、检查、写文件、进程轮询和失败尝试；不能将它直接当作业务操作次数或资源消耗。
本轮新 trace 仍是独立生成任务的证据。比较框架或操作系统性能时，应使用同一份固定 trace/helper，并另行保证运行环境一致。
