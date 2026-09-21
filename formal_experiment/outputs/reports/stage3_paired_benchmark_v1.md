# Stage 3 paired compliance benchmark (v1)

Benchmark id: `stage3_paired_benchmark_v1` - status `dev_only_benchmark_not_human_gold` - zero LLM calls.

## What this fixes

The 30-item mutation panel had no compliant items, so precision and specificity had no denominator, and every reported per-type F1 was degenerate. This benchmark pairs each mutated BPMN with the **frozen original** of the same process as a compliant control.

## Counts

- Items: **60** (30 pairs)
- By role: {'control': 30, 'variant': 30}
- By target violation type: {'missing_action': 20, 'incorrect_actor': 20, 'out_of_order': 20}
- By gold label: {'compliant': 30, 'missing_action': 10, 'incorrect_actor': 10, 'out_of_order': 10}

## Anti-degeneracy validation

Rule: every control must NOT exhibit its target violation and every variant MUST exhibit it.

Result: **PASS** (0 problem(s)).

## Grounding contract

each item declares its rule->process binding explicitly; a detector may consume it (grounded path) or re-derive it (similarity path), and the two are comparable because the binding is recorded rather than assumed.

## Per-pair structural observation

| Pair | Type | Control | Variant | Separable |
|---|---|---|---|---|
| syn_missing_action_01 | missing_action | compliant | violates | YES |
| syn_missing_action_02 | missing_action | compliant | violates | YES |
| syn_missing_action_03 | missing_action | compliant | violates | YES |
| syn_missing_action_04 | missing_action | compliant | violates | YES |
| syn_missing_action_05 | missing_action | compliant | violates | YES |
| syn_missing_action_06 | missing_action | compliant | violates | YES |
| syn_missing_action_07 | missing_action | compliant | violates | YES |
| syn_missing_action_08 | missing_action | compliant | violates | YES |
| syn_missing_action_09 | missing_action | compliant | violates | YES |
| syn_missing_action_10 | missing_action | compliant | violates | YES |
| syn_incorrect_actor_01 | incorrect_actor | compliant | violates | YES |
| syn_incorrect_actor_02 | incorrect_actor | compliant | violates | YES |
| syn_incorrect_actor_03 | incorrect_actor | compliant | violates | YES |
| syn_incorrect_actor_04 | incorrect_actor | compliant | violates | YES |
| syn_incorrect_actor_05 | incorrect_actor | compliant | violates | YES |
| syn_incorrect_actor_06 | incorrect_actor | compliant | violates | YES |
| syn_incorrect_actor_07 | incorrect_actor | compliant | violates | YES |
| syn_incorrect_actor_08 | incorrect_actor | compliant | violates | YES |
| syn_incorrect_actor_09 | incorrect_actor | compliant | violates | YES |
| syn_incorrect_actor_10 | incorrect_actor | compliant | violates | YES |
| syn_out_of_order_01 | out_of_order | compliant | violates | YES |
| syn_out_of_order_02 | out_of_order | compliant | violates | YES |
| syn_out_of_order_03 | out_of_order | compliant | violates | YES |
| syn_out_of_order_04 | out_of_order | compliant | violates | YES |
| syn_out_of_order_05 | out_of_order | compliant | violates | YES |
| syn_out_of_order_06 | out_of_order | compliant | violates | YES |
| syn_out_of_order_07 | out_of_order | compliant | violates | YES |
| syn_out_of_order_08 | out_of_order | compliant | violates | YES |
| syn_out_of_order_09 | out_of_order | compliant | violates | YES |
| syn_out_of_order_10 | out_of_order | compliant | violates | YES |

## Provenance

- Source panel: `data/development/stage3_synth/synthetic_controlled_error_extension_v1.json` (sha256 `e6b4da045a44ffc347a8de88909e005bef584335f63804d3c2155ef9242c3026`)
- Controls: the frozen Stage 1 GDPR7 membership BPMN (data/input/stage1_stage3/gdpr7/), re-used via each variant's manifest-declared source_bpmn + source_bpmn_sha256; no new compliant process was authored
- Scoring denominator: 60 items = 30 control (compliant) + 30 variant, so precision, recall, F1 and compliant specificity all have a denominator
