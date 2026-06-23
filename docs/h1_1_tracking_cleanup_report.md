# H1.1-C — Outputs/Memories Tracking Cleanup Report

**Phase**: H1.1-C  
**Commit**: a87ae2b (HEAD)  
**Cleanup timestamp**: 2026-06-23T21:30:00Z  

---

## 1. Tracking Status

| Path | Tracked? | Notes |
|------|----------|-------|
| `outputs/r12_*` | ✅ Yes | Pre-existing R12 experiment outputs (historical, not from R15) |
| `outputs/r15_*` | ❌ No | R15 outputs NOT tracked (correct) |
| `memories/` | ❌ No | NOT tracked (correct) |
| `*.tmp` | ❌ No | NOT tracked |
| `.pytest*` | ❌ No | NOT tracked |
| `__pycache__` | ❌ No | NOT tracked |

---

## 2. R12 Outputs Analysis

The tracked R12 outputs (`outputs/r12_1_synthetic_prototype_pilot/`, `outputs/r12_3_1_timeout_sanity/`) are historical artifacts from previous experiments. They were committed before the R15 GDPR-50 experiment and are part of the project history.

**Decision**: Leave R12 outputs tracked. They are historical artifacts, not from the current R15 experiment.

---

## 3. R15 Outputs Status

R15 outputs exist locally in `outputs/` but are NOT tracked. Formal copies exist in `data/formal/results/`:
- `r15_gdpr50_rule_plus_llm_summary.json` ✅
- `r15_gdpr50_spacy_enhanced_summary.json` ✅
- `r15_gdpr50_sun_style_summary.json` ✅
- `r15_gdpr50_three_way_comparison_summary.json` ✅

---

## 4. Verdict

**PASS** — R15 outputs NOT tracked (correct). R12 outputs are historical artifacts. Memories NOT tracked. No cleanup needed.
