# Barrientos 2026 LLM Role

This document locks the role of the Barrientos et al. (2026) paper in this
experiment.

## Terminology

When this project says "the LLM paper", it means:

Barrientos, Winter, and Rinderle-Ma (2026), "Impact analysis of regulatory
requirement changes on business process compliance".

This is different from Winter et al. (2020), which is the textual compliance
assessment baseline compared by Sun.

## Main Rule

Sun is the main methodological backbone.

Barrientos 2026 is only an LLM-assistance reference. It must not replace Sun's
rule-record representation, Sun's Stage 2 extraction targets, or Sun's Stage 3
checking goal.

## What We Borrow From Barrientos

Allowed Barrientos-inspired ideas:

- LLM-based formalization from natural-language requirements into structured
  output.
- Detailed extraction instructions in the prompt.
- Strict JSON schema.
- Controlled vocabulary for allowed labels.
- Validation of every LLM output against the schema.
- Deterministic post-processing after validation.
- Normalization to reduce inconsistent representations.
- Traceability of what the LLM added or repaired.
- Future optional ideas for compliance deviation explanations and
  over-compliance analysis.

## Exact Schema Mapping

Barrientos/RC4PC does not directly extract Sun's six phrase concepts. Its
formalization contains a Boolean `precondition`, a list of `norms` with
`modality` and `action`, and `temporal_validity`. Each action is assigned to a
control-flow, data, resource, or time dimension and a controlled compliance
pattern.

### Critical: Modality Class Count Difference (verified 2026-07-12)

| Aspect | Barrientos (RC4PC) | Sun et al. (2024) / Our D1 |
|---|---|---|
| Modality classes | **3** | **4** |
| Enum | `obligation`, `permission`, `prohibition` | `obligation`, `prohibition`, `permission`, `definition` |
| `definition` class | ❌ absent | ✅ required (e.g., "X means...", "X refers to...") |

**Implication**: D1/H1 prompts MUST use the 4-class Sun enum, NOT the
3-class Barrientos enum. Direct copy-paste of Barrientos prompt loses the
`definition` class and breaks Sun-compatible narrative. Full audit in
`docs/research/BARRIENTOS_BORROWING_AUDIT_2026-07-12.md`.

The only allowed adaptation is explicit rather than implicit:

| Sun concept | Closest RC4PC construct | Required extension |
|---|---|---|
| modality | `norms[].modality` | source evidence span |
| actor | resource action / `resources` | separate participant from physical resource |
| action | `activities` | preserve the original verb phrase span |
| condition | `precondition` | preserve marker, scope, and source span |
| constraint | pattern plus data/time arguments | preserve the limiting source span |
| exception | no first-class equivalent | add an explicit exception field |

Consequently, the thesis must not state that Barrientos already provides a
method for extracting Sun's six elements. It provides prompt, schema,
normalization, and stability methodology that can be adapted to a Sun-compatible
output.

## What We Do Not Borrow

Not allowed:

- Replacing Sun's semantic concepts with the Barrientos/RC4PC schema.
- Turning the thesis into a regulatory requirement change-impact study.
- Making atomic change operations the main Stage 2 target.
- Using compliance deviation explanations as the primary evaluation objective.
- Calling the main method "Barrientos method".

## Formal Experiment Meaning

The formal method remains:

1. Run Sun or Sun-reconstructed Stage 2 extraction first.
2. If the rule extractor fails, misses required fields, has low confidence, or
   cannot be converted into a Stage 3 record, call the LLM.
3. The LLM output must be validated and normalized.
4. The final record must remain Sun-compatible.

The comparison variants are:

- `sun_rule_only`
- `sun_llm_fallback`
- `direct_llm`

The `sun_llm_fallback` and `direct_llm` variants may use
Barrientos-inspired prompting and validation discipline, but they must output
Sun-compatible fields.

## Legacy Naming Warning

Some old project files use names such as `sun_plus_winter` or
`winter_formalizer`. Those names are historical and misleading.

For formal reporting, treat them as legacy structured-LLM prototypes only. They
must be renamed, replaced, or clearly documented before final metrics are
reported.
