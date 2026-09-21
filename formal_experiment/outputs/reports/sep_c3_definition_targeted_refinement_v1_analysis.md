# SEP-C3 Definition Targeted Refinement - Post-Execution Analysis

- Suite: `SEP-C3-DEFINITION-TARGETED-REFINEMENT-001`
- Scope: targeted development diagnostic; not an unbiased estimate of overall EStG performance
- API calls: 84 (A=0, BASE=42, R_DEF=42); additional calls: 0
- Transport/provider failures: 0
- Retry protocol: `retry=0, unchanged`

## Targeted clause set

- Unique clauses: 45 (definition=25, non-definition=20)
- Slices: {"A": 15, "C": 12, "B": 15, "D": 6}

## Arm metrics on the targeted clause set

| Arm | Modality acc. | Def P | Def R | Def F1 | Def->Obl | Obl->Def | Proh->Def | Perm->Def | Def action present | Empty actions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 0.4667 | 1.0000 | 0.1600 | 0.2759 | 15 | 0 | 0 | 0 | 20/25 (0.8000) | 5 |
| BASE | 0.5111 | 1.0000 | 0.3600 | 0.5294 | 7 | 0 | 0 | 0 | 22/25 (0.8800) | 3 |
| R_DEF | 0.7333 | 0.9500 | 0.7600 | 0.8444 | 2 | 1 | 0 | 0 | 22/25 (0.8800) | 3 |

Note: definition action presence is over the 25 Gold definitions in the
targeted clause set; a failed/missing canonical validation counts as no
action.

## A -> BASE

- Modality accuracy: 0.4667 -> 0.5111
- Definition recall: 0.1600 -> 0.3600
- Definition F1: 0.2759 -> 0.5294
- Definition->obligation: 15 -> 7
- Corrected relative to A: 6; regressed relative to A: 4

### A -> BASE corrected and regressed cases

| Direction | Sample | Clause | Gold | A | BASE | Slices |
|---|---|---|---|---|---|---|
| corrected | estg_000293 | c1 | definition | obligation | definition | A |
| corrected | estg_000302 | c1 | definition | obligation | definition | A |
| corrected | estg_000522 | c1 | definition | obligation | definition | A |
| corrected | estg_000572 | c1 | definition | obligation | definition | A |
| corrected | estg_000773 | c1 | definition | obligation | definition | A |
| corrected | estg_000776 | c1 | definition | obligation | definition | A |
| regressed | estg_000056 | c1 | obligation | obligation | None | C |
| regressed | estg_000075 | c1 | obligation | obligation | None | B |
| regressed | estg_000164 | c1 | definition | definition | None | C |
| regressed | estg_000635 | c1 | obligation | obligation | None | B |

## BASE -> R_DEF

- Definition recall: 0.3600 -> 0.7600
- Definition->obligation: 7 -> 2
- Definition action presence: 22/25 -> 22/25
- B non-definition `shall` false-definition rate: 0.0000 -> 0.0000
- All non-definition false-definition rate: 0.0000 -> 0.0500
- Corrected relative to BASE: 12; regressed relative to BASE: 2

### BASE -> R_DEF corrected and regressed cases

| Direction | Sample | Clause | Gold | BASE | R_DEF | Slices |
|---|---|---|---|---|---|---|
| corrected | estg_000037 | c1 | definition | obligation | definition | A |
| corrected | estg_000056 | c1 | obligation | None | obligation | C |
| corrected | estg_000071 | c1 | definition | obligation | definition | C |
| corrected | estg_000075 | c1 | obligation | None | obligation | B |
| corrected | estg_000080 | c4 | definition | obligation | definition | A |
| corrected | estg_000083 | c1 | definition | prohibition | definition | C |
| corrected | estg_000083 | c2 | definition | prohibition | definition | A |
| corrected | estg_000087 | c1 | definition | prohibition | definition | A |
| corrected | estg_000164 | c1 | definition | None | definition | C |
| corrected | estg_000414 | c1 | definition | obligation | definition | A |
| corrected | estg_000417 | c1 | definition | None | definition | D |
| corrected | estg_000854 | c1 | definition | None | definition | A |
| regressed | estg_000716 | c1 | prohibition | prohibition | None | B |
| regressed | estg_000716 | c2 | prohibition | prohibition | None | B |

## Non-definition `shall` controls (slice B)

| Arm | n | Modality accuracy | False definition | Rate |
|---|---:|---:|---:|---:|
| A | 15 | 0.9333 | 0 | 0.0000 |
| BASE | 15 | 0.8000 | 0 | 0.0000 |
| R_DEF | 15 | 0.7333 | 0 | 0.0000 |

## Secondary field diagnostics (frozen evaluator, 42-sample coarse panel slice)

| Arm | Mean five-field F1 | Micro F1 | Actor F1 | Action F1 | Condition F1 | Constraint F1 | Exception F1 | Sample-label acc. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 0.6697 | 0.7435 | 0.5373 | 0.8910 | 0.8557 | 0.4932 | 0.5714 | 0.5238 |
| BASE | 0.6876 | 0.7216 | 0.5303 | 0.8450 | 0.8381 | 0.4746 | 0.7500 | 0.6190 |
| R_DEF | 0.6617 | 0.7048 | 0.4286 | 0.8264 | 0.8036 | 0.5000 | 0.7500 | 0.7619 |

## Parse / schema validity and transport failures

| Arm | Request OK | Parse passed | Binding passed | Canonical validation passed | Canonical validation failed |
|---|---:|---:|---:|---:|---:|
| A | historical reuse | n/a | n/a | n/a | n/a |
| BASE | 38 | 42 | 42 | 38 | 4 |
| R_DEF | 37 | 42 | 42 | 37 | 5 |

- Transport/provider failures: 0.
- Retry policy: `retry=0, unchanged` - Changing the frozen zero-retry runner would require separate attempt accounting and retryable-status classification; the real transport redacts HTTP status.  The frozen protocol was therefore left unchanged, and any infrastructure failures are reported separately from semantic model failures.

## `apply/applies` stress cases (descriptive only)

| Sample | Clause | Gold | A | BASE | R_DEF |
|---|---|---|---|---|---|
| estg_000056 | c1 | obligation | obligation | None | obligation |
| estg_000071 | c1 | definition | obligation | obligation | definition |
| estg_000083 | c1 | definition | prohibition | prohibition | definition |
| estg_000128 | c2 | obligation | permission | permission | permission |
| estg_000145 | c1 | permission | permission | permission | permission |
| estg_000164 | c1 | definition | definition | None | definition |
| estg_000208 | c2 | obligation | obligation | obligation | obligation |
| estg_000209 | c2 | definition | prohibition | prohibition | prohibition |
| estg_000218 | c1 | definition | non_obligation | prohibition | None |
| estg_000306 | c1 | obligation | None | None | definition |
| estg_000664 | c1 | definition | obligation | obligation | obligation |
| estg_000800 | c1 | definition | prohibition | prohibition | None |

No lexical `apply => definition` rule was introduced or used.
