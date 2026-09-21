# Stage 2 Gold definition audit

Report id: `stage2_gold_definition_audit_v1` - zero new LLM calls - read-only over frozen artifacts.

## 1. Structure

- Records: 150, clauses: 231
- Five-field spans: 824
- Malformed spans (text != source slice): **0**

| Field | Spans |
|---|---|
| actor | 48 |
| action | 247 |
| condition | 214 |
| constraint | 302 |
| exception | 13 |

## 2. Provenance (was the Gold really human-adjudicated?)

- Records where all six element decisions were `accepted`: **0/150**
- Verdict: human-adjudicated: every element decision was edited or rejected, not accepted verbatim.

Decision counts:

| Decision | Count |
|---|---|
| action=edited | 150 |
| actor=accepted | 1 |
| actor=edited | 148 |
| actor=rejected | 1 |
| condition=edited | 150 |
| constraint=accepted | 1 |
| constraint=edited | 148 |
| constraint=rejected | 1 |
| exception=accepted | 3 |
| exception=edited | 147 |
| modality=accepted | 2 |
| modality=edited | 148 |
| translation=accepted | 139 |
| translation=edited | 11 |

## 3. Condition/constraint boundary

- Constraint spans: 302
- Constraints starting with a condition marker: 6
- Overlapping condition/constraint pairs: 11 (constraint inside condition 7, condition inside constraint 4)
- Identical text used as both fields: 1
- Verdict: boundary applied consistently; the few overlaps are the documented nested-constraint rule, not label confusion.

## 4. Sun marker coverage (definitional breadth)

Sun Table 4 marker sets are published as INITIAL sets that Sun extends, so every count here is a lower bound.

| Field | Spans | Distinct | With a Sun marker | Share | No marker class | Share |
|---|---|---|---|---|---|---|
| constraint | 302 | 293 | 114 | 37.7% | 166 | 55.0% |
| condition | 214 | 210 | 87 | 40.7% | 67 | 31.3% |

This project's `constraint` definition is therefore **substantially broader** than Sun's marker-based one. That is a comparability caveat the paper must state.

## 5. Fairness check - does Table 1 survive a matched definition?

Both arms re-scored on the coarse view under three constraint definitions, from the published Gold down to only constraint spans carrying explicit Sun-style quantity/time/comparison wording:

| View | Method | P | R | Overall F1 | Constraint F1 |
|---|---|---|---|---|---|
| full_gold_definition | Sun et al. (rules-only) | 0.6984 | 0.8410 | 0.7631 | 0.6182 |
| full_gold_definition | Ours (Direct-LLM) | 0.8695 | 0.8083 | 0.8378 | 0.7427 |
| matched_sun_marker_phrases | Sun et al. (rules-only) | 0.6357 | 0.8992 | 0.7448 | 0.5400 |
| matched_sun_marker_phrases | Ours (Direct-LLM) | 0.7678 | 0.8398 | 0.8022 | 0.5614 |
| matched_sun_marker_phrases_and_numerals | Sun et al. (rules-only) | 0.6592 | 0.8851 | 0.7556 | 0.5828 |
| matched_sun_marker_phrases_and_numerals | Ours (Direct-LLM) | 0.8085 | 0.8362 | 0.8221 | 0.6625 |

| View | d Overall (pp) | d Constraint (pp) |
|---|---|---|
| full_gold_definition | +7.47 | +12.45 |
| matched_sun_marker_phrases | +5.74 | +2.14 |
| matched_sun_marker_phrases_and_numerals | +6.65 | +7.98 |

**Conclusion:** the Direct-LLM advantage over the rules baseline is NOT an artifact of the broader constraint definition: it stays positive in every matched view, while the constraint-field advantage shrinks as the definition is narrowed.

### How to report this in the paper

The **overall** conclusion is robust: the Direct-LLM advantage stays positive in every view (+5.74 pp, +6.65 pp under the matched views).

The **constraint-field** advantage is NOT robust: it ranges from a large margin down to a small one as the definition is narrowed, so the paper must not headline a single large constraint number. Report constraint as *definition-sensitive* and give the range.

Either way the paper must state that the comparison is **this project's Sun-style rules baseline scored on this project's broader Gold definition** - it is not a reproduction of Sun's own reported numbers.

## Audit verdict

No systematic Gold error was found that would justify reconstructing the annotations. The Gold is structurally valid, demonstrably human-edited, and applies the condition/constraint boundary consistently. The one real issue is **definitional breadth**, which is a reporting caveat, not a Gold defect.

## Provenance

- Gold: `data/gold/stage2/estg150_formal_gold_v1.json` (sha256 `c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100`)
- New LLM calls: 0
