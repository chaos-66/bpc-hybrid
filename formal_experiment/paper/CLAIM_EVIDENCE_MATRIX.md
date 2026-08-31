# 科学主张—证据矩阵

**状态**：活动写作控制表  
**当前正式实验结果**：三方法正式比较已发布（2026-08-11，`stage2_formal_three_method_comparison_v1` 与 `stage2_formal_conclusion_v1`）；性能结论仅限正式报告中字段级描述性结论，禁止显著性推断

状态只使用：`VERIFIED_PRIMARY_SOURCE`、`VERIFIED_PROJECT_FACT`、
`PLANNED_METHOD`、`BLOCKED_RESULT`、`PROHIBITED_CLAIM`。

| ID | 论文主张 | 状态 | 当前证据 | 允许时态/表述 | 解锁任务或正式来源 |
|---|---|---|---|---|---|
| C01 | Sun 的完整方法由 Stage 1/2/3 构成 | VERIFIED_PRIMARY_SOURCE | Sun 最终版；`docs/research/SUN_FINAL_VERSION_AND_DATA_AUDIT.md` 作导航 | 一般现在时；正式引用回到原论文 | `[[TODO-SOURCE:SUN2024:核对章节/页码]]` |
| C02 | Sun Stage 2 最终版使用 BERT-TextCNN 与 CoreNLP/Tregex/Tsurgeon | VERIFIED_PRIMARY_SOURCE | 机器合同和 Sun 证据导航 | 一般现在时；不能说本项目已完成 | `[[TODO-SOURCE:SUN2024:核对方法页码]]` |
| C03 | 本项目进行独立、可审计的 paper-faithful reconstruction | VERIFIED_PROJECT_FACT | contract、主 Pipeline | “目标/实施路线是”；不能写 exact/original | S2.6 后回填完成状态 |
| C04 | 工作区没有 Sun 完整 Stage 2 源码、权重、完整 marker 和原始 150 phrase Gold | VERIFIED_PROJECT_FACT | 项目研究证据和机器 blocker | 作为复现边界与局限 | 投稿前再核查资产 |
| C05 | 项目只有一个固定 EStG-150 membership | VERIFIED_PROJECT_FACT | membership hash、ROUTE_LOCK | 已固定；不是 Sun 原始 150 | hash 不得变 |
| C06 | 项目 Gold 采用五层 LLM-assisted、human-adjudicated 流程 | VERIFIED_PROJECT_FACT | AGENTS、HUMAN_GOLD_GUIDE、contract | 可写流程；150/150 adjudicated（2026-08-06 用户裁决经授权恢复并验证，freeze_ready=True） | 已完成（150/150 adjudicated，freeze_ready=True；formal Gold 发布仍待 route/data/stage3 重锁） |
| C07 | Rules-Only、Direct-LLM、Rules+LLM-Repair 已共享 IDs/Gold/schema/normalization/evaluator 并完成正式比较 | VERIFIED_PROJECT_FACT | 三方法 formal capsules（b0_formal_arm_v1 / direct_llm_formal_arm_v1 / sun_llm_fallback_formal_arm_v1，独立 verifier 全过）；shared comparison capsule `outputs/evidence/d1_h1_zero_api_reeval_v1/comparison_capsule.json`；正式报告 `outputs/reports/stage2_formal_three_method_comparison_v1.json` | 可写"三方法在冻结输入/Gold/合同/evaluators 上完成正式比较"；不得超出报告字段级结论 | S2.10 verified（2026-08-11） |
| C08 | 复杂法律语料可能放大传统方法与 LLM 的差异 | PLANNED_METHOD | RQ2、导师要求 | “待检验假设”，不能写既定事实 | G0.5、S2.11、S2.12 |
| C09 | Rules+LLM-Repair 是负结果对照，保留为 comparison-only 且停止优化（正式比较确认净负） | VERIFIED_PROJECT_FACT | development 负结果（commit `74614e3`，§8.8.1）+ 正式比较确认 （`stage2_formal_three_method_comparison_v1.json`：actor 粗 F1 0.4296 vs Rules-Only 0.8203；`stage2_formal_conclusion_v1.json` H1 comparison-only 结论） | 仅写对照臂/负结果；不得写成可优化主方法 | 已完成（comparison-only 正式结论，2026-08-11） |
| C10 | LLM/Hybrid 优于完整 B0 | BLOCKED_RESULT | 当前无正式结果（development 证据：D1-R3 细 Gold F1 0.7756 vs B0-R3 0.7186，同 Gold 同口径非正式；粗 Gold 0.8726 vs 0.7986，见 outputs/reports/b0_d1_experiment_closure_brief.md） | 禁止比较词（formal 层面）；development 证据可单独标注引用 | S2.10/S2.12 formal manifest |
| C11 | LLM 在复杂法律语料上优势更明显 | BLOCKED_RESULT | 当前无冻结复杂集或结果 | 禁止结论 | S2.11/S2.12 formal manifest |
| C12 | Stage 3 改进带来 Oracle 提升 | BLOCKED_RESULT | 当前只有 scaffold | 禁止结论 | S3.7 formal manifest |
| C13 | Stage 2/3 改进带来端到端提升 | BLOCKED_RESULT | 当前未完成两阶段冻结 | 禁止结论 | E00/E10/E01/E11 manifests |
| C14 | 当前 heuristic runner 是完整 Sun baseline | PROHIBITED_CLAIM | 与 methods registry 冲突 | 只能称 development heuristic | 永不直接转为允许；需 S2.6 新实现 |
| C15 | EStG-150 是 Sun 原始 150/443 spans | PROHIBITED_CLAIM | 与 membership 决策冲突 | 必须称项目独立重建 benchmark | 永不允许 |
| C16 | Gold 是纯人工或从零人工标注 | PROHIBITED_CLAIM | Layer C 为 LLM 候选 | 必须披露 LLM assistance | 永不允许 |
| C17 | Barrientos 已实现 Sun 六要素或标签完全兼容 | PROHIBITED_CLAIM | schema/modality 不同 | 只能写工程借鉴与显式 adapter | 永不允许 |
| C18 | Stage 2 与 Stage 3 或不同数据的数字可直接证明优劣 | PROHIBITED_CLAIM | C1–C4 比较合同 | 必须分表并标证据等级 | 永不允许 |
| C19 | B0/D1 的低分主要由标注粒度与 constraint 定义口径差异解释（归因证据） | VERIFIED_PROJECT_FACT | 句子级粗 Gold（主口径，2026-08-07 用户决策对齐 Sun 粒度）：B0 F1 0.7186→0.7986、D1 0.7756→0.8726（同一粗 Gold，sha 6e19cf3c）；Sun-marker 收敛：B0 constraint R 1.0 (13/13)、condition R 0.989 (91/92)。产物 `outputs/development/s27_b0_coarse_gold_cc_v1/`、`s27_b0_coarse_gold_sentence_granularity_v1/`、`s27_d1_coarse_gold_sentence_granularity_v1/`；汇总 `outputs/reports/b0_d1_experiment_closure_brief.md` | 只写"development/attribution 证据表明粒度与定义口径影响显著"；不得改写为正式结论或"方法已达 Sun 水平"；marker 收敛仅支持 R 侧结论 | 正式 Gold 冻结后复核 |
| C20 | Winter et al. (2020) Stage 3 baseline 已有 development 实现与可移植重放（S3.4） | VERIFIED_PROJECT_FACT | `src/bpc_hybrid/winter_stage3/`（Winter 原型语义转写：spaCy 匹配、gamma 0.4/delta 0.8、fitness/cost 三分量）；clean replay `outputs/development/s34_winter_stage3_development_v2_clean/` + prototype_literal 敏感性（reachability 双模式，本数据无差异）；DEV_ONLY：MAP 0.6429、violation macro F1 0.373；manifest 1.1.0（implementation hashes/export index/external prerequisites） | 只能写"Winter baseline 已有 development 实现与 DEV_ONLY 指标"；不得把 DEV_ONLY 数字写成正式比较或 Stage 3 结论 | formal Oracle（S3.7）与正式 Gold 门禁 |
| C21 | Stage 3 matching/violation Gold 标注已冻结（用户裁决） | VERIFIED_PROJECT_FACT | `data/development/human_review/stage3_gold_annotation_human_correction_v1.json`（25 matching=11 相关/14 不相关；33 violation=三类各 11）；冻结 manifest `s32_s33_gold_annotation_freeze_v1.manifest.json` | 可写"Stage 3 Gold 标注已冻结（LLM 无关、用户裁决）"；正式 Gold 发布仍待 stage3.status 合同门禁 | stage3.status 重锁 + publication gate 白名单 |
| C22 | Sun et al. (2024) Stage 3 已有方法级独立 development 重建（S3.5，Def 4-7） | VERIFIED_PROJECT_FACT | `src/bpc_hybrid/sun_stage3/`（matching=Def4、missing action=Def5、incorrect actor=Def6、out-of-order=Def7；tau/gamma/theta=0.8 预注册）；58 条 run `outputs/development/s35_sun_stage3_development_v1/`（DEV_ONLY：MAP 0.8175、violation macro F1 0.333）；与 Winter 同口径比较 `comparison_with_winter_dev.json` | 只能写"Sun Stage 3 方法级独立重建已有 development 实现与 DEV_ONLY 指标"；禁止 exact reproduction/Sun original/paper-faithful（除非逐项验证全部公开规则）；不得把 DEV_ONLY 写成正式结论 | formal Oracle（S3.7）与正式 Gold 门禁 |

| C23 | 三方法正式比较结论：Direct-LLM 在 action/condition/constraint 与 modality label accuracy 领先；Rules-Only 在 actor/exception 领先；字段级互补、无整体胜者声明 | VERIFIED_PROJECT_FACT | 正式报告 `outputs/reports/stage2_formal_three_method_comparison_v1.json`（c9d76544…）+ manifest（dc41eb4b…）；G0.4 授权口径（粗五字段 + modality label 单独；modality evidence-span unavailable；历史六字段 aggregate 不引用）；数据规模 150 句；历史调用 300、新增 0 | 只写"正式比较（描述性）表明字段级差异"；禁止显著性推断；禁止把 Rules-Only 称为 Sun 原始实现或 exact reproduction | 已完成（S2.10 verified；B0-R5/D1-R5 结论包 `stage2_formal_conclusion_v1.json` d882a5e2…） |
| C24 | B0-R5/D1-R5 正式结论已形成（方法级独立复现；结果可正可负、描述性披露） | VERIFIED_PROJECT_FACT | `outputs/reports/stage2_formal_conclusion_v1.json`（d882a5e2…）+ verifier（16fd36f5… VERIFIED）；重建披露（paper-faithful independent reconstruction、非 exact reproduction）、数据规模、调用成本、无显著性推断均已记录 | 按结论包表述写作；每条结论回指报告/manifest/hash；不得把 H1 写成主方法 | 已完成（2026-08-11）；论文正式回填时对照 manifest 复核 |

| C25 | 正式三方法比较的字段级数字已按命名迁移写入论文 §7.2（粗 Gold 五字段主视图 + modality label 分表） | VERIFIED_PROJECT_FACT | `outputs/reports/stage2_formal_three_method_comparison_v1.json`（report c9d76544…、manifest dc41eb4b…）；论文 §7.2 表（Rules-Only actor 0.8203/action 0.8927/condition 0.7738/constraint 0.6182/exception 0.88、mean 0.797；Direct-LLM 0.7579/0.9437/0.8380/0.7427/0.7619、mean 0.8088；Rules+LLM-Repair 0.4296/0.8945/0.7774/0.6200/0.88、mean 0.7203；modality label acc 0.74/0.8333/0.82） | 只写“正式比较（描述性）表明字段级差异”；禁止显著性推断；modality evidence-span unavailable 不置零 | 已完成（2026-08-11 formal 报告；论文 §7.2 回填） |
| C26 | 论文方法章节按细模块撰写（Direct-LLM 8 模块、Rules-Only 8 模块、Rules+LLM-Repair 负结果、Barrientos 15 维对比表） | PLANNED_METHOD | `paper/THESIS_DRAFT.md` §4 已按 `MASTER_PIPELINE.md` §8.8.4 骨架撰写；每个模块含问题/输入输出不变量/去掉的失败/验证方式/与 Barrientos 对照 | 写作层面可写“方法按模块分解”；**不得**写“模块有效性已验证”（待 AB-1–AB-10 正式消融） | 写作完成（2026-08-20）；模块有效性待消融数据 |
| C27 | AB-1–AB-10 消融矩阵已登记现状表（含已有历史证据与待运行/待授权状态） | VERIFIED_PROJECT_FACT（仅指“状态登记”，不含未跑数字） | `paper/ABLATION_MATRIX.md`；已有历史证据：AB-1 v5→v6（constraint R 0.2881→0.4172）、AB-6（D1-R1/R3 150/150 有效 0 事故）、AB-7（细 0.7186/0.7756、粗 0.7986/0.8726、Sun-marker 收敛）、AB-8（B0-R1 各批次）；AB-3 离线可评（def=39/231）、AB-5 设计+历史证据、AB-9/AB-10 待授权/待实现 | 已登记项可引用“仅已有历史证据”；未跑项必须标“待运行/待授权”，不得补造 | 状态登记完成（2026-08-20）；正式消融数据待 API 授权 |
| C28 | Barrientos 2026 三类证据分层（论文自动实验 / 专家标注协议 / 本文适配指标）写入论文 §2.4，不与“20×20 重跑”混淆 | VERIFIED_PRIMARY_SOURCE | `docs/research/BARRIENTOS_BORROWING_AUDIT_2026-07-12.md`（2026-08-20 原文复核）+ 论文 §2.4 + `docs/research/BARRIENTOS_LLM_ROLE.md`；正确事实：36 条×5 次完整运行、80 annotations 为专家标注、κ=0.52 为专家 NC/OC/NE 一致性 | 论文可写“36 条×5 次完整流程独立运行”“20 requirements × 2 versions × 2 experts = 80 annotations” | 已完成（2026-07-12 审计 + 2026-08-20 纠正；论文 §2.4 回填） |
| C29 | S3.9-EXT 四类扩展按六要素未覆盖字段选择：禁止动作、条件未落实、约束违反、例外未处理 | VERIFIED_PROJECT_FACT（仅 development controlled extension） | `scripts/run_s3_extended_violation_panel_v2.py` 的 `SELECTION_RATIONALE`；`outputs/reports/s3_extended_violation_comparison_v2.{json,md}`；论文 §7.4 | 可写“四类是最小字段覆盖扩展，并分别消费 modality+action / condition / constraint / exception”；必须同时写 DEV_ONLY、非穷尽分类、未改变三类人工 Gold/正式 Oracle | S3.9-EXT 已完成；不得据此声称七类正式 benchmark 或真实场景泛化 |

新增任何结果性句子前，先在本表新增一行。正式回填必须记录 manifest 路径、事件
时间、样本数、失败数、模型和 evaluator 版本；否则维持 `BLOCKED_RESULT`。
