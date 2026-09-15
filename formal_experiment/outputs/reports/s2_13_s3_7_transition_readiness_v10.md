# S2.13 -> S3.7 Transition Readiness v10

- S2.11: **verified / frozen**, 36/36 adjudicated; formal Gold published.
- S2.12: **partial**; active methods Rules-Only / Direct-LLM; `sun_llm_fallback` is cancelled and not an experimental condition.
- S2.13: **blocked_only_on_two_method_contract**; not auto-marked complete.
- S3.4-S3.6: **development-only**.
- S3.7: **Gold Rule Records published** (9 rules / 74 sentences / 92 items; independent verifier verified); **Oracle isolation run** on the frozen development evaluation surface; **formal main table not started or authorized**.

## Two-method evidence

- comparison complete: **False**
- Rules-Only evidence: {'verified': True, 'input_binding_ok': True, 'all_36_rows': True, 'metrics_valid': True}
- Direct-LLM evidence: {'verified': False, 'input_binding_ok': False, 'all_36_rows': False, 'metrics_valid': False}
- remaining calls: {'s2_12_direct': 36, 'gdpr7_direct': 74, 'total': 110}
- S2.13 blockers: ['direct_llm_evaluation_missing_or_not_complete']

## Oracle isolation (frozen development evaluation surface)

| rule source | macro-F1 | exact | detected | unobservable |
|---|---:|---:|---:|---:|
| oracle | 0.3333 | 0.3333 | 11 | 11 |
| oracle_obligation_only | 0.3175 | 0.3030 | 10 | 11 |
| reference | 0.3889 | 0.3636 | 12 | 10 |

No post-result method, rule, prompt, threshold, or Gold adjustment was made. The cancelled repair arm is never consulted.

Historical verifier lifecycle: v1-v9 stay byte-exact; v9's three-method / API-arm S2.12 state is superseded by the two-method contract bound here.
