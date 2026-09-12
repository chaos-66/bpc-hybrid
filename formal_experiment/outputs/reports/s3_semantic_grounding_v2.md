# s3_semantic_grounding_v2 (development-only)

Evaluation-protocol repair around the frozen v1 deterministic scorer. Zero real API calls.

## Target-paired causal evaluation (primary)

| Type | P | R | F1 | Balanced acc | Variant TP/FN/unknown | Control TN/FP/unknown | Pair success |
|---|---|---|---|---|---|---|---|
| prohibited_action_present | 1.0000 | 1.0000 | 1.0000 | 1.0 | 10/0/0 | 8/0/2 | 8/10 |
| required_condition_not_enforced | 0.9000 | 0.9000 | 0.9000 | 0.9 | 9/1/1 | 9/1/0 | 8/10 |
| constraint_violated | 1.0000 | 0.2000 | 0.3333 | 0.6 | 2/8/8 | 2/0/8 | 2/10 |
| exception_not_handled | 1.0000 | 0.3000 | 0.4615 | 0.65 | 3/7/7 | 9/0/1 | 3/10 |

- Target-paired macro-F1: **0.6737**
- Control target-field FP rate: **0.0250**
- Target-field unknown rate: **0.3375**
- Pair success rate: **0.5250**

## Variant binary checks (40 variants)

| Type | P | R | F1 |
|---|---|---|---|
| prohibited_action_present | 1.0000 | 1.0000 | 1.0000 |
| required_condition_not_enforced | 0.3600 | 0.9000 | 0.5143 |
| constraint_violated | 1.0000 | 0.2000 | 0.3333 |
| exception_not_handled | 0.6000 | 0.3000 | 0.4000 |

- Variant binary macro-F1: **0.5619**

## Unified metrics

- Legacy 80-object diagnostic: 5-class accuracy **0.3500**, 5-class Macro-F1 **0.4246**, 4-type Macro-F1 **0.4752** (not a pure none-Gold benchmark because controls only guarantee the target field).
- Clean unified subset (5 verified controls + 40 variants): 5-class accuracy **0.6222**, 5-class Macro-F1 **0.6709**, 4-type Macro-F1 **0.5886**.

## Composite-input collision audit

- True collision groups: **9**, true collision items: **20**.
- Old BPMN-only variant collision groups: **7**.
- The v1 audit grouped only by variant BPMN bytes.  The Stage 3 input also contains the Rule Input; two byte-identical BPMN files with different model-visible rule fields are distinguishable and therefore are not true input collisions.  The v1 audit also counted only the variant scope, while the corrected audit checks both variant and control side objects and requires different expected labels only after the identity grouping is fixed.

## Fallback candidate pack

- Frozen fallback items: **20**.
- Trigger counts: `{"action_grounding_ambiguous": 10, "condition_semantic_ambiguous": 10, "unsupported_abstract_constraint": 11, "action_grounding_unresolved": 5, "exception_semantic_ambiguous": 3, "other_documented_semantic_ambiguity": 1, "exception_handler_semantic_ambiguous": 1}`
- Side counts: `{"variant": 7, "control": 13}`

## LLM arm C

- Status: **IMPLEMENTED_READY_FOR_AUTHORIZATION**; no real API call in this deterministic revision.

## Claim boundary

Development-only synthetic controlled panel.  Not formal Oracle and not human Gold. Controls are target-field controls, not globally compliant objects unless the offline control-global-compliance status says so.
