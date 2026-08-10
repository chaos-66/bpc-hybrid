# direct_llm method gate decision v2 (DRY-RUN, not applied)

- status: dry_run_not_applied
- zero-API default path after authorization: no new LLM budget
- binding_ok: True

## Purpose
- D1 is a CANDIDATE, not yet formally authorized. The historical 150-row snapshot (s27_d1_v6_r3_clean_rerun_150_hist56d_v1) IS bound to formal input v2 (IDs, per-row input text hashes, prompt/model/sampling locks, schema-validity all verified). After the user authorizes the method gate, the DEFAULT path is a zero-API formal publication OF THAT SNAPSHOT (same Gold views, same evaluators) -- NO new API call. A new LLM budget is only needed if the binding breaks or the user explicitly requests a rerun. The v1 claim that a formal run necessarily needs a new LLM budget was incorrect and is removed.

## Zero-API path
- publish the existing bound snapshot zero-API (no new LLM budget required); new API budget ONLY if binding breaks or user explicitly requests a rerun
- new LLM calls required for default path: 0

## Proposed change
- before: blocked_until_official_data_output_contract_and_evaluator_are_locked
- after: ready / formal_ready_candidate_authorized
- simulated blockers: {'formal_methods_not_ready': {'present': True, 'non_ready_methods': {'sun_llm_fallback': 'blocked_until_faithful_baseline_data_and_triggers_are_locked'}}, 'methods_unexpectedly_ready': {'present': False}, 'final_experiment_ready': False, 'note': 'simulation under CURRENT audit/status semantics; final_experiment_ready stays False because the formal capsule/readiness hardening gates are not met'}

## Risks
- formal publication of the D1-R3 snapshot reuses the locked v6 prompt (3aa64877) and deepseek-v4-pro recipe; the snapshot was produced on the official API without json_object. Candidate metrics are NOT formal until authorized.

## Rollback
- git revert of the applied commit (methods.json only)
