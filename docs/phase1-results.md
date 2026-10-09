> 后续进展：共用模板与可核验背景上下文回归已通过，见 [本轮对比](../reports/context-aligned-trace-comparison-v4.md)。下文保留当时记录。

# 第一阶段结果

当前 TLC/OPM 已恢复旧提示词主体并重新真实运行，两轮均通过新旧验收。
最新结果见 `docs/prompt-restoration-results.md` 与 `reports/prompt-restored-trace-comparison-v2.md`。
以下计数描述第一轮简化提示词的历史结果，不是当前最新运行。

通用化与 TLC/OPM 回归已完成。运行镜像为 `office-trace-bench:runtime`，
基于原 OpenClaw 2026.6.6 / Node 24.14.0，Python 3.12.3、LibreOffice 24.2.7.2、Poppler 24.02.0。
模型为 `deepseek/deepseek-v4-flash`，使用现有宿主配置的只读副本。

- 八项测试通过；封存产物同时通过新旧验收器。
- OPM：16 个 ATIF steps / 27 个工具调用，十份 PDF、33 张 PNG。
- TLC：32 个 ATIF steps / 36 个工具调用，八个工作表，48 个公式，零重算错误。
- 两个新运行均通过 Agent 内验收、独立重验和旧 verifier；源码快照未改变，
  trace 未引用历史成功产物或其他运行目录。完整记录见 `docs/status.json` 的证据路径。

新 trace 的步骤数与旧 trace 不要求相等；任务完成、输入保护和业务验收兼容性是本阶段目标。
没有从这两个运行推导 CPU/OS 性能结论。

新旧 trace 的逐项对比见 `reports/trace-comparison-v1.md` 与对应 JSON。
核心 KPI、CSV 和 PDF 字段映射保持一致。旧 TLC 实际重算两次，新 TLC 重算一次；
新版另有额外展示公式和辅助命令重试，报告保留这些差异，不能按完全相同的负载解释。
API 认证来源和脱敏指纹见 `reports/credential-provenance.json`；该指纹是事后当前配置检查，
原运行没有记录请求时的密钥指纹。

提示词改动与可比性审计见 `reports/prompt-comparison-v1.md`。目前 baseline_accepted 表示
业务回归及来源审计通过，不表示旧程序负载保持一致；新 trace 尚不能替换旧 trace 用于
判断通用化前后的资源消耗变化。

初期一次容器配置初始化失败、一次 OPM 运行曾读取历史成功产物，均保留为开发证据并排除。
正式 OPM 回归在仅暴露当前代码、输入和自身结果目录的容器内重新执行。TLC 使用早期代码
快照布局，经事后核对确认源码未改变且没有历史/其他运行引用；当前 runner 已统一使用独立
`.snapshots/` 与单次结果目录挂载。

下一阶段加入 Retail/MRTS、Manufacturing/M3、Workforce/OEWS、IRS W-4、SBA 1919 候选，
每个实例独立冻结输入与预期并生成真实 trace。所有实例 trace 可生成后再讨论离线复现镜像。
