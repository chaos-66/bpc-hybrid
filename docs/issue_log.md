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