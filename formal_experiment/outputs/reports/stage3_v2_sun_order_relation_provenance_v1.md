# Sun U_r Order-Relation Provenance Audit v1

- status: `SUN_U_R_PROVENANCE_RESOLVED`
- sun_u_r_provenance: `PAPER_NATIVE_EXPLICIT, PAPER_UNDERSPECIFIED, CURRENT_INTERFACE_MISSING`
- order_implementation_gate: `CASE_3_PAPER_OR_DATA_INSUFFICIENT` / `ORDER_IMPLEMENTATION_BLOCKED=true`

## Direct Answers
- **is_current_project_missing_it**: Yes. The schema has an order_relations placeholder but both frozen Stage2 predictions contain zero non-empty order relations, and the five development TYPE-A requirements have zero derivable existing-action endpoints for the temporal marker.
- **is_it_automatically_extracted**: PAPER_UNDERSPECIFIED. The paper says extracted but gives no extraction rule, algorithm, code, or released artifact.
- **is_it_experiment_metadata**: No. The paper separates U_r (rule-side sequential constraint) from out-of-order BPMN mutations (swapped activity positions). Current benchmark order_pair/tasks are experiment construction metadata and must not be used to build U_r.
- **is_it_part_of_stage2**: Formally yes, it is part of the Rule Record produced before Stage 3. In the current project, Stage 2 canonical records have an empty order_relations field in practice.
- **what_exactly_is_u_r**: U_r is a binary sequential relation over rule actions, U_r subseteq A_r x A_r, stored in the Rule Record and consumed by Definition 7.
- **where_does_it_come_from**: The paper says it is a sequential constraint extracted from the Rule Record. The exact source field and extraction algorithm are PAPER_UNDERSPECIFIED.
- **who_constructs_it**: The paper names no component. It is implicit in Regulatory Documents Parsing / Rule Base Construction (Stage 2), not Stage 3 and not experiment mutation construction.

## Paper Evidence
### definition_3_rule_record
- section: 3.1 Definition 3
- page: 5
- evidence line hint: 168
> where each r in R is denoted as r = (t_r, A_r, P_r, C_r, O_r, E_r, U_r, f_r) ... U_r in A_r x A_r indicates the sequential relationship between the actions and a partial function f_r : P_r -> A_r that specifies which actors must execute certain actions.

U_r is a native Rule Record member typed as a binary relation over actions. This is paper-native explicit representation.

### section_4_2_six_concepts
- section: 4.2.2 Phrase-level: Semantic Classification
- page: 11
- evidence line hint: 399
> we first design six specific semantic concepts from the rules, i.e., modality, actor, action, condition, constraint, exception

The paper describes six semantic extraction concepts. U_r is not among them and no seventh order-relation extraction rule is provided.

### section_4_2_action_rule
- section: 4.2.2 Action
- page: 12
- evidence line hint: 458
> The single rule for action detects every verb phrase (VP) encountered, except those contained in modality, condition, constraint and exception.

A_r is defined by VP extraction. Nominalizations such as processing are not VPs under this stated rule unless the parser admits them, and no nominalization allowance is stated.

### section_4_2_constraint_rule
- section: 4.2.2 Constraint and Table 4
- page: 12
- evidence line hint: 470
> Constraints usually exist in the form of phrases ... NP <(constraint marker); PP <(IN <(constraint marker)) $ NP. Table 4: before, after, at least, at most, equal to, greatest, smallest, last of, least of ...

Temporal markers before/after are treated as constraint markers. This is the only textual clue for order origin, but no rule turns a temporal Constraint plus A_r actions into U_r.

### definition_7_order_violation
- section: 4.3 Definition 7
- page: 14
- evidence line hint: 560
> where (u_r, u'_r) in U_r is a sequential constraint extracted from the rule record ... U_{r,m,gamma} indicates that the similarity between the rule record and the operation in the process model is equivalent when the similarity is greater than the threshold gamma.

The paper says U_r is extracted from the Rule Record but does not specify the source field, algorithm, or endpoint-selection policy.

### section_5_3_2_mutation_construction
- section: 5.3.2 Evaluation of Checking
- page: 20
- evidence line hint: 845
> For the out-of-order execution violation, the positions between activities are swapped. Each checking contains only one violation.

The paper explains BPMN variant construction, not U_r construction. This is experiment-side mutation metadata and must not be fed into Stage 3 relation extraction.

### case_study_r2
- section: 5.3.2 case study Table 13
- page: 22
- evidence line hint: 947
> R2 ... After receiving the customer's personal information, it is necessary to verify the correctness of their personal information. ... For the rule with R2, we detected the out-of-order execution violation.

The only out-of-order case study involves an event-like trigger phrase and an action, consistent with TYPE B trigger precedence as much as TYPE A action-action precedence, reinforcing that U_r construction is underspecified.

### availability_no_code
- section: Availability of supporting data
- page: 26
- evidence line hint: 1018
> The datasets generated during and/or analysed during the current study are available from the corresponding author on reasonable request.

No code repository, extractor, rule file, or U_r artifact is released. Construction cannot be recovered from the paper alone.

## Current Interface Audit

| Method | Clauses | order_relations | Non-empty clauses | Temporal constraints |
|---|---:|---:|---:|---:|
| ours | 36 | 0 | 0 | 8 |
| sun | 37 | 0 | 0 | 13 |

Development TYPE-A requirements: R5-D-01, R5-D-02, R5-D-03, R5-D-04, R5-D-05.

Evaluation uses 15 scored TYPE-A cells per method: 5 positive variants and 10 negative controls. The diagnostic order rows cover the 5 baseline plus 5 out-of-order variants; the additional 5 negative controls are incorrect-actor variants whose out_of_order reference state is satisfied.

The current projection requires both endpoints to be already-validated Stage-2 actions. It generated **0** U_r relations for both methods across all 15 scored cells. The missing after-endpoint is nominalized or lies inside a temporal constraint phrase.

## Order Metrics

| Method | TYPE-A Order F1 | TP | FP | FN | TN | U_r generated | U_r absent | Scored cells |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ours | 0.0000 | 0 | 0 | 5 | 0 | 0 | 15 | 15 |
| sun | 0.0000 | 0 | 0 | 5 | 0 | 0 | 15 | 15 |

## Conclusion

It is both an interface gap and an evidence gap. The interface gap is real (Stage2 passes zero order_relations). It cannot be repaired paper-faithfully because the paper does not specify U_r construction and benchmark endpoints are not demonstrably A_r under the paper action rule.

Order implementation is **BLOCKED_ON_EVIDENCE**. No sample-specific rewrite, expected-BPMN target, mutation metadata, or Gold-informed relation was used.
