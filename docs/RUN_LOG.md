# Agent Run Log

## Current Run

Start time: 2026-06-23T00:00:00Z  
Agent/model: GitHub Copilot  
Main objective: Read Sun and Barrientos PDFs, update method alignment, and proceed with experiment pipeline  

---

## Entries

### Entry 001

- Time: 2026-06-23T00:05:00Z
- Phase: PDF Intake
- Action: Extracted text from Barrientos PDF to `data/formal/raw/barrientos_2026_full_text.txt`
- Files changed: `data/formal/raw/barrientos_2026_full_text.txt`
- Commands run: `pip install pdfplumber`, pdfplumber extraction script
- Result: Extracted 107654 characters
- Next action: Update RUN_LOG with PDF intake entry

### Entry 002

- Time: 2026-06-23T00:10:00Z
- Phase: Method Alignment
- Action: Reading Sun and Barrientos papers to update METHOD_ALIGNMENT.md
- Files changed: None yet
- Commands run: None
- Result: In progress
- Next action: Extract key method details from Sun paper Section 4.2

### Entry 003

- Time: 2026-06-23T00:15:00Z
- Phase: Method Alignment
- Action: Updated METHOD_ALIGNMENT.md with Sun paper method details and current implementation status
- Files changed: `docs/METHOD_ALIGNMENT.md`
- Commands run: None
- Result: Table filled with 12 components; conclusion: partially aligned
- Next action: Check GDPR dataset for expansion

### Entry 004

- Time: 2026-06-23T00:20:00Z
- Phase: Dataset Construction
- Action: Started building 50-sample GDPR dataset per user's four-step plan
- Files changed: None yet
- Commands run: Checked GDPR PDF extractability (88 pages, text extractable)
- Result: GDPR PDF can be extracted with pdfplumber
- Next action: Install spaCy and extract sentences from GDPR

### Entry 005

- Time: 2026-06-23T00:30:00Z
- Phase: Dataset Construction
- Action: Built 50-sample GDPR dataset with auto-annotations
- Files changed: `scripts/build_gdpr_50_dataset.py`, `data/formal/r15_gdpr50/r15_gdpr50_candidate_samples.jsonl`, `data/formal/r15_gdpr50/r15_gdpr50_gold.jsonl`
- Commands run: `python scripts/build_gdpr_50_dataset.py`
- Result: 50 samples (35 obligation, 12 permission, 3 prohibition)
- Next action: Run Sun-style baseline on GDPR-50

### Entry 006

- Time: 2026-06-23T00:35:00Z
- Phase: Baseline Evaluation
- Action: Ran Sun-style rule-only baseline on GDPR-50 dataset
- Files changed: `scripts/run_r15_gdpr50_sun_style.py`, `data/formal/predictions/r15_gdpr50_sun_style_predictions.jsonl`
- Commands run: `python scripts/run_r15_gdpr50_sun_style.py`, `python scripts/evaluate_r14_field_metrics.py`
- Result: strict_f1=0.2706, lenient_f1=0.4456
- Next action: Build spaCy-enhanced extractor

### Entry 007

- Time: 2026-06-23T00:40:00Z
- Phase: Baseline Enhancement
- Action: Built spaCy-enhanced Sun-style extractor with dependency parsing
- Files changed: `src/bpc_hybrid/sun_style/spacy_syntactic_rules.py`, `src/bpc_hybrid/sun_style/spacy_semantic_extractor.py`, `scripts/run_r15_gdpr50_spacy_enhanced.py`
- Commands run: `python scripts/run_r15_gdpr50_spacy_enhanced.py`
- Result: strict_f1=0.2827, lenient_f1=0.3787 (slightly better strict F1)
- Next action: Add LLM fallback mechanism

### Entry 008

- Time: 2026-06-23T01:10:00Z
- Phase: Hybrid Extraction
- Action: Ran Rule + LLM fallback extraction on GDPR-50 dataset
- Files changed: scripts/run_r15_gdpr50_rule_plus_llm.py
- Commands run: python scripts/run_r15_gdpr50_rule_plus_llm.py
- Result: 50/50 samples, 49 LLM calls, 0 errors, 1599.9s total
- Non-empty fields: modality=50, actor=49, action=50, condition=36, constraint=43, exception=7
- Next action: Run comparative evaluation

### Entry 009

- Time: 2026-06-23T01:15:00Z
- Phase: Comparative Evaluation
- Action: Three-way comparison (Sun-style vs spaCy-enhanced vs Rule+LLM)
- Files changed: scripts/compare_three_variants.py, outputs/r15_gdpr50_rule_plus_llm_summary.json
- Commands run: python scripts/compare_three_variants.py
- Result: 
  - Best Strict F1: spaCy-enhanced (0.2827) > Sun-style (0.2706) > Rule+LLM (0.2675)
  - Best Lenient F1: Sun-style (0.4456) > spaCy-enhanced (0.3787) > Rule+LLM (0.3779)
  - Best Exact Accuracy: Rule+LLM (0.2669) > spaCy-enhanced (0.2598) > Sun-style (0.2464)
  - Best Macro Strict F1: Rule+LLM (0.2132) > spaCy-enhanced (0.1924) > Sun-style (0.1866)
  - Rule+LLM showed higher non-empty field coverage in this local GDPR-50 run, but uses longer phrasing vs gold annotations
  - In this local run, LLM-assisted modality extraction reached 100% non-empty coverage; rule-based baseline reached 92.5%
- Next action: Document findings, commit changes

### Entry 010

- Phase: H1.1 Cleanup
- Action: Cleaned tracked PDF/copyright risk and temporary script pollution after H1 self-audit
- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction modification: no
- Result metric modification: no
- .env content read/search: no
- Result: pending verification
