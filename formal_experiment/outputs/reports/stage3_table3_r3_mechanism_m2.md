# R3 independent mechanism/development check

- backend: `m2`
- status: `pass`
- passed: `14/14`

## logi_active_after — PASS

- actual_edges: `[('the parcel arrives at the dock', 'scans the parcel')]`
- expected_edges: `[['the parcel arrives at the dock', 'scans the parcel']]`
- rejection_reason: `None`

## invoice_before_passive — PASS

- actual_edges: `[('be approved', 'the payment is dispatched')]`
- expected_edges: `[['be approved', 'the payment is dispatched']]`
- rejection_reason: `None`

## invoice_prior_to_passive — PASS

- actual_edges: `[('act', 'the restriction of processing being lifted')]`
- expected_edges: `[['act', 'the restriction of processing being lifted']]`
- rejection_reason: `None`

## logi_nominal_processing — PASS

- actual_edges: `[('consult the authority', 'processing')]`
- expected_edges: `[['consult the authority', 'processing']]`
- rejection_reason: `None`

## invoice_date_duration_rejected — PASS

- actual_edges: `[]`
- expected_edges: `[]`
- rejection_reason: `nominal_endpoint_date_time_quantity_root`

## logi_truncated_span_rejected — PASS

- actual_edges: `[]`
- expected_edges: `[]`
- rejection_reason: `truncated_selected_span`

## logi_multiple_events_rejected — PASS

- actual_edges: `[]`
- expected_edges: `[]`
- rejection_reason: `multiple_top_level_event_predicates`

## invoice_negated_marker_rejected — PASS

- actual_edges: `[]`
- expected_edges: `[]`
- rejection_reason: `dependency_neg_ancestor`

## same_object_different_action — PASS

- actual_selected: `N1`
- expected_selected: `N1`
- tied: `['N1']`

## same_action_different_object — PASS

- actual_selected: `N2`
- expected_selected: `N2`
- tied: `['N2']`

## duplicate_node_names_stable_id — PASS

- actual_selected: `N1`
- expected_selected: `N1`
- tied: `['N1', 'N2']`

## normal_order_satisfied — PASS

- actual_status: `satisfied`
- expected: `satisfied`

## reverse_order_violated — PASS

- actual_status: `violated`
- expected: `violated`

## p2_imperative_vocab_limitation_scan — PASS

- actual_selected: `N1`
- expected_selected: `N1`
- tied: `['N1']`
