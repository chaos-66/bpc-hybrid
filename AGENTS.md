# Workspace AI Contract

All active experiment changes must be made inside `formal_experiment/`.

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
