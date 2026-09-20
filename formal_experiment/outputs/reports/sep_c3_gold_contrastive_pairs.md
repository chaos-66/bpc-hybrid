# SEP-C3 Gold Contrastive Pairs v1

- 新增 API：0
- 目的：寻找 surface 相似、但 Gold condition/constraint annotation decision 不同的 pair。
- 约束：lexical features 只做 pair retrieval 和描述；不能作为最终 semantic decision。
- 所有 pair 均需人工语义复核。

## Pair 1 — Percentage / threshold

### `estg_000052` (condition-only threshold)

- Gold condition: `insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit of the immediately preceding business year` `[38,198)`
- Gold constraints: empty
- Surface: `10%`, `do not exceed`, `preceding business year`

### `estg_000104` (threshold as separate constraint)

- Gold condition: `Upon the acquisition or production of depreciable fixed assets` `[4,66)`
- Gold constraints: `up to 20% of the acquisition or production costs` `[118,166)`; `as a profit-reducing deduction` `[167,197)`
- Surface: `up to 20%`

### Contrast

- Both clauses contain a percentage threshold and a permission-like context.
- In `000052`, the threshold is inside the applicability predicate and is not separately annotated.
- In `000104`, the threshold is a parameter after the action `claim an investment allowance` and is annotated as constraint.
- Candidate interpretation: threshold on the applicability proposition vs parameter of an already applicable action.
- Unresolved: still requires manual review; cannot decide by `%` or `up to`.

## Pair 2 — Duration / time

### `estg_000106` (nested duration constraint)

- Gold condition: `have a normal useful life in the business of at least four years` `[77,141)`
- Gold nested constraint: `at least four years` `[122,141)`

### `estg_000062` (duration inside condition, not nested constraint in that clause)

- Gold condition: `If the land was acquired within the last ten years` `[0,50)`
- Gold constraints in same clause: `the acquisition costs` `[52,73)` (not a nested duration phrase)
- Gold later clause has `Upon transition from ... Section 5 ...` condition and no nested time constraint matching that condition.

### Contrast

- Both contain duration/within-language in a condition.
- `000106` has an explicit Gold nested constraint on the same duration phrase.
- `000062` does not annotate the duration phrase as a nested constraint.
- Candidate interpretation: `at least four years` restricts a distinct head `normal useful life`; `within the last ten years` is part of the factual acquisition qualification.
- Unresolved: not sufficient for a general rule; need human review.

## Pair 3 — Eligibility / procedural upon-phrase

### `estg_000104` (`Upon acquisition...` as condition)

- Gold condition: `Upon the acquisition or production of depreciable fixed assets` `[4,66)`
- Gold constraints come after the action and are quantity/manner phrases.

### `estg_000569` (`upon application` as constraint)

- Gold condition: `if the possibility of verification (Sections 86 et seq.) is ensured in another manner or if it concerns cases of minor significance` `[192,323)`
- Gold constraint: `upon application` `[29,45)`

### Contrast

- Both contain `upon`.
- `upon acquisition` is the eligibility trigger in `000104`.
- `upon application` is a procedural circumstance/parameter in `000569`, not the applicability condition.
- Candidate interpretation: procedural circumstance vs applicability trigger.
- Unresolved: `upon` is not decisive; this pair is manual-review-only.

## Pair 4 — Legal reference / purpose inside condition

### `estg_000106` (legal reference as nested constraint)

- Gold condition: `are used in a domestic permanent establishment that serves to generate income within the meaning of Section 2(3) items 1 to 3` `[149,274)`
- Gold nested constraint: `within the meaning of Section 2(3) items 1 to 3` `[227,274)`

### `estg_000209` (legal reference inside condition without nested constraint)

- Gold condition: `if the resolution on the increase of the share capital (Section 149(1) of the Stock Corporation Act 1965) was adopted within two years after the registration of the resolution on the reduction of the share capital for the purpose of repaying parts of the share capital (Section 177 of the Stock Corporation Act 1965)` `[65,381)`
- Gold constraints in clause 0: empty; clause 1 has an outside constraint `to capital reductions by ...` `[401,526)`

### Contrast

- Both have legal references and purpose-like content inside a condition.
- `000106` separately annotates the legal-basis phrase as a nested constraint.
- `000209` does not separately annotate its legal references as constraints in the condition clause.
- Candidate interpretation: only some legal-basis phrases are treated as distinct local restrictions; topic identity is not the distinction.
- Unresolved: high manual-review requirement.

## Pair 5 — Purpose-like phrase

### `estg_000108` (purpose in condition)

- Gold condition: `to the extent that they directly serve the business purpose or are intended for residential purposes of employees of the business` `[64,193)`
- Gold constraint: `For buildings` `[4,17)` (outside condition)

### `estg_000027` (purpose as constraint)

- Gold constraint: `for the purpose of determining the tax rate` `[300,343)`
- Related clause has multiple outside constraints; no nested condition restriction.

### Contrast

- Both contain purpose-language.
- In `000108`, purpose is part of an applicability extent condition.
- In `000027`, purpose is a parameter of the action/conversion context.
- Candidate interpretation: purpose as applicability qualification vs purpose as action parameter.
- Unresolved: manual review.

## Pair-Level Conclusion

The contrastive pairs support only negative/candidate principles:

- Not: `%` => constraint.
- Not: `within` => time constraint.
- Not: `Section` => legal-reference constraint.
- Not: `for ... purpose` => constraint.
- Candidate: role in the applicability proposition vs independent restriction on an already applicable action.

No pair is sufficient to freeze a Prompt rule. The P2 candidate remains `NOT YET A PROMPT RULE`.
