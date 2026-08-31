# S3.9-EXT synthetic extended-violation comparison v2 (development-only)

**Scope**: 40 controlled synthetic variants over the frozen GDPR-7 BPMN membership (10 prohibited_action_present / 10 required_condition_not_enforced / 10 constraint_violated / 10 exception_not_handled). This panel is a **development-only synthetic controlled extension**: it is NOT human Gold and NOT the formal Oracle. Winter et al. (2020) and Sun et al. (2024) define none of the four new violation types — the methods below are project extensions (`Winter-style extension` / `Sun-style extension`) reusing each method's existing similarity backend and frozen action-mapping gamma; they share the SAME new-type formulas. Zero LLM/API.

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

## 1. Four new types — per-method comparison

| Method | prohibited P/R/F1 | condition P/R/F1 | constraint P/R/F1 | exception P/R/F1 | Macro-F1 | Exact | Unobservable | Runtime |
|---|---|---|---|---|---|---|---|---|
| Winter-style extension | 1.000/1.000/1.000 | 1.000/0.200/0.333 | 1.000/0.700/0.824 | 1.000/0.300/0.462 | 0.655 | 0.550 | 17 | 10.1s |
| Sun-style extension | 1.000/1.000/1.000 | 0.000/0.000/0.000 | 1.000/0.200/0.333 | 0.000/0.000/0.000 | 0.333 | 0.300 | 28 | 8.8s |
| BM25 extension | 1.000/0.400/0.571 | 0.000/0.000/0.000 | 1.000/0.200/0.333 | 0.000/0.000/0.000 | 0.226 | 0.150 | 28 | 9.6s |
| TF-IDF/SVD extension | 1.000/1.000/1.000 | 0.000/0.000/0.000 | 1.000/0.200/0.333 | 1.000/0.100/0.182 | 0.379 | 0.325 | 27 | 9.8s |

## 2. Synthetic 7-class overview (descriptive only)

Combines the v1 three-type panel (30 items, stored comparison) and the v2 four-type panel (40 items). **Synthetic only; never merged with the 33-item human-adjudicated Gold; not the formal Oracle.** The two panels use different formulas, so cross-panel numbers are descriptive, not comparable metrics.

| Method | missing_action F1 | incorrect_actor F1 | out_of_order F1 | prohibited F1 | condition F1 | constraint F1 | exception F1 | Macro-F1 | Exact | Unobservable |
|---|---|---|---|---|---|---|---|---|---|
| Winter-style extension | 1.000 | 0.000 | 0.000 | 1.000 | 0.333 | 0.824 | 0.462 | 0.655 | 0.550 | 17 |
| Sun-style extension | 0.333 | 0.333 | 0.333 | 1.000 | 0.000 | 0.333 | 0.000 | 0.333 | 0.300 | 28 |
| BM25 extension | 1.000 | 0.000 | 0.000 | 0.571 | 0.000 | 0.333 | 0.000 | 0.226 | 0.150 | 28 |
| TF-IDF/SVD extension | 1.000 | 0.571 | 0.333 | 1.000 | 0.000 | 0.333 | 0.182 | 0.379 | 0.325 | 27 |

## 3. Per-type success and failure cases (across methods)

### prohibited_action_present  (detected 34 / missed 6 across 40 method-variant pairs)

Detected (up to 2):
- winter / syn_v2_prohibited_action_01 (gdpr_2_consent_to_use_the_data x article22): pred=prohibited_action_present scores={'prohibited_action_present': 1.0, 'required_condition_not_enforced': None, 'constraint_violated': None, 'exception_not_handled': None}
- winter / syn_v2_prohibited_action_02 (gdpr_2_consent_to_use_the_data x article22): pred=prohibited_action_present scores={'prohibited_action_present': 1.0, 'required_condition_not_enforced': None, 'constraint_violated': None, 'exception_not_handled': None}

Missed (up to 2):
- bm25 / syn_v2_prohibited_action_01 (gdpr_2_consent_to_use_the_data x article22): pred=None scores={'prohibited_action_present': 0.400997, 'required_condition_not_enforced': None, 'constraint_violated': None, 'exception_not_handled': None} observability={'observable': True, 'reason': None}
- bm25 / syn_v2_prohibited_action_02 (gdpr_2_consent_to_use_the_data x article22): pred=None scores={'prohibited_action_present': 0.400997, 'required_condition_not_enforced': None, 'constraint_violated': None, 'exception_not_handled': None} observability={'observable': True, 'reason': None}

### required_condition_not_enforced  (detected 2 / missed 38 across 40 method-variant pairs)

Detected (up to 2):
- winter / syn_v2_required_condition_05 (gdpr_7_right_to_be_forgotten x article17): pred=required_condition_not_enforced scores={'prohibited_action_present': None, 'required_condition_not_enforced': 0.857079, 'constraint_violated': 0.519377, 'exception_not_handled': None}
- winter / syn_v2_required_condition_08 (gdpr_5_right_to_withdraw x article17): pred=required_condition_not_enforced scores={'prohibited_action_present': None, 'required_condition_not_enforced': 1.0, 'constraint_violated': 0.627352, 'exception_not_handled': None}

Missed (up to 2):
- winter / syn_v2_required_condition_01 (gdpr_1_data_breach x article33): pred=None scores={'prohibited_action_present': None, 'required_condition_not_enforced': None, 'constraint_violated': 0.455127, 'exception_not_handled': 0.618531} observability={'observable': False, 'reason': 'no_condition_candidates'}
- winter / syn_v2_required_condition_02 (gdpr_1_data_breach x article33): pred=None scores={'prohibited_action_present': None, 'required_condition_not_enforced': None, 'constraint_violated': None, 'exception_not_handled': None} observability={'observable': False, 'reason': 'action_mapping_below_gamma'}

### constraint_violated  (detected 13 / missed 27 across 40 method-variant pairs)

Detected (up to 2):
- winter / syn_v2_constraint_violated_01 (gdpr_1_data_breach x article33): pred=constraint_violated scores={'prohibited_action_present': None, 'required_condition_not_enforced': None, 'constraint_violated': 1.0, 'exception_not_handled': 0.618531}
- winter / syn_v2_constraint_violated_02 (gdpr_1_data_breach x article33): pred=constraint_violated scores={'prohibited_action_present': None, 'required_condition_not_enforced': None, 'constraint_violated': 1.0, 'exception_not_handled': None}

Missed (up to 2):
- winter / syn_v2_constraint_violated_03 (gdpr_6_right_to_rectify x article16): pred=None scores={'prohibited_action_present': None, 'required_condition_not_enforced': None, 'constraint_violated': None, 'exception_not_handled': None} observability={'observable': False, 'reason': 'action_mapping_below_gamma'}
- winter / syn_v2_constraint_violated_07 (gdpr_3_right_to_access x article20): pred=None scores={'prohibited_action_present': None, 'required_condition_not_enforced': None, 'constraint_violated': None, 'exception_not_handled': None} observability={'observable': False, 'reason': 'action_mapping_below_gamma'}

### exception_not_handled  (detected 4 / missed 36 across 40 method-variant pairs)

Detected (up to 2):
- winter / syn_v2_exception_not_handled_01 (gdpr_1_data_breach x article33): pred=exception_not_handled scores={'prohibited_action_present': None, 'required_condition_not_enforced': None, 'constraint_violated': 0.455127, 'exception_not_handled': 0.618531}
- winter / syn_v2_exception_not_handled_06 (gdpr_5_right_to_withdraw x article33): pred=exception_not_handled scores={'prohibited_action_present': None, 'required_condition_not_enforced': 1.0, 'constraint_violated': 0.660812, 'exception_not_handled': 0.610823}

Missed (up to 2):
- winter / syn_v2_exception_not_handled_02 (gdpr_1_data_breach x article34): pred=None scores={'prohibited_action_present': 0.137246, 'required_condition_not_enforced': None, 'constraint_violated': None, 'exception_not_handled': None} observability={'observable': False, 'reason': 'action_mapping_below_gamma'}
- winter / syn_v2_exception_not_handled_03 (gdpr_1_data_breach x article34): pred=None scores={'prohibited_action_present': 0.137246, 'required_condition_not_enforced': None, 'constraint_violated': None, 'exception_not_handled': None} observability={'observable': False, 'reason': 'action_mapping_below_gamma'}

## 4. Analysis

- **Easiest type (average F1)**: `prohibited_action_present` (0.893).
- **Hardest type (average F1)**: `required_condition_not_enforced` (0.083).
- **Best macro-F1 method**: `winter` (0.655).

### Stage 2 six-element Rule Record dependencies

| New type | Rule Record fields consumed | BPMN surface examined |
|---|---|---|
| prohibited_action_present | modality (prohibition) + action | activity/event labels |
| required_condition_not_enforced | condition + action | gateway labels, conditionExpression, sequence-flow labels, adjacent control nodes |
| constraint_violated | constraint + action | activity/data-object/text-annotation/timer labels; explicit time-limit contradiction |
| exception_not_handled | exception + action | boundary events, error/escalation events, alternate branches, handler labels |

The four new checks are **downstream value of the six-element Rule Record**, not extra labels on the old three scores: each check consumes a different element (modality+action / condition / constraint / exception) and a different BPMN surface. When Stage 2 produces an empty element, or the variant model has no matching surface, the check is recorded unobservable (never hard 0/1).

### Unobservable reasons (all methods combined)

- `action_mapping_below_gamma`: 92
- `no_condition_candidates`: 7
- `no_exception_candidates`: 1

### BPMN expressiveness limits

unobservable reasons caused by BPMN expressiveness: no_condition_candidates / no_constraint_candidates / no_exception_candidates (no gateway/condition surface, no data/annotation/timer surface, no boundary/error/branch surface in the variant model), and action_mapping_below_gamma (the variant's activity labels are not similar enough to the rule action under the method's frozen gamma)

Concrete findings on the frozen GDPR-7 files:

- The frozen files contain **no conditionExpression and no boundary event**; every condition/exception compliant structure in this panel is a synthetic control added to a frozen copy. Removing it makes the variant byte-identical to the frozen process — the frozen process itself is the violated model.
- The **named decision gateways** of gdpr_1 ('Are stolen data exploitable?', 'Does the data controller have high security standard?', 'The data subject has to be notified?') live **inside subProcesses**, which the canonical parser treats as opaque activities. The process-level record therefore exposes no named gateway / condition surface, and condition checks on those variants are `no_condition_candidates` unobservable (7 unobservables across methods).
- The '72 hours' timer start event of gdpr_1 sits inside the 'Handle delay' subProcess: invisible to the record parser, observable only at the raw-XML level. The two timer-contradiction variants were still detected (exact contradiction) by every method, because the contradiction record is a direct observation independent of action mapping.
- **Method-backend scale effects**: for BM25 an exact text match scores ~0.4-0.6 depending on label length (the S3.6-A v3 normalization), so long prohibited-action labels fall below `gamma_ext` (BM25 prohibited recall 0.4), while spaCy and TF-IDF exact matches score 1.0. This is a backend scale property of the frozen similarity functions, not a panel artifact.
- **Action-mapping gate**: sun (gamma 0.8), BM25 (0.8) and TF-IDF (0.5) fail the action-mappable precondition on most condition/constraint/exception variants (92 `action_mapping_below_gamma` unobservables across methods). The new checks inherit the same action-mapping bottleneck as the original three violation types; only the Winter-style extension (gamma 0.4) maps most rule actions.

## 5. Safety

- `llm_api_calls = 0`, `network_calls = 0`, `gold_read = False`.
- The 33-item human-adjudicated violation Gold, the formal Stage 3 schemas and the v1 three-type predictions/results are untouched (byte-unchanged; see the focused tests).
- This panel is a synthetic controlled extension; results must not be cited as formal Oracle or human-Gold performance.
