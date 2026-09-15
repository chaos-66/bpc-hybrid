# SEP-C3 modular E/S/J ablation

- status: complete_real_execution
- planned calls: 600
- actual API attempts total: 600 (541 new sends in the resumed process; 59 durable rows reused after a shell reset; no duplicate sample sends)
- primary metric: `coarse_five_field_mean_f1`
- old v6 full (reused D-full-0813): 0.7850304424814778

| arm | mean F1 | micro F1 | modality macro-F1 | failed | delta vs old | delta vs 111 |
|---|---:|---:|---:|---:|---:|---:|
| 111 | 0.7262056454982766 | 0.7902398853428036 | 0.7535381285381285 | 0 | -0.058825 | 0.0 |
| 011 | 0.7469554158324833 | 0.8031520481113739 | 0.7635337942092276 | 0 | -0.038075 | 0.02075 |
| 101 | 0.7610556475180569 | 0.8144330550967624 | 0.755381204656567 | 0 | -0.023975 | 0.03485 |
| 110 | 0.7355390106019669 | 0.7969838964033982 | 0.7488343081854532 | 0 | -0.049491 | 0.009333 |

Acceptance: **fail**

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
