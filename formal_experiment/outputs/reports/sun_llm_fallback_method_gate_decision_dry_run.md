# sun_llm_fallback method gate decision (DRY-RUN, not applied)

- status: dry_run_not_applied
- proposed formal_status: comparison_only_ready
- zero-API binding: True
- new LLM calls: 0

## Authorization sentence (copy-ready)
> I authorize recording configs/methods.json sun_llm_fallback as comparison-only: formal_status blocked_until_faithful_baseline_data_and_triggers_are_locked -> comparison_only_ready (command_status formal_ready_candidate_authorized), based on the zero-API binding evidence; this does NOT authorize any further LLM optimization or a formal fallback run.

## Expected audit changes
- formal_methods_not_ready would drop sun_llm_fallback (2 -> 1 non-ready method); final_experiment_ready stays False while direct_llm is blocked.

## Rollback
- git revert of the applied commit (methods.json only)
