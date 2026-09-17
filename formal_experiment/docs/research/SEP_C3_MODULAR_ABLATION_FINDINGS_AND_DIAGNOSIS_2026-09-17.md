# SEP-C3 Modular E/S/J Ablation: Findings and Diagnosis (2026-09-17)

- record_id: `SEP_C3_MODULAR_ABLATION_FINDINGS_AND_DIAGNOSIS_2026-09-17`
- status: `research_interpretation_layer_complete_offline`
- generated_at_utc: `2026-09-17T13:20:17.867843+00:00`
- starting_git_head: `18f5cf9ad79602c12315b21d6f54c56da5190580`
- network/LLM calls in this record: `0`
- scope: research interpretation layer over already-completed real API runs; no prediction, Gold, prompt, evaluator, or historical report was modified.

## 1. Original question and pre-experiment hypotheses

Do the E / S / J prompt components individually and jointly improve regulatory information extraction? E = synthetic worked examples; S = semantic interpretation rules; J = additional output organization / JSON discipline.

### Pre-experiment hypotheses (not conclusions)
- E has a positive contribution.
- S has a positive contribution.
- J has a positive contribution.
- Combining components may produce cumulative gains.
- The full configuration `111` may be better than simpler configurations.

### Explicit status
- The bullets above are pre-experiment hypotheses, not current conclusions. Some were weakened or contradicted by the completed full-8 experiment.

## 2. Formal full-8 results (frozen evaluator fields)

Primary metric: `coarse_five_field_mean_f1`; modality label metrics are reported separately and never mixed into span F1.

| descriptive rank | arm (E S J) | mean F1 | micro P | micro R | micro F1 | modality acc | modality macro-F1 | records scored | records failed | batch binding |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 1 0 0 | 0.778763 | 0.809380 | 0.821351 | 0.815321 | 0.813333 | 0.765254 | 150 | 0 | `current_implementation_binding` |
| 2 | 1 0 1 | 0.761056 | 0.837025 | 0.793028 | 0.814433 | 0.813333 | 0.755381 | 150 | 0 | `original_execution_binding` |
| 3 | 0 1 1 | 0.746955 | 0.777929 | 0.830065 | 0.803152 | 0.826667 | 0.763534 | 150 | 0 | `original_execution_binding` |
| 4 | 1 1 0 | 0.735539 | 0.777931 | 0.816993 | 0.796984 | 0.813333 | 0.748834 | 150 | 0 | `original_execution_binding` |
| 5 | 0 1 0 | 0.727790 | 0.772251 | 0.827887 | 0.799102 | 0.820000 | 0.752377 | 150 | 0 | `current_implementation_binding` |
| 6 | 1 1 1 | 0.726206 | 0.772989 | 0.808279 | 0.790240 | 0.820000 | 0.753538 | 150 | 0 | `original_execution_binding` |
| 7 | 0 0 0 | 0.636749 | 0.594657 | 0.710240 | 0.647330 | 0.773333 | 0.693765 | 150 | 0 | `current_implementation_binding` |
| 8 | 0 0 1 | 0.618356 | 0.603687 | 0.732026 | 0.661691 | 0.780000 | 0.706858 | 150 | 0 | `current_implementation_binding` |

### Per-field F1

| arm | actor | action | condition | constraint | exception |
|---|---:|---:|---:|---:|---:|
| 111 | 0.515814 | 0.928697 | 0.813301 | 0.741638 | 0.631579 |
| 011 | 0.513198 | 0.912782 | 0.830565 | 0.772349 | 0.705882 |
| 101 | 0.675725 | 0.928506 | 0.846796 | 0.687584 | 0.666667 |
| 110 | 0.477033 | 0.925033 | 0.822616 | 0.776958 | 0.676056 |
| 100 | 0.619375 | 0.925472 | 0.847156 | 0.724036 | 0.777778 |
| 010 | 0.490323 | 0.925788 | 0.856625 | 0.741212 | 0.625000 |
| 001 | 0.305538 | 0.828143 | 0.849158 | 0.472577 | 0.636364 |
| 000 | 0.278593 | 0.848051 | 0.842604 | 0.414498 | 0.800000 |

### Batch/time binding
- The original four cells `111/011/101/110` are `original_execution_binding` (SEP-C3-MODULAR-ESJ-001); the new four cells `000/001/010/100` are `current_implementation_binding` / `executed_incremental_batch` (SEP-C3-MODULAR-ESJ-002). Model, input, Gold, evaluator, and prompt composition are matched, but batch/time is confounded with cell membership.

### Parser / schema / canonicalization failures
- Canonical parser/schema/canonicalization failures: 0 records in all eight cells. Every arm produced 150/150 request_status=ok canonical predictions, 150/150 schema_valid=true, 150/150 cross_field_valid=true, and no validation errors. Raw response fence counts differ by arm and are recorded as raw-format diagnostics, not as canonical failures.

### Actual calls / resume metadata
- original_four_suite: suite_id=SEP-C3-MODULAR-ESJ-001; planned_calls=600; actual_calls_in_execution_summary=541; completed_samples=600; aborted=False; runtime_seconds=4329.388; arm 111 actual=91 + resumed=59; other three arms actual=150 each; all failed_count=0.
- new_four_suite: suite_id=SEP-C3-MODULAR-ESJ-002; planned_calls=600; actual_calls=600; completed_samples=600; resume_events=0; aborted=False; runtime_seconds=5292.487; budget_gate_calls_made=600; failed_count total=0.
- token/cost_original_four: input_tokens=915525; output_tokens=518029; cost_usd=3.25988784; missing_usage_calls=0
- token/cost_new_four: input_tokens=503023; output_tokens=559176; cost_usd=2.87832732; missing_usage_calls=0
- transparency_note: The original-four evidence execution summary records actual_calls=541 with 59 resumed completed samples for arm 111; the evidence manifest records actual_api_attempts_total=600 and duplicate_sample_sends=0. These fields are recorded verbatim as different counters/caps and must not be silently collapsed. The new four-cell batch records actual_calls=600 and completed_samples=600.

## 3. Unexpected / negative findings
### 4.1 Full prompt 111 is not the best configuration

Descriptive ranking: 100 > 101 > 011 > 110 > 010 > 111 > 000 > 001. `111` is not the highest cell; `100` is highest with mean F1 0.778763. The current data therefore do not support 'more modules is better' or 'full E+S+J is optimal'.

However, the old four cells (`111/011/101/110`) and the new four cells (`000/001/010/100`) are batch/time confounded. The cross-batch ranking is descriptive and cannot be written as strict causal proof.

- negative and non-monotonic ablation results are treated as findings, not discarded.
- `111` is not descriptively superior to several simpler configurations.

### 4.2 Single-factor deletions from 111 are anomalous

Within the old batch, deleting E (`111 -> 011`), deleting S (`111 -> 101`), and deleting J (`111 -> 110`) are all associated with higher mean F1 than `111`. This contradicts a simple additive positive-contribution hypothesis.

Old-batch paired analysis: `111_vs_011` E deletion increases mean F1 by 0.020750; `111_vs_101` S deletion increases by 0.034850; `111_vs_110` J deletion increases by 0.009333. The negative finding is preserved.

- Do not describe any module as universally useless; this is a single dataset/model/setting result.
- Do not describe the deletions as causal proof of harmful wording.

### 4.3 E and S each help alone, while their combination shows negative interaction

Same new batch: `100 - 000` is 0.142014, and `010 - 000` is 0.091041. E-only and S-only both show descriptive improvement over the common skeleton.

But `110 - 100` is -0.043224, and `111 - 101` is -0.034850. The E x S interaction signal is the dominant negative two-way effect.

This is consistent with redundancy, overlap, conditional interference, or instruction conflict. It is not proof that E and S semantically conflict. Paired error analysis and the prompt audit are required before stronger claims.

### 4.4 J shows no stable benefit under the shared baseline structured-output interface

`000` already retains the common skeleton, including the required schema/interface and coordinate discipline. Thus this experiment tests whether *additional* J output-organization/JSON-discipline instructions improve performance beyond the shared baseline interface.

Observed under the shared interface: J main effect is slightly negative (-0.006567); matched comparisons are mixed; `000/001/010/100` all yielded 150/150 canonical schema-valid and cross-field-valid records, with no canonical parser/schema/canonicalization failure. Without J, raw bare-JSON rates were lower (000: 114/150; 100: 146/150; 010: 149/150), but the canonical adapter recovered fenced objects without dropping records.

Correct current wording: under the shared baseline structured-output interface, the additional J module did not yield a consistent measurable benefit in extraction F1 or canonical output reliability on this dataset/model setting. Do not generalize to 'JSON schema is useless' or 'structured output constraints are unnecessary'.

## 4. Historical prompt simplification context

Earlier prompt-simplification/history records exist and must be included in the timeline. They show that some global shortenings or module removals were associated with severe drops, but they are not the same operation as the current controlled E/S/J component ablation.

| historical observation | value | interpretation boundary |
|---|---:|---|
| D1 full v6 prompt overall F1 (historical evaluator view, six-field micro) in the real 450-call factorial batch | 0.771908 | Historical v6 prompt family and evaluator view; not the current modular E/S/J coarse five-field mean F1. |
| D1 no-semantic-examples overall F1 delta after removing/replacing full examples | -0.006937 | Controlled single-module removal in the old v6 prompt; actor F1 delta was -0.131708. |
| D1 no-detailed-semantic-guidance overall F1 delta | 0.003994 | Removal improved actor/condition/constraint/exception but reduced action F1 in that arm; not the current E/S/J schema. |
| D1 no-explicit-JSON-contract overall F1 delta | 0.007125 | Valid-output rate without the module was 1.000000; current common skeleton is already stricter/different. |
| D-no-fewshot current-locked F1 / parseable JSON / non-empty raw clauses | 0.000 / 147 of 150 JSON parseable / 146 non-empty raw clauses | The near-zero score is attributed by the existing diagnosis to a coordinate-representation interface mismatch (arrays vs named span objects), not to loss of all semantic extraction. The retrospective bridge is diagnostic only. |
| D-minimal historical pressure test | classified report records F1 0.000, parse rate 0.000, failure rate 1.000 | This was a global multi-part simplification, not a controlled E/S/J component ablation. Exact deletion inventory needs artifact-level recheck before paper use. |

Controlled component ablation changes one named prompt component while holding the common skeleton, input, model, and evaluator fixed. Global prompt shortening/simplification may simultaneously remove genuinely useful example information, common constraints, span guidance, and task framing. Therefore 'a global simplified prompt scored worse' does not imply 'all redundant instructions are useful', and it does not directly contradict the current `100` result.

## 5. Evidence / Observation / Hypothesis layers

### A_directly_observed

- E-only (`100`) > common skeleton (`000`) in the current same batch.
- S-only (`010`) > common skeleton (`000`) in the current same batch.
- J-only (`001`) does not improve the current primary metric.
- Full `111` is not descriptively best; `100` is currently highest.
- The E/S relationship is non-additive in the current full-8 descriptive analysis.
- Canonical parser/schema/canonicalization failure is 0 in all evaluated cells.
- Without J, some raw responses were Markdown-fenced; with J, raw bare-JSON rates were 150/150 in the evaluated J arms.

### B_strongly_suggested_but_not_proven

- E and S information may overlap.
- Instruction load may create interference.
- Examples may implicitly encode part of the semantic rules.
- J may be redundant on a strong instruction-following model once a shared structured-output interface exists.
- E-only reduces actor false positives relative to the common skeleton.

### C_unverified_hypotheses

- S may cause actor over-extraction.
- E/S may give conflicting boundary guidance on specific sentences.
- Examples and rules contain an explicit wording contradiction.
- Performance drops come from attention competition.
- Constraint/exception rules are the main source of E x S interaction.

## 6. Paired error attribution (zero API)

Paired labels are derived only from persisted canonical predictions and frozen coarse Gold using the existing `stage2_sun_literal_overlap` intersection evaluator. A sample-field is called evaluator-correct when all predicted spans in that sample-field are matched and all coarse Gold spans are matched. Boundary and cross-field counts are diagnostic overlays and never recompute official F1.

### 100_vs_000: 000 -> 100

- purpose: E contribution against the common skeleton; batch relation: `same_new_batch`; mean-F1 delta (variant-baseline): `0.142014`.

| field | fixed | regressed | both correct | both wrong | unmatched-pred delta | matched-Gold delta |
|---|---:|---:|---:|---:|---:|---:|
| actor | 90 | 3 | 19 | 38 | -188 | +0 |
| action | 24 | 7 | 105 | 14 | -43 | +3 |
| condition | 11 | 10 | 104 | 25 | -14 | -4 |
| constraint | 54 | 11 | 37 | 48 | +23 | +53 |
| exception | 1 | 1 | 145 | 3 | -1 | -1 |

- representative sample IDs: `estg_000020`, `estg_000021`, `estg_000075`

### 010_vs_000: 000 -> 010

- purpose: S contribution against the common skeleton; batch relation: `same_new_batch`; mean-F1 delta (variant-baseline): `0.091041`.

| field | fixed | regressed | both correct | both wrong | unmatched-pred delta | matched-Gold delta |
|---|---:|---:|---:|---:|---:|---:|
| actor | 73 | 2 | 20 | 55 | -149 | -1 |
| action | 26 | 4 | 108 | 12 | -46 | +1 |
| condition | 9 | 12 | 102 | 27 | -2 | +3 |
| constraint | 48 | 4 | 44 | 54 | +23 | +54 |
| exception | 1 | 3 | 143 | 3 | -1 | -3 |

- representative sample IDs: `estg_000021`, `estg_000027`, `estg_000030`

### 001_vs_000: 000 -> 001

- purpose: J contribution against the common skeleton; batch relation: `same_new_batch`; mean-F1 delta (variant-baseline): `-0.018393`.

| field | fixed | regressed | both correct | both wrong | unmatched-pred delta | matched-Gold delta |
|---|---:|---:|---:|---:|---:|---:|
| actor | 15 | 2 | 20 | 113 | -24 | +1 |
| action | 5 | 10 | 102 | 33 | +10 | +0 |
| condition | 5 | 7 | 107 | 31 | +5 | +3 |
| constraint | 13 | 6 | 42 | 89 | +1 | +7 |
| exception | 0 | 2 | 144 | 4 | +3 | -1 |

- representative sample IDs: `estg_000095`, `estg_000127`, `estg_000020`

### 111_vs_011: 011 -> 111

- purpose: adding E when S+J are present; batch relation: `same_old_batch`; mean-F1 delta (variant-baseline): `-0.020750`.

| field | fixed | regressed | both correct | both wrong | unmatched-pred delta | matched-Gold delta |
|---|---:|---:|---:|---:|---:|---:|
| actor | 13 | 19 | 72 | 46 | +4 | +1 |
| action | 8 | 7 | 124 | 11 | -12 | -2 |
| condition | 8 | 8 | 101 | 33 | -13 | -9 |
| constraint | 13 | 18 | 79 | 40 | +14 | +0 |
| exception | 1 | 3 | 142 | 4 | +2 | +0 |

- representative sample IDs: `estg_000080`, `estg_000020`

### 111_vs_101: 101 -> 111

- purpose: adding S when E+J are present; batch relation: `same_old_batch`; mean-F1 delta (variant-baseline): `-0.034850`.

| field | fixed | regressed | both correct | both wrong | unmatched-pred delta | matched-Gold delta |
|---|---:|---:|---:|---:|---:|---:|
| actor | 7 | 38 | 78 | 27 | +41 | -1 |
| action | 8 | 4 | 124 | 14 | -2 | -1 |
| condition | 3 | 8 | 106 | 33 | -1 | -7 |
| constraint | 16 | 7 | 76 | 51 | +16 | +16 |
| exception | 1 | 2 | 142 | 5 | +1 | +0 |

- representative sample IDs: `estg_000080`, `estg_000083`, `estg_000020`, `estg_000106`

### 111_vs_110: 110 -> 111

- purpose: adding J when E+S are present; batch relation: `same_old_batch`; mean-F1 delta (variant-baseline): `-0.009333`.

| field | fixed | regressed | both correct | both wrong | unmatched-pred delta | matched-Gold delta |
|---|---:|---:|---:|---:|---:|---:|
| actor | 10 | 5 | 75 | 60 | -9 | +1 |
| action | 4 | 3 | 128 | 15 | -2 | +0 |
| condition | 2 | 2 | 107 | 39 | -1 | -2 |
| constraint | 8 | 12 | 84 | 46 | +8 | -3 |
| exception | 1 | 2 | 142 | 5 | +1 | +0 |

- representative sample IDs: `estg_000020`, `estg_000106`

### 100_vs_110: 100 -> 110

- purpose: adding S when E is present (new-batch baseline vs old-batch variant); batch relation: `cross_batch_confounded`; mean-F1 delta (variant-baseline): `-0.043224`.

| field | fixed | regressed | both correct | both wrong | unmatched-pred delta | matched-Gold delta |
|---|---:|---:|---:|---:|---:|---:|
| actor | 6 | 35 | 74 | 35 | +40 | -1 |
| action | 9 | 7 | 122 | 12 | -7 | -4 |
| condition | 3 | 9 | 106 | 32 | +4 | -3 |
| constraint | 17 | 12 | 79 | 42 | -3 | +7 |
| exception | 0 | 2 | 144 | 4 | +1 | -1 |

- representative sample IDs: `estg_000020`, `estg_000033`, `estg_000210`

### Representative real cases

All cases below are selected from persisted canonical predictions and frozen coarse Gold. The mechanical observation is artifact-derived; any interpretation is marked as hypothesis.

#### e_fixes_actor_000_to_100

- `estg_000075` / `actor` / `fixed`
  - source (excerpt): If business assets of a business (permanent establishment) located in Austria are transferred abroad to another business (permanent establishment), the business assets transferred abroad shall be measured at the values t
  - coarse Gold: (none)
  - 000: `business assets of a business (permanent establishment) located in Austria` [3,77); `another business (permanent establishment)` [104,146); `the business assets transferred abroad` [148,186); `the same taxpayer` [379,396); `a co-entrepreneur of the foreign business` [416,457); `a substantial interest, i.e. more than 25%, in the foreign corporation` [480,550); `the same persons` [557,573); `both businesses` [610,625)
  - 100: (none)
  - mechanical observation: 000: 8 predicted span(s), 8 unmatched, 0 missed Gold span(s); 100: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- `estg_000277` / `actor` / `fixed`
  - source (excerpt): Special increment amounts from supplementary insurance in the pension insurance or supplementary insurance pensions are to be recorded at only 25%.\nb) Similar emoluments from welfare and support institutions of the cham
  - coarse Gold: (none)
  - 000: `Special increment amounts from supplementary insurance in the pension insurance or supplementary insurance pensions` [0,115); `Similar emoluments from welfare and support institutions of the chambers of self-employed persons` [152,249); `Pensions from a foreign statutory social insurance that corresponds to a domestic statutory social insurance` [255,363); `Emoluments, expense allowances and retirement (pension) benefits within the meaning of the Emoluments Act and the Constitutional Court Act` [372,510); `Similar emoluments, expense allowances and retirement (pension) benefits received by members of a provincial government (of the Vienna City Senate) and members of a provincial parliament and their survivors on the basis of provincial legislation` [516,761); `emoluments, expense allowances and retirement (pension) benefits received by mayors, deputy mayors (mayoral representatives) or city councillors (executive municipal councillors), district chairpersons (deputies) of the City of Vienna and their survivors on the basis of provincial legislation` [775,1068)
  - 100: (none)
  - mechanical observation: 000: 6 predicted span(s), 6 unmatched, 0 missed Gold span(s); 100: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- `estg_000210` / `actor` / `fixed`
  - source (excerpt): Shares for which guarantees regarding value or dividend claims are provided are not eligible.\nb) Stock corporations within the meaning of paragraph 1 item 4 are stock corporations having their registered seat and place o
  - coarse Gold: (none)
  - 000: `Shares` [0,6); `Stock corporations` [97,115); `which` [253,258); `which` [602,607); `A stock corporation` [691,710)
  - 100: (none)
  - mechanical observation: 000: 5 predicted span(s), 5 unmatched, 0 missed Gold span(s); 100: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).

#### e_fixes_constraint_000_to_100

- `estg_000134` / `constraint` / `fixed`
  - source (excerpt): (7) Hidden reserves may be allocated to a tax-free reserve in the year of their disclosure, provided that no transfer is effected in the same business year.
  - coarse Gold: `in the year of their disclosure` [59,90)
  - 000: `no transfer is effected in the same business year` [106,155)
  - 100: `in the year of their disclosure` [59,90)
  - mechanical observation: 000: 1 predicted span(s), 1 unmatched, 1 missed Gold span(s); 100: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- `estg_000020` / `constraint` / `fixed`
  - source (excerpt): A prerequisite for the tax exemption is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale. 20.
  - coarse Gold: `in such quantity as to actually preclude a sale` [130,177)
  - 000: (none)
  - 100: `in such quantity as to actually preclude a sale` [130,177)
  - mechanical observation: 000: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); 100: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- `estg_000021` / `constraint` / `fixed`
  - source (excerpt): Free tobacco, free cigars and free cigarettes to employees in tobacco processing establishments, if the products granted may not be sold and are granted only in such a quantity that actually precludes a sale. 21.
  - coarse Gold: `in such a quantity that actually precludes a sale` [158,207)
  - 000: (none)
  - 100: `only in such a quantity that actually precludes a sale` [153,207)
  - mechanical observation: 000: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); 100: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).

#### s_fixes_actor_000_to_010

- `estg_000075` / `actor` / `fixed`
  - source (excerpt): If business assets of a business (permanent establishment) located in Austria are transferred abroad to another business (permanent establishment), the business assets transferred abroad shall be measured at the values t
  - coarse Gold: (none)
  - 000: `business assets of a business (permanent establishment) located in Austria` [3,77); `another business (permanent establishment)` [104,146); `the business assets transferred abroad` [148,186); `the same taxpayer` [379,396); `a co-entrepreneur of the foreign business` [416,457); `a substantial interest, i.e. more than 25%, in the foreign corporation` [480,550); `the same persons` [557,573); `both businesses` [610,625)
  - 010: (none)
  - mechanical observation: 000: 8 predicted span(s), 8 unmatched, 0 missed Gold span(s); 010: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- `estg_000112` / `actor` / `fixed`
  - source (excerpt): No. 253/1957) and civil aviation schools. — For low-value assets written off pursuant to Section 13. — Upon acquisition of a business, a part of a business or an interest of a partner who is deemed to be an entrepreneur
  - coarse Gold: (none)
  - 000: `low-value assets` [48,64); `a part of a business` [135,155); `an interest of a partner who is deemed to be an entrepreneur (co-entrepreneur)` [159,237); `used assets` [245,256); `used assets` [424,435); `a group company` [448,463)
  - 010: (none)
  - mechanical observation: 000: 6 predicted span(s), 6 unmatched, 0 missed Gold span(s); 010: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).

#### s_fixes_constraint_000_to_010

- `estg_000021` / `constraint` / `fixed`
  - source (excerpt): Free tobacco, free cigars and free cigarettes to employees in tobacco processing establishments, if the products granted may not be sold and are granted only in such a quantity that actually precludes a sale. 21.
  - coarse Gold: `in such a quantity that actually precludes a sale` [158,207)
  - 000: (none)
  - 010: `only in such a quantity that actually precludes a sale` [153,207)
  - mechanical observation: 000: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); 010: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- `estg_000027` / `constraint` / `fixed`
  - source (excerpt): Section 25(1) items 7, 8, 8a, 9 of the Civilian Service Act 1986) only for part of the calendar year, the income as defined in Section 2(3) items 1 to 3 earned in the remainder of the calendar year and current income fro
  - coarse Gold: `the income as defined in Section 2(3) items 1 to 3 earned in the remainder of the calendar year and current income from employment as defined in Section 41(4) shall be converted to an annual amount for the purpose of determining the tax rate` [102,343)
  - 000: (none)
  - 010: `for the purpose of determining the tax rate` [300,343)
  - mechanical observation: 000: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); 010: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- `estg_000030` / `constraint` / `fixed`
  - source (excerpt): (3) Income within the meaning of paragraph 1 items 10 and 11 shall be taken into account when determining the tax for the employee's other income.
  - coarse Gold: `within the meaning of paragraph 1 items 10 and 11` [11,60)
  - 000: (none)
  - 010: `within the meaning of paragraph 1 items 10 and 11` [11,60)
  - mechanical observation: 000: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); 010: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).

#### s_regresses_actor_101_to_111

- `estg_000080` / `actor` / `regressed`
  - source (excerpt): Contributions shall be valued in accordance with item 5; b) In the case of acquisition of a business for consideration, the assets shall be recognized at acquisition cost. 9. a) If a business, a part of a business or the
  - coarse Gold: `the legal successor` [342,361)
  - 101: `the legal successor` [342,361)
  - 111: `Contributions` [0,13); `the assets` [120,130); `the legal successor` [342,361); `the amount that the recipient would have had to pay for the individual asset at the time of receipt` [607,706)
  - mechanical observation: 101: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); 111: 4 predicted span(s), 3 unmatched, 0 missed Gold span(s).
- `estg_000059` / `actor` / `regressed`
  - source (excerpt): (9) Contributions for voluntary membership in professional and trade associations shall be deductible only under the following conditions:\n— The professional and trade associations must, according to their statutes and
  - coarse Gold: `The professional and trade associations` [143,182)
  - 101: `The professional and trade associations` [143,182)
  - 111: `Contributions for voluntary membership in professional and trade associations` [4,81); `The professional and trade associations` [143,182); `The contributions` [362,379)
  - mechanical observation: 101: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); 111: 3 predicted span(s), 2 unmatched, 0 missed Gold span(s).
- `estg_000083` / `actor` / `regressed`
  - source (excerpt): This does not apply if the input tax is adjusted under Section 12(10) and (11) of the Turnover Tax Act 1972; in this case, the additional amounts shall be treated as business income and the reduced amounts as business ex
  - coarse Gold: (none)
  - 101: (none)
  - 111: `the additional amounts` [123,145); `the reduced amounts` [186,205)
  - mechanical observation: 101: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); 111: 2 predicted span(s), 2 unmatched, 0 missed Gold span(s).

#### s_regresses_constraint_101_to_111

- `estg_000002` / `constraint` / `regressed`
  - source (excerpt): Bookkeeping farmers and foresters and registered traders (Section 5) may, however, have a business year deviating from the calendar year; in this case, the profit shall be taken into account in determining the income for
  - coarse Gold: (none)
  - 101: (none)
  - 111: `in determining the income for that calendar year in which the business year ends` [191,271)
  - mechanical observation: 101: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); 111: 1 predicted span(s), 1 unmatched, 0 missed Gold span(s).
- `estg_000106` / `constraint` / `regressed`
  - source (excerpt): (2) The investment allowance may only be claimed for business assets which\n— have a normal useful life in the business of at least four years, and\n— are used in a domestic permanent establishment that serves to generate
  - coarse Gold: `for business assets which\n— have a normal useful life in the business of at least four years, and\n— are used in a domestic permanent establishment that serves to generate income within the meaning of Section 2(3) items 1 to 3` [49,274)
  - 101: `at least four years` [122,141)
  - 111: `only` [33,37); `for business assets which\n— have a normal useful life in the business of at least four years, and\n— are used in a domestic permanent establishment that serves to generate income within the meaning of Section 2(3) items 1 to 3.` [49,275)
  - mechanical observation: 101: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); 111: 2 predicted span(s), 1 unmatched, 0 missed Gold span(s).
- `estg_000119` / `constraint` / `regressed`
  - source (excerpt): This list must contain the following:\n— acquisition or production costs,\n— date of acquisition or production,\n— name and address of the supplier,\n— the investment allowance claimed.
  - coarse Gold: `acquisition or production costs,\n— date of acquisition or production,\n— name and address of the supplier,\n— the investment allowance claimed` [42,188)
  - 101: `acquisition or production costs` [42,73); `date of acquisition or production` [79,112); `name and address of the supplier` [118,150); `the investment allowance claimed` [156,188)
  - 111: (none)
  - mechanical observation: 101: 4 predicted span(s), 0 unmatched, 0 missed Gold span(s); 111: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s).

#### s_regresses_actor_100_to_110_cross_batch

- `estg_000210` / `actor` / `regressed`
  - source (excerpt): Shares for which guarantees regarding value or dividend claims are provided are not eligible.\nb) Stock corporations within the meaning of paragraph 1 item 4 are stock corporations having their registered seat and place o
  - coarse Gold: (none)
  - 100: (none)
  - 110: `Shares for which guarantees regarding value or dividend claims are provided` [0,75); `Stock corporations within the meaning of paragraph 1 item 4` [97,156); `which` [253,258); `for which` [598,607); `A stock corporation whose 152.` [691,721)
  - mechanical observation: 100: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); 110: 5 predicted span(s), 5 unmatched, 0 missed Gold span(s).
- `estg_000285` / `actor` / `regressed`
  - source (excerpt): If a wage-structuring provision within the meaning of Section 68(5) items 1 to 6 contains a special rule on the definition of the term “business trip,” that rule shall be applied.\na) The mileage allowance shall be taken
  - coarse Gold: (none)
  - 100: (none)
  - 110: `that rule` [152,161); `The mileage allowance` [184,205); `The daily allowance for domestic business trips` [292,339)
  - mechanical observation: 100: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); 110: 3 predicted span(s), 3 unmatched, 0 missed Gold span(s).

#### s_regresses_constraint_100_to_110_cross_batch

- `estg_000020` / `constraint` / `regressed`
  - source (excerpt): A prerequisite for the tax exemption is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale. 20.
  - coarse Gold: `in such quantity as to actually preclude a sale` [130,177)
  - 100: `in such quantity as to actually preclude a sale` [130,177)
  - 110: `only` [117,121); `in such quantity as to actually preclude a sale` [130,177)
  - mechanical observation: 100: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); 110: 2 predicted span(s), 1 unmatched, 0 missed Gold span(s).
- `estg_000033` / `constraint` / `regressed`
  - source (excerpt): Gains or losses from the disposal or withdrawal and other changes in value of land that is part of the fixed assets are not to be taken into account.
  - coarse Gold: `that is part of the fixed assets` [83,115)
  - 100: `Gains or losses from the disposal or withdrawal and other changes in value of land that is part of the fixed assets` [0,115)
  - 110: (none)
  - mechanical observation: 100: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); 110: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s).

#### j_fixes_action_000_to_001

- `estg_000095` / `action` / `fixed`
  - source (excerpt): This depreciation is also permissible for acquisition or construction costs incurred for listed commercial buildings in the interest of monument preservation.
  - coarse Gold: `depreciation` [5,17)
  - 000: `is also permissible` [18,37)
  - 001: `This depreciation` [0,17)
  - mechanical observation: 000: 1 predicted span(s), 1 unmatched, 1 missed Gold span(s); 001: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- `estg_000111` / `action` / `fixed`
  - source (excerpt): (5) In the following cases, an investment allowance may be claimed neither as a reduction of profit nor through the designated use of an investment reserve (a tax-free amount):\n— For aircraft used for passenger transpo
  - coarse Gold: `be claimed` [56,66)
  - 000: `claimed` [59,66); `as a reduction of profit` [75,99); `through the designated use of an investment reserve` [104,155)
  - 001: `may be claimed` [52,66)
  - mechanical observation: 000: 3 predicted span(s), 2 unmatched, 0 missed Gold span(s); 001: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).

#### j_regresses_action_000_to_001

- `estg_000127` / `action` / `regressed`
  - source (excerpt): (1) If fixed assets are sold, the hidden reserves disclosed thereby may be deducted from the acquisition or production costs, or from the partial amounts of the acquisition or production costs within the meaning of Secti
  - coarse Gold: `be deducted` [72,83)
  - 000: `may be deducted from the acquisition or production costs, or from the partial amounts of the acquisition or production costs within the meaning of Section 10(7), second sentence, of fixed assets acquired or produced in the financial year of the sale` [68,317)
  - 001: `sold` [24,28); `deducted` [75,83); `acquired` [263,271); `produced` [275,283)
  - mechanical observation: 000: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); 001: 4 predicted span(s), 3 unmatched, 0 missed Gold span(s).
- `estg_000033` / `action` / `regressed`
  - source (excerpt): Gains or losses from the disposal or withdrawal and other changes in value of land that is part of the fixed assets are not to be taken into account.
  - coarse Gold: `be taken into account` [127,148)
  - 000: `are not to be taken into account` [116,148)
  - 001: `Gains or losses from the disposal or withdrawal and other changes in value of land that is part of the fixed assets` [0,115)
  - mechanical observation: 000: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); 001: 1 predicted span(s), 1 unmatched, 1 missed Gold span(s).

#### j_fixes_constraint_000_to_001

- `estg_000020` / `constraint` / `fixed`
  - source (excerpt): A prerequisite for the tax exemption is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale. 20.
  - coarse Gold: `in such quantity as to actually preclude a sale` [130,177)
  - 000: (none)
  - 001: `only granted in such quantity as to actually preclude a sale` [117,177)
  - mechanical observation: 000: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); 001: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- `estg_000044` / `constraint` / `fixed`
  - source (excerpt): This shall be assessed on the basis of the average benefits granted by the fund to the recipients during the three years preceding the date of the allocation. 3.
  - coarse Gold: `on the basis of the average benefits granted by the fund to the recipients during the three years preceding the date of the allocation` [23,157)
  - 000: (none)
  - 001: `on the basis of the average benefits granted by the fund to the recipients during the three years preceding the date of the allocation` [23,157)
  - mechanical observation: 000: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); 001: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).

## 7. Prompt overlap / conflict audit

A 38-item atomic instruction inventory was built from the frozen common/E/S/J prompt files. E and S overlap functionally. No literal contradiction was found. J is distinct from the common baseline interface at the serialization level, but its extra discipline has no observed canonical-reliability or primary-metric benefit in this dataset/model setting.

### E/S overlap
- `E01, S03, S10`: functional_overlap — actor surface preservation, including unresolved subject pronouns; literal contradiction=False.
- `E02, S04, S06, S10`: functional_overlap — passive action mapping plus constraint extraction; literal contradiction=False.
- `E03, S02, S07`: functional_overlap — prohibition modality and exception extraction; literal contradiction=False.
- `E04, S11, S12`: functional_overlap — definition/obligation clause splitting; literal contradiction=False.
- `E05, S05, S06, S08`: functional_overlap — condition/constraint nesting and field partition; literal contradiction=False.

### J/common relationship
- baseline structural interface: C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16
- additional J discipline: J01, J02
- literal duplicates: 0
- genuinely new J constraint: Return one bare JSON object. Do not wrap it in Markdown fences or add a prefix, explanation, comments, or trailing text.
- why 000 parses 150/150: The persisted canonical parser/adaptor accepts and canonicalizes fenced raw responses. 000 raw responses included 36/150 Markdown-fenced objects, yet all 150 became canonical schema/cross-field-valid records.

### Sample-linked prompt evidence
- `actor_overextraction_after_S_addition`: instructions S03, S10, S13; evidence type `mechanically_observed_span_difference`; samples estg_000080, estg_000083.
  - hypothesis: The broad actor-surface instructions in S may be over-applied to noun phrases in coordinated or passive contexts, while the passive-voice exception in S10 is not always followed. This is a plausible interference hypothesis, not a causal proof.
  - unresolved: No same-prompt repeat or token-level activation evidence is available to separate S wording effects from ordinary run-to-run generation variation.
- `constraint_marker_overextraction_after_S_addition`: instructions S06, S08; evidence type `mechanically_observed_span_difference`; samples estg_000020, estg_000106.
  - hypothesis: S06's marker-inclusion and smallest-complete-limit guidance can produce separate marker spans that the evaluator treats as unmatched. The wording does not explicitly require splitting a marker from its governed limit.
  - unresolved: The pair 100_to_110 is cross-batch confounded; the 101_to_111 pair is same-batch but single-run. Neither establishes causal wording attribution.
- `E_constraint_recovery`: instructions E02, E05; evidence type `mechanically_observed_span_difference`; samples estg_000020, estg_000021.
  - hypothesis: E examples may supply concrete condition/constraint span patterns that reduce missed constraint spans in the common skeleton. This is consistent with E-only improvement but is not isolated from other prompt differences in this single run.
  - unresolved: No controlled E-only wording variant or repeat is available yet.
- `J_serialization_effect`: instructions J01, J02; evidence type `raw_response_and_canonical_pipeline_counts`; samples .
  - hypothesis: J mainly adds a serialization/discipline constraint. It changes raw response form, but the current canonical parser already recovers fenced objects, so no F1 or canonical-failure benefit is observable.
  - unresolved: The canonical semantic predictions also differ across arms, but each arm is a single generation; those differences cannot be attributed to J alone.

## 8. Root-cause evidence status

### confirmed
- `100` and `010` each improve over `000` in the current new batch.
- `111` is not descriptively best; `100` has the highest descriptive mean F1.
- Old-batch single-module deletions from `111` are associated with higher, not lower, mean F1.
- J-only does not improve the current primary metric; canonical failure counts are zero with and without J.
- The negative E x S two-way interaction is present in the descriptive factorial analysis.

### strongly_suggested
- Actor over-extraction is the dominant old-batch failure mode when S is added: `101 -> 111` fixes 7 actor sample-fields but regresses 38, while actor unmatched predictions rise from 43 to 84.
- S helps constraint recall in the new batch (`000 -> 010` fixes 48 constraint sample-fields) but also increases extra constraint spans; E helps both constraint recall and actor minimality.
- J's main observed effect is raw serialization discipline; it does not add measurable canonical reliability under the current adapter.
- The E examples and S rules overlap functionally rather than containing a literal contradiction.

### unresolved
- Whether a specific S sentence causes a specific actor over-extraction sample.
- Whether E/S interfere through attention competition.
- Whether the negative E x S interaction is caused by redundancy, conditional interference, or instruction conflict.
- Whether single-run differences are stable under repeat sampling.
- Whether the historical D-minimal deletions match the current controlled comparison operation.

## 9. Current interpretation
### 1. Why did single-factor ablation initially look like it had little effect?
In the old batch, each deletion changed the score by only +0.009 to +0.035 mean F1, so the direction was negative for the kept module but the magnitudes were modest. Full-8 and paired analysis show that behind the small aggregate changes are large offsetting field changes: deleting S fixes actor precision but loses constraint recall; deleting E changes condition/constraint recall; deleting J changes raw serialization and some semantic predictions. Aggregate mean F1 hides these offsetting effects.

### 2. Why is the full prompt not necessarily best?
The full prompt combines overlapping actor/action/condition/constraint instructions and examples. In this dataset/model/setting, the added S module is associated with actor over-extraction (`101 -> 111`: 38 actor sample-fields regressed, 7 fixed), and the added E/J modules do not compensate. This supports non-additivity and conditional interference, but the exact causal wording remains unresolved.

### 3. Why could previous prompt simplification have been worse?
The previous simplification observations were not controlled single-module ablations. D-no-fewshot removed complete examples and appears to have broken the coordinate/output interface; D-minimal was a broad multi-part reduction. Those operations can remove common constraints, span guidance, and task framing together. Current `100` keeps the common skeleton and only adds compact E examples, so it does not directly contradict the earlier global-simplification failures.

### 4. What does E actually provide?
In the new batch, E-only is the strongest cell. Paired analysis shows E fixes 90 actor sample-fields and 54 constraint sample-fields over `000`, while substantially reducing unmatched actor predictions (241 -> 53). It does not eliminate actor false positives and adds some constraint over-extraction (unmatched constraint predictions 9 -> 32). E therefore provides concrete boundary demonstrations that improve actor minimality and constraint recall, but not a complete solution.

### 5. What does S actually provide?
S-only also improves over `000` (73 actor fixes, 48 constraint fixes), with a slightly higher constraint F1 than `100` but much weaker actor F1. When S is added to E-containing arms, actor over-extraction dominates (`101 -> 111`: 38 regressions) while constraint recall can improve. S therefore carries useful constraint/condition guidance but its broad surface rules are not safely compositional with E in this setting.

### 6. What can and cannot be concluded about J?
Can conclude: under the shared baseline structured-output interface, additional J did not yield a consistent measurable extraction-F1 or canonical-reliability benefit. J did increase raw bare-JSON rates (without J: 000 114/150, 100 146/150, 010 149/150; with J: 150/150) but the canonical adapter already recovered fenced objects. Cannot conclude: JSON schema is useless, structured output constraints are unnecessary, or J can never help another model release/parser/dataset.

### 7. Is there direct evidence of instruction interference?
There is strong sample-level association but no direct causal evidence. The largest signal is actor over-extraction when S is added to E+J (`101 -> 111`), with real samples such as `estg_000080` and `estg_000083`. Constraint-marker over-extraction appears after S in `estg_000020` and `estg_000106`. These motivate interference hypotheses but do not establish which instruction token caused them.

## 10. Next experiment (design only; NOT executed)
Design only; no API calls were made in this round. Default principle: targeted repair rather than restoring the entire removed S or J module. Start from the strongest simple baseline (`100`, common skeleton + E examples) and test at most three small, pre-declared deltas in one controlled batch with the baseline rerun in that same batch.

Recommended baseline: `100 (common skeleton + E examples)`. `100` is the highest same-batch cell (0.778763 mean F1, +0.142014 vs `000` and +0.050974 vs `010`), and paired analysis shows E-only fixes actor false positives and recovers constraints without the S-induced actor regression. The decision is based on paired error attribution and prompt overlap audit, not on mean F1 alone.

### E + actor_minimality_fix
- hypothesis: A narrow negative actor-boundary demonstration will reduce over-extraction without reducing actor recall.
- exact prompt delta: Add one short worked example/rule to E showing a passive or nominalized subject that should not become an actor unless an explicit by-phrase/performer is present; preserve E1's unresolved pronoun rule. Do not add the full S actor module.
- targeted failure: `100` still has 53 unmatched actor predictions and actor precision 0.4592; real false positives include `estg_000046`, `estg_000664`, `estg_000161`, and `estg_000271`.
- supporting sample IDs: `estg_000046`, `estg_000664`, `estg_000161`, `estg_000271`
- intended behavior change: Suppress non-bearer noun phrases and passive-clause subjects where Gold has no actor, without dropping genuine explicit actors.
- possible side effect: May reduce actor recall or remove unresolved-pronoun actors; monitor actor missed-Gold and both-correct counts.
- evaluation criterion: Actor precision/recall/F1 paired against same-batch `100`; no >0.01 drop in primary mean F1.

### E + constraint_recall_fix
- hypothesis: A narrow constraint/legal-reference demonstration will recover missed constraint spans without a precision collapse.
- exact prompt delta: Add a minimal constraint example/rule derived from S06 but restricted to legal references, time/duration, quantity, purpose, and exclusivity; do not import S actor/voice/coordination rules.
- targeted failure: `100` has constraint recall 0.6667 and 45 missed coarse Gold constraint spans; S-only recovers 48 constraint sample-fields over `000` but introduces extra constraint spans.
- supporting sample IDs: `estg_000021`, `estg_000020`, `estg_000027`, `estg_000030`
- intended behavior change: Increase constraint recall while keeping each constraint span as a minimal complete limit rather than a marker-only fragment.
- possible side effect: May increase constraint over-extraction or condition/constraint category confusion; monitor unmatched-pred delta and cross-field candidates.
- evaluation criterion: Constraint F1 improvement and no >0.01 primary mean-F1 drop vs same-batch `100`.

### E + combined_minimal_fixes
- hypothesis: Actor minimality and constraint recall fixes are complementary if their effects are field-specific.
- exact prompt delta: Apply both minimal deltas exactly as above; do not add any other S or J text.
- targeted failure: Tests whether actor and constraint repair add or interfere when combined.
- supporting sample IDs: `estg_000046`, `estg_000664`, `estg_000021`, `estg_000027`
- intended behavior change: Improve actor precision and constraint recall relative to `100`.
- possible side effect: Two added instructions may interact; the union of the individual side effects must be monitored.
- evaluation criterion: Primary mean F1 not lower than the better single fix, with actor and constraint trade-offs reported separately.

### Controls, size, metrics, stopping rule
- controls: same EStG-150 input, frozen Gold, model/release, sampling, parser, canonicalizer, evaluator, and prompt skeleton as the current batch; baseline `100` rerun in the same batch.
- sample count: 4 arms x 150 records = 600 planned calls if baseline `100` is rerun; 450 calls if a same-batch baseline reuse is later justified, but same-batch rerun is preferred for causal interpretation.
- metrics: coarse_five_field_mean_f1 (primary), micro P/R/F1, per-field F1, modality-label metrics separately, paired fixed/regressed counts, actor/constraint over- and under-extraction, canonical failures, raw bare-JSON rate.
- stopping rule: Predeclare the four arms and thresholds before running; run all 600 calls without adaptive prompt changes; stop the refinement line if no variant improves its target field without a >0.01 primary mean-F1 drop, or if results are non-interpretable because of batch/parser drift.

## 11. Is a future same-batch full-8 needed?
A future same-batch full-8 is not required for the next targeted repair experiment, but it is the correct later design if the paper needs a causal full-factorial comparison of E/S/J under one batch/time condition.

- It addresses the batch/time confound between old four and new four, improving causal interpretability of factorial effects.
- A single same-batch full-8 still does not address repeat variance; it is one run per cell.
- Strong statistical conclusions about stability or significance require separately pre-registered repeats, not one full-8 batch.
- For the immediate next step, small controlled variants (baseline + targeted fixes) are more interpretable and cheaper than re-running all eight cells.

## 12. Research log: how our understanding changed
### Before ablation
Pre-experiment hypothesis: E, S, and J each contribute positively and may combine cumulatively; full `111` may be best.

### After single-factor ablation
Old-batch deletions of E, S, or J did not lower mean F1 relative to `111`; all three deletions were associated with higher mean F1. This weakened the simple additive contribution hypothesis and created the negative/non-monotonic finding.

### After full-8
`111` was not descriptively best; `100` was highest. E-only and S-only each improved over `000`, but E x S was a strong negative interaction. J-only did not improve the primary metric. Batch/time confound remained.

### After paired error analysis
E-only fixes many actor and constraint sample-fields; S helps constraint recall but drives actor over-extraction when added to E-containing arms. J's clearest effect is raw serialization form, not canonical semantic reliability. Large offsetting field changes explain why aggregate deltas looked modest.

### After prompt audit
E and S overlap functionally; no literal contradiction was found. J is distinct from the common baseline interface at the no-fence/bare-object level, but the adapter already recovers fenced responses, explaining the lack of canonical reliability gain.

### Next hypothesis
Test whether minimal actor-minimality and constraint-recall repairs added to `100` improve their target fields without restoring the full S module. Also test whether the two repairs combine or interfere.

## 13. Paper-safe wording

### J
- avoid: JSON schema is unnecessary / structured output constraints are unnecessary.
- use: Given the shared baseline structured-output interface retained across all configurations, the additional output-organization module did not provide a consistent measurable benefit under the evaluated model and dataset.

### E/S
- avoid: E and S conflict.
- use: The ablation results indicate a non-additive relationship between worked examples and explicit semantic rules, motivating a finer-grained error analysis of their overlapping or potentially interfering guidance.

### 111
- avoid: Full prompt is worse.
- use: The complete configuration was not descriptively superior to several simpler configurations in the current experiments.

### Negative results
- avoid: Hiding or deleting non-monotonic results.
- use: Negative and non-monotonic ablation results are treated as experimental findings rather than discarded as failed experiments.

### Batch confound
- avoid: Cross-batch ranking as strict causal proof.
- use: The full-8 ranking is descriptive; the original four and new four cells are batch/time confounded, so cross-batch module effects are not strict causal estimates.

## 14. Artifact / provenance bindings

- starting_head: `18f5cf9ad79602c12315b21d6f54c56da5190580`
- formal_full8_report: `outputs/reports/sep_c3_modular_ablation_v2.json sha256=2c42674e709a4331ae30f01442238777af690f7fc541c280b7d9219ee7e930a7`
- protocol_audit: `outputs/reports/sep_c3_modular_full8_protocol_audit_v1.json sha256=b40146803cf01197e86d4704c71bae1a98670810ef235f0849e560e5743848de`
- paired_error_attribution: `outputs/reports/sep_c3_modular_paired_error_attribution_v1.json sha256=716a65686ba67f5f1f56bd533ade72c5960a5039f1b2bf2246573eaaf05e1866`
- prompt_overlap_audit: `outputs/reports/sep_c3_modular_prompt_overlap_audit_v1.json sha256=d914c4401b4dd77b9182933a52b138698a5231f9bc85ef673bb4cf390be6e5ce`
- gold: `data/gold/stage2/estg150_formal_gold_v1.json sha256=c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100`
- predictions_are_read_only: `All eight canonical prediction paths are bound through the paired attribution report; no prediction file was modified.`
- prompts_are_read_only: `Prompt component hashes are bound in the prompt overlap audit; no prompt file was modified.`

## 15. Git / dirty-worktree note
This record and the two zero-API analysis scripts/outputs are new files. Pre-existing dirty files observed at the start of the round must remain untouched; only this round's files may be staged.
