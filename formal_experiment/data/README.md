# Formal Data Area

This directory separates development evidence from future frozen evidence.

```text
data/
  development/    drafts, stale predictions, LLM-generated annotations,
                  and legacy evidence; never use in final result tables
    estg/         independently reconstructed EStG-150 v1 — see below
    human_review/ 5-layer v2 workflow — see below
    complex_legal/ S2.11 official GDPR source + frozen 50-ID membership;
                   semantic Gold remains pending human adjudication
  input/          future frozen regulatory inputs shared by all methods
  gold/           future human-reviewed, span-aware, locked Gold
  predictions/    future canonical predictions from M1/M2/M3
  results/        future canonical metric summaries and details
```

Do not place new exploratory output beside frozen data. Generated diagnostics
belong under `outputs/development/`.

## EStG-150 v1 (the only EStG benchmark in this project)

There is exactly **one** 150-record EStG benchmark. Membership is the 150
legacy `record_id`s of `data/development/estg/estg_selected_150_de.jsonl`.
Re-sampling, replacement, and "old 150 / new 150" parallel routes are
**forbidden**. The full data map, ID-mapping proofs, and per-record SHA-256
live in `docs/ESTG150_DATA_MAP.md` and the generated
`data/development/estg/estg_150_membership_hashes.json`.

### 5-layer v2 workflow (LLM-assisted, human-adjudicated Gold)

The single 150 benchmark is split into 5 layers. Only layer E is
editable by the user; layers A/B/C/D are immutable. Final Gold will be
declared as **LLM-assisted, human-adjudicated Gold**; the paper must
not claim it is "from-scratch human Gold" or "without LLM assistance".

| Layer | Path | Role | Editable? |
|---|---|---|---|
| A. German source | `data/development/estg/estg_selected_150_de.jsonl` | 150 legacy record_ids, raw German | **NO** |
| B. English translation candidate | `data/development/human_review/estg_150_translation_en_v1.jsonl` | LLM-produced English candidate + provenance | **NO** |
| C. LLM six-element candidate | `data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl` | modality/actor/action/condition/constraint/exception from legacy LLM draft | **NO** |
| D. Chinese review aid | `data/development/human_review/estg_150_review_aids_zh_v1.jsonl` | text_zh + back_translation_en, all null until authorized LLM call | **NO** |
| **E. Human correction** | `data/development/human_review/estg_150_human_correction_v1.json` | user-editable; `llm_candidate` is immutable copy from layer C | **YES** |

Build all 5 layers: `python formal_experiment/scripts/build_estg150_review_layers.py`
Review: `python formal_experiment/scripts/estg150_review_tool.py` (default: opens layer E)

## S2.11 complex legal set

`development/complex_legal/gdpr_2016_679_oj_en/` contains the hash-locked
Publications Office Formex source for CELEX `32016R0679`, a deterministic
50-record membership covering GDPR Articles 5–50, and a blank 0/50 human-Gold
template. The input membership and mapping protocol are verified; semantic
Gold and formal complexity profiles are not frozen. The old
`development/gdpr50/` heuristic pack is provenance only and is never imported.
Validate: `python formal_experiment/scripts/validate_human_correction.py`

Initial state should be: `format_valid=true`, `review_ready=false`,
`freeze_ready=false`, `approved_text_en: 0/150`, all decisions
`unreviewed`, all review_state `needs_review`.

**Important**: copying the LLM candidate into the human correction does
**not** approve it. Every field in `human_correction` starts with
`decision=unreviewed` and `value=null`. The user must explicitly move
each field to `accepted` / `edited` / `rejected` / `needs_adjudication`.

### Retired as editing surface, retained as development provenance (do **not** edit, do **not** delete)

- `data/development/human_review/estg150_review_pack_v1.jsonl` (v1 review schema)
- `data/development/human_review/estg_150_canonical_review_v1.json` (v1 single-editing-surface workflow; **retired as workflow draft**, kept for provenance and dev sanity check via `validate_canonical_review.py`)
- `data/development/estg/estg_gold_150_llm_draft.jsonl` (Layer C candidate source)
- `data/development/estg/estg_gold_150_v1_backup.jsonl`
- `data/development/estg/estg_gold_150_v2_distribution_targeted.jsonl`

The replaced user-familiarization copies now live under
`_retired/data/human_review_user_audit/`. They are read-only provenance and are
not an editing surface. The historical R15.0 output pair is similarly isolated
under `_retired/data/legacy_r15_0/`.

The official EStG text under
`references/datasets/estg_1988.pdf` / `references/datasets/estg_1988_raw.txt`
is used **only** for read-only 1-to-1 source location mapping and for
low-risk German text cleaning; it is **not** a translation source and
**not** a re-selection source.

## Frozen directories

The route is **reopened** (Route v2) and the frozen directories
(`data/input/`, `data/gold/`, `data/predictions/`, `data/results/`)
remain empty until the final-version method + official-data route is
re-locked AND the v2 human_correction file passes `freeze_ready=true`
under `scripts/validate_human_correction.py` AND the user explicitly
approves freezing.

Only the canonical schema
(`configs/schemas/stage2_prediction.schema.json@1.0.0`) and the
stage 2 multi-clause / span-aware / 4-class modality contract are
locked; dataset IDs (other than the EStG-150 v1 membership above), the
final-version method, provenance, and the review protocol are not.
Populate `predictions/` and `results/` only through guarded formal
runners; never copy development predictions into them merely to clear
an audit blocker.
