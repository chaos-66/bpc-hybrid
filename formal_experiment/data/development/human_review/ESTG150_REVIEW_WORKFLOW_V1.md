# EStG-150 Review Workflow v1 (LLM-assisted, human-adjudicated)

**Effective**: 2026-07-12. **Scope**: replaces the
`estg_150_canonical_review_v1.json` schema as the active editing surface
for EStG-150 v1. The old file is preserved as a retired workflow draft
and remains a valid read-only provenance artifact.

## 5 layers

| Layer | File | Role | Editable? |
|---|---|---|---|
| A. German source | `data/development/estg/estg_selected_150_de.jsonl` | original EStG clause text | **immutable** (no tool writes here) |
| B. English translation | `data/development/human_review/estg_150_translation_en_v1.jsonl` | LLM-produced English candidate + provenance | **immutable** (review tool cannot overwrite `candidate_text_en`) |
| C. LLM six-element candidate | `data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl` | per-clause modality/actor/action/condition/constraint/exception from legacy LLM draft | **immutable** |
| D. Chinese review aid | `data/development/human_review/estg_150_review_aids_zh_v1.jsonl` | Chinese gloss + English back-translation | **immutable, fields null until authorized LLM call** |
| E. Human correction | `data/development/human_review/estg_150_human_correction_v1.json` | LLM candidate is copied here as `llm_candidate` (immutable); the user edits `human_correction`, `decisions`, and `review_state` | **only editable file** |

## How "copy" works

`llm_candidate` in layer E is a verbatim copy of layer C for that
sample. The user does **not** edit it.

`human_correction.clauses[]` is a duplicate of the LLM clause list
with the same `clause_id` and `clause_span`, but **every** field starts
as `decision=unreviewed` and `value=null`. The user explicitly
moves each field to `accepted` / `edited` / `rejected` /
`needs_adjudication`. A copy on disk is **not** an approval.

## What this workflow does NOT do

- Does not call a real LLM/API in this build.
- Does not fabricate Chinese translations.
- Does not write to the old `estg_150_canonical_review_v1.json`.
- Does not pre-approve any field.
- Does not freeze the formal Gold; final Gold is
  `LLM-assisted, human-adjudicated Gold` and is only declared after
  the user finishes layer E and the validator confirms freeze_ready.

## Tooling

- Review tool: `python formal_experiment/scripts/estg150_review_tool.py`
  (default: opens layer E)
- Validator: `python formal_experiment/scripts/validate_human_correction.py`
- Action log: `outputs/development/human_review/estg_150_review_actions_v1.jsonl`
- Backups: `outputs/development/human_review/review_backups/`

## Retired files

- `estg_150_canonical_review_v1.json` is the previous workflow draft
  (single editing surface, three-pane UI). It is preserved for
  provenance and remains in the audit's read path. Any new editing
  must go through layer E.
- `estg_gold_150_v1_backup.jsonl` and
  `estg_gold_150_v2_distribution_targeted.jsonl` remain as
  development-only provenance; they are not mixed into layer C.
