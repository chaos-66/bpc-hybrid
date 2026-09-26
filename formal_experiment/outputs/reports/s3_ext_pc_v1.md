# S3.9-EXT-PC-V1 bounded mechanism diagnosis

**Status:** development-only AI-constructed mechanism evidence; not a formal benchmark, unseen test, or human Gold.

## Semantics

- Prohibition v1: `FORBID(A)`; violation iff A is an executable activity reachable from a start node.
- Necessary-precondition v1: `A only if C`; violation iff A remains reachable after removing all C-enforcing sequence-flow edges.
- Legacy target name `required_condition_not_enforced` is retained only as a compatibility field; the semantic subtype is `necessary_precondition_bypass_v1`.

## Metrics

| Family | Pos TP | Pos FN-observed | Pos FN-unknown | Neg TN | Neg FP | Neg unknown | Precision | Recall | F1 | Coverage | Pair success |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| prohibition | 5 | 0 | 0 | 5 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 5/5 |
| necessary_precondition | 5 | 0 | 0 | 5 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 5/5 |

- 10-pair total pair success: **10/10**
- Overall coverage: **1.0**
- Positive unknown: **0/10**
- Negative unknown: **0/10**

## Counterexamples (non-scoring)

| Case | Expected | Actual applicability | Actual decision | Matched | Reason |
|---|---|---|---|---|---|
| CE1 | not_applicable | not_applicable | None | True | absence_of_obligation_not_prohibition |
| CE2 | not_applicable | not_applicable | None | True | permission_not_prohibition |
| CE3 | not_applicable | not_applicable | None | True | rule_applicability_not_process_action_prohibition |
| CE4 | not_applicable | not_applicable | None | True | trigger_obligation_not_necessary_precondition |
| CE5 | unsupported | unsupported | None | True | conditional_prohibition_outside_v1 |
| CE6 | unsupported | unsupported | None | True | unsupported_bpmn_fragment:parallelGateway |

## Failure / unknown cases

- none

## Legacy 20-case semantic disposition

```json
{
  "eligible_for_new_v1_semantics_but_requiring_canonical_action_rebinding": 2,
  "historical_target_counts": {
    "prohibited_action_present": 10,
    "required_condition_not_enforced": 10
  },
  "new_v1_eligibility_counts": {
    "eligible_for_new_v1_semantics": 2,
    "not_applicable": 18
  },
  "old_required_condition_pairs_reused": 0,
  "semantic_relation_assessment_counts": {
    "direct_unconditional_action_prohibition": 2,
    "legal_effect_or_state": 4,
    "rule_applicability": 4,
    "trigger_obligation_C_implies_OA": 10
  },
  "total": 20
}
```

## Existing real extraction linkage (Table B)

Separate from the mechanism table; no new API calls and no overall method ranking.
- `gdpr_article22_s001`: projection `right_or_prohibition_ambiguous_not_v1_direct`
  - direct_llm: modality=['obligation'], action_binding=unresolved_no_exact_normalized_gdpr7_activity, checker=not_applicable (right_or_prohibition_ambiguous_not_v1_direct)
  - sun_rule_only: modality=['obligation'], action_binding=unresolved_no_exact_normalized_gdpr7_activity, checker=not_applicable (right_or_prohibition_ambiguous_not_v1_direct)
- `gdpr_article22_s002`: projection `rule_applicability_not_necessary_precondition`
  - direct_llm: modality=['prohibition'], action_binding=unresolved_no_exact_normalized_gdpr7_activity, checker=not_applicable (rule_applicability_not_necessary_precondition)
  - sun_rule_only: modality=['prohibition'], action_binding=unresolved_no_exact_normalized_gdpr7_activity, checker=not_applicable (rule_applicability_not_necessary_precondition)
- `gdpr_article33_s001`: projection `trigger_obligation_not_necessary_precondition`
  - direct_llm: modality=['obligation'], action_binding=unresolved_no_exact_normalized_gdpr7_activity, checker=not_applicable (trigger_obligation_not_necessary_precondition)
  - sun_rule_only: modality=['obligation'], action_binding=unresolved_no_exact_normalized_gdpr7_activity, checker=not_applicable (trigger_obligation_not_necessary_precondition)
- `gdpr_article6_s001`: projection `necessary_precondition_conservative_projection`
  - direct_llm: modality=['obligation'], action_binding=unresolved_no_exact_normalized_gdpr7_activity, checker=unknown (action_binding_unresolved_or_ambiguous)
  - sun_rule_only: modality=['obligation'], action_binding=unresolved_no_exact_normalized_gdpr7_activity, checker=unknown (action_binding_unresolved_or_ambiguous)

## Constraint / exception capability boundary

{
  "constraint_chain": {
    "constraint_heterogeneity": [
      "time",
      "amount",
      "quantity",
      "purpose",
      "legal_reference"
    ],
    "correct_interpretation": "mapping error plus decision-guard repair; not evidence that the LLM cannot perform temporal reasoning.",
    "heterogeneity_statement": "These are different predicates; a single similarity formula is not claimed to solve all constraints.",
    "historical_item": "syn_v2_exception_not_handled_06",
    "side": "control",
    "six_categories": {
      "decision_semantics_error": "the old checker treated absence of a time bound on the wrongly anchored node as a violation; v5 guard demoted this to unknown",
      "evaluation_limitation": "deadline compliance cannot be established from this process slice without start-event/time semantics",
      "extraction_error": "not the primary cause in this chain; the rule fields contain an explicit 72-hour constraint",
      "mapping_error": "verified: the action grounder bound 'notify the personal data breach' to the exception-handler node",
      "process_information_missing": "ordinary BPMN task order/text does not prove whether the clock starts at breach occurrence, discovery, awareness, or internal case opening",
      "representation_insufficiency": "the six-element Rule Record does not encode the temporal anchor/origin of the 72-hour clock"
    }
  },
  "exception_chain": {
    "conclusion": "This is a joint extraction/representation/mapping issue, not an 'LLM cannot reason' claim or a general unobservability excuse.",
    "historical_item": "syn_v2_exception_not_handled_02",
    "logical_warning": "E -> not O(A) does not entail E -> FORBID(A); voluntarily performing A while E holds is not automatically a violation.",
    "requires": [
      "whether E holds",
      "which obligation E targets",
      "its effect on the path",
      "priority relations with other rules"
    ],
    "side": "variant",
    "six_categories": {
      "decision_semantics_error": "absence of a matched handler must not be promoted to a violation without actionable exception semantics",
      "evaluation_limitation": "current process and schema cannot support a determinate exception verdict",
      "extraction_error": "the historical action 'referred to' is not an executable activity label",
      "mapping_error": "the matcher could not bind 'referred to' to the process activity 'Communication with data subject'",
      "process_information_missing": "no dedicated handler structure was present in the frozen process",
      "representation_insufficiency": "the Rule Record does not encode exception scope, priority, or obligation target"
    }
  },
  "source": "outputs/evidence/s3_semantic_grounding_v5/constraint_exception_failure_chains.json"
}

## Paper method material and limitations

{
  "bounded_semantic_definition": "Direct unconditional prohibition over reachable executable BPMN activities; necessary precondition bypass by sequence-flow enforcement edges.",
  "cannot_claim": [
    "our method generalizes",
    "formal benchmark proves",
    "outperforms Sun",
    "outperforms Winter",
    "first to",
    "new five-type Table 3"
  ],
  "failure_example": null,
  "formula": "V_proh = exists a in B_A: Reach_G(S,a); bypass = Reach_G_without_E_C(S,a).",
  "limitation_statement": "This is development evidence on AI-constructed mechanism cases; it does not establish generalization to unseen legal text or full BPMN semantics.",
  "mechanism_result": {
    "by_family": {
      "necessary_precondition": {
        "all_denominators": {
          "coverage_denominator_eligible_sides": 10,
          "negative_total": 5,
          "positive_total": 5,
          "precision_denominator_tp_plus_fp": 5,
          "recall_denominator_positive_total": 5
        },
        "coverage": 1.0,
        "decided": 10,
        "eligible": 10,
        "f1": 1.0,
        "negative": {
          "fp": 0,
          "negative_unknown": 0,
          "tn": 5,
          "total": 5
        },
        "negative_unknown_rate": 0.0,
        "pair_success": 5,
        "pair_total": 5,
        "positive": {
          "fn_observed_negative": 0,
          "fn_unknown": 0,
          "total": 5,
          "tp": 5
        },
        "positive_unknown_rate": 0.0,
        "precision": 1.0,
        "recall": 1.0
      },
      "prohibition": {
        "all_denominators": {
          "coverage_denominator_eligible_sides": 10,
          "negative_total": 5,
          "positive_total": 5,
          "precision_denominator_tp_plus_fp": 5,
          "recall_denominator_positive_total": 5
        },
        "coverage": 1.0,
        "decided": 10,
        "eligible": 10,
        "f1": 1.0,
        "negative": {
          "fp": 0,
          "negative_unknown": 0,
          "tn": 5,
          "total": 5
        },
        "negative_unknown_rate": 0.0,
        "pair_success": 5,
        "pair_total": 5,
        "positive": {
          "fn_observed_negative": 0,
          "fn_unknown": 0,
          "total": 5,
          "tp": 5
        },
        "positive_unknown_rate": 0.0,
        "precision": 1.0,
        "recall": 1.0
      }
    },
    "failed_or_nonideal_cases": [],
    "overall": {
      "coverage": 1.0,
      "decided_sides": 20,
      "eligible_sides": 20,
      "negative_total": 10,
      "negative_unknown_count": 0,
      "pair_success": 10,
      "pair_success_rate": 1.0,
      "pair_total": 10,
      "positive_total": 10,
      "positive_unknown_count": 0
    }
  },
  "supported_fragment": "flat, acyclic BPMN fragment with start/end events, executable activities, sequence flows, XOR gateways and explicit conditionExpression / guarded flow labels."
}

## Isolation and safety

- real_api_calls=0
- network_experiment_calls=0
- gold_status=AI_constructed_development_not_gold
- Main paper-facing Table 3, Table 1 and Table 2 are unchanged by this task.
