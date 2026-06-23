# Agent Contract

## Mission

The agent must reproduce and audit the paper-aligned experiment pipeline for this project.

The goal is not to produce inflated metrics. The goal is to make the implementation, data processing, evaluation, and reported Precision / Recall / F1 genuinely aligned with the target paper method.

## Hard Objectives

1. Identify the exact method used in the target Sun paper.
2. Map each paper method component to the current project implementation.
3. Detect all mismatches between the paper method and current code.
4. Fix implementation mismatches.
5. Run a reproducible harness.
6. Report Precision, Recall, and F1 for:
   - rule-only baseline
   - rule + LLM pipeline, if applicable
   - any improved version
7. Produce an audit report explaining whether the result is trustworthy.

## Non-Negotiable Rules

The agent must not:

1. Change evaluation labels to improve metrics.
2. Change test data, gold data, or benchmark definitions without explicitly documenting why.
3. Silently weaken evaluation criteria.
4. Delete files outside the project directory.
5. Modify unrelated files.
6. Claim success without running the harness.
7. Claim paper alignment without filling METHOD_ALIGNMENT.md.
8. Hide failed experiments.
9. Report only accuracy. Precision, Recall, and F1 are required.
10. Use LLM output in the rule-only baseline.

## Required Workflow

The agent must work in phases:

1. Precheck
2. Paper-method analysis
3. Current-code audit
4. Harness repair
5. Method-alignment implementation
6. Experiment execution
7. Metrics collection
8. Self-audit
9. Final report

After each phase, the agent must:

1. Update docs/RUN_LOG.md.
2. Run relevant tests or harness commands.
3. Create a git commit if the project is in a valid git repository.
4. Stop if a critical safety or data integrity issue is found.

## Definition of Done

The task is complete only when:

1. `python scripts/run_harness.py` passes.
2. Precision / Recall / F1 are reported.
3. METHOD_ALIGNMENT.md is complete.
4. AUDIT_RULES.md checks are complete.
5. A final report exists under `data/formal/reports/`.
6. All changes are committed.
