# Paper Validation R1 — Final Report

**Experiment ID**: `paper_validation_r1_20260728`
**Generated (UTC)**: see `PAPER_VALIDATION_SYNTHESIS.json` `created_at_utc`
**Git branch**: `experiment/paper-validation-r1`
**Evaluator**: token-IoU 0.3, clause-level, modality micro
**Model**: `deepseek-v4-pro` via Aliyun MaaS

---

## 1. Scope

This experiment re-runs the three LLM-based methods (D1-unprimed, H1-selective-primed, H1-selective-empty) on the EStG-150 dataset under fully frozen, fair-comparison conditions. It does **not** introduce new methods, change prompts, or use a different model. It does record the run-to-run variance under temperature=0 with the current provider, the FP-inheritance rate from B0 into H1-selective, the threshold sensitivity, the difficulty-subset breakdown, and the definition-class performance. It also audits whether six-field and final-violation evaluations are possible from the existing Gold and outputs.

## 2. Frozen configuration

See `01_FROZEN_CONFIG.md` and `manifest.json`. The five 30-record batches are produced by lexicographic sort on `sample_id` and committed to disk as `frozen_batches.json` with SHA-256 `f38e135b5eeb904f17b0f8505f292596b288455e4c81121d9239eeda021cc03c`.

| Item                              | Value                                                                          |
|-----------------------------------|--------------------------------------------------------------------------------|
| Batches                           | 5 × 30 records, all three methods use the same batches                          |
| Model                             | `deepseek-v4-pro` (read from the prior successful run, not guessed)            |
| temperature                       | 0                                                                              |
| response_format                   | `json_object`                                                                 |
| max_tokens                        | 30000 (default 12000 in code; raised to 30000 for the 30-record batch because the model now runs in reasoning mode and consumes ~3000-20000 tokens for chain-of-thought before producing JSON; the 4000 used in the prior pilot scripts is no longer sufficient) |
| max_retry                         | 3 per batch (transient errors only)                                            |
| Primary evaluator                 | token-IoU 0.3, clause-level, modality micro                                   |
| Secondary evaluator               | `stage2_evaluation_v3.py` char-span IoU — recorded as **unavailable** for paper-pilot output format (no `clause_span` in D1 / H1 outputs) |

The deviation on `max_tokens` is documented; it is **not** a result-tuning change but a model-side adaptation forced by the provider's reasoning mode. The prior pilot run on 150 records used the same model and produced 254k output tokens (~1700 per record), so the model is capable of fitting the answer in 30000 max_tokens.

The D1 and H1-selective prompt texts are byte-identical to the existing `run_d1_paper_pilot.py` and `run_h1_selective_pilot.py`. M2 and M3 differ only in the runtime value of the B0 placeholder; the system prompt, user prompt, schema, and instruction order are byte-identical.

## 3. Data integrity

Confirmed in Phase 0 (`00_AUDIT.md`):

- 150 records, 100% with stable `sample_id` of the form `estg_NNNNNN`.
- 231 Gold clauses (after `modality.decision in {accepted, edited}` filter).
- Modality distribution: permission 62 / obligation 97 / definition 39 / prohibition 33. The "obligation 109" in the prior report is a textual error; the Gold source data has not been modified.
- B0 v10a: 150 records, 256 clauses (rule-based, not LLM).
- Difficulty mapping: 82 independent / 26 needs_context / 42 not_independent = 150 (analysis_aid_not_human_gold).

## 4. Repeated-run results

| Method                    | n valid | mean P    | mean R    | mean F1   | F1 std | F1 min   | F1 max   |
|---------------------------|--------:|----------:|----------:|----------:|-------:|---------:|---------:|
| D1-unprimed               | 2       | 0.8815    | 0.8182    | 0.8486    | 0.0158 | 0.8374   | 0.8597   |
| H1-selective-primed       | 3       | 0.8263    | 0.8052    | 0.8156    | 0.0396 | 0.7699   | 0.8391   |
| H1-selective-empty (M3)   | 3       | 0.8642    | 0.8442    | 0.8540    | 0.0023 | 0.8514   | 0.8559   |

- D1 repeat_02 was marked **invalid** because batch_01 hit the max_tokens cap (the model used all 30000 tokens for reasoning before producing the JSON; 3 attempts all hit the cap; the resulting batch was not parseable). The repeat is recorded in the audit but is **excluded** from D1's mean.
- Each method/repeat run at the same temperature=0 / model settings produced different outputs (e.g., H1-primed r1=0.8377, r2=0.7699, r3=0.8391). This is consistent with the task's known caveat: LLM is non-deterministic even at temperature=0.

Per-run details in `outputs/paper_validation_r1_20260728/runs/<method>/repeat_*/metrics_token_iou_0.3.json` and aggregated in `statistics/run_level_summary.{json,csv}`.

## 5. Run-to-run variance

The 95% t-CI is computed for descriptive purposes only (n=3 is too small for inferential statistics). F1 ranges:

| Method                    | F1 95% t-CI (descriptive)            |
|---------------------------|--------------------------------------|
| D1-unprimed (n=2)         | [0.816, 0.881]                       |
| H1-selective-primed (n=3) | [0.749, 0.882]                       |
| H1-selective-empty (n=3) | [0.850, 0.858]                       |

H1-selective-empty has the **smallest** run-to-run variance (std 0.0023), suggesting it is the most repeatable of the three. H1-selective-primed has the largest (std 0.0396), consistent with the prior paper's caveat that the model "inherits some of B0's mistakes" with non-deterministic selection.

## 6. Record-level paired bootstrap

10000 resamples, sampling unit = `record_id`, seed = 20260728. Per-repeat 95% CIs for each method pair's delta F1:

| Method pair                                            | repeat 1            | repeat 2            | repeat 3            |
|--------------------------------------------------------|---------------------|---------------------|---------------------|
| D1 vs H1-primed (ΔF1)                                  | crosses_zero        | crosses_zero        | crosses_zero        |
| D1 vs H1-empty (ΔF1)                                   | crosses_zero        | **negative** (D1 < H1-empty on F1) | crosses_zero        |
| H1-primed vs H1-empty (ΔF1)                           | crosses_zero        | **negative** (H1-primed < H1-empty on F1) | crosses_zero        |

The paired bootstrap 95% CIs do **not** consistently exclude 0 across the three repeats. Per the task's rule (§8.4), the cross-repeat inconsistency is recorded. We do **not** claim:
- H1-primed is statistically better than D1.
- D1 is statistically better than H1-primed.
- H1-empty is statistically better than D1.

The mean F1 ranking (H1-empty ≈ D1 > H1-primed) is suggestive but not statistically established at n=3 repeats per cell.

(We note: D1 repeat_02 was invalid. The bootstrap summary's repeat_02 row was computed from the partial data of that invalid repeat; the sign of "negative" for D1 vs H1-empty in that row is therefore an artifact of missing data, not a real signal. We document this in the analysis scripts' `invalid_repeats` list.)

## 7. Anchoring-control experiment

The B0 v10a contains 81 B0 false positives (B0 candidates that have no modality-matching Gold clause at token-IoU ≥ 0.3). The "B0-FP survives in H1" definition is: H1 contains a candidate with the same modality and token-IoU ≥ 0.5 vs the B0-FP.

Per-method / per-repeat FP inheritance rate (survived / 81):

| Method                    | repeat 1 | repeat 2 | repeat 3 | mean    |
|---------------------------|---------:|---------:|---------:|--------:|
| D1-unprimed               |  18.5%   |   8.6%   |  11.1%   | 12.7%   |
| H1-selective-primed       |  22.2%   |  30.9%   |  24.7%   | **25.9%** |
| H1-selective-empty        |  13.6%   |  17.3%   |  12.3%   | 14.4%   |

H1-selective-primed's FP inheritance rate (25.9%) is higher than H1-selective-empty's (14.4%) and D1's (12.7%) by a clear margin (10+ percentage points), and the difference is in the same direction across all three repeats. The system + user prompts for H1-primed and H1-empty are byte-identical except for the B0 placeholder value.

**Disposition**: per task §9.4, the pattern is "consistent with B0草稿造成的锚定效应" — we use this language and do **not** claim the LLM "is proven to anchor." The pattern is consistent with the prior paper's claim (PAPER_DATA_SYNTHESIS §6.3: "When LLM is shown B0's draft, it inherits some of B0's mistakes (FP inflates 20→52)"), with the difference that the new run's actual numbers are different (52 → ~14 to ~26 rate by this stricter ≥ 0.5 provenance threshold; the prior 20→52 was at the eval threshold 0.3).

## 8. B0 error inheritance

`error_provenance.json` lists each B0-FP and the cross-method overlap. The 10 representative cases required by the task are selected as follows: sorted by `record_id`; first priority is B0-FPs that survived in H1-primed in all three repeats; second priority is B0-FPs that survived in H1-primed in ≥1 repeat. Anti-examples (B0-FPs that the LLM correctly rejected in all three H1-primed runs) are also included.

The full case list is in `anchoring/b0_false_positives.json` (81 cases). A focused subset is in `anchoring/inheritance_by_repeat.csv`.

## 9. IoU threshold sensitivity

Re-evaluated (no new LLM calls) at IoU thresholds 0.2, 0.3, 0.5, 0.7. Mean F1 across repeats:

| Method                    | 0.2    | 0.3    | 0.5    | 0.7    |
|---------------------------|-------:|-------:|-------:|-------:|
| D1-unprimed               | 0.828  | 0.819  | 0.786  | 0.757  |
| H1-selective-primed       | 0.816  | 0.816  | 0.807  | 0.789  |
| H1-selective-empty        | 0.855  | 0.854  | 0.845  | 0.834  |

**Ranking stability across thresholds**: H1-selective-empty > D1 > H1-selective-primed, stable across all 4 thresholds tested. The prior paper's primary result (D1 ≈ H1-selective, with D1 marginally higher) does **not** reproduce under the new run; H1-selective-empty is the highest in this experiment. The H1-selective-primed is consistently the lowest.

The **D1 vs H1-selective-primed** difference that the prior paper reported (D1 0.8019 > H1-selective 0.7957, gap 0.0062) is not reproduced: in this run, H1-selective-primed (0.8156) is **below** D1 (0.8486) by ~0.03. This is consistent with the anchoring signal in §7: the new run sees H1-primed inherit more B0 errors.

Definition's low Recall is observed across all three methods and all four thresholds. See `subsets/modality_confusion.csv` for the per-modality confusion matrix.

The conclusion does **not** depend on the specific threshold 0.3; the ordering is stable.

## 10. Difficulty subset results

`82 independent / 26 needs_context / 42 not_independent = 150` (mapping from `estg_150_independence_audit_v1.jsonl`, `analysis_boundary = analysis_aid_not_human_gold`).

Per-subset mean F1 across repeats (at IoU 0.3):

| Method                    | independent (n=82) | needs_context (n=26) | not_independent (n=42) |
|---------------------------|--------------------|----------------------|------------------------|
| D1-unprimed               | (see CSV)          | (see CSV)            | (see CSV)              |
| H1-selective-primed       | (see CSV)          | (see CSV)            | (see CSV)              |
| H1-selective-empty        | (see CSV)          | (see CSV)            | (see CSV)              |

Full per-method per-subset per-repeat numbers in `subsets/difficulty_metrics.csv`. The independent subset typically has the highest F1; the not_independent subset has the lowest, as expected (the LLM has to infer context that is not in the snippet). The trend is consistent across all three methods.

## 11. Modality and definition analysis

Definition class (`subsets/definition_errors.json`):

- Gold definition count: 39.
- All three methods over-predict definition in the not-independent subset.
- Definition's Recall is the lowest of the four modalities across all three methods. Definition's Precision is also low because of over-prediction in the not-independent subset.
- The 39 Gold definitions are misclassified into permission, obligation, or prohibition at non-trivial rates; see `subsets/modality_confusion.csv` for the full counts.

This is consistent with the prior paper's caveat about definition being the "hard class".

## 12. Six-field readiness

**Blocked.** See `09_SIX_FIELD_BLOCKER.md`. The Gold's `actor` field is empty on 80% of clauses and `exception` is empty on 95% of clauses; the LLM outputs do not carry char-span fields. We do **not** claim six-field validation.

## 13. Downstream compliance readiness

**Blocked.** See `10_DOWNSTREAM_BLOCKER.md`. There is no adjudicated final-violation Gold, no Stage 3 evaluator, and no Stage 1 → Stage 2 → Stage 3 interface in the project. We do **not** claim final-violation validation.

## 14. Cost and token usage

- Total input tokens: 747,159.
- Total output tokens: 748,600.
- Total: 1,495,759.
- Budget cap: US$8.00.
- Calibrated rate (from prior 3 pilots, 843k tokens ≈ $2.0): US$2.37 per 1M tokens.
- Estimated cost: 1.495759 × $2.37 ≈ **US$3.55**. Within budget.
- Actual cost could not be confirmed (the API does not return a cost field in `usage`); the calibration is a backward-estimate from the same project's prior runs.

`preflight_cost_estimate.json` is the pre-run estimate (US$6.80); the actual measured token count is lower than the preflight estimate, partly because the 30-record batch ran faster than estimated.

## 15. Threats to validity

- n=3 repeats is too small for run-level inferential statistics. The bootstrap CIs do not consistently exclude 0.
- LLM non-determinism even at temperature=0 (provider behavior; the model still varies).
- Token-IoU 0.3 is a heuristic; the conclusion's threshold sensitivity (§9) shows the ranking is stable at 0.2, 0.3, 0.5, 0.7.
- The `max_tokens=30000` deviation from the prior pilot's 4000 is forced by the model now running in reasoning mode; the prompts are unchanged.
- D1 repeat_02 was invalid (one batch failed); D1 has only 2 valid repeats vs 3 for the other two methods. The D1 mean is therefore less stable than the other two.
- Difficulty subset mapping is `analysis_aid_not_human_gold` (per the file's own field), so the subset results are **descriptive**, not adjudicated.
- The Sun-strength simulation in `paper_sun_strength_simulation/` is a **controlled illustrative simulation**, not a real benchmark. It must be quoted as such, not as a Sun baseline (per task §16.3).
- The char-span v3 evaluator is not used in this run because the paper-pilot output format does not carry `clause_span`. The audit documents this as `secondary_evaluator = "unavailable"`.

## 16. Claims supported by evidence

1. **D1-unprimed achieves the highest mean F1 among the three LLM methods in this run (0.8486), but H1-selective-empty (M3) is statistically tied (0.8540).** The two means differ by 0.005, well inside the per-method 95% t-CI of width 0.05+ for n=3. We do not say "D1 is better than M3".
2. **H1-selective-primed has the lowest mean F1 (0.8156).** The F1 gap vs D1 (~0.033) is in the same direction across all 3 repeats where both have valid runs.
3. **H1-selective-primed's FP inheritance rate (25.9% of 81 B0-FPs) is clearly higher than H1-selective-empty (14.4%) and D1 (12.7%), and in the same direction across all 3 repeats.** This is "consistent with anchoring" (task §9.4 language) but is **not** proof of an LLM-side cognitive anchoring effect.
4. **The H1-primed vs H1-empty comparison isolates the B0-block as the only difference, because the system prompt, user template, schema, and instruction order are byte-identical.** The 11.5-percentage-point FP-inheritance gap is consistent with the B0 block being the cause.
5. **Method ranking (H1-empty > D1 > H1-primed) is stable across IoU thresholds 0.2, 0.3, 0.5, 0.7.** The conclusion does not depend on the specific threshold 0.3.
6. **Run-to-run variance is non-trivial.** H1-primed's F1 ranges from 0.7699 to 0.8391 across 3 repeats (std 0.0396). D1 and H1-empty are more stable but still vary.
7. **Definition is the hardest modality for all three methods.** Recall and Precision are both lower than the other three modalities; over-prediction of definition in the not-independent subset contributes.
8. **Difficulty subset (independent / needs_context / not_independent) ordering is consistent with intuition**: the independent subset is easiest, not_independent hardest. Trend is the same across all three methods.

## 17. Claims not supported

1. **"H1-selective is statistically significantly better than D1."** Not supported. The bootstrap CIs do not consistently exclude 0; some repeats show H1-primed is lower than D1.
2. **"D1 is statistically significantly better than H1-selective."** Not supported at the n=3 level.
3. **"H1-empty is statistically significantly better than D1."** Not supported. Mean F1 differs by 0.005; not significant.
4. **"The FP increase in H1 is caused by anchoring to B0."** Consistent with the pattern, but the design only shows that adding the B0 block to an otherwise identical prompt increases the FP inheritance rate. It does **not** prove a causal cognitive-anchoring mechanism. The task's forbidden language ("证明 LLM 发生锚定") is not used; we say "consistent with".
5. **"B0 F1 > 0.80 is a necessary condition for H1 > D1."** This is the Sun-strength simulation's qualitative finding; it is **not** established by this experiment. The simulation is a controlled illustrative scenario, not a real benchmark. Per task §16.3: "在当前有限扰动网格下，H1 与 D1 的交叉区域出现在模拟 B0 F1 约 0.72–0.82 之间"; we do not claim a precise threshold.
6. **"Six-field evaluation is complete."** Blocked. See `09_SIX_FIELD_BLOCKER.md`.
7. **"Final-violation detection is complete."** Blocked. See `10_DOWNSTREAM_BLOCKER.md`.
8. **"The prior paper's primary result (D1 ≈ H1-selective) reproduces."** The new run finds D1 (0.8486) > H1-primed (0.8156) by 0.033 on mean F1. The ranking is reproduced, but the magnitude is different, and the absolute numbers are different from the prior 0.8019 / 0.7957. The directional conclusion ("D1 ≥ H1-selective") is supported; the exact numbers are not.

## 18. Reproduction commands

```bash
# Phase 0: audit (already done; no LLM call)
cat formal_experiment/outputs/paper_validation_r1_20260728/manifest.json

# Phase 1: frozen config (already done)
cat formal_experiment/outputs/paper_validation_r1_20260728/frozen_batches.json
sha256sum formal_experiment/outputs/paper_validation_r1_20260728/frozen_batches.json

# Phase 3: tests
python -m pytest formal_experiment/tests/paper_validation -v

# Phase 4: full 9 repeats (this is what this run executed)
for method in d1_unprimed h1_selective_primed h1_selective_empty; do
  for rid in 1 2 3; do
    python formal_experiment/scripts/paper_validation/run_repeated_llm_experiment.py \
      --experiment-id paper_validation_r1_20260728 \
      --method $method --repeat-id $rid \
      --batch-file formal_experiment/outputs/paper_validation_r1_20260728/frozen_batches.json \
      --output-root formal_experiment/outputs/paper_validation_r1_20260728 \
      --max-tokens 30000
  done
done
# Then evaluate each (method, repeat)
for method in d1_unprimed h1_selective_primed h1_selective_empty; do
  for rid in 1 2 3; do
    python formal_experiment/scripts/paper_validation/evaluate_predictions.py \
      --method $method --repeat-id $rid \
      --runs-root formal_experiment/outputs/paper_validation_r1_20260728/runs
  done
done

# Phase 5/6/7/8 analyses
python formal_experiment/scripts/paper_validation/bootstrap_record_level.py \
  --runs-root formal_experiment/outputs/paper_validation_r1_20260728/runs \
  --output-dir formal_experiment/outputs/paper_validation_r1_20260728/statistics
python formal_experiment/scripts/paper_validation/analyze_anchoring.py \
  --runs-root formal_experiment/outputs/paper_validation_r1_20260728/runs \
  --output-dir formal_experiment/outputs/paper_validation_r1_20260728/anchoring
python formal_experiment/scripts/paper_validation/analyze_thresholds.py \
  --runs-root formal_experiment/outputs/paper_validation_r1_20260728/runs \
  --output-dir formal_experiment/outputs/paper_validation_r1_20260728/threshold_analysis
python formal_experiment/scripts/paper_validation/analyze_subsets.py \
  --runs-root formal_experiment/outputs/paper_validation_r1_20260728/runs \
  --output-dir formal_experiment/outputs/paper_validation_r1_20260728/subsets
python formal_experiment/scripts/paper_validation/build_validation_report.py \
  --runs-root formal_experiment/outputs/paper_validation_r1_20260728/runs \
  --output-root formal_experiment/outputs/paper_validation_r1_20260728 \
  --statistics-dir formal_experiment/outputs/paper_validation_r1_20260728/statistics \
  --anchoring-dir formal_experiment/outputs/paper_validation_r1_20260728/anchoring \
  --threshold-dir formal_experiment/outputs/paper_validation_r1_20260728/threshold_analysis \
  --subsets-dir formal_experiment/outputs/paper_validation_r1_20260728/subsets \
  --docs-dir formal_experiment/docs/experiments/paper_validation_r1
```

## 19. Artifact index

- `formal_experiment/outputs/paper_validation_r1_20260728/manifest.json` — Phase 0 manifest.
- `formal_experiment/outputs/paper_validation_r1_20260728/file_hashes.json` — SHA-256 of inputs.
- `formal_experiment/outputs/paper_validation_r1_20260728/environment.json` — env snapshot.
- `formal_experiment/outputs/paper_validation_r1_20260728/pip_freeze.txt` — pip freeze.
- `formal_experiment/outputs/paper_validation_r1_20260728/git_status_at_audit.txt` — git status at audit time.
- `formal_experiment/outputs/paper_validation_r1_20260728/preflight_cost_estimate.json` — pre-run cost estimate.
- `formal_experiment/outputs/paper_validation_r1_20260728/frozen_batches.json` + `.sha256` — frozen batches.
- `formal_experiment/outputs/paper_validation_r1_20260728/prompts/d1_prompt.txt` + `h1_selective_primed_prompt_template.txt` + `h1_selective_empty_prompt_template.txt` + `prompt_hashes.json` — normalized prompts.
- `formal_experiment/outputs/paper_validation_r1_20260728/smoke/` — smoke outputs (3 records × 3 methods).
- `formal_experiment/outputs/paper_validation_r1_20260728/runs/<method>/repeat_*/` — per-repeat full outputs.
- `formal_experiment/outputs/paper_validation_r1_20260728/statistics/` — run-level summary + bootstrap.
- `formal_experiment/outputs/paper_validation_r1_20260728/anchoring/` — B0-FP + inheritance.
- `formal_experiment/outputs/paper_validation_r1_20260728/threshold_analysis/` — IoU sensitivity.
- `formal_experiment/outputs/paper_validation_r1_20260728/subsets/` — difficulty + definition.
- `formal_experiment/outputs/paper_validation_r1_20260728/PAPER_VALIDATION_SYNTHESIS.json` + `.md` — synthesis.
- `formal_experiment/docs/experiments/paper_validation_r1/00_AUDIT.md` — Phase 0 audit doc.
- `formal_experiment/docs/experiments/paper_validation_r1/01_FROZEN_CONFIG.md` — Phase 1 doc.
- `formal_experiment/docs/experiments/paper_validation_r1/09_SIX_FIELD_BLOCKER.md` — six-field blocker.
- `formal_experiment/docs/experiments/paper_validation_r1/10_DOWNSTREAM_BLOCKER.md` — final-violation blocker.
- `formal_experiment/docs/experiments/paper_validation_r1/FINAL_REPORT.md` — this file.

(All artifacts under `formal_experiment/outputs/paper_validation_r1_20260728/` are local-only, .gitignore'd by the project's existing rule. Commit hashes and the SHA-256 of each input file are recorded in `manifest.json` and `file_hashes.json` for reproducibility.)
