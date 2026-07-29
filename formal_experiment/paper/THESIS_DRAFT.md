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

法规通常以自然语言描述义务、禁止、许可、定义及其适用条件，业务流程模型则以活动、
事件、网关、参与者和控制流表达组织行为。设计时业务流程合规检查的目标，是在流程
投入执行前判断模型是否符合适用规则，从而把缺失活动、执行者错误或顺序冲突等风险
提前暴露。与运行时监控或事后日志检查相比，本文只研究流程模型尚处于设计阶段时的
合规评价。[[TODO-SOURCE:SUN2024:核对 Introduction 中设计时检查定义与动机的页码]]

这一任务至少包含三个相互依赖的表示问题。首先，流程图中的结构节点和短标签需要被
还原为可比较的行为语义；其次，法规句子需要同时完成句子级规范模态判断和短语级语义
要素抽取；最后，两侧的结构化表示需要被匹配，并据此定位具体违规。任何上游表示错误
都可能进入下游判断，因此只报告一个端到端总分，无法说明误差来自流程解析、法规解析，
还是规则—流程匹配。

Sun et al. 将完整方法组织为 process model disassembly、regulatory documents parsing
和 multiple violation detection 三个部分。本文为了进行组件级评价，将它们分别操作化
为 Stage 1 流程解析、Stage 2 法规解析和 Stage 3 匹配与违规检测，并用 Process Record、
Rule Record 和 Violation Report 作为阶段间的统一合同。这里的 Stage 1/2/3 是本文的
实验分解；正式引用仍以 Sun 最终发表版的方法结构为准。
[[TODO-SOURCE:SUN2024:核对 Section 4 与 Figure 1 的最终版页码]]

完整作者资产并未随本项目获得：当前工作区没有 Sun 最终 Stage 2 的完整源码、训练
权重、完整 marker lexicon 或原始 150 句 phrase Gold，且已有实现与最终发表方法之间
存在需要对齐的差异。因此，本文不声称复用作者原始实现或进行 exact reproduction，
而是以最终发表方法为控制来源，实施可审计的 paper-faithful independent reconstruction。
复现中能够核验的内容、必须独立实现的内容以及仍不可恢复的资产，将分别记录并进入
研究局限。

本文优先研究 Stage 2，因为它把法规文本转换为 Stage 3 所消费的 Rule Record，也是
传统规则、监督学习、直接 LLM 与混合方法能够在同一输出合同下比较的交汇点。实验将
设置代表性传统下限与监督学习 baseline、完整非 LLM 重建 B0、只在预注册失败或不确定
条件下调用 LLM 的 H1，以及直接生成 Rule Record 的 D1。所有方法必须共享 frozen IDs、
Gold、schema、normalization 和 evaluator；模态分类、六要素抽取、完整记录有效性、
失败率与成本分别报告。

LLM 在本研究中不是默认更优的答案，而是需要受控检验的候选方法。D1 能否稳定生成
符合合同的完整记录、H1 能否用有限调用修复 B0 的局部失败、两者的收益是否足以抵消
invalid output、重试和调用成本，均由预注册实验回答。类似地，复杂法律文本是否会
放大方法差异只是研究假设；复杂度字段、分层规则和外部语料资格必须在查看测试结果前
冻结。

为区分组件能力与误差传播，Stage 3 将先使用 Gold Process/Rule Records 进行 Oracle
比较，再让不同 Stage 2 预测进入同一冻结 Stage 3。最终通过 E00、E10、E01 和 E11
交叉消融分别估计 Stage 2 改进、Stage 3 改进及二者交互。本文接受改进方法不超过重建
baseline 的可能性；只要输入、Gold、评价器和失败记录保持一致，负结果同样构成对方法
适用边界的有效证据。

### 1.1 研究问题

- RQ0：在作者完整源码、权重和部分 Gold 不可得的条件下，能否以明确的复现边界、
  统一中间合同和可重放 manifest，完整且可追溯地独立重建 Sun 的三部分设计时合规
  检查框架？
- RQ1：在相同 frozen IDs、Gold、schema、normalization 和 evaluator 下，代表性传统
  方法、完整非 LLM 重建 B0、Direct LLM D1 和 selective Hybrid H1 在 Stage 2 的
  模态分类、六要素抽取、完整记录有效性、失败率与成本上如何比较？
- RQ2：在预注册的法律文本复杂度分层下，各 Stage 2 方法的性能、覆盖率和错误构成
  如何变化，哪些语言或结构因素与退化相关？
- RQ3：在 Gold Process/Rule Records 构成的 Oracle 条件下，词法/检索、Winter、Sun、
  现代非 LLM、LLM 与 Hybrid 方法在 Stage 3 的规则—流程匹配和违规类型分类上如何
  比较？
- RQ4：当 Stage 2 与 Stage 3 分别固定或替换时，局部改进能否转化为端到端变化，
  其贡献来自 Stage 2、Stage 3，还是二者交互？

### 1.2 预期贡献（待验证）

本文计划交付以下五项成果：

1. 对 Sun 完整方法的三阶段独立重建，明确区分原文可核验内容、项目独立实现和不可得
   资产，并为每个阶段保留可重放命令与 provenance；
2. 在统一 canonical contract 下比较代表性传统方法、B0、H1 和 D1，分开报告模态、
   六要素、完整记录、失败与成本，而不使用跨数据或跨阶段数字证明优劣；
3. 构建并冻结项目唯一的 EStG-150 `LLM-assisted, human-adjudicated Gold`，完整披露
   LLM 候选、人工决定与最终 benchmark 的关系；
4. 在结果前冻结的复杂法律语料和复杂度合同上开展退化曲线、覆盖率与错误类型分析；
5. 分离 Stage 3 Oracle 与 end-to-end 评价，并通过 E00/E10/E01/E11 消融解释 Stage 2、
   Stage 3 和二者交互的贡献，包括如实报告负结果和失败边界。

[[TODO-STATUS:S2.13/S1.7/S3.11：各阶段冻结后将“计划”改为已完成贡献]]
[[TODO-STATUS:S2.2：150/150 人工裁决后将第 3 项从计划改为已完成]]

## 2. 相关工作

过去十年中，研究者提出了多种业务流程合规性检查方法，并将其应用于流程查询、法律
合规检查和审计等场景。本文关注设计时业务流程合规检查，即在流程执行前判断流程模型
是否满足法规要求。

现有设计时合规检查方法通常按照基础技术分为逻辑方法、模式方法和混合方法。逻辑方法
使用流程合规逻辑、Compliance Request Language、事件演算和线性时序逻辑等形式语言
描述义务、禁止及活动顺序 [Governatori and Rotolo, 2010; Montali et al., 2014]。模式
方法在检查前将法规要求转换为图形化合规模式，例如 Elgammal 等使用基于 LTL 的模式
表示流程约束 [Elgammal et al., 2016]。混合方法则结合语义 Web、LegalRuleML 和专用
检查器；Governatori 等使用 LegalRuleML 手工建模法律规则，并由 Regorous 执行合规
检查 [Governatori et al., 2016]。这类方法具有明确的形式语义和较好的可解释性，但
通常需要领域专家预先完成规则形式化。

为减少人工建模，研究者开始使用 NLP 处理流程描述和法规文本。Sánchez-Ferreres 等从
自然语言流程描述中提取形式约束 [Sánchez-Ferreres et al., 2019]；NLP4BPM 支持文本
描述与 BPMN 模型之间的转换及一致性分析 [Delicado Alcántara et al., 2017]。另一些
方法从需求文档或规则导向文本中抽取动作、参与者和声明式流程约束。然而，流程描述
主要表达活动及其控制流，法规文本还包含规范模态、条件、约束和例外，因此流程文本
解析不能直接替代法规规则抽取。

在法规语义抽取方面，相关方法通常结合机器学习分类、marker 词典、规则模板和句法
分析。Sleimi 等使用成分分析、依存分析、Tregex 规则和 marker 抽取句子级及短语级
法律语义元数据 [Sleimi et al., 2021]。Michel 等将 EStG 句子分类为 definition、
obligation、permission 和 prohibition [Michel et al., 2022]。Sun 等进一步把法规
解析划分为句子级模态分类和短语级语义抽取，并使用 BERT-TextCNN 以及 CoreNLP、
Tregex/Tsurgeon 和 marker 规则生成包含 actor、action、condition、constraint 和
exception 的规则记录 [Sun et al., 2024]。这类方法处理过程较为确定且容易追踪，但
性能受到训练数据、词典覆盖、解析质量和规则迁移能力的限制。本文的非 LLM 方法 B0
属于这一技术路线。

Winter 等直接分析监管文档与 BPMN 模型，从法规中识别义务活动、执行顺序和组织实体，
再计算文本与流程元素之间的匹配，并检查活动缺失、顺序错误和执行者错误
[Winter et al., 2020]。Sun 在此基础上连接流程模型拆解、法规文档解析和多重违规检测。
本文将 Winter 作为直接文本—流程检查的代表性前驱，将 Sun 作为三阶段方法学主干；
由于 Sun 的完整源码、权重、marker 和原始短语 Gold 不可得，B0 仅称为依据论文完成的
独立重建，而非作者原始实现。

近年来，LLM 被用于把自然语言法规直接转换为预定义 Schema 下的结构化表示。
Barrientos 等将 LLM 与受控词表、JSON Schema、输出验证和归一化结合，用于法规变更
影响分析 [Barrientos et al., 2026]。LLM 能减少对固定词典和句法模板的依赖，但也可能
产生字段遗漏、无依据补全、格式错误和重复运行不一致。本文设置直接 LLM 方法 D1，
用于评价 LLM 在统一 Rule Record 输出任务中的表现。

规则方法与 LLM 具有互补性。选择性预测、级联系统和模型路由通常先使用成本较低或
确定性较强的方法，仅在结果不可靠时调用更复杂的模型 [Geifman and El-Yaniv, 2017;
Chen et al., 2023; Ong et al., 2024]。据此，本文设置选择性 LLM 回退方法 H1：先运行
完整 B0，只在预注册失败或不确定条件触发时进行字段级 LLM 修复。最终，B0、D1 和 H1
将在相同输入、Gold、输出 Schema 和评价协议下比较；相关工作的论文报告值只用于说明
方法背景，不直接作为本文方法优劣的证据。

## 3. 问题定义与总体框架

### 3.1 Stage 1：Process Record

Stage 1 将 BPMN 转换为可供后续匹配的 Process Record。目标记录至少包含 process ID，
activity、event、gateway、pool、lane、actor 与 sequence flow，活动标签中的 action 和
business object，以及直接顺序、可达、分支、并行和 order relation；同时保存 BPMN
文件 hash、解析器和版本。结构解析与标签语义解析将分开评价，使 XML 节点恢复错误
不会与 actor/action 解释错误混为一谈。

S1.1/S1.2/S1.4 已在 synthetic 范围完成技术验证：`process_record@1.0.0` 固定上述
结构字段与 BPMN hash/parser provenance；结构 parser 保留原标签，确定性抽取 pool、
lane、activity、event、gateway 和 sequence flow，并派生 direct/transitive reachability、
activity order、branch/parallel、cycle 与 unreachable nodes。两个合成 BPMN fixture 及
负例由 exact-hash gate 锁定。这些证据只说明结构合同可执行，不是正式 BPMN 性能结果。

S1.3 进一步冻结两个透明的标签下限。P0 仅复制 activity raw label 与 lane-label context，
不产生 actor、action 或 business object；P1 只在存在唯一非空 lane label 时产生 actor
surface，并把折叠空白后的首个 token 作为 action surface、余文作为 business-object
surface。P1 不做词形还原、POS tagging、受控词表或学习推断；空标签、标点首词、
无泳道和多泳道歧义均显式标记。该合同已在 6 个 synthetic activities 上通过 exact-hash
验证，但 P2 与正式性能评价仍未完成。

S1.5 已固定人工核对工作文件的空白协议：每个 process 精确绑定 BPMN 与 Process
Record hash，每个 activity 显示 raw label/lane context，但 actor/action/business object
均以 unreviewed/null 初始化，P0/P1 候选不得自动写入 Gold。只有 formal membership
已冻结、所有结构和标签字段由人 adjudicate、Gold Process Record 通过验证时才可冻结。
当前活动正式 BPMN 和人工 Gold 均为 0，因此这只是协议证据，不是标注结果。

S1.6 已冻结评价算术：pool/lane/activity/event/gateway/flow、direct edge 和 activity
order 按集合计算 P/R/F1；actor/action/business-object 按 exact surface value 计算字段与
micro P/R/F1、value accuracy，并报告三字段同时正确的 activity-level accuracy。缺失、
terminal error 和 invalid prediction 均保留在分母。验证用 synthetic reference 常数，
formal scope 当前会拒绝，因此不得把这些常数写成 Stage 1 性能。
[[TODO-STATUS:S1.7：回填正式 membership、Gold、P2、指标与 formal manifests]]

### 3.2 Stage 2：Rule Record

Stage 2 把法规文本转换为 canonical Rule Record。已验证的 v1.0.0 预测合同要求所有
B0/H1/D1 输出包含 sample/source ID、完整 source text、一个或多个 clause、四类
modality，以及 actor、action、condition、constraint、exception 五类 span 数组；
actor-action map 和 order relations 通过稳定 ID 引用相应 span。每个证据片段同时保存
原文 text、字符 start/end 和独立 normalized value，且必须满足
`text == source_text[start:end]`。

JSON Schema 之外的确定性校验还检查 clause 与 span ID 唯一性、子 span 的 clause
边界、actor/action 引用和顺序关系引用。记录必须带方法名、schema source、验证错误和
`unsupported_or_ambiguous`；生产器不能自行伪造 validation 结果。该合同已经由项目
测试验证，但它只是方法间接口，不代表任何方法已经完成或取得性能结果。

### 3.3 Stage 3：Violation Report

Stage 3 消费 Process Record 与 Rule Record，先进行规则—流程匹配，再判断
compliant/none、missing_action、incorrect_actor 和 out_of_order。目标 Violation
Report 至少包含 process/rule ID、matching score、一个或多个违规类型、相关 activity、
lane/actor 或 order pair、文本与 BPMN 证据、threshold/model version、输入 hash 和
运行 manifest。Oracle 实验将输入 Gold Process/Rule Records，端到端实验才输入上游
预测，以此分开 Stage 3 自身能力与误差传播。

当前 Stage 3 只有 fixture/scaffold，原 4 个或扩展 7 个 GDPR BPMN、matching Gold、
violation Gold、方法和阈值均未冻结。本节同样只定义输出合同和评价分层。
[[TODO-STATUS:S3.1–S3.11：回填数据范围、Winter/Sun/现代 baseline、阈值与 manifest]]

## 4. 方法

### 4.1 B0：非 LLM 的 Sun Stage 2 独立重建

B0 的正式定义是完全不调用 LLM 的 Sun Stage 2 独立重建，由句子级模态分类与短语级
六要素抽取两部分组成。句子级目标分类器为 BERT-TextCNN，输出 definition、
obligation、prohibition 和 permission。项目已经完成官方补充包的字节、schema、冲突
quarantine 与 development split 核验。数据许可证证据仍为
`unknown_pending_confirmation`，但项目所有者已明确允许把本地副本用于本论文的非商业
训练、开发集选择与评价，同时禁止再分发原始或逐条派生数据。该决定不等于发现了显式
权利人许可证。S2.4 已用固定配置完成 Legal-BERT + TextCNN 的训练、development
选择与唯一一次 test 评价。S2.6 随后完成了完整 B0 的技术组合验证。

短语级 S2.5 已验证 CoreNLP 4.5.10 运行身份、公开来源英文 marker、Tregex/Tsurgeon
规则合同和 synthetic live fixtures。当前冻结的处理顺序为 modality、condition、
constraint、exception、action、actor；其中 action 在前述限定成分定位并移除后抽取，
以减少作用域混入。该验证证明 12 个候选 pattern 可编译并在合成句上产生预期字段与
tree surgery，不是对真实数据的性能评价，也不代表已恢复 Sun 的完整原始 lexicon。

S2.6 已把已验证的 BERT-TextCNN 与已验证的短语抽取器组合并转换为 canonical
Rule Record，再以同一 validator 检查输出。联调明确采用德文文本进入分类器、对齐英文
文本进入短语抽取与 canonical evidence 的双语路由。锁定 synthetic manifest 生成 1 条
record/1 个 clause，schema invalid 和 cross-field invalid 均为 0；它证明组件接口可执行且
全程不调用 LLM，但不是 phrase 性能评价或 Stage 2 正式主表结果。旧 heuristic 产物不再是
活动 B0 入口，当前实现仍只能称 paper-faithful independent reconstruction。

### 4.2 H1：selective LLM fallback

H1 的设计原则是完整复用同一个 B0，只对推理时可观察到的失败或不确定字段调用 LLM，
而不是在触发后无条件重做整句。候选 trigger 包括 parser/Tregex 失败、schema invalid、
非 definition 子句缺少 action、模态置信度或 margin 低于阈值、互斥字段 span 冲突、
marker 命中但作用域缺失、actor 候选无法由依存关系消歧，以及固定 Stage 3 adapter
拒收。trigger 不得读取 Gold、样本是否预测错误或测试集类别分布，所有阈值只能在
development split 上确定并在测试前冻结。

LLM 返回 field-level repair patch，指明 sample/clause、被修复字段、替换 span、修复
原因和 provenance。runner 将 patch 合并回原 B0 记录，保留未触发字段与规则证据，
然后重新运行 canonical validator；失败、重试和未修复状态均进入覆盖率和成本统计。
S2.8 已在不读取 Gold/test、也不调用真实 LLM 的条件下完成离线预注册。H1 runner 已
重基到 verified S2.6 canonical B0；模态 confidence/margin 阈值冻结为严格低于 0.60/
0.15，结构 trigger 只接受运行时可见 telemetry。actor/action 修复自动带上引用字段，
patch 只能整字段替换；envelope、span、ID 引用或合并后 canonical validation 失败时，
回退 B0 的语义内容但把 method identity 保持为 H1。provider error 也按 recovered error
单独记账，使该条 canonical fallback 留在 H1 评价分母并继续计分，而不是把记录置空或
丢弃。离线合同固定 `gpt-4.1-2025-04-14`、temperature 0、按 sample/clause 排序的名额
分配，以及正式 150 条输入最多 45 次、每条最多一次、0 重试、46.08 万总 token 与
1.5 USD 硬上限。以上只证明合同、请求渲染、merge 与失败计分语义可执行；真实调用、
质量、实际成本和性能仍无证据，且尚未授权。

### 4.3 D1：Direct LLM

D1 不运行 B0，也不读取 B0 预测或 Gold，而是从同一法规输入直接生成完整 canonical
Rule Record。prompt 将要求每个字段返回原文 evidence span 和独立 normalized value，
信息缺失时输出空数组或显式 `unsupported_or_ambiguous`，不得猜测隐含 actor、改写
evidence text 或把 exception 静默并入 condition。输出经过与 B0/H1 相同的 schema、
字符边界、引用关系和确定性 normalization 检查；schema invalid、解析失败或 API error
均保留在分母和失败清单中。

S2.9 已将上述方法冻结为离线、可审计合同。检查发现 v3 文档中的嵌套 Markdown fence
会使实际 user prompt 在第一个示例的 `Output:` 处被 loader 截断，因此 v4 改为显式
插入 4 个独立解析并验证的 few-shot。模型固定为 dated snapshot
`gpt-4.1-2025-04-14`，temperature=0、top_p=1、max output=4096；稳定性设计对每条
输入独立运行 5 次，0 重试。150 条全量最多 750 次调用、输入/输出合计 token 上限
9,216,000，按冻结标准价格的最坏估算为 36.864 USD，并设 37 USD 硬上限。synthetic
dry-run 还验证 non-JSON、identity mismatch 和 API error 均保留为 S2.10-E attempt，
不会从分母删除。该事实只说明 prompt/model/budget/失败合同已验证；真实调用仍未获
授权，也没有 D1 性能结果。

### 4.4 共享控制与可审计性

B0、H1 和 D1 的唯一允许差异是 Stage 2 方法本身。正式比较将固定 input/test IDs、
Gold、canonical schema、normalization、evaluator 和 Stage 3 配置，runner 对 Gold 不可见，
三组输出写入彼此独立且默认拒绝覆盖的目录。每次运行的 manifest 将记录输入与代码
hash、方法/规则/prompt/模型版本、依赖、阈值、随机种子、失败数、调用与成本信息。

任何无法生成合法记录的样本都不能从评价中删除；除逐字段和逐类别 P/R/F1 外，论文还
将报告 schema-valid rate、完整记录覆盖率、unsupported、超时/API error 和重试情况。
这些控制中的统一评价器已由 S2.10-E synthetic exact-hash gate 验证；但数据、Gold 和
正式方法运行尚未冻结，因此仍不能把 B0/H1/D1 比较改写为正式执行时态。
[[TODO-STATUS:S2.13：用 formal manifests 回填共享控制的最终版本与实际失败统计]]

## 5. 数据与人工 Gold

### 5.1 官方 modality 数据

句子级 modality 轨道使用 Sun 官方 Archive.org 补充包
`Decision_Logic_data.zip` 中的 `EStG_sent_vec.csv`。项目已把 ZIP 的 size、官方
SHA-1、CSV member hash、三个预期成员和安全路径逐项锁定，并对 470,740,514 个解压
字节和全部 2,833 行完成流式 schema 审计。CSV 无表头，法规文本位于第 3 列，四个
strict one-hot 标签位于第 4–7 列；四列与 Michel 原文分布的唯一对应为 definition、
obligation、permission、prohibition。原始分布分别为 1,190、1,274、265 和 104。

第 0 列只有 164 个不同值，不能充当 2,833 行的唯一 source ID，因此 importer 明确
使用由 source asset、row index 和 normalized text 派生的稳定 ID。完整扫描还发现一个
原文完全相同、但分别标为 permission 和 obligation 的两行冲突组。该问题在任何训练
或评价前处理：项目不选择或改写任一原标签，保留 2,833 行 raw source 不变，只把精确
锁定的 row 616/1221 整组写入 hash-only quarantine，并从主分析数据排除。该处理是
预注册的数据质量隔离，不是“修正了两个标签”。

隔离后的主分析集为 2,831 行，分布为 1,190/1,273/264/104。项目以 seed 20260715
执行 0.70/0.15/0.15 的 normalized-text group-aware split，得到 train 1,985、dev 420、
test 426；相同 normalized text group 不跨 split，三个集合两两不交且并集覆盖全部分析
行。该拆分是 `project_reconstructed_deterministic_split`，不是 Sun 原始 split。所有
方法必须共享同一 population 与 membership hash，已登记但尚未运行的 full-source
sensitivity variant 也不得替代主表。

这套 ingestion、schema、quarantine、split 与重放已通过 development 门禁。许可证
仍为 `unknown_pending_confirmation`；项目决定允许本地非商业训练、开发集选择、评价和
发表不可逆聚合指标，但不允许再分发原始文本、向量或逐条派生数据，也不允许把该决定
表述为显式权利人许可。S2.4 运行 `s24_legal_bert_textcnn_seed20260717_v1` 共完成 7 个
epoch，并按 development macro-F1 选择 epoch 5。唯一一次 test 评价覆盖 426 条记录，
accuracy 为 0.924883，macro-F1 为 0.851071；详细逐类聚合指标、配置和输入 hash 见版本化
manifest。该数字是独立重建分类器的 development 组件结果，不是完整 B0 或 Stage 2 正式
主表结果，也不是 Sun 原始 split 上的复现值。

### 5.2 项目固定 EStG-150

六要素评价使用项目唯一固定的 EStG-150。membership 是从 885 条候选池中一次性选定
的 150 个 legacy record ID，canonical ID 为六位补零形式；membership payload SHA-256
为 `8573e105d2bc167c6aa0a92c16f79a3aaf725baadfea86f0b5d2b1ea68b1e0d7`。它是
`independently_reconstructed_estg_150_v1`，不是 Sun 的原始 150，也不得重新抽样、替换
样本或建立平行的 old/new 150。

为同时保留原文、机器辅助与人工责任，审核数据被拆成同一 membership 的五个层次：

| 层 | 内容 | 在审核中的权限与作用 |
|---|---|---|
| A | 150 条德文原文 | 永久只读，作为 source identity |
| B | LLM 英文翻译候选及 provenance | 永久只读，只是待核候选 |
| C | LLM 六要素候选 | 永久只读，`human_approved=false` |
| D | 中文 gloss 与英文回译辅助 | 永久只读；当前未获真实调用授权，字段保持空值 |
| E | 人工修正、逐字段决定与 review state | 唯一可编辑层，只能由人工审核工具写入 |

Layer C 的候选被复制到 Layer E 仅为降低录入负担，复制不等于接受。审核者先接受、
编辑、拒绝或标记待裁决的英文翻译，再对每个 clause 的 modality、actor、action、
condition、constraint 和 exception 分别作 `accepted`、`edited`、`rejected` 或
`needs_adjudication` 决定。modality 必须显式四选一，不设 obligation 默认值；span 必须
满足原文字符边界和 clause 作用域，actor-action map 与 order relations 的引用也必须
有效。任何 approved English 变更都会使旧 span 失效并把记录退回待审状态。

单条状态依次经历 `needs_review → in_progress → reviewed → adjudicated`。标记 reviewed
要求翻译和六字段均已作决定且结构校验通过；标记 adjudicated 还要求先处于 reviewed，
并消除全部 `needs_adjudication`。这些状态只能由人工操作触发，每次保存均执行原子替换、
validator、action log 和带时间戳的整文件备份。最终只有 150/150 均 adjudicated、所有
字段决定均已解决且全局 `freeze_ready=true` 时，才可冻结注释。

截至本稿状态快照，Layer E 为 format-valid，但 approved English、reviewed 和
adjudicated 均为 0/150，六字段决定为 0/900；`human_review_input_ready=true` 仅表示
可以开始审核，`human_review_freeze_ready=false`。正式 Gold 还需 route、dataset、
Stage 3 与 publication whitelist 分别重锁，所以最终名称只能在门禁通过后写为
`LLM-assisted, human-adjudicated Gold`，不能称为纯人工或从零人工标注。

[[TODO-STATUS:S2.2：150/150 后回填 accepted/edited/rejected、裁决、reviewer 与一致性统计]]

### 5.3 复杂法律语料

RQ2 的外部验证输入已在查看任何方法结果前锁定为
`gdpr_2016_679_articles_5_50_seeded50_v1`。原文来自 EU Publications Office 的
CELEX `32016R0679` 英语 Official Journal Formex XML；EUR-Lex legal notice 允许法律
文件在未另行限制时用于商业或非商业复用，本项目保留来源署名和变更说明。程序从
Articles 5–50 解析 200 个顶层条文单位，在每个 Article 内按固定 seed 的 SHA-256 rank
选择一条，再从剩余单位中选择 4 条，形成覆盖全部 46 个 Article 的 50 条 membership
（hash=`9a6a2c...d09c28b9`）。选择过程只读取原文字节、locator 和固定 seed，不读取
预测、错误或评价结果。

旧 `data/development/gdpr50/` 未被升级：规范化核验只有 44/50 能匹配官方整份原文，
只有 29/50 能定位到 Article 5–50，而且其所谓 Gold 是规则自动标注待复核。活动复杂集
因此使用新的空白人工协议，逐条裁决 clause、四类 modality、五类语义 span、
actor-action map 和 order relations；无 canonical rule 的条目仍保留为负例，不因难度或
模型表现删样。当前模板结构有效但为 0/50 reviewed/adjudicated，不能称复杂集 Gold 已冻结。

G0.5 已在任何复杂集结果产生前冻结复杂度合同。文本 profile 记录字符/token、sentence/
clause、dependency depth、actor/action、condition/constraint/exception 数量与嵌套、被动
语态、隐含 actor、跨句引用和语言/翻译 provenance，并由 11 个固定布尔指标映射到
low（0–3）、medium（4–7）和 high（8–11）。BPMN profile 记录 flow node/activity/event/
gateway、lane/participant、sequence/message flow、subprocess/boundary event、弱连通分量、
cyclomatic complexity、branch/join、cycle 与 SCC condensation depth，并由 12 个固定
指标映射到 low（0–3）、medium（4–7）和 high（8–12）。语言/翻译状态只作 facet，
不计入复杂度分数；模型预测、方法错误、test 结果和事后手改 bin 会 fail closed。
synthetic fixtures 已验证合同实现；S2.11 输入 membership 与 Gold/mapping 协议已冻结，
但只有在复杂集 50/50 人工裁决后才允许以 `human_approved_gold` 生成正式文本 profile。
当前仍无正式复杂度分层统计或性能趋势。
[[TODO-RESULT:S2.11/S2.12：复杂集 50/50 人工裁决后回填 strata 分布、退化曲线与错误类型]]

## 6. 实验设计

### 6.1 Stage 2 baseline

Stage 2A 与 Stage 2B 的任务和 Gold 不同，先分别比较组件，再比较完整 Rule Record。
Stage 2A 至少包含多数类/关键词下限、一个代表性监督学习分类器和 B0 的
BERT-TextCNN，并与 H1、D1 的 modality 输出比较。Stage 2B 至少包含 marker/regex
下限、一个代表性非 LLM 句法或序列标注方法、B0 的 CoreNLP/Tregex/Tsurgeon、H1 和
D1。只有同时产生 modality 与五类 phrase spans，并通过 canonical validator 的组合，
才能进入“完整 Stage 2”表。

正式最低覆盖固定为简单规则下限、一个强监督 baseline、完整 B0、H1 和 D1。同一范式
的多个模型变体只在 development split 上选代表项，未被选择者进入附录，不能靠增加
相近变体制造比较数量。若 EStG-150 的训练标注不足以支持 CRF/token classifier，该方法
只作为条件性扩展，不从 test Gold 反向构造训练集。

S2.7-M 已完成不依赖 phrase Gold 的 modality component 比较。三个方法都使用与 S2.4
相同的项目重建 1985/420/426 split：train-majority 在 test 上的 accuracy/macro-F1 为
0.457746/0.157005，固定德文关键词为 0.483568/0.414154，word 1–2 gram Multinomial
Naive Bayes 为 0.784038/0.568849。该运行不依赖外部 ML 库、不做超参数搜索、不保存
逐条预测。为避免隐藏研究过程，manifest 明确披露：versioned run 前曾以完全相同的
NB 配置做过一次未版本化 test-label implementation smoke；没有尝试或据此选择其它
配置。上述数字只能称重建 split 的 modality component 结果，不能称完整 Stage 2，
也不能提前与未运行的 H1/D1 比较。

| 角色 | Stage 2A modality | Stage 2B phrase | 是否可称完整 Stage 2 |
|---|---|---|---|
| 简单下限 | 多数类/固定德文关键词；S2.7-M aggregate run verified | marker/regex；待 S2.2 | 仅在两组件按预注册方式组合后 |
| 监督 baseline | word 1–2 gram Multinomial NB；S2.7-M aggregate run verified | 训练 Gold 足够时选 token classifier | 取决于两组件是否均存在 |
| B0 | BERT-TextCNN | CoreNLP + Tregex/Tsurgeon | 是；S2.6 技术组合与 S2.10-E evaluator 已验证，正式 batch 待冻结 Gold/输入 |
| H1 | 复用 B0，按 trigger 修复 | field-level repair | 是；S2.8 离线合同与 S2.10-E evaluator 已验证，正式 batch 待 S2.2 与真实调用授权 |
| D1 | 直接预测 | 直接抽取 | 是；S2.9 离线合同与 S2.10-E evaluator 已验证，正式 batch 待 S2.2 与真实调用授权 |

[[TODO-DECISION:S2.7-P：phrase baseline 与完整组合仍待 S2.2；S2.7-M modality、S2.9 D1 已冻结]]

### 6.2 Stage 3 baseline

Stage 3A 规则—流程匹配至少比较 TF-IDF/BM25 下限、Winter fitness/cost、Sun semantic
matching 和一个现代 embedding + graph 方法，主指标为 AP/MAP，并辅以 Recall@k 与
nDCG@k。Stage 3B 至少比较词法+BPMN 图规则、Winter、Sun 和同一现代非 LLM 方法，
标签为 compliant/none、missing_action、incorrect_actor 和 out_of_order，报告逐类与
macro/micro P/R/F1。每个 baseline 必须注明只解决 matching、只解决 violation，还是
覆盖二者。

所有非 LLM 方法先在 Gold Process/Rule Records 的 Oracle 条件下比较；只有该表稳定后，
才预注册 Stage 3 LLM/Hybrid。随后固定同一 Stage 3，将 B0/H1/D1 的 Rule Records 分别
送入，形成独立的 end-to-end 表。Oracle、end-to-end 以及不同 BPMN 数据轨道不得混表。
[[TODO-DECISION:S3.1–S3.8：冻结 BPMN 集、Gold、adapter、threshold 与 baseline 版本]]

### 6.3 指标与统计控制

**模态分类。** 评价单元是 clause，不是整句。四类 obligation、prohibition、permission、
definition 分别报告 support、precision、recall 和 F1，主指标为四类 Macro-F1，并给出
4×4 confusion matrix。若某个数据轨道的某类 support 为 0，precision 显式记为 N/A，
recall/F1 按冻结 evaluator 规则处理，不能静默从 macro 平均中删除。

**六要素与 span。** actor、action、condition、constraint、exception 分别报告 exact
span 和 token-overlap P/R/F1；exact 要求 text、start、end 全部相等，token overlap
使用 token set IoU/Jaccard。micro 聚合所有评价单元，macro 先按 sample 计算再平均，
两者分开报告。modality 仍按四分类评价，不与 phrase span F1 混成一个不透明总分。

**完整性与结构。** 为避免只看“命中的 span”，副表还报告 gold-required presence
recall、predicted-field precision、hallucinated-field rate、complete-record rate、
schema-valid rate、unsupported/ambiguous rate 和 invalid/API-error rate。actor-action 与
order-relation 使用 edge P/R/F1，clause segmentation 使用 exact-match 与 span IoU。
`TP/(TP+FP+FN)` 只能称 Jaccard/edge IoU，clause ID 唯一性属于 validation invariant，
不能称为 accuracy。S2.10-E 已把 clause/entity 对齐冻结为 exact ID 优先、未匹配项再按
exact raw span 的 Hybrid；数组位置对齐被禁止，所有方法使用同一策略。

**归一化敏感性。** 主结果使用 strict span；secondary 结果使用版本化的 safe
normalization，只允许 Unicode NFC、大小写、空白折叠和尾部标点等低风险操作，并报告
相对 strict 的 lift。去冠词、词形还原、复数折叠、同义词和数字/单位转换默认关闭；
loose 规则只作为附录敏感性分析。机器 normalization-aware matching 与人工抽样判断的
style-equivalent alignment 是两个概念，后者必须报告抽样和人工一致性，不能自动化替代。
当前实现固定 `safe-legal-v1`，并提供固定 seed、默认 40 条且空白起始的人工三分类模板；
article/plural/lemma/同义词/数字换算等 loose 规则没有进入冻结 evaluator。

**Stage 3。** matching 报告 AP、MAP、Recall@k 和 nDCG@k；违规检测报告四类 support、
P/R/F1 与 macro/micro。Stage 2 与 Stage 3 的数字、Oracle 与 end-to-end 的数字分别
成表，不用跨阶段分数高低证明方法优劣。

### 6.4 统计比较

所有主比较均为 paired design：方法共享相同 sample IDs，差异按同一评价单元计算。
S2.12-P 已在查看正式结果前把 `sample_id` 冻结为重采样 cluster，使同一记录中的多个
clause 和 span 在重采样时保持关联。每个主指标报告点估计、95% percentile bootstrap
区间和相对 B0 的绝对差值及区间；bootstrap 固定为 10,000 次。双侧 p 值使用另一个
固定 seed 的 10,000 次 paired sample-cluster sign-swap randomization，并加一修正。
每个数据轨道把两个 contrast（H1−B0、D1−B0）乘以六个主 endpoint（modality
Macro-F1 与五字段 strict exact F1）组成 12 个假设的 Holm family；两条数据轨道不合并
成一个 family。stratum-specific 和次要指标为带区间的描述性分析，不进入主 Holm family。

对 D1/H1 等随机方法，还将把同一冻结输入上的重复运行与样本 bootstrap 分开：前者
描述运行间稳定性和 field/span agreement，后者描述样本不确定性。类别不均衡通过
per-class support、macro 指标和 confusion matrix 显式呈现。无显著差异或负向差异照实
报告，不通过修改 Gold、threshold、trigger、normalization 或删除失败样本制造优势。
D1 主指标只使用预注册的 primary repeat 1；其余四次只报告稳定性，不作为显著性重复。
上述参数、seed 和错误分类优先级已由 `s212_analysis_protocol.json` 与 synthetic exact-hash
manifest 冻结；synthetic 数字不进入结果章节。Stage 3 的独立统计族仍在 S3.7 前冻结。

### 6.5 复现与运行门禁

正式运行前，manifest 必须冻结数据来源与许可、sample IDs、输入/Gold SHA-256、schema、
split/seed、方法命令、代码 commit、依赖、模型/checkpoint、prompt/rule/marker 版本、
temperature、threshold、调用上限和 evaluator version。runner 只读取 frozen input，不能
读取 Gold；三种方法写入不同目录并默认拒绝覆盖，每个 invalid、skip、timeout 和 API
error 均进入结果摘要。

执行顺序为：先通过 final-ready 审计和全量测试，再列出并核对正式命令，最后在真实
LLM 调用获得用户明确授权且硬预算已锁定时运行。每个实际 experiment run 必须有唯一
run ID、manifest、命令、事件日志、结果摘要和成功/失败状态。当前 formal runner 会在
门禁未通过时拒绝执行。正式 evaluator 已由 S2.10-E 冻结，但统计参数、正式数据/Gold
和方法运行仍未冻结，因此本节仍是预注册设计，不构成实验已运行。

与前人结果比较继续采用 C1–C4 证据等级：同 frozen IDs/Gold/evaluator 的 C1 重跑才是
主优劣证据；C2 只限同一官方数据轨道；C3 论文报告值只作描述；C4 跨任务或跨阶段数字
禁止直接比较。
[[TODO-STATUS:S2.13/S3.11：回填最终 evaluator、commands、manifests 与环境摘要]]

## 7. 结果（仅模板）

本章当前只定义结果结构，所有待测数值单元均为 `—`，状态均为 `TEMPLATE`。任何回填
必须来自已记录 `experiment_run` 事件的 formal manifest，并同时核对 run ID、commit、
input/Gold/evaluator hash、样本数和失败数；禁止手工复制 development 输出或论文报告值。

### 7.1 Stage 2 主数据

#### 7.1.1 Modality 四分类主表

| 方法 | 状态 | Clause N | Obl. F1 | Proh. F1 | Perm. F1 | Def. F1 | Macro-F1 [95% CI] | Invalid/Fail N |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 简单规则 | TEMPLATE | — | — | — | — | — | — | — |
| 强监督 baseline | TEMPLATE | — | — | — | — | — | — | — |
| B0 | TEMPLATE | — | — | — | — | — | — | — |
| H1 | TEMPLATE | — | — | — | — | — | — | — |
| D1 | TEMPLATE | — | — | — | — | — | — | — |

表下注明：四类 support、micro 指标、split/membership hash、bootstrap 配置和 confusion
matrix 图号。[[TODO-RESULT:S2.10-A：只从 modality formal manifest 回填]]

#### 7.1.2 六要素抽取主表与字段副表

| 方法 | 状态 | Actor Exact F1 | Action Exact F1 | Condition Exact F1 | Constraint Exact F1 | Exception Exact F1 | Phrase Micro/Macro F1 | Token-overlap Macro F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 简单规则 | TEMPLATE | — | — | — | — | — | — | — |
| 强非 LLM baseline | TEMPLATE | — | — | — | — | — | — | — |
| B0 | TEMPLATE | — | — | — | — | — | — | — |
| H1 | TEMPLATE | — | — | — | — | — | — | — |
| D1 | TEMPLATE | — | — | — | — | — | — | — |

详细副表按“方法 × 字段”展开：

| 方法 | 字段 | Gold N | Pred N | Exact P/R/F1 | Token P/R/F1 | Strict F1 | Safe F1 | Normalized lift |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 〈方法〉 | actor | — | — | — | — | — | — | — |
| 〈方法〉 | action | — | — | — | — | — | — | — |
| 〈方法〉 | condition | — | — | — | — | — | — | — |
| 〈方法〉 | constraint | — | — | — | — | — | — | — |
| 〈方法〉 | exception | — | — | — | — | — | — | — |

正式生成时为每个方法复制五行；loose normalization 只进入附录敏感性表。
[[TODO-RESULT:S2.10-B：只从 phrase formal manifest 回填]]

#### 7.1.3 完整记录、结构、失败与成本

| 方法 | Gold-required Recall | Pred-field Precision | Hallucination Rate | Complete Record | Schema-valid | Actor-action Edge F1 | Order Edge F1 | Unsupported | Invalid/API-error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 简单规则 | — | — | — | — | — | — | — | — | — |
| 强非 LLM baseline | — | — | — | — | — | — | — | — | — |
| B0 | — | — | — | — | — | — | — | — | — |
| H1 | — | — | — | — | — | — | — | — | — |
| D1 | — | — | — | — | — | — | — | — | — |

| 方法 | Trigger Rate | LLM Calls | Input/Output Tokens | Median/P95 Latency | Retries | Failed N | Estimated Cost | Repeated-run Agreement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 | N/A | 不调用（方法定义） | N/A | — | N/A | — | N/A | — |
| H1 | — | — | — | — | — | — | — | — |
| D1 | N/A（direct） | 每条输入（设计定义） | — | — | — | — | — | — |

表中的 B0 不调用 LLM 与 D1 逐输入调用是方法定义，不是性能结果；其余字段仍待正式
manifest。[[TODO-RESULT:S2.10-C：回填覆盖、结构、失败、稳定性与成本]]

### 7.2 复杂度分层与错误类型

S2.12-P 分析协议已经完成，但正式分层结果仍未运行。low/medium/high 直接使用 G0.5
固定分箱；任何分层少于 10 个 sample cluster 时只报告 N 与点估计，并把区间标为不可估，
不得在看结果后合并或删除。invalid、API error 和 missing attempt 继续留在原分母中。

| 数据轨道 | 复杂度维度/分箱 | 方法 | Bin N | Modality Macro-F1 | Phrase Exact Macro-F1 | Complete Record | Invalid/Fail | 95% CI |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 主数据 | 〈预注册 bin〉 | 〈方法〉 | — | — | — | — | — | — |
| 外部复杂集 | 〈预注册 bin〉 | 〈方法〉 | — | — | — | — | — | — |

预留图形如下；只有对应表的 formal manifest 解锁后才生成：

| 图 ID | 图形 | x 轴 | y 轴 | series/分面 | 不确定性与数据源 |
|---|---|---|---|---|---|
| F7-1 | 复杂度退化曲线 | 预注册 complexity bin | Modality Macro-F1 | 方法；按数据轨道分面 | sample-cluster 95% CI；S2.12 manifest |
| F7-2 | 复杂度退化曲线 | 同上 | Phrase Exact Macro-F1 | 方法；按字段分面 | sample-cluster 95% CI；S2.12 manifest |
| F7-3 | Risk–coverage | retained coverage | error risk / 1−score | B0/H1/D1 | trigger/uncertainty manifest |
| F7-4 | 质量—成本前沿 | 每样本成本或调用率 | 主指标 | H1 预算/trigger 变体、D1 | bootstrap CI + cost manifest |
| F7-5 | Confusion matrix | predicted modality | Gold modality | 每方法一图，共享色标 | S2.10-A evaluator output |
| F7-6 | 错误构成堆叠图 | 方法 | 错误数或率 | missed/misclassified/extra/invalid | S2.12 error taxonomy |

[[TODO-RESULT:S2.12：冻结 bins 后从正式 complexity/error manifests 生成表和 F7-1–F7-6]]

### 7.3 Oracle Stage 3

规则—流程匹配表：

| 方法 | 状态 | Query/Rule N | AP | MAP [95% CI] | Recall@k | nDCG@k | Failed N |
|---|---|---:|---:|---:|---:|---:|---:|
| TF-IDF/BM25 | TEMPLATE | — | — | — | — | — | — |
| Winter | TEMPLATE | — | — | — | — | — | — |
| Sun | TEMPLATE | — | — | — | — | — | — |
| Embedding + graph | TEMPLATE | — | — | — | — | — | — |
| LLM/Hybrid（若解锁） | TEMPLATE | — | — | — | — | — | — |

违规检测表：

| 方法 | None F1 | Missing-action F1 | Incorrect-actor F1 | Out-of-order F1 | Macro/Micro F1 | Evidence Coverage | Invalid/Fail N |
|---|---:|---:|---:|---:|---:|---:|---:|
| 词法+BPMN 图规则 | — | — | — | — | — | — | — |
| Winter | — | — | — | — | — | — | — |
| Sun | — | — | — | — | — | — | — |
| Embedding + graph | — | — | — | — | — | — | — |
| LLM/Hybrid（若解锁） | — | — | — | — | — | — | — |

[[TODO-RESULT:S3.7：只从 Gold Process/Rule Records 的 Oracle manifests 回填，不混入端到端]]

### 7.4 端到端与归因消融

| 组合 | Stage 2 | Stage 3 | 状态 | Matching MAP | Violation Macro-F1 | End-to-end Coverage | Failed N | 相对 E00 差值 [95% CI] |
|---|---|---|---|---:|---:|---:|---:|---:|
| E00 | Sun | Sun | TEMPLATE | — | — | — | — | — |
| E10 | Improved | Sun | TEMPLATE | — | — | — | — | — |
| E01 | Sun | Improved | TEMPLATE | — | — | — | — | — |
| E11 | Improved | Improved | TEMPLATE | — | — | — | — | — |

若只完成 Stage 2 改进而 Stage 3 尚未扩展，先单列 B0/H1/D1 → 同一 Sun Stage 3 的
误差传播表，不虚构 E01/E11。[[TODO-RESULT:E00/E10/E01/E11：只从正式交叉消融 manifests 回填]]

### 7.5 结果 provenance 登记

| 结果块 | Run ID | Manifest | Event time | Git commit | Input hash | Gold hash | Evaluator/version | 样本/失败数 | 复核状态 |
|---|---|---|---|---|---|---|---|---|---|
| S2.10-A modality | — | — | — | — | — | — | — | — | BLOCKED |
| S2.10-B phrase | — | — | — | — | — | — | — | — | BLOCKED |
| S2.12 complexity | — | — | — | — | — | — | — | — | BLOCKED |
| S3.7 Oracle | — | — | — | — | — | — | — | — | BLOCKED |
| S3.10 end-to-end | — | — | — | — | — | — | — | — | BLOCKED |
| P8 E00/E10/E01/E11 | — | — | — | — | — | — | — | — | BLOCKED |

本登记表的 `BLOCKED` 是当前真实门禁状态，不是实验结果。每个结果块只有在主张矩阵
由 `BLOCKED_RESULT` 更新为有正式证据后才可进入正文叙述。

## 8. 讨论与局限性

当前可确认的复现边界包括：Sun 完整 Stage 2 源码、权重、完整 marker 和原始 150
phrase Gold 不可得；德文法规与英文公共 marker 之间需要显式语言适配；Sun 报告的
四个 GDPR BPMN 文件名尚未在现有证据中确定；不同论文的数据、split 和指标不能直接
用于严格显著性比较。

[[TODO-RESULT:S2.12/S3.10：结合正式结果讨论适用边界和失败案例]]

## 9. 结论

[[TODO-RESULT:P8：所有正式实验和主张复核完成后撰写]]
