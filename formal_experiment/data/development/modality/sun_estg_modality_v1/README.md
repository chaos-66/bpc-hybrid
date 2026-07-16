# Sun EStG modality development area

This directory is the local-only S2.1-C target for the official
`EStG_sent_vec.csv` development import.

Versionable aggregate files are `.gitignore`, this `README.md`,
`schema_audit.json`, `manifest.json`, `split_summary.json`, and
`quarantine_manifest.json`. These aggregate files contain hashes, schema,
population counts, label counts, split statistics, and provenance only; they
must never contain raw sentences or vector values.

`records.jsonl` and `splits/{train,dev,test}.jsonl` are ignored here because the
official rights status remains `unknown_pending_confirmation`. They must not be
redistributed, uploaded, committed, copied into formal data directories, or
described as the Sun original split.

S2.1-C-R1 applies the user's pre-result governance decision
`pre_result_conflicting_label_group_quarantine`. The immutable raw population
remains 2,833 rows. The one exactly locked raw-text-identical group at source
row indices 616 and 1221 carries conflicting permission/obligation labels;
neither label is selected or changed, and the entire two-row group is excluded
from the 2,831-row main analysis population. Any conflict that does not exactly
match the locked source/hash/row/label contract remains fail-closed.

The local development split uses seed 20260715, ratios 0.70/0.15/0.15, and
normalized-text group-aware allocation. It is a
`project_reconstructed_deterministic_split`, not a Sun original split. The
full-source sensitivity variant is preregistered as `planned_not_run`; no
training, evaluation, or sensitivity run occurred in S2.1-C-R1.

S2.1-D made `contract_path` and `source_asset.local_path` project-relative and
locked this development area with an independent machine gate. The path-only
repair did not change the records or train/dev/test membership, row counts, or
SHA-256 values. The gate verifies the source identity, contracts, schema,
quarantine decision, artifact hashes, split invariants, local ignore policy,
and license boundary without extracting or rescanning the 470 MB CSV. This is
still development-only data, not formal Gold, a Sun original split, or an
authorization to train or evaluate a model.
