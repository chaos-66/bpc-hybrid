# direct_llm method gate decision (DRY-RUN, not applied)

- status: dry_run_not_applied
- proposed formal_status: ready
- zero-API binding: True
- new LLM calls: 0

## Authorization sentence (copy-ready)
> I authorize promoting configs/methods.json direct_llm formal_status from blocked_until_official_data_output_contract_and_evaluator_are_locked to ready (command_status formal_ready_candidate_authorized), based on the zero-API binding evidence in b0_d1_formal_readiness_v2 and the D1/H1 comparison capsule, acknowledging that a formal D1 run then requires an explicit separate LLM budget authorization.

## Expected audit changes
- formal_methods_not_ready would drop direct_llm (2 -> 1 non-ready method); final_experiment_ready stays False while sun_llm_fallback is blocked; methods_unexpectedly_ready must NOT trigger.

## Rollback
- git revert of the applied commit (methods.json only)
