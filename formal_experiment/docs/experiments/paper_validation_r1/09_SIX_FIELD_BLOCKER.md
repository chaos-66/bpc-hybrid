# Phase 9 — Six-Field Evaluation Blocker

**Status**: BLOCKED. The Gold supports the four `modality`-class labels at full coverage (231/231), but the other five fields are present only partially. We **do not** fabricate Gold, do not use B0 / D1 outputs as Gold, and do not run a full six-field evaluation on the three methods.

## 1. Gold coverage audit (already in `00_AUDIT.md` §3.7)

Counts of non-empty `human_correction.clauses[i].<field>` over the 231 adjudicated Gold clauses (filters: `modality.decision in {accepted, edited}`):

| Field        | Non-empty count | Coverage | Field shape (sample)                |
|--------------|----------------:|---------:|--------------------------------------|
| `modality`   |             231 |   100.0% | enum: permission/obligation/prohibition/definition |
| `actions`    |             230 |    99.6% | list[{id, text, start, end, decision}]   |
| `conditions` |             162 |    70.1% | list[{id, text, start, end, decision}]   |
| `constraints`|             186 |    80.5% | list[{id, text, start, end, decision}]   |
| `actors`     |              46 |    19.9% | list[{id, text, start, end, decision}]   |
| `exceptions` |              11 |     4.8% | list[{id, text, start, end, decision}]   |

## 2. The blocker

A **method-independent** six-field evaluation would require:

1. A complete, adjudicated Gold for all six fields on all 231 clauses.
2. A method-independent evaluator (the project's `stage2_evaluation_v3.py` uses char-span IoU with `clause_minimum_iou=0.5` and the canonical schema; it is method-independent in principle, but requires the predicted output to carry `clause_span` and the six field spans, which the LLM method outputs do not).

We have neither:

- **`actor` is empty on 80% of clauses.** A fair `actor` evaluation would treat empty Gold as "the method is required to abstain", which is a different evaluation regime from the prior `modality` evaluation. The current LLM prompts (D1 and H1-selective) do not require the LLM to abstain on missing `actor`, so a fair six-field evaluation cannot be built on the existing output schema.
- **`exception` is empty on 95% of clauses.** Same issue.
- **The LLM output schema is text-only.** D1 outputs `clause_text` (no spans). H1-selective outputs `clause_text` (no spans). The canonical v3 evaluator cannot be applied to this format.
- **No adjudicated final-violation Gold.** Phase 10 covers this separately.

## 3. Hard-rule check (per task §12.2)

- We do not use D1 output as Gold.
- We do not use B0 output as Gold.
- We do not use another LLM to generate Gold.
- We do not default missing fields to "correct".
- We do not claim six-field evaluation is complete.

The task explicitly says: "如果某字段没有人工 Gold: 不得... 不得声称完成六字段评价." We are complying.

## 4. What would unblock the six-field evaluation

The minimum additional annotation needed:

| Field      | Clauses to annotate (out of 231) | Estimated effort |
|------------|---------------------------------:|------------------|
| `actor`    | 185 (currently 46 covered)        | medium           |
| `exception`| 220 (currently 11 covered)        | high (the empty-ness is informative) |
| `condition`| 69 (currently 162 covered)        | low              |
| `constraint`| 45 (currently 186 covered)       | low              |
| `action`   | 1 (currently 230 covered)         | trivial          |

A re-prompted D1 / H1 cycle that emits char-span-aligned fields would also be needed; the current prompts only emit `clause_text`. The prompts would have to change, which is **out of scope** for this experiment (task §0.3: "不得修改现有方法定义").

## 5. Disposition

Phase 9 produces this blocker file. The modality-only results from Phase 5 stand. The six-field and final-violation results are explicitly **not claimed** in the synthesis or the final report.
