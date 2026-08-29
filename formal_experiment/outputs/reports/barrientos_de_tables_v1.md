# Barrientos D/E Result Tables v1.2 (four-table separation)

## Table D — D prompt/few-shot ablation (DeepSeek-V4-Pro-0813)

| arm | overall F1 | overall P | overall R | parse ok | nonempty canonical | fail% |
| 完整六字段提示（含 4-shot） | 0.772 | 0.820 | 0.729 | 1.000 | 0.987 | 0.000 |
| 去掉 few-shot 示例 | 0.000 | 0.000 | 0.000 | 0.980 | 0.000 | 0.020 |
| 极简任务与 JSON 要求 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| Barrientos 风格结构约束替换 | 0.000 | 0.000 | 0.000 | 0.993 | 0.000 | 0.007 |

delta vs D-full-0813 (module effect, 0813 window only):
- 去掉 few-shot 示例: overall F1 -0.772
- 极简任务与 JSON 要求: overall F1 -0.772
- Barrientos 风格结构约束替换: overall F1 -0.772

model-drift appendix: model-version sensitivity (Preview vs V4-Pro-0813); explicitly NOT a prompt/module ablation contribution

## Table A — Barrientos-native (BARR-FULL)

| repeat | pre P | pre R | pre F1 | norm P | norm R | norm F1 | validity | coverage | fail% |
| repeat-01 | 0.750 | 0.818 | 0.783 | 0.949 | 0.712 | 0.813 | 1.000 | 1.000 | 0.000 |
| repeat-02 | 0.692 | 0.818 | 0.750 | 0.951 | 0.750 | 0.839 | 1.000 | 1.000 | 0.000 |
| repeat-03 | 0.750 | 0.818 | 0.783 | 0.929 | 0.750 | 0.830 | 1.000 | 1.000 | 0.000 |
| repeat-04 | 0.750 | 0.818 | 0.783 | 0.927 | 0.731 | 0.817 | 1.000 | 1.000 | 0.000 |
| repeat-05 | 0.739 | 0.773 | 0.756 | 0.950 | 0.731 | 0.826 | 1.000 | 1.000 | 0.000 |

self-consistency (paper distance<=2): 0.8806 (pairwise=360)

## Table B — Ours-native (OURS-FULL vs OURS-BARRIENTOS-MODULE)

| metric | OURS-FULL mean | OURS-FULL SD | swap mean | swap SD | delta |
| overall_f1 | 0.874 | 0.003 | 0.000 | 0.000 | -0.874 |
| overall_p | 0.862 | 0.008 | 0.000 | 0.000 | -0.862 |
| overall_r | 0.887 | 0.003 | 0.000 | 0.000 | -0.887 |
| actor_f1 | 0.821 | 0.013 | 0.000 | 0.000 | -0.821 |
| action_f1 | 0.963 | 0.000 | 0.000 | 0.000 | -0.963 |
| condition_f1 | 0.790 | 0.004 | 0.000 | 0.000 | -0.790 |
| constraint_f1 | 0.764 | 0.000 | 0.000 | 0.000 | -0.764 |
| exception_f1 | 0.000 | 0.000 | 0.000 | 0.000 | +0.000 |
| parse_success_rate | 1.000 | 0.000 | 1.000 | 0.000 | +0.000 |
| nonempty_canonical_clause_rate | 1.000 | 0.000 | 0.000 | 0.000 | -1.000 |
| failure_rate | 0.000 | 0.000 | 0.000 | 0.000 | +0.000 |
| modality_label_macro_f1 | 0.617 | 0.000 | 0.000 | 0.000 | -0.617 |

## Table C — Shared-target (same Gold, same metric)

| arm | ob F1 | per F1 | pro F1 | macro F1 |
| Barrientos 原生方法 | 1.000 | 0.781 | 0.889 | 0.890 |
| 本文完整方法 | 1.000 | 0.667 | 0.800 | 0.822 |
| 本文方法替换为 Barrientos 提示模块 | 0.000 | 0.000 | 0.000 | 0.000 |

not expressible: actor_action_exception=not_expressible_in_barrientos_schema, definition=not_expressible_in_barrientos_schema, precondition=not_strictly_alignable

---

**Table D F1 (0813-window D prompt/few-shot ablation) and Table A F1 (Barrientos-native) and Table B F1 (Ours-native) use different schemas/evaluators and MUST NOT be compared directly. Only Table C (same Gold, same metric function via deterministic adapters) is a legitimate cross-method comparison, and only on the pre-defined shared targets. The old Preview D-full is NEVER part of any module delta.**

