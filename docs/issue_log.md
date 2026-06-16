# Issue Log

This document records implementation issues, audit findings, debugging decisions, and resolutions encountered during the `bpc-hybrid` rebuild.

The log supports reproducibility, implementation transparency, and later thesis or paper writing.

## Claim Boundary

This issue log does not report formal benchmark results. Synthetic prototype results are used only for pipeline sanity checking.

The project has not yet been evaluated on real GDPR data, real BPMN models, the original Sun dataset, or a Sun-aligned formal benchmark.

## Issue Table

| ID | Stage | Issue | Symptom | Root Cause | Fix | Verification | Commit |
|---|---|---|---|---|---|---|---|
| I001 | Codex Audit / R1.6 | GitHub private repo credential limitation | `git ls-remote` / remote hash verification failed in Codex sandbox | Codex sandbox lacked GitHub private repo credentials | Converted Codex to local-only audit; persisted audit report through MIMO | Codex local-only audit report persisted and pushed | 5323343 |
| I002 | R3 / R3.1 | Package import failure | `IndentationError` in `src/bpc_hybrid/__init__.py`; pytest and health script failed before validation | malformed `__all__` list with duplicate residual entries after list close | Fixed `__all__`, reran compile check and tests | py_compile passed; extractor tests passed; full pytest passed; health script passed | 6def21f |
| I003 | R4 | Action boundary bleeding | Extracted action could cross clause segment boundary after multi-clause splitting | extractor action extraction lacked segment end boundary | Added `end_bound` to action extraction and passed `seg.span_end` | splitter tests, extractor regression tests, and full pytest passed | 970a65c |
| I004 | R5 / R5.1 | CLI import failure | Direct execution of rule baseline and evaluation scripts failed with `ModuleNotFoundError: No module named 'bpc_hybrid'` | direct script execution did not add project `src/` to `sys.path` | Added project-local `src` path insertion to CLI scripts | direct CLI commands passed; evaluator tests passed; full pytest passed | 66046a1 |
| I005 | R5 / R5.1 | Prototype dataset ID mapping mismatch | Codex found required categories under wrong IDs | synthetic prototype dataset IDs were not aligned to the audit protocol | Updated legal and gold JSONL IDs to required mapping | dataset mapping tests passed; gold validation passed; evaluation command succeeded | 66046a1 |
| I006 | R6 / R6.1 | R6 documentation omitted resolved implementation issues | Codex R6 audit found that `docs/experiment_log.md` recorded R6 issues as none despite three test/validation fixes during implementation | R6 implementation logs were not fully reflected in experiment documentation | Updated R6 Issues and Resolutions with the actual resolved issues and corrected stale test counts | R6 documentation fix committed and pushed; Codex re-audit pending | pending |
| I007 | R7 / R7.1 | LLM config validation and documentation audit blockers | Codex R7 audit found disabled configs skipped provider/numeric validation, base_url secret material was not rejected, and R7 issue documentation was incomplete | R7 validation logic and documentation did not fully enforce audit requirements | Harden shared validation, reject secret-containing base_url, add tests, and update R7 issue documentation | R7.1 tests passed; Codex re-audit pending | pending |
| I008 | R7.2 | Incomplete base_url secret query coverage | Codex R7.1 audit found `access_token` and `authorization` were missing from secret query-key detection | Secret query-key list was incomplete | Added `access_token` and `authorization` detection plus regression tests | R7.2 tests passed; Codex re-audit pending | pending |
| I009 | R8 / R8.1 | Invalid dry-run error path returned success exit code | R8 verification found invalid LLM/mock response errors were emitted as JSON but the CLI process still returned exit code `0` | The dry-run CLI error path produced structured error output but did not propagate a non-zero process exit status | Updated the CLI to return non-zero on invalid LLM/mock response errors and documented the issue | R8 dry-run tests passed; full pytest passed; Codex re-audit pending | pending |