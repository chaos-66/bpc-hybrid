# R13.1 — Sun (2024) Paper Intake Report

## 1. Paper Identification

| Field | Value |
|-------|-------|
| Title | Design-time business process compliance assessment based on multi-granularity semantic information |
| Authors | Xiaoxiao Sun, Siqing Yang, Chenying Zhao, Dongjin Yu |
| Corresponding author | Dongjin Yu (yudj@hdu.edu.cn) |
| Affiliation | School of Computer Science and Technology, Hangzhou Dianzi University, Hangzhou, China |
| Year | 2024 |
| Venue | Springer Nature (LaTeX template; likely LNCS proceedings or journal) |
| Pages | 28 |
| PDF path | `data/formal/raw/sun_2024_design_time_bpc_multigranularity.pdf` |
| PDF size | 2,694,008 bytes (~2.7 MB) |
| Full text extracted | `data/formal/raw/sun_2024_full_text.txt` (65,448 chars) |
| Intake date | 2026-06-19 |
| Intake stage | R13.1 |
| Keywords | Compliance Checking, Violation Detection, Business Process, Text Mining, Natural Language Processing, Deep Learning |

## 2. Paper Summary

Sun et al. (2024) propose an **automatic and interpretable design-time business process compliance (BPC) checking approach** that covers the entire lifecycle: extracting semantic information from regulatory documents at multiple granularities, matching rules to process models, and detecting violations from three control-flow perspectives (missing action, incorrect actor, out-of-order execution).

The approach combines **deep learning (BERT pre-training + fine-tuning)** for sentence-level modality classification with a **rule-template-based NLP method** for phrase-level semantic extraction (modality, actor, action, condition, constraint, exception).

### 2.1 Pipeline Overview

1. **Modality Classification** (Sec 4.1): Pre-train BERT on general + legal corpora, fine-tune on labeled Austrian Income Tax Code sentences classified into obligation / prohibition / permission / definition (4-way). Best model: `bert-legal-uncased`.

2. **Semantic Information Extraction** (Sec 4.2): Use constituent parse trees + marker-based rules to extract six phrase-level concepts (modality, actor, action, condition, constraint, exception) from each regulatory sentence.

3. **Rule Base Construction** (Sec 4.3): Match extracted semantic concepts to rule records (obligation/prohibition/permission) with normalized actors, actions, conditions, constraints, and exceptions.

4. **Process Model Disassembly** (Sec 4.4): Decompose BPMN process models into sequential, parallel, and exclusive-gateway fragments; extract label semantics from each activity.

5. **Compliance Checking** (Sec 4.5): Match rule records to process model fragments using text similarity (τ threshold); detect three violation types (missing action, incorrect actor, out-of-order execution).

## 3. Datasets Identified in Paper

### 3.1 Dataset A — Austrian Income Tax Code (Modality Classification)

| Field | Value |
|-------|-------|
| Source | Reference [28] — publicly available |
| Content | Sentences from Austrian Income Tax Code (Bundesgesetzblatt 1988/400) |
| URL | https://ris.bka.gv.at/eli/bgbl/1988/400/P0/NOR40205159 |
| Labels | 4 categories: definition (0), obligation (1), prohibition (2), permission (3) |
| Split | 9:1 train/test |
| In workspace | NO |
| Acquisition path | Contact corresponding author OR locate reference [28] |

### 3.2 Dataset B — Annotated Sentences (Semantic Extraction)

| Field | Value |
|-------|-------|
| Source | Same Austrian Income Tax Code |
| Content | 150 sentences, each >20 words, annotated by authors |
| Annotations | Phrase-level: type (concept) + span (start/end character position) |
| Inter-annotator check | 10% independently double-annotated |
| In workspace | NO |
| Acquisition path | Contact corresponding author ("available on reasonable request") |

### 3.3 Dataset C — 12 BPMN Process Models (Matching Evaluation)

| Field | Value |
|-------|-------|
| Source | Reference [33] — earlier work by domain experts |
| Content | 12 BPMN process models for Austrian energy supplier smart meter scenarios |
| Rule base | Parsed from regulatory documents related to smart meters |
| In workspace | NO |
| Acquisition path | Reference [33]; contact corresponding author |

### 3.4 Dataset D — 4 GDPR BPMN Models (End-to-End Checking)

| Field | Value |
|-------|-------|
| Source | Reference [35] |
| Content | 4 BPMN process models capturing GDPR privacy constraints |
| Regulatory docs | GDPR Articles 1–50 |
| Violation data | Table 10: 21/30/38/46 matching rules per model, 7–23 missing actions, 5–10 incorrect actors, 9–16 out-of-order |
| In workspace | NO |
| Acquisition path | Reference [35]; contact corresponding author |

## 4. Key Results Tables

### Table 6: Modality Classification (different pre-trained models)

| Model | Precision | Recall | F1 |
|-------|-----------|--------|-----|
| bert-base-uncased | 90.8% | 89.6% | 88.7% |
| bert-base-cased | 86.7% | 87.6% | 84.1% |
| bert-large-uncased | 89.4% | 91.3% | 86.7% |
| bert-large-cased | 88.8% | 89.7% | 89.0% |
| **bert-legal-uncased** | **92.1%** | **94.1%** | **89.3%** |
| bert-legal-cased | 91.3% | 93.3% | 88.5% |

### Table 7: Modality Classification (vs baselines, bert-legal-uncased)

| Model | Precision | Recall | F1-score |
|-------|-----------|--------|----------|
| CF_KW (keyword) | 62.7% | 64.7% | 60.8% |
| CF_RNN | 90.3% | 91.6% | 90.9% |
| CF_CNN | 87.4% | 90.1% | 90.2% |
| **Our approach** | **92.1%** | **94.1%** | **93.1%** |

### Table 8: Semantic Extraction (per concept)

| Concept | Ground Truth | Extracted | Matched | Misclassified | Missed | Precision | Recall |
|---------|-------------|-----------|---------|--------------|--------|-----------|--------|
| Modality | 82 | 81 | 80 | 1 | 2 | 98.8% | 97.6% |
| Actor | 118 | 110 | 109 | 1 | 9 | 99.1% | 92.4% |
| Action | 147 | 147 | 145 | 2 | 2 | 98.6% | 98.6% |
| Condition | 46 | 40 | 40 | 0 | 6 | 100% | 86.9% |
| Constraint | 35 | 38 | 34 | 4 | 1 | 89.5% | 97.1% |
| Exception | 15 | 15 | 14 | 1 | 1 | 93.3% | 93.3% |
| **Overall** | **443** | **431** | **422** | **9** | **21** | **97.9%** | **95.3%** |

### Table 12: Comparison with Winter et al. (2020) [14]

| Method | Precision | Recall | F-score |
|--------|-----------|--------|---------|
| Winter et al. (2020) | 0.58 | 0.89 | 0.70 |
| **Sun et al. (our method)** | **0.77** | **0.83** | **0.80** |

## 5. Paper State Classification

**PAPER_ONLY** — The PDF is available. None of the four underlying datasets (A–D), reference implementations, rule bases, or gold annotations are present in the workspace.

## 6. Compliance with bpc-hybrid Framework

| Aspect | Sun (2024) | bpc-hybrid (current) |
|--------|-----------|---------------------|
| Pipeline stage | Full end-to-end (classification → extraction → matching → checking) | R12: synthetic prototype (extraction + schema validation only) |
| Modality classification | BERT pre-training + fine-tuning | Not implemented (LLM fallback for multi-modality) |
| Semantic extraction | Constituent parse + marker rules | Rule-template regex extraction (same spirit) |
| Rule base | Structured rule records | Not yet (R13+ target) |
| Process model matching | Text similarity with τ threshold | Not yet |
| Violation detection | 3 types (missing action, incorrect actor, out-of-order) | Not yet |
| Real API pipeline | N/A | Single-sample validation (R11.4.3), bounded pilot (R12.1), timeout sanity (R12.3.1) |

## 7. R13.2 Implications

The Sun paper defines the primary baseline for bpc-hybrid's formal evaluation. R13.2 mini-pilot design must account for:
- Missing dataset acquisition (all 4 datasets require author contact or re-creation)
- Missing BERT pre-trained model (bert-legal-uncased)
- Missing compliance checking pipeline (matching + violation detection)
- The bpc-hybrid "hybrid" strategy (rule-first + LLM fallback) aligns with Sun's combined deep learning + rule-based approach

## 8. Intake Verification

| Check | Result |
|-------|--------|
| PDF exists at declared path | ✅ `data/formal/raw/sun_2024_design_time_bpc_multigranularity.pdf` |
| PDF = 28 pages | ✅ |
| Full text extracted (utf-8) | ✅ `data/formal/raw/sun_2024_full_text.txt` |
| pdfplumber used (no network) | ✅ offline extraction |
| No API calls made | ✅ |
| No .env read | ✅ |
| No source code modified | ✅ (new docs only) |

## 9. Artifact Redistribution Policy (added R13.1.1)

- The Sun (2024) PDF is stored locally at `data/formal/raw/sun_2024_design_time_bpc_multigranularity.pdf` and the derived full-text extract at `data/formal/raw/sun_2024_full_text.txt`.
- **Neither file is committed to git** due to unclear redistribution/copyright status of the published PDF.
- Both files are excluded via `.gitignore` rules (`data/formal/raw/**/*.pdf`, `data/formal/raw/**/*full_text*.txt`).
- All derivative work (this intake report, evidence JSON, metadata registry, reconstruction plan) is committed.
- If you clone this repository, you will need to obtain the PDF independently (e.g., Springer Nature download or corresponding author request) and run the offline text extraction yourself.
