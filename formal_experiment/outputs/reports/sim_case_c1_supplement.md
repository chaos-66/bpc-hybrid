# 补充案例：Sun Figure 10 重建模型上的非 LLM 基线（S3.9-EXT-REAL-CASE）

- run: `sim_case_c1_supplement_v1`；口径：**development_supplement_reconstructed_model_not_authors_model**
- 模型身份：**our reconstruction from the published Figure 10 (not the authors' model)**（重建件，非作者原模型）
- 阈值：tau=0.8, gamma=0.8, theta=0.8, gamma_ext=0.5
- 模型证据：activities=11, gateways=4, events=5, flows=20, lanes=['Another Phone Company', 'Customer', 'Phone Company'], 不可达节点=3

## 1. 本轮实际运行的组与缺失的组

- 已运行：{"A": "non-LLM deterministic adapter + Sun-style three types (+ four extended types reported as extension)"}
- **缺失**：{"B": "real-LLM Stage 2 not run", "C": "depends on B"}

## 2. 历史真实 LLM 预测复用审计（Table 13 文本 vs 既有预测输入）

| Table 13 | 对应既有输入 | 完全相同 | 规范化后相同 | 可复用 | 原因 |
|---|---|---|---|---|---|
| R1 | `SIM_card_scenario/r8/v2` | False | True | False | case/punctuation differs; span offsets are bound to the original string |
| R2 | `SIM_card_scenario/r9/v2` | False | False | False | case/punctuation differs; span offsets are bound to the original string |
| R3 | `SIM_card_scenario/r10/v2` | False | True | False | case/punctuation differs; span offsets are bound to the original string |
| R4 | `SIM_card_scenario/r11/v2` | False | True | False | case/punctuation differs; span offsets are bound to the original string |

## 3. 逐条结果（非 LLM 基线，A 组）

| 规则 | 检测项 | 族 | 状态 | 分数 | 原因 |
|---|---|---|---|---|---|
| R1 | missing_action | three_types | violation | 1.0 | — |
| R1 | incorrect_actor | three_types | undetermined | None | action_mapping_below_gamma |
| R1 | out_of_order | three_types | undetermined | 0.0 | no_mapped_rule_order_endpoints |
| R1 | prohibited_action_present | four_extended_extension | undetermined | None | rule_modality_not_prohibition |
| R1 | required_condition_not_enforced | four_extended_extension | undetermined | None | action_mapping_below_gamma |
| R1 | constraint_violated | four_extended_extension | undetermined | None | empty_rule_constraint |
| R1 | exception_not_handled | four_extended_extension | undetermined | None | empty_rule_exception |
| R2 | missing_action | three_types | violation | 1.0 | — |
| R2 | incorrect_actor | three_types | undetermined | None | empty_rule_actor_denominator |
| R2 | out_of_order | three_types | undetermined | 0.0 | no_mapped_rule_order_endpoints |
| R2 | prohibited_action_present | four_extended_extension | undetermined | None | rule_modality_not_prohibition |
| R2 | required_condition_not_enforced | four_extended_extension | undetermined | None | action_mapping_below_gamma |
| R2 | constraint_violated | four_extended_extension | undetermined | None | empty_rule_constraint |
| R2 | exception_not_handled | four_extended_extension | undetermined | None | empty_rule_exception |
| R3 | missing_action | three_types | violation | 1.0 | — |
| R3 | incorrect_actor | three_types | undetermined | None | action_mapping_below_gamma |
| R3 | out_of_order | three_types | undetermined | 0.0 | no_mapped_rule_order_endpoints |
| R3 | prohibited_action_present | four_extended_extension | undetermined | None | rule_modality_not_prohibition |
| R3 | required_condition_not_enforced | four_extended_extension | undetermined | None | action_mapping_below_gamma |
| R3 | constraint_violated | four_extended_extension | undetermined | None | empty_rule_constraint |
| R3 | exception_not_handled | four_extended_extension | undetermined | None | empty_rule_exception |
| R4 | missing_action | three_types | violation | 1.0 | — |
| R4 | incorrect_actor | three_types | undetermined | None | action_mapping_below_gamma |
| R4 | out_of_order | three_types | undetermined | 0.0 | no_mapped_rule_order_endpoints |
| R4 | prohibited_action_present | four_extended_extension | undetermined | None | rule_modality_not_prohibition |
| R4 | required_condition_not_enforced | four_extended_extension | undetermined | None | action_mapping_below_gamma |
| R4 | constraint_violated | four_extended_extension | undetermined | None | empty_rule_constraint |
| R4 | exception_not_handled | four_extended_extension | undetermined | None | empty_rule_exception |

## 4. 规则记录与映射（证据）

- **R1**（Company regulation）：actions=['terminated']，actors=['The process of phone company']，order_relations=[]，condition='if it takes more than 30 days for any reason'，best_activity={'id': 'sun10_new_client_acquired', 'name': 'New client acquired', 'similarity': 0.446202}
- **R2**（Company regulation）：actions=['verify the correctness of their personal information']，actors=[]，order_relations=[]，condition="After receiving the customer's personal information"，best_activity={'id': 'sun10_ask_portability_third_party', 'name': 'Ask portability third party', 'similarity': 0.386329}
- **R3**（Company regulation）：actions=['activate the sim card']，actors=['the customer']，order_relations=[]，condition='When the customer receives the sim card'，best_activity={'id': 'sun10_send_sim_card', 'name': 'Send SIM card', 'similarity': 0.706705}
- **R4**（GDPR）：actions=['ask the Data Subject']，actors=['Phone company']，order_relations=[]，condition='Before retrieving any kind of personal data from the Data Subject'，best_activity={'id': 'sun10_ask_portability_third_party', 'name': 'Ask portability third party', 'similarity': 0.545584}

## 5. 论文两种读法（仅作文献声明，不作 Gold）

- 正文：R1 and R4 = missing action; R2 = out-of-order execution; R3 = incorrect actor
- Figure 10：V1/R1 and V2/R2 = Missing Action; V3/R3 = Incorrect Actor; V4/R4 = Out-of-order Execution
- 冲突：两种读法在 R2 与 R4 上互换；正式版未取得，二者都只作文献原始声明，均不作可靠 Gold。

## 6. 缺项与边界

- 真实 LLM 组（B/C）在本补充案例中**未运行**：既有预测绑定 Barrientos 输入字符串，与 Table 13 存在大小写/标点差异，span 偏移不可直接复用，本轮不授权重新调用。
- 重建件由我方按 Figure 10 重建，正式版未取得；18 项歧义见 provenance 文件。
- 本结果是开发性补充案例，不构成对论文原始实验的复现。

