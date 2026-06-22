# R13.2 Mini Dataset Reconstruction Plan

## 1. Objective

Define a concrete, executable plan for building a **mini formal dataset** (6-10 samples) from
publicly collected sources. This dataset is for pipeline sanity checking and paper-aligned
reconstruction — it is NOT the original Sun dataset and does NOT support benchmark claims.

## 2. Why Mini Dataset Reconstruction Is Needed

R13.1 confirmed:

- Original Sun source code: **not available**.
- Original complete Sun datasets (DS001-DS005): **all NOT_ACQUIRED** (require author contact).
- Exact Sun reproduction: **forbidden**.

The project must have at least a small set of real regulatory sentences with gold annotations
to validate the pipeline before any larger formal effort. A mini dataset bridges the gap
between synthetic prototype (R12) and full formal evaluation.

## 3. Reconstruction Principle

```
Paper-aligned, not Sun-copied.
```

- Use **paper-visible descriptions** (tables, definitions, formulas, cited sources) from
  Sun et al. 2024 to guide reconstruction.
- Source text from **publicly available legal/regulatory documents**, not from Sun's private data.
- Annotations created **by this project**, following Sun's annotation categories as described
  in the paper.
- Results are comparable to Sun's paper-reported metrics in a qualitative/approximate sense
  only — not as a formal reproduction.

## 4. Candidate Input Sources

| Priority | Source | Type | Expected Contribution |
|----------|--------|------|----------------------|
| P0 | GDPR EUR-Lex (Articles 1-50) | Regulatory text | 3-5 mini-gold samples |
| P0 | Austrian Income Tax Code (BGBl 1988/400) | Legal text | 2-3 mini-gold samples (if acquired) |
| P1 | Agostinelli et al. GDPR BPMN | Process models | 1-2 BPMN case-study samples (if acquired) |
| P1 | Böhmer et al. energy supplier BPMN | Process models | 1-2 BPMN case-study samples (if acquired) |
| P2 | Manual annotation | Gold labels | All gold annotations created by this project |

## 5. Proposed Mini Dataset Size

| Sample Type | Count | Source |
|-------------|-------|--------|
| GDPR Article sentences | 3-5 | `gdpr_eurlex` |
| Austrian Income Tax Code sentences | 2-3 | `austrian_income_tax_code` |
| BPMN case-study samples | 1-2 | `agostinelli_2019_gdpr_bpmn` or `bohmer_2016_energy_supplier` |
| **Total** | **6-10** | |

Exact counts depend on what the user successfully collects. The minimum viable is **6 samples**
from at least 2 different source types.

## 6. Data Units

The primary data unit is a **regulatory sentence** or **clause** from a legal/regulatory text.
Each sample may contain one or more normative clauses (obligations, prohibitions, permissions,
definitions).

For process-model samples, the unit is a **sentence or rule extracted from a BPMN model**
paired with its regulatory reference.

## 7. Processed JSONL Format

Each sample in `data/formal/processed/formal_mini_samples.jsonl`:

```json
{
  "sample_id": "formal_mini_001",
  "source_id": "gdpr_eurlex",
  "source_type": "legal_text",
  "source_ref": "Article 5(1)(a)",
  "text": "Personal data shall be processed lawfully, fairly and in a transparent manner in relation to the data subject.",
  "language": "en",
  "license_status": "EU_open",
  "provenance_note": "Extracted from EUR-Lex Regulation (EU) 2016/679, Article 5",
  "processing_date": "2026-06-22",
  "processing_stage": "R13.2"
}
```

## 8. Gold Annotation Format

Each gold annotation in `data/formal/gold/manual_mini/gold_samples.jsonl`:

```json
{
  "sample_id": "formal_mini_001",
  "modality": "obligation",
  "actor": "data controller",
  "action": "process personal data lawfully, fairly, transparently",
  "condition": null,
  "constraint": "in relation to the data subject",
  "exception": null,
  "annotation_status": "manual_gold_candidate",
  "reviewer_notes": "Clear obligation on the controller. 'Shall' indicates obligation.",
  "annotation_date": "2026-06-22",
  "annotator": "project_author"
}
```

Schema definition: see `data/formal/metadata/mini_dataset_schema.json`.

## 9. Baseline-compatible Fields

To enable paper-aligned comparison against Sun Table 9 (matching) and Table 12 (violation detection):

| Sun Metric | Mini Dataset Field | Notes |
|------------|-------------------|-------|
| Modality classification (Table 7) | `modality` | 4-class + unknown |
| Semantic extraction (Table 8) | `actor`, `action`, `condition`, `constraint`, `exception` | 6-concept phrase-level |
| Matching MAP (Table 9) | Matching requires BPMN models + rule base | Not available at mini scale |
| Violation detection (Table 12) | `violation_type`, `violation_status` | Only if BPMN source obtained |

The mini dataset can support modality classification and semantic extraction comparison.
It **cannot** support matching MAP or full violation detection without BPMN models.

## 10. Manual Review Procedure

1. **First pass**: Project author annotates all 6-10 samples independently.
2. **Second pass**: Re-review after ≥24 hours to catch errors and resolve ambiguities.
3. **Uncertain samples**: Mark `annotation_status: "uncertain"` and document the ambiguity.
4. **Final review**: Promote to `reviewed_gold` when annotation is stable.
5. **Commit**: Only `reviewed_gold` samples may be committed as formal gold.

## 11. Quality Gates

| Gate | Criterion | Required Before |
|------|-----------|-----------------|
| G1 | ≥6 samples from ≥2 source types | R13.3 data intake |
| G2 | All samples have `reviewed_gold` status | R13.4 pipeline run |
| G3 | All samples have 100% field completeness (null allowed where not applicable) | R13.4 pipeline run |
| G4 | Ambiguity notes exist for all `uncertain` samples | R13.4 pipeline run |
| G5 | No sample claims to be from original Sun dataset | Always |

## 12. What This Dataset Can Support

- Pipeline sanity checking on real regulatory text.
- Paper-aligned modality classification comparison (Sun Table 7 equivalent).
- Paper-aligned semantic extraction comparison (Sun Table 8 equivalent).
- Qualitative error analysis.
- Annotation guideline refinement.

## 13. What This Dataset Cannot Support

- Exact Sun reproduction.
- Sun baseline reproduction.
- Formal benchmark results.
- Statistical significance claims.
- Method validation claims.
- "Outperforming Sun" claims.
- Full matching MAP evaluation (requires BPMN models).
- Full violation detection evaluation (requires BPMN models + violation data).

## 14. R13.3 Next Step

After user completes public-source collection per `docs/r13_2_public_source_collection_plan.md`:

1. **R13.3 data intake**: Inventory collected sources, verify license/provenance, register
   in `sources.json`.
2. **R13.4 mini dataset construction**: Extract sentences, create gold annotations, run
   pipeline.
3. **R13.5 paper-aligned comparison**: Run modality classification and semantic extraction
   against paper-reported metrics.
