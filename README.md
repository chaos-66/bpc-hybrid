# bpc-hybrid

## Current Status

**R0 — Safe GitHub-backed Bootstrap**
Current stage: R0 in progress — pending commit and GitHub push.

## Research Positioning

pc-hybrid is a **rule-first LLM-assisted hybrid framework** for
design-time business process compliance assessment.

The framework keeps Sun-style rule-template / marker-based regulatory
semantic extraction as the **primary path** because it provides
consistency, low cost, interpretability, and deterministic traceability.
LLMs are planned only as a **controlled fallback** for cases such as
multi-modality, missing actor/action, parser failure, or low-confidence
matching.

LLM outputs must be constrained by strict JSON schemas and then processed
through span normalization and deterministic post-processing to reduce
hallucination and representation inconsistency.

## Important Declarations

- This is NOT a formal benchmark.
- No GDPR / BPMN / Sun dataset data is fabricated or included.
- Only a successful GitHub push marks the completion of a stage.
- No claims about surpassing Sun or any prior work are made.
- The current repository is a bootstrap skeleton, not a validated system.
- R1 will only proceed after R0 GitHub push succeeds.

## R0 Artifacts

| File | Description |
|------|-------------|
| .gitignore | Git ignore rules for Python, secrets, outputs, OS/IDE files |
| README.md | Project overview and current status (this file) |
| docs/research_idea.md | Research concept and methodology outline |
| docs/experiment_log.md | Experiment progress log |
| docs/safety_rules.md | Safety constraints for this project |

## Stage Flow

R0 is the mandatory bootstrap. No later stage (R1+) may begin until R0
completes: commit + GitHub push succeeds. This constraint is enforced
by the safety rules recorded in docs/safety_rules.md.
