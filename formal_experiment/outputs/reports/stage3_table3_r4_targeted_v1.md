# Stage 3 Table 3 R4 Targeted Fix Delivery

- status: `development_retrospective_not_independent_test_complete`
- development/retrospective; not independent test or formal Table-3 acceptance.
- API calls: 0; Winter reused from R2, not rerun.

## M1 vs R4 metrics

| Config | Method | TP | FP | FN | TN | P | R | F1 | Coverage | Unknown+ | Unknown- | N/A |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| m1 | sun | 8 | 14 | 7 | 9 | 0.3636 | 0.5333 | 0.4324 | 0.6400 | 6 | 12 | 10 |
| m1 | ours | 7 | 13 | 8 | 6 | 0.3500 | 0.4667 | 0.4000 | 0.5200 | 8 | 16 | 10 |
| m1 | winter | 7 | 6 | 8 | 19 | 0.5385 | 0.4667 | 0.5000 | 0.7000 | 5 | 10 | 10 |
| r4 | sun | 8 | 14 | 7 | 11 | 0.3636 | 0.5333 | 0.4324 | 0.7000 | 5 | 10 | 10 |
| r4 | ours | 6 | 9 | 9 | 14 | 0.4000 | 0.4000 | 0.4000 | 0.6400 | 6 | 12 | 10 |
| r4 | winter | 7 | 6 | 8 | 19 | 0.5385 | 0.4667 | 0.5000 | 0.7000 | 5 | 10 | 10 |

## Per-type R4 counts

| Method | Type | TP | FP | FN | TN | Unknown+ | Unknown- | N/A | P | R | F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sun | missing_action | 3 | 6 | 2 | 9 | 0 | 0 | 0 | 0.3333 | 0.6000 | 0.4286 |
| sun | incorrect_actor | 4 | 8 | 1 | 0 | 1 | 2 | 5 | 0.3333 | 0.8000 | 0.4706 |
| sun | out_of_order | 1 | 0 | 4 | 2 | 4 | 8 | 5 | 1.0000 | 0.2000 | 0.3333 |
| ours | missing_action | 2 | 3 | 3 | 12 | 0 | 0 | 0 | 0.4000 | 0.4000 | 0.4000 |
| ours | incorrect_actor | 3 | 6 | 2 | 0 | 2 | 4 | 5 | 0.3333 | 0.6000 | 0.4286 |
| ours | out_of_order | 1 | 0 | 4 | 2 | 4 | 8 | 5 | 1.0000 | 0.2000 | 0.3333 |
| winter | missing_action | 3 | 6 | 2 | 9 | 0 | 0 | 0 | 0.3333 | 0.6000 | 0.4286 |
| winter | incorrect_actor | 4 | 0 | 1 | 10 | 0 | 0 | 5 | 1.0000 | 0.8000 | 0.8889 |
| winter | out_of_order | 0 | 0 | 5 | 0 | 5 | 10 | 5 | null | 0.0000 | 0.0000 |

## Decision changes M1 -> R4

| Method | Case | Rule | Type | Ref | M1 | R4 | New raw reason / diagnostic |
|---|---|---|---|---|---|---|---|
| ours | case_0adc59ea1a26 | article36p1 | missing_action | violated | violated | satisfied | None |
| ours | case_0f7180438501 | article14p4 | missing_action | violated | violated | satisfied | None |
| ours | case_3d2aaae29b37 | article14p4 | missing_action | satisfied | violated | satisfied | None |
| ours | case_44fc51ad7da0 | article14p4 | missing_action | satisfied | violated | satisfied | None |
| ours | case_89c44a45c04d | article18p3 | incorrect_actor | satisfied | unknown | violated | None |
| ours | case_89c44a45c04d | article18p3 | missing_action | satisfied | violated | satisfied | None |
| ours | case_89c44a45c04d | article18p3 | out_of_order | satisfied | unknown | satisfied | reachability_satisfied |
| ours | case_8cbb7ad90a6d | article18p3 | incorrect_actor | satisfied | unknown | violated | None |
| ours | case_8cbb7ad90a6d | article18p3 | missing_action | satisfied | violated | satisfied | None |
| ours | case_8cbb7ad90a6d | article18p3 | out_of_order | violated | unknown | violated | reachability_violated |
| ours | case_d038f52f8cf3 | article18p3 | incorrect_actor | violated | unknown | violated | None |
| ours | case_d038f52f8cf3 | article18p3 | missing_action | satisfied | violated | satisfied | None |
| ours | case_d038f52f8cf3 | article18p3 | out_of_order | satisfied | unknown | satisfied | reachability_satisfied |
| ours | case_d8a82d59687d | article35p1 | missing_action | violated | violated | satisfied | None |
| ours | case_f8aaa652c17b | article14p4 | missing_action | satisfied | violated | satisfied | None |
| sun | case_0adc59ea1a26 | article36p1 | missing_action | violated | violated | satisfied | None |
| sun | case_0f7180438501 | article14p4 | missing_action | violated | satisfied | violated | None |
| sun | case_3d2aaae29b37 | article14p4 | missing_action | satisfied | satisfied | violated | None |
| sun | case_44fc51ad7da0 | article14p4 | missing_action | satisfied | satisfied | violated | None |
| sun | case_5c2cca2ca4cf | article13p3 | incorrect_actor | violated | violated | unknown | action_mapping_below_gamma |
| sun | case_89c44a45c04d | article18p3 | incorrect_actor | satisfied | unknown | violated | None |
| sun | case_89c44a45c04d | article18p3 | missing_action | satisfied | violated | satisfied | None |
| sun | case_89c44a45c04d | article18p3 | out_of_order | satisfied | unknown | satisfied | reachability_satisfied |
| sun | case_8cbb7ad90a6d | article18p3 | incorrect_actor | satisfied | unknown | violated | None |
| sun | case_8cbb7ad90a6d | article18p3 | missing_action | satisfied | violated | satisfied | None |
| sun | case_8cbb7ad90a6d | article18p3 | out_of_order | violated | unknown | violated | reachability_violated |
| sun | case_9a62a7fd9853 | article13p3 | incorrect_actor | satisfied | violated | unknown | action_mapping_below_gamma |
| sun | case_d038f52f8cf3 | article18p3 | incorrect_actor | violated | unknown | violated | None |
| sun | case_d038f52f8cf3 | article18p3 | missing_action | satisfied | violated | satisfied | None |
| sun | case_d038f52f8cf3 | article18p3 | out_of_order | satisfied | unknown | satisfied | reachability_satisfied |
| sun | case_d8a82d59687d | article35p1 | missing_action | violated | violated | satisfied | None |
| sun | case_f8aaa652c17b | article14p4 | missing_action | satisfied | satisfied | violated | None |
| sun | case_fd4b197b953b | article13p3 | incorrect_actor | satisfied | violated | unknown | action_mapping_below_gamma |

## article18p3 chain

### correct_order_control (`case_89c44a45c04d`)

- sun: M1=unknown, R4=satisfied, gamma=0.8, theta=0.8
  - before: original `be informed by the controller`; action_surface `informed`; R4 selected `Activity_1` score `1.0000`; M1 selected `Start` score `0.7320`
  - after: original `the restriction of processing is lifted`; action_surface `lifted`; R4 selected `Activity_2` score `1.0000`; M1 selected `Activity_2` score `1.0000`
- ours: M1=unknown, R4=satisfied, gamma=0.8, theta=0.8
  - before: original `be informed`; action_surface `informed`; R4 selected `Activity_1` score `1.0000`; M1 selected `Start` score `0.7320`
  - after: original `the restriction of processing is lifted`; action_surface `lifted`; R4 selected `Activity_2` score `1.0000`; M1 selected `Activity_2` score `1.0000`

### reverse_order_mutation (`case_8cbb7ad90a6d`)

- sun: M1=unknown, R4=violated, gamma=0.8, theta=0.8
  - before: original `be informed by the controller`; action_surface `informed`; R4 selected `Activity_1` score `1.0000`; M1 selected `Start` score `0.7320`
  - after: original `the restriction of processing is lifted`; action_surface `lifted`; R4 selected `Activity_2` score `1.0000`; M1 selected `Activity_2` score `1.0000`
- ours: M1=unknown, R4=violated, gamma=0.8, theta=0.8
  - before: original `be informed`; action_surface `informed`; R4 selected `Activity_1` score `1.0000`; M1 selected `Start` score `0.7320`
  - after: original `the restriction of processing is lifted`; action_surface `lifted`; R4 selected `Activity_2` score `1.0000`; M1 selected `Activity_2` score `1.0000`

## Actor evidence and diagnostic counterfactual

- M1 Sun actor false-positive rows: 8
- R4 actor false-positive rows: 14
- m1/sun: observable=22, changed=0, business_object_was_minimum=0, empty_remaining_C=0
- m1/ours: observable=6, changed=0, business_object_was_minimum=0, empty_remaining_C=0
- r4/sun: observable=46, changed=0, business_object_was_minimum=4, empty_remaining_C=0
- r4/ours: observable=22, changed=0, business_object_was_minimum=4, empty_remaining_C=0

## Frozen Stage2 residual loss

- article13p3: raw contains actor=`True`, canonical actors=`[]`, canonical actor-action map=`[]`
- article14p4: raw contains actor=`True`, canonical actors=`[]`, canonical actor-action map=`[]`

## Ranking analysis

- supports Ours > Sun > Winter: `False`
- actual overall F1: `{'m1': {'sun': 0.43243243243243246, 'ours': 0.4, 'winter': 0.5}, 'r4': {'sun': 0.43243243243243246, 'ours': 0.4, 'winter': 0.5}}`
- R4 F1 order is winter=0.5000 > sun=0.4324 > ours=0.4000. The Ours-vs-Sun gap is not a threshold-tuning issue: per-type counts show Sun missing_action TP=3 FP=6 FN=2, Ours TP=2 FP=3 FN=3; Sun actor TP=4 FP=8 FN=1, Ours actor TP=3 FP=6 FN=2; order is identical (TP=1 FP=0 FN=4). Winter stays high because its actor TP=4 FP=0 FN=1, while Sun/Ours continue to lose actor cells to the the/Controller surface mismatch and frozen Stage2 losses.

## Classification

### A_interface_or_implementation
- R3 action comparison used action_surface + business_object_surface; R4 uses action_surface only on both sides.
- R3 mechanism-check entry point returned 0 regardless of failure; R4 check returns non-zero on contract/probe failure with an explicit self-test failure fixture.
- R3 backend selection normalized unknown values to sm; R4 entry point requires an explicit allowed --backend and records the actual loaded backend.
- R3 order-unknown reporting collapsed many causes into no_rule_order_endpoints; R4 keeps the raw reason and adds a precise diagnostic category without changing scores/denominators.
### B_frozen_stage2_real_prediction_errors
- Ours D1 article13p3/article14p4 raw response contains 'the controller' and actor-action maps, but the stored canonical record has actors=[] and actor_action_map=[]; R4 cannot repair that.
- Ours article13p3 action is fragmented into two predicted actions; article14p4 is a single long action; neither is repaired.
- Frozen rule/order extraction still has missing order relations for some rules; R4 only evaluates the saved relations.
### C_method_or_representation_limits
- action_surface-only cannot distinguish 'Archive the parcel' from 'Archive the invoice'; the mechanism fixtures retain this limitation and also test the correct-object-absent case.
- The existing actor normalizer leaves 'the controller'/'The controller' vs 'Controller' at raw similarity about 0.4272, below theta=0.8; R4 deliberately does not add a synonym/role normalization.
- Winter natively does not support before/prior-to relations; its out_of_order cells remain unknown and are reused from R2.
- Definition 6 C-scope has a literal-formula/prose ambiguity around business objects; R4 preserves the frozen union and reports a minimal discriminating example.
### D_evidence_gaps
- No unresolved evidence gap remains for the changed R4 cells: action mappings, candidate IDs, raw scores, gamma/theta, and order diagnostics are saved.
- The evaluation remains development/retrospective because the same data have been reused for multiple diagnostics; it is not independent test or formal Table-3 acceptance.

## Conclusions

### fixed_implementation_or_interface
- Sun/Ours action comparisons now use action_surface on both sides across Definitions 4, 5, 6 internal action gating, and 7.
- article18p3 order endpoints now map (before: informed/inform; after: lifted/lift), and correct/reverse model order is distinguished by reachability.
- Mechanism check now separates implementation-contract checks, behaviour probes, and known-limitation reproductions, and exits non-zero on failure.
- Backend selection is explicit and validated before scoring.
- Order-unknown diagnostics separate no edge, projection rejection (including multiple predicates), endpoint parse failure, missing model action field, below-gamma, other mapping/reachability, and Winter native unsupported.
### remaining_frozen_upstream_errors
- Ours article13p3/article14p4 actor and actor-action association loss after D1 canonicalization.
- Ours article13p3 fragmented action.
- Missing order relations in the frozen rule extraction for some rules.
### method_limitations
- Action-surface-only cannot reject same-verb/different-object candidates.
- Role strings such as 'the controller' and 'Controller' remain below theta without a normalization rule; R4 does not add one.
- Some rule actions are below gamma against all model action surfaces; R4 retains unknown rather than inventing actions.
- Winter native order checking remains unsupported for before/prior-to semantics.
### supported_by_current_data
- R4 increased Sun order coverage from 0.64 to 0.70 and produced TP=1 for out_of_order while keeping FP=0.
- R4 increased Ours order coverage from 0.52 to 0.64 and produced TP=1 for out_of_order while keeping FP=0.
- The mechanism check passes implementation contracts and behaviour probes in the synthetic development fixtures.
### not_supported_by_current_data
- Ours > Sun > Winter is not supported by the R4 overall F1 values.
- R4 does not make Sun/Ours actor detection generally correct; actor F1 remains 0.4706 for Sun and 0.4286 for Ours.
- R4 does not recover missing Stage2 actor/action information and should not be described as doing so.

## Validation

- `python -m pytest tests/test_stage3_r4_targeted_fix.py -q` -> exit `0`: 8 passed
- `python scripts/run_stage3_r4_mechanism_check.py --backend r4_sm --out-json outputs/reports/stage3_table3_r4_targeted_mechanism_v1.json --out-md outputs/reports/stage3_table3_r4_targeted_mechanism_v1.md` -> exit `0`: status=pass; 5/5 contract checks, 11/11 behaviour probes, 2/2 known limitations reproduced
- `python scripts/run_stage3_r4_mechanism_check.py --backend r4_sm --self-test-failure` -> exit `1`: deliberate failure fixture detected; non-zero exit code verified
- `python formal_experiment/scripts/audit_project.py` -> exit `0`: Integrity pass: True; ERRORS 0; BLOCKERS 0; WARNINGS 3
- `git -c core.whitespace=-blank-at-eof diff --cached --check` -> exit `0`: no material whitespace errors; only intentional blank-at-EOF lines in two historical run-time code files are exempted by the scoped config override
