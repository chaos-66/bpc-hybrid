# Out-of-order eligibility recheck v1

Re-read of the frozen eligibility evidence for all 10 out-of-order pairs. The check is rule-side: a pair is eligible only when the supplied Rule Records contain an explicit/entailed ordering relation between two human-approved rule-action endpoints. Process-side order mutations alone are not eligible.

| Pair | Rule | Regulation chars | Explicit order cues | Direct-LLM rule order relations | Gold rule order relations | Human order scope | Eligible |
|---|---:|---:|---|---:|---:|---|---:|
| `syn_out_of_order_01` | `article33` | 1867 | after, without undue delay after | 0 | 0 | process_only | False |
| `syn_out_of_order_02` | `article33` | 1867 | after, without undue delay after | 0 | 0 | process_only | False |
| `syn_out_of_order_03` | `article22` | 1343 | none | 0 | 0 | process_only | False |
| `syn_out_of_order_04` | `article22` | 1343 | none | 0 | 0 | process_only | False |
| `syn_out_of_order_05` | `article15` | 3574 | following | 0 | 0 | process_only | False |
| `syn_out_of_order_06` | `article20` | 1175 | none | 0 | 0 | process_only | False |
| `syn_out_of_order_07` | `article17` | 2800 | following | 0 | 0 | process_only | False |
| `syn_out_of_order_08` | `article17` | 2800 | following | 0 | 0 | process_only | False |
| `syn_out_of_order_09` | `article16` | 349 | none | 0 | 0 | process_only | False |
| `syn_out_of_order_10` | `article15` | 3574 | following | 0 | 0 | process_only | False |

## Result

- eligible out-of-order pairs: **0**
- reason for every pair: `ineligible_no_explicit_rule_order` (pair 03 also has an unresolved action binding, but the ordering ground is still absent).
- cue words such as `after` / `following` are diagnostic only; they do not provide two human-approved rule-action endpoints and an explicit/entailed relation.
- Paper boundary: do not report an out-of-order performance row. Keep `out_of_order = N/A`; the method section may state that the checker implements order-relation checks, but the current benchmark has no human-supported rule-side ordering relation and therefore contributes no formal performance denominator.

