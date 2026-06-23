# Experiment Goal

## Main Goal

Reproduce the target Sun paper method as faithfully as possible, then evaluate whether a rule + LLM extension improves performance under the same evaluation protocol.

## Primary Research Questions

1. Does the current implementation match the Sun paper method?
2. If not, what exactly is mismatched?
3. What are the rule-only Precision, Recall, and F1 scores after paper alignment?
4. What are the rule + LLM Precision, Recall, and F1 scores?
5. Is the improvement real, or caused by evaluation/data/method mismatch?

## Required Metrics

For every experiment variant, report:

- True Positive
- False Positive
- False Negative
- Precision
- Recall
- F1
- Number of evaluated cases
- Number of skipped cases
- Reason for skipped cases, if any

## Required Experiment Variants

At minimum:

1. Paper-aligned rule-only baseline
2. Current project rule-only baseline, if different
3. Rule + LLM pipeline
4. Any proposed improved version

## Expected Suspicion to Investigate

If rule + LLM improves by an extremely large margin, the agent must investigate:

1. Whether the rule-only baseline is incorrectly implemented.
2. Whether the LLM pipeline is using extra information unavailable to the baseline.
3. Whether the evaluation protocol changed.
4. Whether the dataset differs from the paper.
5. Whether the gold labels or matching rules are too strict or too loose.
