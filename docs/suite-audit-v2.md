# Suite v2 foundation audit — 2026-10-09

本轮修改保留 OpenClaw Agent、vendored PDF/XLSX Skill、ATIF 和运行镜像主流程。
正式范围固定为 XLSX TLC / Retail / Manufacturing / HR 和 PDF OPM / W-4 / SBA 1919。
不执行 CPU/OS replay，不生成 replay 镜像，不扩展第八个输入。

## 输入与来源边界

Retail 和 Manufacturing 已移除 deterministic 100k expansion。两者直接保留官方 PDF
原始发布表中的类别/行业层级、数值、抑制标记和注释，转录成不同布局的小型 XLSX。
这属于 **official raw-table transcription**，不是官方原生 XLSX，也没有恢复官方
XLSX 的样式、公式或图表。已尝试的 Census 原生文件下载返回 403；未取得原 PDF
字节，因此不提供臆造的官方文件 SHA256。输入 XLSX 和保留的官方文字提取证据分别有哈希。

HR 使用完整、未改写的缓存 XLSX，保留原四张表、格式、合并区域、层级和抑制值。
BLS 官方 ZIP 下载返回 403；实际来源明确为 GitHub cache。旧核对覆盖 825 个选中
详细职业的就业/年平均工资及 767 个已发布小时工资值；本轮额外核对正式 KPI 和图表
用到的 all-occupations 与五个主要职业组。没有声称官方 ZIP 字节一致、所有 1,401
记录全部核验，或年工资中位数/所有分位数全部验证。详见
[正式字段核对](../reports/hr-formal-kpi-provenance-v2.json) 和
[HR provenance](../datasets/xlsx/hr/provenance.json)。

TLC 保留历史生成 workbook：100k 真实 trip-record 样本，加全量清洗汇总。
它不是 TLC 发布的原生 XLSX，原上游字节下载链及精确日期不完整。
OPM 原官方输入同样保留历史下载日期缺失的限制。两者冻结现有输入哈希，不补造历史。

每个输入的 URL、实际来源、发布版本、下载日期或明确的缺失说明、SHA256、转换方式
和未验证字段位于 `datasets/{kind}/{dataset}/provenance.json`。
W-4 固定 2026 版；SBA 固定可填写 04/2024 版。SBA Box 重下载字节相同、七页文字
与旧 SBA.gov 文件一致，未核验官网原字节或 share 直接官网引用。2025 官网下载失败；
银行镜像不可填写不能用来断言未取得的官网字节性质。

## 原始 workbook complexity

| Input | Bytes / compressed XLSX | Sheets | Serialized used cells | Formulas | Charts | Styles | Merged ranges | Shared strings | Cross-sheet formulas |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| TLC | 12,278,348 | 7 | 2,501,211 | 36 | 2 | 21 | 0 | no | 8 |
| Retail | 10,084 | 2 | 512 | 0 | 0 | 1 | 0 | no | 0 |
| Manufacturing | 12,597 | 1 | 1,024 | 0 | 0 | 1 | 0 | no | 0 |
| HR | 289,615 | 4 | 44,958 | 0 | 0 | 27 | 2 | yes | 0 |

`complexity.json` 还包含每个 Sheet 的 row/column 最大已序列化坐标、populated cell、
样式 cell、合并范围和解压 package 大小。空的有样式 cell 计入 used，不计入 populated；
style 数是 cellXfs 条目数，不等同于有效视觉种类。该信息属于分析元数据，不进入任务 Prompt。
四者覆盖不同 Spreadsheet workload 形态；它们不是严格行业控制变量实验。

## 逐项检查

| 用户项目 | 当前处理及证据 |
|---|---|
| 1 | 正式 Retail/M3/HR 无 synthetic expansion；原始行表或未扩增原缓存；旧合成输入移到 `legacy/development-synthetic-v1/`。原生官方下载仍受上述限制。 |
| 2 | 保留各自 2/1/4 张表的不同结构；TLC 原七表保留，不强制跨领域同构。 |
| 3 | 公共 XLSX Prompt 无固定领域 Sheet、地址、row count 或 chart count；Agent inspect 后选择新增布局。 |
| 4 | KPI、单位、维度、scenario 和 chart 意义全部来自 manifest；业务变更不修改公共模板。 |
| 5 | 正式 manifest 不含结果、最终公式、地址、helper 或工具顺序；独立答案只在 verifier oracle `expected.json`。feature index 是 Agent 完成后申报的位置。 |
| 6 | 正式 XLSX 使用 `spreadsheet-semantic-v2`；通用原内容保留与 dataset oracle 分开。v1 仅用于冻结历史兼容 fixture。 |
| 7 | 逐 source cell/公式/默认及显式样式/number format，原表顺序、合并、名称、chart 类型及数据引用验证；另核验新增内容。测试拒绝删表、篡改数据、覆盖公式、删/改图表、改样式、写入原空白和追加虚构行等。不是字节或逐像素等同证明。 |
| 8 | 当前 README/status 指向 v2；历史报告明确标注旧合成阶段，不能证明当前输入/trace。 |
| 9 | 每个 XLSX provenance 冻结，Census 明确 raw-table fallback，HR 明确 cache 和核对范围。未取得官方字节，不声称此项达到原生官方文件身份验证。 |
| 10–11 | TLC 记录级样本与发布统计表分开描述；methodology 禁止直接用行业解释 CPU 差异。 |
| 12 | 四个输入均有独立复杂度 metadata 和输入 hash。 |
| 13–15 | 旧 runner/cases/prompt/session/成功产物冻结在仓库内；测试不再读取 sibling repo 或 ignored runs。当前 passed/skipped/failed/errors 以独立测试 JSON 为准。 |
| 16–18 | 正式 `artifacts/suite.json` 选择 canonical pack；共享 SHA256 objects 保存输入、Prompt、manifest、oracle、Skill/context、执行源、版本、验收和 trace，机器核对绑定。 |
| 19–21 | ATIF/tool events 明确是 execution evidence；完整工具链与最终有效执行分开，尚无 executable recipe。未来编译和执行均禁止 LLM 重新决策。 |
| 22 | 保存 helper、配置、数据、输出及运行中改写版本；passive capture 缺口写入 canonical metadata。不是完整 syscall provenance，最终有效切分仍需审核。 |
| 23–25 | 公共 PDF Prompt/公共 verifier 无 OF-306 字段/页面/固定调用次数；record count、页面、schema、mapping/rules 从 manifest 输入推导。 |
| 26–27 | SBA 04/2024 来源与选择理由准确；W-4 年份、URL、hash、5 页/48 字段冻结。 |
| 28 | 三个 PDF records 的 schema、固定数量、JSON hash、虚构隐私说明及生成方法冻结；W-4/SBA ordinal generator 字节 hash，OPM 为仓库内手工冻结 fixture，无随机 seed。 |
| 29–30 | 七输入 scope 固定；研究定位为 Agent/tool/CPU/OS characterization 和未来 deterministic replay，不是准确率榜单或行业排名。 |
| 31 | 新真实 Agent/独立验收、每条 canonical、XLSX 非默认场景及独立目录 legacy/unit/hash 回归分别核验。正式索引和 status 提供精确 run identity；仍有来源身份与未来 recipe 两类明确边界。 |

## Trace 和验收入口

正式选择以 [suite.json](../artifacts/suite.json) 为准；每项绑定当前 manifest hash、
canonical path/hash，XLSX 还绑定同一输出与 trace 的非默认场景验收报告。
[status.json](status.json) 记录当前结果，不再把被忽略的 `runs/` 路径当作发布证据。
Manufacturing 曾在来源说明误写 65 行；实际是 71 个发布行。修正 manifest provenance 后
重新真实运行；旧成功 pack 保留为被取代的证据，正式索引只选修正后的当前 hash。
TLC 第一条 v2 尝试在原内容验收时超过 30 分钟，CLI 未返回可用 session metadata，
因此没有被晋升为 canonical；[失败诊断](../reports/tlc-v2-timeout.json) 如实保留。
随后缓存同一工作簿对中的重复语义样式比较并重新真实运行，保留同样的验收条件。
后续严格检查发现初版 style 检查跳过了默认样式 cell。Retail/M3 的重算改写了字体
charset/scheme 与默认对齐属性。补全默认样式检查后，两例重新真实生成、独立验收、
场景重算和冻结；正式选择已换为修正后的轨迹，原输入和公共 Prompt hash 不变。
[修复证据](../reports/source-default-style-regression-v2.json) 记录了被取代与正式 run ID。
索引根据验收报告中的显式选择绑定 canonical，不猜测“最新目录”。

canonical pack 包含 original run ID、实际模型与 runtime image、完整源快照及 Skill
hash、工具调用/结果、helper 内容/改写版本、输入/输出和验收报告。验证不执行 helper，
也不调用模型。完整工具链保留，最终有效切分未审核，不冒充已能 deterministic replay。

```bash
make test
make regression
python3 scripts/freeze_suite_index.py --validate
python3 scripts/verify_canonical_outputs.py
# 重现独立发布树检查（先 git add 以选定检查的文件树）：
python3 scripts/check_self_contained.py
```

[独立测试报告](../reports/self-contained-tests-v2.json) 使用 `git archive` 导出的实际 staged
tree；目录不含旧仓库、Git history、runs、snapshots 或 qualification。
其中 unit tests 与 legacy artifact regression 不等同于真实 Agent 回归，场景重算属于
功能 QA，不是原 Agent 的 tool event，也不是 CPU/OS replay 实验。

## 最终回归结果

独立 staged tree 的 26 项测试全部通过：0 skipped、0 failed、0 errors。
仓库内 TLC/OPM legacy 回归通过，七份正式 canonical 的 hash/provenance 绑定通过，
从内容哈希对象恢复的七份产物均通过当前 verifier。最终真实 Agent run ID 与
canonical 选择见 [真实 Agent 回归](../reports/current-agent-regression-v2.json)；
[归档恢复报告](../reports/canonical-output-regression-v2.json) 同时冻结当前 verifier 源文件 hash。
四个 XLSX 共 11 个允许场景通过独立副本重算。
独立测试报告绑定执行检查时的文件树；测试后仅更新本节、README、status 与生成的回归报告，
不修改已通过检查的实现代码。以上结果不消除已列出的官方字节来源限制，也不代表 replay recipe 已完成。
