# Audit Rules

## Data Integrity

The agent must check:

1. Whether input datasets were modified.
2. Whether gold labels were modified.
3. Whether evaluation case count changed.
4. Whether skipped cases are documented.
5. Whether train/test or dev/test boundaries exist and were respected.

## Method Integrity

The agent must check:

1. Whether rule-only baseline uses only deterministic rules.
2. Whether LLM is excluded from rule-only baseline.
3. Whether LLM prompts contain gold labels or answer leakage.
4. Whether rule dictionaries were manually created as required by the target paper.
5. Whether all paper method assumptions are documented.

## Metric Integrity

The agent must check:

1. Precision formula.
2. Recall formula.
3. F1 formula.
4. TP / FP / FN counting.
5. Matching granularity.
6. Whether duplicate predictions are handled correctly.
7. Whether partial matches are counted consistently.

## Reporting Integrity

The agent must report:

1. All failed runs.
2. All changed files.
3. All metric outputs.
4. Any deviation from the Sun paper.
5. Whether the result should be trusted.

## Red Flags

The agent must explicitly investigate these red flags:

1. Rule-only result far below the paper.
2. LLM result far above rule-only result.
3. F1 improvement greater than 20 percentage points.
4. Case count mismatch.
5. Missing false positives or false negatives.
6. Evaluation script changed during implementation.
7. Gold labels changed during implementation.
