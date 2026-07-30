# Formal Experiment AI Contract

This directory is the only active experiment surface.

## Required Reading

1. `docs/MASTER_PIPELINE.md`
2. `docs/PROJECT_AUDIT.md`
3. `docs/AGENT_RUNBOOK.md`
4. `docs/DIRECTORY_GUIDE.md`
5. `docs/EXPERIMENT_LOG.md`（至少阅读最新事件）
6. `docs/REAL_WORLD_ISSUE_REGISTER.md`
7. `docs/AI_CHANGE_PROTOCOL.md`
8. `docs/ROUTE_LOCK.md`
9. `configs/experiment_contract.json`
10. `configs/methods.json`

`docs/MASTER_PIPELINE.md` is the sole whole-project roadmap and work-breakdown
structure. `docs/PROJECT_AUDIT.md` is the sole live status page. Update those two
files in place; do not create another dated status, handoff, or competing
pipeline document.

`docs/DIRECTORY_GUIDE.md` explains where every class of file belongs;
`docs/FILE_CATALOG.md` is the generated exhaustive file index. Retired material
under `_retired/` is read-only provenance and must never be imported or used as
an active task entry.

`docs/AGENT_RUNBOOK.md` defines task dispatch and copy-ready prompts. Live task
status remains only in `docs/PROJECT_AUDIT.md`. When writing the paper, also
read `paper/README.md` and `paper/CLAIM_EVIDENCE_MATRIX.md`; results without a
formal manifest must remain explicit TODOs.

Every practical problem observed in real data, annotation, method behavior,
runtime, provider output, or evaluation MUST be recorded in
`docs/REAL_WORLD_ISSUE_REGISTER.md`, even when it is fixed in the same batch.
Resolved entries must include the implemented method, validation evidence, and
the corresponding experiment event. Unresolved entries remain explicit and
must never be deleted or silently treated as solved.

Before editing human-review data, also read `docs/HUMAN_GOLD_GUIDE.md`.

Sun et al. (2024) supplies the complete three-stage methodological backbone.
Winter et al. (2020) supplies a Stage 3 comparison baseline. Barrientos et al.
(2026) is a candidate source for complex legal data and LLM structured-output,
validation, controlled-vocabulary, and normalization ideas; its labels must not
be treated as Sun-compatible without an explicit adapter and provenance check.

## Mandatory Literature-Grounded Method Control

- When the user asks to execute an existing method, execute that method as
  specified. Do not independently add, remove, or change prompts, models,
  thresholds, matching rules, metrics, statistical tests, bootstrap or other
  resampling, repeat counts, stopping rules, validation gates, datasets, or
  reporting requirements.
- Every methodological opinion, recommendation, or proposed change MUST first
  cite a verified prior publication and give the exact supporting location:
  page number plus section, table, figure, or equation as applicable. A vague
  appeal to "common practice", "greater rigor", or the agent's own judgment is
  not evidence and MUST NOT be used to alter or delay the requested task.
- The agent MUST inspect the cited primary source before relying on it. Project
  configuration, an earlier agent's plan, or a secondary summary does not prove
  that a method appeared in the cited paper.
- If no verified literature basis and exact location can be supplied, do not
  offer the methodological opinion and do not change the method. Continue by
  executing the user's requested method unchanged. If execution is impossible,
  report only the concrete blocker; do not invent a replacement method.
- Reproduction and extension claims MUST remain separate. A procedure may be
  described as Sun-compatible or paper-faithful only when the Sun paper itself
  supports it at a cited exact location. A method borrowed from other prior work
  is an extension, must be labelled as such, and requires explicit user approval
  before implementation or use in an experiment.
- Method changes discovered or suggested after seeing results are forbidden
  unless the user explicitly requests them and the required primary-literature
  citation and exact location are recorded before implementation. Never turn an
  optional extension into a prerequisite for reporting the requested results.

## Mandatory Check and Experiment Log

The legacy `audit_*` filenames refer to automated offline integrity checks and
append-only experiment-provenance logs. They are not institutional or
third-party audits. Keep the safeguards, but do not run the full suite during
read-only analysis or after every tiny edit.

From the workspace root or this directory, run before editing:

```powershell
python formal_experiment/scripts/audit_project.py
```

or, from this directory:

```powershell
python scripts/audit_project.py
```

Run once after each coherent material-change batch:

```powershell
python scripts/audit_project.py --with-tests
```

Then record the verified change or experiment run with
`scripts/record_change.py`; it reuses the matching exact-state test receipt, so
the full suite is not run twice. It appends the human and machine-readable
experiment-provenance logs at `docs/EXPERIMENT_LOG.md` and
`docs/EXPERIMENT_EVENTS.jsonl`. Human-facing log fields are written in Chinese.
Declare Gold, LLM/API, and artifact handling explicitly. See
`docs/AI_CHANGE_PROTOCOL.md`.

`integrity_pass: true` permits continued controlled development. It does not
permit final claims. Final metrics require:

```powershell
python scripts/audit_project.py --require-final-ready
```

## Boundaries

- Do not import from `../archive` or `../references`.
- Do not import, execute, or use `_retired/` as an active experiment source.
- Do not auto-fill or alter human Gold.
- Do not let `sun_rule_only` call an LLM.
- Do not run a real LLM/API batch without explicit authorization and a recorded
  call budget.
- Do not overwrite predictions, manifests, Gold, or results by default.
- Do not call the reconstruction exact Sun or Sun original.
- Keep all new experiment code, tests, prompts, data contracts, and reports
  inside this directory.
- The user is authorized to begin editing the v2 `estg_150_human_correction_v1.json`
  file NOW as long as `--require-human-review-ready` is green. This is the
  **input** gate (data + schema + tool locked, 150 sample_ids stable, format-valid
  editing surface). The **freeze** gate (150/150 adjudicated) is reported
  separately as `human_review_freeze_ready` and remains false until the user
  finishes adjudicating every record. These two gates are intentionally
  distinct: input-ready does NOT require any record to be reviewed, and
  freeze-ready is a **necessary but NOT sufficient** condition for declaring
  formal Gold. Declaring formal Gold also requires `route.status==locked`
  AND `stage2_dataset.status==locked_for_human_review` AND
  `stage3.status==locked` AND
  `formal_gold_publication_gate.status` exactly matching the contract's
  `allowed_publication_statuses` whitelist (default
  `["ready_for_formal_gold_publication"]`; see `configs/experiment_contract.json`).
  The deprecated `human_review_ready` alias mirrors `human_review_input_ready`
  and must NOT be used to decide whether formal Gold can be published.

## EStG-150 5-layer data model (v2 workflow, 2026-07-12 21:30)

The single EStG-150 dataset is now split into 5 layers. Only Layer E is
editable by the user; Layers A/B/C/D are immutable. See
`docs/HUMAN_GOLD_GUIDE.md` for the full guide and
`data/development/human_review/ESTG150_REVIEW_WORKFLOW_V1.md` for the
data-flow diagram.

| Layer | Path | Role | Editable? |
|---|---|---|---|
| A. German source | `data/development/estg/estg_selected_150_de.jsonl` | 150 legacy record_ids, raw German | NO |
| B. English translation | `data/development/human_review/estg_150_translation_en_v1.jsonl` | LLM-produced English candidate | NO |
| C. LLM six-element candidate | `data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl` | modality/actor/action/condition/constraint/exception from legacy LLM draft | NO |
| D. Chinese aid | `data/development/human_review/estg_150_review_aids_zh_v1.jsonl` (placeholder provenance, all null) — active file is selected by `configs/estg150_layer_d.json` `active_path` (e.g. `estg_150_review_aids_zh_v2.jsonl` once authorized LLM run completes 150/150) | text_zh + back_translation_en; v1 is the all-null placeholder, v2 is the filled version on the SAME 150 sample_ids | NO |
| E. Human correction | `data/development/human_review/estg_150_human_correction_v1.json` | user-editable; `llm_candidate` is immutable copy from layer C | **YES** |

Final Gold is `LLM-assisted, human-adjudicated Gold`. The paper MUST
NOT claim it is "from-scratch human Gold" or "without LLM assistance".

## Final-review state semantics (Layer E)

- `format_valid: true` — schema + per-record structural checks
  (span text matches `approved_text_en[start:end]`, span inside
  clause_span, IDs unique within clause, actor_action_map and
  order_relations reference existing IDs, modality is one of 4
  classes, raw DE hash matches source)
- `review_ready: true` — every record has approved_text_en (or
  translation decision=rejected), review_state ∈ {reviewed,
  adjudicated}, all 7 decisions (translation + 6 fields) ∈
  {accepted, edited, rejected, needs_adjudication}
- `freeze_ready: true` — review_state=adjudicated, all decisions
  ∈ {accepted, edited, rejected}, all per-clause modality
  decisions ∈ {accepted, edited, rejected}

The v1 canonical review file
`data/development/human_review/estg_150_canonical_review_v1.json` is
**retired as workflow draft** and kept as provenance only. The old
single-pane tool was replaced by a two-tab v2 tool. The current recommended
review surface is the still simpler `scripts/estg150_simple_review_tool.py`:
internal Sol candidates are prefilled, the user edits only the six elements,
and one explicit “保存并下一条” click performs the existing internal state
transitions. Exact spans remain mandatory but are located and validated in the
background. The two-tab v2 tool remains available only as an advanced fallback.

### Four orthogonal integrity gates (2026-07-13 4-gate split, Event 22; Event 23 harden)

The canonical integrity checker reports four distinct booleans
that are intentionally not collapsed into one. They are stored in
`audit["..."]` and surfaced by `audit_project.py` in this order:

| # | Gate | Current 0/150 | Source of truth | Command |
|---|------|---------------|-----------------|---------|
| 1 | `human_review_input_ready` | **true** | `experiment_contract.human_review_gate.status` + membership + structural preconditions | `--require-human-review-ready` |
| 2 | `human_review_freeze_ready` | false | v2 human_correction per-record adjudicated count | `validate_human_correction.py` `freeze_ready` |
| 3 | `formal_gold_publication_ready` | false | gate 2 + `route.status==locked` + `stage2_dataset.status==locked_for_human_review` + `stage3.status==locked` + `formal_gold_publication_gate.status` exact match against `allowed_publication_statuses` whitelist | conservative — any missing or non-locked field, OR non-whitelisted status, keeps it false |
| 4 | `final_experiment_ready` | false | gate 3 + method readiness + frozen input/gold | `--require-final-ready` |

Gate 1 is true at 0/150 once the data sources, schemas, tool, v2
file, authoritative contract gate status, and membership
cross-check are all in place. The user can begin editing
`data/development/human_review/estg_150_human_correction_v1.json`
NOW. **Gate 2 is true only after 150/150 adjudicated; it is a
necessary but NOT sufficient condition for gate 3.** Even if gate 2
becomes true, gate 3 still requires route / data / stage3 /
freeze_policy to each be individually re-locked AND the
formal_gold_publication_gate.status to be an exact match against
the contract's `allowed_publication_statuses` whitelist
(default `["ready_for_formal_gold_publication"]`; the previous
"not blocked and not unknown" fail-open heuristic was removed in
Event 23). Gate 4 adds method readiness and frozen input/gold.
The deprecated alias `audit["human_review_ready"]` mirrors gate 1
(semantic: "user can start the human review NOW"), NOT gate 3.

Event 23 also makes the v2 strict validator the **single source of
truth** for `format_valid` / `review_ready` / `freeze_ready` in
both `status.py` and `audit.py`. Any status / check divergence on
the same v2 file is now a single-source-of-truth violation.

Route v2 is reopened after discovery of final-version method differences and
the official Sun dataset supplement. The existing 150-row review pack is
development-only. The 150-record EStG-150 v2 human_correction file is the
active editing surface and is NOT a development pack: gate 1 above is
true, and the user may begin editing it. Re-locking route v2 affects
gate 3 / gate 4, NOT gate 1.

### EStG-150 membership is permanently locked (2026-07-13)

The 150 sample_ids in the active editing file
`data/development/human_review/estg_150_human_correction_v1.json`
are the **same** 150 record_ids as in
`data/development/estg/estg_selected_150_de.jsonl`, with membership
payload sha256=`8573e105d2bc167c6aa0a92c16f79a3aaf725baadfea86f0b5d2b1ea68b1e0d7`
locked in `data/development/estg/estg_150_membership_hashes.json`.
This 150 is:

- **NOT** Sun's original 150 sentence phrase Gold (443 spans).
- **NOT** an exact reproduction of any external dataset.
- The project's `independently_reconstructed_estg_150_v1`
  benchmark, to be published as `LLM-assisted, human-adjudicated
  Gold` after the user finishes 150/150.

Once the user begins editing Layer E, this 150 cannot be
re-sampled, re-seeded, swapped with the legacy development pack,
or replaced with a parallel "new 150" derived from the official
Sun supplement. The official Sun Archive.org supplement
(`Decision_Logic_data.zip`, `input 2.zip`) is reserved for
**method, modality data, and baseline alignment** use only; it
MUST NOT be used to overwrite any of the 150 active sample_ids.
Re-sampling, creating a parallel old/new 150, or migrating any
user-entered human_correction result between two different 150s
is FORBIDDEN. The legacy review pack
(`estg150_review_pack_v1.jsonl` /
`estg_150_canonical_review_v1.json`) and the OCR-derived
`estg_selected_150_en_llm_translated.jsonl` are
**development-only provenance**; they are NOT alternative 150s.
The four orthogonal gates above are unchanged by this rule.



```powershell
python scripts/audit_project.py --require-human-review-ready   # checks gate 1
python scripts/audit_project.py --require-final-ready         # checks gate 4
```

Only a human may change review states to `approved`, `reviewed`, or
`adjudicated`. In the simple tool, the user's “保存并下一条” click is the one
explicit final decision for that displayed record; the service may complete the
two legacy internal state transitions during that single click. Agents may
validate, explain, and import explicitly supplied human decisions, but may not
infer them or write an unconfirmed Sol candidate into Layer E.

The three final methods must share frozen input IDs, locked human Gold, output
schema, normalization, evaluator, and Stage 3 configuration:

- `sun_rule_only` (legacy ID for the complete non-LLM Sun Stage 2 baseline,
  not the current heuristic runner)
- `sun_llm_fallback`
- `direct_llm`
