# R14.1 Mini-gold Construction Report

## 1. Scope

This report documents the construction of the R14.1 24-sample mini-gold dataset for the controlled Rule-only vs Rule+LLM comparison experiment designed in R14.0.

The dataset consists of:
- 24 candidate sentences (text input for extraction)
- 24 gold annotations (reference field-level annotations)

## 2. Source Boundary

**Seed samples** (8 samples, `r14_1_sample_001`–`008`):
- Reused from R13.3 candidate samples and gold annotations
- Source files read (read-only): `data/formal/processed/r13_3_candidate_samples.jsonl`, `data/formal/gold/r13_3_manual_gold_template.jsonl`
- Original R13 files were NOT modified
- R13 gold format was adapted from flat to nested `gold_fields` structure per R14.1 spec

**Controlled-authored samples** (16 samples, `r14_1_sample_009`–`024`):
- Authored specifically for this controlled experiment
- Not extracted from real legal texts
- Not drawn from public benchmarks
- Not from the Sun dataset
- Designed to cover diverse extraction challenges: obligations, permissions, prohibitions, definitions, condition-heavy sentences, exception-heavy sentences, multi-clause sentences, passive-voice sentences, constraint-heavy sentences

## 3. Sample Composition

| Sample ID Range | Count | Domain | Source |
|----------------|-------|--------|--------|
| 001–005 | 5 | GDPR-style | r13_seed_reused |
| 006–008 | 3 | Austrian Income Tax / EStG-style | r13_seed_reused |
| 009–015 | 7 | GDPR-style | controlled_authored |
| 016–024 | 9 | Austrian Income Tax / EStG-style | controlled_authored |

**Total**: 8 R13 seed + 16 controlled-authored = 24 samples.

## 4. Field Annotation Schema

Every gold annotation includes all 6 fields in the `gold_fields` object:

| Field | Type | Allowed Values |
|-------|------|---------------|
| modality | closed-set enum | obligation, permission, prohibition, definition |
| actor | free-text | entity name or null |
| action | free-text | action description or null |
| condition | free-text | trigger condition or null |
| constraint | free-text | normative content or null |
| exception | free-text | exception clause or null |

Each field uses the format: `{"value": "...", "applicable": true/false, "notes": "..."}`.

## 5. Domain Balance

| Domain | Seed (R13) | New (authored) | Total |
|--------|-----------|----------------|-------|
| GDPR-style | 5 | 7 | **12** |
| Austrian Income Tax / EStG-style | 3 | 9 | **12** |
| **Total** | **8** | **16** | **24** |

## 6. Design Tag Coverage

The 24 samples collectively cover the following design tags:

| Design Tag | Count | Present In |
|-----------|-------|-----------|
| obligation | 12 | 001–004, 010, 012–014, 016, 020–022 |
| permission | 2 | 009, 017 |
| prohibition | 3 | 005, 011, 018 |
| definition | 7 | 006–008, 015, 019, 023, 024 |
| condition_heavy | 9 | 004, 006, 010–011, 013, 016–017, 019, 022 |
| exception_heavy | 3 | 011, 019, 022 |
| multi_clause | 11 | 005, 007–008, 010, 012, 014, 017, 020–021, 023–024 |
| passive_voice | 7 | 001–003, 005, 013, 018, 021 |
| active_voice | 2 | 004, 009 |
| constraint_heavy | 12 | 001–003, 005, 012, 014–015, 018, 020–021, 023–024 |
| German | 3 | 006–008 |

## 7. Quality Checks

- All 24 candidate samples have correct IDs: `r14_1_sample_001` through `r14_1_sample_024`
- All 24 gold annotations have matching sample IDs
- All gold annotations have all 6 required fields with proper structure
- Domain balance: exactly 12 GDPR-style + 12 Austrian Tax
- Source balance: exactly 8 seed_reused + 16 controlled_authored
- All controlled-authored samples explicitly marked: `is_real_legal_text: false`, `is_public_benchmark: false`, `not_sun_dataset: true`
- No prediction files were created or modified
- No evaluation output was generated
- No metrics were computed

## 8. Limitations

1. **Draft status**: All annotations are marked `draft_mini_gold_pending_user_review`. User review is required before using these gold annotations in any formal comparison.
2. **Controlled authorship**: The 16 new samples are synthetic-style constructions, not authentic legal text extracts. They are designed to test specific extraction challenges but do not represent natural regulatory language distribution.
3. **Single annotator**: All gold annotations were produced by the experiment designer, not by multiple independent annotators. No inter-annotator agreement scores are available.
4. **No real API**: No LLM calls were made during annotation. No retrieval-augmented generation or external knowledge sources were used.
5. **Scale limitation**: 24 samples is appropriate for a small controlled comparison but insufficient for statistical significance testing or benchmark claims.

## 9. Next Stage Recommendation

After R14.1 is accepted by Codex audit:
- **R14.2**: Run rule-only baseline extraction on the 24 samples
- **R14.3**: Run Rule+LLM-assisted extraction on the 24 samples (requires user authorization)
- **R14.4**: Compare results using the metrics defined in `docs/r14_0_metric_definition.md`

Do not proceed to R14.2 or R14.3 until R14.1 is accepted.

## 10. Claim Boundary

This is a draft mini-gold pending user review.
This is not a public benchmark.
This is not Sun reproduction.
This does not contain real GDPR/BPMN formal evaluation data.
No API call, LLM call, rule experiment, or evaluator run was performed.
The 16 controlled-authored samples are synthetic-style constructions for project experimentation only.
