# Office Trace Bench

通用 Office 任务与真实 OpenClaw trace 生成项目。当前支持 **TLC、Retail、Manufacturing、HR XLSX / OPM、IRS W-4、SBA 1919 PDF**，
保持原 `openclaw-trace-bench` 作为冻结的历史基线。

本项目按这个顺序推进：通用化 → TLC/OPM 回归 → 加入 Retail、Manufacturing、OEWS、W-4、
SBA 候选 → 为每个实例生成真实 Agent trace。用于运行 Agent 的镜像属于当前范围；
把 trace 整理成固定 recipe、构建 `document-oe` 一类离线复现镜像属于后续阶段。

共用模板与背景上下文的前轮回归已通过，详见
[前轮对比](reports/context-aligned-trace-comparison-v4.md)。18 项本地检查通过。
最新完成 TLC/OPM 新旧 runner 各一次，共四条真实 trace：实际任务、完整初始系统提示、
输入、配置和镜像在每对运行中一致。TLC 两轮全部通过；OPM 旧轮通过原版验收，
但国籍文本与摘要路径未通过通用规则，新轮全部通过。脚本实现仍有差异；详见
[本次新旧对照及脚本 diff](reports/controlled-runner-pair-v6.md)。OPM 这两个兼容性问题已改为
manifest 中的明确别名，同一旧产物通过当前验收；原失败记录保留，详见
[兼容性审计](reports/pdf-contract-compatibility-v7.json)。新数据的独立检查、真实 trace 和来源边界见
[扩展验证报告](reports/new-dataset-expansion-v8.md)。

## 项目组成

```text
datasets/{xlsx/{tlc,retail,manufacturing,hr},pdf/{opm,irs_w4,sba1919}}/
  manifest.json                 实例任务与输入哈希
  expected.json                 独立验收预期与原始结构指纹
  input/                        冻结输入和来源说明
prompts/{xlsx,pdf}.txt           当前共用的领域参数化模板，保留旧流程
prompts/*-legacy-compatible.txt  上轮专用模板，保留为历史对照
runtime_context/profiles/        必要背景说明和额外 Skill 的冻结快照
office_trace_bench/              准备、验收、运行、ATIF 与工具事件导出
runtime/Dockerfile              真实 Agent 的运行环境
vendor/                         原基线固定 Skill 与 Python wheels
legacy/                         原提示词、验收器、成功产物和历史 trace
runs/RUN_ID/                    每次新运行独立留存，不覆盖旧运行
scripts/regression.py           封存产物回归，明确不等同于真实 Agent 回归
scripts/build_*_expansion.py     官方观测转换、合成扩增或原生 PDF 字段映射
qualification/                 独立正负样本检查产物，不进入 Agent 快照
docs/status.json                当前证据和待办
```

## 先检查通用化

```bash
cd /home/lcq/office-trace-bench
python3 office.py list
python3 office.py validate --kind xlsx --dataset tlc
python3 office.py validate --kind pdf --dataset opm
make test
make regression
```

宿主离线检查需要 Python 3.11+ 与 Pillow。入口直接使用 vendored 纯 Python wheels，
无需修改宿主 Python。TLC 完整验证会读取十万行工作簿，耗时与内存明显高于小单测。

`make regression` 分别用新通用验收器和旧验收器检查同一批封存成功产物。
通过只能证明验收兼容性；新的通用 prompt 仍须通过下面的真实 Agent 运行。

## 构建 trace 运行环境

```bash
make image
```

默认使用本机原有 `ubuntu-openclaw-chromium:24.04-linuxarm64` 基础镜像，安装 LibreOffice、
Poppler 和原基线固定 Python 依赖。构建产物为 `office-trace-bench:runtime`；它包含
OpenClaw 运行工具，未放入任何固定 trace 或 replay recipe。

当前 Pillow wheel 为 CPython 3.12 ARM64。本 Dockerfile 面向该基线架构；其他架构需要
对应 wheel 与 OpenClaw 基础镜像。运行时记录镜像 ID 和实际工具版本，不能把不同版本
的结果直接当作环境相同的性能样本。

## 真实 Agent 回归

```bash
python3 office.py run --kind pdf --dataset opm --config /root/.openclaw
python3 office.py run --kind xlsx --dataset tlc --config /root/.openclaw
```

新运行结束后，执行 `python3 scripts/accept_baseline.py runs/RUN_ID`，检查代码快照未改变、
trace 未引用历史成功产物、Agent 实际调用过验收器。TLC/OPM 用原 verifier 重验；新增实例
没有历史 verifier，验收报告明确标为 `not_applicable`，使用其独立 manifest/expected。
`baseline_acceptance.json` 的 `accepted=true` 才表示完整基线回归通过。

TLC/OPM 的 manifest 选择共用的 `xlsx.txt` / `pdf.txt` 并冻结 SHA-256。
领域内容来自 `requirements` 和 `prompt_contract`；文件、指标、单元格、场景、人数和页数
由数据驱动。单测验证 TLC/OPM 渲染结果保留旧业务、执行和 QA 原文（仅容器环境措辞不同）。
原验收脚本作为冻结输入执行，通用 verifier 在 Agent 结束后独立重验。新增实例没有旧 verifier
时，runner 自动提供 `input/verify_office.py`，调用通用验收器。
XLSX 的 Agent 内业务验收暂不要求随后写入的执行摘要；Agent 结束后的最终验收必须检查摘要存在。
统一模板不保证独立 Agent 会话生成相同 helper 或工具调用序列。

`--config` 指向包含 `openclaw.json` 的宿主配置目录，仅只读挂载。runner 在一次性容器
中复制配置，排除历史 session、日志、媒体、缓存、workspace 和旧 Skill，接入项目固定
Skill。随后从 manifest 指定的 `agent_context` profile 恢复六份必要背景说明、agent-browser，
仅接入当前任务对应的 PDF 或 XLSX Skill。历史任务目录、成功产物和会话不进入新容器。
实际注入文件长度、Skill 注册文本哈希、工具 schema 长度及背景文件前后哈希写入
`agent_context_audit.json`；受控回归要求该审计通过。历史背景文件没有完整内容哈希，
因此对齐结论限于已有历史元数据和当前冻结文件，不声称全部历史模型输入逐字相同。
默认沿用配置中的模型；可用 `--model deepseek/deepseek-v4-flash` 显式指定。
不得在项目内保存 API key。实际模型也保存在 ATIF 轨迹中。

每次运行保存 prompt、输入、Agent stdout/stderr、原始 session、ATIF、完整工具事件、
Agent 内验收报告、宿主编排独立重验报告，以及含版本、时长、哈希的 run_manifest。
失败尝试也保留。捕获 session 必须匹配 Agent 返回的 metadata，禁止取“最新 session”。
每次启动前冻结代码、通用 prompt、Skill、背景 profile 和所选数据集；Agent 只读挂载该快照，
不会看到 `legacy/` 的历史成功产物。运行期间修改项目不会改变这一轮的输入或验收代码。
每轮只挂载自身的结果目录，不能读取其他轮的产物。代码快照保存在 `.snapshots/RUN_ID/`，
与可写结果目录分开；启动前与运行后均检查源码哈希。

## 新旧 runner 对照

`scripts/controlled_runner_pair.py` 在同一当前环境中真实执行原版脚本和新入口，
每个 TLC/OPM 实例各一对。它冻结同一份配置、镜像及项目快照，并记录实际 Agent 调用前
的任务、输入、背景、配置指纹。原版脚本源码保持不变；实验快照将新模板的环境措辞
和尾部换行统一为原版实际任务。项目正式模板不受实验改写影响。

每一对使用同一可见输入清单（含新框架需要的 dataset_manifest.json），
同一只读项目快照同时包含两套入口；仅包含当前实例输入，未加入历史输出或 helper。
这是当前环境对照，历史配置和服务端模型状态不能由本实验还原。
目录实现仍保留原、新差异。完整实验边界、失败明细和四条 trace 路径见报告。

对已有实验重新汇总报告无需调用模型：

```bash
python3 scripts/compare_controlled_pair.py control_pairs/20261008T163759Z-90a05c03
```

该报告同时审计成功与失败尝试；`comparison_complete` 表示对照完成，
不表示所有产物通过严格验收。本轮 `strict_regression_status=failed`，旧 OPM 失败保留。
本实验只有每版各一次，不足以评价生成稳定性。用于复现 trace 的镜像仍待后续阶段。

## 扩展数据集

每个新增实例放入 `datasets/KIND/DATASET_ID/`，提供独立输入、manifest 与 expected。
manifest 使用 `office-dataset-v1`：定义业务指标、场景参数、图表依赖或 PDF 字段映射，
不在通用 verifier 中添加领域名称分支。输入哈希与 expected 哈希必须匹配。
指定通用 `prompt_template`、对应哈希、`prompt_contract` 和 `agent_context`。
新增模板参数参见当前两份 manifest；不要复制一份领域专用提示词。

先用独立可信产物和失败样本验证验收器，再真实运行 Agent。各实例分别生成 trace，
不得跨数据集复用成功轨迹。官方数据转换与合成扩增必须区分记录。

已加入的三个 XLSX 都包含 100,000 条合成分片、16 列、7 张基础表和 2 个原有图表。
Retail/M3 的 Census 序列通过 FRED 分发获取，分片守恒保留原观测汇总；它们不是实际企业或交易。
HR 选取 2025 OEWS 的详细职业，排除重复层级和工资被抑制的条目；数据来自公开仓库缓存，
尚未独立核验与官方 ZIP 的字节一致性。中位工资指标明确为职业中位数的就业加权代理值。
W-4 使用 IRS 原始 2026 五页表单。SBA 使用 SBA 官方 Box 公开分发的 2024 原生可填写版，
保留原文件与公开 SHA-1 核验；当前 2025 官方下载失败，不能把不可填写的银行副本当作正式输入。
每份来源说明、原文件 SHA-256、字段或扩增规则均留存在实例目录和 manifest 中。

后续 [HR / SBA 来源核验](reports/hr-sba-source-reliability-v1.md) 已确认 HR 全部 825 个种子职业的
就业人数与年平均工资吻合 BLS 官方发布表，以及 SBA 七页规范化文字吻合官网 2024 PDF。
两份官网原文件的字节一致性仍未核验；HR 年中位工资列也未直接核验。
前述“官方 Box”应按核验报告的准确边界理解：本地文件取自 `sba.app.box.com` 公开链接，
内容与官网旧版一致，但尚未找到官网到这个具体 share 的直接引用。

新增实例的运行方式相同，例如：

```bash
python3 office.py run --kind xlsx --dataset retail --config /root/.openclaw --model deepseek/deepseek-v4-flash
python3 office.py run --kind pdf --dataset sba1919 --config /root/.openclaw --model deepseek/deepseek-v4-flash
```

`scripts/qualify_{xlsx,pdf}_dataset.py` 只用于独立验收器检查，不能当作真实 Agent trace。
所有 builder、资格检查脚本与资格检查产物均不进入 Agent 只读源码快照。Agent 继续自行编写
helper；没有加入固定执行脚本。运行镜像沿用现有版本，离线复现镜像仍留待下一阶段。

## 证据边界

Git 仓库保存源码、冻结输入、历史基线和分析报告。`runs/`、`.snapshots/`、`qualification/`
以及凭据来源记录和含临时令牌的下载页面不提交；报告中指向这些运行产物的链接用于原工作目录。
运行镜像和离线复现镜像也不作为 Git 文件上传。

`legacy/` 的产物和 trace 来自旧项目，不是本项目的新运行。新输出位于 `runs/`。
`tool_events.json` 完整保存调用参数及对应结果；操作分类是分析标签，不是固定成功路径。
`process`、未知工具、失败与重试均保留。当前不生成可执行 replay recipe。

通用验收包含原始数据逻辑指纹、已有公式与图表数据引用、缓存 KPI、场景表、输出清单
和保护字段。原始数据指纹使用 12 位有效数字，其他既有单元格的十进制数值使用
1e-10 相对/绝对容差，兼容表格软件的无意义浮点表示变化；整数严格比较。
它不是 XLSX 字节一致性校验，也不证明所有公式在所有场景下均已完成重算。
