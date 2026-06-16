# bpc-hybrid

## Current Status

**R0 ✅ | R1 ✅ | R1.5 ✅ | R1.6 ✅ | R2 — Core Multi-Clause Schema**

## Research Positioning

`bpc-hybrid` is a **rule-first LLM-assisted hybrid framework** for design-time business process compliance assessment.

The framework keeps Sun-style rule-template / marker-based regulatory semantic extraction as the **primary path** because it provides consistency, low cost, interpretability, and deterministic traceability. LLMs are planned only as a **controlled fallback** for cases such as multi-modality, missing actor/action, parser failure, or low-confidence matching.

LLM outputs must be constrained by strict JSON schemas and then processed through span normalization and deterministic post-processing to reduce hallucination and representation inconsistency.

A planned **multi-clause schema** will allow compound regulatory sentences with multiple modalities to be decomposed into individual normative clauses, each carrying its own modality, actor, action, condition, constraint, and exception.

## Important Declarations

- ⚠️ This is NOT a formal benchmark.
- ⚠️ No GDPR / BPMN / Sun dataset data is fabricated or included.
- ⚠️ Only a successful GitHub push marks the completion of a stage.
- ⚠️ No claims about surpassing Sun or any prior work are made.
- ⚠️ The current repository is a runnable MVP skeleton, not a validated system.

## R0 Artifacts

| File | Description |
|------|-------------|
| `.gitignore` | Git ignore rules for Python, secrets, outputs, OS/IDE files |
| `README.md` | Project overview and current status (this file) |
| `docs/research_idea.md` | Research concept and methodology outline |
| `docs/experiment_log.md` | Experiment progress log |
| `docs/safety_rules.md` | Safety constraints for this project |

## Current Stage

- R0 ✅: Safe GitHub-backed bootstrap completed.
- R1 ✅: Minimal Python project scaffold completed.
- R1.5 ✅: Research framing integrated into project documentation.
- R1.6 ✅: Codex local-only audit report persisted.
- R2: Core multi-clause schema implemented.

## R2 Scope

R2 implements the core schema objects for multi-clause regulatory extraction:

- `FieldSpan`
- `ClauseExtraction`
- `MultiClauseExtractionResponse`

The schema supports object-or-null fields for modality, actor, action, condition, constraint, and exception, with span offsets and confidence scores. Schema validation is enforced via `SchemaValidationError`.

R2 does not implement rule extraction, multi-clause splitting, LLM fallback, evaluation, BPMN checking, real datasets, or benchmark results.

## Dataset and Claim Boundary

The future formal evaluation target is a **Sun-aligned GDPR + BPMN dataset**, compared against Sun-style rule baseline and Winter-style textual baseline on precision / recall / F1 / AP / MAP.

**EStG / Austrian Income Tax Act** may only be used later as an optional generalization corpus and cannot replace the Sun-aligned main benchmark.

This project currently does **not** claim to outperform Sun-style baselines, Winter-style textual baselines, or any LLM baseline. Synthetic prototype data, if introduced later, is used for pipeline sanity checks only — not for benchmark claims.

## Next Stage

R3 will only proceed after R2 push is confirmed successful and user authorization is granted.
