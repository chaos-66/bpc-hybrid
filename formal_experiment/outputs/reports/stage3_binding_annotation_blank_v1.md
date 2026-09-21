# Stage 3 rule-to-process binding: blank annotation surface

Surface id: `stage3_binding_annotation_blank_v1` - status `blank_awaiting_human_annotation`.

provide the rule-action -> BPMN-activity binding that the Ours detector requires as INPUT and that is currently annotated nowhere; agents must never infer these values.

## Why this is needed

The 30-item mutation panel says WHICH BPMN activity was mutated (`target_activity_id`) but never which rule action that activity discharges, and both are multi-word spans, so the correspondence is not recoverable by construction. A grounded three-type detector needs it as input; deriving it by similarity is the step measured to fail.

## Counts

- Pairs to annotate: **30** (each pair covers one control + one variant BPMN: {'control': 30, 'variant': 30})
- By rule: {'article33': 6, 'article22': 6, 'article15': 4, 'article20': 4, 'article17': 6, 'article16': 4}
- Decisions filled: **0** (this is a blank template)

## Fields to complete

| Field | Meaning |
|---|---|
| `decision_action_id` | the rule action span id (from immutable_context.rule_side.actions) that the target BPMN activity discharges |
| `decision_actor_id` | the rule actor span id that legitimately performs it |
| `decision_expected_lane` | the lane name in the CONTROL BPMN that legitimately owns the target activity |
| `decision_order_before_action_id` | for out_of_order only: the rule action that must precede |
| `decision_order_after_action_id` | for out_of_order only: the rule action that must follow |
| `decision_note` | free-text rationale |
| `review_state` | unreviewed | reviewed | adjudicated |

## Recorded limits (do not work around these silently)

- **order_relations_in_gold**: the published Gold Rule Records carry ZERO order relations across 92 clauses, so the out_of_order decision fields cannot be anchored to existing Gold and would require new annotation of the rules themselves
- **actor_action_map_coverage**: 38 of 92 Gold clauses carry an actor_action_map link, so for most clauses the actor side must also be annotated rather than copied

## Work estimate

- 30 items, each needing an action binding (and, for the 20 out_of_order items, an order pair).
- `missing_action` and `incorrect_actor` are 10/10 structurally detectable, so binding the action is sufficient to score those two types.
- `out_of_order` additionally needs order relations that do not exist in the Gold yet, so it is the expensive third of the work.

## Provenance

- Benchmark: `stage3_paired_benchmark_v1` (sha256 `8205371ee71af75ae9179481fe87e972e2e70650c0985661bbff8d183f1a3fc5`)
- New LLM calls: 0
- Decisions inferred by agent: False
