# Stage 3 Sun-protocol realignment audit v1

Status: protocol-reconstruction audit, zero API, zero new inference.
Source of record: Sun et al. (2024), *Design-time business process compliance assessment based on multi-granularity semantic information*, DOI `10.1007/s11227-023-05626-0`.

## 1. Source of truth

The audit was written after reading the local final-version text at:

- `references/papers/Sun_2024_Design_time_BPC.pdf`
- `references/papers/extracted/sun_2024_full_text.txt`
- `references/papers/extracted/sun_2024_paper_evidence.json`

The following Sun anchors are used throughout:

| Sun anchor | Local location | What it fixes |
|---|---|---|
| Three-stage pipeline | §4, lines 193-226 of extracted text | Stage 1 disassembly -> Stage 2 rule base -> Stage 3 multiple violation detection |
| Definition 1 / Process Model | §3.1, lines 144-159 | `m=(A_m,E_m,G_m,R_m,N_m,F_m,L_m,u_m,t_m,f_m)`; `f_m` associates actors to activities/events |
| Definition 3 / Rule Base | §3.1, lines 167-173 | `r=(t_r,A_r,P_r,C_r,O_r,E_r,U_r,f_r)`; `U_r subset A_r x A_r`; `f_r:P_r->A_r` |
| Definition 4 / Matching Score | §4.3, lines 523-539 | action map `D_{r,m}` and actor/business-object map `O_{r,m}`, threshold `tau` |
| Definition 5 / Missing Action | §4.3, lines 540-548 | missing-action ratio over rule actions using `gamma` |
| Definition 6 / Incorrect Actor | §4.3, lines 549-559 | `R_{r,m,gamma}` rule actors with matched action; `C_{r,m,gamma}` process actors for the same action; threshold `theta` |
| Definition 7 / Out-of-order | §4.3, lines 560-585 | uses the real rule-side relation `U_r`; no relation means no order denominator |
| §5.3.1 Matching evaluation | lines 784-833 | per-model AP and MAP over ranked rule records |
| §5.3.2 Checking evaluation | lines 836-922 | base process supplemented to fully compliant; single mutation variants; four models; Table 12 P/R/F1 |

## 2. Sun Stage 3 input and data flow

Sun Stage 3 consumes:

1. a current process model `m` represented by Definition 1, including activities/events, actor/resource information, business objects, and control flow `F_m`;
2. the full rule base `R`, where each rule record follows Definition 3.

It does **not** consume a pre-selected `rule_id`, a mutation target, a mutation type, or a pair role. The whole matching step exists precisely to decide which rule records are strongly associated with the current model.

Reconstructed flow:

```text
current BPMN / Process Record
+ full Rule Base
        |
        v
Definition 4 matching and ranking
        |
        v
strongly associated rule records
        |
        v
Definition 5/6/7 checking
        |
        v
violation predictions
```

## 3. Definition 4 matching

For each `(r,m)` pair:

- `D_{r,m}` maps every rule action `a_r in A_r` to the process action/event action `a_m` with highest similarity.
- `O_{r,m}` maps every rule actor in `P_r` to the process actor/resource or business object with highest similarity.
- The matching score is the maximum of:
  - the fraction of `D_{r,m}` entries with `sim(a_r,a_m) > tau`,
  - the fraction of `O_{r,m}` entries with `sim(o_r,o_m) > tau`.
- Rules are ranked by this matching score. The strongly associated rules are the ones that enter Def. 5-7.

Current project implementation is essentially this shape in:

- `formal_experiment/src/bpc_hybrid/sun_stage3/sun_scorer.py` (`SunScorer.matching_score`)
- `formal_experiment/src/bpc_hybrid/sun_stage3/sun_model.py` (`SunProcessModel`)

The v2 runner, however, bypassed the full-rule-base ranking by selecting `item["rule_id"]` for each item and checking only that rule. That is a protocol deviation, because the benchmark item's `rule_id` is the mutation Gold.

## 4. Definition 5/6/7 field consumption

| Definition | Rule fields consumed | Process fields consumed | Current code |
|---|---|---|---|
| Def. 5 Missing Action | `A_r` rule actions; `gamma` | process actions/events and their highest-similarity mapping | `SunScorer.missing_action` |
| Def. 6 Incorrect Actor | `P_r`, `f_r` actor-action relation; `gamma`, `theta` | `f_m` actor/activity ownership and business objects; process actions matched to rule actions | `SunScorer.incorrect_actor` |
| Def. 7 Out-of-order | `U_r` real rule-side sequential relation; `gamma` | process reachability/control flow `F_m` | `SunScorer.out_of_order` |

Important consequence: if `U_r` is empty, Definition 7 has no denominator. The current frozen Sun Rules-Only and Direct-LLM capsules both have `order_relations=[]` for all 9 rules. Therefore order violation cannot be evaluated from the present rule bases without inventing a relation.

## 5. Sun §5.3.2 benchmark construction

Sun's checking experiment does the following:

1. starts from real BPMN process models;
2. parses regulatory documents into a rule base;
3. runs rule-process matching;
4. supplements the process model so that it is fully compliant for the matched rules;
5. manually generates one-error variants:
   - missing action: delete an activity;
   - incorrect actor: change the actor;
   - out-of-order: swap activities;
6. each checking instance contains exactly one violation;
7. the complete pipeline checks the current process model plus full rule base;
8. reports Precision / Recall / F-score.

The current `stage3_paired_benchmark_v1` faithfully reuses the one-error mutation idea, but its controls are the **unmutated Winter/GDPR source BPMNs**, not Sun's supplemented fully compliant models. Its Gold is also single-target: it records which target mutation was injected, but it does not provide a complete multi-label compliance annotation for every rule in the 9-rule base.

## 6. How Sun compares Winter

Sun §5.3.2 states that Winter et al. (2020) uses keyword sentence typing and checks all clauses without phrase-level filtering. Sun's Table 12 compares the complete methods:

| Method | Precision | Recall | F-score |
|---|---:|---:|---:|
| Winter et al. (2020) | 0.58 | 0.89 | 0.70 |
| Sun method | 0.77 | 0.83 | 0.80 |

The causal comparison for this paper is narrower: Sun and Ours share Stage 1 and Stage 3, and differ only in the Stage-2 Rule Base. Winter is an independent predecessor pipeline, not a "Winter Stage 2 + Sun Stage 3" hybrid.

## 7. Deviations of current v1/v2 from Sun's Stage 3

### v1 (`stage3_table3_v1`)

- Ours used a custom automatic grounding/control-difference detector.
- The detector consumed the pair control BPMN and target activity/lane.
- The old Ours F1=1.0 was therefore leakage, not semantic compliance checking.
- v1 is retained only as a leakage diagnostic and is permanently retracted as a main result.

### v2 (`stage3_table3_v2`)

- Inference still received the item's correct `rule_id`.
- It checked only that target rule for that item.
- It scored the target check only; non-target alarms were marked unevaluated.
- Matching was therefore not part of the scored pipeline.
- v2 is retained as a repaired target-pair diagnostic, not the final full-pipeline Table 3.

## 8. Which existing code/data are reusable

Reusable as-is or with small adapters:

- `src/bpc_hybrid/stage1_process.py` for the shared BPMN -> Process Record stage;
- `src/bpc_hybrid/sun_stage3/sun_model.py` and `sun_scorer.py` for Def. 4-7;
- `src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py` for both Stage-2 capsules;
- `data/predictions/gdpr7_sun_rule_only_v1/predictions.json`;
- `data/predictions/gdpr7_direct_llm_v1/predictions.json`;
- `data/input/gdpr7_stage2_input_v1.json` (full 9-rule GDPR rule base and 74 clause texts);
- `data/development/stage3_synth/synthetic_controlled_error_extension_v1.json` (mutation provenance);
- `data/development/stage3_synth/stage3_paired_benchmark_eligibility_v1.json` (valid target seeds);
- Winter Stage-3 wrapper under `src/bpc_hybrid/winter_stage3/`.

## 9. What must be superseded

- v1 automatic grounding as a main method;
- v1 Oracle/grounded upper bound as an Ours arm;
- v2 target-rule-scoped inference as the main Table 3 protocol;
- any target activity id / expected lane / mutation type / role / Gold violation type entering inference;
- any result-driven threshold change;
- any attempt to manufacture out-of-order Gold when `U_r` is empty.

## 10. Minimal repair required

The minimal Sun-style repair is:

1. create a Gold-blind case view containing only `case_id`, `bpmn_path`, `process_id`;
2. run each case through the full 9-rule Rule Base;
3. rank all rules with `SunScorer.matching_score` and apply the frozen `tau=0.8`;
4. run Def. 5-7 only on the associated rules;
5. persist all matching and violation outputs before the evaluator reads any label;
6. run Winter as an independent full pipeline over the same BPMN and full regulatory text scope;
7. evaluate matching AP/MAP separately;
8. evaluate checking P/R/F1 only on pairs whose target seed has independent construction evidence and a valid denominator;
9. mark out-of-order unavailable because all frozen rule records lack `U_r`;
10. record control-compliance scope and all exclusions explicitly.

## 11. Data limits found by this audit

- The paired benchmark is a valid **single-mutation construction** source, but it is not a complete multi-label compliance Gold.
- The original BPMNs are unmutated Winter/GDPR reference models; they are not Sun's manually supplemented fully compliant models.
- The mutation manifest and the human binding reference independently support the target seed's action/actor compliance for 13 eligible pairs (8 missing-action and 5 incorrect-actor).
- No eligible out-of-order pair exists: all order mutations are process-only and no rule record has a real `U_r` relation.
- Therefore v3 must evaluate the labeled target seeds after full matching and must report additional unmatched alarms separately; it cannot claim a complete multi-label Gold.
- This limit is a benchmark-validity gate, not a model-tuning opportunity.

## 12. Required audit answers

1. **Sun Stage 3 input**: current Process Record + full Rule Base; no Gold `rule_id`.
2. **Rule Base entry**: full Definition 3 records per rule, including `A_r`, `P_r`, `U_r`, `f_r`.
3. **Definition 4**: highest-similarity action mapping and actor/business-object mapping, max of the two `>tau` fractions.
4. **Def. 5/6/7 fields**: `A_r`; `P_r`/`f_r`; `U_r`; plus the process-side action/event, actor/business-object, and control-flow reachability fields listed above.
5. **Sun §5.3.2 benchmark**: real BPMNs, full rule base matching, supplemented fully-compliant base, one-error variants, one violation per checking instance, P/R/F.
6. **Winter comparison**: an independent predecessor pipeline; Sun reports Winter as a baseline, not as a Stage-2-only replacement.
7. **Current v1/v2 deviations**: v1 control leakage and target-aware detection; v2 correct-rule targeting and target-check scoring without full matching.
8. **Reusable code**: Stage 1 parser, SunProcessModel/SunScorer, capsule converter, Winter wrapper, persisted Stage-2 capsules, mutation manifest, eligibility audit.
9. **Supersede**: v1 automatic grounding, Oracle as Ours, v2 main-route target-check inference, hidden Gold/target fields, threshold tuning, invented order Gold.
10. **Minimal fix**: blinded v3 case view, shared full-rule-base checker, persisted Gold-blind predictions, separate evaluator, matched AP/MAP, checking on valid seeds, Winter independent arm, explicit exclusions and tests.

## 13. Commit boundary

This audit changes no executable behavior. It is the required first-phase record before `stage3_table3_v3` code and data preparation.
