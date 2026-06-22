# R13 Formal Dataset Acquisition and Evaluation Design

## 1. Current Status

R13.0 ✅ completed — planning and dataset acquisition design done.
R13.1 ✅ completed — Sun (2024) paper intake accepted as PAPER_ONLY.
R13.1.1 ✅ completed — cleanup and evidence metric fix.
R13.1.2 ✅ completed — Codex audit documentation fixes.
R13.1.3 ✅ completed — remaining MAP wording residue fix.
R13.2 🔵 IN PROGRESS — public-source collection and mini dataset reconstruction planning.
All 4 original Sun sub-datasets still require author contact.
Original Sun code: not available. Original complete Sun datasets: missing.
No real API calls. No dataset downloads yet. No code changes.

R12 closed as a synthetic prototype API-pipeline sanity milestone (`2324a9e`).
R13.1 intake report: `docs/r13_1_sun_paper_intake.md`.
R13 reconstruction plan: `docs/r13_sun_reconstruction_plan.md`.
R13.2 public-source collection plan: `docs/r13_2_public_source_collection_plan.md`.
R13.2 mini dataset reconstruction plan: `docs/r13_2_mini_dataset_reconstruction_plan.md`.
R13.2 annotation guideline: `docs/r13_2_annotation_guideline.md`.

## 2. Why R13 Is Needed

R12 used 14 synthetic prototype sentences hand-crafted to test the pipeline.
This gave us:

- Schema validation proof (4/14 at 30s, 2/2 at 60s)
- Timeout root-cause analysis
- Per-sample timing metadata infrastructure
- Claim-boundary discipline

It did **not** give us:

- Evaluation on real-world compliance text (GDPR, BPMN, legal)
- Comparison against a published baseline
- Statistical significance
- Generalizability evidence

R13 exists to bridge from synthetic prototype to formal evaluation.

## 3. Dataset Requirements

A formal dataset for `bpc-hybrid` must satisfy:

| Requirement | Description |
|-------------|-------------|
| Real regulatory/compliance text | Not synthetic; sourced from law, regulation, or business process documents |
| Sentence-level or clause-level | Granularity matching the multi-clause schema |
| License confirmed | Permission to use must be verified and recorded |
| Gold annotations exist | Or a plan to produce gold annotations exists |
| Source tracked | URL, download date, license, version recorded in metadata |
| Not a paid/test-only benchmark | Avoid leaderboard lock-in; labels must be available |

## 4. Candidate Dataset Types

Priority order (Scheme B — public research data):

1. **GDPR regulatory text** — Official EU regulation 2016/679 articles and recitals.
   Can be used with Sun-style rule templates or LLM extraction.
2. **Sun et al. baseline dataset** — If the paper published supplementary data,
   this provides a direct comparison target.
3. **Legal requirement extraction datasets** — Annotated corpora from NLP/CL
   venues (ACL, EMNLP, NAACL, LREC, JURIX, ICAIL).
4. **BPMN compliance corpora** — Business process models with compliance rule
   annotations.

See `docs/dataset_sources.md` for the candidate tracking table.

## 5. Required File Structure

```
data/formal/
├── README.md              # This directory's safety and purpose docs
├── raw/                   # Original files, never modified
│   └── .gitkeep
├── processed/             # Cleaned .jsonl for model input
│   └── .gitkeep
├── gold/                  # Gold annotations / labels
│   └── .gitkeep
└── metadata/              # Source records, license, changelog
    └── .gitkeep
```

## 6. Target Processed Format

Each sample in `data/formal/processed/` should be a single JSON line:

```json
{
  "id": "formal_001",
  "text": "The controller shall implement appropriate technical and organisational measures.",
  "source_id": "gdpr_art_24",
  "source_type": "gdpr_article",
  "source_ref": "https://eur-lex.europa.eu/eli/reg/2016/679/art_24",
  "license": "EU-open",
  "language": "en"
}
```

## 7. Gold Annotation Requirements

Each gold record in `data/formal/gold/` should use the multi-clause schema:

```json
{
  "id": "formal_001",
  "source_id": "gdpr_art_24_para_1",
  "clauses": [
    {
      "clause_id": "formal_001-c1",
      "source_id": "formal_001",
      "source_text": "The controller shall implement appropriate technical and organisational measures.",
      "clause_text": "The controller shall implement appropriate technical and organisational measures.",
      "clause_span_start": 0,
      "clause_span_end": 78,
      "modality": {"text": "shall", "span_start": 19, "span_end": 25, "confidence": 1.0},
      "actor": {"text": "The controller", "span_start": 0, "span_end": 14, "confidence": 1.0},
      "action": {"text": "implement appropriate technical and organisational measures", "span_start": 26, "span_end": 78, "confidence": 1.0},
      "condition": null,
      "constraint": null,
      "exception": null,
      "confidence": 1.0
    }
  ],
  "annotation_source": "gold",
  "annotator": "human_expert_001",
  "annotation_date": "YYYY-MM-DD",
  "notes": ""
}
```

Gold annotations may come from:
- Published supplementary data (preferred)
- Manual expert annotation
- Consensus from multiple annotators (with IAA)

## 8. Baseline / Sun Comparison Requirements

To compare against Sun et al.:

- **Same input**: Use the same sentences/documents Sun evaluated on.
- **Same metric**: Use the same evaluation metric (or document differences).
- **Same output format**: Map `bpc-hybrid` output to Sun's format for comparison.
- **Transparency**: Report any differences in preprocessing, tokenization, or schema.

If Sun's exact dataset is unavailable, document the substitution and limitation.

## 9. R13.1 Data Intake Plan

R13.1 will execute the **first data intake** (no API calls):

1. User selects one confirmed dataset from `docs/dataset_sources.md`.
2. User places raw files in `data/formal/raw/`.
3. Create `data/formal/metadata/sources.json` with source info.
4. Process raw text into `data/formal/processed/*.jsonl` (sentence-split, assign IDs).
5. Place or create gold annotations in `data/formal/gold/`.
6. Run `scripts/evaluate_multi_clause.py` against gold to verify format compatibility.
7. Document processing steps in `data/formal/metadata/CHANGELOG.md`.
8. Codex audit the intake before any API call.

## 10. R13.2 Formal Mini-pilot Plan

After R13.1 is accepted, R13.2 may execute a **conservative formal mini-pilot**:

| Constraint | Limit |
|------------|-------|
| Sample count | ≤ 10 |
| Timeout | 60 seconds |
| Real API calls | ≤ 10 |
| Retry | 0 |
| Repair call | 0 |
| Batch | 0 |
| Raw response saved | false |

**Pre-conditions for R13.2:**

- R13.1 data intake is Codex-accepted.
- Gold annotations exist and have been verified.
- The processed input format matches the multi-clause schema.
- The evaluation protocol is documented and accepted.
- No uncommitted changes in the working tree.
- `.env` is gitignored and not staged.

## 11. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Sun dataset unavailable | High | Medium | Use GDPR text directly; document substitution |
| Gold annotations missing | Medium | High | Manual annotation round; IAA threshold |
| License unclear | Medium | High | Stop; do not use unlicensed data |
| Dataset too large for single calls | Low | Medium | Subsample; limit to ≤ 10 in R13.2 |
| Schema mismatch with Sun format | Medium | Low | Document mapping explicitly; note differences |

## 12. Claim Boundary

R13.0 is a **planning-only** stage.

```
R13_0_CLAIM: PLANNING_ONLY
R13_0_BENCHMARK: no
R13_0_METHOD_VALIDATION: no
R13_0_FORMAL_RESULT: no
R13_0_REAL_API: no
```

No formal result is claimed.  No evaluation has been performed.
No dataset has been downloaded or used.

## 13. User Action Items

The user must:

1. Review `docs/dataset_sources.md` and confirm which candidate datasets to pursue first.
2. Locate the Sun et al. baseline paper (title, authors, URL, GitHub if any).
3. Decide whether to use official GDPR text or a pre-processed structured version.
4. Confirm license status for any data before placing it in `data/formal/raw/`.
5. Place verified files in the appropriate `data/formal/` subdirectory.
6. Run the R13.1 intake checklist before any API call.
