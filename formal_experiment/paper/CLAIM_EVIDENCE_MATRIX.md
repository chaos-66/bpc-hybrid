# 科学主张—证据矩阵

**状态**：活动写作控制表  
**当前正式实验结果**：0；任何性能结论均保持 `BLOCKED_RESULT`

状态只使用：`VERIFIED_PRIMARY_SOURCE`、`VERIFIED_PROJECT_FACT`、
`PLANNED_METHOD`、`BLOCKED_RESULT`、`PROHIBITED_CLAIM`。

| ID | 论文主张 | 状态 | 当前证据 | 允许时态/表述 | 解锁任务或正式来源 |
|---|---|---|---|---|---|
| C01 | Sun 将完整方法组织为流程模型拆解、法规文档解析和多重违规检测三个部分；本项目将其操作化为 Stage 1/2/3 | VERIFIED_PRIMARY_SOURCE | Sun 最终版 Section 4 / Figure 1；主 Pipeline 规定项目映射 | 可分别陈述原文三部分与本文阶段映射；不能混写成作者章节命名 | `[[TODO-SOURCE:SUN2024:核对最终版页码]]` |
| C02 | Sun Stage 2 最终版使用 BERT-TextCNN 与 CoreNLP/Tregex/Tsurgeon | VERIFIED_PRIMARY_SOURCE | 机器合同和 Sun 证据导航 | 一般现在时；不能说本项目已完成 | `[[TODO-SOURCE:SUN2024:核对方法页码]]` |
| C03 | 本项目已完成 Sun Stage 2 B0 组件的独立、可审计 paper-faithful technical reconstruction；正式 batch/性能评价尚未完成 | VERIFIED_PROJECT_FACT | contract、S2.4/S2.5/S2.6 manifests、机器门 | 可写技术实现已组合；不能写 exact/original 或完整正式评价已完成 | S2.10 formal manifest |
| C04 | 工作区没有 Sun 完整 Stage 2 源码、权重、完整 marker 和原始 150 phrase Gold | VERIFIED_PROJECT_FACT | 项目研究证据和机器 blocker | 作为复现边界与局限 | 投稿前再核查资产 |
| C05 | 项目只有一个固定 EStG-150 membership | VERIFIED_PROJECT_FACT | membership hash、ROUTE_LOCK | 已固定；不是 Sun 原始 150 | hash 不得变 |
| C06 | 项目 Gold 采用五层 LLM-assisted、human-adjudicated 流程 | VERIFIED_PROJECT_FACT | AGENTS、HUMAN_GOLD_GUIDE、contract | 可写流程；当前仍 0/150 | S2.2 后回填裁决统计 |
| C07 | B0、H1、D1 将共享 IDs/Gold/schema/normalization/evaluator | PLANNED_METHOD | contract、methods registry | 将/计划；不能写已完成比较 | S2.10/S2.13 |
| C08 | 复杂法律语料可能放大传统方法与 LLM 的差异 | PLANNED_METHOD | RQ2、导师要求 | “待检验假设”，不能写既定事实 | G0.5、S2.11、S2.12 |
| C09 | H1 的选择与字段级 merge 合同已预注册；若未来获授权，只有预注册失败/不确定字段可进入 LLM 请求 | VERIFIED_PROJECT_FACT | S2.8 config、dry-run manifest、exact-hash gate | 可写离线合同已验证；不能写真实调用或性能已完成 | 真实调用授权 + S2.10 |
| C10 | LLM/Hybrid 优于完整 B0 | BLOCKED_RESULT | 当前无正式结果 | 禁止比较词 | S2.10/S2.12 formal manifest |
| C11 | LLM 在复杂法律语料上优势更明显 | BLOCKED_RESULT | 当前无冻结复杂集或结果 | 禁止结论 | S2.11/S2.12 formal manifest |
| C12 | Stage 3 改进带来 Oracle 提升 | BLOCKED_RESULT | 当前只有 scaffold | 禁止结论 | S3.7 formal manifest |
| C13 | Stage 2/3 改进带来端到端提升 | BLOCKED_RESULT | 当前未完成两阶段冻结 | 禁止结论 | E00/E10/E01/E11 manifests |
| C14 | 旧 heuristic runner/产物是完整 Sun baseline | PROHIBITED_CLAIM | 与 methods registry 和 S2.6 gate 冲突 | 只能称 development provenance；活动 B0 是独立重建组件组合 | 永不允许 |
| C15 | EStG-150 是 Sun 原始 150/443 spans | PROHIBITED_CLAIM | 与 membership 决策冲突 | 必须称项目独立重建 benchmark | 永不允许 |
| C16 | Gold 是纯人工或从零人工标注 | PROHIBITED_CLAIM | Layer C 为 LLM 候选 | 必须披露 LLM assistance | 永不允许 |
| C17 | Barrientos 已实现 Sun 六要素或标签完全兼容 | PROHIBITED_CLAIM | schema/modality 不同 | 只能写工程借鉴与显式 adapter | 永不允许 |
| C18 | Stage 2 与 Stage 3 或不同数据的数字可直接证明优劣 | PROHIBITED_CLAIM | C1–C4 比较合同 | 必须分表并标证据等级 | 永不允许 |
| C19 | Stage 3 将先做 Gold Process/Rule Records 下的 Oracle 比较，再做端到端误差传播 | PLANNED_METHOD | 主 Pipeline、实验矩阵 | 将/计划；Oracle 与 end-to-end 必须分表 | S3.7、S3.10 |
| C20 | E00/E10/E01/E11 将用于区分 Stage 2、Stage 3 与二者交互贡献 | PLANNED_METHOD | 主 Pipeline 最终归因消融 | 将/计划；不能提前写成已观察到的贡献 | P8 formal manifests |
| C21 | 若改进方法未超过重建 baseline，负结果仍将作为适用边界报告 | PLANNED_METHOD | 主 Pipeline 的最终目标与统计控制 | 研究承诺/报告原则；不能预写结果方向 | 各 formal manifest 与失败记录 |
| C22 | Winter 直接解析流程模型与法规段落，以 fitness/cost 进行 pairwise matching，并检查必需活动、顺序和组织实体问题 | VERIFIED_PRIMARY_SOURCE | Winter et al. (2020) §§3.2–3.3，官方作者稿 | 一般现在时；只能作为 Winter 方法描述 | Winter 官方 PDF pp. 189–203 |
| C23 | Sleimi 的框架包含 6 类句子级和 18 类短语级法律语义元数据，并结合句法规则、marker 与 actor-role 分类 | VERIFIED_PRIMARY_SOURCE | Sleimi et al. (2021) §§3–7，arXiv 作者稿；原文 pp. 4、14–18 | 一般现在时；不能等同于 Sun 六要素 schema | arXiv:2001.11245 |
| C24 | Michel 的 EStG 任务包含 definition/obligation/permission/prohibition 四类共 2,833 条，原文分布为 1190/1274/265/104 | VERIFIED_PRIMARY_SOURCE | Michel et al. (2022) §3、Table 1，作者 PDF | 可报告原文数据构成；不能把论文值当本文重跑结果 | DOI 10.24251/HICSS.2022.752 |
| C25 | Sun 的方法比 Winter 增加句子级模态与短语级语义分类，但二者的研究继承不构成源码或实现身份 | VERIFIED_PRIMARY_SOURCE | Sun et al. (2024) §4/Fig. 1 与 Winter et al. (2020)；项目代码来源审计 | 可描述方法关系；S2.6 项目实现必须称独立重建 | Sun/Winter 一手论文；项目 S2.6 manifest |
| C26 | Barrientos 的 RC4PC 面向法规变更影响，使用受控词表、schema、验证和归一化；其任务与标签不等同于本文 Stage 2 | VERIFIED_PRIMARY_SOURCE | Barrientos et al. (2026) §§4–6，作者 PDF；项目 schema 对照 | 只能写工程借鉴和差异；禁止迁移结果结论 | DOI 10.1016/j.infsof.2026.108079 |
| C27 | Stage 2 canonical prediction schema v1.0.0 与跨字段 validator 已由项目测试验证，B0/H1/D1 必须共享该接口 | VERIFIED_PROJECT_FACT | `STAGE2_CANONICAL_SCHEMA_SPEC.md`、schema、validator、全量审计 | 可写接口已验证；不能据此声称方法已完成 | S2.13 时回填最终 schema/manifest |
| C28 | S2.5 的 CoreNLP 4.5.10、12 个 pattern、六字段顺序与 synthetic live fixtures 已验证，但未做真实数据训练或评价 | VERIFIED_PROJECT_FACT | experiment contract、S2.5 runtime manifest、机器门禁 | 只能写合同/合成验证事实；禁止写真实性能 | S2.6/S2.10 formal manifests |
| C29 | S2.4 Legal-BERT + TextCNN 已完成训练、dev 选择与唯一一次 test 评价；运行 `s24_legal_bert_textcnn_seed20260717_v1` 的 test n=426、accuracy=0.924883、macro-F1=0.851071 | VERIFIED_PROJECT_FACT | versioned S2.4 run manifest、checkpoint/config exact hashes、机器门禁 | 可写 development 分类器组件聚合结果；不得写成 Sun original split、完整 Stage 2 正式结果或显式权利人许可 | S2.10 formal evaluation |
| C30 | H1 只依据推理时可见 trigger 制定 field-level repair plan；Gold/test-derived telemetry 会 fail closed | VERIFIED_PROJECT_FACT | `sun_h1_s28.json`、`h1_selective.py`、S2.8 tests/gate | 可写选择与合并实现已验证；不能写 LLM 已改善结果或降低实际成本 | 真实调用授权 + S2.10 |
| C31 | D1 的离线方法合同已验证：不运行 B0/H1 或读取 Gold；v4 actual prompt 完整插入 4 个 few-shot；直接生成同一 canonical Rule Record；invalid/API error 保留在失败统计中 | VERIFIED_PROJECT_FACT | `sun_d1_s29.json`、prompt v4、implementation、synthetic manifest、S2.9 exact-hash gate | 可写输入隔离、prompt/model/budget/失败合同已验证；不能写真实调用、稳定性观察值或性能 | S2.2 + 真实调用授权 + S2.10 formal manifest |
| C32 | Sun modality raw source 为 2,833 行；精确冲突组 2 行被预结果隔离后，主分析集为 2,831 行，分布 1190/1273/264/104 | VERIFIED_PROJECT_FACT | S2.1 manifest、quarantine manifest、独立 machine gate | 可写数据治理事实；不得称标签被纠正 | 若合同变更需新事件与 manifest |
| C33 | 项目重建的 group-aware split 为 1985/420/426，seed=20260715，normalized-text leakage=0；它不是 Sun original split | VERIFIED_PROJECT_FACT | S2.1 split summary、membership hash、重放验证、S2.4 run manifest | 可写 verified development split 与已运行的 S2.4 组件评价；不得称 Sun original split 或完整 Stage 2 正式评价 | S2.10 formal manifest |
| C34 | 项目只有一个固定 EStG-150 membership，五层数据是同一 150 的不同处理层，不是五个数据集 | VERIFIED_PROJECT_FACT | `ESTG150_DATA_MAP.md`、membership hash、human review contract | 已固定；禁止重抽样或平行 Gold | membership hash 永久不变 |
| C35 | EStG-150 采用只读 A–D 层与唯一可编辑人工 E 层；LLM 候选不等于批准，最终名称必须披露 LLM assistance | VERIFIED_PROJECT_FACT | `HUMAN_GOLD_GUIDE.md`、review schema/tool/validator | 可描述协议；不能称纯人工 Gold | S2.2 后回填最终决策统计 |
| C36 | 当前 Layer E format-valid 但为 0/150 reviewed/adjudicated、0/900 六字段决定；input-ready 不等于 freeze/publication-ready | VERIFIED_PROJECT_FACT | 2026-07-17 validator 与项目审计快照 | 仅作当前状态；论文定稿前必须刷新 | S2.2 + route/data/stage3 重锁 |
| C37 | complexity bins 已由 G0.5 在查看 test 结果前冻结；复杂法律语料的 membership 与标签映射仍将在 S2.11 冻结 | VERIFIED_PROJECT_FACT / PLANNED_METHOD | G0.5 config/manifest/gate、S2.11 主 Pipeline | 可写 bins/泄漏防护已验证；不能声称已有复杂集或退化趋势 | S2.11 |
| C38 | Stage 2 evaluator 已冻结 clause 单位四类 support/P/R/F1、Macro-F1、confusion matrix，以及五类 phrase 的 exact/token-overlap micro/macro | VERIFIED_PROJECT_FACT | `stage2_evaluator_s210.json`、implementation、synthetic manifest、exact-hash gate | 可写 evaluator 合同已实现；synthetic 常数不能写成方法性能 | S2.10 formal result manifests |
| C39 | 完整记录 evaluator 已冻结 coverage、hallucination、schema-valid、unsupported、invalid/API-error、edge 与成本指标，且只把 TP/union 称为 Jaccard/IoU | VERIFIED_PROJECT_FACT | S2.10 config/report schema/implementation/manifest | 可写指标与失败分母已验证；不能提前写任何方法观察结果 | S2.10 formal result manifests |
| C40 | strict、`safe-legal-v1` normalization-aware 与人工 style-equivalent 已实现为不同评价视角；人工模板禁止自动填值，高风险 loose 规则未进入冻结 evaluator | VERIFIED_PROJECT_FACT | `STYLE_EQUIVALENT_SPEC.md`、style schema、S2.10 manifest/gate | 可写合同与 synthetic 验证；不得把自动 normalization 称人工 style-equivalent 或声称已有人工分布 | 正式预测后的人工 style review |
| C41 | Stage 2 主方法比较使用共享 sample IDs 的 paired design；S2.12-P 已在正式结果前冻结 sample_id cluster、10,000 次 bootstrap、10,000 次 sign-swap、每数据轨道 12 假设 Holm family 与 D1 primary-repeat 边界 | VERIFIED_PROJECT_FACT | `s212_analysis_protocol.json`、synthetic manifest、S2.12-P exact-hash gate、本稿 §6.4 | 可写统计合同已冻结；不能写已有显著性、退化趋势或方法优劣 | S2.12 formal manifests；Stage 3 另在 S3.7 冻结 |
| C42 | formal runner 在 final-ready=false 时拒绝执行，真实 LLM 还需要显式授权与硬调用预算 | VERIFIED_PROJECT_FACT | `run_formal_pipeline.py`、REPRODUCTION_PROTOCOL、机器审计 | 可描述运行门禁；不能据此声称方法已运行 | final-ready + 用户真实调用授权 |
| C43 | 结果章当前只有空表、图规范和 provenance 登记；任何数字必须由 experiment_run 事件与 formal manifest 解锁 | VERIFIED_PROJECT_FACT | `THESIS_DRAFT.md` §7、paper README、变更事件 | 可称模板已完成；不得把 `—`/BLOCKED 替换为 development 数字 | PW7/PW8 对应 formal manifests |
| C44 | S2.6 已加载 exact S2.4 checkpoint，并消费 attested S2.5 live phrase observations，按德文分类/对齐英文抽取路由生成 1 条 schema-valid canonical B0 record；invalid=0、无 LLM、无 Gold、未重评 test | VERIFIED_PROJECT_FACT | `s26_sun_b0_canonical_composition_v3.manifest.json`、S2.6 exact-hash gate | 可写组件接口与 no-LLM 技术验证；禁止写 phrase accuracy、真实数据性能或正式主表结果 | S2.10 formal manifest |
| C45 | S2.8 已把 H1 重基到 verified S2.6 B0，锁定推理时 trigger、字段依赖闭包、完整 Chat Completions 请求体、固定 gpt-4.1 快照、按 sample/clause 排序的 45-call 分配、46.08 万 token/1.5 USD 上限，以及 provider error 后保持 H1 身份且可计分的 B0 回退；dry-run 未调用真实 LLM、未读 Gold/test、未评价性能 | VERIFIED_PROJECT_FACT | `s28_sun_h1_selective_dry_run_v5.manifest.json`、S2.8 exact-hash gate、S2.10-E v2 | 可写 preregistration/request/merge/budget/failure-accounting 技术事实；禁止写质量、实际成本收益或正式结果 | 真实调用授权 + S2.10 formal manifest |
| C46 | G0.5 已冻结文本 11/BPMN 12 个方法无关复杂度指标及固定 low/medium/high bins；模型预测、test 结果和事后改 bin 均 fail closed | VERIFIED_PROJECT_FACT | `g05_complexity_contract_synthetic_v1.manifest.json`、G0.5 exact-hash gate | 可写合同和 synthetic 验证；不能写复杂数据已冻结或存在性能退化趋势 | S2.11/S2.12 formal manifests |
| C52 | 设计时合规检查的主要传统路线包括形式逻辑、合规模式以及 LegalRuleML/专用检查器等混合方法；其共同前提通常是先获得形式化约束 | VERIFIED_PRIMARY_SOURCE | Governatori and Rotolo (2010)、Montali et al. (2014)、Elgammal et al. (2016)、Governatori et al. (2016)；Sun §2 作引用导航 | 可描述方法分类、形式语义与人工形式化边界；不能把二手概括当实验结果 | 投稿前核对各原论文页码与参考文献格式 |
| C53 | 流程文本 NLP 可抽取活动、参与者和控制流并支持文本—BPMN 一致性，但其输入与法规的模态、条件、约束和例外抽取不同 | VERIFIED_PRIMARY_SOURCE | Sánchez-Ferreres et al. (2019)、Delicado Alcántara et al. (2017)、van der Aa et al. (2019)；Sun §2 作引用导航 | 可作为 Stage 1/3 背景；不能写成已解决本文完整 Stage 2 | 投稿前核对原论文页码 |
| C54 | Selective classification 以覆盖率换取被保留预测上的风险控制，为“基础方法不确定时拒绝或升级”提供理论背景 | VERIFIED_PRIMARY_SOURCE | Geifman and El-Yaniv (2017)，NeurIPS 30 官方论文 | 一般现在时；不能据此声称 H1 已有风险保证 | NeurIPS 2017 官方版本 |
| C55 | FrugalGPT 的 LLM cascade 在前级响应不可靠时继续调用后续模型；RouteLLM 学习在强弱 LLM 间路由以权衡质量和成本 | VERIFIED_PRIMARY_SOURCE | Chen et al. (2023), arXiv:2305.05176；Ong et al. (2024), arXiv:2406.18665 | 只描述查询级 cascade/routing；不得把其结果迁移为 H1 结果 | 对应原论文与正式参考文献条目 |
| C56 | H1 借鉴选择性升级思想，但采用完整 B0 优先、推理可见 trigger、字段级 repair/merge 和失败回退，而非多个 LLM 间的查询级路由 | VERIFIED_PROJECT_FACT | S2.8 config、implementation、dry-run manifest；与 C54/C55 原论文的方法边界对照 | 可描述架构差异；禁止声称质量或成本收益已经观察到 | 真实调用授权 + S2.10 formal manifest |
| C57 | S2.7-M 在与 S2.4 相同的项目重建 split 上完成三个非 LLM modality component baseline；test accuracy/macro-F1：majority 0.457746/0.157005、固定德文 keyword 0.483568/0.414154、word 1–2 gram Multinomial NB 0.784038/0.568849 | VERIFIED_PROJECT_COMPONENT_RESULT | versioned aggregate manifest、config/implementation exact hashes、S2.7-M gate；manifest 披露一次同配置未版本化 test smoke且无 test 选参 | 只能写重建 split 的 aggregate modality component 结果；不得称 Sun original split、完整 Stage 2、phrase 结果或 H1/D1 比较 | S2.2 phrase Gold + S2.7-P/S2.10 formal manifests |
| C51 | S2.11 已从官方 CELEX 32016R0679 英语 Formex XML 在结果前确定性锁定 50 条复杂法律输入，覆盖 GDPR Articles 5–50 全部 46 个 Article；旧 gdpr50 规则自动标注未导入 | VERIFIED_PROJECT_FACT | `gdpr_articles_5_50_s211.json`、membership hash、S2.11 manifest/exact-hash gate、EUR-Lex reuse evidence | 可写来源、选择算法、50 条 membership 和空白人工协议已验证；不能写语义 Gold、复杂度分布或方法表现已完成 | 复杂集 50/50 人工裁决 + S2.12 formal manifest |
| C58 | S2.12-P 已冻结 G0.5 fixed strata、主/次指标边界、错误多标签与主类优先级、n<10 小分层规则，以及每数据集×方法×主错误类按 SHA-256 固定选 3 个质性案例 | VERIFIED_PROJECT_FACT | `s212_analysis_protocol.json`、`s212_analysis.py`、synthetic manifest、exact-hash gate | 可写分析设计与 fail-closed 规则已验证；synthetic 点估计/p 值不得写成性能，不能声称正式 error distribution 已产生 | EStG 150/150 + GDPR 50/50 + S2.12 formal manifests |
| C59 | S1.1/S1.2/S1.4 已冻结 `process_record@1.0.0`，并在两个 synthetic BPMN 上验证 pool/lane/activity/event/gateway/flow 解析、direct/transitive reachability、activity order、branch/parallel、cycle 与 unreachable-node 语义 | VERIFIED_PROJECT_FACT | `stage1_structural_s11_s14.json`、`stage1_process.py`、`s11_s14_stage1_structural_synthetic_v1.manifest.json`、exact-hash gate | 可写结构合同与 synthetic 技术验证；不得写正式 BPMN accuracy 或完整 Stage 1 已完成 | S1.5–S1.7 formal manifests |
| C60 | S1.3 已冻结 P0 raw-only/no-inference 与 P1 fixed surface-split 标签合同，并在 6 个 synthetic activities 上验证单泳道 actor、首词 action、余文 object 以及 empty/punctuation/no-lane/ambiguous-lane 状态 | VERIFIED_PROJECT_FACT | `stage1_label_semantics_s13.json`、schema/implementation、`s13_stage1_label_semantics_synthetic_v1.manifest.json`、exact-hash gate | 可写方法规则和 synthetic 技术验证；不得声称语言学正确性、P2、正式 BPMN precision/recall 或性能优势 | S1.5–S1.7 formal manifests |
| C61 | S1.5 已冻结 blank human-annotation schema、source/activity context binding、label field state machine 与 freeze rules；synthetic pack 为 1 process/6 activities/18 unresolved fields、0 Gold、freeze=false | VERIFIED_PROJECT_FACT | `stage1_annotation_protocol_s15.json`、human annotation schema/guide/validator、`s15_stage1_annotation_protocol_synthetic_v1.manifest.json`、exact-hash gate | 可写人工协议和当前 blocker；不得声称正式 BPMN membership、人工 Gold 或 Stage 1 performance 已完成 | 用户批准 provenance BPMN 提升 + 人工 adjudication + S1.6/S1.7 manifests |
| C62 | S1.6 已冻结 exact membership、8 类结构 set metrics、3 字段 exact-value metrics、activity triple accuracy、coverage 及 terminal/invalid 分母，并拒绝未解锁 formal scope | VERIFIED_PROJECT_FACT | `stage1_evaluator_s16.json`、report schema/implementation、`s16_stage1_evaluator_contract_synthetic_v1.manifest.json`、exact-hash gate | 可写评价定义与 synthetic 算术验证；synthetic 数值不得写成方法性能 | S1.5 formal membership/Gold + S1.7 formal manifests |

新增任何结果性句子前，先在本表新增一行。正式回填必须记录 manifest 路径、事件
时间、样本数、失败数、模型和 evaluator 版本；否则维持 `BLOCKED_RESULT`。
