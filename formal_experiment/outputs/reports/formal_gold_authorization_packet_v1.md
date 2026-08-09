# Formal Gold 用户授权包（DRY-RUN，未修改任何合同）

- packet_id: formal_gold_authorization_packet_v1；dry_run=true；contract_not_modified=true

## 当前 audit
- errors=0；blockers=["formal_gold_publication_paused", "final_experiment_not_ready", "formal_methods_not_ready", "formal_capsule_not_frozen", "stage3_benchmark_not_locked"]
- integrity_pass=true；human_review_freeze_ready=true (150/150)；formal_gold_publication_ready=false；final_experiment_ready=false

## 当前机器合同状态
- route.status = `locked`（2026-08-06 用户授权重锁，B0-R2 verified + method_conformance 翻转 + supplement hash 匹配）
- stage2_dataset.status = `locked_for_human_review`（modality 2,831 行 verified + phrase Gold 150/150 freeze）
- stage3.status = `pending_final_subset_configuration_and_violation_gold_lock`
- freeze_policy = 尚未重锁（现状：The Sun modality development schema, 2,831-row analysis popu...）
- formal_gold_publication_gate.status = `blocked_pending_route_data_stage3_re_lock`；allowed=["ready_for_formal_gold_publication"]

## 冻结凭证
- Stage 2：150/150 adjudicated（Layer E v2，2026-08-06 恢复，audit human_review_freeze_ready=true）
- Stage 3：58/58 冻结 manifest `outputs/reports/s32_s33_gold_annotation_freeze_v1.manifest.json` (sha f37ae1164b19...)

## 拟议合同修改（before -> after）
- `stage3.status`：`pending_final_subset_configuration_and_violation_gold_lock...` -> `locked`；依据：S3.1-S3.3 data governance complete (7 BPMN byte-exact + matching/violation Gold annotation frozen 58/58, s32_s33_gold_annotation_freeze_v1.manifest.json); the contract notes the lock requires 'final subset configuration and violation Gold lock', which the frozen annotation provides
- `formal_gold_publication_gate.status`：`blocked_pending_route_data_stage3_re_lock...` -> `ready_for_formal_gold_publication`；依据：exact whitelist match to allowed_publication_statuses is required by Event 23; the flip is a user-authorized contract change recorded in the audit log
- `stage2_dataset.freeze_policy`：`The Sun modality development schema, 2,831-row analysis popu...` -> `re-evaluated and explicitly re-locked (no 'reopened_pending_*' status anywhere on the formal Gold publication path)`；依据：required_preconditions demand the freeze policy be re-evaluated and explicitly re-locked

## 翻转后预期 blockers
- 消除：["formal_gold_publication_paused (publication gate enters whitelist)", "stage3_benchmark_not_locked (stage3.status becomes locked)"]
- 保留：["final_experiment_not_ready (three methods + Stage 3 formal run not done)", "formal_methods_not_ready (formal shared capsule not frozen)", "formal_capsule_not_frozen (shared comparison capsule pending)"]

## formal Oracle 仍被阻止
- S1.7（Stage 1 冻结）未完成 -> 无真正 Gold Process Records；S2.13 未完成 -> formal capsule 未冻结
- 详见 s37_oracle_readiness_v1.json：S3.7 formal Oracle blocked_on_s1_7_s2_13

## 回滚
- git revert 合同变更 commit 或恢复合同 blob；重跑 audit 即回到 blocked 状态

## 授权句（用户可直接回复）

> I authorize the machine-contract change that sets stage3.status=locked, re-locks the freeze policy, and moves formal_gold_publication_gate.status into the allowed whitelist ['ready_for_formal_gold_publication'], thereby enabling formal Gold publication (dry-run packet formal_gold_authorization_packet_v1).

