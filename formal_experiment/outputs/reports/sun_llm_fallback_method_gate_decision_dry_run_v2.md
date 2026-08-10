# sun_llm_fallback method gate decision v2 (DRY-RUN, not applied)

- status: dry_run_not_applied
- zero-API default path after authorization: no new LLM budget
- binding_ok: True

## Purpose
- H1 keeps comparison-only / stop optimizing (2026-08-08 user/supervisor decision). The historical 150-row snapshot (s28d_h1_150_v4pro_v1) IS bound to formal input v2 and can be published formally as the comparison arm ZERO-API after authorization (no new API call). IMPORTANT: the proposed v1 status 'comparison_only_ready' is NOT recognized as ready by the current status/audit logic (status.py recognizes only 'formal_status == ready'; audit treats any other value as non-ready), so blockers would NOT decrease under it. Two reviewable options follow; nothing is applied.

## Zero-API path
- publish the existing bound snapshot zero-API as the formal comparison arm (no new LLM budget); new API budget only if binding breaks or user explicitly requests a rerun
- new LLM calls required for default path: 0

## Options (H1)
- Option A (recommended): ready + role/notes comparison-only; simulated blockers: {'formal_methods_not_ready': {'present': True, 'non_ready_methods': {'direct_llm': 'blocked_until_official_data_output_contract_and_evaluator_are_locked'}}, 'methods_unexpectedly_ready': {'present': False}, 'final_experiment_ready': False, 'note': 'simulation under CURRENT audit/status semantics; final_experiment_ready stays False because the formal capsule/readiness hardening gates are not met'}
- Option B: keep comparison_only_ready; requires audit/status semantics sync; simulated blockers (no sync): {'formal_methods_not_ready': {'present': True, 'non_ready_methods': {'sun_llm_fallback': 'blocked_until_faithful_baseline_data_and_triggers_are_locked', 'direct_llm': 'blocked_until_official_data_output_contract_and_evaluator_are_locked'}}, 'methods_unexpectedly_ready': {'present': False}, 'final_experiment_ready': False, 'note': 'simulation under CURRENT audit/status semantics; final_experiment_ready stays False because the formal capsule/readiness hardening gates are not met'}
- recommended: Option A: formal_status=ready with role='comparison_arm_only' and notes marking comparison-only -- uses the EXISTING terminal-set semantics and lets audit/status evaluate the arm correctly without semantic drift

## Risks
- H1 was net-negative (coarse F1 0.7621 vs B0 0.7986); the comparison-only boundary prevents further optimization or misuse; Option B without the audit/status sync would keep the method blocked with no visible effect.

## Rollback
- git revert of the applied commit (methods.json only)
