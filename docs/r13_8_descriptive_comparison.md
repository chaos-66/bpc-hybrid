# R13.8 Descriptive Comparison of R13.4.2 and R13.7

## 1. Scope

This stage performs a descriptive, post-run comparison between the two accepted bounded 8-sample real API mini-pilots:

- **R13.4.2**: baseline real mini-pilot (8 samples, qwen3.7-max, no few-shot, no prompt refinement)
- **R13.7**: Prompt B (few_shot_extraction) real mini-pilot (8 samples, qwen3.7-max, with R13.6 refined prompt B)

No new real API call, LLM call, evaluator rerun, prediction modification, or evaluation output modification was performed.

## 2. Compared Runs

| Property | R13.4.2 | R13.7 |
|---|---|---|
| Stage | R13.4.2 | R13.7 |
| Prompt | Default instruction-only | Prompt B: few-shot extraction with field-specific examples |
| Model | qwen3.7-max | qwen3.7-max |
| Sample set | 8-sample reviewed mini-gold (R13.3) | Same 8-sample set |
| Schema-valid outputs | 8/8 | 8/8 |
| Real API calls | 8 | 8 |
| Raw responses saved | 0 | 0 |
| Retry | 0 | 0 |
| Batch | No | No |

## 3. Evidence Used

- `data/formal/gold/r13_3_manual_gold_template.jsonl`
- `data/formal/results/r13_4_2_real_evaluation_summary.json`
- `data/formal/results/r13_4_2_real_evaluation_details.jsonl`
- `data/formal/predictions/r13_4_2_real_predictions.jsonl`
- `data/formal/results/r13_7_prompt_b_real_evaluation_summary.json`
- `data/formal/results/r13_7_prompt_b_real_evaluation_details.jsonl`
- `data/formal/predictions/r13_7_prompt_b_real_predictions.jsonl`
- `docs/r13_5_post_pilot_error_analysis.md`
- `docs/r13_6_prompt_refinement_design.md`

All evidence was read from committed files. No evaluator was rerun.

## 4. Field-level Count Comparison

### 4.1 Modality

| Score | R13.4.2 | R13.7 | Δ |
|---|---|---|---|
| exact | 7 | 8 | +1 |
| partial | 0 | 0 | 0 |
| missing | 0 | 0 | 0 |
| wrong | 1 | 0 | −1 |
| not_applicable | 0 | 0 | 0 |

**Observed difference**: R13.7 has 8/8 exact modality compared to R13.4.2's 7/8 exact. Sample 006 changed from wrong (obligation) to exact (definition) in R13.7.

**Interpretation boundary**: The sample-006 modality correction may be consistent with Prompt B's inclusion of a definition example in its few-shot demonstrations. This is a count difference in an 8-sample set and does not constitute modality extraction validation.

### 4.2 Actor

| Score | R13.4.2 | R13.7 | Δ |
|---|---|---|---|
| exact | 0 | 7 | +7 |
| partial | 1 | 1 | 0 |
| missing | 4 | 0 | −4 |
| wrong | 3 | 0 | −3 |
| not_applicable | 0 | 0 | 0 |

**Observed difference**: R13.4.2 had 0/8 exact actor matches, 4 missing (null actor output), and 3 wrong. R13.7 has 7/8 exact and 1 partial, with no missing or wrong actors.

**Interpretation boundary**: R13.4.2 frequently returned null actors from passive-voice legal text. In R13.7 Prompt B, the few-shot examples include a passive-voice example with an inferred actor ("entity processing personal data"), which may have guided the model toward inferring actors from passive constructions. This observation is specific to these 8 samples and does not validate general actor-extraction capability.

### 4.3 Action

| Score | R13.4.2 | R13.7 | Δ |
|---|---|---|---|
| exact | 0 | 4 | +4 |
| partial | 0 | 4 | +4 |
| missing | 0 | 0 | 0 |
| wrong | 8 | 0 | −8 |
| not_applicable | 0 | 0 | 0 |

**Observed difference**: R13.4.2 had 0/8 exact or partial action matches — all 8 were scored wrong. The baseline model extracted verbatim text fragments rather than normalized field values. R13.7 has 4/8 exact and 4/8 partial, with no wrong actions.

**Interpretation boundary**: Prompt B's few-shot demonstrations show normalized action forms (e.g., "process personal data" rather than "processed"). This may have helped the model produce more normalized action labels. However, 4/8 samples remain only partial matches, indicating action normalization is not fully achieved even with few-shot guidance. This is a count difference in 8 samples and does not validate action extraction.

### 4.4 Condition

| Score | R13.4.2 | R13.7 | Δ |
|---|---|---|---|
| exact | 1 | 2 | +1 |
| partial | 0 | 3 | +3 |
| missing | 2 | 1 | −1 |
| wrong | 3 | 0 | −3 |
| not_applicable | 2 | 2 | 0 |

**Observed difference**: R13.4.2 had 3 wrong conditions and 2 missing. R13.7 has 0 wrong conditions, 2 exact, 3 partial, and 1 missing. The condition field moved from wrong-dominated to partial-dominated.

**Interpretation boundary**: The reduction in wrong conditions may suggest Prompt B's structured JSON-only output instruction reduced hallucinated or malformed condition fields. However, only 2/6 applicable samples achieved exact condition match, and 1 sample still has a missing condition. Conditions remain a challenging field.

### 4.5 Constraint

| Score | R13.4.2 | R13.7 | Δ |
|---|---|---|---|
| exact | 0 | 3 | +3 |
| partial | 3 | 5 | +2 |
| missing | 1 | 0 | −1 |
| wrong | 4 | 0 | −4 |
| not_applicable | 0 | 0 | 0 |

**Observed difference**: R13.4.2 had 0 exact constraints, 4 wrong, and 3 partial. R13.7 has 3 exact, 5 partial, and 0 wrong or missing. Every sample achieved at least a partial constraint match.

**Interpretation boundary**: The elimination of wrong constraints and the shift from 0 to 3 exact matches is consistent with Prompt B's few-shot constraint examples providing guidance on constraint phrasing. However, 5/8 samples are still only partial matches, suggesting constraint normalization remains incomplete.

### 4.6 Exception

| Score | R13.4.2 | R13.7 | Δ |
|---|---|---|---|
| exact | 0 | 0 | 0 |
| partial | 0 | 0 | 0 |
| missing | 0 | 0 | 0 |
| wrong | 0 | 0 | 0 |
| not_applicable | 8 | 8 | 0 |

**Observed difference**: No change. Exception is not applicable in all 8 samples — none of the gold entries contain exception values.

**Interpretation boundary**: Exception extraction cannot be assessed from this sample set. A separate test set containing exception-bearing samples would be needed for any exception-field observation.

### 4.7 Failure Category Summary

| Failure Category | R13.4.2 | R13.7 |
|---|---|---|
| actor_missing | 4 | 0 |
| condition_wrong | 5 | 1 |
| constraint_wrong | 5 | 0 |
| modality_wrong | 1 | 0 |

R13.7 reduced total failure categories from 15 to 1 (a single condition_wrong in sample 003).

## 5. Sample-level Notes

### 5.1 Sample 001 — gdpr_eurlex (obligation, GDPR lawfulness principle)

| Field | R13.4.2 | R13.7 | Change |
|---|---|---|---|
| modality | exact | exact | — |
| actor | missing (null) | exact | null → "entity processing personal data" |
| action | wrong ("processed") | exact ("process personal data") | verbatim fragment → normalized form |
| condition | n/a | n/a | — |
| constraint | partial | exact | partial → exact |

Likely reason: Prompt B's few-shot passive-voice example with inferred actor ("entity processing personal data") may have directly influenced this output. The JSON-only instruction may have encouraged normalized action phrasing.

### 5.2 Sample 002 — gdpr_eurlex (obligation, purpose limitation)

| Field | R13.4.2 | R13.7 | Change |
|---|---|---|---|
| modality | exact | exact | — |
| actor | missing (null) | partial ("entity collecting personal data") | null → partial |
| action | wrong ("collected") | partial ("collect and process personal data") | verbatim → partially normalized |
| condition | n/a | n/a | — |
| constraint | partial | partial | — |

Likely reason: The few-shot examples may have prompted actor inference, but the compound action ("collect and further process") in the gold was only partially captured. The embedded negative constraint within the obligation may have complicated action extraction.

Remaining weakness: Compound actions with embedded sub-clauses may still be challenging.

### 5.3 Sample 003 — gdpr_eurlex (obligation, data minimisation)

| Field | R13.4.2 | R13.7 | Change |
|---|---|---|---|
| modality | exact | exact | — |
| actor | missing (null) | exact | null → "entity processing personal data" |
| action | wrong ("be adequate, relevant and limited") | exact ("process personal data") | constraint text → correct action |
| condition | missing | missing | unchanged — both miss gold condition |
| constraint | partial | partial | — |

Likely reason: Sample 003's main clause is a data minimisation obligation ("Personal data must be adequate, relevant and limited..."). The baseline model confused the constraint text with the action. Prompt B may have helped separate action from constraint. The condition remains unrecognized in both runs.

Remaining weakness: Condition extraction from text where the condition is implicit in the constraint phrasing.

### 5.4 Sample 004 — gdpr_eurlex (obligation, consent demonstration)

| Field | R13.4.2 | R13.7 | Change |
|---|---|---|---|
| modality | exact | exact | — |
| actor | partial ("the controller") | exact ("controller") | minor change to exact |
| action | wrong (verbose) | partial | changed to partial; still not exact |
| condition | exact | exact | — |
| constraint | missing (null) | exact | null → correct constraint |

Likely reason: Sample 004 is the clearest obligation text in the set with an explicit actor ("the controller"). Both runs recognized the actor. Prompt B's constraint example may have guided the model to include the previously missed constraint.

Remaining weakness: Action normalization — the gold action is "demonstrate consent to processing" but R13.7 predicts a longer form.

### 5.5 Sample 005 — gdpr_eurlex (prohibition, special categories)

| Field | R13.4.2 | R13.7 | Change |
|---|---|---|---|
| modality | exact | exact | — |
| actor | missing (null) | exact ("entity processing personal data") | null → inferred actor |
| action | wrong ("Processing") | exact ("process special categories of personal data") | verbatim → normalized with semantic detail |
| condition | missing | exact | null → correct condition |
| constraint | wrong | partial | wrong → partial |

Likely reason: Prompt B's few-shot examples include a prohibition case that may have helped with both actor inference from passive constructions and action normalization. The condition (list of special categories) was also correctly identified.

### 5.6 Sample 006 — austrian_income_tax_code (definition, unlimited tax liability)

| Field | R13.4.2 | R13.7 | Change |
|---|---|---|---|
| modality | wrong (obligation) | exact (definition) | wrong → exact |
| actor | wrong (German labels) | exact ("natural persons") | German → English normalized |
| action | wrong (German verb) | exact ("be subject to unlimited income tax liability") | German verb → normalized English |
| condition | wrong | partial | wrong → partial |
| constraint | wrong | exact | wrong → exact |

Likely reason: This is the most dramatic single-sample change. Sample 006 is a German-language legal text (Austrian tax code). R13.4.2 produced outputs in German with obligation modality. Prompt B's few-shot demonstrations (all in English with normalized field values) may have guided the model toward English output with correct definition modality. The inclusion of a definition example in Prompt B's few-shot set may have been decisive for the modality correction.

Remaining weakness: The condition in R13.7 is partial — references "the country" instead of "Austria."

### 5.7 Sample 007 — austrian_income_tax_code (definition, unlimited tax liability scope)

| Field | R13.4.2 | R13.7 | Change |
|---|---|---|---|
| modality | exact (definition) | exact (definition) | — |
| actor | wrong (German, lowercased) | exact ("natural persons") | German → normalized English |
| action | wrong (German verb) | partial | German → English partial |
| condition | wrong | partial | wrong → partial |
| constraint | wrong | partial | wrong → partial |

Likely reason: R13.4.2 correctly identified definition modality even without few-shot (unlike sample 006). Prompt B shifted the output from German to English with different field-level scores, though action and condition remain partial.

### 5.8 Sample 008 — austrian_income_tax_code (definition, limited tax liability)

| Field | R13.4.2 | R13.7 | Change |
|---|---|---|---|
| modality | exact (definition) | exact (definition) | — |
| actor | wrong (German, lowercased) | exact ("natural persons") | German → normalized English |
| action | wrong (German verb) | partial | German → English partial |
| condition | wrong | partial | wrong → partial |
| constraint | wrong | partial | wrong → partial |

Likely reason: Same pattern as sample 007. Prompt B shifted German outputs to English with different field scores, though partial matches remain.

## 6. Observed Error-pattern Differences

### 6.1 Modality: Sample 006 Correction

R13.4.2's single modality error was sample 006, where the model classified a definition (German legal classification) as an obligation. This likely occurred because the baseline model associated the German verb "einkommensteuerpflichtig" with an obligation frame. R13.7 Prompt B corrected this to definition, which may be attributed to the definition example in the few-shot set.

### 6.2 Actor: From 0 Exact to 7 Exact

R13.4.2 produced null actors for 4/5 GDPR samples and German-language actor labels for 3/3 Austrian tax code samples. The null actors likely resulted from the baseline model's inability to infer agents from passive constructions. The German labels likely resulted from the model echoing input language without normalization.

R13.7 Prompt B produced English normalized actors in all 8 samples, with 7 exact matches. The few-shot examples include a passive-voice example with an inferred actor ("entity processing personal data"), which may have provided the necessary pattern for actor inference. The English-only few-shot examples may have encouraged English output even for German input.

### 6.3 Action: From 0 Exact to 4 Exact / 4 Partial

R13.4.2's actions were all scored wrong — the model extracted verbatim surface fragments (e.g., "processed", "collected", "Processing", German verbs) rather than normalized action phrases. Prompt B produced normalized action forms (e.g., "process personal data", "be subject to unlimited income tax liability") in all 8 samples. This is consistent with Prompt B's few-shot demonstrations showing normalized field values.

### 6.4 Condition/Constraint: Wrong Eliminated

R13.4.2 had 3 wrong and 2 missing conditions, and 4 wrong and 1 missing constraint. R13.7 eliminated all wrong labels for both fields. Conditions moved from wrong-dominated to partial-dominated (3 partial, 2 exact). Constraints moved to partial-dominated (5 partial, 3 exact). The elimination of wrong labels suggests Prompt B's JSON-only output instruction may have reduced hallucinated or malformed field content, though exact match remains challenging.

### 6.5 Exception: Not Assessable

None of the 8 gold samples contain an exception value. No comparison can be drawn for exception extraction.

## 7. Prompt B Interpretation

Prompt B (few_shot_extraction) differs from the baseline prompt in three ways:

1. **Few-shot demonstrations** (4 examples covering obligation, prohibition, definition, and passive-voice inference patterns)
2. **JSON-only output instruction** (structured output with explicit field keys)
3. **Field-specific normalization guidance** (normalized actor/action forms in examples)

The observed descriptive differences are consistent with these design changes:

- **Few-shot examples may have helped field normalization**: The shift from 0 to 7 exact actors and from 0 to 4 exact actions is consistent with the hypothesis that few-shot demonstrations provide normalization patterns that the baseline prompt lacks.
- **JSON-only instruction may have helped output consistency**: The elimination of wrong conditions and constraints (from 7 combined wrong to 0) may be attributable to the structured output format reducing malformed content.
- **Passive-voice example may have helped actor extraction**: The 4 null actors in R13.4.2's GDPR samples (all passive) becoming exact in R13.7 is consistent with the few-shot passive-voice example providing an inference pattern.
- **Definition example may have helped modality separation**: Sample 006's correction from obligation to definition may be attributed to the definition example in the few-shot set.

These observations suggest Prompt B's design may have contributed to the observed count differences in this 8-sample mini-pilot. They do not prove that Prompt B is superior, validate the prompt design method, or establish benchmark-level performance.

## 8. Remaining Weaknesses

Based on this limited 8-sample comparison:

1. **Action partial matches**: 4/8 actions remain only partial in R13.7, suggesting action normalization is not fully achieved.
2. **Condition extraction**: Only 2/6 applicable conditions are exact. One condition (sample 003) remains missing in both runs.
3. **Constraint partial dominance**: 5/8 constraints are only partial, suggesting constraint phrasing normalization needs further work.
4. **Exception coverage**: Exception extraction cannot be assessed from this sample set.
5. **Sample size**: 8 samples are too few for any statistical conclusion.
6. **Domain coverage**: Only 2 legal sources (GDPR EUR-Lex, Austrian Income Tax Code). Generalizability to other legal domains is unknown.
7. **German-language handling**: R13.4.2 produced German outputs for German inputs; Prompt B shifted to English. Whether this is desirable depends on the task specification.

## 9. Limitations

- **8 samples only**: This comparison is based on two 8-sample mini-pilots. No statistical significance can be claimed.
- **Same samples reused**: Both runs used the identical 8-sample set. No held-out or cross-validation was performed.
- **Mini-gold only**: The gold template was manually reviewed for 8 samples and is not a comprehensive gold standard.
- **Single model**: Both runs used qwen3.7-max. Observations may not transfer to other models.
- **Two domains only**: GDPR and Austrian tax code. Observations may not generalize to other legal domains.
- **No exception coverage**: The field-level comparison for exception is uninformative because no gold sample contains an exception.

## 10. Next Step Recommendation

1. **Return to Codex for R13.8 local-only audit** before drawing any conclusions.
2. **Consider another bounded test** with a different prompt variant (e.g., Prompt A or C from R13.6) to gather more descriptive evidence.
3. **Expand the sample set** before any claim of method performance, but only after user authorization and new data intake.
4. **Do not treat this comparison as benchmark, method validation, or Sun reproduction.**

## 11. Claim Boundary

**This is not a benchmark.**
**This is not method validation.**
**This is not Sun reproduction.**
**This does not prove Prompt B superiority.**

This document is a descriptive comparison of two bounded 8-sample real API mini-pilots. It reports observed field-level and sample-level count differences only. The observations are specific to the 8 samples tested. No conclusion about the general performance of Prompt B, the extraction method, or the project's approach should be drawn from this comparison.

Future real API runs require fresh explicit user authorization.
