# B0 / D1 实验收口材料（development / attribution / fixed-snapshot）

**生成日期**：2026-08-07
**定位**：为导师汇报与论文草稿提供可追溯证据的收口 brief；**不涉及 H1 路线选择**。
**口径声明**：本文全部数字为 development / attribution / fixed-snapshot 结果，
来自 56d2b03 历史 Layer E 构建的 canonical Gold（150 条 / 1055 spans）与固定预测快照，
**不是 final formal result**。正式结论仍待 formal Gold publication / shared capsule /
Stage 3 gate。B0 只能表述为 `method-level independent reconstruction`；Gold 只能表述为
项目独立构建的 `LLM-assisted, human-adjudicated EStG-150 benchmark`。

相关 commit：`40a0262`（Sun Table-4 marker 收敛归因）、`4611337`（B0 句子级粗 Gold 归因）、
`7899fd9`（D1 句子级粗 Gold 归因）。

---

## 一、B0/D1 当前状态摘要

### B0（sun_rule_only，规则方法）

- **已收口**：确定性代码错误已修（B0-R1 七个子批次闭环，ACTION/ALIGN/ACTOR/BRIDGE/
  LEXICON-DECISION 正向或持平、SCOPE-DISAMBIG 实测负结果已记局限、CLAUSE-REVIEW 不改动）；
  方法级一致性 `verified_method_level_independent_reconstruction`（2026-08-04 用户授权，
  非 exact reproduction）。
- **主口径**（细 Gold，1055 spans）：**F1 0.71865（P 0.6845 / R 0.7564）**，
  用户条件授权为论文依据候选。
- **低分解释（归因实验，两路互补）**：
  1. 句子级粗 Gold（609 spans）：F1 0.7986（P 0.7309 / R 0.8801）——我们的 Gold 比 Sun
     更细（clause 级 7.0 spans/句 vs Sun 句子级 ~2.95），细粒度标注是 P/R 的主要负担；
  2. Sun Table-4 marker 收敛（constraint 302→13、condition 214→92）：constraint R 1.000
     (13/13)、condition R 0.989 (91/92)——我们的 constraint 定义范围比 Sun 宽约 8-23 倍，
     低分根源是定义口径差异。
- **剩余局限**：condition/constraint 字段边界（规则层不可安全消歧）、constraint 定义范围
  差异、规则方法的字段归属天花板（残余错误以"压到别的字段"为主）。

### D1（direct_llm，纯 LLM）

- **已收口**：v6 prompt 配方锁定（D1-R2，`configs/models/estg150_d1_active_registry_v1.json`，
  deepseek-v4-pro / temp0 / top_p1 / max_tokens4096 / thinking-disabled / 无 json_object）；
  R3 固定快照干净重跑复现成功（D1-R3 verified，150/150 有效、0 事故）。
- **主口径**（细 Gold）：**F1 0.7756（P 0.8793 / R 0.6938）**；句子级粗 Gold：
  **F1 0.8726（P 0.9012 / R 0.8456）**。
- **当前领先但仍有短板**：constraint 仍是最大错误源（R3 中 302 个 Gold span 有 100 个
  wrong_field、69 个 not_extracted）；actor 存在泛指主语误抽（P 侧历史 0.594）；整体偏
  保守漏抽（not_extracted 154）。

---

## 二、B0 结果证据表

| 项 | 数值 | 证据路径（formal_experiment/ 内，均 tracked） |
|---|---|---|
| 细 Gold P/R/F1（主口径） | 0.6845 / 0.7564 / **0.7186** | `outputs/development/s27_b0_coarse_gold_sentence_granularity_v1/report.json`（fine_metrics）；预测源 `outputs/development/s27_estg150_b0_enhanced_v10a_r2_r3_lex_hist56d_v1/b0_attempts.json`；分析 `docs/B0_ERROR_ANALYSIS.md` §1.1/§8 |
| 句子级粗 Gold P/R/F1 | 0.7309 / 0.8801 / **0.7986** | `outputs/development/s27_b0_coarse_gold_sentence_granularity_v1/report.json`（coarse_metrics，粗 Gold 语义 sha `6e19cf3c…`）；脚本 `scripts/coarse_gold_b0_sentence_granularity_v1.py`；commit `4611337` |
| Sun-marker condition R | **0.989（91/92）** | `outputs/development/s27_b0_coarse_gold_cc_v1/report.json`；脚本 `scripts/coarse_gold_b0_condition_constraint_v1.py`；`docs/B0_ERROR_ANALYSIS.md` §10；commit `40a0262` |
| Sun-marker constraint R | **1.000（13/13）** | 同上（P 侧不可解读：单边收敛设计，收敛后 Gold 13 个 vs 预测数百个） |
| 已修：action span 吞并 | 主口径持平；主语开头 action 8→0；strict-exact 3.0× | `docs/B0_ERROR_ANALYSIS.md` §5-C1；产物 `outputs/development/s27_estg150_b0_enhanced_v10a_r1b_actionfix_hist56d_v1/` |
| 已修：actor 漏抽 | **主口径 F1 +0.0018**；actor F1 0.616→0.670；8/8 找回 | §5-C4；产物 `…r1b_actor_hist56d_v2/` |
| 已修：德英 cue 校验（伪 validated） | validated 107→49；主口径不变；label 面板 −0.48pp（记录代价） | §5-C3；产物 `…r1b_align_hist56d_v1/` |
| 实测拒绝：scope-disambig | 候选 F1 −0.0005，回退，记方法局限 | §5-C2；负面证据 `…r1b_scope_disambig_hist56d_v1/` |
| 已实施：LEXICON-DECISION（13 名词授权） | 词典覆盖 47/48 actor：P 0.692 / R 0.979 / F1 0.811；未覆盖 1/48（代词 "It"，待正式 Gold 裁决） | §1.1-LEXICON 行；sources manifest（source `authorized_local_frozen_estg150_gap_2026_08_04`） |
| 剩余局限 | constraint 143 missed（107 在别字段）+ 178 misclassified（152 压别字段）；marker 归因：only 17 / under 12+8 / pursuant to 11 / within the meaning 8+3 | §8.1/§8.2；C2 cue 一致性统计 §8.3（gold 对 that/who/only 内部不一致） |
| 结构性限制 | Sun 原代码/词典/权重不可得；规则层不可安全消歧；词典规模差异（披露项） | §5-C6；`configs/methods.json` notes |

---

## 三、D1 结果证据表

| 项 | 数值 | 证据路径（formal_experiment/ 内，均 tracked） |
|---|---|---|
| 注册旧 run P/R/F1（s28_s29） | 0.9068 / 0.6645 / **0.7669** | `outputs/development/s28_s29_deepseek_v4pro_sun_literal_v1/metrics.json`；`docs/PROJECT_AUDIT.md` §3.1 |
| v6 verify-pass P/R/F1（R1） | 0.8799 / 0.6900 / **0.7735** | `outputs/development/s27_d1_v6_verify_pass_150_hist56d_v1/verify_pass_evaluation_20260805.json`；`docs/D1_ERROR_ANALYSIS.md` §8 双评表 |
| R3 干净重跑 P/R/F1 | 0.8793 / 0.6938 / **0.7756**（+0.0021 vs R1） | `outputs/development/s27_d1_v6_r3_clean_rerun_150_hist56d_v1/evaluation_d1_r3_20260806.json`（r3_clean_rerun）；manifest 同目录；`docs/D1_ERROR_ANALYSIS.md` §8 |
| 句子级粗 Gold P/R/F1 | 0.9012 / 0.8456 / **0.8726** | `outputs/development/s27_d1_coarse_gold_sentence_granularity_v1/report.json`（粗 Gold 与 B0 实验语义 sha 相同 `6e19cf3c…`，可比）；脚本 `scripts/coarse_gold_d1_sentence_granularity_v1.py`；commit `7899fd9` |
| 主要错误：constraint wrong_field | **100**（内容被抽、落错字段，主要进 action/condition） | §8 失败类型表；R3 逐字段 unmatched 分布 |
| 主要错误：constraint not_extracted | **69**（完全未抽） | 同上 |
| 主要错误：actor 泛指主语误抽 | 旧 run P 0.594（69 pred vs 48 gold，23 无 Gold 交叠） | `docs/D1_ERROR_ANALYSIS.md` §3/§4-D1-C4 |
| 整体偏保守漏抽 | not_extracted 154（R1 142→R3 154，+12，trade-off 已披露）；R3 抽得更少但落位更准 | §8 双评表与要点 |

---

## 四、B0 vs D1 对照矩阵

| 评价口径 | B0 P/R/F1 | D1 P/R/F1 | 谁领先 | 可解释原因 |
|---|---|---|---|---|
| 细粒度 Gold（1055 spans，主口径） | 0.6845 / 0.7564 / **0.7186** | 0.8793 / 0.6938 / **0.7756** | **D1**（F1 +0.057） | D1 高精度但保守（P 0.879 vs 0.685）；B0 规则方法字段归属错误主导（C1 action 吞并 + C2 constraint↔condition 混淆）拖低 P，R 反而高于 D1（0.756 vs 0.694） |
| 句子级粗 Gold（609 spans） | 0.7309 / 0.8801 / **0.7986** | 0.9012 / 0.8456 / **0.8726** | **D1**（F1 +0.074） | 粒度放松两方法 R 均大升（B0 +0.124、D1 +0.152）→ 标注粒度负担证据；D1 P 高保持，领先扩大 |
| condition/constraint Sun-marker 归因（R 侧） | condition R 0.989 (91/92)；constraint R 1.000 (13/13) | **N/A**（D1 未做同口径 marker 收敛实验，不编造；如需可补跑，R 侧可解读、P 侧单边收敛不可解读） | **B0（仅 R 侧）** | B0 在 Sun 公开定义内召回≈满分；我们 constraint 302 个中仅 4%（13 个）符合 Sun marker 定义（Sun 自身 35 个）→ 定义范围差异是低分主因之一 |

---

## 五、论文/汇报安全表述

| 风险表述（禁止） | 安全表述（允许） |
|---|---|
| "exact Sun reproduction" / "Sun 原代码复现" | "method-level independent reconstruction"：Sun 核心组件（BERT-TextCNN + CoreNLP/Tregex/Tsurgeon）+ 公开 marker + 已披露适配（Tsurgeon 为诚实非实现，fail-closed 守卫）；见 `configs/methods.json` 与 `docs/B0_R2_METHOD_CROSSWALK.md` |
| "Sun original 150" / "Sun 的 443 spans" | "项目独立构建的 LLM-assisted, human-adjudicated EStG-150 benchmark"（150 sample_ids 永久锁定；不是 Sun 原始 150，不是 exact reproduction） |
| "final formal result" / "正式结论" | "development / attribution / fixed-snapshot 结果（56d2b03 历史快照）"；formal Gold 未发布（BLOCKERS 5），正式比较（B0-R4/D1-R4）未跑 |
| "H1 已证明有效" | H1 开发机制已修复（S2.8D 系列 canary 成功），但**无新性能结果**；H1 路线选择待导师决定（A 放弃以 D1 为主 / B 选择性风控触发），不写任何"H1 已证明"表述 |
| "D1 完全解决法规抽取" | "D1 是当前领先方法（细 Gold F1 0.7756，development）"，但 constraint 仍弱（wrong_field 100 + not_extracted 69）、actor 泛化误抽仍在 |
| "B0 代码错误导致低分" | "B0 确定性代码错误已修（B0-R1 verified 闭环）"；低分由 Gold 粒度更细 + constraint 定义范围更宽 + 规则方法字段边界天花板解释（归因实验证据，见 §二/§四） |

---

## 六、B0/D1 还缺什么（按优先级）

1. **正式结果仍待 formal Gold publication / shared capsule / Stage 3 gate**：
   `formal_gold_publication_ready=False`、`final_experiment_ready=False`；formal Gold 发布需
   route/data/stage3 重锁 + publication gate 白名单精确匹配（当前 BLOCKERS 5，其中
   `formal_gold_publication_paused`、`final_experiment_not_ready`、`formal_methods_not_ready`、
   `formal_capsule_not_frozen`、`stage3_benchmark_not_locked`）。
2. **B0-R4 / D1-R4 仍需在同一正式 capsule 下运行或登记**（三方法共享 IDs、schema、
   normalization、evaluator）；当前均 blocked。
3. **当前可先用于导师汇报和论文草稿的，是 development / attribution evidence**：
   本文 §二/§三/§四 全部表格 + `docs/B0_ERROR_ANALYSIS.md` + `docs/D1_ERROR_ANALYSIS.md` +
   `docs/SUPERVISOR_Q_A_PREP_2026-08-06.md`（答辩防御手册），标注口径即可引用。
4. **不建议继续改 B0/D1 方法**（不追分）：B0 规则层已到"不可安全消歧"边界、D1 配方已锁定；
   除非导师要求新增实验（如 D1 Sun-marker 收敛、双收敛 P 侧验证）。
5. **若要进一步增强论文，可补 B0/D1 代表性错误案例表**（每方法 ~10 例：Gold span / 预测 /
   错误类型 / 机制），但**不要修改 Gold、不要调参**；该表可用现有 attempts + 56d2b03 Gold
   离线生成（0 LLM 调用）。
