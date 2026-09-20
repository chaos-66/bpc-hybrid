# SEP-C3 Definition R_DEF Future Experiment Plan v1

- Status: **prepared only; not executed**
- New API / LLM calls: **0**
- Run authorization: **none**
- Final sample size: **not selected**
- Final API budget: **not selected**
- Gold modifications: **none**
- Prompt activation: **none**

## 1. Purpose

Determine whether the non-active `R_DEF` definition overlay improves the
systematic definition-modality failure without degrading non-definition
modality behavior, and whether it preserves the approved definition
action-presence behavior.  This is a future experiment plan only.

## 2. Available candidate counts (reported before any size or budget choice)

Counts are derived offline from the frozen Gold and frozen input only.

| Cohort | Clause count | Sample count |
|---|---:|---:|
| All clauses | 231 | 150 |
| All definition clauses | 39 | 34 |
| First-definition samples | - | 29 |
| Definition clauses containing `shall` | 15 | 15 |
| Non-definition clauses containing `shall` | 73 | 60 |
| Non-definition `shall` controls by Gold modality | obligation 64; prohibition 6; permission 3 | - |
| `apply` / `applies` clauses | 12 | 12 |
| `apply` / `applies` clauses with definition Gold | 7 | - |
| `apply` / `applies` clauses with non-definition Gold | 5 (4 obligation, 1 permission) | - |
| Gold definition action spans | 46 action spans across 39 clauses | - |
| Gold definition clauses with empty action | 0 | - |
| Definition clauses with a Gold condition | 28 | - |
| Definition clauses with a Gold constraint | 28 | - |
| Definition clauses with a Gold exception | 5 | - |
| Potential Gold inconsistency pair | 2 clauses (`estg_000505 c2`, `estg_000509 c2`) | 2 |

Additional frozen Gold totals:

- obligation clauses: 97;
- permission clauses: 62;
- definition clauses: 39;
- prohibition clauses: 33.

These counts are the prerequisite for later sample-size and budget choices.
No final sample size or API budget is selected in this report.

## 3. Candidate experiment arms to consider

The clean mechanism comparison keeps E4 v2 constant:

| Arm | Composition |
|---|---|
| `BASE` | frozen common + existing E examples with E4 v2 |
| `BASE_R_DEF` | `BASE` + approved `R_DEF` guidance |

Only the `R_DEF` paragraph differs.  This isolates the guidance effect from
the E4 replacement.

The active A/B/C/D prompts may be retained as historical reference controls,
but they contain the old E4 and are therefore not a clean causal contrast for
the definition-specific change.  Compatibility renderings with frozen `R_A`
and/or `R_C` may be used only if a later authorized design explicitly selects
them.

## 4. Required metric separation

The future analysis must report at least the following cohorts separately.

### 4.1 Definition clauses

- modality recall, precision, and F1 for Gold definition clauses;
- confusion of Gold definition into obligation, permission, and prohibition;
- evidence presence and evidence-span validity.

### 4.2 Shall-definition subset

- modality recall for the 15 definition clauses containing `shall`;
- false-obligation rate for this subset;
- comparison against the corresponding non-definition `shall` controls.

### 4.3 Non-definition "shall" controls

- modality accuracy for the 73 clauses where `shall` is present and Gold is
  obligation, prohibition, or permission;
- regression check: these clauses must not be reclassified as definition
  merely because `shall` appears;
- report by Gold modality.

### 4.4 Ambiguous apply/applies cases

- report the 12 `apply` / `applies` clauses separately;
- show Gold labels and predicted labels without collapsing the ambiguity into
  a lexical rule;
- report any change on near-identical `the following applies` cases;
- never use these cases alone to justify a phrase-level shortcut.

### 4.5 Overall modality accuracy

- clause-level accuracy across all 231 Gold clauses;
- macro/weighted definition and non-definition balances;
- confusion matrix over the four labels.

### 4.6 Definition recall / confusion

- definition true positives, false negatives, false positives;
- false positives from non-definition `shall` controls and apply/applies
  clauses;
- per-sample first-definition behavior.

### 4.7 Action-presence behavior

- share of Gold definition clauses with at least one predicted action;
- empty-action rate for Gold definition clauses;
- action span validity, coverage, and exact/overlap matching;
- whether the action is the definitional predicate and whether it remains
  separated from modality evidence;
- no universal exact action boundary is claimed or evaluated as a lexical
  rule.

### 4.8 Overall five-field extraction metrics

- actor, action, condition, constraint, exception precision/recall/F1;
- coarse five-field mean F1;
- paired changes versus the `BASE` arm on the same samples;
- unsupported/ambiguous reporting rate and parser/canonicalization failures.

## 5. Evaluation unit and pairing

- Use clause-level modality analysis and sample-level extraction analysis.
- Pair arms at sample level so every scheduled prompt is evaluated against
  the same frozen Gold.
- Report failed calls in the denominator exactly as the existing SEP-C3
  convention does; no result-dependent retry.
- Use the frozen canonicalizer/parser/evaluator bindings; do not change them
  for this candidate.

## 6. Safety and ambiguity policy

- Ambiguous apply/applies and potential Gold-inconsistency cases must be
  reported separately and must not be used to justify a lexical rule.
- `estg_000505 c2` vs `estg_000509 c2` remains
  `POTENTIAL_GOLD_INCONSISTENCY`.
- `S8` remains untouched.
- Condition/constraint boundary and exception guidance remain untouched.
- `R_A` and `R_C` remain unchanged.
- The prompt must not be described as a paper-level method/module.

## 7. Budget and sample-size gate

No sample size or API budget is selected yet.  A later authorization step
must first choose the cohort or stratified mixture, then calculate the
required number of calls from the reported counts and the selected repeat
policy.  The plan does not authorize any real call.

## 8. Blockers retained

- apply/applies ambiguity;
- potential Gold inconsistency `estg_000505 c2` / `estg_000509 c2`;
- exact action-span boundary remains evidence-bound;
- S8 boundary issue remains out of scope.