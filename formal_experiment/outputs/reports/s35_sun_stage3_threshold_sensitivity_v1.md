# Stage 3 Sun 阈值敏感性实验报告（DEV_ONLY，零 API，2026-09-04）
> 对应论文方法：Sun et al. (2024) 第 5.3 节 / 图 8 / 图 9 的离散阈值网格分析。本报告为 **development-only 方法级重建**，不是 Sun 原代码精确复现，也不是预注册的正式结果；schema：`s35_sun_stage3_threshold_sensitivity_report@1.0.0`；git：`693115a71c7d9c973e542d9132e443a0e5675c09`。

## 0. 结果口径与措辞
- **Sun-transferred**（迁移基线，保留方法级对照，也是论文表 A 中 Sun 行的口径）：τ=0.8、γ=0.8、ϑ=0.8；Macro-F1 0.3889、exact-type accuracy 0.3636、unobservable 10。
- **Sun-style calibrated sensitivity**：测试集合中表现最好的观察设置（**tested values 中的 best observed setting**）：τ=0.8、γ=0.6、ϑ=0.8；Macro-F1 0.8733、exact-type accuracy 0.7879、unobservable 4。
- γ=0.6 只能称为：“tested values 中的 best observed setting”、“Sun-style threshold sensitivity result”、“本文数据与当前相似度后端上的经验校准值”。
- **不得**称为：数学全局最优阈值、Sun 原论文固定阈值、在独立 held-out test 上发现的最优值、与 Sun 原始四模型完全相同的数据结果。

## 1. Sun 原文核对（只读，行号引自 `references/papers/extracted/sun_2024_full_text.txt`）
1. **τ** 是 rule–process matching threshold（Def. 4，L523–539）：matching(r,m,τ)=max(rule action 对中 sim>τ 的比例, rule actor/object 对中 sim>τ 的比例)。
2. **γ** 是 action similarity threshold（Def. 4 前言 L591–596：“if sim(S1,S2) > γ，两个语义成分视为等价”）：决定 missing action 的可观察性（Def. 5，sim<γ 记为缺失）、incorrect actor 的 R/C 映射与可观察性（Def. 6，仅 sim>γ 的动作映射进入 R）以及 out-of-order 端点映射（Def. 7，U_r,m,γ 要求两个端点都以 sim>γ 映射）。
3. **ϑ** 是 actor similarity threshold（Def. 6，L549–559）：规则 actor r∈R 存在 流程 actor/object r′∈C 使 sim(r,r′)<ϑ 即记违规。
4. Sun 的两个 matching 数据集总体均在 τ=0.8 时 MAP 最高：Table 9（12 个能源供应商流程模型）MAP 0.801（9/12 模型在 0.8 最佳、3/12 在 0.6 最佳，L812–833）；Table 11（4 个 GDPR BPMN 模型）MAP 0.840（4/4 在 0.8 最佳，L864–871）。
5. Sun 图 8（L894–907）：missing action 与 out-of-order 一起分析（两类精度只由 γ 决定），多数模型在 γ=0.8 达到最高 Precision；复杂度最高的 Model 4 在 γ=0.6 最高；γ=0.9 低于 0.8。
6. Sun 图 9（L908–922）：固定 γ=0.8 后比较 ϑ；incorrect actor 的精度受 γ 与 ϑ 共同影响，前两类在 γ=0.8 更好，故 ϑ 单独在 γ=0.8 下分析。四个模型中两个在 ϑ=0.8 最好，另外两个（更大、内容更多的模型）在 ϑ=0.7 最好。
7. Sun 的解释（L895–922）：复杂/更大模型的文本内容更多，语义相似度在复杂情境下下降，因此较低阈值可能更合适；阈值过高（更严格）会把正常操作识别为违规、降低 Precision。
8. 措辞：**0.8 是 Sun 自己数据上多数模型表现较好的经验值，不是“Sun 规定所有模型必须使用 0.8”，也不是定义本身写死的值**；同理本文 γ=0.6 只是 tested values 中的 best observed setting。

## 2. 冻结口径（本实验未改动任何输入/方法/公式）
- 冻结 GDPR-7 BPMN（7 流程）；33 条人工裁决 Gold（11/11/11，`data/gold/stage3/`）；25 条 matching Gold；Rule/Process Records（S3.5 缓存）；Sun Definition 4–7 重建；spaCy `en_core_web_sm` 相似度后端；common evaluator；原始 γ=0.8 结果与全部其他方法结果。
- 未修改 Gold、样本、预测标签或评价公式；**全程离线，API calls = 0、cost = $0**；既有 evidence（`outputs/evidence/s35_sun_stage3_development_v2/*`）逐字节未动（测试哈希锁）。
- **限制披露**：33 条人工 Gold 没有 `Gold=none` 合规样本，因此本实验**不能用它证明 specificity 或控制 false-positive rate**；33 条 panel 每个测试点预路由到单一 gold 类型，跨类型 FP 在该 panel 上结构性不可能出现，Precision 的信息量低于 Recall/F1。

## 3. 阈值集合（严格对齐 Sun 的离散网格）
- matching τ ∈ [0.0, 0.2, 0.4, 0.6, 0.8, 0.9]（Sun Table 9 的 τ 列）——只评价 matching AP/MAP，不把 matching MAP 当作 violation F1。
- violation γ ∈ [0.0, 0.2, 0.4, 0.6, 0.8, 0.9]（ϑ 固定 0.8）——每个 γ 都通过 SunScorer 真实重算 action mappings、actor denominators、order endpoints 与 observability，不是对既有最终分数重切阈值。
- incorrect-actor ϑ ∈ [0.5, 0.6, 0.7, 0.8, 0.9]，**固定 γ=0.8**（与 Sun 图 9 一致）。

## 4. 主结果
### 4.1 匹配（τ 扫描：Def-4 分数重算 + 排序 AP/MAP，support=25）
| τ | AP(P1) | AP(P2) | AP(P3) | AP(P4) | AP(P5) | AP(P6) | AP(P7) | MAP | runtime(s) |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 2.73 |
| 0.2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.26 |
| 0.4 | 0.7500 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9643 | 1.42 |
| 0.6 | 0.4167 | 0.5333 | 1.0000 | 0.5000 | 0.5000 | 0.3333 | 0.5000 | 0.5405 | 1.60 |
| 0.8 | 0.5833 | 0.6389 | 1.0000 | 1.0000 | 0.5000 | 1.0000 | 1.0000 | 0.8175 | 1.50 |
| 0.9 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.5000 | 1.0000 | 1.0000 | 0.9286 | 1.32 |

注：per-process AP 只有 3–5 个候选规则；τ 越低 Def-4 分数越饱和（大量 1.0 平局），故该曲线上本文数据**不**呈现 Sun Table 9 的倒 U 型——这是小集合平局排序的披露性结果，不是匹配方法“更好/更差”的证据。τ=0.8 行与 evidence `evaluation.json` 的 per-process AP/MAP 完全一致（验证块）。

### 4.2 违规检测（γ 扫描，ϑ 固定 0.8；33 条人工 Gold，unobservable 计入 FN）
| γ | Missing F1 | Incorrect-actor F1 | Out-of-order F1 | Macro-F1 | Micro-F1 | Exact | Unobs | runtime(s) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.0000 | 1.0000 | 1.0000 | 0.6667 | 0.8000 | 0.6667 | 0 | 4.12 |
| 0.2 | 0.0000 | 1.0000 | 1.0000 | 0.6667 | 0.8000 | 0.6667 | 0 | 2.58 |
| 0.4 | 0.1667 | 1.0000 | 1.0000 | 0.7222 | 0.8214 | 0.6970 | 0 | 2.92 |
| 0.6 | 1.0000 | 0.7778 | 0.8421 | 0.8733 | 0.8814 | 0.7879 | 4 | 2.59 |
| 0.8 | 1.0000 | 0.1667 | 0.0000 | 0.3889 | 0.5333 | 0.3636 | 10 | 2.41 |
| 0.9 | 1.0000 | 0.0000 | 0.0000 | 0.3333 | 0.5000 | 0.3333 | 11 | 2.29 |

γ=0.8（转移基线）：Macro-F1 0.3889、exact 0.3636、unobservable 10——大量合法的 action mappings 无法通过门槛（incorrect-actor 10 条 `action_mapping_below_gamma` 不可观察；out-of-order 端点映射分母为 0 的检查点 11/11 → 0/11 检出），不是公式错误而是门槛与相似度后端的错配。
γ=0.6（tested values 中的 best observed setting）：Missing F1 1.0000、Incorrect-actor F1 0.7778、Out-of-order F1 0.8421、Macro-F1 0.8733、exact 0.7879、unobservable 4；out-of-order 端点映射分母为 0 的检查点降至 3/11。

### 4.3 Incorrect-actor（ϑ 扫描，γ 固定 0.8——Sun 图 9 口径）
| ϑ | Incorrect-actor P | R | F1 | Macro-F1 | Exact | Unobs | runtime(s) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 | 1.0000 | 0.0909 | 0.1667 | 0.3889 | 0.3636 | 10 | 2.43 |
| 0.6 | 1.0000 | 0.0909 | 0.1667 | 0.3889 | 0.3636 | 10 | 2.12 |
| 0.7 | 1.0000 | 0.0909 | 0.1667 | 0.3889 | 0.3636 | 10 | 2.33 |
| 0.8 | 1.0000 | 0.0909 | 0.1667 | 0.3889 | 0.3636 | 10 | 2.43 |
| 0.9 | 1.0000 | 0.0909 | 0.1667 | 0.3889 | 0.3636 | 10 | 2.33 |

γ=0.8 下 incorrect-actor 检查几乎整体不可观察（11 条中 10 条 `action_mapping_below_gamma`）。
唯一可观察检查点 v014 的 min actor similarity = -0.0163，低于测试网格中的最小 ϑ=0.5，因此在每个测试 ϑ 下都触发同一判定。
故 ϑ 行在本文数据上完全平坦——这是可观察性瓶颈的真实结果，不构成对 Sun 图 9 趋势的复现或否定。

### 4.4 各 process 结果（每阈值一行；缩写 P1–P7 = gdpr_1_data_breach … gdpr_7_right_to_be_forgotten）
| 扫描 | 阈值 | process | support | exact | Macro-F1 | Micro-F1 | unobs | Missing F1 | Incorrect-actor F1 | Out-of-order F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| γ | 0 | P1 (gdpr_1_data_breach) | 6 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0 | P3 (gdpr_3_right_to_access) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0 | P4 (gdpr_4_right_of_portability) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0 | P6 (gdpr_6_right_to_rectify) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.2 | P1 (gdpr_1_data_breach) | 6 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.2 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.2 | P3 (gdpr_3_right_to_access) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.2 | P4 (gdpr_4_right_of_portability) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.2 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.2 | P6 (gdpr_6_right_to_rectify) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.2 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.4 | P1 (gdpr_1_data_breach) | 6 | 0.8333 | 0.8889 | 0.9091 | 0 | 0.6667 | 1.0000 | 1.0000 |
| γ | 0.4 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.4 | P3 (gdpr_3_right_to_access) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.4 | P4 (gdpr_4_right_of_portability) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.4 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.4 | P6 (gdpr_6_right_to_rectify) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.4 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 0.6667 | 0.6667 | 0.8000 | 0 | 0.0000 | 1.0000 | 1.0000 |
| γ | 0.6 | P1 (gdpr_1_data_breach) | 6 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 | 1.0000 |
| γ | 0.6 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 | 1.0000 |
| γ | 0.6 | P3 (gdpr_3_right_to_access) | 3 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 | 1.0000 |
| γ | 0.6 | P4 (gdpr_4_right_of_portability) | 3 | 0.6667 | 0.6667 | 0.8000 | 1 | 1.0000 | 0.0000 | 1.0000 |
| γ | 0.6 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.6 | P6 (gdpr_6_right_to_rectify) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.6 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 | 1.0000 |
| γ | 0.8 | P1 (gdpr_1_data_breach) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.8 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 0.4444 | 0.5000 | 0.6154 | 2 | 1.0000 | 0.5000 | 0.0000 |
| γ | 0.8 | P3 (gdpr_3_right_to_access) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.8 | P4 (gdpr_4_right_of_portability) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.8 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.8 | P6 (gdpr_6_right_to_rectify) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.8 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.9 | P1 (gdpr_1_data_breach) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.9 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 0.3333 | 0.3333 | 0.5000 | 3 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.9 | P3 (gdpr_3_right_to_access) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.9 | P4 (gdpr_4_right_of_portability) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.9 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.9 | P6 (gdpr_6_right_to_rectify) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| γ | 0.9 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.5 | P1 (gdpr_1_data_breach) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.5 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 0.4444 | 0.5000 | 0.6154 | 2 | 1.0000 | 0.5000 | 0.0000 |
| ϑ(γ=0.8) | 0.5 | P3 (gdpr_3_right_to_access) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.5 | P4 (gdpr_4_right_of_portability) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.5 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.5 | P6 (gdpr_6_right_to_rectify) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.5 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.6 | P1 (gdpr_1_data_breach) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.6 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 0.4444 | 0.5000 | 0.6154 | 2 | 1.0000 | 0.5000 | 0.0000 |
| ϑ(γ=0.8) | 0.6 | P3 (gdpr_3_right_to_access) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.6 | P4 (gdpr_4_right_of_portability) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.6 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.6 | P6 (gdpr_6_right_to_rectify) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.6 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.7 | P1 (gdpr_1_data_breach) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.7 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 0.4444 | 0.5000 | 0.6154 | 2 | 1.0000 | 0.5000 | 0.0000 |
| ϑ(γ=0.8) | 0.7 | P3 (gdpr_3_right_to_access) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.7 | P4 (gdpr_4_right_of_portability) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.7 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.7 | P6 (gdpr_6_right_to_rectify) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.7 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.8 | P1 (gdpr_1_data_breach) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.8 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 0.4444 | 0.5000 | 0.6154 | 2 | 1.0000 | 0.5000 | 0.0000 |
| ϑ(γ=0.8) | 0.8 | P3 (gdpr_3_right_to_access) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.8 | P4 (gdpr_4_right_of_portability) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.8 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.8 | P6 (gdpr_6_right_to_rectify) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.8 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.9 | P1 (gdpr_1_data_breach) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.9 | P2 (gdpr_2_consent_to_use_the_data) | 9 | 0.4444 | 0.5000 | 0.6154 | 2 | 1.0000 | 0.5000 | 0.0000 |
| ϑ(γ=0.8) | 0.9 | P3 (gdpr_3_right_to_access) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.9 | P4 (gdpr_4_right_of_portability) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.9 | P5 (gdpr_5_right_to_withdraw) | 6 | 0.3333 | 0.3333 | 0.5000 | 2 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.9 | P6 (gdpr_6_right_to_rectify) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |
| ϑ(γ=0.8) | 0.9 | P7 (gdpr_7_right_to_be_forgotten) | 3 | 0.3333 | 0.3333 | 0.5000 | 1 | 1.0000 | 0.0000 | 0.0000 |

### 4.5 两种报告口径汇总（相同 33 条 Gold、相同 evaluator）
| 设置 | τ/γ/ϑ | Matching MAP | Missing F1 | Incorrect-actor F1 | Out-of-order F1 | Macro-F1 | Micro-F1 | Exact | Unobs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sun-transferred | 0.8/0.8/0.8 | 0.8175 | 1.0000 | 0.1667 | 0.0000 | 0.3889 | 0.5333 | 0.3636 | 10 |
| Sun-style calibrated (best observed) | 0.8/0.6/0.8 | 0.8175 | 1.0000 | 0.7778 | 0.8421 | 0.8733 | 0.8814 | 0.7879 | 4 |

## 5. 为什么 γ=0.6 更适合当前数据（解释，不含“最优”声明）
1. 相似度后端差异：本文与 S3.4/S3.5 共用 spaCy `en_core_web_sm`（无词向量，W007；相似度来自 tagger/parser/NER 张量），词面-语义相似度分布与 Sun 论文所用后端/数据不同，因此同一 0.8 门槛在本数据上放行的合法 mapping 更少。
2. γ=0.8 的可观察性结果（scorer 诊断测量）：10/11 incorrect-actor 检查为 `action_mapping_below_gamma` 不可观察；out-of-order 检查 11/11 个端点映射分母为 0、0/11 检出（F1=0）。这不是公式错误，而是门槛与该相似度后端的错配（mapping 分数整体偏低）。
3. γ=0.6 的平衡点：missing-action 保持 F1=1.0（其对词面缺失信号不敏感于 0.6–0.9 区间）；incorrect-actor 可观察 7/11、F1 0.1667→0.7778（7 条可观察检查点的 min actor sim 全部 ≤ 0.1364，即任何 ϑ∈[0.5, 0.6, 0.7, 0.8, 0.9] 判定都不变（诊断测量，非正式 ϑ 扫描））；out-of-order 端点映射分母>0 的 8/11 全部检出、其余分母为 0 不可判定，F1 0.0→0.8421；Macro-F1 0.3889→0.8733、exact 0.3636→0.7879、unobservable 10→4。
4. 结论措辞（与 Sun 一致的方式）：Sun 将其 Model 4 在 γ=0.6 更好归因于复杂模型文本相似度下降；本文的同类现象出现在**相似度后端整体偏低**的七模型数据上。结论是阈值需要随数据复杂度与相似度后端重新校准，而不是 Sun 的公式无效。

## 6. 验证与不变量
- primary row (0.8, 0.8) 与 evidence `evaluation.json` 逐项一致：通过；与 evidence `threshold_sensitivity.json` 的所有重叠行一致：通过。
- 输入绑定（hash）见报告 JSON `input_bindings`；correction/gold/inference/blank/BPMN 均未改动。
- 安全声明：llm_api_called=False、api_calls=0、usd_cost=0、network_called=False、env_read=False；Gold 只由 common evaluator 读取。

## 7. 产物
- 本报告：`outputs/reports/s35_sun_stage3_threshold_sensitivity_v1.md`
- 机器可读 JSON：`outputs/reports/s35_sun_stage3_threshold_sensitivity_v1.json`（完整 sweep：`outputs/development/s35_sun_stage3_threshold_sensitivity_v1/sweep.json`）
- 图 A（γ 敏感性，missing action + out-of-order；对应 Sun 图 8 口径）：`..._figA_gamma_missing_action_out_of_order.svg`
- 图 B（ϑ 敏感性，incorrect actor，γ=0.8；对应 Sun 图 9 口径）：`..._figB_theta_incorrect_actor.svg`
- 复现：`python scripts/build_sun_stage3_threshold_sensitivity_v1.py`（全量离线重算）；`--report-only` 从 sweep JSON 确定性重放报告/图。总耗时 54.61 s。
