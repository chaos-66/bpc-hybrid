# Research Idea: Rule-First LLM-Assisted Hybrid Framework for Design-Time Business Process Compliance Assessment

## Overview

This research proposes a **rule-first LLM-assisted hybrid framework** for design-time business process compliance assessment.

## Core Components

### 1. Rule-Based Foundation (Sun-style)
- Rule-template / marker-based regulatory semantic extraction serves as the foundation
- Retains high consistency, low cost, and interpretability of rule-based methods

### 2. LLM-Assisted Layer
- Structured formalization via LLM
- Controlled vocabulary for regulatory concepts
- Strict JSON schema output for downstream processing
- Normalization of regulatory text representations

### 3. Target Problems
- Long and complex regulatory sentences
- Multi-normative sub-clauses
- Missing regulatory elements
- Representational inconsistency across regulation sources

## Extraction Fields (Six Categories)

The framework targets extraction of six regulatory element types:

1. **Modality** — obligation, permission, prohibition
2. **Actor** — the subject bound by the rule
3. **Action** — the required/permitted/prohibited activity
4. **Condition** — triggering or qualifying conditions
5. **Constraint** — temporal, spatial, or scope constraints
6. **Exception** — exemptions and special cases

## Future Directions

- Introduction of **multi-clause schema** for compound regulatory statements
- Main evaluation track: **Sun-aligned GDPR + BPMN**
- **EStG / Austrian Income Tax Act** may be used as an optional generalization corpus only — it does NOT replace the Sun dataset

## Current Phase Status

- **Current phase**: R0 — Safe GitHub-backed Bootstrap
- **No real data** is included at this stage
- **No benchmark results** are claimed
- **No BPMN compliance checking** has been completed
- **No over-compliance detection** has been implemented
- This project is rebuilding a runnable MVP from a clean, safe foundation
