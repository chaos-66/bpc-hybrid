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

已落地的正式/DEV 结果（均为描述性）：Stage 1 固定 GDPR-7 复现（P2 语义
micro-F1 0.8185 / accuracy 0.6928 / triple 0.4222，structure 1.0 仅共享解析，
§7.1）；Stage 2 正式三方法比较（无整体胜者；Direct-LLM 对 action/condition/
constraint/modality label 更优，Rules-Only 对 actor/exception 更优，
Rules+LLM-Repair 为净负对照，§7.2）；Stage 3 在人工 33 条 panel 与新增 30 条
合成受控错误 panel 上的四方法违规检测（missing_action 最易、incorrect_actor
依赖参与者语义、out_of_order 最难，§7.4）。

[[TODO-RESULT:S2.12：回填复杂度分层结果（Direct/Fallback 为 pending
authorized extension，不阻塞本文主体）]]
[[TODO-RESULT:S3.7/S3.10：回填 Oracle 与端到端结果]]
在上述事项完成前，本摘要对 Oracle/端到端不写性能提升、最佳方法或最终结论。

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
- RQ3a（2026-08-22 新增）：在人工裁决的 33 条 violation panel 之外，现有非 LLM
  Stage 3 方法（Winter、Sun、BM25、TF-IDF）在 30 条**合成受控错误**（三类各 10
  条）上分别表现如何？哪种错误类型最易/最难检测？（§7.4.2–7.4.6）
- RQ3b：Stage 1 的结构/语义标签质量如何传播到 Stage 3 的违规类型判定？（§7.4.6）
- RQ4：Stage 2 或 Stage 3 的局部改进能否转化为端到端提升？

### 1.2 预期贡献（待验证）

本文计划交付：三阶段独立重建及其可复现边界；统一 canonical contract 下的 Stage 2
多 baseline 比较（正式结果见 §7.2）；复杂法律语料上的复杂度分层与错误分析；Stage 1
描述性复现（正式结果见 §7.1）与 Stage 3 违规检测（人工 33 条 panel + 30 条合成
受控错误 panel，见 §7.4）；Stage 3 Oracle 与 end-to-end 分离评价；以及解释
Stage 2、Stage 3 和二者交互贡献的受控消融。方法层面，本文把 Direct-LLM 的实现
拆分为 8 个可独立叙述与消融的模块，把 Rules-Only 拆分为 8 个模块，并逐模块与
Barrientos et al. (2026) 的直接借鉴来源做对照（见 §4、§6.6）。

**已落地（2026-08-22 论文优先主线）**：Stage 1 reproduction 完成（§7.1）；Stage 2
正式三方法比较完成（§7.2）；Stage 3 人工 panel + 合成受控错误 panel 完成（§7.4）；
S2.12 复杂语料 Direct/Fallback 为 pending authorized extension，不是论文主体阻塞
（§7.3 保留零 API arm）。

[[TODO-STATUS:S2.13/S3.7/S3.11：Stage 2/3 冻结与 Oracle/端到端完成后将“计划”改为
已完成贡献]]

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

Stage 1 把 BPMN 解析为 canonical Process Record：process/lane/pool 身份、活动
（activity/event/gateway）集合、sequenceFlow 与控制流（direct edges、reachable
pairs、activity order relations、start/end、分支/并行网关、环）。S1.7 已冻结
（2026-08-13）：固定 GDPR-7 上 7 个流程、45 个 activities、135 个人工裁决标签
字段；正式评价见 §7.1。方法语义（P0/P1/P2）见 §4.1 与 Stage 1 描述性复现
（structure micro-F1=1.0 来自共享解析组件，不构成泛化证据）。

### 3.2 Stage 2：Rule Record

Stage 2 输出统一包含 sample/clause ID、source text、modality（4 类，含 evidence
span 与 label 分离）、actor、action、condition、constraint、exception、
actor-action map、order relations 及 provenance。

### 3.3 Stage 3：Violation Report

Stage 3 输出 matching（rule→process 候选相关性）与 violation（三类）：
`missing_action`（法规义务在流程中缺失）、`incorrect_actor`（义务动作由错误
参与者执行）、`out_of_order`（顺序违反法规规定的先后）。Gold = 25 条 matching
decision Gold + 33 条 violation decision Gold（人工裁决，2026-08-08 冻结）；
验证方法包括 Winter wrapper、Sun Def 4–7 重建、BM25、TF-IDF/SVD（§7.4），
以及 2026-08-22 新增的 30 条合成受控错误 panel（§4.5/§6.4）。

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
- 哪些仍是假设、必须等待消融：**2026-08-22 Barrientos 离线消融套件已把其中
  AB-2/AB-3/AB-5/AB-8 的前置证据做实（见 §6.6 与 `paper/ABLATION_MATRIX.md`）**；
  仍需真实 LLM 臂：AB-2 few-shot/Barrientos-style prompt、AB-4 dual-view
  adapter、AB-9 五次稳定性重跑、AB-10 style-equivalent——这些必须等授权数据，
  不得现在写成“已完成”。

### 4.5 实验结果对 Barrientos 模块对照的更新（2026-08-22，零 API）

§4.4 的**模块级对照现在有离线实验证据**（套件 v1，见 §6.6）：

1. **校验/确定性后处理（对应 Barrientos 的 strict-JSON）**：实验 A 显示 span
   canonicalizer 在 150 条锁定响应上重锚 966 个 span、改变/恢复 149/150 个样本
   的坐标、并带来 action 字段 F1 +0.0095（overall +0.0024）。**这回答“校验链是否
   是本文真实贡献模块”：是**——Barrientos 论文只报告 strict-JSON 合法性，不逐
   字段 re-anchor；本文的 unique exact-text re-anchor 是可测量的额外层次。
2. **受控词汇（对应 Barrientos 44 模式）**：实验 B 的 no_lexicon_extensions 显示
   去掉词典扩展（public tier 之外的本地 frozen-gap 扩展）overall F1 −0.0066，
   主要由 actor 词典扩展驱动。两边的受控词汇服务于不同表示层（six-field vs
   change-impact），不互相替代（C4）。
3. **schema 类别（4 类 vs 3 类）**：实验 C 显示 4 类覆盖比 3 类多
   definition=39 条（231 clauses 的 16.88%）；definition 是本文六要素任务中
   可度量的类别，Barrientos 的 3 类 enum 会排除它——这是 schema 覆盖差异，
   不是方法优劣。
4. **各模块去掉后的实际影响（实验 B）**：lexicon 扩展 −0.0066、modality
   classifier 在 label 口径下降（span 口径不变）、multi-match guard 首候选消费
   反而 +0.0053（副作用已披露）、actor-action 归属与 DE-EN 验证只改 label/map/
   route 不改 span 覆盖。整体结论：**本文六要素抽取的 span 覆盖主要由 lexicon +
   tregex + 校验链贡献；classifier 与 alignment 验证主要影响 modality label 质量**
   （full clause-label accuracy 0.7316；definition 类最弱 0.487）。

### 4.5 Stage 3 受控错误注入方法（synthetic_controlled_error_extension）

为把 Stage 3 从 33 条人工裁决 panel（人工 Gold）扩展到可量化错误类型的
受控实验，本文在上游冻结 GDPR-7 上构造独立、明确标记为
`synthetic_controlled_error_extension` 的合成错误注入 panel（30 条 = 三类各
10；**不是人工 Gold，不并入 33 条正式 Gold，不得冒充 Oracle**）。生成器
`scripts/build_s3_error_injection_v1.py` 实现三类最小变异，目标锁定自原始
Process Record（先锁定后运行，无任何方法结果参与选择）：

**missing_action（10 条）**：删除一个与法规义务对应的任务并在 sequence-flow
层面重接前后节点。要求：原始 BPMN 不修改；变体可解析；只产生这一个目标错误；
记录被删 activity ID、label、前后 flow；不同时制造 actor/order 错误。

**incorrect_actor（10 条）**：把目标任务的 lane/performer 映射替换为同一数据集
participant vocabulary 中的合法 actor（如 Data subject、National Authority），
通过加入命名 actor lane 并移动该任务的 flowNodeRef 实现。要求：action 文本与
控制流不变；wrong actor 来自合法词汇表；记录正确 actor、注入 actor 与目标
activity；不同时改变 action 或顺序。

**out_of_order（10 条）**：对具有明确先后义务的任务对（A before B）重接
sequence flow 使顺序逆转（f_in→B、路径首流→B、末流→A、B 的出流→A），保持
activity 集合、actor、label 完全不变，只改变目标顺序；记录原顺序、变更后
顺序与受影响 flows。

每个变体在发布前通过机器校验：XML parse、BPMN 结构校验（冻结 parser）、原始
BPMN byte-unchanged、mutation diff、exactly-one-targeted-error、非目标字段
（其余 activity/lane/order/label）不变、deterministic replay（生成器重复运行
byte-identical）。规则绑定（variant → process → rule_id）与输入 aggregate hash、
输出 aggregate hash 一并锁定在面板 manifest
`data/development/stage3_synth/synthetic_controlled_error_extension_v1.json`。
运行器 `scripts/run_s3_synthetic_panel_v1.py` 以与人工 panel 完全相同的
`evaluate_stage3_common.py` 口径对四种非 LLM 方法评分；方法无法提供的信号
明确写 `not applicable`/unobservable，不补 0 冒充支持。

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

最低覆盖：词法/检索下限、Winter、完整 Sun、一个现代 embedding/graph baseline
（TF-IDF/SVD）；LLM/Hybrid 只在 Oracle 非 LLM 比较稳定后加入。实测（2026-08-22）：
Winter wrapper（`winter_stage3_development_v1` 配方）、Sun Stage 3 重建
（`sun_stage3_development_v1`，Def 4–7）、BM25（`bm25_stage3_development_v3`）、
TF-IDF/SVD（`tfidf_svd_stage3_development_v1`）四者共享同一 inference pack、
同一 `evaluate_stage3_common.py` 评估器；在 33 条人工 panel 与 30 条合成受控错误
panel 上分别报告（§7.4）。

### 6.3 Stage 1 实验设置（描述性复现）

固定 GDPR-7（7 流程 / 45 activities / 135 语义字段人工裁决标签），构造
P0（结构基线）/ P1（简单规则）/ P2（模型上下文+依赖+style recognition）三方法，
pre-evaluation lock、无 post-evaluation tuning；metrics = 语义 micro-P/R/F1、
exact value accuracy、triple exact accuracy；仅作描述性报告，禁止 held-out
泛化声明。正式结果见 §7.1。

### 6.4 Stage 3 合成受控错误实验设置

- 面板：`synthetic_controlled_error_extension_v1`（30 变体 = MA 10 / IA 10 /
  OO 10），生成器/校验/规则绑定/aggregate hash 全部锁定（§4.5）；
- 运行：同一 evaluator、同一四个方法配方、同一阈值（development 冻结值，
  非盲预注册）；
- 报告：overall accuracy、macro-F1、per-error P/R/F1、exact match、false
  positive/negative、unobservable 数量、每类检测率、runtime、失败案例
  （详见 `s39_synthetic_panel_<method>_v1/` 与 compare capsule）；
- 纪律：样本选择不依据 Winter/Sun/BM25/TF-IDF 预测调整；合成 panel 结果
  以 DEV 标注，不并入人工 Gold。

### 6.5 指标与统计控制

Stage 2 分别报告模态分类和六字段/完整 Rule Record 指标；Stage 3 分别报告 matching
AP/MAP/Recall@k 和违规分类 P/R/F1。所有方法共享输入、Gold、schema、normalization
和 evaluator，复杂度分层在查看 test 结果前冻结。与 Barrientos 的数字比较必须
分表并标证据等级（C1–C4）。

### 6.6 受控消融 AB-1–AB-10 与 Barrientos 消融套件（现状）

模块替换/去除矩阵的完整结构化结论见 `paper/ABLATION_MATRIX.md`。原则：
(1) 每项消融输出“我的完整模块 / 换成 Barrientos 模块 / 去掉模块 / 我的优势 /
Barrientos 优势 / 综合结论 / 可比较性限制”的结构化结论；(2) 没有正式数据时标记
“待运行”或“仅已有历史证据”，不得把“已经设计矩阵”写成“已经完成实验”；
(3) 涉及真实 LLM 的 AB-2/AB-4/AB-9 必须逐批用户授权。

**Barrientos 离线消融套件 v1（2026-08-22，零 API）已运行**（脚本
`scripts/run_barrientos_ablation_suite_v1.py`、
`scripts/run_b0_module_removal_ablation_v1.py`；结果
`outputs/development/barrientos_ablation_suite_v1/`、
`outputs/development/b0_module_removal_ablation_v1/`、
`outputs/reports/barrientos_ablation_comparison_v1.json`）：

- **实验 A（Direct-LLM 校验链，锁定 D1-R3 响应）**：Full 0.7756 / Schema-only
  0.7733 / Raw-approx 0.7733（fine Gold literal-overlap v2）；canonicalizer 重锚
  966 spans、改变/恢复 149/150 样本、dropped spans 42 / edges 18；Full vs
  Schema-only Δoverall F1 +0.0024、Δaction F1 +0.0095。结论：**校验+确定性后处理
  是真实贡献模块**（坐标恢复证据充分），但 span-overlap 主口径总体增量小。
- **实验 B（Rules-Only 模块去除，同一 150/同 Gold/同 evaluator）**：full 0.7186
  （复刻锁定 v10a）；no_lexicon_extensions −0.0066；no_multi_match_guard
  +0.0053（首候选消费副作用，如实披露）；其余 span 口径 0.0（只改 label/map/
  route 不改 span 覆盖）；modality clause-label accuracy full 0.7316，
  no_modality_classifier 下降（marker-only），definition 类 0.487 为最弱。
- **实验 C（4→3 modality 投影）**：四类 39/97/62/33；三类共享 97/62/33；
  definition 覆盖率损失 16.88%；definition 不并入其它类；仅 schema 覆盖比较，
  非 Barrientos 方法性能比较。
- **实验 D/E（prompt/few-shot 与同数据比较）**：full arm 复用锁定 formal 结果；
  no_fewshot / barrientos_style / minimal_prompt 三臂 prompt 已生成
  （`prompts/sun_compat/ablation_v1/`）并记录精确运行命令；E 同数据输入合同
  （38 条非空 Barrientos requirements，`configs/ablations/e_same_data_input_contract_v1.json`）
  与共享/分表指标协议已锁定；**未执行**（零 API 批次，需授权后运行）。

已锁定零 API 项：AB-1（v5→v6 历史证据：constraint R 0.288→0.417）、AB-3（4 类
→3 类投影，2026-08-22 完成）、AB-5（validator/canonicalizer 离线作用，2026-08-22
实验 A 量化）、AB-6（150/150 有效、0 事故历史证据）、AB-7（细/粗/Sun-marker 三
口径已成表）、AB-8（Rules-Only 逐模块去除，2026-08-22 实验 B 量化）、AB-2/AB-4/
AB-9（prepared / 待授权）。

## 7. 结果

### 7.1 Stage 1 正式复现结果（FORMAL，2026-08-13 冻结；描述性，非 held-out）

来源：`outputs/reports/stage1_formal_evaluation_v2.json`（status=
claim_corrected_numbers_locked；numeric body
`data/results/stage1_formal_v1/stage1_formal_evaluation_v1.json`，SHA
a072db39…；claim：post-Gold、target-aware Sun/Leopold-style method-level
reconstruction with Gold-isolated inference、pre-evaluation lock、no
post-evaluation tuning）。固定 GDPR-7：7 个流程、45 个 activities、135 个
semantic-field 人工裁决标签。

**表 1：Stage 1 三方法正式结果（固定 GDPR-7，描述性）**

| 方法 | 语义 micro F1 | Accuracy | Triple 准确率 |
|---|---:|---:|---:|
| P0（structural baseline） | 0.0000 | 0.0000 | 0.0000 |
| P1（简单规则） | 0.5956 | 0.4241 | 0.0000 |
| P2（模型上下文+依赖+style recognition） | 0.8185 | 0.6928 | 0.4222 |
| structure micro F1（共享解析组件） | 1.0000 | — | — |

- **P0 为什么不能恢复语义**：P0 只做结构转换（BPMN → Process Record 的活动/事件/
  网关/流骨架），不附加任何标签语义；135 个语义字段全部未填充（precision/recall/F1
  全 0）。它验证的是解析管线本身，而不是语义抽取。
- **P1 为什么有明显提升但组合仍然弱**：简单规则利用公开 marker/依存模板可恢复
  actor/action/condition 的**词面**语义（语义 micro-F1 0.5956、Accuracy 0.4241），
  但三元组（actor–action–object）需要跨字段一致对齐；P1 的 triple exact=0，
  说明字段间组合（谁对谁做什么）没有被规则层保证。
- **P2 为什么有效**：P2 引入模型上下文（BERT 表示）、依赖结构和 style recognition
  （label-style 信号），把词面规则升级为上下文感知的字段分配，语义 micro-F1
  0.5956→0.8185、Accuracy 0.4241→0.6928、triple 0→0.4222。
- **structure micro-F1=1.0 的读法**：来自共享解析组件（全部方法共用），只证明
  BPMN→记录结构的转换无错，**不能作为外部泛化证据**（见 §7.4.6 误差传播）。
- **边界**：这是 fixed GDPR-7 上的描述性复现（formal descriptive component
  evaluation）；held-out generalization claim 被明确禁止（eval v2 claim:
  held_out_generalization_claim_allowed=false、target_labels_seen_during_
  development=true、developer_blind=false）。不再为 Stage 1 增加新方法或新门禁。

[[TODO-RESULT:S2.10：Stage 2 六字段正式 manifest 回填（三方法比较见 §7.2）]]

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

### 7.4 Stage 3 违规检测：人工裁决 panel（33 条，已冻结）与合成受控错误扩展（30+40 条，DEV）

#### 7.4.1 两个独立评价面板

**人工裁决 panel（正式，2026-08-08 冻结）**：`data/gold/stage3/stage3_violation_gold_v1.json`
（SHA `039ae8b2…`，33 条）= 人工裁决的 violation type/evidence Gold：
missing_action 11 / incorrect_actor 11 / out_of_order 11（11 个 process-rule 对 × 3
类）。这是**人工 Gold**，用于论文正式 Stage 3 表格。

**合成受控错误 panel（DEV，2026-08-22）**：`data/development/stage3_synth/
synthetic_controlled_error_extension_v1.json`（`synthetic_controlled_error_extension`
面板，30 条 = missing_action 10 / incorrect_actor 10 / out_of_order 10）。生成器
`scripts/build_s3_error_injection_v1.py` 在冻结 GDPR-7 上做**最小受控变异**：
missing_action = 删除一个与法规义务对应的任务并重接 sequence flow（保留被删
activity ID/label/前后 flow；仅一个目标错误）；incorrect_actor = 把目标任务移到
同一数据集 participant vocabulary（如 Data subject/National Authority）中新的
actor lane（action 文本与控制流不变）；out_of_order = 对具有明确先后义务的任务
交换 sequence flow 末端使其顺序逆转（activity 集合、actor、label 均不变）。每个
变体通过 XML parse、结构校验、源 BPMN byte-unchanged、mutation diff、exactly-one-
targeted-error、非目标字段不变与 deterministic replay 检查；规则绑定自冻结
inference pack；生成器重复运行 byte-identical。**该 panel 不是人工 Gold，不得并入
33 条正式 Gold，也不得冒充 Oracle**；全部结果以 DEV 标注。

**新增四类的选择动机（S3.9-EXT，DEV，2026-08-31）**：原三类只回答“必需
动作是否存在、执行者是否正确、顺序是否正确”，主要消费 action、actor 与 order
信息；它们无法判断一个流程是否执行了**被禁止的动作**，也无法判断正确动作是否
满足其**适用条件、限制约束和例外处理**。因此，扩展不是任意增加标签，而是按照
“未被 Stage 3 消费的 Rule Record 字段”选择四个最小、互不替代且可由 BPMN 表面
证据验证的违规族：

| 新违规类型 | 选择理由 | 使用的 Rule Record/BPMN 证据 |
|---|---|---|
| prohibited_action_present（出现禁止动作） | 补足 missing_action 只覆盖“应做而未做”的遗漏错误；即使必需动作、actor 和顺序全部正确，流程仍可能“做了不该做的事” | prohibition modality + action；activity/event label |
| required_condition_not_enforced（必需条件未落实） | 法律义务常有适用条件；动作本身存在并不等于只有在合法条件下才执行 | condition + action；gateway、conditionExpression、sequence-flow label |
| constraint_violated（约束被违反） | 动作、actor、顺序均正确时，仍可能违反期限、数量、用途或使用限制 | constraint + action；timer、data object、annotation 等 |
| exception_not_handled（例外未处理） | 正常路径可以合规，但流程可能缺少法规要求的例外分支或处理器 | exception + action；boundary/error event、alternate branch、handler activity |

四类的共同选择原则是：（1）补齐六要素的下游字段覆盖；（2）在原三类全部通过时
仍可能独立发生，语义上不重复；（3）可构造 exactly-one-error 的受控 BPMN 变异；
（4）对应明确的 BPMN 可观察表面，缺少表面时诚实记为 unobservable。该集合是
**最小字段覆盖扩展，不是穷尽性的法律违规分类体系**；40 条结果保持 DEV_ONLY，
不改变冻结的三类人工 Gold，也不把正式 Oracle 改称七类 benchmark。

#### 7.4.2 表 A：原 33 条人工裁决 panel（已锁定开发结果）

| 方法 | Missing-action F1 | Incorrect-actor F1 | Out-of-order F1 | Macro-F1 | Exact type acc | Unobservable |
|---|---:|---:|---:|---:|---:|---:|
| Winter wrapper | 0.9524 | 0.0000 | 0.1667 | 0.3730 | 0.3333 | 0 |
| Sun Stage 3 重建 | 1.0000 | 0.1667 | 0.0000 | 0.3889 | 0.3636 | 10 |
| BM25 | 1.0000 | 0.0000 | 0.0000 | 0.3333 | 0.3333 | 11 |
| TF-IDF/SVD | 1.0000 | 0.6250 | 0.0000 | 0.5417 | 0.4848 | 6 |

来源：`outputs/development/s34_winter_stage3_development_v3_clean/`、
`s35_sun_stage3_development_v2/`、`s36_bm25_stage3_development_v3/`、
`s36_tfidf_svd_stage3_development_v2/` 的 evaluation.json；同一
`evaluate_stage3_common.py` 口径。

#### 7.4.3 表 B：新增 30 条合成受控错误 panel（DEV，同一 evaluator）

| 方法 | Missing-action F1 | Incorrect-actor F1 | Out-of-order F1 | Macro-F1 | Exact | Unobservable |
|---|---:|---:|---:|---:|---:|---:|
| Winter wrapper | 1.0000 | 0.0000 | 0.0000 | 0.3333 | 0.3333 | 0 |
| Sun Stage 3 重建 | 0.3333 | 0.3333 | 0.3333 | 0.3333 | 0.2000 | 8 |
| BM25 | 1.0000 | 0.0000 | 0.0000 | 0.3333 | 0.3333 | 10 |
| TF-IDF/SVD | 1.0000 | 0.5714 | 0.3333 | 0.6349 | 0.5333 | 6 |

来源：`outputs/development/s39_synthetic_panel_<method>_v1/`；逐条
per-error P/R/F1、detected/missed/wrong-type、检测率与 runtime 见各 run
evaluation.json（Winter 3.9s、Sun 15.0s、BM25 6.0s、TF-IDF/SVD 12.7s）；
失败案例（FN/FP 明细）见 `predictions.jsonl` 与对比胶囊
`s39_synthetic_panel_compare_v1/comparison.json`。

#### 7.4.4 S3.9-EXT 40 对受控扩展结果（DEV，variant-only 与 paired 分表）

**选择动机见 7.4.1**。四类结果按两种口径分开报告（均 DEV_ONLY，来自持久化
预测的离线统计，零重新运行）：

- **variant-only detection evaluation**（40 个 variant）：只评价变异流程是否
  被检出且类型正确；unobservable 保持 predicted=None 并计入 FN（原 v2 表）。
- **paired control-plus-variant evaluation**（80 个对象 = 40 个 control
  Gold=none + 40 个 variant）：额外要求同一对中 control 不得误报为违规，
  回答“系统能否同时做到不误报正确流程、并检出违规流程”。control 预测
  严格由持久化的 `control_scores` 按原四类规则、原 `gamma_ext` 与固定
  EXTENDED_TYPES 优先级离线重建，未修改阈值或决策顺序；失败、none 与
  unobservable 全部保留在分母中。

| 方法 | variant-only：prohibited/condition/constraint/exception F1 | Macro-F1 | Exact | Unobservable |
|---|---:|---:|---:|---:|
| Winter-style extension | 1.000 / 0.333 / 0.824 / 0.462 | 0.655 | 0.550 | 17 |
| Sun-style extension | 1.000 / 0.000 / 0.333 / 0.000 | 0.333 | 0.300 | 28 |
| BM25 extension | 0.571 / 0.000 / 0.333 / 0.000 | 0.226 | 0.150 | 28 |
| TF-IDF/SVD extension | 1.000 / 0.000 / 0.333 / 0.182 | 0.379 | 0.325 | 27 |

| 方法 | paired：5-class acc (80) | variant exact (40) | control FP rate (40) | paired acc (40) | 4-type Macro-F1 | 5-class Macro-F1 |
|---|---:|---:|---:|---:|---:|---:|
| Winter-style extension | 0.425 | 0.550 | 0.500 | 0.225 | 0.514 | 0.504 |
| Sun-style extension | 0.263 | 0.300 | 0.125 | 0.175 | 0.283 | 0.300 |
| BM25 extension | 0.250 | 0.150 | 0.000 | 0.100 | 0.226 | 0.285 |
| TF-IDF/SVD extension | 0.338 | 0.325 | 0.275 | 0.300 | 0.330 | 0.368 |

paired 口径下各方法 control 误报率显著（Winter 0.5、TF-IDF 0.275、
Sun 0.125、BM25 0），paired accuracy 因此明显低于 variant-only exact：
加入 control 后，Winter 的 prohibited 精度从 1.000 降至 0.667、
condition 精度从 1.000 降至 0.182（control 侧误报进入 FP）。

**结论（收紧措辞，仅限受控数据）**：

- `prohibited_action_present`：**支持新增检测类型的可行性**——除 BM25
  长度标度限制外，各后端对插入禁止动作任务的检出精度/召回都很高。
- `constraint_violated`：**部分支持**——annotation/timer/data-object 变异在
  动作可映射且存在约束表面时可检出，但仍受动作映射与冻结 BPMN 表面限制。
- `required_condition_not_enforced`：当前结果**主要暴露 condition surface
  与 action mapping 的可观察性瓶颈**（命名 gateway 藏在 subProcess 内、
  动作映射低于 gamma），冻结 GDPR-7 上几乎没有正面证据。
- `exception_not_handled`：当前结果**主要暴露 boundary event、异常分支与
  parser 可观察性不足**，多数例外检查不可观察或不可映射。

因此不写“全部四类都证明六要素下游价值”；准确表述为：**新增四类使四个此前
未使用的规则字段（prohibition modality、condition、constraint、exception）
获得明确的 Stage 3 消费接口，但当前受控数据只对部分类型提供了较强性能
证据，其余类型主要揭示可观察性和映射瓶颈**。40 条结果始终标为 DEV_ONLY，
不并入 33 条人工 Gold，也不把正式 Oracle 改称七类 benchmark。

#### 7.4.5 表 C：错误类型分析

| 错误类型 | 最容易的方法 | 最困难的方法 | 主要失败原因 | 对应方法模块 |
|---|---|---|---|---|
| missing_action | Winter / BM25 / TF-IDF（合成 panel R=1.0） | Sun（合成 panel R=0.2，8 条 action_mapping_below_gamma） | 规则 action 与删除任务的词面相似度低于 gamma；Sun Def-5 对映射阈值敏感 | Sun Def-5 similarity mapping；Winter cost_obligation |
| incorrect_actor | TF-IDF/SVD（人工 0.625 / 合成 0.5714） | Winter / BM25（恒 0） | 这三个方法不引入参与者的语义标签：Winter 只读 process participant，BM25 对 actor 候选池的检索不足以支撑 min-sim<θ 判定 | actor vocabulary / pool-lane 解析；Def-6 actor matching |
| out_of_order | 全部薄弱（人工 panel 最优 0.1667） | Sun/BM25/TF-IDF（合成 0.3333，人工 0） | 顺序违规依赖控制流可达关系；现有方法对 gateway 分支与可达性的粒度不足，多数顺序变异在可达关系上不可观测 | control-flow reachability；Def-7 顺序约束 |

#### 7.4.6 讨论

- **哪种错误最容易检测**：missing_action——凡规则含明确义务 action 且词面可映射，
  Winter/BM25/TF-IDF 在合成 panel 上 R=1.0（人工 panel 亦 0.95–1.0）。原因：删除任务
  直接改变 action 集合，检索/词面方法对这一信号最敏感。
- **哪种错误最难**：out_of_order——人工 panel 最优仅 0.1667（Winter），合成 panel
  最高 0.3333（TF-IDF/SVD）。**actor 与 order 错误都比 missing_action 难**。
- **actor 错误是否需要 Stage 1 更好的语义标签**：是。TF-IDF/SVD 的 actor 优势来自把
  business-object/actor 文本纳入同一 dense 空间并参与 min-sim 判定；Winter/BM25 因
  依赖有限的 pool/lane 名或独立候选池而恒 0。GDPR-7 中 lane 名为空、actor 只存在于
  participant，Stage 1 更完整的 actor 语义标签（而非仅结构解析）是 actor 类检测的
  前置条件。
- **order 错误是否依赖控制流可达关系**：是。Sun Def-7 与 Winter cost_so 都以可达
  关系为唯一顺序信号；合成 panel 的 OO 变异若落在 gateway 分支/并行结构上，可达
  关系不变即不可观测。需要 sequence-flow 级的 directly-follows 或执行语义信号。
- **missing action 为何不能只靠词面相似度**：合成 panel 中 Sun 对 8/10 条
  missing_action 变异给出 action_mapping_below_gamma（规则 action 与模型 action
  的相似度低于 gamma，Def-5 分母为 0 或映射失败）。**删除动作后词面相似度取决于
  剩余任务中是否存在同义表达**；只靠词面会把“同义保留”（规则义务以不同措辞仍
  存在）误判为缺失，或把删除漏判为未缺失。
- **Stage 1 错误如何传播到 Stage 3**：Stage 1 结构 micro-F1=1.0（共享解析组件）只
  保证 BPMN-Process Record 的结构转换无错，**不证明语义标签正确**。actor 类错误
  检测为 0 的 Winter/BM25 正说明：Stage 1 未提供参与者语义（lane 名为空、participant
  未绑定到活动），该语义缺失直接传递到 Stage 3 的 actor 判定；而组合三元组（P2
  triple exact 0.4222）与 stage 1 标签质量共同决定 Stage 3 的证据链。
- **各方法擅长什么**：Winter=义务/缺失动作（obligation cost）与可达顺序；Sun=
  约束驱动的匹配（MAP 0.8175）与缺失动作（Def-5 强于 actor/order）；BM25=词面
  极大化（missing action 强、语义 actor 弱）；TF-IDF/SVD=两个领域共享 dense 表示，
  对 actor 类错误最有效（人工 0.625、合成 0.5714），整体 macro 最优。
- **synthetic 与人工 Gold 是否一致**：一致点=missing_action 两类 panel 都是最易
  检测、顺序错误都最弱；合成 panel 复现了人工 panel 中 Winter/BM25 的 actor=0。
  差异点=Sun 在合成 panel 的 missing_action R 降至 0.2（人工 panel R=1.0）——
  因为合成变异删除的任务未必与绑定 rule 的 action 词面匹配（生成器按语法结构
  选择目标，而非按 rule 词面），人工 panel 的 11 条则由人工基于 rule 语义构建。
- **哪些结论只能作为受控实验结论**：合成 panel 的精确检测率、easiest/hardest
  排序、与人工 panel 的差异归因，均为**受控变异上的描述性结论**，不是真实
  process-model 犯罪的泛化结论；正式 Stage 3 claim 仍以人工 panel 为依据，Oracle
  与端到端仍需 S3.7/S3.10。

#### 7.4.7 Stage 3 Sun 式阈值敏感性（τ/γ/ϑ 离散网格；DEV，2026-09-04，零 API）

> 来源与复现：`outputs/reports/s35_sun_stage3_threshold_sensitivity_v1.{json,md}`
> 与图 A/图 B（`..._figA_gamma_missing_action_out_of_order.svg`、
> `..._figB_theta_incorrect_actor.svg`）；`scripts/build_sun_stage3_threshold_sensitivity_v1.py`
> （全量离线重算与 `--report-only` 确定性重放）；同一 33 条人工 Gold、同一
> Rule/Process Records、同一 Sun Definition 4–7 重建、同一 spaCy 相似度后端与
> 同一 common evaluator，未修改任何 Gold/样本/预测/公式，API calls=0、cost=0。

Sun et al. 将 γ 视为可调的语义等价门槛。其多数流程模型在 γ=0.8 时获得最高违规检测精度，但复杂度最高的模型在 γ=0.6 时表现更好；作者将其归因于复杂流程中文本相似度降低。本文首先直接迁移 γ=0.8，以保留方法级对照。结果表明，在本文七模型数据和 spaCy 相似度后端上，γ=0.8 使大量合法的 action mappings 无法通过门槛，导致 incorrect-actor 和 out-of-order 检查不可观察。按照 Sun 的离散阈值敏感性分析方式，γ=0.6 是测试值中表现最平衡的设置，Macro-F1 从 0.3889 提升至 0.8733。该结果说明阈值需要随数据复杂度和相似度后端重新校准，而不是说明 Sun 的公式无效。

**表格/图形与两种口径**：

- 表 A 的 Sun 行即 **Sun-transferred**（τ=0.8、γ=0.8、ϑ=0.8；Macro-F1 0.3889、
  exact 0.3636、unobservable 10），本小节不删除、不隐藏该低分基线；
- **Sun-style calibrated sensitivity** = tested values 中的 best observed setting
  （τ=0.8、γ=0.6、ϑ=0.8；Missing F1 1.0、Incorrect-actor F1 0.7778、
  Out-of-order F1 0.8421、Macro-F1 0.8733、exact 0.7879、unobservable 4）；
- τ∈{0.0,…,0.9} 只评价 matching 的每流程 AP/MAP（Def-4 分数随 τ 重算后重排），
  不把 matching MAP 当作 violation F1；γ∈{0.0,…,0.9}（ϑ 固定 0.8）与
  ϑ∈{0.5,…,0.9}（固定 γ=0.8，Sun 图 9 协议）均由 SunScorer 真实重算
  mappings/denominators/order endpoints/observability，不是对既有最终分数重切阈值；
- 图 A = 不同 γ 下 missing action 与 out-of-order 的每流程结果（Sun 图 8 口径；
  Sun 原图主要报告 Precision，图内另附 Recall/F1 补充面板）；图 B = 固定 γ=0.8 后
  不同 ϑ 下 incorrect actor 的每流程结果（Sun 图 9 口径）。

**边界与措辞（必须与正文一致）**：

- Sun 原论文与本文数据不同（模型集合、规则库、相似度后端与 panel 构造均不同）；
  “0.8 是其数据上多数模型表现较好的经验值”，不是“Sun 规定所有模型必须使用 0.8”；
- 本文是 Sun 方法级独立重建，不是原代码精确复现；γ=0.6 只是本文数据与当前
  相似度后端上的经验校准值，不得称数学全局最优阈值、Sun 原论文固定阈值、
  held-out 最优值或“与 Sun 原始四模型完全相同的数据结果”；
- 不把敏感性结果伪装成预注册正式结果：主阈值保持预注册 (τ,γ,ϑ)=(0.8,0.8,0.8)，
  本小节与全部敏感性产物标注 DEV_ONLY；
- 33 条人工 Gold 没有 Gold=none 合规样本，不能用它证明 specificity 或控制
  false-positive rate；33 条 panel 每个测试点预路由单一 gold 类型，跨类型 FP
  结构性不可能出现，Precision 面板仅按 Sun 口径保留，信息以 Recall/F1 为主。

[[TODO-RESULT:S3.7：Oracle Stage 3 与 end-to-end 分表]]

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

### 8.4 Threats to Validity

**内部效度**：
- Stage 1 为固定 GDPR-7 上的描述性复现：target labels 在开发期可见、
  developer_blind=false、无 held-out 分割（§7.1 claim 逐项披露）；structure
  micro-F1=1.0 仅来自共享解析组件，不可外推为语义能力。
- Stage 3 双手工 panel 指标使用 dev 阈值（0.5/fixed gamma/delta，非 blind
  预注册）；同一 evaluator 的 observability 政策（incorrect_actor 的
  unobservable 计为 FN）影响宏观口径，表 B 的 per-type F1 与 unobservable
  列须一起读。
- 合成受控错误 panel 的生成目标按**语法/结构**锁定（非按规则词面选择），因此
  “方法检测不到”可能部分反映目标与原 rule 的词面对齐程度，而不仅是错误本身
  的固有难度；此点已在 §7.4.6 如实讨论。

**外部效度**：
- 全部 Stage 3 违规结果基于 7 个 GDPR 流程（45 activities）与 GDPR 义务类型
  （通知、同意、访问、可携、撤回、更正、删除）；扩展到其他法规域与更复杂的
  流程拓扑（gateway 并发、循环）需要新面板。
- 合成错误是**最小、单一**变异；真实流程模型可能同时存在多重违规与跨阶段
  交互错误，本文的 exactly-one-error 设计不能代表其分布。

**构建效度**：
- violation type 的定义采用 Sun Def 5–7 / Winter cost_* 的映射口径；
  不同论文对 missing_action/incorrect_actor/out_of_order 的边界定义可能不同。
- 合成 panel 的 “expected violation” 是生成器契约的一部分，与人工 Gold 的
  decision 语义分离（不混用、不冒充）。

**结论效度**：
- 样本量小（33/30 条、7 流程），不做显著性推断；表 A/B 均为描述性数值。
- actor/order 检测率（尤其 Winter/BM25 的 0）不能解释为“真实流程无此类违规”，
  只能解释为“这些方法在该表示上没有对应信号”。

### 8.5 Stage 1 → Stage 3 误差传播小结（§7.4.6 的汇总）

- Stage 1 结构正确（micro-F1=1.0）保证 Stage 3 的流程图输入无转换错误，但
  不提供参与者语义；GDPR-7 的 lane 名为空，actor 只存在于 participant，
  Winter/BM25 的 actor=0 与该语义缺失直接对应。
- Stage 1 的组合三元组准确率（P2 0.4222）与标签质量决定了 Stage 3 的
  rule-action 映射：Sun 在合成 missing_action 上 8/10 为
  action_mapping_below_gamma，本质是 Stage 1/规则抽取的词面对齐不足向
  Stage 3 的传播。
- 结论：Stage 3 违规检测的瓶颈不只在于匹配/顺序算法，还在于 Stage 1 语义
  标签（actor、组合三元组）的质量；改进 Stage 3 需先补 Stage 1 的参与者
  语义与三元组一致性（见 §7.4.6 讨论）。

## 9. 结论

本文围绕 Sun et al. 的三阶段框架完成了可追溯的独立重建与扩展实验，并产出
正式或 DEV 标注的结果：(1) Stage 1 在固定 GDPR-7 上完成描述性复现（P2
语义 micro-F1 0.8185、accuracy 0.6928、triple 0.4222；structure 1.0 仅
共享解析；P0 0/P1 0.5956 提供下限与规则基准）；(2) Stage 2 正式三方法
比较显示无整体胜者——Direct-LLM 在 action/condition/constraint/modality
label 领先，Rules-Only 在 actor/exception 领先，Rules+LLM-Repair 因 actor
过度抽取成为净负对照（§7.2）；(3) Stage 3 在人工 33 条 panel 与新增 30 条
合成受控错误 panel 上量化了四类非 LLM 方法：missing_action 最易检测，
incorrect_actor 依赖 Stage 1 参与者语义（TF-IDF/SVD 相对最优），out_of_order
最难且依赖控制流可达信号（§7.4）；(4) 误差传播分析表明 Stage 3 的 actor/order
瓶颈部分来自 Stage 1 语义标签缺失。S2.12 复杂语料 Direct/Fallback 为
pending authorized extension，不阻塞本文主体方法描述；Stage 3 Oracle 与
端到端评价仍待 S3.7/S3.10。综合来看，本文的贡献是“分阶段、可追溯的方法级
重建 + 类型化违规检测的受控证据”，而不是对单一全局指标的胜者宣称。

[[TODO-RESULT:P8：S2.12 API arms、S3.7 Oracle 与端到端完成后复核并回填]]
