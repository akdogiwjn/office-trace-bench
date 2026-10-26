# Agent trace 与 replay 仓库交接

本仓库保存真实 Agent 运行的输入、Prompt、执行上下文、成功 trace 及验证证据。
[office-trace-replay](https://github.com/akdogiwjn/office-trace-replay) 保存从这些证据整理的
确定性执行、人工适配用例、离线镜像和性能分析。本次同步不重新生成 trace，不重跑 workload，
不将 replay 的执行脚本或最新版 verifier 覆盖到历史 canonical 源快照。

## 集合与来源

- `artifacts/suite.json` 保留原七项 Agent suite：TLC、Retail（Census）、Manufacturing（Census）、
  HR（全国 OEWS）、OPM、IRS W-4、SBA 1919。原资格报告保持不变。
- `artifacts/extensions.json` 单独关联 Industry Productivity 的原始输入、manifest 和成功
  canonical。原运行 ID 为 `xlsx-industry_productivity-20261019T043257Z-06a71220`。
- replay 当前正式 XLSX 为 TLC、HR Metro、Retail Online、Industry Productivity；PDF 为
  OPM、IRS W-4、SBA 1919。原 Census Retail/Manufacturing、全国 HR 仍为可显式运行的历史对照。
- HR Metro、Retail Online 是 replay 内的 `manual_workflow_adaptation`，没有本仓库的 Agent
  parent run。本次不伪造其 trajectory，也不复制 replay 准备结果充当 Agent 生成数据。

## Industry Productivity

输入为用户确认从 BLS 官方下载的完整 `labor-productivity-detailed-industries.xlsx`，SHA256 为
`9c1213923977e6dcefd20b6185537434e9057428cb9a16b3329a8ccb4dd117dd`。
独立重下载曾返回 HTTP 403；原 provenance 保留该事实，不将用户来源确认写成独立字节核验。

Annual、MachineReadable、ReadMe 全部保留，业务计算使用 Annual，不重复汇总长表/宽表两种表示。
新增验证代码区分 loop 与 independent。canonical 内保存的是原运行时源快照，后续验证代码
变化不改写历史 trace 或其成功结果。

检查输入和 trace 的机器绑定，不执行工作簿或 helper：

```bash
python3 scripts/freeze_trace.py --validate \
  artifacts/canonical/xlsx/industry_productivity/xlsx-industry_productivity-20261019T043257Z-06a71220
python3 scripts/freeze_suite_index.py --validate
python3 -m unittest tests.test_industry_extension -v
```

## 对应 replay 版本

交接参考为 replay `main` 提交 `c92c851cff53a0ed448bc8e095bfb04164afca68`，其 v12 裸镜像
七个正式用例已有单轮功能证据。Industry Productivity 的 parent canonical SHA256 为
`b3393b732fc10ead2557db2230d2cff231d1a297d17aff3d4db665e6926db8e1`，与本仓库一致。
replay 的功能/独立验收和性能数据由 replay 仓库单独维护；本次提交不构成重新验收。

## 本次提交检查（2026-10-26）

24 项定向单元测试通过，覆盖新增 canonical 绑定、输入篡改拒绝、验证 scope、源代码副本、
既有 PDF/XLSX 小 fixture、Agent 隔离及归档 CLI。原七项 suite 的 canonical/provenance
绑定检查通过；新增 Industry canonical 的全部对象和输入绑定检查通过。未运行完整测试套件、
大表结果复验、Agent、replay、LibreOffice 或性能采集。
