# R13.3 Data Intake Report

## 1. Stage Result

**Status**: R13.3 data intake completed.

All 6 R13.2 planned public-source folders are confirmed present with expected files. Candidate samples were extracted from the 2 text-parseable legal sources (GDPR EUR-Lex, Austrian Income Tax Code). Gold template created but all annotations remain pending manual review.

## 2. Scope

| Item | Value |
|------|-------|
| Real API call | no |
| Data download performed | no (user pre-placed files) |
| Raw file modification | no |
| Code changes | no |
| Benchmark created | no |
| Method validation | no |
| Sun comparison | no |
| Gold annotation completed | no (pending manual review) |

## 3. Raw Source Inventory

| source_id | Status | File Count | Text Extractable |
|-----------|--------|------------|-----------------|
| `gdpr_eurlex` | available_local | 3/3 | yes (PDF via pdfplumber) |
| `austrian_income_tax_code` | available_local | 3/3 | yes (HTML via html.parser) |
| `michel_2022_decision_rules` | available_local | 3/3 | no (paper PDF, not labeled data) |
| `agostinelli_2019_gdpr_bpmn` | available_local | 3/3 | no (paper PDF, BPMN source) |
| `winter_2020_keyword_baseline` | available_local | 3/3 | no (paper PDF, baseline source) |
| `bohmer_2016_energy_supplier` | available_local | 3/3 | no (univie record page) |

Full inventory: `data/formal/metadata/r13_3_raw_inventory.json`

## 4. Source Provenance

All 6 sources have verified `source_url.txt` and `license_or_source_note.txt`. Provenance is recorded in `data/formal/metadata/r13_3_source_provenance.json`.

Key findings:
- GDPR EUR-Lex: official EU legal text, EU-open license, usable for R13.4
- Austrian Income Tax Code: official Austrian legal text, public domain assumed, usable for R13.4
- Michel, Agostinelli, Winter, Böhmer: paper sources only — not original datasets or executable code. Not usable for direct text extraction in R13.4.

## 5. Candidate Sample Extraction

**8 candidate samples extracted** from 2 sources:

| Source | Count | Sample IDs |
|--------|-------|------------|
| GDPR EUR-Lex | 5 | r13_3_candidate_001 through _005 |
| Austrian Income Tax Code | 3 | r13_3_candidate_006 through _008 |

Samples stored in: `data/formal/processed/r13_3_candidate_samples.jsonl`

Sample details:

| ID | Source | Reference | Text (abbreviated) |
|----|--------|-----------|-------------------|
| 001 | GDPR | Article 5(1)(a) | Personal data shall be processed lawfully... |
| 002 | GDPR | Article 5(1)(b) | Personal data shall be collected for specified... |
| 003 | GDPR | Article 5(1)(c) | Personal data shall be adequate, relevant... |
| 004 | GDPR | Article 7(1) | Where processing is based on consent, the controller shall... |
| 005 | GDPR | Article 9(1) | Processing of personal data revealing racial or ethnic origin... shall be prohibited |
| 006 | Austrian | § 1 Abs 1 | Natürliche Personen, die im Inland einen Wohnsitz... sind unbeschränkt einkommensteuerpflichtig |
| 007 | Austrian | § 1 Abs 2 | Unbeschränkt steuerpflichtig sind jene natürlichen Personen... |
| 008 | Austrian | § 1 Abs 3 | Beschränkt steuerpflichtig sind jene natürlichen Personen... |

All samples are `candidate_unreviewed`. No gold annotations have been applied.

## 6. Gold Template Status

Gold template created: `data/formal/gold/r13_3_manual_gold_template.jsonl`

All 8 entries have:
- `modality`: `"unknown"`
- `actor`, `action`, `condition`, `constraint`, `exception`: `null`
- `annotation_status`: `"manual_gold_pending"`

**Gold is NOT completed.** User must manually review and fill annotations following `docs/r13_2_annotation_guideline.md`.

## 7. Missing / Partial Sources

| Item | Status |
|------|--------|
| BPMN process model files | Not extracted (paper sources only, no executable BPMN files) |
| Original Sun labeled datasets | Still missing (requires author contact) |
| Winter baseline executable code | Not found (paper source only) |
| Michel labeled dataset | Not found (paper source only) |
| Böhmer process model data | Not found (publication record only) |

No sources are missing in terms of planned R13.2 collection — all expected files are present. However, 4 of 6 sources are paper-only references and do not provide extractable text or executable data.

## 8. Claim Boundary

- R13.3 does **not** create benchmark data.
- R13.3 does **not** validate the method.
- R13.3 does **not** compare against Sun.
- R13.3 candidate samples are **not gold** until manually reviewed by the user.
- All candidate text is extracted from **publicly available official legal texts** (GDPR EUR-Lex, Austrian RIS), not from original Sun datasets.
- No original Sun code or complete Sun datasets are available.

## 9. Readiness for R13.4

| Gate | Status | Notes |
|------|--------|-------|
| R13.2 planning complete | ✅ | commit `3a5c890` |
| Raw source inventory | ✅ | 6/6 sources confirmed |
| Source provenance recorded | ✅ | All URLs and licenses verified |
| Candidate samples extracted | ✅ | 8 samples (5 GDPR + 3 Austrian) |
| Gold template created | ✅ | All 8 entries as manual_gold_pending |
| Gold annotations completed | ❌ | **BLOCKED** — user must manually review |
| No raw files tracked in git | ✅ | Confirmed (see static scan) |

**R13.4 is blocked until the user completes manual gold review.**

## 10. User Review Needed

The user must:

1. Open `data/formal/gold/r13_3_manual_gold_template.jsonl`
2. For each of the 8 candidate samples, review and fill:
   - `modality` (obligation / prohibition / permission / definition / unknown)
   - `actor` (or null)
   - `action` (or null)
   - `condition` (or null)
   - `constraint` (or null)
   - `exception` (or null)
   - `annotation_status` → change to `reviewed_gold` when confident
   - `reviewer_notes` — document decisions and ambiguities
3. Follow `docs/r13_2_annotation_guideline.md` for labeling rules
4. After review, signal readiness for R13.4

**Important**: The project cannot proceed to any formal mini-pilot (R13.4) until gold annotations are reviewed and committed.

## 11. R13.3.1 Manual Gold Follow-up

The 8 candidate samples have been manually reviewed and the gold template has been updated to `reviewed_gold`. All 8 entries passed JSONL validation (modalities: 3 obligation, 1 prohibition, 4 definition).

**Boundary**: this is a small mini-gold set for future pilot testing only. It is not a benchmark dataset, not an exact Sun reproduction, and not method validation.
