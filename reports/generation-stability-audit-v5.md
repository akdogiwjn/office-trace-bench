> 历史证据：本报告保留原实验及其契约，不代表当前冻结 suite。当前输入、trace 选择与来源边界见 [suite 审计](../docs/suite-audit-v2.md)。

# 旧版稳定性与新版比较口径复核

旧版入口每次清空任务目录并排除历史 session，确实重新请求模型生成；不能直接解释为固定脚本回放。
已核实 KP 原始记录及旧项目两轮的业务任务文本一致；旧 Shell 入口会去掉 prompt 文件末尾换行，逐字比较时须记录该区别。

| 历史 XLSX 生成 | helper 名称 | 最后一版完整写入行数 | 源码 SHA-256 前缀 |
|---|---|---:|---|
| kp_original | enhance_workbook.py | 256 | c8a244422eb6 |
| legacy_first | enhance_workbook.py | 234 | 14bff46f35af |
| legacy_second | enhance_workbook.py | 286 | 2b8fe9c6c839 |

同名 helper 的内容并没有被入口固定；原提示词也未指定 enhance_workbook.py 的名称或完整源码。
历史 KP PDF 使用过 Python 映射生成器与 Shell 批次驱动，旧项目另两轮使用 Python 驱动；模型自编驱动与 Skill 的固定工具脚本要分别比较。

当前新项目的三组运行分别使用：简化任务文本、恢复原任务文本、恢复背景说明和 Skill 注册集合。
三组模型输入不同，因此不能作为“最终新版在同一配置下重复生成”的稳定性样本。

已证明：初期改造改变了任务和背景输入；后续修正恢复了原业务要求及可核验历史背景元数据。
未证明：最终新版是否比旧 runner 更不稳定；是否存在某个剩余运行差异导致脚本结构变化。
需要旧/新 runner 在当前同一环境、相同输入和明确冻结设置下重复对照，才能区分 runner 差异与生成波动。
此复核只分析已保存证据，没有再请求模型。

详细原始路径、session ID、helper 每次写入的哈希见同名 JSON。
