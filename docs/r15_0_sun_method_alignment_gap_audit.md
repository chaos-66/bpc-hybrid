# R15.0 — Sun-method Alignment Gap Audit

**Date:** 2026-06-23  
**Type:** Method comparison audit  
**Purpose:** Compare current `bpc-hybrid` implementation against Sun et al. (2024) method and identify gaps.

---

## Executive Summary

**R14.2 lightweight rule-only baseline is not equivalent to Sun's full method.**

The current project's R14.2 baseline used a minimal regex/marker-based extractor with only 5 modality markers and 4 constraint markers. Sun et al.'s method includes:
- A pre-trained/fine-tuned BERT classifier for modality
- Syntactic parsing trees (constituency + dependency)
- A domain-marked lexicon with systematic marker categories
- Self-defined extraction rule templates based on parse tree patterns
- BPMN process model semantic disassembly
- Violation detection (missing action, incorrect actor, out-of-order execution)

This audit identifies all gaps and proposes local fixes where possible.

---

## 1. Modality Classification

### Sun Method
Pre-trained/fine-tuned BERT + classification layer + softmax, classifying into: obligation, prohibition, permission, definition.

### Current Status
R14.2 used regex marker priority list (`_MODALITY_SPECS`) with only 6 patterns: `no person shall`, `shall not`, `must not`, `shall`, `must`, `may`. No "definition" classification, no ML model.

### Gap
**Severity: MAJOR** — No BERT classifier available. No `transformers`, `torch`, or cached model.

### Fix
Implement Sun-style classifier interface (`ModalityClassifier`) with deterministic fallback using extended marker lexicon + pattern rules. Mark as "interface-compatible fallback" explicitly.

### Local feasibility
Can fix without download: YES. Will fix: YES.

---

## 2. Syntactic Parsing Tree

### Sun Method
Constituency parsing tree + dependency parsing for rule-template extraction.

### Current Status
None. No spaCy, stanza, benepar, nltk, or any parser installed.

### Gap
**Severity: BLOCKING_FOR_EXACT_REPRODUCTION** — No parser available, cannot install.

### Fix
Implement marker-span and dependency-like heuristic approximations:
- Use marker word position + surrounding text window
- Implement span-based rules mimicking Sun's tree patterns
- Document as "approximated; constituency parsing unavailable"

### Local feasibility
Can fix without download: YES (approximation only). Will fix: YES.

---

## 3. Dependency Parsing

### Sun Method
Dependency relations used for actor (subject dependency) and condition extraction.

### Current Status
None. No dependency parser available.

### Gap
**Severity: MAJOR** — No dependency parser.

### Fix
Implement subject-like heuristic: first NP before modality marker in clause. Use marker proximity and word-position patterns.

### Local feasibility
Can fix without download: YES (heuristic approximation). Will fix: YES.

---

## 4. Domain-marked Lexicon

### Sun Method
Systematic marker lexicon covering modality, condition, constraint, exception, and actor markers.

### Current Status
R14.2 had only 6 modality markers and 4 constraint markers. No actor markers, no condition markers, no exception markers.

### Gap
**Severity: MINOR (fixable)** — Marker lexicon can be expanded with stdlib only.

### Fix
Create comprehensive marker lexicon (`data/formal/metadata/r15_0_sun_style_marker_lexicon.json`) with:
- Modality markers: shall, must, may, should, is required to, is prohibited from, must not, shall not, may not
- Condition markers: if, when, where, in case of, provided that, once, after, before, unless
- Constraint markers: within, at least, no later than, without undue delay, for the purpose of, only, minimum, maximum, prior to
- Exception markers: unless, except, except where, except if, notwithstanding, other than, save where
- Actor markers: controller, processor, data subject, supervisory authority, company, provider, physician, officer, authority, court, prosecutor, driver, inspector, customer, phone company

### Local feasibility
Can fix without download: YES. Will fix: YES.

---

## 5. Semantic Concept Extraction Rules

### Sun Method
Self-defined extraction rules based on parse tree patterns:
- condition: SBAR << condition marker; PP << condition marker
- constraint: NP < constraint marker; PP < IN constraint marker
- exception: SBAR/PP/NP with exception marker
- actor: subject dependency + NP containing actor marker
- action: VP after removing modality/condition/constraint/exception spans

### Current Status
R14.2 had very basic extraction: modality marker finding, simple actor extraction, and minimal action extraction from after-modality text. No systematic rule templates.

### Gap
**Severity: MAJOR** — Rules are not Sun-style tree patterns.

### Fix
Implement span-based rule templates that approximate Sun's tree patterns:
- Use marker positions as anchors
- Apply span-level rules (marker + following clause, marker + preceding NP)
- Remove extracted spans from action computation
- Map to Sun's SBAR/PP/NP/VP concepts descriptively

### Local feasibility
Can fix without download: YES. Will fix: YES.

---

## 6. Rule Record Construction

### Sun Method
Structured rule record with six semantic fields for each extracted normative statement.

### Current Status
R14.2 produces `ClauseExtraction` with six fields, but without systematic rule-template provenance.

### Gap
**Severity: MINOR** — Output structure exists but not Sun-style.

### Fix
Add `sun_alignment` metadata block to each extraction, tracking:
- bert_modality status
- syntactic_tree_rules status  
- domain_marker_lexicon usage
- rule_template_extraction provenance

### Local feasibility
Can fix without download: YES. Will fix: YES.

---

## 7. BPMN Process Model Disassembly

### Sun Method
Parse BPMN XML to extract: activity, event, gateway, actor/resource, control flow, label action/object semantics.

### Current Status
No BPMN parser in current project.

### Gap
**Severity: MAJOR** — No BPMN parser. No original Sun BPMN data.

### Fix
Implement BPMN XML parser using `xml.etree.ElementTree` (stdlib):
- Parse activities, events, gateways
- Extract sequence flows
- Parse lane-based actor/resource assignments
- Extract label action/object from task names
- Create minimal BPMN fixture files for testing

### Local feasibility
Can fix without download: YES. Will fix: YES (scaffold + fixtures only).

---

## 8. Matching Score

### Sun Method
Compute similarity between extracted rule records and BPMN process semantic records.

### Current Status
Not implemented.

### Gap
**Severity: MAJOR** — No matching score.

### Fix
Implement field-level Jaccard-based matching score between rule record and process semantic record.

### Local feasibility
Can fix without download: YES. Will fix: YES.

---

## 9. Missing Action Detection

### Sun Method
Detect when a rule's required action has no corresponding BPMN activity.

### Current Status
Not implemented.

### Gap
**Severity: MAJOR** — No violation detection.

### Fix
Implement missing action detector: compare extracted action against BPMN activity labels using Jaccard similarity threshold.

### Local feasibility
Can fix without download: YES. Will fix: YES.

---

## 10. Incorrect Actor Detection

### Sun Method
Detect when a rule's actor does not match the BPMN lane/resource.

### Current Status
Not implemented.

### Gap
**Severity: MAJOR** — No violation detection.

### Fix
Implement incorrect actor detector: compare extracted actor against BPMN lane assignments using token overlap.

### Local feasibility
Can fix without download: YES. Will fix: YES.

---

## 11. Out-of-Order Execution Detection

### Sun Method
Detect when BPMN sequence flow order contradicts rule constraint ordering.

### Current Status
Not implemented.

### Gap
**Severity: MAJOR** — No violation detection.

### Fix
Implement out-of-order detector: compare constraint-implied ordering against BPMN sequence flow ordering.

### Local feasibility
Can fix without download: YES. Will fix: YES.

---

## 12. Evaluation Dataset Equivalence

### Sun Method
Evaluated on original GDPR BPMN models with annotated compliance rules.

### Current Status
R14.1 mini-gold is 24 draft samples from publicly available regulatory texts. Not Sun's original datasets.

### Gap
**Severity: BLOCKING_FOR_EXACT_REPRODUCTION** — Original Sun datasets not available.

### Fix
Cannot fix. Document as permanent gap. Use R14.1 24 samples as local test set only.

### Local feasibility
Can fix without download: NO. Will fix: NO.

---

## 13. Metric Equivalence

### Sun Method
Sun uses accuracy/precision/recall/F1 on compliance checking outcomes.

### Current Status
R14 evaluator uses field-level exact/partial/wrong/missing/NA with Jaccard thresholds.

### Gap
**Severity: MINOR** — Different metrics but field-level evaluation is more granular.

### Fix
Keep existing evaluator. Not a blocking gap for descriptive comparison.

### Local feasibility
Can fix without download: N/A. Will fix: NO.

---

## Summary

| Sun Component | Status | Gap Severity | Fixable Locally | Fix in R15 |
|---|---|---|---|---|
| BERT modality classifier | missing | major | YES (fallback) | YES |
| Constituency parsing tree | missing | blocking | NO (approximation) | YES |
| Dependency parsing | missing | major | NO (approximation) | YES |
| Domain-marked lexicon | partial | minor | YES | YES |
| Semantic extraction rules | different | major | YES | YES |
| Rule record construction | partial | minor | YES | YES |
| BPMN process model disassembly | missing | major | YES (scaffold) | YES |
| Matching score | missing | major | YES | YES |
| Missing action detection | missing | major | YES | YES |
| Incorrect actor detection | missing | major | YES | YES |
| Out-of-order execution detection | missing | major | YES | YES |
| Evaluation dataset equivalence | different | blocking | NO | NO |
| Metric equivalence | different | minor | N/A | NO |

---

## Claim Boundary

R14.2 lightweight rule-only baseline is **not equivalent** to Sun's full no-LLM method. R15.0 implements a more Sun-aligned local rule-template pipeline but does not constitute exact Sun reproduction because:
1. Original Sun BERT model/weights not available
2. Original Sun training data not available
3. Original Sun full marker lexicon not available (Sun may have domain-specific extensions)
4. Original Sun BPMN evaluation data not available
5. Original Sun constituency/dependency parser not available locally
6. Sun's original implementation is not publicly released

R15.0 is a **best-effort local Sun-style approximation** using deterministic fallbacks and stdlib-only implementation.
