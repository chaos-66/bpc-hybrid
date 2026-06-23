# Checkpoint Protocol

## Required Git Behavior

Before making changes:

```bash
git status
git log --oneline -5
```
If there are uncommitted user changes, the agent must not overwrite them.

## Commit Rules
The agent must create a commit after each successful phase:

1. `checkpoint: precheck project state`
2. `checkpoint: document paper method alignment`
3. `checkpoint: repair harness`
4. `checkpoint: align rule baseline`
5. `checkpoint: run experiments and collect metrics`
6. `checkpoint: audit results`
7. `checkpoint: final report`

## Commit Message Format
Use:

```
R<round>: <short description>

- What changed
- Why it changed
- Verification command
- Harness result
```

## When to Stop
The agent must stop if:

1. The harness repeatedly fails for the same reason after 3 repair attempts.
2. The required dataset or paper reference is missing.
3. The project directory appears corrupted.
4. The current branch has uncommitted user work that cannot be safely separated.
5. The agent detects possible data leakage or metric manipulation.

## Log Requirement
After every significant action, update:

```
docs/RUN_LOG.md
```
Each log entry must include:

- Time
- Phase
- Files changed
- Command run
- Result
- Next action
```
