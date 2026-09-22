# Stage 3 binding annotation proposal：人工审核 checklist

- proposal：`data/development/stage3_synth/stage3_binding_annotation_proposal_v1.json`
- report copy：`outputs/reports/stage3_binding_annotation_proposal_v1.json`
- blank surface（未修改）：`data/development/stage3_synth/stage3_binding_annotation_blank_v1.json`
- status：`proposal_awaiting_human_review`
- 这不是 Gold；不要将 proposal 直接当作 decision fields。

## 审核总览

- pairs：30
- by rule：{'article15': 4, 'article16': 4, 'article17': 6, 'article20': 4, 'article22': 6, 'article33': 6}
- by type：{'incorrect_actor': 10, 'missing_action': 10, 'out_of_order': 10}
- action candidate present / null：27 / 3
- action low-confidence (<0.50)：8
- actor candidate present：30
- actor low-confidence (<0.50)：11
- actor/lane owner match：19 / 30
- order pairs applicable / proposed：10 / 10

## Proposal 字段 -> blank decision 字段

| proposal 字段 | 对应 blank 字段 | 审核动作 |
|---|---|---|
| `action_binding_proposal.rule_action_id` | `decision_action_id` | 确认该 action 是 target activity 所执行的规则动作；不确定则拒绝。 |
| `actor_binding_proposal.rule_actor_id` | `decision_actor_id` | 确认 actor 合法执行该 action；若 Rule Record 没有 actor span，需要人工处理，不得由 proposal 自动补写。 |
| `actor_binding_proposal.candidate_lane` | `decision_expected_lane` | 确认它是 control BPMN 中 target activity 的 lane id/name。 |
| `order_relation_proposal.before_activity` | `decision_order_before_action_id`（需再映射到 rule action） | 确认 control BPMN 的顺序；再把 before activity 对应的 action 填入。 |
| `order_relation_proposal.after_activity` | `decision_order_after_action_id`（需再映射到 rule action） | 确认 control BPMN 的顺序；再把 after activity 对应的 action 填入。 |

## 审核步骤

1. 打开 proposal JSON，确认 `safety.blank_modified=false`、`safety.benchmark_modified=false`、`safety.gold_created=false`。
2. 对每个 pair：先看 control BPMN 中 target activity 是否存在、位于哪个 lane；再看 action proposal 是否与 target activity 的 name/语义/BPMN 行为一致。
3. 对 action proposal 为 null 或 confidence < 0.50 的项，必须人工判断是否可以绑定；若不能，保持 null 或补新的合法标注，不要强行接受 proposal。
4. 对 actor proposal：检查 actor 文本是否为 Rule Record 中真的 actor span，并检查它是否与 control BPMN 的 process participant/lane owner 一致；标记 `actor_lane_owner_mismatch` 的项需要重点裁决。
5. 对 out_of_order：检查 `order_relation_proposal.before_activity` / `after_activity` 在 control BPMN 中确有顺序，并确认 variant 反序；然后把两个 activity 对应的 rule action id 填入 blank 的 order 字段。
6. 最后只在 human-filled decision file 中写决定，并保持 `review_state` 为 `reviewed` 或 `adjudicated`。

## 需重点复审的项

| pair | type | target activity | action candidate | actor candidate | flags |
|---|---|---|---|---|---|
| syn_incorrect_actor_01 | incorrect_actor | Retrieve breached subjects | gdpr_article33_s004.c1.action.1 (0.45) | gdpr_article33_s001.c1.actor.1 (0.70) | low_confidence_action, order_not_applicable |
| syn_incorrect_actor_03 | incorrect_actor | Retrieve identity and contact details | null (0.00) | gdpr_article22_s005.c1.actor.1 (0.70) | null_action_candidate, order_not_applicable |
| syn_incorrect_actor_05 | incorrect_actor | Retrieve elaborations | gdpr_article15_s001.c2.action.1 (0.45) | gdpr_article15_s001.c2.actor.1 (0.35) | low_confidence_action, low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_incorrect_actor_06 | incorrect_actor | Retrieve available data of the data subject | gdpr_article20_s001.c1.action.1 (0.60) | gdpr_article20_s001.c1.actor.1 (0.35) | low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_incorrect_actor_07 | incorrect_actor | Communicate data and elaborations | gdpr_article20_s001.c2.action.1 (0.65) | gdpr_article20_s001.c2.actor.1 (0.35) | low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_incorrect_actor_10 | incorrect_actor | Rectify data | gdpr_article16_s001.c1.action.2 (0.90) | gdpr_article16_s001.c1.actor.1 (0.35) | low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_missing_action_01 | missing_action | Retrieve breached subjects | gdpr_article33_s004.c1.action.1 (0.45) | gdpr_article33_s001.c1.actor.1 (0.70) | low_confidence_action, order_not_applicable |
| syn_missing_action_02 | missing_action | Retrieve breached data | gdpr_article33_s004.c1.action.1 (0.45) | gdpr_article33_s001.c1.actor.1 (0.70) | low_confidence_action, order_not_applicable |
| syn_missing_action_07 | missing_action | Check if withdrawn data are relevant | null (0.00) | gdpr_article17_s001.c2.actor.1 (0.70) | null_action_candidate, order_not_applicable |
| syn_missing_action_08 | missing_action | Communicate the rectification  | gdpr_article16_s001.c1.action.2 (0.40) | gdpr_article16_s001.c1.actor.1 (0.35) | low_confidence_action, low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_missing_action_09 | missing_action | Communicate data and elaborations | gdpr_article20_s001.c2.action.1 (0.65) | gdpr_article20_s001.c2.actor.1 (0.35) | low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_missing_action_10 | missing_action | Rectify data | gdpr_article16_s001.c1.action.2 (0.90) | gdpr_article16_s001.c1.actor.1 (0.35) | low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_out_of_order_01 | out_of_order | Retrieve breached subjects | gdpr_article33_s004.c1.action.1 (0.45) | gdpr_article33_s001.c1.actor.1 (0.70) | low_confidence_action |
| syn_out_of_order_02 | out_of_order | Retrieve breached data | gdpr_article33_s004.c1.action.1 (0.45) | gdpr_article33_s001.c1.actor.1 (0.70) | low_confidence_action |
| syn_out_of_order_03 | out_of_order | Retrieve identity and contact details | null (0.00) | gdpr_article22_s005.c1.actor.1 (0.70) | null_action_candidate |
| syn_out_of_order_05 | out_of_order | Retrieve available data of the data subject | gdpr_article15_s001.c1.action.1 (0.50) | gdpr_article15_s001.c1.actor.1 (0.35) | low_confidence_actor, actor_lane_owner_mismatch |
| syn_out_of_order_06 | out_of_order | Retrieve available data of the data subject | gdpr_article20_s001.c1.action.1 (0.60) | gdpr_article20_s001.c1.actor.1 (0.35) | low_confidence_actor, actor_lane_owner_mismatch |
| syn_out_of_order_09 | out_of_order | Rectify data | gdpr_article16_s001.c1.action.2 (0.90) | gdpr_article16_s001.c1.actor.1 (0.35) | low_confidence_actor, actor_lane_owner_mismatch |
| syn_out_of_order_10 | out_of_order | Retrieve elaborations | gdpr_article15_s001.c2.action.1 (0.45) | gdpr_article15_s001.c2.actor.1 (0.35) | low_confidence_action, low_confidence_actor, actor_lane_owner_mismatch |

## 全量审核表

| pair | type | rule | target activity | action proposal | actor proposal | order proposal | flags |
|---|---|---|---|---|---|---|---|
| syn_incorrect_actor_01 | incorrect_actor | article33 | Retrieve breached subjects | gdpr_article33_s004.c1.action.1 (0.45) | gdpr_article33_s001.c1.actor.1 @ sid-4035AA0F-2D62-46AC-A369-4151026920A3 (0.70) | n/a (0.00) | low_confidence_action, order_not_applicable |
| syn_incorrect_actor_02 | incorrect_actor | article33 | Handle delay | gdpr_article33_s002.c1.action.1 (0.85) | gdpr_article33_s001.c1.actor.1 @ sid-4035AA0F-2D62-46AC-A369-4151026920A3 (0.70) | n/a (0.00) | order_not_applicable |
| syn_incorrect_actor_03 | incorrect_actor | article22 | Retrieve identity and contact details | null (0.00) | gdpr_article22_s005.c1.actor.1 @ sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB (0.70) | n/a (0.00) | null_action_candidate, order_not_applicable |
| syn_incorrect_actor_04 | incorrect_actor | article22 | Add "existence of the right to withdraw" | gdpr_article22_s005.c1.action.1 (0.75) | gdpr_article22_s005.c1.actor.1 @ sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB (0.90) | n/a (0.00) | order_not_applicable |
| syn_incorrect_actor_05 | incorrect_actor | article15 | Retrieve elaborations | gdpr_article15_s001.c2.action.1 (0.45) | gdpr_article15_s001.c2.actor.1 @ sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F (0.35) | n/a (0.00) | low_confidence_action, low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_incorrect_actor_06 | incorrect_actor | article20 | Retrieve available data of the data subject | gdpr_article20_s001.c1.action.1 (0.60) | gdpr_article20_s001.c1.actor.1 @ sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F (0.35) | n/a (0.00) | low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_incorrect_actor_07 | incorrect_actor | article20 | Communicate data and elaborations | gdpr_article20_s001.c2.action.1 (0.65) | gdpr_article20_s001.c2.actor.1 @ sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F (0.35) | n/a (0.00) | low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_incorrect_actor_08 | incorrect_actor | article17 | Stop using withdrawn data | gdpr_article17_s001.c2.action.1 (0.60) | gdpr_article17_s001.c2.actor.1 @ sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C (0.90) | n/a (0.00) | order_not_applicable |
| syn_incorrect_actor_09 | incorrect_actor | article17 | Communicate the withdraw | gdpr_article17_s008.c1.action.2 (0.75) | gdpr_article17_s008.c1.actor.1 @ sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C (0.75) | n/a (0.00) | order_not_applicable |
| syn_incorrect_actor_10 | incorrect_actor | article16 | Rectify data | gdpr_article16_s001.c1.action.2 (0.90) | gdpr_article16_s001.c1.actor.1 @ sid-95D07626-A357-422E-830F-B1E57917DB74 (0.35) | n/a (0.00) | low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_missing_action_01 | missing_action | article33 | Retrieve breached subjects | gdpr_article33_s004.c1.action.1 (0.45) | gdpr_article33_s001.c1.actor.1 @ sid-4035AA0F-2D62-46AC-A369-4151026920A3 (0.70) | n/a (0.00) | low_confidence_action, order_not_applicable |
| syn_missing_action_02 | missing_action | article33 | Retrieve breached data | gdpr_article33_s004.c1.action.1 (0.45) | gdpr_article33_s001.c1.actor.1 @ sid-4035AA0F-2D62-46AC-A369-4151026920A3 (0.70) | n/a (0.00) | low_confidence_action, order_not_applicable |
| syn_missing_action_03 | missing_action | article22 | Add "existence of the right to withdraw" | gdpr_article22_s005.c1.action.1 (0.75) | gdpr_article22_s005.c1.actor.1 @ sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB (0.90) | n/a (0.00) | order_not_applicable |
| syn_missing_action_04 | missing_action | article22 | Add "existence of the right to rectify of personal data" | gdpr_article22_s005.c1.action.1 (0.70) | gdpr_article22_s005.c1.actor.1 @ sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB (0.90) | n/a (0.00) | order_not_applicable |
| syn_missing_action_05 | missing_action | article15 | Communicate data and elaborations | gdpr_article15_s010.c1.action.1 (0.70) | gdpr_article15_s010.c1.actor.1 @ sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F (0.90) | n/a (0.00) | order_not_applicable |
| syn_missing_action_06 | missing_action | article17 | Stop running BPs using withdrawn data | gdpr_article17_s008.c1.action.1 (0.55) | gdpr_article17_s008.c1.actor.1 @ sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C (0.90) | n/a (0.00) | order_not_applicable |
| syn_missing_action_07 | missing_action | article17 | Check if withdrawn data are relevant | null (0.00) | gdpr_article17_s001.c2.actor.1 @ sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C (0.70) | n/a (0.00) | null_action_candidate, order_not_applicable |
| syn_missing_action_08 | missing_action | article16 | Communicate the rectification  | gdpr_article16_s001.c1.action.2 (0.40) | gdpr_article16_s001.c1.actor.1 @ sid-95D07626-A357-422E-830F-B1E57917DB74 (0.35) | n/a (0.00) | low_confidence_action, low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_missing_action_09 | missing_action | article20 | Communicate data and elaborations | gdpr_article20_s001.c2.action.1 (0.65) | gdpr_article20_s001.c2.actor.1 @ sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F (0.35) | n/a (0.00) | low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_missing_action_10 | missing_action | article16 | Rectify data | gdpr_article16_s001.c1.action.2 (0.90) | gdpr_article16_s001.c1.actor.1 @ sid-95D07626-A357-422E-830F-B1E57917DB74 (0.35) | n/a (0.00) | low_confidence_actor, actor_lane_owner_mismatch, order_not_applicable |
| syn_out_of_order_01 | out_of_order | article33 | Retrieve breached subjects | gdpr_article33_s004.c1.action.1 (0.45) | gdpr_article33_s001.c1.actor.1 @ sid-4035AA0F-2D62-46AC-A369-4151026920A3 (0.70) | Retrieve breached subjects -> Notify national authority (1.00) | low_confidence_action |
| syn_out_of_order_02 | out_of_order | article33 | Retrieve breached data | gdpr_article33_s004.c1.action.1 (0.45) | gdpr_article33_s001.c1.actor.1 @ sid-4035AA0F-2D62-46AC-A369-4151026920A3 (0.70) | Retrieve breached data -> Retrieve breached subjects (1.00) | low_confidence_action |
| syn_out_of_order_03 | out_of_order | article22 | Retrieve identity and contact details | null (0.00) | gdpr_article22_s005.c1.actor.1 @ sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB (0.70) | Retrieve identity and contact details -> Collect consent information (1.00) | null_action_candidate |
| syn_out_of_order_04 | out_of_order | article22 | Check if legitimate interests are presents | gdpr_article22_s005.c1.action.1 (0.80) | gdpr_article22_s005.c1.actor.1 @ sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB (0.90) | Check if legitimate interests are presents -> Collect consent information (1.00) |  |
| syn_out_of_order_05 | out_of_order | article15 | Retrieve available data of the data subject | gdpr_article15_s001.c1.action.1 (0.50) | gdpr_article15_s001.c1.actor.1 @ sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F (0.35) | Retrieve available data of the data subject -> Communicate data and elaborations (1.00) | low_confidence_actor, actor_lane_owner_mismatch |
| syn_out_of_order_06 | out_of_order | article20 | Retrieve available data of the data subject | gdpr_article20_s001.c1.action.1 (0.60) | gdpr_article20_s001.c1.actor.1 @ sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F (0.35) | Retrieve available data of the data subject -> Communicate data and elaborations (1.00) | low_confidence_actor, actor_lane_owner_mismatch |
| syn_out_of_order_07 | out_of_order | article17 | Stop running BPs using withdrawn data | gdpr_article17_s008.c1.action.1 (0.55) | gdpr_article17_s008.c1.actor.1 @ sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C (0.90) | Stop running BPs using withdrawn data -> Stop using withdrawn data (1.00) |  |
| syn_out_of_order_08 | out_of_order | article17 | Stop using withdrawn data | gdpr_article17_s001.c2.action.1 (0.60) | gdpr_article17_s001.c2.actor.1 @ sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C (0.90) | Stop using withdrawn data -> Communicate the withdraw (1.00) |  |
| syn_out_of_order_09 | out_of_order | article16 | Rectify data | gdpr_article16_s001.c1.action.2 (0.90) | gdpr_article16_s001.c1.actor.1 @ sid-95D07626-A357-422E-830F-B1E57917DB74 (0.35) | Rectify data -> Communicate the rectification  (1.00) | low_confidence_actor, actor_lane_owner_mismatch |
| syn_out_of_order_10 | out_of_order | article15 | Retrieve elaborations | gdpr_article15_s001.c2.action.1 (0.45) | gdpr_article15_s001.c2.actor.1 @ sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F (0.35) | Retrieve elaborations -> Communicate data and elaborations (1.00) | low_confidence_action, low_confidence_actor, actor_lane_owner_mismatch |

## 审核签核

| 项目 | 结果 |
|---|---|
| proposal 是否只作为候选使用 | [ ] 是 |
| 是否发现无依据的 binding | [ ] 无 / [ ] 有（在 notes 写明） |
| 是否已把人工决定写入独立 decision file | [ ] 是 |
| 审核人 |  |
| 日期 |  |

> 本 checklist 只用于人工审核；proposal 不会被自动导入 blank surface，也不会生成 Gold。
