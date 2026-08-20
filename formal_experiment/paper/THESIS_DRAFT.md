# BPC-Hybrid 论文工作稿

**状态**：DRAFT — 已启动写作，但无正式实验结果（注：Stage 2 三方法正式比较已于
2026-08-11 发布，正式数字见 §7.2，按 formal manifest 定向回填；这里是命名与方法
章节的连贯工作稿）
**写作语言**：中文；技术术语保留规范英文
**主张控制**：`CLAIM_EVIDENCE_MATRIX.md`
**命名约定（2026-08-08 导师要求锁定）**：本文统一使用正式名称 **Rules-Only /
Direct-LLM / Rules+LLM-Repair**；`B0`、`H1`、`D1` 仅作为 legacy 机器 ID，首次出现
时给出映射（如 “Direct-LLM（旧代号 D1）”），之后正文不再反复使用代号。

## 题目候选

面向设计时业务流程合规检查的法规语义解析：传统方法、大语言模型与混合方法的
分阶段比较

## 摘要

设计时业务流程合规检查需要把法规文本中的规范性要求与流程模型中的活动、参与者
和控制流进行对应。本文围绕 Sun et al. 提出的三阶段框架，设计一套可追溯的独立
重建与扩展实验：Stage 1 解析 BPMN 流程结构和标签语义，Stage 2 从法规文本中识别
模态及 actor、action、condition、constraint、exception，Stage 3 进行规则—流程
匹配和违规类型分类。研究将比较代表性非 LLM 方法、paper-faithful Sun 重建、
Direct-LLM（直接 LLM）和 Rules+LLM-Repair（选择性混合），并在预先冻结的复杂
法律语料上检验不同方法随复杂度增加的退化边界。

[[TODO-RESULT:S2.10：回填 Stage 2 主数据结果（正式三方法比较已于 2026-08-11
发布，见 §7.2，本处摘要待 S2.13 后回填复杂度分层）]]
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
不稳定输出和额外调用成本。因此，本文不预设“LLM 必然更优”，而是把 Direct-LLM、
不使用 LLM 的完整重建 baseline（Rules-Only），以及只在预注册失败/不确定条件下
调用 LLM 的 Rules+LLM-Repair（选择性混合）放在相同输入、Gold、输出合同和评价器
下比较。复杂法律语料是否会放大不同方法之间的差异，同样作为待检验问题，而不是
预先成立的结论。

### 1.1 研究问题

- RQ0：能否完整、可追溯地独立重建 Sun 的三阶段设计时合规检查框架？
- RQ1：传统方法、完整 Sun 重建、Direct-LLM 和 Rules+LLM-Repair 在 Stage 2 的
  模态分类与六要素抽取上如何比较？
- RQ2：法律文本复杂度增加时，各 Stage 2 方法如何退化，错误类型如何变化？
- RQ3：在 Gold Rule/Process Records 下，多个 Stage 3 baseline 与 LLM/Hybrid
  方法在匹配和违规类型分类上如何比较？
- RQ4：Stage 2 或 Stage 3 的局部改进能否转化为端到端提升？

### 1.2 预期贡献（待验证）

本文计划交付：三阶段独立重建及其可复现边界；统一 canonical contract 下的 Stage 2
多 baseline 比较；复杂法律语料上的复杂度分层与错误分析；Stage 3 Oracle 与
end-to-end 分离评价；以及解释 Stage 2、Stage 3 和二者交互贡献的受控消融。
方法层面，本文把 Direct-LLM 的实现拆分为 8 个可独立叙述与消融的模块，把
Rules-Only 拆分为 8 个模块，并逐模块与 Barrientos et al. (2026) 的直接借鉴来源
做对照（见 §4、§6.4）。

[[TODO-STATUS:S2.13/S1.7/S3.11：各阶段冻结后将“计划”改为已完成贡献]]

## 2. 相关工作

### 2.1 设计时业务流程合规检查

[[TODO-SOURCE:WINTER2020/AGOSTINELLI2019：核对原论文并撰写]]

### 2.2 法律文本的 modality 与语义要素抽取

[[TODO-SOURCE:MICHEL2022/SLEIMI：核对数据、类别和 marker 方法]]

### 2.3 Sun 与 Winter 的方法关系

[[TODO-SOURCE:SUN2024/WINTER2020：说明继承边界，不把 Winter 代码当 Sun Stage 2]]

### 2.4 LLM 的结构化法规表示与 Barrientos et al. (2026)

Barrientos et al. (2026) 是本文**直接借鉴的工程方法来源**，借鉴内容包括：
LLM 结构化输出、严格 JSON schema、受控词汇（controlled vocabulary）、确定性
验证与归一化、traceability，以及稳定性与评估纪律。需要严格区分三类证据：
(1) 论文正文的自动 RC4PC 方法评价——3 个场景、36 条 requirements，完整流程
独立运行 5 次，Step 1 报告 P/R/F1、strict JSON 和基于 pairwise distance≤2 的
self-consistency；(2) artifact 中的专家标注协议——“20 requirements × 2 versions
× 2 experts = 80 annotations”，Cohen’s κ=0.52 是专家对 20 个变更影响的
NC/OC/NE 判断一致性；(3) 本文拟新增的适配指标（如 style-equivalent 敏感性），
必须分表报告，不得把专家协议指标冒充论文自动实验主指标。
Barrientos 不是本文的任务/schema 主干，不能直接用其 change-impact schema 替换
Sun 六要素 Rule Record（详见 §4.4 对比表）。

[[TODO-SOURCE:BARRIENTOS2026：核对刊物/页码/表号]]

### 2.5 本文定位

本文将前人比较分为同测集重跑、官方数据复现、论文报告值和跨阶段/跨任务四级；
只有共享 frozen IDs、Gold 和 evaluator 的同测集重跑才能作为严格方法优劣证据。
与 Barrientos 的对比中，本文禁止因为任务/schema 不同，就用单一 F1 宣称“综合
上我的方法更好”；跨 schema 比较必须写明适配限制与可比较性边界。

## 3. 问题定义与总体框架

### 3.1 Stage 1：Process Record

[[TODO-STATUS:S1.7：回填冻结实现与字段]]

### 3.2 Stage 2：Rule Record

Stage 2 输出统一包含 sample/clause ID、source text、modality（4 类，含 evidence
span 与 label 分离）、actor、action、condition、constraint、exception、
actor-action map、order relations 及 provenance。

### 3.3 Stage 3：Violation Report

[[TODO-STATUS:S3.11：回填 matching、violation type、证据和 BPMN 定位实现]]

## 4. 方法

本节把三种方法写成**细模块**。方法不是“我们调用了一个 LLM”或“我们写了一个
正则”，而是由一组可独立叙述、可单独消融的模块构成；每个模块说明它解决什么问题、
输入/输出与不变量、去掉该模块会造成什么失败、如何验证模块有效，以及它与
Barrientos 对应模块的相同点、差异点和适配理由。目标是为论文方法章节提供 4–5 页
的可写骨架（见 `MASTER_PIPELINE.md` §8.8.4）。

### 4.1 Rules-Only（纯规则法，旧代号 B0）

**一句话**：非 LLM 传统流水线——BERT-TextCNN 模态分类 + public marker 路由 +
CoreNLP 句法/依赖抽取 + Tregex/Tsurgeon 六要素规则抽取，是 Sun Stage 2 的
方法级独立重建（非 exact reproduction）。机器 ID `sun_rule_only`。

Rules-Only 拆为 8 个模块：

1. **Public marker lexicon 重建**。
   - 解决的问题：Sun 的完整私有 marker lexicon 不可得，需要一个来源可定位、
     hash 固定的受控 cue 词典来驱动标记抽取。
   - 输入/输出/不变量：输入 = 9 个公开来源的 cue（Sleimi/LexNLP/Wiktionary 等
     引证）；输出 = `public_marker_lexicon_en_v1`（5 类 64 个英文公开 marker）与
     actor 等扩展词典（v2 激活项上游）；不变量 = source/hash/版本锁定、
     development-only、禁止评测数据回流。
   - 去掉该模块会失败：condition/constraint/exception/actor 的 marker 触发层
     全部失效，抽取退化为无 cue 的启发式。
   - 如何验证：S2.3 机器门禁（来源、规则、语言、hash、空扩展表离线锁定）。
   - 与 Barrientos 对照：Barrientos 也有受控词汇（44 模式、4 维度
     control_flow/resource/data/time），但那是 change-impact 表示的规范化分类
     字典；我们的是六要素抽取 cue 词典。相同点=“用受控词汇约束输出”；差异点=
     用途（抽取触发 vs 表示分类）；适配理由=两者任务不同（六要素抽取 vs 变更影响
     表示），不能互相替代。

2. **BERT-TextCNN 模态分类**。
   - 解决的问题：为先验模态提供强监督非 LLM 基线（RQ1），也是 Sun 论文的方法主干。
   - 输入/输出/不变量：输入 = clause 文本；输出 = modality 4 类候选；不变量 =
     checkpoint/config/manifest 三重 hash 绑定、inference-only、不做 test 调参。
   - 去掉该模块会失败：模态分类只能靠 marker，非 marker 型 clause 召回显著下降。
   - 如何验证：S2.4 重建 + 锁定分类器契约测试。
   - 与 Barrientos 对照：Barrientos 没有非 LLM 分类器（直接用 LLM 输出 modality）；
     我们的分类器是 Sun-compatible 重建资产，用于与 LLM 对称比较。

3. **Marker routing 与德英 cue 验证**。
   - 解决的问题：把 modality evidence span 路由到 4 类 label，并在德（源）英
     （翻译）两侧做一致性验证，避免“伪 validated”。
   - 输入/输出/不变量：输入 = modality evidence 与 DE/EN clause 对；输出 =
     label + validated/unsupported 路由；不变量 = 无伪 validated、跨语言 cue
     验证（B0-R1-ALIGN 修复后 validated 107→49）。
   - 去掉该模块会失败：modal label 面板混淆上升（historical 79.3% 准确率中的
     路由混淆来源），路由输入不可靠。
   - 如何验证：`test_b0_r1_align_cue_validation.py` + label 面板。
   - 与 Barrientos 对照：Barrientos 无跨语言 cue 验证（英文单语）；这是我们对
     德英数据适配的必要工程。

4. **CoreNLP 句法/依赖抽取**。
   - 解决的问题：为 Tregex 树模式与 actor/action 归属提供成分/依赖解析。
   - 输入/输出/不变量：输入 = 原句；输出 = Stanford CoreNLP 4.5.10
     （tokenize/ssplit/pos/lemma/parse/depparse）结构；不变量 = 版本锁定、
     jar 身份记入 manifest。
   - 去掉该模块会失败：所有结构驱动的规则抽取（Tregex/actor 归属）无解析输入。
   - 如何验证：`test_s25_corenlp_contract.py`。
   - 与 Barrientos 对照：Barrientos 不依赖本地 DSL 解析栈（LLM 直接输出）；
     我们为 Sun Stage 2 方法级重建保留 CoreNLP。

5. **Tregex 模式注册表**。
   - 解决的问题：把语言 cue 翻译成树匹配模式，抽取六要素候选 span。
   - 输入/输出/不变量：输入 = parse tree + `sun_phrase_patterns_v3_enhanced.json`
     （六字段 28 模式）；输出 = 候选 span；不变量 = `<`/`<<` 语义有真实 bridge
     测试（B0-R1-BRIDGE）、`test_time_rule_edits_forbidden=true`。
   - 去掉该模块会失败：无结构候选产生，六要素抽取整体失效。
   - 如何验证：`test_b0_r1_bridge_semantics.py`（真实编译运行）。
   - 与 Barrientos 对照：Barrientos 无 Tregex 等价物（表示层为 LLM 结构化输出）；
     这是 Sun 特色的句法规则层。

6. **Tsurgeon fail-closed 守卫**。
   - 解决的问题：Sun 的 Tsurgeon 手术在本地是“诚实非实现”——registry 当前无
     operation、`tsurgeon_enabled=false`；守卫保证 operated 多命中 fail-closed，
     而非伪实现。
   - 输入/输出/不变量：输入 = Tregex 匹配 + (空) operation 集；输出 = 若启用则
     手术、当前关闭；不变量 = 多命中拒绝、绝不伪造手术。
   - 去掉该模块会失败：要么伪实现（造假），要么无守卫（多命中误消费）。
   - 如何验证：`test_b0_r1_bridge_semantics.py` 的 multi-match 守卫。
   - 与 Barrientos 对照：Barrientos 无 Tsurgeon 等价物（其“normalization”是
     JSON 层的确定性归一化，不是树手术）；这是已披露的适配限制。

7. **Actor/Action 归属解析**。
   - 解决的问题：把名词短语与动词短语正确归属到 actor/action 字段，避免 action
     span 吞并 constraint、漏抽多词 actor、被动句 by-agent 误归属。
   - 输入/输出/不变量：输入 = 依赖树 + actor 词典；输出 = actor/action span 与
     actor-action 候选；不变量 = 无主语开头 action（8→0）、actor R 0.958
     （B0-R1-ACTION/ACTOR 修复后）。
   - 去掉该模块会失败：字段归属错误主导（79% 的 missed Gold span 内容被抽到
     其它字段）。
   - 如何验证：`test_b0_r1_action_span_scope.py`、`test_b0_r1_actor*` + 主口径重评。
   - 与 Barrientos 对照：Barrientos 的 actor 表达在 `action.resources` 层面；
     我们把 actor 作为六要素一等公民，归属语义不同。

8. **确定性评价与可复现性资产**。
   - 解决的问题：让非 LLM 方法在共享 Gold/evaluator 下可重放、可审计。
   - 输入/输出/不变量：输入 = attempts + canonical Gold；输出 =
     `sun_literal_overlap_evaluation@2.0.0` 指标 + manifest；不变量 = 同输入
     确定性重放、粗/细 Gold 双口径、主/对照口径分表。
   - 去掉该模块会失败：方法与其它方法不可比，无法进入同一评价表。
   - 如何验证：B0-R3/R4 同进程双评、主口径与历史快照一致。
   - 与 Barrientos 对照：两者都强调 deterministic normalization 与评估纪律
     （相同点）；我们用 span overlap 主口径，Barrientos 用 Step-specific
     P/R/F1 + strict JSON 合法性 + self-consistency。

**总体结果（formal，2026-08-11 三方法正式比较，粗 Gold 主口径）**：Rules-Only
五字段 F1——actor 0.8203、action 0.8927、condition 0.7738、constraint 0.6182、
exception 0.8800，粗五字段 mean F1 0.797；modality label accuracy 0.74 /
macro-F1 0.7128。字段级约束 P/R/F1 与 modality label 分表（modality
evidence-span 在正式 Gold 中为普通字符串字段，结构性地 unavailable，不置零不
纳入 aggregate）。

### 4.2 Direct-LLM（直接 LLM，旧代号 D1）

**一句话**：纯 LLM 端到端生成同一六要素 Rule Record，不读取 Rules-Only 预测、
不读取 Gold；核心是可验证的六要素证据契约 + 锁定配方（prompt hash、model、
sampling、transport、budget）。机器 ID `direct_llm`。

Direct-LLM 拆为 8 个模块：

1. **六要素 schema 与证据契约**。
   - 解决的问题：LLM 输出必须可验证——每个 evidence 都是 source 的 verbatim
     span（`text == source[start:end]`）、clause 内 span、actor-action map、
     order relations、`unsupported_or_ambiguous` 兜底。
   - 输入/输出/不变量：输入 = source_text；输出 = 满足
     `stage2_extraction_contract@1.0.0` 与 `stage2_prediction.schema@1.0.0` 的
     canonical record；不变量 = 每个 evidence 必须等于原文精确切片、子 span 必须
     位于 clause span 内。
   - 去掉该模块会失败：输出不可验证，坏 span/clause/边无法被下游检测，等于
     接受黑盒输出。
   - 如何验证：canonical validator（格式/回指/字段权限）+ 契约 hash 三方锁定。
   - 与 Barrientos 对照：相同点 = 严格 JSON schema 与验证每个 LLM 输出；差异点 =
     schema 内容不同（我们六要素 + 原文 span，他 RC4PC precondition/norms/
     temporal_validity）；适配理由 = 任务不同（抽取 Sun 六要素）。

2. **Prompt 字段定义与 v1→v6 演进**。
   - 解决的问题：constraint 字段召回弱（基线 R=0.288），主要因为“constraint
     语义未在 prompt 中显式定义，内容被并入 action/condition 或完全漏抽”。
   - 输入/输出/不变量：输入 = v1→v6 prompt 版本线；输出 = 锁定 v6
     （`direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md`，SHA-256
     3aa64877…）；不变量 = 每次变更走 “真实验证 pilot → delta 记录 → KEEP/
     REJECT”，禁止读 Gold 反向调 prompt。
   - 去掉该模块会失败：constraint R 回落到 ~0.288（99 个 constraint 内容进
     action、16 个进 condition、91 个完全未抽）。
   - 如何验证：D1-R1 的 v5→v6 配对 pilot + 150 全量：constraint R 0.288→0.417、
     Overall F1 0.7669→0.7735。
   - 与 Barrientos 对照：相同点 = prompt 中给出详细抽取指令与字段枚举；差异点 =
     我们的字段定义针对 Sun 六要素，且“空=absent”语义与“不确定入
     unsupported_or_ambiguous”是本项目合同；适配理由 = schema 不同。

3. **Gold-blind 合成 few-shot fixture**。
   - 解决的问题：低资源字段（condition/constraint/exception）需要在 few-shot 中
     展示，但又不能让测试集通过 few-shot 泄漏 Gold。
   - 输入/输出/不变量：输入 = 6 个合成样例（覆盖 condition/constraint/exception
     缺口）；输出 = Gold-blind fixture；不变量 = 与 150 测试句零交叠（S2.9 DoD）。
   - 去掉该模块会失败：低资源字段缺少正例示范，漏抽/错标上升。
   - 如何验证：`verify_d1_few_shot_fixtures.py` + Gold 不可见核查。
   - 与 Barrientos 对照：Barrientos prompt 也有示例，但没有“合成 + 与测试集零
     交叠”的 Gold-invisible 保证；这是我们的适配（数据隔离纪律）。

4. **结构化输出 transport 配方**。
   - 解决的问题：官方 deepseek-v4-pro 端点在 provider 默认 thinking 下返回空
     内容、在 json_object 下返回不同嵌套形状——需要固定可复现调用层。
   - 输入/输出/不变量：输入 = prompt + source；输出 = transport 配方
     （thinking-disabled、response_format=null、stream=false、temp 0/top_p 1/
     max_tokens 4096）；不变量 = 150/150 有效、0 事故（clean rerun）。
   - 去掉该模块会失败：结构化输出形状不稳定、事故率升高、可复现性被破坏。
   - 如何验证：D1-R1-CLEAN-RERUN / D1-R3 干净重跑（0 lost/recovery/retry）。
   - 与 Barrientos 对照：相同点 = 报告 strict JSON 合法性与稳定性设计；差异点 =
     我们的 transport 是对官方端点的实证适配（thinking 关闭、无 json_object）。

5. **Canonical validator、span canonicalizer 与确定性后处理**。
   - 解决的问题：把 LLM 原始输出转成严格契约数据；坏 span/clause/边丢弃并审计，
     坐标重锚采用 fail-closed unique exact-text re-anchor。
   - 输入/输出/不变量：输入 = LLM 原始输出；输出 = canonical record + 审计；
     不变量 = 无法唯一回指的 span 整 patch 拒绝，不做模糊猜测。
   - 去掉该模块会失败：schema 合法但语义/回指损坏的输出进入结果。
   - 如何验证：validator + canonicalizer 测试（含 Rules+LLM-Repair 的 span
     canonicalizer 离线 replay 3/3 re-anchor）。
   - 与 Barrientos 对照：相同点 = validation 后的 deterministic post-processing
     与 normalization；差异点 = 我们加 fail-closed unique exact-text re-anchor
     （Rules-Only/Rules+LLM-Repair 的坐标漂移防护）。

6. **API 预算、授权与硬停止合同**。
   - 解决的问题：真实 LLM 调用必须有成本与事故控制。
   - 输入/输出/不变量：输入 = 逐批用户授权 + `--max-calls` 硬上限；输出 =
     manifest 记录 llm_calls/max_calls/模型/采样/失败率；不变量 = 无授权不调用、
     retry 需授权、无测试调参。
   - 去掉该模块会失败：成本失控、可复现性与审计缺失。
   - 如何验证：S2.9/D1-R2 预算合同（150 calls 硬上限）+ 历史运行登记。
   - 与 Barrientos 对照：Barrientos 报告成本/延迟/失败率（相同点是成本与失败
     计数纪律）；差异点 = 我们把它做成逐批授权 + 硬停止的合同（项目治理）。

7. **双口径评价与错误类型归因**。
   - 解决的问题：单一 Gold 口径会掩盖“标注粒度/定义差异”与“方法缺陷”的区别。
   - 输入/输出/不变量：输入 = 同一进程双评（细 Gold 1055 spans 对照口径、粗
     Gold 609 spans Sun 句子级主口径）；输出 = 主表 + 失败类型归因
     （matched/wrong_field/not_extracted）；不变量 = 主/对照分表、modality
     evidence-span 单独报告。
   - 去掉该模块会失败：无法区分“抽错字段”与“漏抽”，跨方法/跨口径比较失真。
   - 如何验证：D1-R3 失败类型分析（1055 gold spans：matched 732、wrong_field
     169 其中 constraint 100、not_extracted 154）。
   - 与 Barrientos 对照：相同点 = 分维报告（Step-specific P/R/F1）；差异点 =
     我们加 span-overlap + 错误类型归因；适配 = Sun 六要素 span 合同。

8. **Prompt/config/manifest hash 与可复现性资产**。
   - 解决的问题：LLM 运行的可复现性。
   - 输入/输出/不变量：输入 = prompt 磁盘文件、loader、manifest；输出 = v6
     prompt hash 三方一致（3aa64877…）、注册表
     `configs/models/estg150_d1_active_registry_v1.json`；不变量 = hash 三方
     锁定、同输入同配置重放。
   - 去掉该模块会失败：无法证明同一 prompt/模型/采样下的可重放性。
   - 如何验证：D1-R2 lock-config 测试（12 项，含 Gold 不可见核查）。
   - 与 Barrientos 对照：相同点 = temperature 0 + 稳定性设计；差异点 =
     Barrientos 论文是 36 条 requirements × 5 次完整运行报 self-consistency，
     我们当前只有 temp0 + hash 锁定，同协议 5 次正式重跑尚未执行（AB-9 待授权）。

**总体结果（formal，2026-08-11 三方法正式比较，粗 Gold 主口径）**：Direct-LLM
五字段 F1——actor 0.7579、action 0.9437、condition 0.8380、constraint 0.7427、
exception 0.7619，粗五字段 mean F1 0.8088；modality label accuracy 0.8333 /
macro-F1 0.7695。字段级结论：Direct-LLM 在 action/condition/constraint 与
modality label accuracy 领先；actor 字段落后 Rules-Only。禁止显著性推断，仅描述
性字段级比较。

### 4.3 Rules+LLM-Repair（规则+LLM 修复，旧代号 H1）—— 对照负结果

**一句话**：同一 Rules-Only，仅按预注册 trigger 让 LLM 修复失败/不确定字段；
**不作为贡献，只作为对照臂证明“无足够证据约束的选择性 LLM 修复可能产生净负
收益”**。机器 ID `sun_llm_fallback`。

**正式对照结果（2026-08-11 三方法正式比较，粗 Gold 主口径）**：Rules+LLM-Repair
五字段 F1——actor 0.4296、action 0.8945、condition 0.7774、constraint 0.6200、
exception 0.8800，粗五字段 mean F1 0.7203（vs Rules-Only 0.797、Direct-LLM
0.8088）；modality label accuracy 0.82 / macro-F1 0.8123。正式结论（描述性）
confirm 该对照方法在 actor 字段 net-negative（actor F1 0.4296 vs Rules-Only
0.8203 / Direct-LLM 0.7579），与 2026-08-08 停止优化决策一致。

**development 全量 150 负结果（commit 74614e3，2026-08-08，粗 Gold 主口径）**：
- 主口径 F1 0.7621 vs Rules-Only 0.7986（−0.0365 净负）；细 Gold F1 0.6875 vs
  0.7186（同样净负）；
- LLM 修复在 actor 字段过度抽取：P 0.7077→0.2754、actor spans 65→167；
- 机制本身工作正常（103 accepted / 89 changed / gate=True / 0 incidents），
  问题出在 **trigger+repair 配方增加 false positives 而非召回**。

**三个难点（可写进讨论）**：
1. **trigger 与失败错位**：trigger 只能看到推理时信号（低置信、结构冲突、候选
   多义），而 Rules-Only 压倒性失败模式是“字段归属错误”（79% 的 missed Gold
   span 内容被抽到其它字段）——这类失败在推理时不可见，Gold-blind trigger 无法
   对准真正需要修复的样本。
2. **修复难以约束在字段边界内**：请求补 actor 时 LLM 倾向扩大 span、补多个候选，
   把 precision 打穿（actor spans 65→167 的直接原因）。
3. **收益上限受限**：修复收益被触发子集覆盖限制，成本—收益不利。

**优化方向（仅供未来参考，当前不执行）**：保守修复配方（actor span 长度上限 +
候选数上限 + 修复后 verbatim 回指强制校验）；用 risk-coverage 曲线在 development
上选择触发子集；字段级白名单 + patch 前后 diff 约束。**论文表述约束**：只能作为
对照臂报告“选择性混合”的负结果，不得把该对照方法写成项目贡献，不得再派发其
优化任务。

### 4.4 与 Barrientos et al. (2026) 的逐模块对比表

以下表格从 15 个维度对比 Barrientos 方法与本文方法；**禁止**因任务/schema 不同就
用单一 F1 宣称“综合上我的方法更好”。（取值依据见 `docs/research/
BARRIENTOS_BORROWING_AUDIT_2026-07-12.md` 与 `docs/EVAL_3DIM_SPEC.md`。）

| 维度 | Barrientos et al. (2026) | 本文（Rules-Only / Direct-LLM） | 可比较性 |
|---|---|---|---|
| 任务目标 | regulatory requirement **change-impact** analysis | Sun-compatible 六要素抽取（Stage 2）+ 后续 Stage 3 匹配 | 任务不同 → C4 跨任务 |
| schema | RC4PC：`id + precondition + norms + temporal_validity` | `modality/actor/action/condition/constraint/exception + evidence spans + maps` | schema 不同，不能照搬 |
| modality 类别 | 3 类（obligation/permission/prohibition） | 4 类（+ `definition`，Sun 主干） | 需显式扩展，不能直接照抄 enum |
| evidence span | 无独立原文 evidence span（结构化对象） | 每个要素 verbatim span（`text==source[start:end]`） | 可比较性受限（Barrientos 无 span 概念） |
| controlled vocabulary | 44 模式 × 4 维度（control_flow/resource/data/time）约束 normalized view | public marker lexicon（英文 64 个）+ 受控 six-field schema | 都是“受控词汇”纪律，用途不同 |
| JSON validation | strict JSON schema（对每个 LLM 输出验证） | canonical validator（格式/回指/字段权限） | 相同点=强验证 |
| deterministic normalization | 有（论文声明 normalization） | fail-closed canonicalizer + span canonicalizer | 相同点=确定性归一化 |
| stability design | 36 条 × 完整流程运行 5 次，Step 1 pairwise distance≤2 self-consistency | temp0 + prompt hash 三方锁定；同协议 5 次重跑未执行（AB-9） | 设计对齐、执行缺口 |
| evaluation metrics | Step-specific P/R/F1 + strict JSON 合法性 + self-consistency | span-overlap 主口径 + 细/粗 Gold 双口径 + modality label 面板 | 主指标不同（span vs 结构化）；分表报告 |
| expert protocol | artifact：semantic coverage / structural encoding / deontic correctness + style-equivalent alignment；κ=0.52（20 个变更影响的 NC/OC/NE 一致性） | 本项目拟新增 style-equivalent 敏感性（未实现，AB-10）；Gold 为 user-adjudicated | 专家协议指标≠论文自动实验主指标，禁止冒充 |
| traceability | recording LLM 增加/修复的内容 | runner 记录 prompt/model/sampling/预算/失败率 + manifest | 相同点=traceability 纪律 |
| API/reproducibility contract | temperature 0 + 运行结果存档 | 逐批授权 + 硬停止 + prompt hash 三方 + transport 配方 | 相同点=稳定性与可复现；差异=授权治理 |
| 适合 Barrientos 的场景 | 需求变更对流程影响的自动分析、合规模式分类 | 六要素 span 抽取、Sun Stage 2/3 转写 | 各有所适 |
| 适合本文方法的场景 | Sun 六要素抽取、错误归因、复杂度分层、Stage 3 输入端 | 同上 | 任务定义决定 |
| 可否直接做数字比较 | **不能**——任务/schema/指标均不同（C4 跨任务约束） | 同左 | 只能用同一 frozen IDs/Gold/evaluator 的 C1 重跑比较 |

**综合结论（有条件）**：
- 哪些方面本文方法更好：六要素 span 回指、错误类型归因、Gold-blind few-shot
  隔离、逐批授权硬停止治理（有实现证据）。
- 哪些方面 Barrientos 更完整或更合适：change-impact 表示、44 模式受控分类、
  5 次完整运行的稳定性报告、专家 multi-dimension 标注协议（论文已实现）。
- 哪些差异来自任务定义：schema、modality 类别数、evidence span、评估单元——
  这些是任务/表示差异，不构成方法优劣。
- 哪些结论已有数据：温度 0、严格 JSON schema、确定性验证/归一化、traceability、
  成本/失败率纪律——本文 Direct-LLM 已实现并有运行证据。
- 哪些仍是假设、必须等待消融：模块级替换/去除的影响（AB-1–AB-5）、稳定性 5 次
  重跑（AB-9）、style-equivalent（AB-10）——这些必须等真实数据，不得现在写成
  “已完成”。

## 5. 数据与人工 Gold

### 5.1 官方 modality 数据

官方补充材料已被定位，development schema/split 已锁定（2,831 analysis rows，
train/dev/test=1985/420/426，许可仍 unknown_pending_confirmation）。
[[TODO-STATUS:S2.1：formal use 解锁与最终行数回填]]

### 5.2 项目固定 EStG-150

项目固定唯一 150-record membership，并明确它不是 Sun 原始 150。审核采用五层
工作流，最终只能称 `LLM-assisted, human-adjudicated Gold`。150/150 已裁决并
冻结（2026-08-06 用户裁决经授权恢复验证；formal Gold 已于 2026-08-10 发布）。

[[TODO-STATUS:S2.2：回填人工审核统计和一致性/裁决说明的论文版本]]

### 5.3 复杂法律语料（S2.11）

Barrientos 3 个场景、36 条固定 IDs 的复杂语料已冻结并发布正式 Gold
（`data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json`，SHA
039ae8b2…，36/36 adjudicated、0 unresolved）。Gold 逐记录等值复制用户裁决的
canonical decisions（provenance=`deepseek_offline_proposal_v3` +
`user_batch_confirmation` by hyc），不得表述为独立专家从零标注。复杂度合同
G0.5 已冻结（`configs/g05_complexity_frozen_v1.json`）。第三方原文 local-only，
提交资产只含 hash/坐标/必要标签。

## 6. 实验设计

### 6.1 Stage 2 baseline（0.5 行改为两行）

最低覆盖：简单规则下限、一个强监督学习 baseline、完整 Rules-Only、Rules+
LLM-Repair 和 Direct-LLM。模态分类（4 类 label 另表）与六要素抽取（span
P/R/F1 主表，modality evidence-span 单独/辅助）分别报告，不能用只做分类的方法
冒充完整 Stage 2。

### 6.2 Stage 3 baseline

最低覆盖：词法/检索下限、Winter、完整 Sun、一个现代 embedding/graph baseline；
LLM/Hybrid 只在 Oracle 非 LLM 比较稳定后加入。

### 6.3 指标与统计控制

Stage 2 分别报告模态分类和六字段/完整 Rule Record 指标；Stage 3 分别报告 matching
AP/MAP/Recall@k 和违规分类 P/R/F1。所有方法共享输入、Gold、schema、normalization
和 evaluator，复杂度分层在查看 test 结果前冻结。与 Barrientos 的数字比较必须
分表并标证据等级（C1–C4）。

### 6.4 受控消融 AB-1–AB-10（现状）

“模块替换/去除”消融矩阵的设计与现状见 `paper/ABLATION_MATRIX.md`。原则：
(1) 每项消融输出“我的完整模块 / 换成 Barrientos 模块 / 去掉模块 / 我的优势 /
Barrientos 优势 / 综合结论 / 可比较性限制”的结构化结论；(2) 没有正式数据时标记
“待运行”或“仅已有历史证据”，不得把“已经设计矩阵”写成“已经完成实验”；
(3) 涉及真实 LLM 的 AB-2/AB-4/AB-9 必须逐批用户授权。已锁定零 API 消融项：
AB-1（v5→v6 历史证据：constraint R 0.288→0.417）、AB-3（4 类→3 类投影需新
离线脚本，输入已具备）、AB-5（validator/canonicalizer 的离线作用分析，仅设计 +
历史证据）、AB-6（150/150 有效、0 事故历史证据）、AB-7（细/粗/Sun-marker 三
口径已成表）、AB-8（Rules-Only 各模块批次的既有结果）。

## 7. 结果

### 7.1 结果模板（legacy 机器 ID；正式数字见 §7.2 与 §7.3）

| 方法 | 状态 | Modality Macro-F1 | 六字段指标 | 完整记录指标 | 失败/invalid | 成本 |
|---|---:|---:|---:|---:|---:|---:|
| 简单规则 | TEMPLATE | — | — | — | — | — |
| 强监督 baseline | TEMPLATE | — | — | — | — | — |
| B0 | TEMPLATE | — | — | — | — | — |
| H1 | TEMPLATE | — | — | — | — | — |
| D1 | TEMPLATE | — | — | — | — | — |

[[TODO-RESULT:S2.10：只从 formal manifest 回填（正式三方法比较见 §7.2，模板保留
legacy 行以对应机器 ID）]]

### 7.2 Stage 2 正式三方法比较（FORMAL，2026-08-11）

来源：`outputs/reports/stage2_formal_three_method_comparison_v1.json`
（report SHA c9d76544…，manifest dc41eb4b…）；G0.4 授权口径：句子级粗 Gold
五字段 span 主视图 + modality four-class label 分表；modality evidence-span
结构性地 unavailable（不置零不纳入 aggregate）；细 Gold 为诊断/对照；
历史六字段 aggregate 仅 development provenance 不混入。数据规模 150 句；
历史真实调用（含 Rules+LLM-Repair 对照 arm）300、本轮新增 0。

**5 字段 span 主视图（粗 Gold，F1）**

| 方法 | actor | action | condition | constraint | exception | 五字段 mean F1 | Modality label acc / macro-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Rules-Only（旧代号 B0） | 0.8203 | 0.8927 | 0.7738 | 0.6182 | 0.8800 | 0.797 | 0.7400 / 0.7128 |
| Direct-LLM（旧代号 D1） | 0.7579 | 0.9437 | 0.8380 | 0.7427 | 0.7619 | 0.8088 | 0.8333 / 0.7695 |
| Rules+LLM-Repair（旧代号 H1，对照） | 0.4296 | 0.8945 | 0.7774 | 0.6200 | 0.8800 | 0.7203 | 0.8200 / 0.8123 |

字段级结论（描述性，禁止显著性推断）：Direct-LLM 在 action（+0.051）、condition
（+0.064）、constraint（+0.125）与 modality label accuracy（0.8333 vs 0.7400）
领先 Rules-Only；Rules-Only 在 actor（+0.062）与 exception（+0.118）领先
Direct-LLM；Rules+LLM-Repair 因 actor 过度抽取而 net-negative（actor F1 0.4296，
vs Rules-Only 0.8203 / Direct-LLM 0.7579）。**无整体胜者声明**。

### 7.3 复杂度分层与错误类型（S2.12，零 API arm）

复杂语料（S2.11，36 条固定 IDs）上 Rules-Only 零 API arm（B0 v10a、CPU、0
API/0 network、cost=$0）：overall modality accuracy / macro-F1 = 0.638889 /
0.535461；五字段 span P/R/F1 = 0.862319 / 0.802721 / 0.831453；L1=31、L2=5、
L3=0（无样本，不报性能）。这是**单一 zero-API arm**，不是三方法比较；
Direct-LLM 与 Rules+LLM-Repair 两个 API arms 仍 pending explicit authorization
（授权申请见 `docs/API_AUTHORIZATION_REQUEST.md`）。

[[TODO-RESULT:S2.12：API 授权后回填 Direct-LLM / Rules+LLM-Repair 复杂语料臂与
三方法完整比较、最终冻结]]

### 7.4 Oracle Stage 3

[[TODO-RESULT:S3.7：与 end-to-end 分表]]

### 7.5 端到端消融

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
用于严格显著性比较。以下按方法列出**基于量化证据**的局限：每条包含定量证据、具体
文本例子、错误原因、方法边界、可能优化方向，以及“为什么当前没有继续优化或为什么
仍需实验”。

### 8.1 Rules-Only（纯规则法）的局限性

1. **action 吞并 constraint（字段归属错误主导）**。
   - 定量证据：C1 分析显示 matched 的 212 个 action 中 192 个（91%）预测长于
     Gold、中位超出 54 字符；constraint 的 143 个 missed 中 57 个仅被 action
     覆盖。
   - 文本例子：`"the data shall be processed only to the extent necessary"`
     整段被并入 action，而 Gold 将 `"to the extent necessary"` 归 constraint。
   - 错误原因：`_subtree_span` 把 nsubj/全部依赖纳入 action 子树（B0-R1-ACTION
     已修主语开头 8→0，但边界/从句尾部仍有残余）。
   - 方法边界：Bedrock any-overlap 主口径对边界不敏感；修复主要体现在诊断面板
     （strict-exact action F1 3.0×）。
   - 可能优化方向：从句尾/编号残余的进一步收紧、C7 under-extension 与 C1 的
     双向平衡。
   - 为何没有继续：主口径非指标驱动项（真实运行 F1 持平），继续优化对主表无贡献、
     风险>收益；需正式 Gold 后按需再议。

2. **constraint↔condition 双向混淆**。
   - 定量证据：C2 分析——114 个 extra constraint 压 condition Gold、31 个反向；
     “to the extent” 双触发（44 个同界双发中 43 个为双 tregex）；SCOPE-DISAMBIG
     候选真实运行 F1 −0.0005 已回退。
   - 文本例子：`"to the extent"` 同时命中 `to<<an|the` 与 `to<<extent|purpose`
     两类模式。Gold 自身对 `that/who/to the extent/only` 的 condition/constraint
     标注内部不一致（见 B0_ERROR_ANALYSIS §8.3 cue 一致性统计）。
   - 错误原因：规则层共享 cue + Gold 定义口径差异；“不读 Gold 反向调规则”的
     硬约束下规则层无法安全消歧。
   - 方法边界：记为该规则方法的**方法局限**而非代码缺陷；P 侧需双边收敛验证。
   - 可能优化方向：registry 模式层复核（去掉 constraint 对 “to the extent” 的
     捕获）、逐条上下文约束。
   - 为何没有继续：候选实测净负，任何偏向都对称损失匹配；调整属于 registry/
     scope 层改动，需用户决策，当前不做。

3. **词典覆盖不足**。
   - 定量证据：13 个无词典覆盖名词漏抽（successor/spouse/child/developers/bank/
     body/society/owners/shareholders/beneficiary），代词 `It` 作 actor 需 Gold
     语义裁决（未覆盖 1/48）。
   - 文本例子：`"the body shall ensure…"`、继承人/配偶等法律 actor 名词不在 actor
     词典。
   - 错误原因：方法以“名词短语 + 词典 + 依赖关系”为 actor 判据；公开 marker
     lexicon 为 dev-only（禁止训练/评测数据回流）。
   - 方法边界：词典规模与方法细节差异属已披露适配，不阻断方法级复现。
   - 可能优化方向：向用户申请公开法律 actor 名词来源扩展；或 local-frozen
     授权扩展（路径 b 已用过一次：13 名词以 source
     `authorized_local_frozen_estg150_gap_2026_08_04` 加入）。
   - 为何需要用户决策：S2.3 对公开种子有严格来源约束，“看词典缺口反推词典”
     属于治理覆盖，不能由 Agent 自行决定。

4. **Sun marker 定义与当前 Gold 定义口径差异**。
   - 定量证据：我们的 constraint Gold 302 个中仅 13 个（4%）符合 Sun Table-4
     公开 marker 定义（Sun 自己仅 35 个 constraint）；定义范围宽约 8–23 倍；
     Sun-marker 收敛后 Rules-Only constraint R=1.0 (13/13)、condition R=0.989
     (91/92)。
   - 文本例子：法律引用类（under/pursuant to/within the meaning）与排他（only）
     被我们计入 constraint，Sun 只算数量/时间/比较类限制。
   - 错误原因：不是“同一定义标得更细”，而是 constraint 定义本身不同。
   - 方法边界：Sun Table-4 是 “initial sets”，13 个是 Sun 定义下界；
     P 侧需双边收敛（Sun-marker 版规则）另行验证。
   - 可能优化方向：实现 Sun-marker 版规则做双边收敛；或与审稿人说明定义差异。
   - 为何需要更多实验/讨论：这是低分主因之一，必须透明披露，且需要一个
     dual-side convergence 实验（未实施）。

5. **原始 Sun 资产缺失与已披露适配限制**。
   - 定量证据：无 Sun 原代码/权重/完整私有词典/原始 150 phrase Gold；Tsurgeon
     为诚实非实现（fail-closed 守卫）；CoreNLP 版本 4.5.10 是本地锁定（Sun 未
     公布版本）。
   - 错误原因：资产不可得；方法级独立复现是唯一允许口径。
   - 方法边界：只能称 `method-level independent reconstruction`，禁止 exact/
     original；不因缺资产阻断。
   - 如何披露：`B0_R2_METHOD_CROSSWALK.md` 11 元素逐项记录实现/测试/披露。
   - 为何不需要继续：这属于已披露的复现边界，不是可“修复”的缺陷。

### 8.2 Direct-LLM（直接 LLM）的局限性

1. **constraint recall 较弱（最弱字段）**。
   - 定量证据：基线 R=0.288（99 个 constraint 内容进 action span、91 个完全
     未抽）；v6 修至 0.417 后 formal 粗 constraint F1 0.7427（细 0.5482）；
     R3 失败类型：wrong_field 169（constraint 100）+ not_extracted 154
     （constraint 69）。
   - 文本例子：`estg_000003 "a shorter period"`、`estg_000027 "to an annual
     amount"` 落在 action 里而非 constraint。
   - 错误原因：constraint 语义（法律引用/时间/数量/within the meaning/pursuant
     to/subject to）需要显式定义；v6 已定义但完成度有限。
   - 方法边界：高精度保守型——宁可漏抽不误抽；constraint 在 Gold 中占比高
     （302/1055），召回损失显著。
   - 可能优化方向：更多 constraint few-shot、两遍 verify-pass、条款级子类进一步
     细分。
   - 为何仍需实验：任何更激进召回都会牺牲 precision，必须在授权预算内做
     AB-2（few-shot）与 AB-1（字段定义去除对照）的真实消融。

2. **constraint 内容进入 action 或完全漏抽**。
   - 定量证据：R1 基线 124 个“已抽到但落错字段”（99 action + 16 condition + …）；
     R3 constraint wrong_field 100 / not_extracted 69。
   - 文本例子：`"It may cover a shorter period if …"` 中 `"a shorter period"`
     被并入 action。
   - 错误原因：prompt 早期未定义 constraint 与 action 的边界。
   - 方法边界：该问题在 v6 已显著缓解（constraint R 0.288→0.417），但仍存在。
   - 可能优化方向：显式 “禁止并入 action/condition” 规则（已加入 v6 规则 25–27）
     进一步强化；属 prompt 层，需真实 pilot 验证。
   - 为何仍需实验：prompt 修改必须经授权 pilot + delta 记录，不能直接改正式数据。

3. **泛指 actor 误抽**。
   - 定量证据：历史 run actor P=0.594（69 pred vs 48 gold，23 个无 Gold 交叠的
     actor）；formal 粗 actor F1 0.7579（低于 Rules-Only 0.8203）。
   - 文本例子：表述 `"the body shall ensure…"` 中抽取无 Gold 交叠的泛指主语作为
     actor。
   - 错误原因：LLM 把非 actor 主语也列为 actor；多词/泛指实体边界判断不稳。
   - 方法边界：actor 字段是 Direct-LLM 相对弱项（P 侧）；R 侧召回尚可
     （coarse 0.8780）。
   - 可能优化方向：actor 定义更严格（只取最小名词短语、禁止泛指主语）；few-shot
     增加反例。
   - 为何仍需实验：提 actor precision 可能伤 recall，需真实消融（AB-2/AB-4 方向）。

4. **高精度、较保守、召回偏低（整体模式）**。
   - 定量证据：细 Gold F1 0.7756（P 0.8793 / R 0.6938）vs Rules-Only 0.7186
     （P 0.6845 / R 0.7564）——Direct-LLM 精度更高、召回更低；“宁可漏抽不误抽”
     在低资源字段（exception/constraint）牺牲召回。
   - 错误原因：prompt 的 “不确定就省略/入 unsupported” 保守指令 + 低资源字段
     few-shot 不足。
   - 方法边界：这是方法固有 trade-off，不是单一缺陷。
   - 可能优化方向：v6 已把省略改“列出候选 + 不确定入 unsupported”；进一步可通过
     few-shot/验证轮提升召回。
   - 为何需要更多数据：精度—召回平衡的最终判断必须等复杂语料 API arms 与消融。

5. **对真实 API、预算合同、transport 配方和 prompt hash 的依赖**。
   - 定量证据：模型钉死 deepseek-v4-pro；transport 配方（thinking-disabled、无
     json_object、temp0/top_p1/max_tokens4096）是端点实证适配；提示 hash
     3aa64877 三方锁定；每批需用户授权 + `--max-calls` 硬上限；官方 billing
     tokens/cost 只能从真实响应 usage 获得（preflight 已锁定 63 个 payload、
     retry=0、输出 cap 258,048 total、建议输入 cap 63,000,000 tokens、
     USD cap 27.63——尚未运行）。
   - 错误原因：LLM 可复现性来自外部端点与治理合同，不是本地可完全控制。
   - 方法边界：任何新模型/端点/采样变更都会破坏锁定，必须重新走授权链条。
   - 可能优化方向：AB-9 的 5 次独立重跑 + self-consistency/field-span agreement
     报告（对齐 Barrientos 论文设计）。
   - 为何仍需授权：所有真实 LLM 调用都需用户明确授权，当前零调用、零成本。

### 8.3 Rules+LLM-Repair 的负结果对照（不写为贡献）

选择性 LLM 修复在当前触发器设计下产生净负收益（§4.3）：主口径 F1 0.7621 vs
Rules-Only 0.7986（−0.0365）、actor P 0.7077→0.2754。结论引用
`MASTER_PIPELINE.md` §8.8.1 三项困难，并只能作为对照臂解释“证据约束的必要性”。

[[TODO-RESULT:S2.12/S3.10：结合复杂语料与 Stage 3 结果讨论适用边界和失败案例]]

## 9. 结论

[[TODO-RESULT:P8：所有正式实验和主张复核完成后撰写]]
