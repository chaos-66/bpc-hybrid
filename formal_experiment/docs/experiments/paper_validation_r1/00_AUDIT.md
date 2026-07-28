# Phase 0 Audit — Paper Validation R1 (paper_validation_r1_20260728)

**Audit timestamp (UTC)**: 2026-07-28T21:11:22Z
**Auditor**: Phase-0 read-only audit (no LLM calls performed)
**Project root (canonical)**: `D:\Paper\experiment\bpc-hybrid`
**Git toplevel confirmed**: `D:/Paper/experiment/bpc-hybrid` ✓
**Branch**: `main`
**HEAD commit at audit start**: `ceac334ef6151d84916c3cecec488ce58540d709`
**Git remote**: `https://github.com/chaos-66/bpc-hybrid.git`
**Outputs in this run root (under `formal_experiment/`)**: `formal_experiment/outputs/paper_validation_r1_20260728/`
**Docs in this run**: `formal_experiment/docs/experiments/paper_validation_r1/`
**Scripts in this run**: `formal_experiment/scripts/paper_validation/`
**Tests in this run**: `formal_experiment/tests/paper_validation/`

---

## 0. Scope of this audit

This document records the Phase 0 read-only audit required by the task
`BPC-Hybrid 论文实验严格执行任务：Paper Validation R1` (referred to below as
**the task**). It is a precondition for any later phase that would call paid
LLM APIs. **No paid API call was made during this audit.**

The audit covers:

1. Project root and working tree state.
2. Location, content, and SHA-256 of all inputs that the task requires us to
   identify (dataset, Gold, B0 predictions, D1/H1 scripts, prompts, evaluators).
3. Data integrity checks (record count, clause count, modality distribution,
   duplicate / empty / out-of-span detection, modality enumeration).
4. Environment snapshot (OS, Python, pip, git, model config).
5. Verdict of the Phase 0 gate.

---

## 1. Project root and working tree

### 1.1 Canonical project root

`git rev-parse --show-toplevel` returns `D:/Paper/experiment/bpc-hybrid` — matches
the task's required root `D:\Paper\experiment\bpc-hybrid`.

### 1.2 Working tree state (uncommitted at audit time)

```
$ git status --short | wc -l
313
```

The 313 uncommitted entries (modified tracked files + untracked new files) all
live inside `formal_experiment/` (and one file at repo root,
`STAGE2_CONTRACT_v0.1_DRAFT.md`).

The 313 entries were captured in full and saved as
`formal_experiment/outputs/paper_validation_r1_20260728/git_status_at_audit.txt`.

**Overlap with the directories this experiment will write to**:

| This run's planned write root            | Uncommitted path under that root |
|------------------------------------------|----------------------------------|
| `formal_experiment/outputs/paper_validation_r1_20260728/` (new) | 0 |
| `formal_experiment/docs/experiments/paper_validation_r1/`     (new) | 0 |
| `formal_experiment/scripts/paper_validation/`                  (new) | 0 |
| `formal_experiment/tests/paper_validation/`                    (new) | 0 |

**Verdict on overlap**: 0 entries. All 313 uncommitted items live in paths that
this experiment will NOT modify, create, or delete. The task's stopping rule
("只要存在文件重叠风险，立即停止") is therefore NOT triggered.

The user owns the 313 uncommitted items. **This experiment does not stage,
stash, clean, restore, reset, force-push, or otherwise disturb them.**
This experiment only writes into the four new directories listed above.

The 313 items are predominantly (i) earlier in-flight edits the user is making
in `formal_experiment/src/`, `formal_experiment/scripts/`, `formal_experiment/configs/`,
`formal_experiment/docs/`, `formal_experiment/data/` and
`formal_experiment/outputs/reports/`, and (ii) new untracked files the user
added at the repo root and under `formal_experiment/`. None of those are
in the new directories this experiment creates.

### 1.3 Branch policy for this run

The task specifies branch `experiment/paper-validation-r1`. The current branch
on disk is `main`. The Phase 0 audit does not switch branches; a new
branch will be created only when we move into Phase 1 and start producing
the frozen configuration (no paid API call is involved in branch creation).

If the user already created `experiment/paper-validation-r1` in a prior
session, that branch is available; otherwise Phase 1 will create it from
`ceac334` (the audit-start commit).

---

## 2. Located files (paths, sizes, SHA-256)

All SHA-256 values are stored in full in
`formal_experiment/outputs/paper_validation_r1_20260728/file_hashes.json`.
Summary (16-char prefix) reproduced here for readability:

| Item                                        | Path (relative to repo root)                                                                                              | Size (B) | SHA-256 (prefix) |
|---------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|---------:|------------------|
| EStG-150 input (EN)                         | `formal_experiment/data/development/estg/estg_selected_150_en_llm_translated.jsonl`                                       |  128 145 | `f4227871072e9ed6` |
| Gold (231 adjudicated clauses)              | `formal_experiment/data/development/human_review/estg_150_human_correction_v1.json`                                        | 1 301 626 | `7fd55f98a7dd6aee` |
| B0 v10a predictions (150 records)           | `formal_experiment/outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json`                                      |  957 397 | `79dc457cdf933cb9` |
| B0 v10a canonical evaluation                | `formal_experiment/outputs/development/s27_estg150_b0_enhanced_v10a/evaluation_all150.json`                                |   11 437 | `fe0c5ec8f7f7dca1` |
| D1 paper-pilot script                       | `formal_experiment/scripts/run_d1_paper_pilot.py`                                                                          |   15 493 | `a56b9095154467a0` |
| H1-selective paper-pilot script             | `formal_experiment/scripts/run_h1_selective_pilot.py`                                                                      |   20 574 | `8c3d80ab24e60edf` |
| D1 150-sample prediction file (prior run)   | `formal_experiment/outputs/paper_d1_pilot/d1_full150/d1_predicted_150.json`                                                |   90 697 | `b428bcf76974993a` |
| H1-selective 150 combined summary (prior)   | `formal_experiment/outputs/paper_h1_selective_pilot/h1s_combined_150_summary.json`                                          |    1 351 | `8ce2da921feb739f` |
| Paper synthesis (4-way aggregate)           | `formal_experiment/outputs/paper_synthesis/paper_full_data_synthesis.json`                                                 |   75 142 | `1ac4b76782051948` |
| Project stage2 evaluation v3                | `formal_experiment/src/bpc_hybrid/stage2_evaluation_v3.py`                                                                 |   32 347 | `d7df11f86908b684` |
| Project stage2 evaluation v2                | `formal_experiment/src/bpc_hybrid/stage2_evaluation.py`                                                                    |   ~     | `86be001f6eb956fb` |
| Project synthetic-only evaluator            | `formal_experiment/src/bpc_hybrid/evaluator.py`                                                                           |   ~     | `7f0e66b5dd660c9d` |
| Difficulty / independence audit             | `formal_experiment/outputs/development/estg150_independence_audit_v1/estg_150_independence_audit_v1.jsonl`                 |  267 978 | `d32a60727e0470c9` |

The D1 Prompt text is **inline** in `run_d1_paper_pilot.py` (constants
`SYSTEM` and `USER_TEMPLATE`). The H1-selective Prompt text is **inline** in
`run_h1_selective_pilot.py` (constants `SYSTEM` and `USER_TEMPLATE`). The
construct location is therefore the script file, not a separate template
file. **This is a known deviation from the task description**: the task
expected a separate "Prompt construction location" file. There is none.
The audit records this honestly rather than fabricate one.

### 2.1 D1 Prompt (verbatim, as read from `run_d1_paper_pilot.py`)

**System**:

> You are a legal text annotator. Extract deontic clauses from
> EStG (German tax law) excerpts that are provided in English.
> Return only valid JSON.

**User template** (one shot example, one `Source:`/`Output:` pair):

> Extract deontic clauses from the following English legal text.
>
> For each clause, return:
> - clause_text: the verbatim text of the clause (must be a contiguous substring of the source)
> - modality: one of "permission", "obligation", "prohibition", "definition"
> - evidence: the verbatim short cue word/phrase that supports the modality (a contiguous substring of clause_text)
> - actor: the entity performing the action (or null if passive/unspecified)
> - action: the action being performed (verbatim from clause_text, or null)
>
> Return JSON in the form: {"clauses": [...]}
>
> Example: [single example sentence with {clause_text, modality, evidence, actor, action}]
>
> Now extract from:
> Source: {source_text}
>
> Output (JSON only):

### 2.2 H1-selective Prompt (verbatim, as read from `run_h1_selective_pilot.py`)

**System**:

> You are a legal text annotator. You will be given a legal text excerpt
> and a rule-based system's preliminary clause predictions. Your job is to
> review each B0 prediction and either keep / correct / remove it, and to
> add any clauses B0 missed. Return only valid JSON.

**User template** (with 2 examples and a B0 block):

> Review the following rule-based predictions for an EStG (German tax law) excerpt and produce a corrected clause set.
>
> For each B0 prediction, decide ONE of:
> - "keep"     : B0 is correct (right clause_text AND right modality). Include as-is.
> - "correct"  : B0 is wrong in clause_text or modality. Provide the corrected clause_text and corrected_modality.
> - "remove"   : B0 is wrong AND should be discarded entirely.
>
> For the source text, also identify any clauses B0 missed entirely:
> - "add"      : new clause that B0 did not predict at all.
>
> Modality is one of: "permission", "obligation", "prohibition", "definition"
> All clause_text values MUST be a contiguous substring of the source.
>
> Return JSON in this exact form: {"keep": [...], "correct": [...], "remove": [...], "add": [...]}
>
> [two examples follow]
>
> Now process:
> Source: {source_text}
> B0 predictions:
> {b0_predictions}
>
> Output (JSON only):

The B0 block is constructed in `run_h1_selective_pilot.py` as
`"\n".join(f'- "{c["clause_text"][:200]}" -> {c["modality"]}' for c in b0_clauses)`.
This is the **only** template slot that the H1-empty control method
(M3) will set to `[]` (no B0 block) while keeping the rest of the template
byte-for-byte identical.

### 2.3 Token-IoU evaluator used in paper pilots (primary evaluator)

Located inline in `run_d1_paper_pilot.py` and `run_h1_selective_pilot.py`
(both contain identical copies of `text_iou`, `best_effort_align`,
`evaluate_modality`). Threshold is **0.3**. Modality must match exactly
for a TP; mismatch is FP+FN. Match is one-to-one (greedy by descending IoU).

This is the same evaluator that produced the 4-way aggregate in
`paper_full_data_synthesis.json`:

| Method       |      P |      R |     F1 |  TP |  FP | FN |
|--------------|-------:|-------:|-------:|----:|----:|---:|
| B0 v10a      | 0.6406 | 0.7100 | 0.6735 | 164 |  92 | 67 |
| D1           | 0.8936 | 0.7273 | 0.8019 | 168 |  20 | 63 |
| H1-naive     | 0.6327 | 0.7532 | 0.6877 | 174 | 101 | 57 |
| H1-selective | 0.7806 | 0.8114 | 0.7957 | 185 |  52 | 43 |

These are the numbers the task's reference table reproduces.

### 2.4 Char-span v3 evaluator (auxiliary)

Located at `formal_experiment/src/bpc_hybrid/stage2_evaluation_v3.py`.
It defines `clause_iou_pairs(gold, predicted, minimum_iou=0.5)` using
`v2._char_iou` on the `clause_span` text of each clause. Its
`clause_minimum_iou` default is 0.5 (the v3 contract hardcodes 0.5).

**Why v3 cannot serve as the secondary evaluator in this run (data
mismatch, not missing code)**:

- D1 paper-pilot output (`d1_predicted_150.json` → `.predicted[sample_id][]`)
  stores only `{clause_text, modality, evidence, actor, action}`. It does
  NOT carry `clause_span = {text, start, end}`.
- H1-selective paper-pilot output (`h1s_combined_150_summary.json`) only
  stores aggregate metrics; per-clause output is not retained.
- The new runs in this experiment will store clauses in the same format
  as the prior pilots (text-only) because the prompts demand a
  text-only schema, and the task forbids changing the prompts.

So v3 is **not directly applicable** to the modality output format
produced by the paper pilots. The audit records this as
`secondary_evaluator = "unavailable"` in `manifest.json`, with the
reason above. The primary evaluator (token-IoU 0.3) remains the
single comparison basis for this run, as required by §4.4 of the task.

The B0 v10a output DOES carry `clause_span`, so v3 could in principle
be applied to it. But B0 is a rule-based system, not one of the LLM
methods being compared. v3 is therefore not useful as a cross-method
check here.

---

## 3. Data integrity checks

### 3.1 Record counts

| Check                                                    | Expected | Observed | Pass |
|----------------------------------------------------------|---------:|---------:|:----:|
| Records in Gold                                          |      150 |      150 |  ✓   |
| Records in B0 v10a attempts                              |      150 |      150 |  ✓   |
| Records in D1 150 predicted (sample_id keys)             |      150 |      150 |  ✓   |
| Unique `sample_id` in Gold                               |      150 |      150 |  ✓   |
| All `sample_id` strings well-formed (`estg_NNNNNN`)      |       -- |      150 |  ✓   |

### 3.2 Gold clause count and modality distribution

Loaded from
`formal_experiment/data/development/human_review/estg_150_human_correction_v1.json`
under the path `records[].human_correction.clauses[]`, filtered by
`modality.decision in {"accepted", "edited"}` (this is the same filter the
existing D1/H1 pilot scripts use; it is **not** a change introduced by this
run).

| Modality    | Count |
|-------------|------:|
| permission  |    62 |
| obligation  |    97 |
| definition  |    39 |
| prohibition |    33 |
| **Total**   |   231 |

**Text in the existing paper report claims "obligation = 109". The
recomputed value is 97.** The audit records this as a textual error in
the prior report. The Gold source data has not been modified.

Sum check: 62 + 97 + 39 + 33 = 231 ✓.

### 3.3 B0 v10a clause and modality distribution (read-only)

`b0_attempts.json` contains 150 records, each with `record.clauses[]`.
Total predicted clauses: 256.

| Modality    | B0 v10a count | Gold count |
|-------------|--------------:|-----------:|
| permission  |            62 |         62 |
| obligation  |           119 |         97 |
| definition  |            54 |         39 |
| prohibition |            21 |         33 |
| **Total**   |       **256** |    **231** |

B0 v10a is rule-based, not LLM. It over-predicts obligation
(119 vs 97) and definition (54 vs 39), and under-predicts prohibition
(21 vs 33).

### 3.4 D1 150 predicted — record coverage and modality enumeration

Loaded from `d1_predicted_150.json` → `.predicted[sample_id]`.

| Check                                                                              | Result |
|------------------------------------------------------------------------------------|--------|
| sample_id keys present                                                              | 150    |
| Any sample_id missing from a 150-id set                                             | 0      |
| Any sample_id duplicated                                                           | 0      |
| Any record with empty `.predicted[sample_id]` array                                | logged per record |
| Any predicted clause with modality not in the 4-class set                          | 0      |
| Any predicted clause with empty `clause_text`                                      | 0 in this file (run-level re-check in Phase 4) |

Modality distribution in D1 150 will be re-counted in Phase 4 from
the per-run output of `run_repeated_llm_experiment.py`, not from the
prior run's file. The prior file is included here only as a
**reference** for fair-comparison sanity.

### 3.5 String encoding and out-of-span / duplicate / null checks

Audited across the Gold (`estg_150_human_correction_v1.json`):

- All `sample_id` strings are ASCII `estg_NNNNNN` (no Unicode issues).
- All `approved_text_en` strings decode cleanly as UTF-8 (Python read
  with `encoding='utf-8'`; PowerShell `Get-Content -Encoding UTF8`).
- No `clause_span` has `start < 0` or `end > len(approved_text_en)`.
- No clause has a null `clause_id`.
- No `clause_id` collides within a record.
- Across the file, the tuple `(sample_id, clause_id)` is unique.

Audited across `b0_attempts.json`:

- All `sample_id` strings match the same set of 150 ids in Gold.
- All `record.clauses[].clause_id` strings are well-formed
  `estg_NNNNNN.cK`.
- `clause_span.start` and `clause_span.end` are non-negative integers
  and `end > start` for every clause.
- `clause_span.text` for every clause is a (case-sensitive) substring of
  `record.source_text`.

Modality label values across all 150 B0 records: only
`{permission, obligation, definition, prohibition}` appear (no illegal
label, no empty string, no `null`).

### 3.6 Difficulty / independence subset mapping

File: `formal_experiment/outputs/development/estg150_independence_audit_v1/estg_150_independence_audit_v1.jsonl`.

The audit file's own `analysis_boundary` field is
`"analysis_aid_not_human_gold"` for every record (all 150). This means
**the audit is explicitly NOT a human-adjudicated Gold**; it is an
analysis aid that the project uses to drive a "difficulty" subset split.

Field `classification` (counted across the 150 records):

| Classification (Chinese)        | English gloss       | Count |
|---------------------------------|---------------------|------:|
| 独立                             | independent         |    82 |
| 需上下文核实                     | needs context       |    26 |
| 不独立                           | not independent     |    42 |
| **Total**                       |                     |   150 |

Counts match the task's reference (82 / 26 / 42). The mapping is
**not Gold-adjudicated**; it is recorded for the difficulty subset
analysis in Phase 8. The audit will mark every subset result with the
caveat that the split is `analysis_aid_not_human_gold`.

Per-record subset coverage: each `sample_id` appears exactly once.
Sum check: 82 + 26 + 42 = 150 ✓.

### 3.7 Six-field Gold and final-violation Gold (Phase 9/10 audit preview)

Gold `human_correction.clauses[].*` field presence (across all 231
adjudicated clauses):

| Field        | Non-empty count | Coverage |
|--------------|----------------:|---------:|
| `modality`   |             231 |   100.0% |
| `actions`    |             230 |    99.6% |
| `conditions` |             162 |    70.1% |
| `constraints`|             186 |    80.5% |
| `actors`     |              46 |    19.9% |
| `exceptions` |              11 |     4.8% |

`modality` is fully covered; `action` is nearly fully covered;
`conditions`/`constraints` are majority-covered; **`actors` is
covered only on ~20% of clauses** and **`exceptions` on ~5%**.

There is no separate Stage 1 / Stage 3 / final-violation Gold file
under the standard paths the task checks. The Gold only carries the
modality-aware clause spans and the six-element candidate annotations;
**there is no adjudicated final-violation Gold** (e.g. no file of
`missing_action` / `incorrect_actor` / `out_of_order` examples).

This means:

- A fair six-field evaluation of `actor` is **not possible** on
  clauses where Gold `actors` is empty (≈80% of clauses).
- A fair six-field evaluation of `exceptions` is **not possible** on
  clauses where Gold `exceptions` is empty (≈95% of clauses).
- A final-violation evaluation (Stage 3) cannot be performed because
  the Stage-3 Gold is not present in the project.

These findings are recorded now (Phase 0) so Phase 9 / Phase 10 do not
need to re-discover them; Phase 9 / Phase 10 will produce the
`09_SIX_FIELD_BLOCKER.md` and `10_DOWNSTREAM_BLOCKER.md` files as the
task requires.

---

## 4. Environment snapshot

Saved to
`formal_experiment/outputs/paper_validation_r1_20260728/environment.json`
(verbatim). Highlights:

| Field                  | Value |
|------------------------|-------|
| OS                     | Windows (win32) |
| Python                 | 3.14.6 |
| Virtual env            | not activated for the running shell |
| Git branch             | `main` |
| Git commit (start)     | `ceac334ef6151d84916c3cecec488ce58540d709` |
| Git uncommitted items  | 313 (full list in `git_status_at_audit.txt`) |
| pip freeze             | 111 packages (full list in `pip_freeze.txt`) |
| API host               | `ws-jbghs9fos5ct05j4.cn-beijing.maas.aliyuncs.com` (Alibaba Cloud MaaS DeepSeek relay; host only — no header / no key) |
| Model config string    | `deepseek-v4-pro` (taken from the prior D1 150-sample run; this is the only model string that the task allows, since the rule is to copy the model string from existing successful runs) |
| Temperature            | 0 |
| Response format        | `json_object` |
| Max tokens (per call)  | 4000 |
| Max retry per batch    | 3 |
| Seed support           | unknown at audit time; will not be faked. If the API does not return a seed field in usage, the run will record `seed = null` rather than invent one. |
| Timezone (audit)       | local (China Standard Time); UTC stamp is also written |

The .env file is **not** read by this audit. Only env var **names** were
listed (via grep on the `=` sign of non-comment lines), and only the
**host portion of BASE_URL** is recorded. No API key, no token, no
Authorization header is written to disk, in any output of this run.

---

## 5. Phase 0 gate verdict

| Gate condition                                                                                  | Status |
|-------------------------------------------------------------------------------------------------|--------|
| Project root confirmed = `D:\Paper\experiment\bpc-hybrid`                                       | ✓      |
| Working tree has 0 file-overlap with this run's planned write roots                             | ✓      |
| Dataset record count = 150 (no duplicates)                                                      | ✓      |
| Gold clause count = 231 (sum of 4 modalities)                                                  | ✓      |
| All 4 modality counts reproducible from Gold source data                                       | ✓      |
| Modality count text conflict ("109 obligation") resolved: actual = 97 (text in report is wrong) | resolved (no Gold edit) |
| B0 v10a prediction file exists, 150 records, modality labels in 4-class set                     | ✓      |
| D1 and H1-selective source scripts exist, prompts and token-IoU evaluator are inline           | ✓      |
| Primary evaluator (token-IoU 0.3) is reproducible from the existing scripts                     | ✓      |
| Secondary evaluator (char-span v3) exists in code but cannot consume the pilot output format   | recorded; not a blocker |
| No "fairness-breaking" issue discovered in the audit (B0 frozen; scripts untouched; same model string, same temperature, same response_format) | ✓ |
| No accidental change made to `formal_experiment/` files outside the four new directories       | ✓ (verified with diff against HEAD) |

**Phase 0 gate**: **PASS**. Phase 1 (frozen fair-comparison configuration)
may begin. **No paid API call has been made.** No real LLM call is
authorized until Phase 3 (smoke test) is reached and the smoke test
passes.

### 5.1 Deviations from the task spec that the audit found

These are NOT blockers; they are facts the audit discovered while
reading the code and data:

1. **Prompts are inline, not in separate files.** The D1 system/user
   prompts live as Python string constants in
   `formal_experiment/scripts/run_d1_paper_pilot.py`; the H1-selective
   prompts are in `run_h1_selective_pilot.py`. Phase 1 will write the
   prompts out to separate files
   (`outputs/paper_validation_r1_20260728/prompts/*.txt`) as the task
   requires, but the prompts themselves will be byte-identical to the
   inline versions, with the record_id list and B0 candidates block
   replaced by placeholder tokens.
2. **The secondary (char-span v3) evaluator cannot be wired to the LLM
   output format.** The v3 evaluator requires `clause_span` with
   `start`/`end` integers, which the D1/H1 paper pilots do not produce.
   This is recorded as `secondary_evaluator = "unavailable"` rather
   than fabricated.
3. **No adjudicated final-violation Gold exists in the project.**
   The `d1_predicted_150.json` and H1 outputs are LLM output, not Gold.
   No alternative adjudicated Gold is present. Phase 10 will produce
   `10_DOWNSTREAM_BLOCKER.md`.
4. **Gold's six-field coverage is uneven** (see §3.7). `actor` is
   covered on 20% of clauses, `exception` on 5%. Phase 9 will produce
   `09_SIX_FIELD_BLOCKER.md` accordingly.

### 5.2 Items deliberately NOT done in Phase 0

- No `git checkout`, `git reset`, `git clean`, `git restore`,
  `git push --force`, `git add -f`, `rm -rf`, `Remove-Item -Recurse`
  was used.
- No `.env` value was read into a string and printed.
- No API key, token, or Authorization header was written to any file.
- No D1 / H1 / H1-empty LLM call was made.
- No prompt was modified.
- No B0 prediction was modified.
- No Gold clause was modified.
- No new branch was created yet (will be created at the start of
  Phase 1 if it does not already exist; if it exists, we use it).

---

## 6. File index of this audit

| File                                                                          | Purpose |
|-------------------------------------------------------------------------------|---------|
| `formal_experiment/outputs/paper_validation_r1_20260728/manifest.json`        | Machine-readable Phase-0 manifest (status, paths, SHA, counts). |
| `formal_experiment/outputs/paper_validation_r1_20260728/file_hashes.json`     | Full SHA-256 of every input file identified in §2. |
| `formal_experiment/outputs/paper_validation_r1_20260728/environment.json`     | Environment + model-config snapshot (host only; no secrets). |
| `formal_experiment/outputs/paper_validation_r1_20260728/pip_freeze.txt`       | `pip freeze` at audit time. |
| `formal_experiment/outputs/paper_validation_r1_20260728/git_status_at_audit.txt` | The full 313-line `git status --short` capture. |
| `formal_experiment/docs/experiments/paper_validation_r1/00_AUDIT.md`          | This document. |
