# R12 Pilot Plan

## 1. Current Status

R11.4.3 single-sample real API smoke: **PASSED**.

| Field | Value |
|-------|-------|
| `source_id` | `r11_4_real_schema_smoke_001` |
| `real_api_call_performed` | `true` |
| `attempted_call_count` | 1 |
| `successful_call_count` | 1 |
| `schema_valid` | `true` |
| `normalizer_status` | `accepted` |
| `fallback_status` | `success` |
| `raw_response_saved` | `false` |
| `batch` | `false` |

The end-to-end pipeline (`LLMConfig.from_env()` → `RealAPITransport` →
`LLMFallbackAdapter` → `normalize_llm_fallback_json()` →
`MultiClauseExtractionResponse` schema gate) produced schema-valid
output for one synthetic sentence.  This is a necessary prerequisite
for a small-sample pilot — it is NOT a benchmark, NOT a dataset
experiment, and NOT method validation.

## 2. Dataset Inventory

```
data/
├── prototype/
│   ├── .gitkeep                       (0 bytes)
│   ├── legal_sentences.jsonl          (1011 bytes, 14 sentences)
│   └── gold_multiclause.jsonl         (10564 bytes, 14 gold annotations)
```

### `legal_sentences.jsonl` (14 synthetic sentences)

| Source ID | Sentence | Type |
|-----------|----------|------|
| d01 | A controller shall record the decision. | single-clause |
| d02 | A reviewer may inspect the file. | single-clause |
| d03 | A service provider must retain the log. | single-clause |
| d04 | A user shall not disclose the token. | single-clause (negated) |
| d05 | Unless approved, a controller shall record the decision. | single-clause + condition |
| d06 | A reviewer may inspect the file and must not alter the record. | multi-clause (2) |
| d07 | A controller may disclose the record only if authorized. | single-clause + constraint |
| d08 | A controller shall respond within 30 days. | single-clause + constraint |
| d12 | The request shall be reviewed by the controller. | single-clause (passive) |
| d13 | A reviewer may inspect the file and shall record the decision. | multi-clause (2) |
| d27 | A violation results in a penalty. | no modality / no actor (hard) |
| d28 | No person shall alter the record unless an exception applies. | single-clause + exception |
| d34 | The provider warrants that the service is available. | no modality (hard) |
| d35 | Unless authorized, no person shall disclose the record. | single-clause + condition |

### `gold_multiclause.jsonl` (14 gold annotations)

Each line is a `MultiClauseExtractionResponse` with clause-level
annotations.  All 14 sentences have human-authored gold labels.

**Sentence complexity distribution**:

| Category | IDs | Count |
|----------|-----|-------|
| Simple single-clause | d01, d02, d03 | 3 |
| Negated modality | d04 | 1 |
| With condition | d05, d35 | 2 |
| Multi-clause | d06, d13 | 2 |
| With constraint | d07, d08 | 2 |
| Passive voice | d12 | 1 |
| Hard (no explicit modality) | d27, d34 | 2 |
| With exception | d28 | 1 |

## 3. Dataset Readiness Judgment

| Question | Answer |
|----------|--------|
| Is there a formal GDPR/BPMN/Sun dataset? | **No** |
| Is there a real regulatory text corpus? | **No** |
| Is there synthetic prototype data? | **Yes** — 14 sentences with gold |
| Can the pipeline process all 14 sentences? | **Yes** — all are legal-style single/multi-clause sentences |
| Is this sufficient for a small-sample pilot? | **Yes** — bounded, auditable, gold-annotated |
| Is this sufficient for formal benchmark? | **No** — sample is too small, no real regulatory texts |
| Is this sufficient for method validation? | **No** — requires formal dataset and statistical analysis |

**Action required before R13+**: acquire or construct a formal
regulatory compliance dataset (GDPR articles, BPMN compliance
patterns, or Sun-style annotations).  R12 pilot uses ONLY the
existing 14 synthetic sentences.

## 4. R12.1 Pilot Scope

R12.1 executes the single-call entrypoint against the 14 synthetic
sentences in `data/prototype/legal_sentences.jsonl`, one at a time,
using the real API pipeline proven in R11.4.3.

**R12.1 IS**:

- A small-sample (14 sentences) real API pilot on synthetic data
- A systematic schema-valid / schema-invalid / api-error count
- A qualitative review of output structure vs gold
- Metadata-only (no raw response storage)

**R12.1 IS NOT**:

- A benchmark
- Method validation
- Formal accuracy evaluation
- A comparison against the Sun baseline
- A dataset experiment on real regulatory texts

## 5. Sample Selection Policy

All 14 sentences from `data/prototype/legal_sentences.jsonl` are
included.  No sampling — the prototype dataset is small enough to
process exhaustively.

If a future dataset is large (>100 sentences), sampling to 10–20
sentences is recommended for pilot phases.

## 6. API Call Budget

| Constraint | Value |
|------------|-------|
| Maximum API calls | **14** (1 per sentence) |
| Per-sentence retry | **0** (no retry) |
| Per-sentence repair call | **0** (no repair) |
| Total maximum API calls | **14** |
| `--execute-real-api` flag | Required |

Each sentence is processed via the single-call entrypoint:

```
python scripts/run_single_call_schema_smoke.py \
  --execute-real-api \
  --source-id <id> \
  --text "<sentence>" \
  --provider openai_compatible
```

## 7. Output Format

Per-sentence JSON metadata (same format as R11.4.3):

```json
{
  "source_id": "<id>",
  "input_text": "<sentence>",
  "real_api_call_performed": true/false,
  "attempted_call_count": 0/1,
  "successful_call_count": 0/1,
  "fallback_status": "success|error|not_triggered",
  "schema_valid": true/false,
  "normalizer_used": true/false,
  "normalizer_status": "accepted|rejected|noop",
  "raw_response_saved": false,
  "secret_redacted": true,
  "batch": false,
  "error": null|"<error message>",
  "output": null|{<MultiClauseExtractionResponse>}
}
```

Plus a summary table after all 14 calls:

| Source ID | Schema Valid | Fallback Status | Notes |
|-----------|-------------|-----------------|-------|
| d01 | true/false | success/error | ... |
| ... | ... | ... | ... |

**No raw LLM responses are saved.**  Metadata only.

## 8. Failure Handling

| Outcome | Action |
|---------|--------|
| `schema_valid=true, error=null` | Count as success |
| `schema_valid=false` | Record, do NOT retry, do NOT repair |
| `api_error` (transport/HTTP) | Record, do NOT retry |
| `config_blocked` | Abort entire pilot, report CONFIG_BLOCKED |
| `schema_valid=true` but wrong structure | Record, note in qualitative review |

Pilot continues through all 14 sentences regardless of individual
failures (except `config_blocked`, which aborts immediately).

## 9. Claim Boundary

R12.1 pilot results support ONLY these statements:

- ✅ "X of 14 synthetic sentences produced schema-valid output"
- ✅ "The pipeline handled N modalities / M clauses correctly"
- ✅ "Failure patterns observed: ..."

R12.1 pilot results DO NOT support:

- ❌ "The method achieves Y% accuracy"
- ❌ "The method outperforms Sun / prior work"
- ❌ "The method is validated for production use"
- ❌ "The method generalizes to real GDPR/BPMN texts"

## 10. Exit Criteria

R12.1 pilot exits when:

- [ ] All 14 sentences processed (or config_blocked abort)
- [ ] Per-sentence metadata collected
- [ ] Summary table with success/failure counts produced
- [ ] Qualitative review of output-vs-gold patterns written
- [ ] No raw responses stored
- [ ] No batch execution
- [ ] No retry or repair calls
- [ ] No benchmark/accuracy/method-validation claims
- [ ] R12.1 documentation updated (experiment_log, issue_log, README)
- [ ] Git commit pushed

After R12.1 exit: **Codex audit required before R13 formal dataset planning.**
