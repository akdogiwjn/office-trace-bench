# 执行顺序与完成条件

1. 通用化：类型级 prompt、manifest、通用 verifier、独立运行目录与 ATIF 导出。
2. 基线回归：封存 TLC/OPM 产物同时通过新旧 verifier；失败样本能被新 verifier 拒绝。
3. 真实 Agent 回归：新 prompt 分别产生 TLC/OPM 新 session、有效 ATIF 和独立验收 success。
4. 新输入：Retail MRTS、Manufacturing M3、Workforce OEWS；PDF W-4、SBA 1919。
   先确认数据粒度、统计口径或表单兼容性，冻结输入与独立预期；再跑真实 Agent。
5. 所有实例 trace 可生成后，再讨论固定成功路径提取、跨环境复现和离线负载镜像。

原始 TLC/OPM 基线保留，新数据不是替换旧数据。

真实 Agent 回归必须有新运行证据；封存产物检查、历史 trace 导出和 PDF 单记录技术
检查分别登记，不能充当真实回归。失败尝试留存，不自动无限重试。

通用化会改变 prompt、工具名称和验收成本，不能宣称新轨迹与旧轨迹字节等价。
业务结果、输入保护和验收兼容性是当前回归目标，CPU 比较另立环境一致性口径。
