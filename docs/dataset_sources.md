# Dataset Sources

## 1. Purpose

Track candidate formal datasets for the `bpc-hybrid` project after R12 closed as a
synthetic prototype API-pipeline sanity milestone.  This document lists known/possible
sources, the files the user must (manually) collect, and storage rules.

No dataset has been downloaded yet (R13.0 is planning only).

## 2. Candidate Source Categories

| Category | Description | Priority |
|----------|-------------|----------|
| GDPR regulatory text | Official GDPR articles/recitals as plaintext or structured JSON | High |
| Legal requirement extraction | Annotated sentences/clauses from academic NLP papers | High |
| BPMN compliance | Business process models paired with compliance rules | Medium |
| Sun baseline | Sun et al. paper data, supplementary, code repo, gold labels | High |
| Public compliance corpora | Open-licensed legal/compliance text corpora | Medium |

## 3. Candidate Datasets / Papers

| ID | Name | Type | URL / Location | License | Has Gold | Has Baseline | Status | Notes |
|----|------|------|----------------|---------|----------|--------------|--------|-------|
| DS001 | Sun et al. (2024) — Design-time BPC multi-granularity | Paper + 4 datasets | PDF: `data/formal/raw/sun_2024_design_time_bpc_multigranularity.pdf` | author_request | yes | yes | paper_intake_complete | Intake: R13.1. 4 sub-datasets: Austrian tax code, 150 annotated sentences, 12 energy BPMN models, 4 GDPR BPMN models. All need author contact. See `docs/r13_1_sun_paper_intake.md`. |
| DS002 | GDPR official text (EUR-Lex) | Regulatory text | https://eur-lex.europa.eu/eli/reg/2016/679/oj | EU open | no (raw text) | no | needs_user_confirmation | Articles and recitals; needs sentence splitting and ID assignment |
| DS003 | GDPR recitals + articles structured | Processed regulatory text | source_unknown | license_unknown | partially | no | needs_user_confirmation | Some public repos provide structured JSON/XML; check GDPR.eu, GDPR-info.eu |
| DS004 | Legal document clause/requirement extraction datasets | NLP dataset | source_unknown | license_unknown | yes (assumed) | unknown | needs_user_confirmation | Search ACL Anthology, Papers With Code for "legal requirement extraction", "compliance checking" |
| DS005 | BPMN compliance checking corpus | Research data | source_unknown | license_unknown | yes (assumed) | unknown | needs_user_confirmation | Business process model repositories paired with compliance rules |
| DS006 | Public GDPR annotation projects | Community data | source_unknown | varies | yes (partial) | no | needs_user_confirmation | GDPR.eu, Privado, or academic annotation projects |

## 4. User File Request List

The user must **manually** locate and verify each candidate source.  Requested files per
candidate:

### DS001 — Sun (2024) baseline

**Paper PDF**: ✅ Acquired — `data/formal/raw/sun_2024_design_time_bpc_multigranularity.pdf` (2.7 MB, 28 pages)
**Full text**: ✅ Extracted — `data/formal/raw/sun_2024_full_text.txt` (65,448 chars, utf-8)
**Intake report**: `docs/r13_1_sun_paper_intake.md`

**Still needed (contact author or re-create)**:
```
- Austrian Income Tax Code text (Bundesgesetzblatt 1988/400 — public at RIS)
- Modality labels (4-class: definition/obligation/prohibition/permission)
- 150 annotated sentences (6-concept phrase-level, 443 ground-truth components)
- 12 BPMN process models (Austrian energy supplier smart meter)
- Rule base (parsed from smart meter regulatory documents)
- 4 GDPR BPMN models (GDPR Articles 1-50 privacy constraints)
- bert-legal-uncased pre-trained model (HuggingFace or author)
- Source code (not publicly available)
- Gold standard matching data
```

**Contact**: Dongjin Yu (yudj@hdu.edu.cn), Hangzhou Dianzi University
**Data availability**: "available from the corresponding author on reasonable request"
**Reconstruction plan**: `docs/r13_sun_reconstruction_plan.md`
**Missing assets**: `data/formal/metadata/sun_2024_missing_assets.md`

### DS002 — GDPR official text

```
- Full GDPR regulation text (2016/679) — EUR-Lex HTML or PDF
- Alternatively, a pre-cleaned .txt or .json version from a trusted source
- Source URL and download date for metadata record
```

### DS003 — Structured GDPR

```
- GDPR articles + recitals in .json or .jsonl format with article/recital numbering
- Source attribution and license file
```

### DS004 — Legal extraction datasets

```
- Dataset paper PDF
- Download link or contact author for data
- gold annotation file (.jsonl, .csv)
- train/dev/test split definitions if applicable
- License statement
```

### DS005 — BPMN compliance

```
- BPMN model files (.bpmn, .xml)
- Compliance rule annotations
- Gold mapping file (model element → rule clause)
```

### DS006 — Public GDPR annotations

```
- Annotation file (.jsonl or .csv)
- Annotation guidelines document
- Inter-annotator agreement report if available
- License / terms of use
```

## 5. Storage Rules

Once any data is downloaded (after separate Codex approval):

| Directory | What goes there |
|-----------|-----------------|
| `data/formal/raw/` | Original downloaded files — never modified |
| `data/formal/processed/` | Cleaned, sentence-split, ID-assigned `.jsonl` for model input |
| `data/formal/gold/` | Gold annotations, labels, answer keys |
| `data/formal/metadata/` | `sources.json` (source info), `CHANGELOG.md` (processing steps), license files |

**Never store in these directories:**
- API keys, tokens, cookies
- Account credentials
- Personal data not covered by the dataset license
- Unconfirmed-license proprietary data

## 6. Exclusion Rules

Exclude any dataset that:

- Has no identifiable license or the license prohibits research use.
- Includes personal data of EU/UK residents without GDPR-compliant consent.
- Requires a paid subscription or institutional access that the user does not have.
- Is a benchmark test-set whose labels are not publicly available (avoids leaderboard gaming).
- Contains real-case confidential legal advice or client-attorney information.

## 7. Open Questions

1. Does the Sun baseline paper have a public GitHub repository? (If yes, URL?)
2. What is the exact license of the Sun dataset?
3. Should we use the same subset of GDPR articles as Sun, or a different set?
4. Does the user have institutional access to any paid legal corpora?
5. Should inter-annotator agreement be computed on the formal dataset before any API call?
