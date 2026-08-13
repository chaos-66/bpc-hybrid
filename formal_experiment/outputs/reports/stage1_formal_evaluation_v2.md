# Stage 1 正式评价 v2（claim 纠正版，2026-08-13）

> 状态：**`claim_corrected_numbers_locked`**——数值由 v1 逐位锁定并迁移到
> 正式路径；claim 语义按 target-overlap 审计纠正。
> 机器可读：`outputs/reports/stage1_formal_evaluation_v2.json`（sha
> `954122d4…`）
> verifier：`scripts/verify_stage1_formal_evaluation_v2.py`（VERIFIED）

## 1. 准确 claim 表述

> **post-Gold, target-aware Sun/Leopold-style method-level reconstruction
> with Gold-isolated inference, pre-evaluation code/config lock, and no
> post-evaluation tuning**

- `evaluation_role = formal_descriptive_component_evaluation_on_fixed_GDPR7`
- `strict_test_blind=false`、`developer_blind=false`
- `held_out_generalization_claim_allowed=false`
- `target_labels_seen_during_development=true`（见 overlap audit：3 条重合）
- `runtime_gold_read=false`、`implementation_locked_before_scoring=true`
- `post_evaluation_tuning=false`

## 2. 正式权威路径（v2）

| 资产 | 路径 | sha256 |
|---|---|---|
| Predictions（权威副本） | `data/predictions/stage1_formal_v1/formal_predictions_v1.json` | `79a9b2c1…`（与锁定 predictions 逐位一致） |
| Results（数值主体） | `data/results/stage1_formal_v1/stage1_formal_evaluation_v1.json` | `a072db39…`（canonical `19002346…`） |
| 评价报告 v2 | `outputs/reports/stage1_formal_evaluation_v2.json` | `954122d4…` |
| Overlap audit | `outputs/reports/s1_p2_target_overlap_audit_v1.json` | `948d268a…` |
| Claim correction | `outputs/reports/s1_stage1_claim_correction_v2.json` | — |

旧 development 路径（`outputs/development/stage1_predictions/`、
`outputs/development/stage1_formal_capsule_v1/`）保留为 **historical
provenance**：数值仍有效、claim metadata 由 v2 纠正、不作为最终正式入口。

## 3. 指标（数值与 v1 逐位一致，未重算）

| 方法 | 语义 micro P/R/F1 | exact acc | triple | 结构 micro F1 |
|---|---|---|---|---|
| P0 | 0.0 | 0.0 | 0.0 | 1.0 |
| P1 | 0.744444… / 0.496296… / 0.595555… | 0.424083… | 0.0 | 1.0 |
| P2 | 0.854838… / 0.785185… / **0.818532…** | 0.692810… | **0.422222…** | 1.0 |

分母：7 processes / 45 activities / 135 semantic fields。

## 4. 绑定

- membership payload `e88caf81…`；7 个 BPMN source hashes（见 v2 JSON）
- P2 config `59ac4e8e…`、implementation `c95910ef…`、runtime spaCy
  3.8.13/en_core_web_sm 3.8.0（dir `f5c9433c…`）
- Stage 1 Gold `f33aa857…` + gold manifest
- 正式 evaluator 合同 `stage1_evaluator_s16_formal.json`
- overlap audit + claim correction

## 5. 披露

- candidate-assisted human adjudication；结构 Gold=人工接受的 parser
  candidate；**结构 1.0 不是独立泛化证据**
- 无显著性推断；不与 Sun 不同数据集绝对分数硬比较
- 泛化证据需要方法冻结后另取并独立裁决的新 BPMN 集合
