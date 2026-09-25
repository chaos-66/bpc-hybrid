# Direct-LLM span-grounding repair (retrospective development A/B)

Zero-API replay of the frozen `D-full-0813` responses; only the span-grounding policy changes (OLD `legacy` vs NEW `repair_v1`).

## Overall

| arm | P | R | F1 |
| --- | --- | --- | --- |
| OLD | 0.8203 | 0.7289 | 0.7719 |
| NEW | 0.8172 | 0.7479 | 0.7810 |
| delta | -0.0031 | 0.0190 | 0.0091 |

## Per field

| field | OLD P | OLD R | OLD F1 | NEW P | NEW R | NEW F1 | dF1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| modality | 0.9706 | 0.8658 | 0.9152 | 0.9608 | 0.9134 | 0.9365 | 0.0213 |
| actor | 0.5488 | 0.9167 | 0.6865 | 0.5349 | 0.9375 | 0.6811 | -0.0054 |
| action | 0.8978 | 0.8259 | 0.8603 | 0.9000 | 0.8462 | 0.8722 | 0.0119 |
| condition | 0.9058 | 0.6916 | 0.7843 | 0.9058 | 0.6916 | 0.7843 | 0.0000 |
| constraint | 0.6535 | 0.5497 | 0.5971 | 0.6513 | 0.5596 | 0.6020 | 0.0049 |
| exception | 0.7778 | 0.5385 | 0.6364 | 0.7778 | 0.5385 | 0.6364 | 0.0000 |

## Grounding telemetry

- old_dropped_spans: 42
- new_dropped_spans: 9
- old_actor_dropped_spans: 4
- new_actor_dropped_spans: 0
- recovered_spans_total: 33
- recovered_actor_spans: 4
- repeated_occurrence_cases: 33
- repeated_occurrence_recovered: 33
- repeated_occurrence_unresolved: 0
- ties: 0
- one_to_one_assignment_cases: 7
- assignment_ambiguities: 0

| field | old dropped | new dropped | recovered |
| --- | --- | --- | --- |
| action | 5 | 0 | 5 |
| actor | 4 | 0 | 4 |
| clause_span | 1 | 1 | 0 |
| constraint | 7 | 0 | 7 |
| modality | 26 | 9 | 17 |

## Actor attribution

- old actor FN: 4
- new actor FN: 3
- recovered by grounding repair: 1
- remaining: 3
- grounding-attributable FN share: 0.2500

| sample | actor | old pred | old outcome | candidates | new pred | strategy | gold overlap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| estg_000082 | it | [100,102] | unresolved | [{'start': 98, 'end': 100}, {'start': 133, 'end': 135}, {'start': 185, 'end': 187}, {'start': 214, 'end': 216}] | [98,100] | nearest_original_offsets | False |
| estg_000103 | the tax office | [176,190] | unresolved | [{'start': 34, 'end': 48}, {'start': 183, 'end': 197}] | [183,197] | nearest_original_offsets | True |
| estg_000286 | it | [300,302] | unresolved | [{'start': 320, 'end': 322}, {'start': 325, 'end': 327}] | [320,322] | nearest_original_offsets | False |
| estg_000433 | it | [124,126] | unresolved | [{'start': 20, 'end': 22}, {'start': 60, 'end': 62}, {'start': 118, 'end': 120}, {'start': 155, 'end': 157}] | [118,120] | nearest_original_offsets | False |

## Safety / invariance audit

- invented_semantic_spans: 0
- field_reclassification: 0
- text_mutation: 0
- normalized_mutation: 0
- id_mutation: 0
- old_only_spans: 0
- invented_modality_evidence: 0
- old_only_modality_evidence: 0
- clause_span_text_mutation: 0

## Boundaries

- Retrospective development post-processing ablation; no formal claim.
- The repair is opt-in (`policy=repair_v1`); the production default stays `legacy`.
- No Prompt / actor-semantics change, no LLM call, no Gold-guided recovery.
