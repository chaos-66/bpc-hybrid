# 科学主张—证据矩阵

**状态**：活动写作控制表  
**当前正式实验结果**：0；任何性能结论均保持 `BLOCKED_RESULT`

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
| C07 | B0、H1、D1 将共享 IDs/Gold/schema/normalization/evaluator | PLANNED_METHOD | contract、methods registry | 将/计划；不能写已完成比较 | S2.10/S2.13 |
| C08 | 复杂法律语料可能放大传统方法与 LLM 的差异 | PLANNED_METHOD | RQ2、导师要求 | “待检验假设”，不能写既定事实 | G0.5、S2.11、S2.12 |
| C09 | H1 只在预注册失败/不确定字段调用 LLM | PLANNED_METHOD | STAGE2_LLM_INNOVATION_DESIGN | 将/计划 | S2.8 + 真实调用授权 |
| C10 | LLM/Hybrid 优于完整 B0 | BLOCKED_RESULT | 当前无正式结果（development 证据：D1-R3 细 Gold F1 0.7756 vs B0-R3 0.7186，同 Gold 同口径非正式；粗 Gold 0.8726 vs 0.7986，见 outputs/reports/b0_d1_experiment_closure_brief.md） | 禁止比较词（formal 层面）；development 证据可单独标注引用 | S2.10/S2.12 formal manifest |
| C11 | LLM 在复杂法律语料上优势更明显 | BLOCKED_RESULT | 当前无冻结复杂集或结果 | 禁止结论 | S2.11/S2.12 formal manifest |
| C12 | Stage 3 改进带来 Oracle 提升 | BLOCKED_RESULT | 当前只有 scaffold | 禁止结论 | S3.7 formal manifest |
| C13 | Stage 2/3 改进带来端到端提升 | BLOCKED_RESULT | 当前未完成两阶段冻结 | 禁止结论 | E00/E10/E01/E11 manifests |
| C14 | 当前 heuristic runner 是完整 Sun baseline | PROHIBITED_CLAIM | 与 methods registry 冲突 | 只能称 development heuristic | 永不直接转为允许；需 S2.6 新实现 |
| C15 | EStG-150 是 Sun 原始 150/443 spans | PROHIBITED_CLAIM | 与 membership 决策冲突 | 必须称项目独立重建 benchmark | 永不允许 |
| C16 | Gold 是纯人工或从零人工标注 | PROHIBITED_CLAIM | Layer C 为 LLM 候选 | 必须披露 LLM assistance | 永不允许 |
| C17 | Barrientos 已实现 Sun 六要素或标签完全兼容 | PROHIBITED_CLAIM | schema/modality 不同 | 只能写工程借鉴与显式 adapter | 永不允许 |
| C18 | Stage 2 与 Stage 3 或不同数据的数字可直接证明优劣 | PROHIBITED_CLAIM | C1–C4 比较合同 | 必须分表并标证据等级 | 永不允许 |
| C19 | B0/D1 的低分主要由标注粒度与 constraint 定义口径差异解释（归因证据） | VERIFIED_PROJECT_FACT | 句子级粗 Gold：B0 F1 0.7186→0.7986、D1 0.7756→0.8726（同一粗 Gold，sha 6e19cf3c）；Sun-marker 收敛：B0 constraint R 1.0 (13/13)、condition R 0.989 (91/92)。产物 `outputs/development/s27_b0_coarse_gold_cc_v1/`、`s27_b0_coarse_gold_sentence_granularity_v1/`、`s27_d1_coarse_gold_sentence_granularity_v1/`；汇总 `outputs/reports/b0_d1_experiment_closure_brief.md` | 只写"development/attribution 证据表明粒度与定义口径影响显著"；不得改写为正式结论或"方法已达 Sun 水平"；marker 收敛仅支持 R 侧结论 | 正式 Gold 冻结后复核 |

新增任何结果性句子前，先在本表新增一行。正式回填必须记录 manifest 路径、事件
时间、样本数、失败数、模型和 evaluator 版本；否则维持 `BLOCKED_RESULT`。

