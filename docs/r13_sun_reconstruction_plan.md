# R13 — Sun (2024) Reconstruction Plan

## 1. Purpose

This document defines a detailed, auditable plan for reconstructing and comparing against the Sun et al. (2024) baseline using the `bpc-hybrid` framework. It covers all missing assets, gated stages, and the minimum viable comparison (MVC) strategy.

## 2. Baseline Reference

Sun, X., Yang, S., Zhao, C., & Yu, D. (2024). Design-time business process compliance assessment based on multi-granularity semantic information. Springer Nature.

Full intake report: `docs/r13_1_sun_paper_intake.md`

## Terminology

### Paper-aligned Reconstruction

A reconstruction based **only** on Sun paper-visible descriptions, tables, formulas, cited sources, and local/publicly available materials. It is **not** exact reproduction. Paper-aligned reconstruction uses paper-reported metrics (e.g., Table 9 Overall MAP 0.801 at τ=0.8) as comparison targets without claiming access to original Sun code or full original Sun datasets.

### Sun-style Baseline Reconstruction

A local implementation or evaluation design **inspired by** Sun et al.'s described method and comparison setup, without claiming access to original Sun code/data. Sun-style reconstruction may use public cited sources, independently re-created annotations, or simplified model variants.

## Reconstruction Levels

### Level A — Paper-visible Evidence Reconstruction

Use tables, definitions, formulas, and described metrics only. All evaluation targets are taken directly from Sun paper tables (Table 7-12). No original Sun data is used. This is the **current feasible level**.

### Level B — Cited Public Source Reconstruction

Collect public cited sources such as GDPR EUR-Lex, Austrian Income Tax Code, cited BPMN/GDPR papers. Independently process these sources to approximate Sun's pipeline inputs. Results are compared against Sun's paper-reported metrics.

### Level C — Manual Mini-gold Construction

Manually create a small auditable mini-gold dataset with explicit annotation notes. This is used for pipeline sanity checking and qualitative comparison. Mini-gold is **not** a replacement for full Sun dataset evaluation.

### Level D — Optional Author-data Replacement if Later Obtained

If original author code/data are later obtained, replace reconstruction with author-data-backed evaluation. This level requires explicit confirmation of data provenance and license.

## What Cannot Be Claimed With Current Assets

- Exact Sun reproduction cannot be claimed.
- Original Sun baseline reproduction cannot be claimed.
- Original Sun implementation cannot be claimed.
- Original Sun full dataset evaluation cannot be claimed.
- Sun outperformance cannot be claimed.

## 3. Paper Pipeline (Sun 2024) vs bpc-hybrid

```
Sun (2024) Pipeline:
  Regulatory Text → [1] BERT Modality Classification → [2] Parse + Marker Semantic Extraction
  → [3] Rule Base Construction → [4] BPMN Process Model Disassembly
  → [5] Text Similarity Matching (τ) → [6] Violation Detection (3 types)

bpc-hybrid Pipeline (target):
  Regulatory Text → [1] Rule-First Marker Extraction (Sun-like, regex)
  → [2] LLM Fallback (for multi-modality, missing actor/action, low confidence)
  → [3] Multi-Clause Schema → [4] Structured Rule Records
  → [5] Process Model Matching (future) → [6] Violation Detection (future)
```

## 4. Missing Assets Inventory

| ID | Asset | Sun Section | Priority | Acquisition Path | Status |
|----|-------|------------|----------|-----------------|--------|
| A1 | Austrian Income Tax Code text | 5.1.1 | HIGH | https://ris.bka.gv.at/eli/bgbl/1988/400/P0/NOR40205159 | NOT_ACQUIRED |
| A2 | Modality classification labels (4-class) | 5.1.1 | HIGH | Contact author / Reference [28] | NOT_ACQUIRED |
| A3 | 150 annotated sentences (phrase-level) | 5.2 | HIGH | Contact author ("reasonable request") | NOT_ACQUIRED |
| A4 | 12 BPMN process models + rule base | 5.3.1 | HIGH | Reference [33] / Contact author | NOT_ACQUIRED |
| A5 | 4 GDPR BPMN models | 5.3.2 | HIGH | Reference [35] / Contact author | NOT_ACQUIRED |
| A6 | Pre-trained bert-legal-uncased model | 5.1.2 | MEDIUM | HuggingFace / Author | NOT_ACQUIRED |
| A7 | Source code / implementation | — | LOW | Not publicly available | NOT_AVAILABLE |
| A8 | GDPR Articles 1–50 text | 5.3.2 | MEDIUM | EUR-Lex (public) | missing_user_to_collect |

## 5. Minimum Viable Comparison (MVC) Strategy

Given the bpc-hybrid focus on **rule-first extraction + hybrid LLM fallback**, the MVC targets:

### Phase 1: Semantic Extraction Comparison (MVC-1)
- **Target metric**: Precision/Recall/F1 on 6-concept extraction (Table 8 equivalent)
- **Data needed**: A2 (labels) + A3 (annotations) or equivalent re-annotation
- **bpc-hybrid role**: Rule-first extraction alone; LLM fallback for difficult cases
- **Gate**: Rule-first F1 ≥ 60% of Sun's 95.3% to justify the hybrid claim

### Phase 2: Modality Classification Comparison (MVC-2)
- **Target metric**: 4-way classification F1 (Table 7 equivalent)
- **Data needed**: A1 (text) + A2 (labels)
- **bpc-hybrid role**: LLM-based classification vs Sun's BERT fine-tuning
- **Gate**: LLM F1 within ±15% of Sun's 93.1%

### Phase 3: End-to-End Compliance Checking (MVC-3)
- **Target metric**: Violation detection P/R/F1 (Table 12 equivalent)
- **Data needed**: A4 (BPMN models + rules) or A5 (GDPR models)
- **bpc-hybrid role**: Full pipeline with hybrid extraction
- **Gate**: F1 within ±10% of Sun's 0.80

## 6. Stage-Gate Plan

### R13.2 — Mini-Pilot Design (next stage)
- Design ≤10-sample real API pilot
- 60s timeout, ≤10 API calls
- No raw response storage
- NO execution — planning only
- See `docs/r13_formal_dataset_plan.md` Section 8

### R13.3 — Dataset Acquisition
- Contact corresponding author (yudj@hdu.edu.cn)
- Or re-create: download Austrian Income Tax Code from EUR-Lex / RIS
- Re-annotate a small subset (≤50 sentences) for phrase-level concepts
- License verification and metadata recording

### R13.4 — MVC-1 Implementation
- Implement Sun-compatible evaluation metrics
- Run rule-first extraction on acquired/annotated data
- Compare against Sun Table 8
- Document gap analysis

### R13.5 — MVC-2 Implementation
- LLM-based modality classification
- Compare against Sun Table 7
- Gate: within ±15% F1

### R13.6 — MVC-3 Implementation
- Full pipeline integration
- Compare against Sun Table 12
- Gate: within ±10% F1

## 7. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Author does not share data | HIGH | HIGH | Re-create Austrian tax code dataset; re-annotate independently |
| bert-legal-uncased unavailable | MEDIUM | LOW | Use general BERT + fine-tune on public legal corpora |
| BPMN models unavailable | HIGH | MEDIUM | Use public BPMN datasets; GDPR BPMN can be modeled from Article text |
| Quality gap >15% F1 | MEDIUM | HIGH | Accept hybrid is different approach, not strictly better/worse |
| Licensing issues with re-annotation | LOW | MEDIUM | Use only public-domain regulatory text |

## 8. Claim Boundaries

- This is a RECONSTRUCTION PLAN, not an implementation claim.
- No comparison against Sun has been performed yet.
- No formal result exists. No benchmark.
- All R13.x stages before dataset acquisition are PLANNING_ONLY.
- The MVC strategy may change after dataset inventory.
