# Phase 1 — Frozen Fair-Comparison Configuration

**Experiment ID**: `paper_validation_r1_20260728`
**Frozen at (UTC)**: see `frozen_batches.json` / `prompt_hashes.json` `created_at_utc` field
**Phase 0 gate**: PASS (see `00_AUDIT.md`)
**Branch**: `experiment/paper-validation-r1` (created at start of Phase 1; pushed after Commit 1; HEAD at start of Phase 1 = `ceac334`)

---

## 1. Frozen sample order and batches

- Stable order: lexicographic sort on `sample_id` (e.g. `estg_000002` < `estg_000003` < `estg_000376`). The list is sourced from `estg_150_human_correction_v1.json` and is the same across all three methods.
- 5 batches × 30 records = 150 total.
- Each `record_id` appears in exactly one batch.
- The batch file is the **single source of truth** for batch composition. No script may randomly reshuffle or re-batch.

| File                                                                            | SHA-256                                                            |
|---------------------------------------------------------------------------------|--------------------------------------------------------------------|
| `formal_experiment/outputs/paper_validation_r1_20260728/frozen_batches.json`   | `f38e135b5eeb904f17b0f8505f292596b288455e4c81121d9239eeda021cc03c` |

The first 3 record_ids of batch 1: `estg_000002`, `estg_000003`, `estg_000004` (these are the **smoke** record_ids; see §6).

## 2. Frozen model and request parameters

| Parameter        | Value                                                                  | Source of truth                                                                 |
|------------------|------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| Model            | `deepseek-v4-pro`                                                     | read from the prior successful run's summary field `model` in `paper_d1_pilot/d1_full150/d1_predicted_150.json` |
| temperature      | `0`                                                                    | same as the existing pilot scripts (`run_d1_paper_pilot.py`, `run_h1_selective_pilot.py`) |
| response_format  | `json_object`                                                          | same as the existing pilot scripts                                              |
| max_tokens       | `4000`                                                                 | same as the existing pilot scripts                                              |
| max_retry        | `3` per batch                                                          | task §5.5                                                                       |
| seed             | not set; the API does not return a seed field. We **do not fabricate** a seed. The `repeat_id` is a run identifier, not a random seed. | recorded in `environment.json`                                                  |
| API host         | `ws-jbghs9fos5ct05j4.cn-beijing.maas.aliyuncs.com`                     | read from `.env` BASE_URL (host only, no key)                                  |

No other request parameters are added by this run.

## 3. Three methods (M1, M2, M3) — Prompt freeze

The three Prompt files are **byte-level extractions** of the existing
`SYSTEM` and `USER_TEMPLATE` Python string constants in the existing
pilot scripts. The language is unchanged. Runtime placeholders
(`{source_text}`, `{b0_predictions}`) are kept as placeholders.

| Method                          | Prompt file (relative to repo root)                                              | SHA-256                                                            |
|---------------------------------|---------------------------------------------------------------------------------|--------------------------------------------------------------------|
| M1: D1-unprimed                 | `formal_experiment/outputs/paper_validation_r1_20260728/prompts/d1_prompt.txt` | (see `prompt_hashes.json`)                                          |
| M2: H1-selective-primed         | `formal_experiment/outputs/paper_validation_r1_20260728/prompts/h1_selective_primed_prompt_template.txt` | (see `prompt_hashes.json`)                              |
| M3: H1-selective-empty (control) | `formal_experiment/outputs/paper_validation_r1_20260728/prompts/h1_selective_empty_prompt_template.txt` | (see `prompt_hashes.json`)                              |

### 3.1 M2 vs M3 difference

`diff -u primed empty` shows **exactly one** line differs:

```diff
 B0 predictions:
-{b0_predictions}
+{b0_predictions_block}
```

At runtime, the wrapper substitutes the placeholder:

- M2 (primed): `{b0_predictions_block}` → B0 v10a candidate list, formatted as
  `'\n'.join(f'- "{c["clause_text"][:200]}" -> {c["modality"]}' for c in b0_clauses)`,
  identical to the existing `run_h1_selective_pilot.py` formatting.
- M3 (empty): `{b0_predictions_block}` → the literal string
  `"(B0 made no predictions for this source)"`,
  identical to the existing `run_h1_selective_pilot.py` empty-handling
  branch.

The system prompt, the user-prompt header, the schema description,
the example block, and the output-format line are **byte-identical**
between M2 and M3. Only the value of the B0 placeholder differs.
This satisfies the task §4.3 invariant.

## 4. Primary evaluator

| Item                | Value                                                |
|---------------------|------------------------------------------------------|
| Function            | `text_iou`, `best_effort_align`, `evaluate_modality` (cloned into our wrapper to keep audit reproducible; logic identical to the existing pilot scripts) |
| Token-IoU threshold | 0.3                                                  |
| Modality match      | strict equality (`==`); mismatch = FP+FN             |
| Multi-pred to one Gold | **forbidden**; one-to-one greedy by descending IoU    |
| Tie-break           | sort by (descending IoU, ascending pred_idx, ascending gold_idx) — deterministic |
| Aggregation         | **micro** TP/FP/FN, then Precision/Recall/F1; F2 is auxiliary; macro F1 reported per-modality for transparency |
| Modality set        | `{permission, obligation, prohibition, definition}`  |

The evaluator code is exactly the same function body as
`run_d1_paper_pilot.py` (line 162-226) and
`run_h1_selective_pilot.py` (line 247-307). The threshold 0.3 is the
only knob exposed; no test-time tuning.

## 5. Secondary evaluator

The project's `stage2_evaluation_v3.py` (`clause_iou_pairs` using
`v2._char_iou` with `clause_minimum_iou=0.5`) is **not** directly
applicable to the paper pilot output format (see Phase 0 §2.4). The
manifest records `secondary_evaluator = "unavailable"`. No new
evaluator is designed in this run.

## 6. Smoke test record_ids

From the frozen batch 1, the **first 3 record_ids** are used for smoke:
`estg_000002`, `estg_000003`, `estg_000004`. Smoke calls one LLM request
per method × 1 batch of these 3 records. Smoke output goes to
`formal_experiment/outputs/paper_validation_r1_20260728/smoke/` and
**never** enters the main statistics.

## 7. Run order (time-order de-bias)

```
repeat_01:  d1_unprimed → h1_selective_primed → h1_selective_empty
repeat_02:  h1_selective_empty → d1_unprimed → h1_selective_primed
repeat_03:  h1_selective_primed → h1_selective_empty → d1_unprimed
```

Each method × repeat uses the **same** frozen batches (no re-shuffle).
This Latin-square ordering is the only systematic-bias mitigation we
can apply at n=3.

## 8. Budget guard

| State                                          | Action                                                    |
|------------------------------------------------|-----------------------------------------------------------|
| Pre-flight cost estimate > US$8.00              | stop, do not call                                         |
| Cumulative actual cost ≥ US$7.20                | stop launching new full repeats; keep completed ones      |
| Per-batch retry cap                             | 3 attempts (network/429/5xx/truncation/JSON-parse only)   |
| A repeat cannot reach 150 unique predictions    | mark the repeat `invalid`; do not include in mean         |
| Manual patching of predictions is forbidden     | enforced by file-write discipline and the read-only Gold  |

## 9. Output directory layout (per task §5.2)

```
formal_experiment/outputs/paper_validation_r1_20260728/
  runs/
    d1_unprimed/         repeat_01/, repeat_02/, repeat_03/
    h1_selective_primed/ repeat_01/, repeat_02/, repeat_03/
    h1_selective_empty/  repeat_01/, repeat_02/, repeat_03/
  statistics/
  anchoring/
  threshold_analysis/
  subsets/
  prompts/
  test_logs/
  smoke/
  frozen_batches.json
  frozen_batches.sha256
  preflight_cost_estimate.json
  manifest.json
  file_hashes.json
  environment.json
  pip_freeze.txt
  git_status_at_audit.txt
  PAPER_VALIDATION_SYNTHESIS.json
  PAPER_VALIDATION_SYNTHESIS.md
```

> **Important**: `formal_experiment/outputs/paper_validation_r1_20260728/`
> is **.gitignore'd** by the project's existing rule
> (`formal_experiment/outputs/*` is ignored; only `outputs/reports/` is
> committed). This is consistent with how the existing
> `paper_d1_pilot/`, `paper_h1_selective_pilot/`, `paper_synthesis/` are
> handled. All large raw outputs and aggregated statistics therefore
> live in the local working tree only. The commit hash and a per-file
> SHA-256 are recorded in `manifest.json` and `file_hashes.json` for
> reproducibility. The audit document and the
> `01_FROZEN_CONFIG.md` you are reading **are** tracked in Git, so
> provenance is preserved.
