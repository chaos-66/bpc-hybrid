# Table 2 - v6 prompt-family 2^3 E/S/J factorial ablation

- status: **complete**
- primary metric: `coarse_five_field_micro_f1`
- Gold: `data/gold/stage2/estg150_formal_gold_v1.json`
- prompt family: `v6_chunk_direct_assembly`

| E S J | Modality macro-F1 | Actor | Action | Condition | Constraint | Exception | Overall pooled (micro) F1 | Mean-of-5 F1 | Delta overall vs 111 | Failed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 0 0 | 0.8338 | 0.4841 | 0.8649 | 0.8436 | 0.5613 | 0.7059 | 0.7380 | 0.6920 | -0.0844 | 0 |
| 0 0 1 | 0.8096 | 0.4682 | 0.8435 | 0.8648 | 0.5206 | 0.7778 | 0.7261 | 0.6950 | -0.0964 | 0 |
| 0 1 0 | 0.8006 | 0.5588 | 0.9027 | 0.8578 | 0.7779 | 0.6667 | 0.8107 | 0.7528 | -0.0117 | 0 |
| 0 1 1 | 0.7627 | 0.5697 | 0.9122 | 0.8652 | 0.7618 | 0.7368 | 0.8142 | 0.7691 | -0.0083 | 0 |
| 1 0 0 | 0.7370 | 0.7948 | 0.9181 | 0.8248 | 0.7654 | 0.7000 | 0.8354 | 0.8006 | +0.0129 | 0 |
| 1 0 1 | 0.7083 | 0.7637 | 0.8855 | 0.8446 | 0.7771 | 0.7456 | 0.8299 | 0.8033 | +0.0074 | 0 |
| 1 1 0 | 0.7520 | 0.6978 | 0.9401 | 0.8187 | 0.7631 | 0.8182 | 0.8268 | 0.8076 | +0.0043 | 0 |
| 1 1 1 | 0.7537 | 0.7083 | 0.9185 | 0.8405 | 0.7578 | 0.7000 | 0.8224 | 0.7850 | +0.0000 | 0 |

## Overall metric detail

| E S J | Precision | Recall | F1 | Source |
|---|---:|---:|---:|---|
| 0 0 0 | 0.7269 | 0.7495 | 0.7380 | v6_factorial_new_calls |
| 0 0 1 | 0.7119 | 0.7407 | 0.7261 | v6_factorial_new_calls |
| 0 1 0 | 0.7771 | 0.8475 | 0.8107 | v6_factorial_new_calls |
| 0 1 1 | 0.7743 | 0.8584 | 0.8142 | historical_same_release |
| 1 0 0 | 0.8430 | 0.8279 | 0.8354 | v6_factorial_new_calls |
| 1 0 1 | 0.8319 | 0.8279 | 0.8299 | historical_same_release |
| 1 1 0 | 0.8130 | 0.8410 | 0.8268 | historical_same_release |
| 1 1 1 | 0.8150 | 0.8301 | 0.8224 | historical_same_release |

## Main effects (overall pooled micro-F1 scale)

```json
{
  "E_main_effect": 0.05637197796916027,
  "J_main_effect": -0.004583695996826509,
  "S_main_effect": 0.036200027165982696,
  "three_way_ESJ": -0.014181958660408278,
  "two_way_EJ": -0.0006549709390174518,
  "two_way_ES": -0.08847751503991097,
  "two_way_SJ": 0.008305922366957486
}
```

## Provenance

- prompt manifest: `prompts/sun_compat/ablation_v2_factorial/manifest.json`
- Gold sha256: `c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100`
- historical 111/110/101/011: reused predictions from the same DeepSeek-V4-Pro-0813 release window.
- new 000/001/010/100: 600 calls in this batch.
- no Gold or benchmark mutation; evaluator fixed.
