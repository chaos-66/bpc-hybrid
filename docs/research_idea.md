# Research Idea: Rule-First LLM-Assisted Hybrid Framework for Design-Time Business Process Compliance Assessment

## 1. Overview

This research proposes a rule-first LLM-assisted hybrid framework for
design-time business process compliance assessment.

## 2. Core Principles

### 2.1 Sun-style Rule-template / Marker-based Extraction as Foundation

Sun et al. demonstrated that rule-template and marker-based regulatory
semantic extraction achieves high consistency, low cost, interpretability,
and deterministic traceability. This project retains Sun-style extraction
as the **primary path**.

### 2.2 LLM Structured Formalization as Controlled Fallback

LLMs are introduced as a controlled fallback for cases where rule-based
extraction struggles:
- Long / compound normative sentences
- Multi-clause sentences with multiple modalities
- Missing actor or action elements
- Representation inconsistency across different legal texts

Key LLM integration constraints:
- Controlled vocabulary to constrain output space
- Strict JSON schema enforcement
- Span normalization to reduce hallucination
- Deterministic post-processing

### 2.3 Six Extraction Fields

All extraction methods (rule-first and LLM-fallback) target six fields:

1. **modality** — obligation, permission, prohibition (shall / may / must not)
2. **actor** — the subject bound by the rule
3. **action** — the required, permitted, or prohibited activity
4. **condition** — triggering or qualifying conditions
5. **constraint** — temporal, spatial, or scope constraints
6. **exception** — exemptions and special cases

### 2.4 Future Multi-clause Schema

A planned multi-clause schema will allow compound regulatory sentences
with multiple modalities to be decomposed into individual normative
clauses, each carrying its own set of six fields.

## 3. Main Track and Generalization

- **Main track**: Sun-aligned GDPR + BPMN compliance assessment.
- **Optional generalization corpus**: EStG / Austrian Income Tax Act.
  This corpus may be used as an optional generalization test but must
  NOT replace or substitute the Sun dataset.

## 4. Current Stage Boundary

This is **R0 — Safe GitHub-backed Bootstrap**. The project currently:
- Contains NO real data.
- Contains NO code implementation.
- Contains NO benchmark results.
- Does NOT claim to surpass Sun or any prior work.
- Does NOT claim to have completed BPMN compliance checking.
- Does NOT claim to have completed over-compliance detection.

All later stages (R1+) require R0 GitHub push success first.
