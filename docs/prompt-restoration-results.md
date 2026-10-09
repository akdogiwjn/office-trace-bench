> 历史阶段记录，当前契约以 [suite 审计](suite-audit-v2.md) 为准。旧模板和合成扩增不属于当前正式输入。

> 后续进展：共用模板与可核验背景上下文回归已通过，见 [本轮对比](../reports/context-aligned-trace-comparison-v4.md)。下文保留当时记录。

# 旧提示词恢复与重新执行

TLC/OPM 当前通过 manifest 的 prompt_template 字段选择旧版兼容提示词，模板哈希也被冻结。

- TLC：业务、执行和 QA 原文保留；只参数化 workspace、将 fresh VM 改为 fresh trace-generation container、将 packaged openpyxl 描述改为 installed openpyxl。
- OPM：业务、执行和 QA 原文保留；只参数化 workspace 并修改 fresh VM 的环境描述。
- 原验收脚本按原文件名放回 input，并冻结其哈希。Agent 按原命令验收，Agent 结束后再运行通用独立验收。
- 两轮均使用已有 office-trace-bench:runtime 镜像和 deepseek/deepseek-v4-flash，无需重新构建镜像。
- 10 项测试通过，其中包括原提示词约束完整保留、模板变更无法绕过哈希检查。

| 用例 | 本轮运行 | steps / calls | 业务验收 |
|---|---|---:|---|
| TLC | xlsx-tlc-20261008T123533Z-e0fe46a7 | 18 / 19 | 原验收、独立通用验收、原验收器重验均 success |
| OPM | pdf-opm-20261008T124346Z-f0f172a6 | 19 / 26 | 原验收、独立通用验收、原验收器重验均 success |

两轮代码快照哈希均保持不变，trace 未引用历史成功产物。
原 prompt 和所有历史运行保持原样。第一轮简化提示词运行保留作为对照，不覆盖旧负载基准。

TLC 实际重算一次，无公式错误；第一次以 time 启动 helper 的命令失败，随后直接执行成功，
helper 真正运行一次。现有镜像没有 time，本轮保留这次失败，不用删除日志或重跑来掩盖它。
TLC 仍有 48 个公式，旧 trace 为 45 个；新增的三个参考指标以及 INDEX/MATCH 与 VLOOKUP 差异见对比报告。
OPM 仍为 10 份 PDF、10 份映射与 33 张 PNG；本轮 Agent 选择 Python 映射生成器加 Bash 批量驱动，
旧版则使用两个 Python helper。这是重新生成的脚本，尚不是固定负载移植。

本轮没有读取通用框架代码或 expected.json。恢复旧提示词减少了这些额外探索，
但无法保证独立 Agent 会话有相同脚本、公式和工具序列，因此不宣称资源负载与旧版完全相同。

后续完整上下文审计还发现了未对齐的控制变量：新 runner 排除了宿主 workspace 和 skills，
新运行的 AGENTS.md 等背景文件及可用 Skill 注册集合与旧版不同，并新增 BOOTSTRAP.md。
恢复 task.prompt 只恢复了用户任务文本，尚未恢复完整模型输入；详见
`reports/agent-context-audit-v3.md`。这些差异可能影响行为，不能把当前差异全部解释为模型随机性。

证据：reports/prompt-restoration-v1.json、reports/prompt-restored-trace-comparison-v2.md、
reports/prompt-restored-trace-comparison-v2.json，以及各 run 下的 task.prompt、trajectory.json、
independent_verification.json、legacy_verification.json 和 baseline_acceptance.json。
