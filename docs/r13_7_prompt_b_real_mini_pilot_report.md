# R13.7 Prompt B Real Mini-pilot Report

## 1. Scope

Bounded 8-sample real API mini-pilot using Prompt B (`r13_6_prompt_B`,
few_shot_extraction) on the same 8 mini-gold samples from R13.3. One API
call per sample, no retry, no repair, no batch, no raw response saving.

## 2. User Authorization

User explicitly authorized this single bounded run per the R13.7-pre
authorization plan:

> I authorize R13.7 to use Prompt B to execute one bounded real API
> mini-pilot, with a maximum of 8 API calls, one attempt per sample,
> no retries, no repair calls, no batch execution, and no raw response
> saving. I understand this is NOT a benchmark, method validation, or
> Sun reproduction.

Authorization was consumed and the gate is now closed. No future real
API run may proceed without fresh explicit user authorization.

## 3. Selected Prompt

| Property | Value |
|----------|-------|
| Prompt ID | `r13_6_prompt_B` |
| Prompt Name | few_shot_extraction |
| Prompt Path | `prompts/r13_6/few_shot_extraction_prompt.md` |
| Strategy | 3 synthetic few-shot examples with in-context learning |
| Snapshots | `data/formal/metadata/r13_7_prompt_b_selected_prompt_snapshot.json` |

Key prompt features:
- Inferred actor from passive voice
- Normalized [verb] [object] action phrases
- Full propositional constraint statements
- Definition-vs-obligation classification boundary
- English-only output regardless of source language

## 4. Input Samples

Same 8 samples from R13.3 mini-gold set:

| # | Sample ID | Source | Type |
|---|-----------|--------|------|
| 1 | r13_3_candidate_001 | gdpr_eurlex Art 5(1)(a) | Obligation |
| 2 | r13_3_candidate_002 | gdpr_eurlex Art 5(1)(b) | Obligation |
| 3 | r13_3_candidate_003 | gdpr_eurlex Art 5(1)(c) | Obligation |
| 4 | r13_3_candidate_004 | gdpr_eurlex Art 7(1) | Obligation |
| 5 | r13_3_candidate_005 | gdpr_eurlex Art 9(1) | Prohibition |
| 6 | r13_3_candidate_006 | austrian_tax_code § 1 Abs 1 | Definition |
| 7 | r13_3_candidate_007 | austrian_tax_code § 1 Abs 2 | Definition |
| 8 | r13_3_candidate_008 | austrian_tax_code § 1 Abs 3 | Definition |

- Input: `data/formal/processed/r13_3_candidate_samples.jsonl`
- Gold: `data/formal/gold/r13_3_manual_gold_template.jsonl`

## 5. API Boundary

| Constraint | Value |
|------------|-------|
| Provider | openai_compatible |
| Model | qwen3.7-max |
| Max API calls | 8 |
| Attempted calls | 8 |
| Successful calls | 8 |
| API errors | 0 |
| Timeouts | 0 |
| Retry count | 0 |
| Repair call count | 0 |
| Batch used | No |
| Raw response saved | No |
| Benchmark | No |
| Method validation | No |
| Sun reproduction | No |

## 6. Runtime Result

All 8 API calls returned schema-valid JSON (`schema_valid: true`).
All responses were properly parsed into the 6 compliance fields.

### Prediction Output

Sample predictions (`data/formal/predictions/r13_7_prompt_b_real_predictions.jsonl`):

| Sample | Modality | Actor | Action | Condition | Constraint |
|--------|----------|-------|--------|-----------|------------|
| 001 | obligation | entity processing personal data | process personal data | null | Personal data must be processed lawfully, fairly... |
| 002 | obligation | entity collecting personal data | collect and process personal data | null | Personal data must be collected for specified, explicit... |
| 003 | obligation | entity processing personal data | process personal data | null | Personal data must be adequate, relevant and limited... |
| 004 | obligation | controller | demonstrate data subject consent to processing of personal data | Processing is based on consent. | The controller must be able to demonstrate that... |
| 005 | prohibition | entity processing personal data | process special categories of personal data | The personal data reveal racial or ethnic origin... | Processing of special categories of personal data is prohibited. |
| 006 | definition | natural persons | be subject to unlimited income tax liability | The person has a residence or habitual abode... | The person is classified as subject to unlimited income tax liability. |
| 007 | definition | natural persons | be subject to unlimited tax liability | The person has a domicile or habitual abode... | The unlimited tax liability extends to all domestic and foreign income. |
| 008 | definition | natural persons | be subject to limited tax liability | The person has neither a residence nor a habitual abode... | The limited tax liability extends only to the income listed in Section 98. |

Key observations:
- All predictions are in English.
- Actors are canonical forms ("controller", "natural persons", "entity processing personal data").
- Actions are normalized [verb] [object] phrases — no verbatim fragment extraction.
- German text (006-008) correctly translated and classified as definition.
- Passive voice correctly resolved to inferred actors.

## 7. Evaluation Output

- Summary: `data/formal/results/r13_7_prompt_b_real_evaluation_summary.json`
- Details: `data/formal/results/r13_7_prompt_b_real_evaluation_details.jsonl`

All 8 predictions are schema-valid.

## 8. Descriptive Field-level Counts

| Field | Exact | Partial | Missing | Wrong | N/A |
|-------|-------|---------|---------|-------|-----|
| **modality** | 8 | 0 | 0 | 0 | 0 |
| **actor** | 7 | 1 | 0 | 0 | 0 |
| **action** | 4 | 4 | 0 | 0 | 0 |
| **condition** | 2 | 3 | 1 | 0 | 2 |
| **constraint** | 3 | 5 | 0 | 0 | 0 |
| **exception** | 0 | 0 | 0 | 0 | 8 |

Failure categories: `condition_wrong` count = 1.

## 9. Comparison Boundary Against R13.4.2

This section provides descriptive differences observed between R13.4.2
(minimal prompt, no examples) and R13.7 (Prompt B, few-shot). Both are
8-sample mini-pilots on the same samples with the same model (qwen3.7-max).
These are **not** benchmark results and do **not** establish Prompt B as
"better" — they are only observations from two independent 8-sample runs.

| Field | R13.4.2 Exact | R13.7 Exact | Observed Difference |
|-------|---------------|-------------|---------------------|
| modality | 7 | 8 | R13.7 had 1 more exact match |
| actor | 0 | 7 | R13.7 produced canonical actors; R13.4.2 mainly null |
| action | 0 | 4 | R13.7 normalized actions; R13.4.2 verbatim fragments |
| condition | mixed | 2 exact + 3 partial | R13.7 produced propositional conditions |
| constraint | 0 | 3 exact + 5 partial | R13.7 produced full-sentence constraints |
| exception | 8 N/A | 8 N/A | Consistent: both runs had no applicable exceptions |

Note: The R13.7 actor and action improvements align with the design
intent of Prompt B (inferred passive-voice actor, normalized [verb]
[object] action, English-only output). This is consistent with the
R13.5 error analysis predictions but does **not** establish causation
from 8 samples.

## 10. Safety Checks

- [x] Authorization gate verified before API config load
- [x] `--execute-real-api` flag required and present
- [x] Max 8 calls enforced programmatically
- [x] One attempt per sample — no retry logic
- [x] No repair call — schema-invalid responses not retried
- [x] No batch — sequential processing only
- [x] Raw response not saved to disk
- [x] No `.env` content read, logged, or stored
- [x] No API key / token / secret printed
- [x] Authorization gate closed after execution
- [x] R13.4.2 prediction/evaluation files not modified
- [x] New R13.7 output paths used — no overwrite

## 11. Limitations

1. **8 samples only** — no statistical power to draw conclusions about
   prompt effectiveness.
2. **Single model** (qwen3.7-max) — results may differ with other models.
3. **Single run** — no repeated measures to assess variance.
4. **Synthetic few-shot examples** — examples were hand-crafted and may
   not generalize to diverse legal texts.
5. **5 English + 3 German samples** — German sample set is small and all
   from one domain (Austrian tax code).
6. **Gold annotations are human-produced** — gold itself may contain
   judgment variability.
7. **No inter-annotator agreement assessment** — gold reliability not
   independently measured.

## 12. Next Step

Return to Codex for R13.7 local-only audit before accepting the Prompt B
real mini-pilot results or drawing any post-run analysis. The audit must
verify:
- Call count ≤ 8
- Schema validity of all outputs
- No retry, no repair, no batch
- No raw response storage
- No `.env` exposure
- Authorization gate properly closed

## 13. Artifacts

| Type | Path |
|------|------|
| Runner | `scripts/run_r13_7_prompt_b_real_mini_pilot.py` |
| Predictions | `data/formal/predictions/r13_7_prompt_b_real_predictions.jsonl` |
| Evaluation Summary | `data/formal/results/r13_7_prompt_b_real_evaluation_summary.json` |
| Evaluation Details | `data/formal/results/r13_7_prompt_b_real_evaluation_details.jsonl` |
| Execution Contract | `data/formal/metadata/r13_7_prompt_b_execution_contract.json` |
| Authorization Checklist | `data/formal/metadata/r13_7_prompt_b_authorization_checklist.json` |

## 14. Claim Boundary

This is an 8-sample Prompt B real API mini-pilot only. It is NOT a
benchmark, NOT method validation, and NOT a Sun reproduction. No claim
of improvement, better model, or better prompt is made. All observations
are descriptive and bounded to this single 8-sample run.
