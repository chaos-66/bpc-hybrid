# SEP-C3 Definition Targeted Execution Plan v1

- Status: **prepared offline; not executed**
- New API calls authorized: **no**
- Suite: `SEP-C3-DEFINITION-TARGETED-REFINEMENT-001`
- Unique panel samples N: **42**
- Planned calls: **84** (BASE=42, R_DEF=42; A=0 new calls)
- Retry: **0** (identical for both arms)
- Model: `deepseek-v4-pro` / `DeepSeek-V4-Pro-0813`
- Sampling: `{"temperature": 0.0, "top_p": 1.0, "max_tokens": 4096, "retry": 0, "stream": false, "thinking": {"type": "disabled"}, "response_format": null}`

## Frozen inputs

- Panel: `configs/sep_c3_definition_targeted_panel_v1.json` SHA-256 `8ba4517f21402566d61364e86a5516e0ea89f1f82a32781b303eb7a53d97ec61`
- Schedule: `configs/sep_c3_definition_targeted_schedule_v1.json` SHA-256 `ed4b12fe5de27ae9611759e0aedb292cfa633bc853b07df867e3fb4291aa355a`
- Gold read timing: after predictions are fixed and hashed
- Prompt BASE system SHA-256: `9db8893c75af4c306f5f5142ea77b6c93b6a2bae79a72ba8dd0f2b3ca1985d4f`
- Prompt R_DEF system SHA-256: `95c234ab44357411fb493f7b3ed46a29e76ada91f02ce3d2c1cd6b7af0496843`

## Execution order

1. Re-validate panel, schedule, budget, prompt, parser, and evaluator hashes.
2. Render and persist offline request capsules.
3. Freeze and record the request-set hash and leakage audit.
4. Obtain explicit authorization for exactly 84 calls.
5. Execute BASE and R_DEF with identical model/config/parser/evaluator.
6. Canonicalize predictions and hash them before reading Gold for scoring.
7. Evaluate the frozen slices and report trade-offs; do not promote R_DEF automatically.

## Current authorization gate

- Leakage audit status: `BLOCKED_STRICT_LEAKAGE_CHECK`
- Blocking checks: `['strict_no_concrete_sample_id_in_rendered_model_prompt']`
- Decision: **STOP before real calls** until explicit user authorization for this exact suite/scope exists and any leakage residual is resolved.
