# CCF C 投稿强度判断与导师汇报图说明

**日期**：2026-07-12  
**当前判断**：有 CCF C full/regular paper 的潜力，但实验尚未完成，不能说已经达到
录用强度。若论文只剩“给 Sun Stage 2 加 LLM”，创新偏弱；若完整实现本文锁定的
方法、消融和下游验证，形成一篇 CCF C 级完整实验论文是合理目标。

CCF 将 C 类描述为国际学术界认可的重要会议/期刊；会议目录只计算 Full paper 或
Regular paper，Short/Demo/Workshop 不按该目录中的会议论文计算。具体投稿时仍要
核对导师、学校采用的目录版本和目标 venue 当年 CFP：
<https://www.ccf.org.cn/service/pj/2024-03-14/814278.shtml>。

## 1. 导师汇报图

独立矢量图：`outputs/reports/experiment_design_overview.svg`。

![实验总体设计](../outputs/reports/experiment_design_overview.svg)

图中最重要的阅读顺序：

1. 同一个德文 EStG 来源，经固定流程翻译为英文，由用户审核六要素 Gold；
2. B0、H1、D1 读取同一冻结输入；
3. B0 是论文忠实 Sun baseline，不是几个关键词组成的 heuristic；
4. H1 是主方法：先运行 B0，只对预注册失败字段进行 LLM 修复；
5. D1 是纯 LLM 对照，不是主要创新；
6. 三组输出同一个 Sun rule record；
7. 先评价 Stage 2，再进入完全不变的 Stage 3，观察最终合规检查是否改善。

## 2. 一句话论文故事

> 现有规则型法规解析依赖不公开的 marker，并在句法失败时产生系统性漏检；我们先
> 重建一个可审计的 Sun Stage 2，再提出证据约束的字段级选择性 LLM fallback，
> 最后通过冻结 Stage 3 验证语义抽取改进能否真正减少业务流程合规检查错误。

建议英文题目：

> Evidence-Grounded Selective LLM Repair for Regulatory Semantic Parsing
> and Business Process Compliance

建议中文题目：

> 面向业务流程合规检查的证据约束选择性大模型法规语义抽取方法

## 3. Baseline、Idea、Innovation 必须怎样区分

### Baseline：B0

按最终 Sun 论文独立重建：

- BERT-TextCNN 四类 modality；
- CoreNLP + Tregex/Tsurgeon；
- 公开来源重建并冻结 marker；
- modality、actor、action、condition、constraint、exception；
- 输出 Sun-compatible rule record。

B0 是公平实验的基础，不是本研究最主要的算法创新。但“公开 marker provenance +
可运行的论文忠实 baseline”可以作为 enabling artifact contribution。

### Idea：H1

规则先运行，只有推理时可见的不确定性触发 LLM：parser failure、必需字段缺失、
span 冲突、低分类 margin、marker 命中但作用域失败、Stage 3 adapter invalid 等。

LLM 不重写一切，只修复失败字段；输出必须引用原文 span，并保留原规则结果、触发
原因和修改 provenance。

### Control：D1

纯 LLM 直接输出相同六要素和 rule record。它回答“为什么不全部交给 LLM”，但
“使用 LLM 直接抽取”本身不是创新点。

### 三项正式创新

1. **可复现的 Sun Stage 2 重建与 marker provenance**：解决作者 marker/Stage 2
   源码不公开导致的不可比较问题；
2. **证据约束的字段级选择性 LLM fallback**：在保留规则可解释性的同时，只为
   高风险字段付出 LLM 成本，并提供 risk-coverage-cost 权衡；
3. **Stage 2 到冻结 Stage 3 的误差传播评价**：不止证明 span F1 提高，还证明
   actor/action/order 改进是否减少 incorrect-actor、missing-action、
   out-of-order 错误。

双视图表示（原文 evidence span + Barrientos-style normalized pattern）建议作为
第 2 项创新的机制组成，不再单独拆成第四项，避免贡献显得零散。

## 4. 当前创新强度评分

| 维度 | 当前设计 | 完成目标 | 解释 |
|---|---:|---:|---|
| 问题价值 | 4/5 | 4/5 | 法规到流程合规的端到端问题明确 |
| 方法新颖性 | 3/5 | 4/5 | 必须突出字段级门控、evidence 和 selective risk |
| 技术完整性 | 2/5 | 4/5 | 当前尚未实现正式 B0/H1/D1 |
| 实验证据 | 1/5 | 4/5 | 尚无冻结 Gold、消融、显著性和 Stage 3 结果 |
| 可复现性 | 3/5 | 5/5 | marker/source/hash 和严格审计具有优势 |

所以答案不是“创新不够”，而是“创新框架够用，证据尚不够”。最终能否达到 CCF C，
主要取决于是否完成下面的最低实验包。

## 5. CCF C 强度的最低实验包

### 必做主实验

- 同一 Gold 上 B0、H1、D1 三组完整比较；
- sentence modality macro-F1；
- 六要素 exact span 和 overlap P/R/F1；
- schema valid、coverage、API failure、调用比例和费用；
- 同一冻结 Stage 3 的 AP/MAP 与三类 violation P/R/F1；
- H1/D1 相对 B0 的 downstream delta。

### 必做消融

至少包含：

1. B0 仅论文 marker examples；
2. B0 + public reconstructed marker；
3. H1 整句 fallback vs 字段级 fallback；
4. H1 every-call vs selective-call；
5. H1 有/无 evidence span validation；
6. D1 有/无 controlled vocabulary 或 normalized view。

### 必做可靠性

- BERT-TextCNN 至少 3--5 个训练 seeds；
- LLM temperature 0，同一输入重复运行评估稳定性；
- paired bootstrap confidence interval 或适合配对离散结果的显著性检验；
- invalid/API error 不得从分母删除；
- 独立错误分析：parser、marker、actor、action、scope、translation、LLM
  hallucination。

## 6. 数据规模风险

Sun-aligned 150 句适合做主复现实验，但对一篇完整 CCF C 论文可能偏小，尤其
exception 只有约 15 个原论文标注。推荐结构：

- **主集**：150 条按 Sun 标准选择的 EStG 英文译文，用户完整审核六要素；
- **增强集**：额外 100--200 条与 Stage 3 直接相关的 GDPR/合规句子，冻结抽样后
  由用户审核，验证跨法规泛化；
- 如果人工成本不能支持增强集，至少用 LEXDEMOD、PET、MGTC 做 modality、actor、
  action 的外部子任务验证，并把“非完整六要素”写清楚。

不能为了匹配 Sun 的 443 个数量而人为选择样本或修改 Gold。少数类最好通过预先
定义的分层抽样保证最低评价数量，并同时报告自然分布结果。

## 7. Stage 3 如何支撑创新，而不是喧宾夺主

Stage 3 不修改，只作为“效用测量仪”：

| Stage 2 改进 | 预期 Stage 3 影响 |
|---|---|
| actor 更准确 | incorrect-actor FP/FN 降低 |
| action 召回提高 | missing-action FN/FP 降低 |
| action order/scope 更准确 | out-of-order 与 matching 改善 |
| condition/constraint/exception 更准确 | rule-to-BPMN AP/MAP 改善或减少误匹配 |

如果 Stage 2 F1 提高而 Stage 3 不提高，仍是有效结果：说明提升集中在下游未使用的
字段，或 Stage 3 threshold/matching 已成为瓶颈。必须报告这种情况，不能只选择
有利样本。

## 8. 容易被审稿人否定的写法

- “我们首次使用 LLM 抽取法规语义”；范围过大且很可能不成立；
- “直接 LLM 就是创新”；已有大量结构化法规抽取工作；
- “指标比 Sun 高，因此优于 Sun”；若数据、翻译、Gold 不同则不可直接比较；
- “导师包是 Sun 完整源码”；事实不成立；
- “LLM 生成 Gold，再证明 LLM 更好”；评价循环；
- 只报告总体 F1，不报告 exception 等少数类、invalid 和调用成本；
- 修改 Stage 3 threshold 让 H1 获得更好结果。

## 9. 给导师的两分钟讲法

1. Sun 相比 Winter 的主要贡献在 Stage 2，但作者没有公开完整 Stage 2；我们先按
   论文和引用链建立可复现 baseline。
2. 规则方法精确且可解释，但遇到 marker 缺失、parser failure 和隐式表达会漏检；
   纯 LLM 覆盖强，却有幻觉、不稳定和成本问题。
3. 我们的主方法不是“把文本交给 LLM”，而是规则优先、按字段识别风险、只修复
   失败字段，并要求每个修复对应原文 evidence span。
4. B0、H1、D1 使用完全相同的数据和人工 Gold，输出同一个 rule record。
5. 最后不修改 Sun Stage 3，直接检验更好的六要素是否真的提升业务流程合规检查。

## 10. 当前结论

以当前设计投稿 CCF C：**方向可行，方法故事基本足够，当前实验成熟度不足**。
完成正式 B0、字段级 H1、D1、公平 Gold、核心消融、稳定性/显著性和 Stage 3 传播
分析后，可以合理把 CCF C full paper 作为目标；若只有 150 句上的“三组 F1”且无
消融和下游结果，则录用把握偏低。
