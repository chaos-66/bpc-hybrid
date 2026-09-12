# s3_semantic_grounding_v1 (development-only)

Deterministic-first Stage 3 semantic-grounding repair over the frozen 40-variant + 40-control development panel.  Zero real API calls.

## Per-type binary structural checks (40 variants)

| Type | P | R | F1 |
|---|---|---|---|
| prohibited_action_present | 1.0000 | 1.0000 | 1.0000 |
| required_condition_not_enforced | 0.3600 | 0.9000 | 0.5143 |
| constraint_violated | 1.0000 | 0.2000 | 0.3333 |
| exception_not_handled | 0.6000 | 0.3000 | 0.4000 |

- Binary per-type Macro-F1: **0.5619**

## Unified variant decision (fixed structural-specificity priority)

| Type | P | R | F1 |
|---|---|---|---|
| prohibited_action_present | 1.0000 | 1.0000 | 1.0000 |
| required_condition_not_enforced | 0.4706 | 0.8000 | 0.5926 |
| constraint_violated | 1.0000 | 0.2000 | 0.3333 |
| exception_not_handled | 0.7500 | 0.3000 | 0.4286 |

- Unified 4-type Macro-F1: **0.5886**
- Micro-F1: **0.6301**
- Exact type accuracy: **0.5750**
- Unobservable: **7**

## Target-field diagnostic (each pair scored only on its mutated field)

| Type | P | R | F1 | Variant detected | Control target violations |
|---|---|---|---|---|---|
| prohibited_action_present | 1.0000 | 1.0000 | 1.0000 | 10/10 | 0 |
| required_condition_not_enforced | 0.9000 | 0.9000 | 0.9000 | 9/10 | 1 |
| constraint_violated | 1.0000 | 0.2000 | 0.3333 | 2/10 | 0 |
| exception_not_handled | 1.0000 | 0.3000 | 0.4615 | 3/10 | 0 |

- Target-field 4-type Macro-F1: **0.6737**
- Control target-field FP rate: **0.0250**

## Paired 80-object evaluation (unified single-label)

- 5-class accuracy: **0.3500**
- Variant exact accuracy: **0.5750**
- Control any-type false-positive rate: **0.5500**
- Paired accuracy: **0.1250**
- 4-type Macro-F1: **0.4752**
- 5-class Macro-F1: **0.4246**
- Unobservable total: **20**

## Input-identifiability audit

- Byte-identical variant-input collision groups: **7** covering **28** variants.
- A single-side method must make identical predictions inside a collision group; the unified single-label metrics are therefore structurally bounded. The per-type and target-field views are the valid type-level evidence.

## Baseline comparison (historical reference/winter)

- Historical unified variant Macro-F1: 0.4738
- Historical paired 5-class Macro-F1: 0.3900
- Historical paired accuracy: 0.2250
- Delta unified variant Macro-F1: +0.1148
- Delta paired 5-class Macro-F1: +0.0346
- Delta paired accuracy: -0.1000

## LLM semantic-grounding fallback

- Status: **IMPLEMENTED_NOT_REAL_RUN**
- Real API calls: **0**
- Fallback-eligible objects (deterministic ambiguity): **26**
- The fallback schema/validator/mock plumbing is implemented and tested offline. No real API authorization was present for this revision, so no fallback call was made and no LLM-improved metric is reported.

## Claim boundary

Development-only synthetic controlled panel; not formal Oracle and not human Gold. The four types are project extensions, not native Winter/Sun capabilities. The fallback is implemented and offline-validated but was not real-run.
