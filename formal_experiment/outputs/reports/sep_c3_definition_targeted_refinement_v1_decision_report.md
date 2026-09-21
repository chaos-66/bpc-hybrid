# SEP-C3 Definition Targeted Refinement - Decision Report

- Suite: `SEP-C3-DEFINITION-TARGETED-REFINEMENT-001`
- Execution: BASE=42 calls, R_DEF=42 calls, historical A read-only; total new calls=84.
- Post-processing: live runner completed all sends, then aborted inside the full-150 evaluator membership check; recovered without any additional API calls using the same raw responses, parser, canonicalizer, and frozen underlying evaluators on the 42-sample panel slice.
- Transport/provider failures: 0. Retry protocol: retry=0, unchanged.

Key targeted numbers (45 unique clauses: 25 definition, 20 non-definition):

| Arm | Modality acc. | Def P | Def R | Def F1 | Def->Obl | Obl->Def | Proh->Def | Perm->Def | Def action present | Empty actions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 0.4667 | 1.0000 | 0.1600 | 0.2759 | 15 | 0 | 0 | 0 | 20/25 | 5 |
| BASE | 0.5111 | 1.0000 | 0.3600 | 0.5294 | 7 | 0 | 0 | 0 | 22/25 | 3 |
| R_DEF | 0.7333 | 0.9500 | 0.7600 | 0.8444 | 2 | 1 | 0 | 0 | 22/25 | 3 |

## 1. Did A -> BASE support the hypothesis that the E4 Prompt-Gold conflict was harmful?

Directionally yes, but the support is modest rather than decisive.

- Modality accuracy: 0.4667 -> 0.5111.
- Definition recall: 0.1600 -> 0.3600; definition F1: 0.2759 -> 0.5294.
- Definition -> obligation count: 15 -> 7.
- Obligation/prohibition/permission -> definition counts: A=0/0/0, BASE=0/0/0.
- Definition action presence: 20/25 -> 22/25; empty actions 5 -> 3.
- Corrected relative to A: 6; regressed relative to A: 4. The regressions include 2 canonical-validation failures and 2 alignment/no-overlap cases.

Interpretation: replacing the conflicting E4 example moved the targeted definition failures in the expected direction, but it did not fix the bulk of them.

## 2. Did BASE -> R_DEF provide additional benefit?

Yes. The explicit R_DEF guidance produced a large additional targeted benefit after E4 replacement.

- Definition recall: 0.3600 -> 0.7600; definition F1: 0.5294 -> 0.8444.
- Definition -> obligation reduction: 7 -> 2.
- Definition action presence: 22/25 -> 22/25 (unchanged overall; 3 gained and 3 lost, the losses being R_DEF canonical-validation failures).
- Non-definition shall (slice B) false-definition rate: 0.0000 -> 0.0000 (no increase).
- Corrected relative to BASE: 12; regressed relative to BASE: 2. Both regressions are R_DEF validation failures on estg_000716 c1/c2.

Interpretation: R_DEF substantially improves definition detection and reduces definition->obligation confusion, without turning the B non-definition shall controls into definitions.

## 3. What regressions or side effects occurred?

- B non-definition shall control modality accuracy fell 0.8000 -> 0.7333, driven by missing/validation-failed controls rather than false definitions.
- All non-definition false-definition rate rose 0.0000 -> 0.0500: one apply/applies case (estg_000306 c1, Gold obligation) was labeled definition by R_DEF. This is descriptive; no lexical apply=>definition rule was introduced.
- Secondary frozen coarse panel-slice mean five-field F1: A=0.6697, BASE=0.6876, R_DEF=0.6617. R_DEF is lower than BASE on this secondary span-field diagnostic, especially actor F1.
- Parse validity: BASE 42/42 and R_DEF 42/42 parsed successfully; input binding 42/42 both.
- Canonical schema validity: BASE 38/42 passed (4 failed), R_DEF 37/42 passed (5 failed). All failures are canonical-validation failures, not transport or JSON-parse failures. BASE failures: estg_000075, estg_000417, estg_000635, estg_000854. R_DEF failures: estg_000218, estg_000509, estg_000635, estg_000716, estg_000800.
- No transport/provider failures occurred; retries were not used.

## 4. Which candidate, if any, is justified for one full-150 confirmation run?

R_DEF is the only candidate with a large enough targeted definition benefit to justify one full-150 confirmation run, with the side-effect caveats above. BASE alone shows only modest A -> BASE improvement and should not be promoted on this panel. This report does not launch or authorize the full-150 run.

This remains a targeted development diagnostic, not an unbiased estimate of overall EStG performance. No significance claims are made, R_DEF is not automatically promoted, and no new prompt is designed from individual cases.
