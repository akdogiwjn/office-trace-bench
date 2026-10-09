# Native XLSX input revision — 2026-10-09

本轮按用户提供的官方文件和 URL 替换 Retail / Manufacturing 正式输入。
公共 Prompt、Agent/Skill/Trace 框架、TLC 和三个 PDF 输入及 trace 保持现有版本。
七个 dataset 范围固定，CPU/OS replay 和复现镜像继续暂停。

## 文件与发布时期

| Dataset | 原生输入 | 原始结构 | 当前任务时期 |
|---|---|---|---|
| Retail | `mrtssales92-present.xlsx` | 35 个年度 Sheet，1992–2026 | July 2026；增长比较 June 2026 / July 2025，趋势 May–July 2026 |
| Manufacturing | `text.xlsx` | 8 张 Sheet，含七张 M3 发布表及原空表 | January–March 2025；March shipments；文件说明为 May 16, 2025 Benchmark Report |
| HR | `national_M2025_dl.xlsx` | 4 张原表，1,401 个职业/层级记录 | May 2025；任务和原 trace 不变 |

Retail 原始文件没有提供精确的发布日；冻结其下载日期、内嵌年份/月度标签、原文件 SHA256，
不把本次下载日期当成发布日。制造业按文件 source note 记录具体 benchmark revision。

Retail 和 Manufacturing 独立重下载成功，分别与用户文件逐字节相同。官方 URL 为
[Census MRTS](https://www.census.gov/retail/mrts/www/mrtssales92-present.xlsx) 和
[Census M3 benchmark](https://www.census.gov/manufacturing/m3/bench/text.xlsx)。
输入没有通过 openpyxl 重新保存或裁剪；manifest 的业务时期和独立 oracle 随文件同步更新，
公共 Prompt hash 不变。官方动态 URL 以后更新不会自动替换冻结输入。

## HR 来源补充，不重跑

用户从 [BLS 官方 ZIP](https://www.bls.gov/oes/special-requests/oesm25nat.zip) 下载、解压的
XLSX 与仓库当前输入逐字节相同，SHA256 为
`852250997ceff9b721ff68f63e877d818f9c1ec8b1b69dd367958faedd5282b2`。
当前环境独立重下载 ZIP 仍返回 403；核对证据明确区分用户提供的官方来源与 Agent 独立观察。
没有保存或臆造官方 ZIP SHA256，不把 XLSX 同哈希描述为 Agent 自己完成 ZIP 下载和解压。

该次 HR Agent 实际使用的缓存输入 provenance、manifest 和 canonical pack 保持原样。
新增 `datasets/xlsx/hr/provenance-supplement.json` 绑定原 provenance、manifest、输入、
canonical 与下载核对报告；suite index 同时验证补充证据。这避免仅改 provenance
导致旧 manifest/hash 失配，也避免为了 metadata 更新重新调用 LLM。

## 输入复杂度

| Input | XLSX bytes | Sheets | Serialized used cells | Formulas | Charts | Styles | Merged ranges | Shared strings |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Retail | 441,281 | 35 | 60,504 | 0 | 0 | 27 | 0 | yes |
| Manufacturing | 80,910 | 8 | 8,339 | 0 | 0 | 238 | 12 | yes |
| HR | 289,615 | 4 | 44,958 | 0 | 0 | 27 | 2 | yes |
| TLC | 12,278,348 | 7 | 2,501,211 | 36 | 2 | 21 | 0 | no |

这些是原始 spreadsheet 复杂度，不是统一记录数，也不能直接推导行业 CPU 排名。
本轮复用严格原内容保留 verifier，不为原生文件降低数据/公式/样式/图表等保护要求。

## Trace 与回归记录

新的 Retail / Manufacturing 必须由真实 Agent 成功运行、独立验收、场景重算并冻结成
canonical 后，才能更新 `artifacts/suite.json` 的正式选择。旧转录文件、manifest、预期值、
suite/index 和报告保存在 `legacy/suite-v2-transcription/`；旧 canonical pack 不覆盖。
TLC、HR 和三个 PDF 的 selected run ID 不因本次更新改变。

下载和字节核对见 [官方输入证据](../reports/official-native-input-provenance-v3.json)，
最终 run ID 见 [Agent 回归报告](../reports/current-agent-regression-v2.json)，
独立目录结果见 [测试报告](../reports/self-contained-tests-v2.json)，
归档恢复结果见 [当前 verifier 验收](../reports/canonical-output-regression-v2.json)。
历史转录阶段报告只对应当时的输入；当前原生输入回归结果如下。

## 已选定的两条新 trace

| Dataset | Original run ID | Agent wall seconds | Independent verifier seconds | Acceptance / scenarios |
|---|---|---:|---:|---|
| Retail | `xlsx-retail-20261009T101352Z-725a21b6` | 289.812 | 3.811 | success；Base / Higher / Lower 全通过 |
| Manufacturing | `xlsx-manufacturing-20261009T101352Z-bd60f53e` | 164.402 | 1.075 | success；Base / Expansion / Contraction 全通过 |

两次都保留严格原数据/样式验收，没有因采用原生文件放宽检查；工具链分别有 57 / 39 个调用。
这里的秒数属于真实 Agent 生成阶段墙钟时间，用来记录本次执行，不是 CPU/OS 性能结果。
旧 TLC、HR、OPM、W-4、SBA 的五条 selected canonical identity 与上一版一致。

## 最终独立回归

发布树通过 `git archive` 导出到独立目录；不包含 sibling repo、Git history、runs、
snapshots 或 qualification。**27 passed，0 skipped，0 failed，0 errors**。
旧 TLC/OPM 兼容回归通过；七个 canonical 的完整哈希及 provenance 绑定通过；
从共享对象恢复的七份正式产物均通过当前 verifier。四个 XLSX 共 11 个允许场景的报告
绑定到各自选定 trace 和 workbook。
测试报告绑定检查时的 staged tree；测试完成后只更新 README、本节、status 和两份
生成报告，实现代码及正式输入没有变化。未执行 CPU/OS replay。
