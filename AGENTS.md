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
2. Run the required focused checks, then
   `python formal_experiment/scripts/audit_project.py --with-tests`, and follow
   `formal_experiment/docs/AI_CHANGE_PROTOCOL.md` to append the matching event
   with `formal_experiment/scripts/record_change.py`.
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

Before editing, read `formal_experiment/AGENTS.md` and run:

```powershell
python formal_experiment/scripts/audit_project.py
```

After editing, run:

```powershell
python formal_experiment/scripts/audit_project.py --with-tests
```

Then follow `formal_experiment/docs/AI_CHANGE_PROTOCOL.md` and use
`formal_experiment/scripts/record_change.py` to append the tested change event.

Treat `references/` and `archive/` as read-only provenance stores. Moving an
item out of either directory, or making archived code active again, requires an
explicit audit-log entry and user approval. Never delete archived user data to
make a test pass.

Do not read or print `formal_experiment/.env`. Do not call a real LLM/API batch
without explicit user authorization.
