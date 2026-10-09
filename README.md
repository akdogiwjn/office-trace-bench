# Office Trace Bench

本项目冻结七个 Office workload，用于 Agent 轨迹、工具工作量及后续 CPU/OS 工作量研究。
现有 OpenClaw Agent、PDF/XLSX Skill 和 ATIF 导出框架保持使用。真实 Agent 在运行镜像中生成
trace；后续离线工具 replay 以冻结证据为输入，不重新调用 LLM。当前尚无可执行 recipe、
离线 replay 镜像或 CPU/OS 性能结论。

正式输入、来源限制和逐项回归状态见 [原生输入更新审计](docs/native-input-update-v3.md)；研究边界见
[methodology](docs/methodology.md)。测试结果以 [独立目录测试报告](reports/self-contained-tests-v2.json)
为准：当前原生输入版本为 **27 passed、0 skipped、0 failed、0 errors**。
七个正式 dataset 均已由真实 Agent 成功运行并冻结；归档产物恢复后通过当前 verifier，
四个 XLSX 的 11 个场景重算通过，旧 TLC / OPM 兼容回归通过。
详见 [真实 Agent 回归](reports/current-agent-regression-v2.json) 和
[归档恢复验收](reports/canonical-output-regression-v2.json)。

| Dataset | 正式输入形态 | 边界 |
|---|---|---|
| XLSX TLC | 历史生成的真实 trip-record 样本与全量汇总 workbook | 100k 真实样本记录，25 列；不是 TLC 官方原生 XLSX，没有 synthetic shard |
| XLSX Retail | Census 原生 MRTS 历史 XLSX | 保留 1992–2026 共 35 张原表；任务聚焦 2026 年 7 月；独立官方下载字节一致 |
| XLSX Manufacturing | Census 原生 M3 benchmark XLSX | 保留 8 张原表，含 2025 年 1–3 月七张发布表；May 16, 2025 revision；独立官方下载字节一致 |
| XLSX HR | 未扩增、未改写的 May 2025 OEWS XLSX | 保留 4 张原表及 1,401 个职业/层级记录；与用户官网下载文件字节一致，既有缓存输入 trace 保留 |
| PDF OPM | OF-306 August 2023 + 冻结虚构记录 | 3 页、38 字段；历史官网下载的精确日期未保留 |
| PDF IRS W-4 | IRS 原始 2026 W-4 + 可复现虚构记录 | 5 页、48 字段；官方 URL 与 SHA256 冻结，不能静默更新年份 |
| PDF SBA 1919 | 可填写的 04/2024 表单 + 可复现虚构企业记录 | 7 页、127 字段；不是当前 2025 版；来源与核对边界见下文 |

Retail/M3 直接使用完整官方原生文件，原始字节与独立官网下载一致；不转录、不扩增，
不统一成 100k × 16 模板。历史转录输入及其验收记录已归档到
`legacy/suite-v2-transcription/`，旧 canonical pack 保持原样。HR 用户提供的官方 ZIP
解压 XLSX 与已有缓存文件字节完全一致，因此保留原 manifest 和 trace；新增
[provenance supplement](datasets/xlsx/hr/provenance-supplement.json) 绑定官方链接、输入哈希、
既有 manifest/canonical 和下载核对报告。原 provenance 仍准确记录该次运行用缓存，
不改写历史。当前环境的 BLS ZIP 重下载仍返回 403，官方 ZIP 获取与解压由用户提供，
没有独立 ZIP 字节核验。详见 [下载证据](reports/official-native-input-provenance-v3.json)。
旧三个 synthetic-expanded workbook 和 builder 位于 `legacy/development-synthetic-v1/`，
仅是历史开发对照，既不在正式 suite 中，也不进入 Agent 输入快照。

SBA 实际取自 `sba.app.box.com` 公开链接。重复下载字节一致，七页规范化文字与 SBA.gov
旧版 PDF 一致；未核验官网原 PDF 字节，未找到官网对具体 share 的直接引用。选择 04/2024
是为了固定原生可填写任务。当前 2025 官网下载失败；下载到的银行镜像没有 AcroForm，
这不证明未取得的官网 2025 文件不可填写。详见 [SBA provenance](datasets/pdf/sba1919/provenance.json)。

## 从独立 checkout 检查

```bash
python3 office.py list
make test
make regression
python3 scripts/freeze_suite_index.py --validate
python3 scripts/verify_canonical_outputs.py
```

需要 Python 3.11+ 和 Pillow。纯 Python 依赖从仓库内 vendored wheels 引导加载；宿主若没有
Pillow，可在自己的虚拟环境中安装。无需旁边的旧仓库、`runs/`、`qualification/` 或开发机
绝对路径。`make regression` 仅检查仓库内的 TLC/OPM 冻结 legacy fixture；不调用模型，
也不等同于新的真实 Agent 运行。历史 runner、提示词、输入、成功产物和 session 均在 `legacy/`。

## 真实 Agent trace 生成

```bash
make image
python3 office.py run --kind xlsx --dataset retail --config /path/to/openclaw-config --model deepseek/deepseek-v4-flash
python3 office.py run --kind pdf --dataset irs_w4 --config /path/to/openclaw-config --model deepseek/deepseek-v4-flash
python3 scripts/accept_baseline.py runs/RUN_ID
python3 scripts/freeze_trace.py runs/RUN_ID
```

`--config` 是宿主配置目录，含 openclaw.json，只读挂载到一次性容器；镜像中的
`/root/.openclaw` 是容器路径。API key 不进入项目或 canonical pack。运行镜像当前面向
ARM64、CPython 3.12，并使用已有 OpenClaw 基础镜像；其他架构需对应依赖。

公共 `prompts/xlsx.txt` 只描述 inspect → 根据 manifest 语义增强 → 重算 → 验收流程。
公共 `prompts/pdf.txt` 从 manifest 和 records 得到字段、业务规则、人数和页面规模。
所有 XLSX 业务 KPI、单位、维度、允许场景和图表语义来自 manifest；没有规定最终公式、
单元格、Sheet 名、脚本名或工具顺序。Agent 自行选择实现，并通过 workbook_features.json
登记位置。PDF 字段 ID 是输入表单映射，不是公共提示词硬编码。

XLSX 通用验证分别检查原工作簿的 worksheet 保留及相对顺序、逐单元格数据和公式、
原图表类型及数据引用、默认与显式样式、合并区域和名称，以及新增公式依赖、KPI 缓存、场景、图表、QA
和交付文件。它不要求全局固定行列数、Sheet 数或图表数。独立预期保存在 expected.json，
不属于任务语义要求。重算后的数值允许有限序列化误差；这不是 OOXML 字节或视觉逐像素
等同证明。非默认场景通过额外临时副本重算验证，不混入原 Agent tool_events。

每次运行冻结所选 dataset、代码、Prompt、Skill 和背景上下文；Agent 只看到该只读快照及
自身可写 workspace，不看到历史成功产物或其他 runs。原始 session 必须匹配返回的 session
metadata，禁止选择“最新 session”。每条 trace 保留失败尝试、改写、重试、process 和验收事件。

## 正式 trace artifacts

`artifacts/suite.json` 选择每个 dataset 的唯一 canonical run 和 canonical metadata 哈希。
`artifacts/canonical/` 保存 trajectory、tool_events、切分索引和 canonical.json；共享
`artifacts/objects/sha256/` 保存按内容哈希寻址的输入、全部执行源快照、Skill、helper 及
改写版本、中间配置/数据、输出和验收报告。它们属于正式 Git artifact，不依赖被忽略的 runs。
验证 pack 不执行其中的 helper。

使用 `python3 scripts/materialize_trace.py artifacts/canonical/KIND/DATASET/RUN_ID /path/to/new-directory`
可恢复可读的 workspace、helper 改写版本和源快照，供检查或后续 recipe 编译。
这个命令只恢复证据，不执行轨迹。

ATIF 和工具日志属于 execution trace，不是 executable replay recipe。完整 Agent 工具链
与最终有效执行是两种不同对象；后者尚待依赖切分审核。文件改写捕获及其缺口会如实记录，
不能把最终 helper 内容当成每次尝试使用的内容。后续格式和流程见
[replay contract](docs/replay-contract.md) 与 [recipe schema](schemas/replay-recipe-v1.schema.json)。

原工作簿 complexity 放在 `datasets/xlsx/*/complexity.json`，不混入 Agent Prompt。
文件大小、cell、Sheet、公式、图表、style、合并区域及压缩结构差异是 workload 的一部分；
不能据此把 CPU 差异直接解释成“行业差异”。当前不增加第八个领域。

`runs/`、`.snapshots/`、`qualification/`、凭据来源记录及含临时令牌的下载缓存仍忽略。
这些目录用于开发/运行；正式 evidence 通过 canonical pack 和报告发布。历史报告保留原
实验结果并标注历史阶段，不能替代当前 suite 的成功运行和独立验收。
