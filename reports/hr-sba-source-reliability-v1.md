# HR / SBA 输入来源核验

结论：两个文件都取得了较强的官方内容佐证，可用于当前固定输入的性能 benchmark；尚不能声称与官网原文件逐字节一致。
原输入、manifest、验收预期和已生成 trace 未改动。核验依据、哈希和逐职业匹配清单见 [JSON 报告](hr-sba-source-reliability-v1.json)。

| 文件 | 已核实 | 尚未核实 |
|---|---|---|
| HR `national_M2025_dl.xlsx` | SHA-256 与冻结 manifest 一致；Git blob SHA-1 与缓存仓库记录一致；825 个选定职业的就业人数、年平均工资全部与 BLS 官方表一致；767 个公布小时工资的职业，其小时平均工资和小时中位工资均一致 | 官方 ZIP 仍返回 403，未比对其内部 XLSX 字节；官方发布表未提供年中位工资，`A_MEDIAN` 列尚未直接核验 |
| SBA `sba1919_2024.pdf` | 从同一 Box 链接重下载，SHA-256 和字节与原输入一致；SHA-1 与 Box 元数据一致；7 页完整文字规范化后与 SBA 官网 2024 PDF 完全一致；04/2024 页脚、6/30/2027 到期标识与官方版本相符 | 未取得官网 PDF 原字节进行哈希比较；未找到 SBA.gov 到该具体 Box share 的直接引用，Box 账户身份不能仅由子域名和 PDF Author 字段证明 |

HR 的主要独立依据是 [BLS 官方 May 2025 发布表](https://www.bls.gov/news.release/ocwage.t01.htm)。比较覆盖全部 825 个输入种子职业，缺失 0、数据冲突 0。官方表的职业名换行先拼接；同名的汇总/详细职业按官方表的层级缩进区分，未按本地数值反选条目。工资未公布的 58 个职业不计入小时工资核验。BLS [官方数据目录](https://www.bls.gov/oes/tables.htm) 确认该年 National XLSX 的官方 ZIP 链接。

SBA 的独立内容依据是官网保存的 [2024 年 Form 1919 PDF](https://legacy.sba.gov/sites/default/files/2024-07/Form1919%20%281%29.pdf)，其来源入口为 [官方表单页面的历史版本](https://legacy.sba.gov/document/sba-form-1919-borrower-information-form)。[2024 年官方更新通知](https://legacy.sba.gov/document/information-notice-5000-857390-sba-form-1919-update-criminal-justice-reviews-final-rule) 另行佐证当年表单更新和到期日期。本地保留的 04/2024 表单为 7 页、127 个 AcroForm 字段。

全文比对去除了大小写、空白、标点和复选框字形差异，比较的是全部字母/数字顺序。它不能证明版式、字段坐标、批注、PDF 对象或字节一致。本地重复下载与 Box SHA-1 一致，证明取得的是同一个公开文件，也不能单独证明发布者身份。

前轮将其简称为“官方 Box 分发”证据表述偏强。当前准确表述为：**从 `sba.app.box.com` 公开链接取得，七页内容与 SBA 官网 2024 版本一致，官网原字节及具体 Box 账户的直接引用链尚未闭环**。不将 2024 年固定基准输入称为当前 2025 版。

两份原始输入 SHA-256：

- HR：`852250997ceff9b721ff68f63e877d818f9c1ec8b1b69dd367958faedd5282b2`
- SBA：`db31ccf144266d6cd8a16555927893299f1b2831ee1651b1d4c6634a48caf91a`

离线重验：`python3 scripts/audit_hr_sba_sources.py`。核验用的官方网页/PDF 文字提取留存在 `sources/provenance-audit/`；不是通过第三方页面转抄几项总数来认定完整文件真实。
