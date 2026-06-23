# H1-C — Sun-Method Alignment Audit

**Audit ID**: H1-SUN-ALIGN  
**Commit**: d7f83ff  
**Audit timestamp**: 2026-06-23T21:00:00Z  

---

## 1. Honesty Statement

> **This experiment is not exact Sun reproduction. This experiment is a local GDPR-50 semantic extraction study inspired by Sun-style concepts.**

---

## 2. Method Alignment Matrix

| Component | Sun Method | R15 Sun-Style | R15 spaCy | R15 Rule+LLM |
|-----------|-----------|---------------|-----------|---------------|
| BERT modality classifier | ✅ | ❌ | ❌ | ❌ |
| Syntactic parsing tree | ✅ | ❌ | ❌ | ❌ |
| Domain marker lexicon | ✅ | ❌ | ❌ | ❌ |
| Rule template extraction | ✅ | ✅ | ✅ | ✅ |
| BPMN matching | ✅ | ❌ | ❌ | ❌ |
| Violation detection | ✅ | ❌ | ❌ | ❌ |
| LLM fallback | — | ❌ | ❌ | ✅ (qwen3.7-max) |

---

## 3. Key Findings

### 3.1 What IS present

- **Rule template extraction**: All three variants use keyword-based rule templates to extract modality, actor, action, condition, constraint, exception from GDPR sentences.
- **LLM fallback**: The Rule+LLM variant uses qwen3.7-max (49 calls) to fill missing fields.
- **spaCy enhancement**: The spaCy variant uses dependency parsing and sentence splitting.

### 3.2 What is NOT present

- **BERT modality classifier**: No BERT model is used for modality classification.
- **Syntactic parsing tree**: No constituency or dependency parsing tree is used as a primary feature.
- **Domain marker lexicon**: No domain-specific marker lexicon is used.
- **BPMN matching**: No BPMN model matching is performed.
- **Violation detection**: No compliance violation detection is performed.

### 3.3 Dataset provenance

- **Original Sun dataset**: ❌ Not used
- **Dataset source**: Local GDPR-50 (50 sentences from GDPR Articles 5-50)
- **Label source**: Manually coded, not from Sun annotations

---

## 4. Verdict

**PASS_WITH_WARNINGS**

The experiment is inspired by Sun-style concepts but is NOT an exact Sun reproduction. Method names containing "sun_style" are potentially misleading. The recommended claim boundary prohibits "exact Sun reproduction" and "Sun method validated" claims.
