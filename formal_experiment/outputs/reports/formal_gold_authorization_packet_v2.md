# Formal Gold 用户授权包 v2（DRY-RUN，未修改任何合同）

- packet_id: formal_gold_authorization_packet_v2；dry_run=true；contract_not_modified=true；contract sha256=7d1ad775da5831f8...

## 拟议修改（JSON Pointer，完整 before/after）
- `/stage3/status`
  - before: `pending_final_subset_configuration_and_violation_gold_lock`
  - after : `locked`
  - 依据: S3.1-S3.3 data governance complete (7 BPMN byte-exact, matching/violation Gold 58/58 frozen, s32_s33_gold_annotation_freeze_v1.manifest.json); the contract notes the lock requires 'final subset configuration and violation Gold lock', which the frozen annotation provides
- `/formal_gold_publication_gate/status`
  - before: `blocked_pending_route_data_stage3_re_lock`
  - after : `ready_for_formal_gold_publication`
  - 依据: Event 23 requires an exact match against allowed_publication_statuses; the flip is a user-authorized contract change recorded in the audit log
- `/stage2_dataset/freeze_policy`
  - before: `The Sun modality development schema, 2,831-row analysis population, quarantine policy, and project-reconstructed split are locked by the S2.1-D machine gate. Do not write formal input or Gold: the independently reconstructed phrase Gold still requires human freeze, and the route, Stage 3, freeze/publication policy, and exact publication-status whitelist must each be re-locked separately.`
  - after : `The Sun modality development schema, 2,831-row analysis population, quarantine policy, and project-reconstructed split are locked by the S2.1-D machine gate. The independently reconstructed phrase Gold is frozen (150/150 adjudicated, freeze_ready=True, restored 2026-08-06). The route (locked 2026-08-06), Stage 3 (locked 2026-08-08 by user authorization), the freeze/publication policy (re-locked 2026-08-08) and the exact publication-status whitelist are all satisfied. Formal Gold publication is authorized by the user; formal Oracle and final experiments remain gated by S1.7/S2.13 and the missing true Gold Rule/Process Records (see s37_oracle_readiness_v1.json). Prohibitions are unchanged: do not write formal input or Gold outside the authorized publication action; predictions, manifests and results remain no-overwrite; the modality dataset stays development-only with redistribution/publication forbidden.`
  - 依据: required_preconditions demand the freeze policy be re-evaluated and explicitly re-locked with no 'reopened_pending_*' status anywhere on the formal Gold publication path; governance content and prohibitions are preserved

## 临时副本门禁校验（等价机器检查）
- before: formal_gold_publication_ready=False
- after : formal_gold_publication_ready=True
- preconditions(after): {"route.status==locked": true, "stage2_dataset.status==locked_for_human_review": true, "stage3.status==locked": true, "freeze_policy re-locked (no reopened_pending_*)": true, "publication gate exact whitelist match": true}

## 预期 blocker
- 消除: ["formal_gold_publication_paused (publication gate enters whitelist)", "stage3_benchmark_not_locked (stage3.status becomes locked)"]
- 保留: ["final_experiment_not_ready", "formal_methods_not_ready", "formal_capsule_not_frozen"]

## formal Gold publication 与方法正确性是不同门禁
- formal Gold publication and method correctness are DIFFERENT gates: the Stage 3 data/Gold lock can be satisfied now, while the formal Oracle remains blocked by S1.7/S2.13 and the missing true Gold Rule/Process Records (s37_oracle_readiness_v1.json); publication does NOT imply method readiness

## 回滚
- git revert 合同变更 commit 或恢复合同 blob；重跑 audit 即回到 blocked

## 授权句

> I authorize the machine-contract change that sets /stage3/status to 'locked', replaces /stage2_dataset/freeze_policy with the re-locked policy (governance content preserved), and sets /formal_gold_publication_gate/status to 'ready_for_formal_gold_publication', thereby enabling formal Gold publication (dry-run packet formal_gold_authorization_packet_v2).

