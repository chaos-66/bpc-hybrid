# S2.13 → S3.7 Transition Readiness v9

- S2.11: **verified / frozen**, 36/36 adjudicated; formal Gold published.
- S2.12: **partial**; `sun_rule_only` zero-API arm complete; `direct_llm` and `sun_llm_fallback` await the process-environment credentials.
- S2.13: **blocked only on remaining S2.12 DoD**.
- S3.4–S3.6: **development-only**.
- S3.7: **Gold Rule Records published** (9 rules / 74 sentences / 92 items; independent verifier verified); **Oracle isolation run** on the frozen development evaluation surface; **formal main table not started or authorized**.

## Oracle isolation (frozen development evaluation surface)

| rule source | macro-F1 | exact | detected | unobservable |
|---|---:|---:|---:|---:|
| oracle | 0.3333 | 0.3333 | 11 | 11 |
| oracle_obligation_only | 0.3175 | 0.3030 | 10 | 11 |
| reference | 0.3889 | 0.3636 | 12 | 10 |

The complex-corpus result is one zero-API arm, not a three-method comparison. No post-result method, rule, prompt, threshold, or Gold adjustment was made.

Historical verifier lifecycle: v1 verifies; v2–v8 fail closed with their exact expected superseded-snapshot signatures (their Gold-Rule-Record absence probe is no longer true).
