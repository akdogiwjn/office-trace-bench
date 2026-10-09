> 历史证据：本报告保留原实验及其契约，不代表当前冻结 suite。当前输入、trace 选择与来源边界见 [suite 审计](../docs/suite-audit-v2.md)。

# 提示词改动与旧负载可比性

这次通用化不只是替换路径和数据集参数，而是改写了提示词组织形式。
已接受的新 trace 证明业务回归通过，不能作为旧程序负载保持不变的证明。

| 项目 | 旧提示词 | 新运行实际提示词 |
|---|---:|---:|
| XLSX 英文空白分词数 | 565 | 236 |
| XLSX 行数 | 52 | 31 |
| PDF 英文空白分词数 | 472 | 266 |
| PDF 行数 | 45 | 35 |

统计只针对 task.prompt，不包含 Agent 后续读取的 Skill、manifest、expected 和验收代码。
业务细节多数被移到 manifest，所以不能把文本缩短比例理解为业务要求删除比例。

## 实质变化

- 旧版在 prompt 内直接列出输入、KPI 单元格、情景表、图表来源和交付物；新版让 Agent 首先读取 manifest。
- XLSX 旧版明确要求“编辑完成后重算恰好一次”，失败修复后才允许额外重算；新版只规定重算及记录次数，遗漏了这个执行约束。
- XLSX 旧版允许一个简洁 helper，并要求汇总 helper 文件名、执行尝试数和成功数；新版要求自行编写 helper，摘要约束较笼统。
- 验收调用从 input/verify_xlsx_enhanced.py 改为 /project/office.py verify，并向 Agent 暴露了通用项目目录。
- 新 XLSX 实际读取了通用 verify.py、workbooks.py、cli.py 和 expected.json；旧版则主要读取旧验收器和输入。
- PDF 的执行次数约束大部分仍在，但新 prompt 没有要求保持旧 helper 的拆分方式，因此映射与填写渲染被合并进一个 helper。

不能把所有执行差异都归因于 prompt：旧 XLSX trace 自己就偏离了原 prompt 的“恰好一次”，实际重算两次。
新 Agent 即使收到完全相同的 prompt，也可能改变检查方法、公式实现、脚本和轮询次数。

## 脚本变化

| 用例 | 旧 Agent 生成的脚本 | 新 Agent 生成的脚本 |
|---|---|---|
| TLC | enhance_workbook.py，286 行 | build_report.py，201 行 |
| OPM | generate_and_run_batch.py，184 行；run_batch_fill_render.py，52 行 | run_batch.py，143 行 |

脚本由两个独立 Agent 会话分别生成，并不是将旧 helper 做路径替换后移植。
名称和行数只是差异的索引，不能直接用于推断资源消耗。TLC 已确认的实质变化包括
INDEX/MATCH 改为 VLOOKUP、额外三个展示公式，以及两次重算变为一次；OPM 的业务处理次数保持一致。

## 对后续比较的影响

原 trace 和原脚本应继续作为旧负载基准。当前新 TLC/OPM trace 是业务回归证据，
尚不能替换旧负载用于判断通用化前后的资源变化。

如果要判断框架改造是否影响执行，应先在新 runner 中使用保留的旧脚本和相同输入做对照，
从而避免把重新生成脚本的差异混入框架变化。如果要判断通用 prompt 是否能完成原任务，
则应恢复旧 prompt 的主体，只参数化必要的路径、数据和验收接口，并另行生成候选 trace；
即便如此，也只可比较结果与受约束的业务操作，不能保证逐条工具调用或脚本完全相同。

对新数据集，通用化可以继续通过 manifest/runner/verifier 扩展；扩展成功不要求覆盖或替换旧负载基准。
本次仅完成提示词审计，未改写现有提示词，未生成新的运行，也未构建离线复现镜像。

来源：legacy/xlsx/task.prompt、legacy/pdf/task.prompt、prompts/xlsx.txt、prompts/pdf.txt、
两个已接受运行的 task.prompt 与 trajectory.json。详细执行差异见 trace-comparison-v1.md。
