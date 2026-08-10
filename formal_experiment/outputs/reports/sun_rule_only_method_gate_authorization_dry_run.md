# sun_rule_only method gate authorization (DRY-RUN, not applied)

- status: dry_run_not_applied
- proposed formal_status: ready
- candidate primary F1: 0.7186482580011335

## methods.json sun_rule_only diff (only this method)
### before
- formal_status: blocked_final_sun_stage2_reimplementation_required
- command_status: development_only_not_formal
### after (proposed)
- formal_status: ready
- command_status: formal_ready_candidate_authorized

## Binding hashes
- b0_config: 151c0cd2261075c1... (configs/models/estg150_b0_enhanced_s27_v10a.json)
- b0_runner: 6993956eadefd080... (scripts/run_estg150_b0_formal.py)
- formal_input_v2: 52a73aa1109970b6... (data/input/estg150_formal_inference_input_v2.json)
- gold_stage2: c31a514a6b58b640... (data/gold/stage2/estg150_formal_gold_v1.json)
- primary_evaluator_config: 352113b568c6075c... (configs/evaluation/sun_table8_literal_overlap_v2.json)
- strict_evaluator_config: 28ce332564c5d10d... (configs/stage2_evaluator_s210_v3.json)
- release_manifest_v2: 4a89ec2fb3e8317a... (outputs/reports/formal_benchmark_release_v2.manifest.json)
- candidate_manifest: 56ef81d7179ef6d1... (outputs/development/b0_r4_formal_candidate_v1/manifest.json)

## Formal run command (after authorization)
```
python scripts/run_estg150_b0_formal.py --runtime-home D:\environment\stanford-corenlp-4.5.10 --output-dir outputs/development/b0_r4_formal_candidate_v2_authorized && python scripts/audit_project.py
```

## Expected audit changes
- {'formal_methods_not_ready': 'sun_rule_only moves out of the non-ready set', 'final_experiment_not_ready': 'remains present while sun_llm_fallback and direct_llm are not ready (their authorization is a separate decision)', 'methods_unexpectedly_ready': 'MUST NOT trigger: audit currently errors when ALL three methods are ready; with only sun_rule_only ready the non-ready set still has 2 members'}

## Rollback
- git revert of the authorization commit (methods.json only)
- restore configs/methods.json sun_rule_only formal_status to 'blocked_final_sun_stage2_reimplementation_required' and command_status to 'development_only_not_formal'; the candidate outputs under outputs/development are non-formal and need no rollback
