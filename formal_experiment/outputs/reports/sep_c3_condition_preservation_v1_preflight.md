# SEP-C3 condition-preservation v1 preflight

- overall_status: `FAIL_NOT_READY_FOR_RUN`
- preparation_status: `pass`
- authorization_status: `not_authorized`
- real_api_calls: `0`
- ready_to_run: `false`

| item | status | detail |
|---|---|---|
| `prompt_identity_and_unique_difference` | `pass` | BASE == old B, RC1 == old D, RC_KEEP == RC1 plus exactly one sentence. |
| `offline_render_450_hashes` | `pass` | All 450 scheduled request bodies rendered and hashed offline. |
| `fixed_schedule` | `pass` | 150 sample blocks x 3 arms, six permutations each 25 times, seed=20260919, frozen before run. |
| `input_gold_binding` | `pass` | Frozen EStG-150 input and formal Gold hashes are recorded in the budget. |
| `processing_validator_binding` | `pass` | Adapter, canonicalizer, validator, schema, and lightweight backend are bound; runtime dependency switching is forbidden. |
| `evaluator_binding` | `pass` | Frozen coarse five-field evaluator and shared literal-overlap backend are hash-recorded. |
| `failure_and_denominator_policy` | `pass` | Failures remain in the 150-sample denominator; retry=0; no result-dependent prompt change or resend. |
| `judgment_rules_and_bootstrap` | `pass` | Retention criteria, stop rules, paired bootstrap seed/resamples, and zero-in-interval rule are fixed. |
| `real_api_calls_zero` | `pass` | No transport was constructed and no .env was read in this preparation. |
| `authorization` | `fail` | authorization status is not_authorized; a new explicit user authorization is required. |
| `channel_unit_price` | `fail` | The actual channel unit price has not been verified; no confirmed USD cost or hard USD cap exists yet. |
| `execution_entrypoint` | `fail` | No new execution runner/transport was implemented in this zero-API round; the old runner execute path must not be reused. |

Blocking items: authorization, channel_unit_price, execution_entrypoint

This file records a zero-API preparation state. It must not be read as execution authorization.
