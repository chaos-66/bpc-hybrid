# R14.2 Rule-only Baseline Report

## 1. Scope

This report documents the R14.2 deterministic rule-only baseline experiment
on the 24-sample R14.1 draft mini-gold dataset. The experiment uses only the
marker/pattern-based `RuleFirstExtractor` — no LLM, no API, no network.

## 2. Input Dataset

- **Candidate samples**: `data/formal/r14_controlled/r14_1_candidate_samples.jsonl` (24 samples)
- **Gold annotations**: `data/formal/r14_controlled/r14_1_mini_gold.jsonl` (24 annotations)
- **Domain balance**: 12 GDPR-style + 12 Austrian Income Tax / EStG-style
- **Source balance**: 8 R13 seed + 16 controlled-authored

## 3. Rule-only Method

The extraction uses the `RuleFirstExtractor` from `src/bpc_hybrid/extractor.py`:

- **Modality detection**: Ordered priority matching of `shall`, `must`, `may`,
  `shall not`, `must not`, `no person shall` — longest match first, word-boundary
  enforced.
- **Actor extraction**: Pre-marker text for active voice; `by <agent>` pattern
  for passive voice.
- **Action extraction**: Text between modality marker and the nearest
  constraint/exception/end boundary.
- **Condition extraction**: Leading `Unless <X>,` pattern (inherited across
  split clauses).
- **Constraint extraction**: `within`, `before`, `after`, `only if`,
  `provided that` markers.
- **Exception extraction**: Mid-sentence `unless` clauses.
- **Multi-clause splitting**: `and`-based decomposition when multiple modality
  markers are detected.

Modality marker strings are mapped to the closed-set enum:
- `shall` / `must` → `obligation`
- `shall not` / `must not` / `no person shall` → `prohibition`
- `may` → `permission`

## 4. No-LLM / No-API Boundary

R14.2 is a **purely deterministic local experiment**. The following were
NOT used or accessed:

- No LLM API call (no OpenAI, no Anthropic, no local LLM)
- No embedding API
- No reranker API
- No external network access
- No `.env` file read
- No raw response storage
- No retry logic
- No manual correction after seeing gold results

Every prediction record contains `execution.llm_used: false`,
`execution.api_used: false`, `execution.network_used: false`.

## 5. Evaluation Metrics

Evaluation follows the scoring taxonomy defined in `docs/r14_0_metric_definition.md`:

| Score | Definition |
|-------|-----------|
| exact | Normalized string equality OR token-set equivalence (Jaccard = 1.0) |
| partial | Token overlap Jaccard >= 0.5 and < 1.0 |
| missing | Gold non-null, prediction null |
| wrong | Token overlap Jaccard < 0.5, or gold null + prediction non-null |
| not_applicable (NA) | Both gold and prediction null |

Metrics computed:
- **overall_field_exact_accuracy**: sum(exact) / sum(applicable) across all 6 fields
- **strict_precision / strict_recall / strict_f1**: only exact counts as correct
- **lenient_partial_precision / recall / f1**: exact + partial count as correct
- **macro_strict_f1**: average of per-field strict F1
- **micro_strict_f1**: micro-averaged strict F1 across all fields
- **macro_lenient_f1 / micro_lenient_f1**: same with lenient counts

## 6. Overall Result

See `data/formal/results/r14_2_rule_only_evaluation_summary.json` for exact numbers.

Key metrics (to be filled after run):

| Metric | Value |
|--------|-------|
| overall_field_exact_accuracy | 0.1491 |
| strict_f1 (micro) | 0.2138 |
| macro_strict_f1 | 0.1405 |
| lenient_partial_f1 (micro) | 0.3145 |
| macro_lenient_f1 | 0.2212 |

## 7. Field-level Result

See `data/formal/results/r14_2_rule_only_evaluation_summary.json` →
`field_level_summary` for per-field counts and metrics.

## 8. Error Pattern Notes

The rule-only extractor has known limitations:

- **Actor extraction** is heuristic — relies on pre-marker text (active voice)
  or `by <agent>` patterns (passive voice). Sentences with complex noun phrases
  or implicit actors will produce partial or missing actors.
- **Action boundary** is approximate — the action span ends at the nearest
  constraint/exception marker. Complex sentences with nested clauses may
  produce truncated or over-extended actions.
- **Condition/exception** detection covers only `unless`-based patterns.
  Conditional constructions using `if`, `when`, `provided`, `in case of`,
  `subject to` are not handled.
- **Multi-clause merging** takes only the first clause's fields. Later clauses'
  constraints and exceptions may be lost.

These limitations are expected for a deterministic rule-only baseline and
represent the gap that a Rule+LLM approach (R14.3) may address.

## 8. PPT-safe Summary

R14.2 establishes the no-LLM deterministic baseline on the 24-sample draft
mini-gold. The result will be used later as the rule-only side of a controlled
comparison, after a separate Rule+LLM run is authorized and audited.

## 9. Limitations

1. **Deterministic rules only**: The extractor uses hard-coded marker patterns
   and cannot generalize to unseen syntactic structures.
2. **24-sample scale**: This is a draft mini-gold, not a statistically powered
   benchmark. Results describe this specific dataset only.
3. **No inter-annotator agreement**: Gold annotations are from a single
   annotator and marked `draft_mini_gold_pending_user_review`.
4. **No comparison with Rule+LLM yet**: R14.2 provides only the rule-only
   baseline side. R14.3 (Rule+LLM) is a separate future stage.

## 10. Next Stage Recommendation

After R14.2 is accepted by Codex audit:
- **R14.3**: Run Rule+LLM-assisted extraction on the same 24 samples (requires
  separate user authorization).
- **R14.4**: Compare rule-only vs Rule+LLM results using the metrics defined in
  `docs/r14_0_metric_definition.md`.

Do not proceed to R14.3 until R14.2 is accepted and Rule+LLM authorization is
explicitly provided.

## 11. Claim Boundary

This is a rule-only baseline result.
This is not a benchmark.
This is not method validation.
This is not Sun reproduction.
This does not compare against Rule+LLM yet.
No LLM or real API was used.
