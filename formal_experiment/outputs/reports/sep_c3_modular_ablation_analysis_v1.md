# SEP-C3 E/S/J modular Direct-LLM real-run analysis

**Decision: reject the modular v1 full prompt for default use; keep old v6 as default.**

## Result table

| version | samples | main P/R/F1 (micro five fields) | primary mean F1 (five fields) | Δmean F1 vs full 111 | raw bare-JSON valid | failures |
|---|---:|---:|---:|---:|---:|---:|
| old v6 full 0813 | 150 | 0.8150/0.8301/0.8224 | 0.7850 | +0.0588 | 107/150 (71.3%) | 0 |
| full 111 | 150 | 0.7730/0.8083/0.7902 | 0.7262 | +0.0000 | 150/150 (100.0%) | 0 |
| delete E 011 | 150 | 0.7779/0.8301/0.8032 | 0.7470 | +0.0208 | 150/150 (100.0%) | 0 |
| delete S 101 | 150 | 0.8370/0.7930/0.8144 | 0.7611 | +0.0348 | 150/150 (100.0%) | 0 |
| delete J 110 | 150 | 0.7779/0.8170/0.7970 | 0.7355 | +0.0093 | 150/150 (100.0%) | 0 |

The primary acceptance score is `coarse_five_field_mean_f1` (arithmetic mean of the five coarse sentence-level span-field F1 values). Micro P/R/F1 and modality-label metrics are reported separately and are not folded together.

## Per-field F1

| version | actor | action | condition | constraint | exception |
|---|---:|---:|---:|---:|---:|
| old v6 full 0813 | 0.7083 | 0.9185 | 0.8405 | 0.7578 | 0.7000 |
| full 111 | 0.5158 | 0.9287 | 0.8133 | 0.7416 | 0.6316 |
| delete E 011 | 0.5132 | 0.9128 | 0.8306 | 0.7723 | 0.7059 |
| delete S 101 | 0.6757 | 0.9285 | 0.8468 | 0.6876 | 0.6667 |
| delete J 110 | 0.4770 | 0.9250 | 0.8226 | 0.7770 | 0.6761 |

## Acceptance checks

```json
{
  "status": "fail",
  "checks": {
    "full_not_worse_than_old_by_more_than_0.01": false,
    "full_minus_011_at_least_0.01": false,
    "full_minus_101_at_least_0.01": false,
    "full_minus_110_at_least_0.01": false,
    "full_not_better_than_old?": null
  },
  "interpretation": "all three module deletions must have at least 0.01 lower coarse_five_field_mean_f1 than full 111; the full prompt must not be more than 0.01 below the comparable old v6 full baseline"
}
```

All checks fail: full 111 is 0.0588 below old v6; deleting E, S, and J is associated with +0.0208, +0.0349, and +0.0093 mean-F1 changes respectively, all opposite to or below the required +0.01 contribution from a kept module.

## Concrete findings
- Full 111 mean F1 fell 0.0588 below the comparable old v6 D-full-0813 baseline (0.7262 vs 0.7850).
- Actor precision is the largest single loss: 0.3538 vs 0.5732 old; 130 predicted actor spans vs 82 old, with only 46 matched predicted spans (84 false positives).
- Condition, constraint, and exception F1 also fell (0.8133 vs 0.8405; 0.7416 vs 0.7578; 0.6316 vs 0.7000). Action F1 rose slightly (0.9287 vs 0.9185).
- All three deletions (011, 101, 110) had higher mean F1 than full 111 by 0.0208, 0.0349, and 0.0093 respectively; none of the modules shows the required +0.01 increment.

## Module diagnosis

- **E**: The compact E examples are followed by omission of some condition/constraint/exception phrases; deleting E recovers them. This is an observed association, not proof of a single causal token.
  - `estg_000028` condition gold: `when taking into account the converted income`; full 111 predicted `[]`; delete-E 011 predicted `['when taking into account the converted income']`.
- **S**: The condensed S actor rule is associated with extra noun-phrase actors; deleting S raises actor precision from 0.354 to 0.517. The result does not isolate which wording caused it.
  - `estg_000664` gold actor spans: `[]`; full 111 predicted `['The following', 'Certain income, in particular foreign income', 'taxation', 'the tax base or the tax']`; old v6 predicted `['Certain income, in particular foreign income']`.
- **J**: Deleting J did not lower the primary metric; it was 0.0093 higher than full 111 (below the 0.01 acceptance threshold for a J contribution). Raw bare-JSON validity was already 150/150 without J, so this run provides no F1 or raw-format evidence for keeping J.

## Calls and provenance

- Planned calls: 600. Actual API attempts: 600. First process persisted 59 rows before a shell reset; the resumed process reused them and sent 541 new calls. Duplicate sample sends: 0.
- Input tokens: 915525; output tokens: 518029; cost: $3.25988784; missing-usage calls: 0.
- Old baseline source: outputs/development/barrientos_ablation_suite_v2/D-full-0813/repeat-01 (immutable 450-call factorial batch); same prompt SHA-256, input, model release, sampling and evaluator. Old baseline raw bare-JSON format was 107/150; one canonical source_text echo (estg_000092) contains literal \n instead of newlines. The evaluator scores spans against frozen Gold, so the metric is not affected by that echo difference.

## Default version

- Old v6 full remains default: `prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md`.
- Modular v1 is preserved as a tested, rejected candidate; do not use it as the default or as a formal replacement without a new pre-run threshold declaration and validation run.
