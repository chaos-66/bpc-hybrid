# S3-ASSET-RECOVERY：Sun 官方继承输入与 checking benchmark 核对

2026-09-23；资产审计完成；未运行性能实验，未调用 LLM，未修改已有 Gold。
机器明细：`sun_stage3_official_asset_audit_v1.json`。

## 已核实的来源与内容

Springer 正式页面仍指向 <https://archive.org/details/input-2>：
<https://link.springer.com/article/10.1007/s11227-023-05626-0>。
本轮未重新取得官方 ZIP：网页工具不可访问 Archive.org，本机 HTTPS 证书验证失败；
没有关闭 TLS 验证。官方 ZIP 身份沿用历史审计，不能说本轮重验了官方 ZIP 字节。

本轮直接读取两份本地继承输入，57/57 相对路径、大小、SHA-256 相同：

- 7 个原始 GDPR BPMN；活动区 7/7 与来源逐字节相同。
- GDPR Articles 5–50，共 46 篇。
- `gdpr.config` 与 stopwords/signalwords/sequencemarkers 三个词表。

其中没有 Sun 补充后的 fully compliant BPMN、单错误变体、逐项违规答案、
relevant-rule 对照或 Sun 四模型文件名映射。57 个文件不是 57 个可直接评分的案例。
不得执行 provenance 中的旧程序，也不将其恢复到活动实现。

## 协议纠正

可读本地文献是作者稿，不能称为已取得最终发表版全文。§4.3 Definition 4 在组件
相似度内部使用 tau；未给出 `matching_score > tau` 的外层规则选择条件。
§5.3.2 要求先补充成合规流程，再分别删活动、换执行者、交换活动以制造单一错误。
原文未明确公开规则选择接口，不能自定 Top-K/cutoff 后称其为 Sun 原方法。

当前 v3 的完整规则库方向保留，但其外层门槛和基准流程合规性依据不足。
**v3 F1=0 撤销论文性能身份；v1、v2、v3 及 no-gate replay 均为历史诊断。**
保存历史预测、分数和日志，不重写成新协议的结果。

控制流程触发报警不等于已证明它实际不合规；这也可能是抽取、匹配或检查错误。
新 control 的参考语义必须从条文和流程逐项确认，不能以任何参评方法不报警作为
构造或筛选标准。F1 为 0 或 1 本身不是错误证明，不能通过筛样本或调答案避开极值。

## 当前可复用证据与缺口

- 9 条法规、74 句既有 Rules-Only/Direct-LLM 抽取可复用，不能当作 46 篇已全覆盖。
- 已有人工 Rule Gold 为 92 个 clause，规则侧顺序关系为 0；不追加伪造关系。
- Matching Gold 只覆盖 7×9 的 63 个组合中的 25 个；其余 38 个是未标注，不能
  静默当负例。已有 v3 MAP 只能按其局部 reference 范围解释。
- 原绑定审核已完成，不重开；其 AI 补充结果不冒充正式人工 Gold。

## 本轮用户选择与下一步

用户明确选择：优先补齐三类，补充有明确顺序依据的条文与基准流程；新增 LLM
调用先列精确预算再授权。仍固定 Stage 1≈Sun、Stage 2 为主要变量、Stage 3≈Sun。

先建立独立的新 benchmark 版本，列出法规范围、适用条件、合规 control、实际
执行者和有原文依据的先后要求。冻结参考与变体构造后再运行参评方法。
匹配与 checking 的接口范围必须明确披露，任何条件化 checking 不称为自动端到端。
不新增专属 matcher/grounding/backend、不调阈值、不按结果删样本、不改旧 Gold。
本报告完成资产审计，不表示三类 benchmark 或最终 Table 3 已完成。

## 复核命令

`python formal_experiment/scripts/audit_sun_stage3_official_assets_v1.py`

命令只读取文件、XML 和现有参考，输出库存摘要；显式 `--output` 时只新建报告，
已有路径拒绝覆盖。不调用合规检测器、模型、网络或外部 API。
