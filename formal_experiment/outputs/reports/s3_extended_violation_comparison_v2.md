# S3.9-EXT synthetic extended-violation comparison v2 (development-only)

**Scope**: 40 controlled synthetic variants over the frozen GDPR-7 BPMN membership (10 prohibited_action_present / 10 required_condition_not_enforced / 10 constraint_violated / 10 exception_not_handled), each with a synthetic compliant CONTROL (Gold = none) and one mutated VARIANT (Gold = its expected type). This panel is a **development-only synthetic controlled extension**: it is NOT human Gold and NOT the formal Oracle. Winter et al. (2020) and Sun et al. (2024) define none of the four new violation types — the methods below are project extensions (`Winter-style extension` / `Sun-style extension`) reusing each method's existing similarity backend and frozen action-mapping gamma; they share the SAME new-type formulas. Zero LLM/API.

Two evaluation kinds are reported separately:

- **variant-only detection evaluation** (original v2 table): the 40 variants only; unobservable items keep predicted=None and count as FN.
- **paired control-plus-variant evaluation** (new): 40 controls (Gold=none) + 40 variants = 80 objects; it answers whether the system can simultaneously NOT flag a compliant process (control -> none) and flag the mutated one with the right type (variant -> expected). Control predictions are re-derived OFFLINE from the persisted `control_scores` with the original per-type rules, the frozen gamma_ext, and a fixed EXTENDED_TYPES priority order; variant predictions are the persisted `predicted_violation_type` of the original run. No threshold or decision order was changed.

## Selection rationale

The original Stage 3 taxonomy checks whether a required action is present, assigned to the correct actor, and ordered correctly. It does not consume four other parts of the six-element Rule Record: prohibition modality, condition, constraint, and exception. The extension therefore adds one operational violation family for each uncovered part instead of adding arbitrary labels.

The four categories were selected by four fixed principles:

- field coverage: each new type gives an existing Stage 2 field a distinct Stage 3 consumer
- semantic non-redundancy: each type can occur even when action presence, actor, and order are all correct
- controlled testability: each type permits a single targeted BPMN mutation with the other activity, actor, label, and order properties held fixed
- BPMN observability: each type has an explicit process-model surface, while absent surfaces are reported as unobservable rather than fabricated

| New type | Why it is needed beyond action/actor/order |
|---|---|
| prohibited_action_present | Complements missing_action by covering commission rather than omission: a process may contain every required task yet still perform an action that the rule explicitly prohibits. It makes prohibition modality and action jointly usable downstream. |
| required_condition_not_enforced | Covers conditional applicability: the correct action, actor, and order are insufficient when the BPMN does not enforce the condition under which the action is permitted or required. It connects the condition field to gateways, condition expressions, and flow labels. |
| constraint_violated | Covers limits on otherwise correct conduct: an action may be present, correctly assigned, and correctly ordered but still breach a deadline, quantity, purpose, or usage restriction. It connects the constraint field to timer, data, annotation, and related BPMN evidence. |
| exception_not_handled | Covers defeasible rules and exceptional paths: a normal path may be compliant while the process has no branch or handler for a legally specified exception. It connects the exception field to boundary/error events, alternate branches, and handler activities. |

**Boundary**: These four types are a minimal field-coverage extension, not an exhaustive legal-violation taxonomy. They are development-only controlled categories and do not convert the frozen three-type human Gold or the formal Oracle into a seven-type benchmark.

## 1. Four new types — variant-only detection evaluation (40 variants)

| Method | prohibited P/R/F1 | condition P/R/F1 | constraint P/R/F1 | exception P/R/F1 | Macro-F1 | Exact | Unobservable | Runtime |
|---|---|---|---|---|---|---|---|---|
| Winter-style extension | 1.000/1.000/1.000 | 1.000/0.200/0.333 | 1.000/0.700/0.824 | 1.000/0.300/0.462 | 0.655 | 0.550 | 17 | 10.1s |
| Sun-style extension | 1.000/1.000/1.000 | 0.000/0.000/0.000 | 1.000/0.200/0.333 | 0.000/0.000/0.000 | 0.333 | 0.300 | 28 | 8.8s |
| BM25 extension | 1.000/0.400/0.571 | 0.000/0.000/0.000 | 1.000/0.200/0.333 | 0.000/0.000/0.000 | 0.226 | 0.150 | 28 | 9.6s |
| TF-IDF/SVD extension | 1.000/1.000/1.000 | 0.000/0.000/0.000 | 1.000/0.200/0.333 | 1.000/0.100/0.182 | 0.379 | 0.325 | 27 | 9.8s |

## 2. Four new types — paired control-plus-variant evaluation (80 objects: 40 controls + 40 variants)

| Method | 5-class acc (80) | variant exact (40) | control FP rate (40) | paired acc (40) | 4-type Macro-F1 | 5-class Macro-F1 | Unobservable |
|---|---|---|---|---|---|---|---|
| Winter-style extension | 0.425 | 0.550 | 0.500 | 0.225 | 0.514 | 0.504 | 25 |
| Sun-style extension | 0.263 | 0.300 | 0.125 | 0.175 | 0.283 | 0.300 | 54 |
| BM25 extension | 0.250 | 0.150 | 0.000 | 0.100 | 0.226 | 0.285 | 54 |
| TF-IDF/SVD extension | 0.338 | 0.325 | 0.275 | 0.300 | 0.330 | 0.368 | 42 |

## 3. Per-type P/R/F1: variant-only vs paired

| Method | Type | variant-only P/R/F1 (40 variants) | paired P/R/F1 (80 objects incl. controls) |
|---|---|---|---|
| Winter-style extension | prohibited_action_present | 1.000/1.000/1.000 | 0.667/1.000/0.800 |
| Winter-style extension | required_condition_not_enforced | 1.000/0.200/0.333 | 0.182/0.200/0.191 |
| Winter-style extension | constraint_violated | 1.000/0.700/0.824 | 0.636/0.700/0.667 |
| Winter-style extension | exception_not_handled | 1.000/0.300/0.462 | 0.600/0.300/0.400 |
| Sun-style extension | prohibited_action_present | 1.000/1.000/1.000 | 0.667/1.000/0.800 |
| Sun-style extension | required_condition_not_enforced | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| Sun-style extension | constraint_violated | 1.000/0.200/0.333 | 1.000/0.200/0.333 |
| Sun-style extension | exception_not_handled | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| BM25 extension | prohibited_action_present | 1.000/0.400/0.571 | 1.000/0.400/0.571 |
| BM25 extension | required_condition_not_enforced | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| BM25 extension | constraint_violated | 1.000/0.200/0.333 | 1.000/0.200/0.333 |
| BM25 extension | exception_not_handled | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| TF-IDF/SVD extension | prohibited_action_present | 1.000/1.000/1.000 | 0.714/1.000/0.833 |
| TF-IDF/SVD extension | required_condition_not_enforced | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| TF-IDF/SVD extension | constraint_violated | 1.000/0.200/0.333 | 1.000/0.200/0.333 |
| TF-IDF/SVD extension | exception_not_handled | 1.000/0.100/0.182 | 0.333/0.100/0.154 |

## 4. v1 three-type synthetic panel (30 variants, stored comparison)

| Method | missing_action F1 | incorrect_actor F1 | out_of_order F1 | Macro-F1 | Exact | Unobservable |
|---|---|---|---|---|---|---|
| Winter-style extension | 1.000 | 0.000 | 0.000 | 0.333 | 0.333 | 0 |
| Sun-style extension | 0.333 | 0.333 | 0.333 | 0.333 | 0.200 | 8 |
| BM25 extension | 1.000 | 0.000 | 0.000 | 0.333 | 0.333 | 10 |
| TF-IDF/SVD extension | 1.000 | 0.571 | 0.333 | 0.635 | 0.533 | 6 |

## 5. Synthetic 7-class type-coverage overview (per-class F1 ONLY)

| Method | missing_action F1 | incorrect_actor F1 | out_of_order F1 | prohibited F1 | condition F1 | constraint F1 | exception F1 |
|---|---|---|---|---|---|---|---|
| Winter-style extension | 1.000 | 0.000 | 0.000 | 1.000 | 0.333 | 0.824 | 0.462 |
| Sun-style extension | 0.333 | 0.333 | 0.333 | 1.000 | 0.000 | 0.333 | 0.000 |
| BM25 extension | 1.000 | 0.000 | 0.000 | 0.571 | 0.000 | 0.333 | 0.000 |
| TF-IDF/SVD extension | 1.000 | 0.571 | 0.333 | 1.000 | 0.000 | 0.333 | 0.182 |

**This table shows type coverage only.** The first three columns come from the 30-item v1 synthetic panel; the last four from the 40-item v2 synthetic panel. The two panels use different samples, detection formulas and backends, so **no joint Macro-F1, joint Exact or joint Unobservable is computed** and this table must not be used for overall performance ranking. Synthetic only; never merged with the 33-item human-adjudicated Gold; not the formal Oracle.

## 6. Per-type cases (from the paired evaluation, across methods)

### prohibited_action_present

Control false positives (total 14 across methods; up to 2):
- winter / syn_v2_prohibited_action_03 (gdpr_2_consent_to_use_the_data x article22): control_predicted=prohibited_action_present
- winter / syn_v2_prohibited_action_04 (gdpr_2_consent_to_use_the_data x article22): control_predicted=prohibited_action_present

Variant detected (total 34 across methods; up to 2):
- winter / syn_v2_prohibited_action_01 (gdpr_2_consent_to_use_the_data x article22): pred=prohibited_action_present scores={'constraint_violated': None, 'exception_not_handled': None, 'prohibited_action_present': 1.0, 'required_condition_not_enforced': None}
- winter / syn_v2_prohibited_action_02 (gdpr_2_consent_to_use_the_data x article22): pred=prohibited_action_present scores={'constraint_violated': None, 'exception_not_handled': None, 'prohibited_action_present': 1.0, 'required_condition_not_enforced': None}

Variant missed (total 6 across methods; up to 2):
- bm25 / syn_v2_prohibited_action_01 (gdpr_2_consent_to_use_the_data x article22): pred=None scores={'constraint_violated': None, 'exception_not_handled': None, 'prohibited_action_present': 0.400997, 'required_condition_not_enforced': None}
- bm25 / syn_v2_prohibited_action_02 (gdpr_2_consent_to_use_the_data x article22): pred=None scores={'constraint_violated': None, 'exception_not_handled': None, 'prohibited_action_present': 0.400997, 'required_condition_not_enforced': None}

### required_condition_not_enforced

Control false positives (total 14 across methods; up to 2):
- winter / syn_v2_prohibited_action_10 (gdpr_7_right_to_be_forgotten x article17): control_predicted=required_condition_not_enforced
- winter / syn_v2_constraint_violated_05 (gdpr_7_right_to_be_forgotten x article17): control_predicted=required_condition_not_enforced

Variant detected (total 2 across methods; up to 2):
- winter / syn_v2_required_condition_05 (gdpr_7_right_to_be_forgotten x article17): pred=required_condition_not_enforced scores={'constraint_violated': 0.519377, 'exception_not_handled': None, 'prohibited_action_present': None, 'required_condition_not_enforced': 0.857079}
- winter / syn_v2_required_condition_08 (gdpr_5_right_to_withdraw x article17): pred=required_condition_not_enforced scores={'constraint_violated': 0.627352, 'exception_not_handled': None, 'prohibited_action_present': None, 'required_condition_not_enforced': 1.0}

Variant missed (total 38 across methods; up to 2):
- winter / syn_v2_required_condition_01 (gdpr_1_data_breach x article33): pred=None scores={'constraint_violated': 0.455127, 'exception_not_handled': 0.618531, 'prohibited_action_present': None, 'required_condition_not_enforced': None}
- winter / syn_v2_required_condition_02 (gdpr_1_data_breach x article33): pred=None scores={'constraint_violated': None, 'exception_not_handled': None, 'prohibited_action_present': None, 'required_condition_not_enforced': None}

### constraint_violated

Control false positives (total 4 across methods; up to 2):
- winter / syn_v2_required_condition_03 (gdpr_1_data_breach x article33): control_predicted=constraint_violated
- winter / syn_v2_required_condition_04 (gdpr_1_data_breach x article34): control_predicted=constraint_violated

Variant detected (total 13 across methods; up to 2):
- winter / syn_v2_constraint_violated_01 (gdpr_1_data_breach x article33): pred=constraint_violated scores={'constraint_violated': 1.0, 'exception_not_handled': 0.618531, 'prohibited_action_present': None, 'required_condition_not_enforced': None}
- winter / syn_v2_constraint_violated_02 (gdpr_1_data_breach x article33): pred=constraint_violated scores={'constraint_violated': 1.0, 'exception_not_handled': None, 'prohibited_action_present': None, 'required_condition_not_enforced': None}

Variant missed (total 27 across methods; up to 2):
- winter / syn_v2_constraint_violated_03 (gdpr_6_right_to_rectify x article16): pred=None scores={'constraint_violated': None, 'exception_not_handled': None, 'prohibited_action_present': None, 'required_condition_not_enforced': None}
- winter / syn_v2_constraint_violated_07 (gdpr_3_right_to_access x article20): pred=None scores={'constraint_violated': None, 'exception_not_handled': None, 'prohibited_action_present': None, 'required_condition_not_enforced': None}

### exception_not_handled

Control false positives (total 4 across methods; up to 2):
- winter / syn_v2_required_condition_01 (gdpr_1_data_breach x article33): control_predicted=exception_not_handled
- winter / syn_v2_constraint_violated_01 (gdpr_1_data_breach x article33): control_predicted=exception_not_handled

Variant detected (total 4 across methods; up to 2):
- winter / syn_v2_exception_not_handled_01 (gdpr_1_data_breach x article33): pred=exception_not_handled scores={'constraint_violated': 0.455127, 'exception_not_handled': 0.618531, 'prohibited_action_present': None, 'required_condition_not_enforced': None}
- winter / syn_v2_exception_not_handled_06 (gdpr_5_right_to_withdraw x article33): pred=exception_not_handled scores={'constraint_violated': 0.660812, 'exception_not_handled': 0.610823, 'prohibited_action_present': None, 'required_condition_not_enforced': 1.0}

Variant missed (total 36 across methods; up to 2):
- winter / syn_v2_exception_not_handled_02 (gdpr_1_data_breach x article34): pred=None scores={'constraint_violated': None, 'exception_not_handled': None, 'prohibited_action_present': 0.137246, 'required_condition_not_enforced': None}
- winter / syn_v2_exception_not_handled_03 (gdpr_1_data_breach x article34): pred=None scores={'constraint_violated': None, 'exception_not_handled': None, 'prohibited_action_present': 0.137246, 'required_condition_not_enforced': None}

## 7. Analysis

- **Easiest type (average variant-only F1)**: `prohibited_action_present` (0.893).
- **Hardest type (average variant-only F1)**: `required_condition_not_enforced` (0.083).
- **Best variant-only macro-F1 method**: `winter` (0.655).

### Per-type support conclusions (DEV_ONLY)

- **prohibited_action_present**: supports the FEASIBILITY of the new detection type: insertion of the prohibited-action task is detected with high precision and recall by every backend except the BM25 length-scale limit
- **required_condition_not_enforced**: current results mainly expose the OBSERVABILITY BOTTLENECK of condition surfaces (subProcess-hidden named gateways) and of action mapping under the frozen gamma; little positive evidence is available on the frozen GDPR-7 models
- **constraint_violated**: PARTIAL support: annotation/timer/data-object mutations are detectable when the rule action maps and a constraint surface exists, but the check remains limited by action mapping and by the BPMN surface available in the frozen models
- **exception_not_handled**: current results mainly expose the lack of boundary events, exception branches and parser-level observability; most exception checks are unobservable or unmappable on the frozen models

### Stage 2 six-element Rule Record dependencies

| New type | Rule Record fields consumed | BPMN surface examined |
|---|---|---|
| prohibited_action_present | modality (prohibition) + action | activity/event labels |
| required_condition_not_enforced | condition + action | gateway labels, conditionExpression, sequence-flow labels, adjacent control nodes |
| constraint_violated | constraint + action | activity/data-object/text-annotation/timer labels; explicit time-limit contradiction |
| exception_not_handled | exception + action | boundary events, error/escalation events, alternate branches, handler labels |

The four new types give four previously unused Rule Record fields (prohibition modality, condition, constraint, exception) an explicit Stage 3 consumption interface, each against a distinct BPMN surface. However, the current controlled data provide strong performance evidence only for some types; the remaining types mainly reveal observability and mapping bottlenecks. This is NOT evidence that all four types 'prove downstream value' — it is evidence that the consumption interface exists and that observability limits where performance can be demonstrated.

### Unobservable reasons (all methods combined, variant-only)

- `action_mapping_below_gamma`: 92
- `no_condition_candidates`: 7
- `no_exception_candidates`: 1

### BPMN expressiveness limits

unobservable reasons caused by BPMN expressiveness: no_condition_candidates / no_constraint_candidates / no_exception_candidates (no gateway/condition surface, no data/annotation/timer surface, no boundary/error/branch surface in the variant model), and action_mapping_below_gamma (the variant's activity labels are not similar enough to the rule action under the method's frozen gamma)

Concrete findings on the frozen GDPR-7 files:

- The frozen files contain **no conditionExpression and no boundary event**; every condition/exception compliant structure in this panel is a synthetic control added to a frozen copy. Removing it makes the variant byte-identical to the frozen process — the frozen process itself is the violated model.
- The **named decision gateways** of gdpr_1 ('Are stolen data exploitable?', 'Does the data controller have high security standard?', 'The data subject has to be notified?') live **inside subProcesses**, which the canonical parser treats as opaque activities. The process-level record therefore exposes no named gateway / condition surface, and condition checks on those variants are `no_condition_candidates` unobservable.
- The '72 hours' timer start event of gdpr_1 sits inside the 'Handle delay' subProcess: invisible to the record parser, observable only at the raw-XML level. The two timer-contradiction variants were still detected (exact contradiction) by every method, because the contradiction record is a direct observation independent of action mapping.
- **Method-backend scale effects**: for BM25 an exact text match scores ~0.4-0.6 depending on label length (the S3.6-A v3 normalization), so long prohibited-action labels fall below `gamma_ext` (BM25 prohibited recall 0.4), while spaCy and TF-IDF exact matches score 1.0. This is a backend scale property of the frozen similarity functions, not a panel artifact.
- **Action-mapping gate**: sun (gamma 0.8), BM25 (0.8) and TF-IDF (0.5) fail the action-mappable precondition on most condition/constraint/exception variants (`action_mapping_below_gamma` unobservables). The new checks inherit the same action-mapping bottleneck as the original three violation types; only the Winter-style extension (gamma 0.4) maps most rule actions.

## 8. Safety

- `llm_api_calls = 0`, `network_calls = 0`, `gold_read = False`.
- The 33-item human-adjudicated violation Gold, the formal Stage 3 schemas, the 30-item v1 panel, the 40 v2 variants and the four methods' original predictions/evaluations/manifests are untouched (byte-unchanged; see the focused tests).
- This panel is a synthetic controlled extension; results must not be cited as formal Oracle or human-Gold performance.
