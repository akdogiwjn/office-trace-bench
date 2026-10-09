# 新数据与真实 trace 验证（v8）

五个新实例完成独立正样本、破坏样本检查和真实 Agent 验收。保留 TLC/OPM 后，共七个可运行实例。
两份正式共用提示词未改；Agent 继续自行生成 helper。用于复现 trace 的 recipe 和镜像尚未构建。

| 实例 | 真实 trace | 步数 / 工具调用 | 验收 |
|---|---|---:|---|
| xlsx/retail | [xlsx-retail-20261009T023342Z-42168240](../runs/xlsx-retail-20261009T023342Z-42168240/trajectory.json) | 26 / 31 | Agent、独立验收、背景与隔离检查通过 |
| xlsx/manufacturing | [xlsx-manufacturing-20261009T024115Z-4afa2f56](../runs/xlsx-manufacturing-20261009T024115Z-4afa2f56/trajectory.json) | 27 / 36 | Agent、独立验收、背景与隔离检查通过 |
| xlsx/hr | [xlsx-hr-20261009T025210Z-173694e5](../runs/xlsx-hr-20261009T025210Z-173694e5/trajectory.json) | 31 / 41 | Agent、独立验收、背景与隔离检查通过 |
| pdf/irs_w4 | [pdf-irs_w4-20261009T021352Z-a22a4aaa](../runs/pdf-irs_w4-20261009T021352Z-a22a4aaa/trajectory.json) | 24 / 34 | Agent、独立验收、背景与隔离检查通过 |
| pdf/sba1919 | [pdf-sba1919-20261009T030304Z-987669df](../runs/pdf-sba1919-20261009T030304Z-987669df/trajectory.json) | 31 / 38 | Agent、独立验收、背景与隔离检查通过 |

三个新 XLSX 均为 100,000 行、16 列、7 张基础表、2 个原有图表；仅保留官方观测汇总，并明确标记合成工作量分片。
W-4 为 5 页、48 个叶字段、10 份填写结果和 55 张 PNG；SBA 为 7 页、127 个叶字段、10 份结果和 77 张 PNG。

来源边界：Retail/M3 通过 FRED 获取 Census 序列。HR 使用公开仓库的 2025 OEWS 工作簿缓存，尚未核验与官方 ZIP 的字节一致性；仅使用选定详细职业，“中位工资”为职业中位数的就业加权代理值。
SBA 使用 SBA 官方公开 Box 分发的 2024 原生可填写版，文件与公开 Box SHA-1 相符；不称为当前 2025 版。当前版官方原文件下载失败，下载到的银行副本没有 AcroForm，已排除。

OPM 国籍与摘要路径改为 manifest 中的明确别名；同一旧产物通过当前验收，无输出改写。原 v6 失败记录保留，见 [兼容性审计](pdf-contract-compatibility-v7.json)。
五个新实例的破坏样本全部拒绝，见 [负样本检查](expansion-failure-samples-v1.json)。
具体规模、输入/trace/helper 哈希、来源与全部证据路径见 [完整报告](new-dataset-expansion-v8.json)。

每实例这轮仅生成一次，不能据此证明多次生成稳定性。操作标签会包含读取脚本和批处理调用，不能直接视为 helper 调用次数；本轮没有 CPU/OS 性能结论。
W-4 与制造业 trace 包含探索性 import 探测的 ModuleNotFoundError，随后通过提供的验收入口完成验收；这些观察没有删除。最终验收通过不表示每条探索命令都成功。
