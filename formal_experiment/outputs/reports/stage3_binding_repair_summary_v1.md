# Stage 3 binding / automatic grounding / Table 3 repair summary

## Binding audit (30 pairs)

- audit classes: {'A': 11, 'N': 5, 'U': 14, 'action:A': 25, 'action:U': 5, 'actor:A': 22, 'actor:N': 7, 'actor:U': 1, 'order:H': 20, 'order:U': 10}
- action human fields: 25
- action AI-unresolved fields: 5
- actor human fields: 22
- actor AI-proposal fields: 7
- actor unresolved fields: 1
- order human/not-applicable fields: 20
- order AI-ineligible fields: 10
- required-field human-approved pairs: 13
- pairs needing final human approval: 19 (packet-level; required-field review_state count is 17)
- human approval packet: `outputs/reports/stage3_binding_final_human_approval_packet_v1.md`

## Benchmark eligibility

- missing_action eligible pairs: 8
- incorrect_actor eligible pairs: 5
- out_of_order eligible pairs: 0

## Automatic grounding (evaluated after prediction persistence)

- action any-action top1 accuracy: 0.5000
- action candidate-set recall: 1.0000
- action strong-set recall: 0.6000
- action coverage: 1.0000
- lane coverage: 1.0000
- lane exact accuracy: 1.0000
- rule-order reference available: 0

## Ours (eligible subset only)

- eligible items: 26
- macro-F1: 1.0
- micro-F1: 1.0
- compliant specificity: 1.0
- exact type accuracy: 1.0

## Table 3

See `outputs/reports/stage3_table3_v1.md` for the full table.
- Ours macro-F1: 1.0
- Sun macro-F1: 0.47619047619047616
- Winter macro-F1: 0.3333333333333333
- Oracle/Grounded upper bound macro-F1: 1.0

## Claim boundary

- Ours inference never reads Binding Reference or benchmark mutation answers; it uses a gold-blind inference view and persisted automatic grounding predictions.
- Oracle/Grounded upper bound uses supplied bindings and is reported separately, never as Ours.
- out_of_order is N/A because no eligible rule-side order relation exists; process-only mutations are not formal Gold.
- Full three-type formal Table 3 still requires human approval of 19 unresolved pairs.
