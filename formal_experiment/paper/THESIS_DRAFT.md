# BPC-Hybrid 论文工作稿

**状态**：DRAFT — 已启动写作，但无正式实验结果  
**写作语言**：中文；技术术语保留规范英文  
**主张控制**：`CLAIM_EVIDENCE_MATRIX.md`

## 题目候选

面向设计时业务流程合规检查的法规语义解析：传统方法、大语言模型与混合方法的
分阶段比较

## 摘要

设计时业务流程合规检查需要把法规文本中的规范性要求与流程模型中的活动、参与者
和控制流进行对应。本文围绕 Sun et al. 提出的三阶段框架，设计一套可追溯的独立
重建与扩展实验：Stage 1 解析 BPMN 流程结构和标签语义，Stage 2 从法规文本中识别
模态及 actor、action、condition、constraint、exception，Stage 3 进行规则—流程
匹配和违规类型分类。研究将比较代表性非 LLM 方法、paper-faithful Sun 重建、Direct
LLM 和 selective Hybrid，并在预先冻结的复杂法律语料上检验不同方法随复杂度增加
的退化边界。

[[TODO-RESULT:S2.10：回填 Stage 2 主数据结果]]  
[[TODO-RESULT:S2.12：回填复杂度分层结果]]  
[[TODO-RESULT:S3.7/S3.10：回填 Oracle 与端到端结果]]  
在上述正式结果产生前，本摘要不写性能提升、最佳方法或最终结论。

## 1. 引言

法规通常以自然语言描述义务、禁止、许可、定义及其适用条件，而业务流程模型则以
活动、事件、网关、参与者和控制流表达组织行为。设计时合规检查需要跨越这两种表示
之间的语义差异：一方面从法规中恢复可计算的规范性规则，另一方面从流程模型中恢复
可匹配的行为与结构关系，最终判断流程是否缺少必要活动、由错误参与者执行活动，或
违反法规规定的先后顺序。

Sun et al. 的方法为这一问题提供了 Stage 1 流程解析、Stage 2 法规解析和 Stage 3
匹配/违规检测的完整框架。现有项目证据表明，作者完整的 Stage 2 源码、训练权重、
完整 marker lexicon 和原始 150 句 phrase Gold 并未随本项目获得。因此，本文不声称
复用作者原始实现，而以最终发表方法为来源，进行可审计的 paper-faithful independent
reconstruction。[[TODO-SOURCE:SUN2024:核对三阶段描述与方法资产页码]]

大语言模型能够直接生成结构化语义表示，但它们也可能产生 schema 违规、遗漏字段、
不稳定输出和额外调用成本。因此，本文不预设“LLM 必然更优”，而是把 Direct LLM、
不使用 LLM 的完整重建 baseline，以及只在预注册失败/不确定条件下调用 LLM 的
selective Hybrid 放在相同输入、Gold、输出合同和评价器下比较。复杂法律语料是否会
放大不同方法之间的差异，同样作为待检验问题，而不是预先成立的结论。

### 1.1 研究问题

- RQ0：能否完整、可追溯地独立重建 Sun 的三阶段设计时合规检查框架？
- RQ1：传统方法、完整 Sun 重建、Direct LLM 和 selective Hybrid 在 Stage 2 的
  模态分类与六要素抽取上如何比较？
- RQ2：法律文本复杂度增加时，各 Stage 2 方法如何退化，错误类型如何变化？
- RQ3：在 Gold Rule/Process Records 下，多个 Stage 3 baseline 与 LLM/Hybrid
  方法在匹配和违规类型分类上如何比较？
- RQ4：Stage 2 或 Stage 3 的局部改进能否转化为端到端提升？

### 1.2 预期贡献（待验证）

本文计划交付：三阶段独立重建及其可复现边界；统一 canonical contract 下的 Stage 2
多 baseline 比较；复杂法律语料上的复杂度分层与错误分析；Stage 3 Oracle 与
end-to-end 分离评价；以及解释 Stage 2、Stage 3 和二者交互贡献的受控消融。

[[TODO-STATUS:S2.13/S1.7/S3.11：各阶段冻结后将“计划”改为已完成贡献]]

## 2. 相关工作

### 2.1 设计时业务流程合规检查

[[TODO-SOURCE:WINTER2020/AGOSTINELLI2019：核对原论文并撰写]]

### 2.2 法律文本的 modality 与语义要素抽取

[[TODO-SOURCE:MICHEL2022/SLEIMI：核对数据、类别和 marker 方法]]

### 2.3 Sun 与 Winter 的方法关系

[[TODO-SOURCE:SUN2024/WINTER2020：说明继承边界，不把 Winter 代码当 Sun Stage 2]]

### 2.4 LLM 的结构化法规表示

[[TODO-SOURCE:BARRIENTOS2026：只写可借鉴工程原则与标签差异]]

### 2.5 本文定位

本文将前人比较分为同测集重跑、官方数据复现、论文报告值和跨阶段/跨任务四级；
只有共享 frozen IDs、Gold 和 evaluator 的同测集重跑才能作为严格方法优劣证据。

## 3. 问题定义与总体框架

### 3.1 Stage 1：Process Record

[[TODO-STATUS:S1.7：回填冻结实现与字段]]

### 3.2 Stage 2：Rule Record

Stage 2 输出统一包含 sample/clause ID、source text、modality、actor、action、
condition、constraint、exception、actor-action map、order relations 及 provenance。

### 3.3 Stage 3：Violation Report

[[TODO-STATUS:S3.11：回填 matching、violation type、证据和 BPMN 定位实现]]

## 4. 方法

### 4.1 B0：非 LLM 的 Sun Stage 2 独立重建

设计目标为 BERT-TextCNN 模态分类器与 CoreNLP/Tregex/Tsurgeon 六要素抽取器。当前
实现尚未达到该定义。[[TODO-STATUS:S2.6：完成后改为实现时态]]

### 4.2 H1：selective LLM fallback

H1 将复用同一 B0，只按看 test 结果前锁定的 trigger 修复失败或不确定字段。
[[TODO-DECISION:S2.8：回填 trigger、merge、失败策略和硬预算]]

### 4.3 D1：Direct LLM

D1 将在不读取 Gold 的前提下直接生成相同 Rule Record。
[[TODO-DECISION:S2.9：回填 prompt、few-shot、模型、temperature 和预算 hash]]

## 5. 数据与人工 Gold

### 5.1 官方 modality 数据

官方补充材料已被定位，但本地尚未完成 CSV ingestion、schema、许可和 split 核查。
[[TODO-STATUS:S2.1：回填实际行数、列、标签支持、hash、许可和 split]]

### 5.2 项目固定 EStG-150

项目固定唯一 150-record membership，并明确它不是 Sun 原始 150。审核采用五层
工作流，最终只能称 `LLM-assisted, human-adjudicated Gold`。当前 Layer E 输入门
就绪，但仍为 0/150 adjudicated。

[[TODO-STATUS:S2.2：回填人工审核统计和一致性/裁决说明]]

### 5.3 复杂法律语料

[[TODO-DECISION:G0.5/S2.11：在查看结果前冻结数据资格、复杂度 bins 和标签映射]]

## 6. 实验设计

### 6.1 Stage 2 baseline

最低覆盖：简单规则下限、一个强监督学习 baseline、完整 B0、H1 和 D1。模态分类与
六要素抽取分别报告，不能用只做分类的方法冒充完整 Stage 2。

### 6.2 Stage 3 baseline

最低覆盖：词法/检索下限、Winter、完整 Sun、一个现代 embedding/graph baseline；
LLM/Hybrid 只在 Oracle 非 LLM 比较稳定后加入。

### 6.3 指标与统计控制

Stage 2 分别报告模态分类和六字段/完整 Rule Record 指标；Stage 3 分别报告 matching
AP/MAP/Recall@k 和违规分类 P/R/F1。所有方法共享输入、Gold、schema、normalization
和 evaluator，复杂度分层在查看 test 结果前冻结。

## 7. 结果（仅模板）

### 7.1 Stage 2 主数据

| 方法 | 状态 | Modality Macro-F1 | 六字段指标 | 完整记录指标 | 失败/invalid | 成本 |
|---|---|---:|---:|---:|---:|---:|
| 简单规则 | TEMPLATE | — | — | — | — | — |
| 强监督 baseline | TEMPLATE | — | — | — | — | — |
| B0 | TEMPLATE | — | — | — | — | — |
| H1 | TEMPLATE | — | — | — | — | — |
| D1 | TEMPLATE | — | — | — | — | — |

[[TODO-RESULT:S2.10：只从 formal manifest 回填]]

### 7.2 复杂度分层与错误类型

[[TODO-RESULT:S2.12：回填预注册复杂度分层曲线和错误类型]]

### 7.3 Oracle Stage 3

[[TODO-RESULT:S3.7：与 end-to-end 分表]]

### 7.4 端到端消融

| 组合 | Stage 2 | Stage 3 | 状态 | 主要指标 |
|---|---|---|---|---|
| E00 | Sun | Sun | TEMPLATE | — |
| E10 | Improved | Sun | TEMPLATE | — |
| E01 | Sun | Improved | TEMPLATE | — |
| E11 | Improved | Improved | TEMPLATE | — |

[[TODO-RESULT:E00/E10/E01/E11：只从正式 manifests 回填]]

## 8. 讨论与局限性

当前可确认的复现边界包括：Sun 完整 Stage 2 源码、权重、完整 marker 和原始 150
phrase Gold 不可得；德文法规与英文公共 marker 之间需要显式语言适配；Sun 报告的
四个 GDPR BPMN 文件名尚未在现有证据中确定；不同论文的数据、split 和指标不能直接
用于严格显著性比较。

[[TODO-RESULT:S2.12/S3.10：结合正式结果讨论适用边界和失败案例]]

## 9. 结论

[[TODO-RESULT:P8：所有正式实验和主张复核完成后撰写]]

