# bpc-hybrid workspace

The workspace is intentionally split into three areas:

```text
formal_experiment/   active, audited, reproducible experiment
references/          papers, external source code, datasets, and tools
archive/             historical rounds, outputs, caches, and unused material
```

Only `formal_experiment/` is active experiment code. Start with:

- `formal_experiment/docs/MASTER_PIPELINE.md`
- `formal_experiment/docs/PROJECT_AUDIT.md`
- `formal_experiment/README.md`
- `formal_experiment/AGENTS.md`

Mandatory audit from this root:

```powershell
python formal_experiment/scripts/audit_project.py --with-tests
```

Material changes are recorded with
`formal_experiment/scripts/record_change.py`; see the formal README for the
required safety declarations.

`references/` and `archive/` are retained for provenance. They must not be
imported by formal code or used as current experimental evidence.

The hidden `.agents/` and `.pytest_cache/` directories are tool-managed empty
workspace state and are not part of the experiment.
