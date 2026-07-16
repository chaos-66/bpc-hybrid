# Repository Reorganization Plan

**Date:** 2026-07-11  
**Rule:** move only, never delete; preserve all user and historical artifacts.

## Target Root

```text
bpc-hybrid/
  AGENTS.md
  README.md
  LICENSE
  .gitignore
  formal_experiment/   # only active experiment code and reproducibility assets
  references/          # papers, external source code, tools, source material
  archive/             # historical rounds, outputs, unused data, local clutter
```

## Formal Experiment

The active folder will contain:

- `src/bpc_hybrid/` and `src/formal_experiment/`
- the guarded formal runners and audit commands
- focused tests and fixtures
- Sun-compatible prompts
- development datasets kept separate from future frozen artifacts
- configs, annotation protocol, route lock, audit log, and manifests
- project-local `.env.example`, optional local `.env`, and `pyproject.toml`

All future experiment changes must occur inside `formal_experiment/` and pass:

```powershell
python formal_experiment/scripts/audit_project.py --with-tests
```

## References

- Sun 2024, Barrientos 2026, Michel 2022, and EStG source material.
- Imported `model_check` source under a clearly labelled non-exact-Sun folder.
- Barrientos/RC4PC input, expert evaluation material, notebooks, and tools.
- The legacy Python virtual environment, retained only as a convenience tool.

The 2.13 GB `Logs_for_Neo4J` event-log collection inside `Sun_program` is not
part of the relevant compliance source and will be archived separately.

## Archive

- all R0-R25 historical documentation and scripts not needed by the formal path
- prior predictions, metrics, reports, caches, and root `outputs/`
- unused data branches and Barrientos execution outputs
- old harnesses, transient files, editor settings, and non-formal tests

Archived content remains available for provenance but must not be imported by
the formal experiment or cited as current evidence.

## Safety Checks

1. Resolve every move source and destination under the workspace root.
2. Refuse destination overwrite.
3. Move secrets without reading them.
4. Do not modify Gold or prediction contents during migration.
5. Repair formal paths only after all moves finish.
6. Run the formal audit, focused tests, path-leak scan, and file inventory.
