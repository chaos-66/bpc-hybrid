# S1.1-S1.4 Task Matrix v1 (2026-08-11)

- scope: 7 GDPR BPMN (data/input/stage1_stage3/gdpr7) as the ONLY active input; references/archive not activated
- determinism: double-run byte-identical=True, matches locked process records=True (manifest 8961a1f3ef7f328d...)

## S1.1 (verified)
- task: BPMN input + Process Record schema
- code: src/bpc_hybrid/stage1_process.py (parse + validate)
- schema: configs/schemas/process_record.schema.json (process_record@1.0.0)
- fixtures: tests/fixtures/stage1/s11_branch_parallel.bpmn, tests/fixtures/stage1/s14_cycle_unreachable.bpmn
- tests: tests/test_s1_1_s1_4_stage1_structural.py (contract freeze, malformed XML, duplicate id, DOCTYPE, fail-closed)
- met DoD: schema, fixtures, validator

## S1.2 (verified)
- task: activity/event/gateway/flow/lane parsing
- code: src/bpc_hybrid/stage1_process.py (ACTIVITY_TYPES/EVENT_TYPES/GATEWAY_TYPES, pools/lanes/sequence flows)
- schema: process_record.schema.json (pools/lanes/activities/events/gateways/sequence_flows)
- fixtures: tests/fixtures/stage1/s11_branch_parallel.bpmn
- tests: test_s1_1_s1_4_stage1_structural.py (branch/parallel/condition/is_default)
- met DoD: deterministic stable output on test BPMNs, 7/7 GDPR files double-run byte-identical (s1_1_s1_4_determinism_v1)

## S1.3 (partial)
- task: actor/action/object label parsing
- code: src/bpc_hybrid/stage1_label_semantics.py (P0 raw-only; P1 surface split)
- schema: configs/schemas/stage1_label_semantics.schema.json
- fixtures: tests/fixtures/stage1/s13_label_edge_cases.bpmn
- tests: tests/test_s1_3_stage1_label_semantics.py (P0 no-inference, P1 edge cases, stable hash)
- met DoD: P0 raw-only sidecar, P1 surface split sidecar
- gaps: P2 label semantics not implemented (DoD 'P0/P1/P2 replaceable runs' partially met); actor/action/object remain machine candidates, never Gold

## S1.4 (verified)
- task: control flow and reachability
- code: src/bpc_hybrid/stage1_process.py (control_flow 12-key block)
- schema: process_record.schema.json control_flow (direct_edges/reachable_pairs/order_relations/branching/parallel/cycle/unreachable)
- fixtures: tests/fixtures/stage1/s14_cycle_unreachable.bpmn, tests/fixtures/stage1/s11_branch_parallel.bpmn
- tests: test_s1_1_s1_4_stage1_structural.py (cycle, unreachable, parallel split/join, order relations)
- met DoD: branch/parallel/order tests pass, reachability/cycle/unreachable fail-closed

## Boundaries
- actor_action_object_are_machine_candidates_only: True
- stage3_gold_not_used_to_tune_stage1: True
- no_human_decision_inferred: True
