# Stage 3 Table 3 (eligibility-audited paired benchmark)

- benchmark: `stage3_paired_benchmark_v1`
- eligibility protocol: `data/development/stage3_synth/stage3_paired_benchmark_eligibility_v1.json`
- eligible pairs: missing_action=8, incorrect_actor=5, out_of_order=0

| Method | Missing P | Missing R | Missing F1 | Actor P | Actor R | Actor F1 | Order P | Order R | Order F1 | Macro-F1 | Micro-F1 | Specificity | Exact type | Unobs. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sun et al. reconstruction | 0.5000 | 1.0000 | 0.6667 | 0.5000 | 0.2000 | 0.2857 | N/A | N/A | N/A | 0.4762 | 0.5806 | 0.0000 | 0.6923 | 8 |
| Winter et al. wrapper | 0.5000 | 1.0000 | 0.6667 | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | N/A | 0.3333 | 0.5517 | 0.3846 | 0.6154 | 0 |
| Ours (automatic grounding) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | N/A | N/A | N/A | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| Oracle / Grounded Upper Bound (supplied binding) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | N/A | N/A | N/A | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |

Macro-F1 is over eligible types with a non-empty denominator (missing_action and incorrect_actor). out_of_order is N/A because the supplied Rule Records do not express an explicit rule-side order relation.

The Oracle/Grounded Upper Bound uses supplied human bindings and is never reported as Ours.
