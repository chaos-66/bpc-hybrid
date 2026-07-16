# EStG-150 Data Map (single 150, no re-sampling)

> **Status**: locked 2026-07-12 17:15 (user decision, this session).
> **Audience**: any future Agent, the user, and the auditor.
> **Scope**: this document is the single source of truth for which files belong
> to the EStG-150 reconstruction and how they relate to each other.
>
> **One-line summary**: there is exactly **one** 150-record EStG benchmark in
> this project. The selected 150 legacy `record_id`s from
> `estg_selected_150_de.jsonl` are the membership. All other files are
> different *views* or *derived* artifacts of the **same** 150 records;
> they are not a different dataset.

## 1. The single membership decision

| Decision | Value |
|---|---|
| Number of records | 150 (one and only one set) |
| Membership source | `data/development/estg/estg_selected_150_de.jsonl` |
| Membership key | integer `id` field, the *legacy record_id* (range 0..884 in the 885 pool) |
| Sample ID form (canonical) | `estg_<6-digit zero-padded legacy record_id>` (e.g. `estg_000080`) |
| Source of authority | user, 2026-07-12 (this session) |
| Allowed | local EStG text cleaning and 1-to-1 source mapping against the same 150 |
| Forbidden | re-sampling, replacing, supplementing, or splitting the membership |
| Frozen v1 hash | `membership_payload_sha256 = 8573e105d2bc167c6aa0a92c16f79a3aaf725baadfea86f0b5d2b1ea68b1e0d7` (see §3) |

The 150 IDs are: see `data/development/estg/estg_150_membership_hashes.json`
(`selected_membership.sorted_legacy_record_ids`).

## 2. The seven legacy files and their relationship to the 150

All seven files were inspected in this session. Counts, key shape, and
membership relationship are reported in the table below.

| # | File | Records | ID key | Text language | Role |
|---|---|---|---|---|---|
| 1 | `estg/estg_sentences_de.jsonl` | 885 | `id` (int 0..884) | German | **candidate corpus** (885-sentence pool) |
| 2 | `estg/estg_selected_150_de.jsonl` | 150 | `id` (int, subset of 0..884) | German | **selected membership** (the single 150) |
| 3 | `estg/estg_selected_150_en_llm_translated.jsonl` | 150 | `id` (int, **same set as #2**) | `text_de` + `text_en` | **candidate translation** (LLM-translated candidate EN) |
| 4 | `estg/estg_gold_150_llm_draft.jsonl` | 150 | `sample_id` = `estg_<3-digit>` (order = sorted #2 IDs) | English `source_text` | **old automatic annotation v-draft** (development provenance) |
| 5 | `estg/estg_gold_150_v1_backup.jsonl` | 150 | `sample_id` = `estg_<3-digit>` (order = sorted #2 IDs) | English `source_text` | **old automatic annotation v1** (development provenance; byte-identical text to #4) |
| 6 | `estg/estg_gold_150_v2_distribution_targeted.jsonl` | 150 | `sample_id` = `estg_<3-digit>` (order = permutation of #2 IDs, same as #7) | English `source_text` | **old automatic annotation v2** (development provenance) |
| 7 | `human_review/estg150_review_pack_v1.jsonl` | 150 | `sample_id` = `estg_<6-digit zero-padded>` (order = same permutation as #6) | `source.source_text_de_ocr` + `source.candidate_text_en` | **blank human review pack** (development provenance; status all `needs_review`, clauses all empty) |

Two derived convenience files were previously created for user familiarization
and are now isolated as retired provenance:

| # | File | Records | Role |
|---|---|---|---|
| 8 | `_retired/data/human_review_user_audit/estg150_review_pack_user_audit_v1.jsonl` | 151 lines = 1 `_type:meta` + 150 records (mirrors #7) | retired user-familiarization copy; never promote |
| 9 | `_retired/data/human_review_user_audit/estg150_review_pack_user_audit_v1.json` | 151 records (1 meta + 150) | retired JSON mirror; not for editing |

Status meaning of each file:

- *candidate corpus* — 885 raw candidates from which the 150 were chosen once.
  The 150 must remain a subset; re-running the selection is **not** allowed.
- *selected membership* — the authoritative 150 by legacy `id`.
- *candidate translation* — LLM English candidate for each of the 150.
- *old automatic annotations* — three generations of pre-`canonical` schema
  auto-annotation. **Not** the user-approved Gold. Retained for provenance
  only; **must not** be auto-pre-filled into the canonical review file
  (anchoring risk).
- *blank human review pack* — v1 development review scaffold; spans, clauses
  and review states still `needs_review` / empty. **Retired as the editing
  surface**; superseded by the new canonical review file (see §4).
- *user-familiarization copy* — user override copy for understanding the
  legacy pack; the meta line carries `promotion_blocked: true` and the file
  itself is non-formal by design.

## 3. Mapping proof (one-to-one relationships)

All three relationships below were verified in this session by reading the
files, parsing JSON, and comparing `id` / `sample_id` sets.

### 3.1 The 150 are a subset of the 885 candidate pool

```text
pool_ids     = {r.id for r in estg_sentences_de.jsonl}        # 885 ints 0..884
selected_ids = sorted({r.id for r in estg_selected_150_de.jsonl})  # 150 ints
selected_ids ⊆ pool_ids   : True
len(selected_ids)         : 150
```

### 3.2 English 150 == German 150 by `id`

```text
en_ids = sorted({r.id for r in estg_selected_150_en_llm_translated.jsonl})
en_ids == selected_ids : True   # exact same 150 ints
```

### 3.3 The three old Gold files and the review pack are the same 150

All three auto-annotation files and the review pack use 3-digit or 6-digit
zero-padded `estg_` IDs that parse back to the same 150 legacy `id`s.
Within each file, `id` ↔ `legacy_record_id` is a bijection.

```text
v1_sample_ids_int  = sorted([int(r.sample_id.split("_")[1]) for r in gold_v1_backup.jsonl])
v2_sample_ids_int  = sorted([int(r.sample_id.split("_")[1]) for r in gold_v2_distribution_targeted.jsonl])
rp_sample_ids_int  = sorted([int(r.sample_id.split("_")[1]) for r in review_pack_v1.jsonl])

v1_sample_ids_int  == selected_ids : True
v2_sample_ids_int  == selected_ids : True
rp_sample_ids_int  == selected_ids : True
```

File-level English text identity (across v1, v2, the EN file, the review
pack's `candidate_text_en`) was verified for **all 150 records**:

```text
v1.source_text  == en_text_en        : 150/150
review_pack.candidate_text_en == en_text_en : 150/150
```

So the four English-bearing files hold the same English string per legacy
`id`. They differ in ordering and in surrounding schema, not in membership
or in textual content.

## 4. The v2 human-correction file (the only human-editing surface)

The active **single human-editing source** is:

```text
formal_experiment/data/development/human_review/estg_150_human_correction_v1.json
```

The v1 `estg_150_canonical_review_v1.json` is a retired workflow draft kept as
provenance. Properties enforced for the active v2 file include:

- exactly 150 records with the same locked membership and raw German hashes;
- immutable Layer A/B/C provenance plus a user-owned `human_correction` layer;
- `approved_text_en` and all seven decisions begin unreviewed/null;
- six-element candidate values are suggestions, never approvals;
- span offsets, clause containment, IDs, mappings and modality vocabulary are
  checked before review/adjudication states can be saved.

The validator reports three orthogonal gates:

| Gate | Meaning | Required for |
|---|---|---|
| `format_valid` | schema + ID uniqueness + membership identity + hash match | pass before user opens it |
| `review_ready` | all required translation/six-field decisions are resolved enough for review | human review progress |
| `freeze_ready` | all 150 are adjudicated and no decision needs adjudication | necessary, not sufficient, for formal Gold publication |

The active v2 file currently has `format_valid=true`, `review_ready=false` and
`freeze_ready=false` at 0/150 adjudicated. See `HUMAN_GOLD_GUIDE.md` and the
machine audit for the authoritative current semantics.

## 5. Membership hashes (for any future `freeze` step)

Stored in `data/development/estg/estg_150_membership_hashes.json`:

- `membership_payload_sha256` = `8573e105d2bc167c6aa0a92c16f79a3aaf725baadfea86f0b5d2b1ea68b1e0d7`
  (sorted 150 IDs joined by `,`, UTF-8, no whitespace)
- `file_sha256` of `estg_selected_150_de.jsonl` itself
- 150 per-record SHA-256s of the raw German OCR text

No new membership version may be created without an explicit user decision,
new hash record and logged route change. **No silent membership edits.**

## 6. What is explicitly forbidden

- Re-running the candidate selection; producing any second 150.
- Editing the raw German OCR in place; raw text is the permanent read-only
  source of truth for that record.
- Pre-filling the active human-correction decisions with old auto-annotation content
  (LLM draft / v1 / v2) — that would anchor the human reviewer.
- Treating `estg150_review_pack_v1.jsonl` (or its user-audit mirror) as
  the active editing surface; they are provenance only.
- Changing the user-provided review state (`needs_review` →
  `approved` / `reviewed` / `adjudicated`) by an Agent.

## 7. Allowed automatic actions (low-risk only)

- Unicode normalization (NFC) and whitespace collapse on the German text.
- Tagging candidate OCR/word-boundary issues for human review
  (`source_boundary_issue: true`) without changing the text.
- Hashing the raw German for membership verification.
- Source location lookup against the local official EStG text under
  `references/datasets/estg_1988.pdf` and `references/datasets/estg_1988_raw.txt`
  to record an `official_text_match` evidence (read-only; do not import
  text from the reference into the canonical record).

Anything that would change legal meaning, clause boundaries, or sample
membership is **not** allowed to be done automatically; it must be
flagged `needs_adjudication` and left to the human.
