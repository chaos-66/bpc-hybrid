# Actor Prompt Review

Scope: actor / subject definitions in LegalDiscourse (A), Haque & Singh (B), and COLING 2025 Sun/Luo/Li (C), compared against the current R_A actor-minimality repair.

Current R_A text (from `formal_experiment/src/bpc_hybrid/modular_refinement_prompt.py`):
"Actor: extract only an explicitly stated entity that bears responsibility for performing, refraining from, or being subject to the regulated action. Do not label objects, resources, amounts, or other mentioned noun phrases as actors merely because they are salient in the sentence. If no responsible entity is explicitly stated, return no actor."

---

## 1. LegalDiscourse (A)

1. **How does it define subject/actor?**
   - Verified definition: "A SUBJECT is an entity that gains powers or restrictions under a law."
   - Verified prompt: "Which entities gains powers, restrictions or responsibilities under this law? NOT which entities are used to test the law, or which entities are affected."

2. **Does it require an explicit responsibility/action bearer?**
   - No. It says subjects are "not always explicit, and can be expressed passively"; the prompt says to restrict choices to an entity mentioned in the law OR `"passive voice entity"` if the entity is not explicitly mentioned.
   - It also says to enumerate all instances of the entity, even if repeated.

3. **Does it distinguish object/resource/amount from actor?**
   - It distinguishes SUBJECT from OBJECT and PROBE: not entities affected and not entities used to test the law.
   - It does **not** specifically mention resources or amounts. Its OBJECT label could cover affected entities/resources.

4. **How does it handle absent actor?**
   - SUBJECT/OBJECT/PROBE prompts say `"no entity"` if no matching entity, but the prompt simultaneously permits `"passive voice entity"`, which can license an implied actor.

5. **What is its completeness instruction?**
   - "Enumerate all instances of the entity in the text, even if repeated."
   - "If there are multiple segments of text in the law that apply, join them with a semi-colon."

6. **Could it cause empty-Gold over-extraction?**
   - **Yes.** The `"passive voice entity"` option and the enumerate-all instruction can produce actor predictions when Gold has no actor. This is in direct tension with R_A's "If no responsible entity is explicitly stated, return no actor."

---

## 2. Haque & Singh (B)

1. **How does it define subject/actor?**
   - Verified: subject = "the party on whom the norm applies"; object = "the party with respect to whom the norm applies."
   - Directionality differs by norm type (commitment vs prohibition vs authorization/power).

2. **Does it require an explicit responsibility/action bearer?**
   - It requires a party, but not necessarily an explicit surface entity in the sentence; subject/object may be filled from sentence context.
   - The paper reports that explicit directionality definitions improve subject/object role assignment.

3. **Does it distinguish object/resource/amount from actor?**
   - It separates the subject party from the object party, but `object` is not an action object/resource/amount.
   - It does not model amounts/resources explicitly as actors.

4. **How does it handle absent actor?**
   - Empty norm elements are a reported failure. The paper says an empty subject (or object) may mean no party or all parties, which is ambiguous; often it indicates incorrect extraction.

5. **What is its completeness instruction?**
   - "In cases where more than one norm exists, extract all norms." There is no separate all-instances actor enumeration rule.

6. **Could it cause empty-Gold over-extraction?**
   - Indirectly. Its subject definition is closer to R_A's responsibility criterion, but its empty-field ambiguity ("no party" vs "all parties") is not a safe rule for our empty-Gold actor problems. Its `object` counterparty should not be conflated with actor or action object.

---

## 3. COLING 2025 (C)

1. **How does it define subject/actor?**
   - Verified template: identify "all subjects subject to deontic constraints." These may include organizations, companies, government departments, non-profit organizations, and individuals. Look for words such as "must comply", "is obligated", "should", etc.

2. **Does it require an explicit responsibility/action bearer?**
   - It requires a subject constrained by a deontic word, but it does not define explicit-only or responsible-entity criteria.
   - It also asks for the related deontic constraint, further blurring the actor/action boundary.

3. **Does it distinguish object/resource/amount from actor?**
   - No. The examples are broad and the prompt does not exclude objects, resources, amounts, or other noun phrases.
   - It says subjects may include many organization/person classes but not what cannot be a subject.

4. **How does it handle absent actor?**
   - Not addressed. There is no `"none"` / "no actor" instruction.

5. **What is its completeness instruction?**
   - "Accuracy and completeness are very important; please ensure that no relevant information is omitted." This is a strong no-omission instruction.

6. **Could it cause empty-Gold over-extraction?**
   - **Yes, high risk.** A no-omission, broad-subject instruction is the opposite of R_A's explicit-only/no-actor rule. If copied directly, it would likely increase empty-Gold actor false positives.

---

## R_A comparison table

| Literature instruction | Already covered by R_A? | New information? | Potential conflict? |
|---|---|---|---|
| A: SUBJECT = entity gaining powers/restrictions/responsibilities | Partially: R_A says responsible for performing/refraining/being subject to the action | No new operational rule | No, but A's definition is broader |
| A: subject may be passive / "passive voice entity" | No | Yes, but in the wrong direction | **High** with empty-Gold actor; R_A requires explicit responsible entity |
| A: enumerate all repeated entity mentions | Not explicitly in R_A; common schema allows multiple actor spans | Could add recall, but current schema/S already handles coordinated actors | Medium; may exacerbate over-extraction if unconstrained |
| A: no-answer `"no entity"` | Covered semantically by R_A ("return no actor") | No | None |
| B: subject = party on whom norm applies | Covered semantically by R_A | No new operational rule | Medium: B's party/object directionality does not map to our action object |
| B: explicit directionality definitions improved subject/object roles | Not directly applicable; our actor-action relation is different | No prompt-level transferable rule | Medium |
| B: empty subject can mean all parties or no party | No | Yes, but ambiguous | **Medium-high** with empty-Gold actor; should not be adopted as a rule |
| C: all subjects subject to deontic constraints | Partially broad | No; broader and less precise | **High** with empty-Gold actor |
| C: completeness / do not omit information | No | Yes, but conflicts with R_A | **High** |
| C: no absent-actor handling | No | Negative evidence only | Confirms R_A is stricter |

---

## Conclusion

- **Already covered:** the compatible core of A/B/C subject definitions is covered by R_A's responsibility criterion and explicit-only rule.
- **New information:** none of the three papers provides a new, compatible, high-value instruction that R_A lacks. A's "passive voice entity" and C's completeness rule are not new but are **directions we should not adopt** for empty-Gold actor.
- **Potential conflict:** A (`"passive voice entity"`), B (empty subject may mean "all parties"), and C (no omission) all conflict with R_A's explicit-only/no-actor requirement.
- **No duplicate instruction should be added.** R_A remains the stricter, better-aligned actor rule against the observed empty-Gold failure.
