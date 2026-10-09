> 历史证据：本报告保留原实验及其契约，不代表当前冻结 suite。当前输入、trace 选择与来源边界见 [suite 审计](../docs/suite-audit-v2.md)。

# 新旧 trace 对比

比较结果：`success`。旧轨迹为 2026-07-30 的历史真实运行，新轨迹为 2026-10-08 的通用化真实运行。

| 用例 | ATIF steps（旧 → 新） | 工具调用（旧 → 新） | process 调用（旧 → 新） | 业务回归 |
|---|---:|---:|---:|---|
| XLSX / TLC | 35 → 32 | 41 → 36 | 12 → 5 | success |
| PDF / OPM | 19 → 16 | 25 → 27 | 0 → 0 | success |

两组输入和 Skill 与导入时冻结的 SHA-256 一致；OpenClaw 2026.6.6、模型 deepseek/deepseek-v4-flash、thinking high 一致。
新输出通过 Agent 内验收、独立通用验收、原 verifier；历史输出也通过新旧 verifier。每条工具调用都有对应结果。

## XLSX / TLC

模板检查、构建工作簿、重算、发布 CSV、业务验收均保留。原始 100,000 行数据、原公式和原图表通过保留检查；
新旧均为 8 个 sheet，核心 KPI 缓存值相同，两个 CSV 字节相同，新旧重算报告均无公式错误。
旧 trace 真正调用 recalc.py 2 次，新 trace 1 次。旧 summary 自报一次，与 trace 不符；本比较以 trace 为准。
旧 trace 主动结束了 4 个检查进程；新 trace 没有 process kill。新第 24 步因 time 命令不存在而退出 127，
第 25 步直接执行 builder 成功；首次失败没有开始构建。因此有 2 次启动尝试、1 次成功构建。
新建脚本写入了两版，第一版尚未执行便修正了单元格布局。
公式总数 45 → 48：B13/B14 由 INDEX/MATCH 改为 VLOOKUP，结果相同；新增 B17/B18/B19 展示差额与增幅。

## PDF / OPM

可填写检查、字段抽取、空白模板渲染、映射生成、批量填写/渲染、业务验收均保留。
两边均为 10 份 PDF、10 份映射 JSON、33 张 PNG；10 人的全部映射字段值及页码相同。
两边均使用 Skill 完成 10 次填写、11 次渲染（模板 1 次 + 填写后 10 次），受保护字段均保持空白。
旧版把映射生成与填写渲染拆成两个 helper；新版合并为一个 helper，执行一次。
新 trace 有两个辅助 exec 退出 1：第 5 步 which 查询未安装的可选工具；第 13 步把 protected_blank 的字段对象当作键，出现 TypeError，
第 14 步用正确的字段集合重新检查通过。
实际批量处理和验收均成功。完整结果片段见 JSON 的 command_failures。

## 结论与范围

这些证据支持 TLC/OPM 通用化的业务兼容性。步骤数、脚本布局、重算次数和额外展示公式不同，
因此不能将这两组 trace 视为严格相同的资源负载，也不能据此得出性能提升结论。
阶段覆盖按真实 exec 匹配；新版空白渲染在成功执行的 batch helper 内，结合此前写入的源码和已验收的 PNG 确认。
不把 read 一个脚本当成执行，也不把 batch 的一个工具调用误计为一次填写。

API 凭据来源另见 credential-provenance.json；只记录当前认证解析结果和脱敏指纹，没有保存完整 key。

TLC 新 trace：`runs/xlsx-tlc-20261008T115345Z-63218840/trajectory.json`

OPM 新 trace：`runs/pdf-opm-20261008T115600Z-aa170fa3/trajectory.json`

重建此报告：`python3 scripts/compare_baseline_traces.py`
