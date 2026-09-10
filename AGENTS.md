# Workspace AI Contract

All active experiment changes must be made inside `formal_experiment/`.

## Mandatory Git Checkpoints

This section is a persistent instruction for every new conversation and every
agent working in this workspace. The user requires verified experiment progress
to be preserved on GitHub incrementally. Do not allow more than one coherent
pipeline task or subtask to accumulate only in the local working tree.

A Git checkpoint is mandatory whenever any of the following occurs:

- a task, subtask, gate, or milestone in
  `formal_experiment/docs/MASTER_PIPELINE.md` changes status or reaches its
  Definition of Done;
- a coherent material batch produces or changes versioned code, configuration,
  schema, prompt, data contract, manifest, evaluation, report, or experiment
  event;
- an authorized experiment run finishes and its manifest and experiment event
  have been recorded;
- verified material work is about to be handed to another agent, moved to a new
  conversation, or left at the end of a task.

At every checkpoint, perform the following sequence:

1. Inspect `git status` and the relevant diffs. Separate pre-existing or
   unrelated user changes from the checkpoint. In a mixed dirty worktree, never
   use blanket staging commands such as `git add .` or `git add -A`.
2. Select validation by the actual change scope using the policy below and
   `formal_experiment/docs/AI_CHANGE_PROTOCOL.md`. A checkpoint, commit, push,
   log entry, task completion, or handoff NEVER by itself requires full tests.
   Run only the applicable checks; record experiment-affecting work with
   `formal_experiment/scripts/record_change.py`. Artifact-only/document-only
   work may use the scoped Git commit as its change record.
3. Stage only the explicit files belonging to that coherent checkpoint with
   `git add -- <paths>`. Review `git diff --cached` before committing. Never
   stage `.env`, credentials, caches, prohibited third-party data, unapproved
   Gold changes, or unrelated user work.
4. Commit with a message that names the pipeline task or milestone and the
   verified outcome. A safe, reproducible but incomplete checkpoint must be
   labelled clearly as `checkpoint` or `WIP` and must not be described as
   verified or complete.
5. Push each successful checkpoint commit to the current branch's configured
   upstream with `git push`. Never force-push. If the upstream is missing, or
   authentication, network, branch protection, or a remote conflict blocks the
   push, stop and report the local commit hash and exact blocker; do not claim
   that the checkpoint is backed up remotely.
6. Verify and report the commit hash, branch, and push result in the task
   handoff. A pipeline point is not fully handed off until its commit is present
   on the configured remote, unless the user explicitly pauses pushing or a
   reported external blocker prevents it.

This standing checkpoint instruction authorizes ordinary scoped `git add`,
`git commit`, and non-force `git push` operations needed to preserve completed
work. It does not authorize broad staging, history rewrites, destructive Git
operations, publication of restricted data, real LLM/API calls, or bypassing
any experiment gate below.

## Validation Scope and Cost (user clarification, 2026-09-10)

This policy supersedes older blanket instructions to run full tests after
every edit, material batch, milestone, checkpoint, or handoff, including old
task templates and historical logs. Git backup remains mandatory and scoped;
it is independent of full-suite execution.

- Read-only analysis: no tests or experiment-log event.
- PPT, Word, prose, diagrams, formatting, and documentation-only edits that do
  not change executable experiment behavior: check the content, rendering,
  file integrity, and unchanged sections as applicable. Do NOT run the
  experiment audit or code suite merely because the artifact is in this repo,
  contains formulas/results, or will be committed. Use existing evidence to
  check claims; this does not authorize rerunning experiments.
- Experiment code, configuration, schema, prompts, data contracts, or
  evaluator changes: run one quick integrity check at the batch boundaries
  and only the named tests relevant to the changed behavior and its callers.
  Passing focused checks is sufficient for an ordinary scoped checkpoint;
  report the scope without claiming full-suite coverage.
- Full tests (including `pytest tests` and `audit_project.py --with-tests`)
  require explicit user authorization for this task. Before proposing them,
  identify the concrete cross-module risk or formal-release gate that focused
  checks cannot cover, state the exact scope, expected duration, and any
  already matching evidence. A direct user request for full tests supplies
  authorization; do not ask again. Generic requests to fix, verify, finish,
  commit, or push do not supply it. If authorization is absent, complete
  unaffected work and report the outstanding coverage; do not silently launch.
- Do not start duplicate suites in the shared workspace. Missing/stale
  receipts, unrelated failures, or an incomplete log are not authorization to
  expand or repeat tests. Reuse applicable exact-state evidence. Do not edit
  or rebind receipts to pretend they cover another state.
- For routine focused checks, plan a short run (normally within 3 minutes).
  Explain a known longer run before starting; on timeout or unrelated failure,
  report it and stop expansion. Do not delay a usable artifact for unrelated
  tests or poll unchanged results with repetitive status messages.

Before editing, read `formal_experiment/AGENTS.md`. For experiment-affecting
changes only, the quick check is:

```powershell
python formal_experiment/scripts/audit_project.py
```

After editing, follow the scope table in
`formal_experiment/docs/AI_CHANGE_PROTOCOL.md`; there is no automatic full
test step. `record_change.py` must not launch full tests when a receipt is
missing. Gold, API, and formal-release gates remain in force.

Treat `references/` and `archive/` as read-only provenance stores. Moving an
item out of either directory, or making archived code active again, requires an
explicit audit-log entry and user approval. Never delete archived user data to
make a test pass.

Do not read or print `formal_experiment/.env`. Do not call a real LLM/API batch
without explicit user authorization.
