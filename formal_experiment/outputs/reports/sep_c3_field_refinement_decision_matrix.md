# SEP-C3 Field Refinement Decision Matrix v1

- 新增 API：0
- 本文件只报告 evidence status，不设计 Prompt。
- 状态集合：`NO_REFINEMENT_EVIDENCE` / `ALREADY_ADDRESSED` / `UNRESOLVED_BOUNDARY` / `POTENTIAL_REFINEMENT_TARGET` / `INSUFFICIENT_EVIDENCE`

## Core Matrix

| Field | Stable failure? | Already covered? | Evidence for new instruction? | Main unresolved issue | Status |
|---|---|---|---|---|---|
| modality | 是；29 个 Gold-definition 样本中 20 个 A/B/C/D 全错；另有 6 个非 definition same-wrong | S2 给出 label 名称；E4 只覆盖 definition + obligation 的一种形式 | 有：stable definition -> obligation/prohibition confusion | definition 与 obligation/prohibition 的边界 | `POTENTIAL_REFINEMENT_TARGET` |
| actor | pre-R_A yes；R_A 后 empty-Gold FP 36->19，recall 不降 | R_A 强覆盖；E1/E2 有 actor 相关例子 | 无 | unresolved pronoun / R_A 理论边界；未在 EStG-150 观测到 loss | `ALREADY_ADDRESSED` |
| action | 部分稳定；definition light verb miss；action 与 condition/constraint overlap 行为与 E4/S8 不一致 | S4/E4/E5 部分；S8 与 Gold overlap 冲突；当前 arms 不用 S | 有 boundary evidence，但不足以直接写 action-specific rule | 39/39 Gold definition clauses 有 action；action 可以包含 condition/constraint | `UNRESOLVED_BOUNDARY` |
| condition | 是；R_C 下 condition-only migration 在 A->C 和 B->D 重复 | S5/E5/R_C 部分 | 有，但必须与 constraint joint 处理 | condition predicate threshold vs independent local restriction | `POTENTIAL_REFINEMENT_TARGET` |
| constraint | 是；R_C 提升 recall 但 FP 和 isolated `only` 同时上升 | S6/R_C/E2/E5 部分 | 有，但必须与 condition joint 处理 | 同一 nested boundary；short complete phrase vs isolated cue | `POTENTIAL_REFINEMENT_TARGET` |
| exception | 无法判定；Gold 11 samples / 13 spans；A/B/C/D 正确 5/6/5/6 | S7/E3 基础覆盖 | 无充分证据 | sample size 太小；run/arm sensitivity | `INSUFFICIENT_EVIDENCE` |

## Evidence Notes

### Modality

- Gold-definition samples: 29.
- Same-wrong across A/B/C/D: 26 total; 20 definition, 2 obligation, 2 permission, 2 prohibition.
- Gold-definition specific: 20 always wrong, 7 always right, 2 corrected only by C/D.
- 主要形式：`shall be deemed`, `are not eligible`, `is`, `means`, `does not apply`.

### Actor

- A empty-Gold actor false positives: 36.
- B (+R_A): 19.
- C: 33; D: 23.
- A/B matched Gold actor: 39/41 both.
- R_A 与 Gold actor convention 方向一致；没有实际 recall loss 证据。

### Action

- Gold definition clauses with action spans: 39/39.
- Gold clause-level cross-field overlaps:
  - action::constraint 9 pairs / 8 samples
  - action::condition 2 pairs / 1 sample
  - actor::condition 1 pair / 1 sample
  - condition::exception 1 pair / 1 sample
- Action F1 仍然较高，因此不应写成 action 全面 failure；问题是 specific Gold span boundary 与 E4/S8 wording 不一致。

### Condition / Constraint

- Actual Gold condition/constraint intersections: 11 clause-level pairs / 10 clauses / 10 samples.
- Relations: 7 condition contains constraint, 4 constraint contains condition.
- Sample-level intersections: 21 pairs / 14 samples.
- condition-only clauses: 152 / 116 samples.
- constraint outside-condition spans: 291 / 132 samples.
- Coarse evaluator hull overlaps: 43 / 150 samples; diagnostic only.
- R_C condition coverage loss: 19 sample-direction records; 8 records / 5 independent samples are condition-only migration.
- R_C constraint recall recovery: 52 coarse recoveries; 49 intersect real Gold constraints; 37 exactly recover at least one; 3 only hull gaps.

### Exception

- Gold: 11 samples / 13 spans.
- Correct by arm: A=5, B=6, C=5, D=6.
- E3 only shows `unless`; Gold has `except`, `excluding`, `with the exception`, `even if`, `apart from`, `to the extent that ... not`.
- 不足以支持 targeted refinement。

## No-Current-Justification List

- `actor`: R_A addressed the stable failure; no new evidence.
- `exception`: insufficient sample and no stable error direction.

## Joint Priority

`condition` and `constraint` are one joint boundary problem, not two independent instruction problems. Any future wording should be treated as a joint boundary candidate, not two separate field modules. This report does not design that wording.
