# Semantic Mapping

All rows are **Interpretation** unless the "Their exact definition" cell is quoted from a verified source. `Our closest concept` is always only the closest concept, never an equality claim.

## Legend

- Compatible? values: high / partial / low / incompatible / not applicable.
- Transfer risk: risk that directly copying the source's label semantics would break our Gold or create new errors.

---

## Master mapping table

| Source | Their concept | Their exact definition | Our closest concept | Compatible? | Difference | Transfer risk |
|---|---|---|---|---|---|---|
| LegalDiscourse (A) | SUBJECT | "an entity that gains powers or restrictions under a law"; explicit or passive | actor | partial | A allows implied/passive subjects and enumerates all mentions; our R_A requires an explicitly stated responsible entity | high: could reintroduce empty-Gold over-extraction |
| LegalDiscourse (A) | OBJECT | "an entity (noun phrase) affected by the subject, under a law" | action object / action complement (currently inside `action` span) | partial | A's OBJECT is a discourse participant, not the object of the regulated action; our schema has no separate action-object field | high: label collision risk |
| LegalDiscourse (A) | PROBE | "an entity to which a TEST is applied that is not a SUBJECT or an OBJECT" | condition entity / condition participant | partial | PROBE is an entity role; our `condition` is a full applicability span | high |
| LegalDiscourse (A) | CONSEQUENCE | "the specific power or restriction conferred by the law" | action + modality (and sometimes constraint) | partial | A bundles power/restriction into one predicate role; our action, modality, and constraint are separate | high |
| LegalDiscourse (A) | TEST | "an explicit condition applied to an entity ... that determines when a SUBJECT-CONSEQUENCE-OBJECT relation holds" | condition | partial/high for applicability | A's TEST may include nested population/time/threshold phrases; it has no separate inner constraint label | medium-high: useful conceptually, but no boundary rule |
| LegalDiscourse (A) | EXCEPTION | "a corollary to a TEST; it specifies when a law does NOT apply" | exception | high | A's EXCEPTION is close, but its span treatment is not fully specified | low-medium |
| Haque & Singh (B) | subject | "the party on whom the norm applies" | actor | partial | B's subject can be a party with no explicit verb agent; role directionality changes by norm type | medium |
| Haque & Singh (B) | object | "the party with respect to whom the norm applies" | no current schema field; not our action object | incompatible | B's object is a counterparty party; treating it as action object or actor would be wrong | very high |
| Haque & Singh (B) | antecedent | "which brings the norm into force, i.e., the condition on which the action of the subject depends" | condition | partial | event-level condition; no span boundary; may include conjunction/time/threshold | high |
| Haque & Singh (B) | consequent | "which brings the norm to satisfaction, i.e., the outcomes of the action" | action and/or constraint | partial | B combines outcome/action in one element; no constraint role | high |
| Sun/Luo/Li COLING 2025 (C) | agent / subject under deontic constraint | all subjects subject to deontic constraints; may include organizations, companies, government departments, non-profits, individuals | actor | partial | C emphasizes completeness and broad classes; no empty-actor rule; no resource/amount exclusion | high: direct conflict with empty-Gold actor |
| Sun/Luo/Li COLING 2025 (C) | deontic word | words expressing moral/legal obligation, responsibility, or norm, e.g. "must", "should", "prohibited", "responsibility" | modality evidence | partial | C predicts deontic words with explanations; our `modality` has a label plus evidence span | medium-high: different task granularity |
| RC4PC (D) | precondition | "factual conditions and do not carry deontic meaning"; actions in precondition may have dimensions/patterns | condition | partial | D's precondition is a formal action-object container, not a text span; no separate constraint label | high |
| RC4PC (D) | norm action | deontic modality is "defined only over actions in norms"; action has dimension/compliance_pattern and optional nested temporal_constraints | action + constraint | partial | D's action object can contain restrictions/limits, so it fuses action and constraint at the formal level | high |
| RC4PC (D) | compliance_pattern | controlled vocabulary such as `data_in_range`, `duration`, `validity_period`, `existence_of_A` | constraint/action semantic type | low/partial | This is a formal pattern label, not a text span role | very high |
| LegalChanges4BPC (E) | actor | "The role responsible for executing the action." | actor | high | Nearly matches R_A's responsibility criterion; E does not state an explicit-only/no-answer rule | low-medium |
| LegalChanges4BPC (E) | action | "The activity that is mandatory, prohibited, or permitted." | action | high | Close; E separates action_object from action | low |
| LegalChanges4BPC (E) | action_object | "The item being acted upon." | no separate field; currently part of action span or modifier | partial | Our schema does not have `action_object`; adding it is a schema change, not a prompt-only change | high |
| LegalChanges4BPC (E) | condition | "Specifies when the statement applies." | condition | high | E's definition is underspecified compared with our S rule (antecedent state/event that activates/determines whether/when norm applies) | medium |
| LegalChanges4BPC (E) | constraint | "A restriction limiting how or when the regulation is applicable." | constraint | high | E's definition does not mention purpose, legal reference, quantity, exclusivity, or nesting; our S rule is more operational | medium |
| LegalChanges4BPC (E) | exception | "Conditions under which the regulation does not apply." | exception | high | Close; E does not specify span boundaries | low-medium |
| Kölbel et al. (F) | process model + external standard + question | BPMN model plus standard context and a predefined question | not applicable | incompatible | No condition/constraint/actor extraction; it answers questions about model/standard | not applicable |
| DPLACC (G) | x1/x2 + MASK label | sentence pair compliance classification via masked language modeling and logic-vector fusion | not applicable | incompatible | Not instruction-based field extraction; no semantic role labels | not applicable |

---

## Field-specific notes

### actor / subject / agent

- **LegalDiscourse SUBJECT**: Verified definition "an entity that gains powers or restrictions under a law." The prompt permits `"passive voice entity"` when no explicit entity is mentioned. This is **not** compatible with the current R_A empty-Gold rule.
- **Haque & Singh subject**: Verified "the party on whom the norm applies." Its `object` is another party, not our action object. The subject definition itself overlaps with R_A's responsibility criterion, but the surrounding role-directionality problem does not map cleanly.
- **COLING 2025 agent**: Verified broad constrained-subject instruction with strong completeness. This is the clearest conflict with our empty-Gold actor.
- **LegalChanges4BPC actor**: Verified "The role responsible for executing the action." This is the closest definition to R_A. It does not specify explicit-only extraction or return-none behavior.

### condition / applicability / antecedent / test / precondition

- **LegalDiscourse TEST** is closest to `condition`, but it is defined as a condition applied to an entity that determines whether the full subject-consequence-object relation holds. It can contain thresholds, census references, and time expressions as part of the condition. This supports keeping the complete condition but does not define an inner constraint role.
- **Haque & Singh antecedent** is closest to `condition`, but it is event-level and includes any trigger/precondition; no span.
- **RC4PC precondition** is closest to `condition` and explicitly "does not carry deontic meaning." It is a formal structure containing action objects, sometimes with nested temporal constraints. This supports structural nesting but not overlapping span labels.
- **LegalChanges4BPC condition** is closest to `condition` by exact terminology: "Specifies when the statement applies." The one-shot example also treats a new disclosure clause as `condition`.

### constraint / restriction / limit

- No source except LegalChanges4BPC uses a `constraint` concept with an explicit definition. Its definition is "A restriction limiting how or when the regulation is applicable."
- LegalDiscourse has no separate constraint label; restrictions are bundled into CONSEQUENCE.
- Haque & Singh has no constraint role; restrictions can appear inside antecedent or consequent.
- RC4PC has no separate constraint role; restrictions are encoded as typed action objects/compliance patterns and nested `temporal_constraints`.
- LegalChanges4BPC's example treats a tightened numeric threshold ("less than 10ppm") as `constraint`, and a new disclosure condition as `condition`, but it does not specify whether these are disjoint, overlapping, or nested spans.

### exception

- LegalDiscourse EXCEPTION, LegalChanges4BPC exception, and the current `exception` field all describe cases where the rule does not apply. This is the most compatible cross-paper concept after actor/action, but span-boundary rules remain unspecified in the literature.

### action_object

- Only LegalChanges4BPC explicitly names `action_object` ("the item being acted upon"). Our current schema has no separate `action_object` field; action spans may include the necessary object/complement under the common S rule. This is a schema-level difference and cannot be fixed by prompt wording alone.

---

## Verified vs interpreted summary

| Claim | Level | Source |
|---|---|---|
| LegalDiscourse defines SUBJECT/TEST/EXCEPTION as above | Verified | Paper Section 2.1 and Appendix F |
| Haque & Singh define subject/object/antecedent/consequent as above | Verified | arXiv preprint Section 3.2 |
| COLING 2025 agent prompt asks for all deontic-constrained subjects and completeness | Verified | Appendix C, Figure 7 |
| RC4PC precondition carries no deontic meaning and norms carry modality/action | Verified | Paper Section 4.1/5.1 |
| LegalChanges4BPC defines six concept types including condition/constraint/exception | Verified | Paper Section 6.2.1 and GitHub prompt |
| LegalChanges4BPC example treats threshold as constraint and disclosure as condition | Verified | GitHub one-shot example |
| Our `condition`, `constraint`, `exception` definitions already cover the core of the E definitions | Interpretation | Compare E prompt with current S rules |
| No source directly resolves nested condition/constraint span overlap | Verified absence after search | A/B/C/D/E/F/G review |
