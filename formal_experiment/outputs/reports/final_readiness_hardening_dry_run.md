# Final-readiness gate hardening (DRY-RUN, not applied)

- status: dry_run_not_applied

## Recorded defects
- status.py: final_experiment_ready computed from formal Gold + all-three-methods ready + input/Gold file counts; no requirement for the three-method formal predictions/results capsule to exist and pass independent verification
- status.py: no requirement that the G0.4 formal main-view reporting contract be user-authorized and publishable
- audit.py: methods_unexpectedly_ready error fires unconditionally whenever all three methods are ready; no recognized authorized terminal state exists

## Minimal reproduction (in-memory, no file modified)
- D1_alone_ready: final_experiment_ready(current)=False, methods_unexpectedly_ready(current)=False
- H1_comparison_only_ready_not_recognized: final_experiment_ready(current)=False, methods_unexpectedly_ready(current)=False
- all_three_ready: final_experiment_ready(current)=True, methods_unexpectedly_ready(current)=True
- key finding: all_three_ready -> final_experiment_ready=true under the current status.py logic while the three-method capsule is absent, and audit.py simultaneously raises methods_unexpectedly_ready -- the config flip alone opens the final gate; H1 comparison_only_ready is NOT recognized as ready (blockers unchanged)

## Proposed fail-closed target semantics
- method states must be in a user-approved formal terminal set
- the three formal arm capsules (sun_rule_only / direct_llm / sun_llm_fallback) must each exist AND pass their independent verifier
- shared comparison capsule hashes (input/Gold/schema/normalization/evaluators) must all agree
- the G0.4 formal main-view reporting contract must be user-authorized
- until all of the above hold, final_experiment_ready MUST stay false
- after user authorization AND real satisfaction of all conditions, methods_unexpectedly_ready must no longer fire
- a config status flip alone must not open the final gate early

## Required changes
### code
- status.py: add capsule-completeness + G0.4-authorization terms to final_experiment_ready
- audit.py: replace the unconditional methods_unexpectedly_ready error with a guarded check that only fires when methods are ready WITHOUT the required capsule/contract authorization
- audit.py: add passes for 'three formal capsules verified' and 'G0.4 main-view contract authorized'
### tests
- final gate stays false when only the B0 arm capsule exists
- final gate stays false when G0.4 contract not authorized
- methods_unexpectedly_ready does not fire in the authorized terminal state
### docs
- PROJECT_AUDIT / MASTER_PIPELINE gate tables updated to the new semantics after implementation (not in this dry-run)

## Unified authorization sentence (copy-ready)

> I authorize the formal evaluation-contract and final-readiness decisions: (1) the G0.4 formal main report consists of the sentence-level coarse five span-bearing fields plus the separate four-class modality-label metrics, with modality evidence-span metrics explicitly unavailable (never zeroed, never aggregated), fine-grained five fields as diagnostic/对照, and the historical six-field coarse aggregate retained as development provenance only; (2) the direct_llm method gate may move to ready with the existing bound D1-R3 snapshot published formally zero-API as the default path (new LLM budget only if the binding breaks or I explicitly request a rerun); (3) the sun_llm_fallback method gate may move to ready with role/notes marking it comparison-only (existing bound snapshot published formally zero-API as the comparison arm); (4) the final-readiness gate is hardened fail-closed so final_experiment_ready requires the three verified formal capsules, a consistent shared comparison capsule and the authorized G0.4 contract, and methods_unexpectedly_ready no longer fires in that authorized state.

## G0.4 decision proposal
- sentence-level coarse five span-bearing fields (actor/action/condition/constraint/exception) via the fixed Sun literal-overlap contract, PLUS the separate four-class modality-label metrics (accuracy + macro-F1)
- modality evidence-span: explicitly unavailable (published Gold modality is a plain string); never zeroed, never aggregated into any span aggregate
- fine-grained: diagnostic / 对照 view only
- historical aggregate: development provenance only; NOT formal (includes modality evidence-span numbers not reproducible from the published Gold)
- this is a formal evaluation-contract decision; it is applied only after explicit user authorization. main_view_publishable is NOT flipped by this package.
