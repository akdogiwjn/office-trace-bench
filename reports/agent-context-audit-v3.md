# 旧版重复生成与新旧 Agent 上下文审计

只恢复 task.prompt 还没有恢复完整 Agent 输入；不能将所有执行差异归结为随机性。

## 旧版真实生成也有变化

| TLC | 第一次历史生成 | 第二次历史生成 | 本轮恢复 prompt |
|---|---:|---:|---:|
| steps / calls | 57 / 62 | 35 / 41 | 18 / 19 |
| helper 最后一次完整写入 | 234 行 | 286 行 | 263 行 |

历史两轮 task.prompt 字节一致，OpenClaw 版本、模型名、thinking high 一致。第一轮三次完整写入 helper、一次 edit，第二轮只有一次写入。
这些是原始真实生成 trace；后续 document 场景则从历史成功调用提取固定脚本和 recipe 重复执行，两种重复不能混为一谈。

## 新旧完整背景输入不同

| 输入 | 旧第二轮 | 本轮恢复 prompt |
|---|---:|---:|---:|
| systemPrompt 字符 | 30179 | 33266 |
| projectContext 字符 | 11727 | 13883 |
| AGENTS.md 字符 | 7195 | 8048 |
| BOOTSTRAP.md | 未注入 | 注入 1510 字符 |
| Skill 注册块字符 | 5813 | 6111 |
| 工具 schema 字符 | 27477 | 27477 |

旧 runner 的 sync_openclaw_config.py 不排除 workspace/skills，新 runner 则排除。新运行载入了新的默认背景文件。
旧 Skill 注册表包含 agent-browser 和当前 case 的 Skill；新运行注册表没有 agent-browser，同时包含 PDF 和 XLSX。
Skill 文件正文一致不等于注册表、背景说明和整个系统上下文一致。恢复任务 prompt 的检查仍成立，但不能据此声称完整模型输入一致。

## 工具调用减少有具体等待参数差异

旧版 helper/recalc 的 exec 未指定 yieldMs，常返回 running 后再轮询。
本轮 helper 指定 yieldMs=120000，重算指定 yieldMs=180000，更容易在一次 exec 内返回。
process 调用由旧第二轮 12 次变为本轮 3 次。脚本检查和合并命令也改变了 exec 数量。
这说明调用数受等待策略影响，不能直接用来判断是否少做了业务操作。

## 证据范围

背景输入与 Skill 注册差异是已核实的控制变量，可能影响 Agent 的脚本和工具决策；本审计不能量化它们各自造成的变化。
旧两轮同样有随机性和修复差异。系统提示词 hash 还包含每轮动态信息，不能只用 hash 不同推导行为变化。
进一步受控对照需要冻结背景 Markdown、Skill 注册集合、有效配置和运行环境，再记录完整上下文元数据。
本次只完成审计，未修改 runner，未再请求模型或生成新 trace。

证据与元数据见 agent-context-audit-v3.json；源代码见旧 scripts/sync_openclaw_config.py、新 office_trace_bench/runner.py。
