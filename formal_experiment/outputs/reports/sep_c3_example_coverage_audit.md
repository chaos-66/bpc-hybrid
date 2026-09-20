# SEP-C3 Example / S-Rule Coverage Audit v1

- 新增 API：0
- 本文件只审计 coverage 和 redundancy；不修改 E，不恢复 S。

## Part A — E Worked Examples Coverage

| Example | Semantic situation covered | Gold-related coverage | Gap / over-generalization risk |
|---|---|---|---|
| E1 | unresolved subject pronoun; simple permission condition | Gold has explicit actor and unresolved pronoun patterns | Actor semantics only; no condition/constraint boundary |
| E2 | passive clause; empty actors; coordinated actions; two disjoint constraints | Covers actor absence; covers multiple constraints | Does not cover nested action/constraint or action containing constraint |
| E3 | prohibition + `unless` exception | Covers one exception marker | Gold exception markers are broader: `except`, `excluding`, `with the exception`, `even if`, `apart from` |
| E4 | definition clause + obligation clause | Covers definition label and empty action for one synthetic definition clause | **High risk**: Gold has action span in 39/39 definition clauses. E4's `actions empty` may cause definition/light-verb miss |
| E5 | condition containing nested constraint | Covers one direction of Gold nested relation; Gold has 10 clauses / 11 pairs | Does not cover constraint containing condition (4 pairs), action containing condition/constraint (11 pairs), or condition-only threshold cases |

## Specific Questions

### E 是否已经覆盖 actor absence?

Yes, E2 has `actors: empty` for a passive clause and maps actions with `actor_id=null`. This is directionally consistent with Gold empty-Gold actor convention.

### E 是否覆盖 nested condition + constraint?

E5 covers condition contains constraint one-way. It is a real Gold pattern, but not the full Gold nested pattern.

### E5 是否只是一个单例，还是代表 Gold 中较常见 pattern?

It represents a real but minority pattern. Gold actual:
- 11 clause-level condition/constraint intersection pairs
- 10 clauses / 10 samples
- 7 condition contains constraint, 4 constraint contains condition

E5 is not a single artificial example; it is a genuine pattern. But it is not complete and does not cover the reverse direction.

### E 是否缺少 condition-only threshold 类例子?

Yes. A central contrast is `estg_000052` (10% threshold inside condition, no Gold constraint) vs `estg_000104` (`up to 20%` as Gold constraint). E lacks this pair.

### E 是否存在可能让模型过度泛化的 pattern?

Yes:
1. E4 `definition clause actions empty` conflicts with 39/39 Gold definition clauses having action spans.
2. E5 one-way condition contains constraint may encourage one-way overlap thinking, while Gold also has constraint contains condition.
3. E2/E5 simple disjoint/nested examples do not expose action containing condition/constraint.

## Part B — S Rule Coverage / Redundancy

| S Rule | What it covers | Gold boundary coverage | Issue |
|---|---|---|---|
| S1 source boundary | no outside text | compatible | not a boundary solution |
| S2 modality labels | four labels defined | partial | does not distinguish definition from `shall be deemed` / `not eligible` obligation-like forms |
| S3 actor | explicit actor, pronoun handling | mostly compatible with R_A/Gold | theoretical conflict with R_A "explicit entity" wording for unresolved pronouns |
| S4 action | smallest verb-centred phrase | partial | does not address copula/light verb or nested action span |
| S5 condition | applicability antecedent | partial | does not decide condition predicate threshold vs nested restriction |
| S6 constraint | topics plus action applicability | over-broad in topic triggers | Gold has legal/time/quantity/purpose in condition-only clauses |
| S7 exception | removed/narrowed case | basic | Gold exception surface includes condition-like markers; small sample |
| S8 field partition | separate arrays; nested constraint in both | partly correct | only one-way overlap; `action ends where phrase begins` conflicts with Gold action overlaps |
| S9 absence/uncertainty | empty means absent | compatible | no boundary solution |
| S10 reference and voice | passive/pronoun handling | compatible | no boundary solution |
| S11 definition/empty records | definitions; empty records | **conflicts in practice** | Gold definition clauses all have actions; E4/S11 may over-generalize |
| S12 clause boundaries | independent normative force | partial | may affect modality/action segmentation; not directly boundary |
| S13 coordination | separate spans/edges | compatible | no boundary solution |
| S14 order relations | order evidence only | compatible | no boundary solution |
| S15 normalization | surface-preserving normalization | compatible | no boundary solution |

## Is the Current Problem Instruction Missing or Execution Unstable?

两者都有，但分层：

1. **Instruction present but execution unstable**
   - isolated `only` after R_C already says not to output isolated cue words.
   - condition retention under R_C: old R_C plus E5/S8 already allow nesting, yet C/D still migrate whole condition.
2. **Instruction missing or conflicting**
   - modality definition vs obligation/prohibition is not covered by S2/E4 at the needed specificity.
   - action containing condition/constraint is contradicted by S8 and not represented in E.
   - reverse overlap constraint contains condition is not covered by E5; S8 only states one direction.
3. **Instruction over-broad**
   - S6 topic list implies legal/time/quantity/purpose phrases are constraint-like, but Gold has all these topics in conditions.
   - S8 action-end wording is too strong relative to Gold action overlap.

## Conclusion

- E is useful but not sufficient for the condition/constraint boundary.
- E4 has a specific over-generalization risk for definition actions.
- E5 is genuine but only one direction.
- S contains relevant semantics but also conflicting/over-broad wording.
- The problem is not symmetric across six fields. Do not mechanically add six field instructions.
