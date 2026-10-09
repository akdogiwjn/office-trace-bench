# 当前通用化范围

共用模板现在为 `prompts/xlsx.txt` 和 `prompts/pdf.txt`，TLC/OPM 都从 manifest 传入领域参数。
保留旧任务的组织、业务要求、执行纪律和 QA；本地一致性检查验证渲染后的文本与旧版一致，
仅保留已经说明过的容器环境措辞变化。两份 legacy-compatible 模板仅用于历史对照。

| 部分 | 当前能力 | 验证边界 |
|---|---|---|
| 运行与 trace | 独立输入、代码快照、真实会话、完整工具调用和结果 | 每次 Agent 独立生成，不保证同一个脚本 |
| 参数化提示词 | 文件、指标、单元格依赖、场景、图表、人数、页数、保护字段及验收入口由 manifest 提供 | 参数替换单测不是新领域真实 trace |
| 通用验收 | 工作簿增强和可填写 PDF 批处理两类任务；没有领域名称分支 | 新数据仍需建立并验证独立预期 |
| 背景上下文 | 冻结六份必要 Markdown、agent-browser；仅注册当前任务 Skill | 历史文件只留下长度元数据，没有完整内容哈希 |
| 运行隔离 | 历史任务、成功产物、旧 session 不进入容器；逻辑工作目录指向本轮新输入 | 原基线和各轮新结果分别保留 |
| 新领域 | Retail/M3/HR、W-4/SBA 使用相同模板、runner 与通用验收器，通过 manifest、输入及 expected 接入 | 真实 trace 与独立正负样本检查见扩展报告；数据来源、版本及合成扩增边界明确记录 |

`agent_context_audit.json` 比较实际注入文件长度、Skill 注册文本哈希、工具 schema 长度、
workspace 位置和本轮背景文件前后哈希。可核验的历史元数据对齐不等于全部历史输入逐字相同：
日期、动态系统文本、服务端模型行为、历史配置内容与完整背景哈希仍有证据边界。
不要用总工具调用数直接推导业务处理量或性能变化。

新增实例需要 `prompt_contract` 中的业务说明和 `requirements` 中的结构化要求相符。
共用模板保持处理步骤；领域内容只进入 manifest。没有历史专用 verifier 的实例会自动获得
`input/verify_office.py`，使用共用验收器。新增任务超出工作簿增强/可填写 PDF 批处理时，需要
另立任务类型；当前不宣称支持任意 Office 操作。

TLC/OPM 本轮真实回归与脚本差异见 `reports/context-aligned-trace-comparison-v4.md`。
OPM 明确国籍别名与摘要路径别名的重验见 `reports/pdf-contract-compatibility-v7.json`；旧失败记录不改写。
新数据规模、正负样本与真实验收见 `reports/new-dataset-expansion-v8.md`。
HR 来源是公开缓存，未核验官方 ZIP 字节一致性；SBA 固定为官方 Box 的 2024 原生可填写表单。
当前没有通过修改 PDF Skill、增加 AcroForm 或坐标覆盖来接入不可填写表单。
全部实例能生成 trace 后，再进行固定 recipe 和离线 replay 镜像建设；本阶段不构建后者。
