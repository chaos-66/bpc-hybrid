# R13.2 Public-source Collection Plan

## 1. Objective

Define the complete list of publicly accessible or author-requestable sources needed to
reconstruct a **paper-aligned mini dataset** for `bpc-hybrid`. This plan translates the
R13.1 Sun paper intake and R13 missing-assets inventory into actionable user-collection
items with clear provenance, license, and risk tracking.

## 2. Current Accepted State

| Item | Status |
|------|--------|
| R13.1 Sun paper intake | accepted (PAPER_ONLY, commit `0504e2c`) |
| Original Sun source code | missing / not available |
| Original complete Sun datasets | missing (all require author contact) |
| Exact Sun reproduction claim | forbidden |
| Benchmark / method-validation claim | forbidden |
| Project may proceed to public-source collection | yes |

## 3. Source Categories

| Category | ID Prefix | Description |
|----------|-----------|-------------|
| A. GDPR official legal text | `gdpr_eurlex` | Regulation (EU) 2016/679 from EUR-Lex |
| B. Austrian Income Tax Code | `austrian_income_tax_code` | Modality classification source clue |
| C. Michel et al. 2022 | `michel_2022_decision_rules` | Decision-rule/modality dataset clue |
| D. Agostinelli et al. GDPR BPMN | `agostinelli_2019_gdpr_bpmn` | GDPR BPMN process-model source clue |
| E. Böhmer / Austrian energy supplier | `bohmer_2016_energy_supplier` | Energy supplier process-model source clue |
| F. Winter et al. keyword baseline | `winter_2020_keyword_baseline` | Keyword baseline source clue |
| G. Manual mini-gold annotation | `manual_mini_gold` | Annotation created by this project |

## 4. Priority Collection List

### P0 — Must Collect Before R13.3

| source_id | name | purpose | expected_files | target_raw_folder | license_status | risk_level |
|-----------|------|---------|---------------|-------------------|----------------|------------|
| `gdpr_eurlex` | GDPR Regulation (EU) 2016/679 | Primary regulatory text for Articles 1-50 | official HTML/PDF, `source_url.txt`, `license_or_source_note.txt` | `data/formal/raw/gdpr_eurlex/` | EU open | low |
| `austrian_income_tax_code` | Austrian Income Tax Code (BGBl 1988/400) | Modality classification source (Sun DS001) | RIS HTML/PDF, `source_url.txt`, `license_or_source_note.txt` | `data/formal/raw/austrian_income_tax_code/` | public domain assumed | low |

### P1 — Strongly Recommended

| source_id | name | purpose | expected_files | target_raw_folder | license_status | risk_level |
|-----------|------|---------|---------------|-------------------|----------------|------------|
| `agostinelli_2019_gdpr_bpmn` | Agostinelli et al. GDPR BPMN models | Process-model source (Sun ref [35]) | paper PDF, supplementary BPMN files if available, `source_url.txt`, `license_or_source_note.txt` | `data/formal/raw/agostinelli_2019_gdpr_bpmn/` | author_request | medium |
| `bohmer_2016_energy_supplier` | Böhmer et al. energy supplier BPMN | Process-model source (Sun ref [33]) | paper PDF, supplementary BPMN files if available, `source_url.txt`, `license_or_source_note.txt` | `data/formal/raw/bohmer_2016_energy_supplier/` | author_request | medium |
| `winter_2020_keyword_baseline` | Winter et al. 2020 keyword baseline | Baseline comparison source | paper PDF, code/supplementary if available, `source_url.txt`, `license_or_source_note.txt` | `data/formal/raw/winter_2020_keyword_baseline/` | unknown | high |

### P2 — Nice to Have

| source_id | name | purpose | expected_files | target_raw_folder | license_status | risk_level |
|-----------|------|---------|---------------|-------------------|----------------|------------|
| `michel_2022_decision_rules` | Michel et al. 2022 decision-rule dataset | Modality/decision-rule dataset clue | paper PDF, dataset if available, `source_url.txt`, `license_or_source_note.txt` | `data/formal/raw/michel_2022_decision_rules/` | author_request | high |
| `manual_mini_gold` | Manual mini-gold annotation | Gold annotation by this project | annotation CSV/JSONL created locally, `annotation_notes.md` | `data/formal/gold/manual_mini/` | project_own | low |

## 5. Required Files Per Source

For every collected source, the user must provide:

1. **Source content** — The actual text, PDF, model file, or dataset.
2. **`source_url.txt`** — One line containing the exact URL or DOI where the source was obtained.
3. **`license_or_source_note.txt`** — License statement, terms of use, or a note explaining why the license is unknown/unclear.
4. **`README.md`** (optional but recommended) — Brief description of what this source contains and how it was obtained.

## 6. Storage Layout

```
data/formal/raw/
├── .gitkeep
├── sun_2024_design_time_bpc_multigranularity.pdf    (local only, NOT tracked)
├── sun_2024_full_text.txt                            (local only, NOT tracked)
├── gdpr_eurlex/
│   ├── .gitkeep
│   ├── regulation_2016_679.html|pdf                  (local only, NOT tracked)
│   ├── source_url.txt                                (tracked)
│   └── license_or_source_note.txt                    (tracked)
├── austrian_income_tax_code/
│   ├── .gitkeep
│   ├── bgbl_1988_400.html|pdf                        (local only, NOT tracked)
│   ├── source_url.txt                                (tracked)
│   └── license_or_source_note.txt                    (tracked)
├── agostinelli_2019_gdpr_bpmn/
│   ├── .gitkeep
│   ├── ...                                           (local only, NOT tracked)
│   ├── source_url.txt                                (tracked)
│   └── license_or_source_note.txt                    (tracked)
├── bohmer_2016_energy_supplier/
│   ├── .gitkeep
│   ├── ...                                           (local only, NOT tracked)
│   ├── source_url.txt                                (tracked)
│   └── license_or_source_note.txt                    (tracked)
├── winter_2020_keyword_baseline/
│   ├── .gitkeep
│   ├── ...                                           (local only, NOT tracked)
│   ├── source_url.txt                                (tracked)
│   └── license_or_source_note.txt                    (tracked)
└── michel_2022_decision_rules/
    ├── .gitkeep
    ├── ...                                           (local only, NOT tracked)
    ├── source_url.txt                                (tracked)
    └── license_or_source_note.txt                    (tracked)

data/formal/gold/
└── manual_mini/
    ├── .gitkeep
    ├── gold_samples.jsonl                            (tracked)
    └── annotation_notes.md                           (tracked)
```

**Rule**: Source content files (PDF, HTML, full text, model files) are kept **locally only**
and NOT tracked by git. Only `source_url.txt`, `license_or_source_note.txt`, and `README.md`
metadata are committed. This follows the same policy as the Sun PDF/full-text exclusion in
`.gitignore`.

## 7. License and Provenance Rules

1. **Every source must have a recorded URL or DOI.**
2. **Every source must have a license statement** — even if that statement is "unknown, awaiting author response".
3. **No source may be committed to git** if its redistribution rights are unclear.
4. **EU official documents** (GDPR EUR-Lex, Austrian BGBl) are generally public domain and may be committed as derived plaintext excerpts with proper attribution.
5. **Academic paper PDFs** follow the Sun PDF policy: local only, not tracked.
6. **Project-created annotations** (`manual_mini_gold`) are project IP and may be fully committed.

## 8. Exclusion Rules

The following MUST NOT be collected or used:

- Paywalled datasets or benchmark test sets with hidden labels.
- Leaderboard-locked evaluation data.
- Data with explicitly forbidden redistribution.
- Data obtained through unauthorized crawling or scraping.
- Any dataset that requires accepting terms that conflict with open academic publication.

## 9. User Download Checklist

- [ ] **P0-1**: Download GDPR EUR-Lex text (Articles 1-50 + recitals)
- [ ] **P0-2**: Download Austrian Income Tax Code from RIS
- [ ] **P1-1**: Locate Agostinelli et al. 2019 GDPR BPMN paper/models
- [ ] **P1-2**: Locate Böhmer et al. 2016 energy supplier BPMN paper/models
- [ ] **P1-3**: Locate Winter et al. 2020 keyword baseline paper/code
- [ ] **P2-1**: Locate Michel et al. 2022 decision-rule dataset
- [ ] **P2-2**: Prepare manual mini-gold annotation workspace
- [ ] For each: create `source_url.txt` and `license_or_source_note.txt`
- [ ] Place raw files in correct `data/formal/raw/<source_id>/` folders
- [ ] Do NOT `git add` any PDF, HTML, or large data files

## 10. R13.3 Readiness Criteria

R13.3 (data intake) may begin when:

1. ✅ P0 sources (GDPR EUR-Lex + Austrian Income Tax Code) are collected.
2. ✅ `source_url.txt` and `license_or_source_note.txt` exist for each collected source.
3. ✅ All collected sources are placed in correct folder structure.
4. ✅ No raw source files are tracked by git.
5. ✅ User confirms collection is complete and consents to proceed.

## 11. Claim Boundary

- This is a **public-source collection plan**, not a dataset.
- No data has been downloaded yet.
- No original Sun code or complete Sun datasets are available.
- No benchmark, method-validation, or formal-result claim is made.
- The mini dataset to be built from these sources is for **pipeline sanity and paper-aligned reconstruction only**.
