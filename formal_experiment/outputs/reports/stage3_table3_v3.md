# Stage 3 Table 3 v3

- status: `complete_target_seeded_full_matching`
- scope: three complete pipelines over the full 9-rule Rule Base; the benchmark Gold is the labeled single-mutation target seed. Non-target alarms are reported only as diagnostics because the benchmark is not a complete multi-label compliance Gold.
- eligible pairs: 13
- eligible cases: 26
- Rule Base size: 9

## Matching AP/MAP (separate from checking)

| Method | MAP | Binary P | Binary R | Binary F1 | Recall@3 | Recall@5 |
|---|---:|---:|---:|---:|---:|---:|
| Ours | 0.4159 | 0.0000 | 0.0000 | 0.0000 | 0.3000 | 0.6000 |
| Sun | 0.3877 | 0.3333 | 0.1000 | 0.1538 | 0.2000 | 0.4000 |
| Winter | 0.4343 | 0.4545 | 1.0000 | 0.6250 | 0.5000 | 0.7000 |

## Main Table 3: target-seeded detection after full Rule Base matching

| Method | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ours | 0 | 0 | 13 | 13 | 0.0000 | 0.0000 | 0.0000 |
| Sun | 0 | 0 | 13 | 13 | 0.0000 | 0.0000 | 0.0000 |
| Winter | 8 | 8 | 5 | 5 | 0.5000 | 0.6154 | 0.5517 |

## Secondary per-type (target-seeded)

| Method | Type | Positive | Negative | P | R | F1 |
|---|---|---:|---:|---:|---:|---:|
| Ours | missing_action | 8 | 8 | 0.0000 | 0.0000 | 0.0000 |
| Ours | incorrect_actor | 5 | 5 | 0.0000 | 0.0000 | 0.0000 |
| Ours | out_of_order | 0 | 0 | N/A | N/A | N/A |
| Sun | missing_action | 8 | 8 | 0.0000 | 0.0000 | 0.0000 |
| Sun | incorrect_actor | 5 | 5 | 0.0000 | 0.0000 | 0.0000 |
| Sun | out_of_order | 0 | 0 | N/A | N/A | N/A |
| Winter | missing_action | 8 | 8 | 0.5000 | 1.0000 | 0.6667 |
| Winter | incorrect_actor | 5 | 5 | 0.0000 | 0.0000 | 0.0000 |
| Winter | out_of_order | 0 | 0 | N/A | N/A | N/A |

## Additional diagnostic: all alarms (incomplete multi-label Gold)

| Method | Any-alarm P | Any-alarm R | Any-alarm F1 | Strict TP | Strict FP | Strict FN |
|---|---:|---:|---:|---:|---:|---:|
| Ours | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 13 |
| Sun | 0.5000 | 0.1538 | 0.2353 | 0 | 20 | 13 |
| Winter | 0.5000 | 1.0000 | 0.6667 | 8 | 229 | 5 |

## Exclusions and limits

- eligible missing-action pairs: 8
- eligible incorrect-actor pairs: 5
- eligible out-of-order pairs: 0
- out-of-order unavailable: 10

The v3 run is protocol-correct for full Rule Base matching and Gold-blind inference. The main Table 3 is target-seeded: it asks whether the pipeline detects the single independently constructed mutation after it has performed its own full Rule Base matching. Do not present the any-alarm or strict-instance diagnostics as a complete multi-label compliance Gold.
