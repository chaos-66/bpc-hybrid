# SEP-C3 modular E/S/J full 2^3 ablation

- status: complete_full8
- model: deepseek-v4-pro (DeepSeek-V4-Pro-0813)
- primary metric: `coarse_five_field_mean_f1`
- existing four cells: original execution binding
- new four cells: current implementation binding
- warning: batch/time is confounded between the original four cells and the new four cells.

| E S J | mean F1 | micro F1 | modality macro-F1 | failed | delta vs 111 | binding |
|---|---:|---:|---:|---:|---:|---|
| 111 | 0.7262056454982766 | 0.7902398853428036 | 0.7535381285381285 | 0 | 0.0 | original_execution_binding |
| 011 | 0.7469554158324833 | 0.8031520481113739 | 0.7635337942092276 | 0 | 0.02074977 | original_execution_binding |
| 101 | 0.7610556475180569 | 0.8144330550967624 | 0.755381204656567 | 0 | 0.03485 | original_execution_binding |
| 110 | 0.7355390106019669 | 0.7969838964033982 | 0.7488343081854532 | 0 | 0.00933337 | original_execution_binding |
| 100 | 0.7787634292011848 | 0.8153213060016736 | 0.7652542313536831 | 0 | 0.05255778 | current_implementation_binding |
| 010 | 0.727789654206652 | 0.7991018124142355 | 0.7523765344831649 | 0 | 0.00158401 | current_implementation_binding |
| 001 | 0.618355882378658 | 0.6616907569846889 | 0.7068581595284779 | 0 | -0.10784976 | current_implementation_binding |
| 000 | 0.6367491210830866 | 0.647329617951731 | 0.6937651968710171 | 0 | -0.08945652 | current_implementation_binding |

```json
{
  "E_main_effect": 0.06792841,
  "S_main_effect": 0.03539141,
  "J_main_effect": -0.00656716,
  "two_way_ES": -0.16344954,
  "two_way_EJ": -0.02849913,
  "two_way_SJ": 0.00837442,
  "three_way_ESJ": -0.02918458
}
```
