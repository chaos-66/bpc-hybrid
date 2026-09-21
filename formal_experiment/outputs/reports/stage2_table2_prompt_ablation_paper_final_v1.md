# Table 2 - Stage 2 prompt-design ablation (EStG-150, coarse sentence view)

Report id: `stage2_table2_prompt_ablation_paper_final_v1` - re-scored from the existing 450 real calls, **0 new LLM calls** - same metric family as Table 1.

## Main table

| Prompt arm | Module removed | Modality (macro-F1) | Actor | Action | Condition | Constraint | Exception | Overall (pooled 5) | d Overall vs Full (pp) |
|---|---|---|---|---|---|---|---|---|
| Full (all modules) | - | 0.754 | 0.708 | 0.919 | 0.841 | 0.758 | 0.700 | 0.8224 | +0.00 |
| Full - Examples (E) | semantic examples (E) | 0.763 | 0.570 | 0.912 | 0.865 | 0.762 | 0.737 | 0.8142 | -0.83 |
| Full - Guidance (S) | semantic interpretation guidance (S) | 0.708 | 0.764 | 0.885 | 0.845 | 0.777 | 0.746 | 0.8299 | +0.74 |
| Full - JSON discipline (J) | explicit JSON output contract (J) | 0.752 | 0.698 | 0.940 | 0.819 | 0.763 | 0.818 | 0.8268 | +0.43 |

## Overall metric detail (pooled five span-bearing fields)

| Prompt arm | Precision | Recall | F1 | Gold spans | Extracted | Mean-of-5 F1 | Valid outputs |
|---|---|---|---|---|---|---|---|
| Full (all modules) | 0.8150 | 0.8301 | 0.8224 | 459 | 708 | 0.7850 | 150/150 |
| Full - Examples (E) | 0.7743 | 0.8584 | 0.8142 | 459 | 771 | 0.7691 | 150/150 |
| Full - Guidance (S) | 0.8319 | 0.8279 | 0.8299 | 459 | 690 | 0.8033 | 150/150 |
| Full - JSON discipline (J) | 0.8130 | 0.8410 | 0.8268 | 459 | 722 | 0.8076 | 150/150 |

## Per-field delta vs Full (percentage points)

| Prompt arm | Actor | Action | Condition | Constraint | Exception |
|---|---|---|---|---|---|
| Full (all modules) | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 |
| Full - Examples (E) | -13.86 | -0.63 | +2.46 | +0.40 | +3.68 |
| Full - Guidance (S) | +5.54 | -3.30 | +0.41 | +1.93 | +4.56 |
| Full - JSON discipline (J) | -1.05 | +2.16 | -2.18 | +0.53 | +11.82 |

## Paired per-sample comparison vs Full (10,000 resamples)

| Prompt arm | n | mean delta F1 (pp) | 95% CI (pp) | CI excludes 0 |
|---|---|---|---|---|
| Full (all modules) | 150 | +0.000 | [+0.000, +0.000] | no |
| Full - Examples (E) | 150 | +0.408 | [-2.616, +3.646] | no |
| Full - Guidance (S) | 150 | +2.216 | [-0.710, +5.270] | no |
| Full - JSON discipline (J) | 150 | +1.339 | [-0.977, +3.915] | no |

## Paired per-field deltas vs Full (pp, 95% CI, 10,000 resamples)

| Prompt arm | Field | mean delta (pp) | 95% CI (pp) | CI excludes 0 |
|---|---|---|---|---|
| Full - Examples (E) | Actor | -0.051 | [-1.695, +1.816] | no |
| Full - Examples (E) | Action | +0.956 | [-3.178, +5.244] | no |
| Full - Examples (E) | Condition | +4.222 | [+1.333, +7.778] | yes |
| Full - Examples (E) | Constraint | +2.519 | [-3.188, +8.355] | no |
| Full - Examples (E) | Exception | +0.000 | [-2.000, +2.000] | no |
| Full - Guidance (S) | Actor | -0.109 | [-1.997, +1.959] | no |
| Full - Guidance (S) | Action | +1.091 | [-2.731, +5.061] | no |
| Full - Guidance (S) | Condition | +0.222 | [-4.000, +4.222] | no |
| Full - Guidance (S) | Constraint | -2.083 | [-8.007, +3.528] | no |
| Full - Guidance (S) | Exception | +0.000 | [-2.000, +2.000] | no |
| Full - JSON discipline (J) | Actor | +0.133 | [-1.600, +2.000] | no |
| Full - JSON discipline (J) | Action | +3.467 | [+0.667, +6.800] | yes |
| Full - JSON discipline (J) | Condition | -3.333 | [-6.667, +0.000] | no |
| Full - JSON discipline (J) | Constraint | +1.740 | [-1.924, +5.644] | no |
| Full - JSON discipline (J) | Exception | +1.333 | [+0.000, +3.333] | no |

## Reading (what the ablation actually supports)

**The pooled overall F1 does not separate any arm from Full**: all three deletion deltas have 95% CIs that contain zero. The honest conclusion is therefore NOT 'every module lowers overall F1 when removed'.

The per-field paired test does separate some field-level effects, and they are **mixed in sign**, so they do not support a simple 'each module is necessary' claim either:

- **Examples (E)**: removing E *raises* Condition F1 (significant); Action/Constraint move the other way without a CI excluding zero. E therefore has a field-specific trade-off, not a uniform positive contribution.
- **Guidance (S)**: no field effect is statistically separable from noise at this sample size. S is not established as contributing on this metric.
- **JSON discipline (J)**: removing J *raises* Action F1 (significant) while Condition moves down; all four arms already produce valid JSON and a valid canonical schema at 150/150. J is therefore the BASE OUTPUT CONTRACT (an interface/validity guarantee), NOT an accuracy-improving module.

### Structural limits of this ablation (state these in the paper)

1. **E and S carry overlapping information.** The examples already illustrate the guidance rules, so a leave-one-out arm measures the *residual* after the other carrier is removed, not the module's standalone contribution. This is the recorded reason the modular single-factor ablation was superseded by the full 2^3 design.
2. **Power.** The coarse view has only 459 Gold spans over 150 samples, so small overall effects are not separable from sampling noise at one repeat per arm.
3. **One repeat per arm.** Per-cell repeats were designed but never authorized, so no variance estimate across re-executions exists.

The paired per-sample CI remains the appropriate evidence here: it uses the SAME 150 samples for every arm, so it does not depend on the across-arm execution order.

## Provenance

- Gold: `data/gold/stage2/estg150_formal_gold_v1.json`
- Real LLM calls behind these arms: 450 (DeepSeek-V4-Pro-0813)
- New LLM calls for this report: 0
- Full (all modules): prompt `direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md`, predictions sha256 `2dc036c3c72f54e1...`
- Full - Examples (E): prompt `direct_llm_no_semantic_examples_prompt_v2.md`, predictions sha256 `ba642d6a8377720b...`
- Full - Guidance (S): prompt `direct_llm_no_semantic_guidance_prompt_v2.md`, predictions sha256 `a32e60c7982765f1...`
- Full - JSON discipline (J): prompt `direct_llm_no_explicit_json_contract_prompt_v2.md`, predictions sha256 `a240a11a2bba3a0e...`

**Reproducibility caveat:** per-arm predictions live under the git-ignored outputs/development/ tree, so this re-score is reproducible on this machine but not from a fresh clone; the tracked aggregate report pins the six-field numbers and every arm hash.
