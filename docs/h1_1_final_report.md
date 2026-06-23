# H1.1 — Final Report: PDF Risk and Temporary Script Cleanup

**H1_1_STATUS**: **PASSED**

**Commit audited**: a87ae2b (H1 audit)  
**Cleanup commit**: ffe2605  
**Cleanup timestamp**: 2026-06-23T21:30:00Z  

---

## 1. Status Report

| # | Item | Value |
|---|------|-------|
| 1 | Current path | `D:\Paper\experiment\bpc-hybrid` |
| 2 | `.env` read/searched | no |
| 3 | API/LLM called | no |
| 4 | Evaluator rerun | no |
| 5 | Predictions modified | no |
| 6 | Metrics modified | no |
| 7 | Tracked PDFs before | 2 (Barrientos 2026, Sun 2024) |
| 8 | Tracked PDFs after | 0 (removed with `git rm --cached`) |
| 9 | Scripts kept | `scripts/audit_h1_gold_mismatch.py` (renamed from final) |
| 10 | Scripts removed from tracking | 4 (`h1_gold_mismatch_audit.py`, `_v2.py`, `_v3.py`, `_final.py`) |
| 11 | Outputs tracking | R15 outputs NOT tracked (correct); R12 historical outputs still tracked |
| 12 | Memories tracking | NOT tracked (correct) |
| 13 | Raw tracking | Only `.gitkeep` and metadata files (correct) |
| 14 | Harness contract | PASS (19/19 checks) |
| 15 | Static scan | No positive overclaim patterns in experiment files |
| 16 | Modified files | 14 files changed |
| 17 | Commit hash | `ffe2605` |
| 18 | Push confirmation | ✅ Pushed to `origin/main` |
| 19 | Git status | Clean (only untracked local temp scripts) |

---

## 2. Changes Made

### Phase A — PDF Cleanup
- Removed 2 tracked PDFs with `git rm --cached` (local files preserved)
- Added `*.pdf` to `.gitignore`

### Phase B — Temp Script Cleanup
- Renamed `h1_gold_mismatch_audit_final.py` → `audit_h1_gold_mismatch.py`
- Removed 4 temp scripts from tracking with `git rm --cached`
- Local files preserved

### Phase C — Outputs/Memories Check
- R15 outputs NOT tracked (correct)
- R12 outputs are historical artifacts (left as-is)
- Memories NOT tracked (correct)

### Phase D — Verification
- py_compile: ✅ All scripts compile
- Formal results: ✅ Valid (sample_count=50)
- Harness contract: ✅ 19/19 PASS
- Static scan: ✅ No positive overclaim patterns
- Raw/env tracking: ✅ Correct

---

## 3. Claim Boundary

This stage does not change experimental evidence or metrics. It only reduces repository and audit risks.

| Assertion | Value |
|-----------|-------|
| benchmark | ❌ false |
| method_validation | ❌ false |
| exact_sun_reproduction | ❌ false |
| llm_superiority_claim | ❌ false |

---

## 4. Next Step Recommendation

Return to Codex or another independent audit agent for H1/H1.1 local-only audit before using GDPR-50 results in PPT.
