# SEP-C3 modular prompt overlap / conflict audit v1 (zero API)

- status: complete_zero_api
- audit scope: frozen `common_system.md`, `user_envelope.md`, `examples_E.md`, `semantic_rules_S.md`, `output_format_J.md`
- no prompt, Gold, prediction, evaluator, or formal report was modified.

## Prompt hashes

| component | SHA-256 | chars |
|---|---:|---:|
| common_system | `b8cfc32b87f446ced89da83fd0ad5aef69ee418a116c6ede534816c5204ac2d7` | 1757 |
| user_envelope | `e8f18096d7260ccd23a6a1ed562b15c861f4e6caf2e5bc7de96a8a23d4e98728` | 102 |
| examples_E | `fa04d454914fd85ad422ed40b3e4d3f71027ad87e9a46b1f4808f0cb4e21aebd` | 2350 |
| semantic_rules_S | `113037b73485adb071dbfeabc54dfe6906514279c3dd065f72b4eb019d3a0025` | 3540 |
| output_format_J | `aa4ed3db8c8b55090a719467802cc878847b436fab9ec8af4d730dce9e899879` | 264 |

## Instruction inventory

- atomic/auditable instructions recorded: 38
  - common: 16
  - E: 5
  - S: 15
  - J: 2

## E/S functional overlap

- `E01, S03, S10`: functional_overlap — actor surface preservation, including unresolved subject pronouns (E01 demonstrates the same boundary behavior that S03/S10 state abstractly.)
- `E02, S04, S06, S10`: functional_overlap — passive action mapping plus constraint extraction (E02 gives a boundary example for actions/constraints that S04/S06 define abstractly; S10 states the passive mapping rule.)
- `E03, S02, S07`: functional_overlap — prohibition modality and exception extraction (E03 demonstrates the exception pattern that S07 defines and the modality class that S02 defines.)
- `E04, S11, S12`: functional_overlap — definition/obligation clause splitting (E04 demonstrates the clause split and empty-record pattern governed by S11/S12.)
- `E05, S05, S06, S08`: functional_overlap — condition/constraint nesting and field partition (E05 demonstrates the nested constraint behavior explicitly governed by S08; S05/S06 define the fields.)

## E/S literal contradiction search

- result: `no_literal_contradiction_found`
- method: line-by-line semantic comparison of the frozen common/E/S/J component files by instruction inventory
- boundary: The absence of literal contradiction does not rule out overlapping guidance or conditional interference at generation time.

## J vs common skeleton

- baseline structural interface: C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16
- additional J discipline: J01, J02
- literal duplicates: 0
- genuinely new constraint: Return one bare JSON object. Do not wrap it in Markdown fences or add a prefix, explanation, comments, or trailing text.
- why 000 parses 150/150: The persisted canonical parser/adaptor accepts and canonicalizes fenced raw responses. 000 raw responses included 36/150 Markdown-fenced objects, yet all 150 became canonical schema/cross-field-valid records.

## Sample-linked evidence

### actor_overextraction_after_S_addition
- prompt instructions: S03, S10, S13
- evidence type: `mechanically_observed_span_difference`
- `estg_000080` (101_to_111): 101 predicted exactly the Gold actor; 111 additionally predicted 'Contributions', 'the assets', and a long amount phrase as actors.
- `estg_000083` (101_to_111): 101 predicted no actors; 111 predicted 'the additional amounts' and 'the reduced amounts' although Gold has no actor.
- hypothesis: The broad actor-surface instructions in S may be over-applied to noun phrases in coordinated or passive contexts, while the passive-voice exception in S10 is not always followed. This is a plausible interference hypothesis, not a causal proof.
- unresolved: No same-prompt repeat or token-level activation evidence is available to separate S wording effects from ordinary run-to-run generation variation.

### constraint_marker_overextraction_after_S_addition
- prompt instructions: S06, S08
- evidence type: `mechanically_observed_span_difference`
- `estg_000020` (100_to_110): 100 predicted exactly the Gold constraint span; 110 additionally emitted 'only' as a separate constraint, creating one unmatched prediction.
- `estg_000106` (101_to_111): 101 emitted one partial constraint; 111 emitted the full Gold-overlapping constraint plus an extra 'only' span.
- hypothesis: S06's marker-inclusion and smallest-complete-limit guidance can produce separate marker spans that the evaluator treats as unmatched. The wording does not explicitly require splitting a marker from its governed limit.
- unresolved: The pair 100_to_110 is cross-batch confounded; the 101_to_111 pair is same-batch but single-run. Neither establishes causal wording attribution.

### E_constraint_recovery
- prompt instructions: E02, E05
- evidence type: `mechanically_observed_span_difference`
- `estg_000020` (000_to_100): 000 missed the Gold constraint; 100 recovered the exact Gold span.
- `estg_000021` (000_to_100): 000 missed the Gold constraint; 100 recovered a matching constraint span with the marker 'only'.
- hypothesis: E examples may supply concrete condition/constraint span patterns that reduce missed constraint spans in the common skeleton. This is consistent with E-only improvement but is not isolated from other prompt differences in this single run.
- unresolved: No controlled E-only wording variant or repeat is available yet.

### J_serialization_effect
- prompt instructions: J01, J02
- evidence type: `raw_response_and_canonical_pipeline_counts`
- hypothesis: J mainly adds a serialization/discipline constraint. It changes raw response form, but the current canonical parser already recovers fenced objects, so no F1 or canonical-failure benefit is observable.
- unresolved: The canonical semantic predictions also differ across arms, but each arm is a single generation; those differences cannot be attributed to J alone.

## Conclusion

- E/S: The E examples and S rules overlap functionally; no literal contradiction was found. The paired failures motivate a narrower test of whether actor-surface and constraint-marker guidance causes conditional over-extraction.
- J/common: J is not a pure duplicate of the common interface because bare-object/no-wrapper discipline is genuinely additional. Empirically, however, the shared canonicalizer already yields 150/150 schema-valid records without J, so J's additional discipline has no measurable primary-metric or canonical-failure benefit in this dataset/model setting.
- causal status: Functional overlap and sample-level temporal associations are established. Causal wording-level attribution is unresolved and must not be written as proven.
