# Stage 3 候选判定完成记录

2026-09-23：用户授权由 AI 直接根据候选处理。本批补充判定已完成，没有待用户再次审核的条目。
机器结果：`data/development/stage3_synth/stage3_binding_resolved_reference_v1.json`。原人工决定逐项保留；补充结论标为 AI 判断，未生成 Gold。

## 已落定的处理

- 25 个已有 action 对应保留；另外 5 个空值不再作为待办：2 个候选集无对应、1 个接收者不同、1 个属于条件检查、1 个通知/更正动作不同。
- 22 个已有 actor 对应保留；7 项由原文中 controller 相对方角色推断执行者为 Data Controller；另 1 项只确认流程执行者，因缺少法规通知动作，不声称该义务的 actor 对应。
- 10 项顺序均决定只保留流程关系：4 项没有严格法规顺序依据、2 项落在同一规则动作、4 项缺少合适动作端点。不生成伪造的法规 before/after。
- 所有 null 均带有明确判定类型、原因和来源；不创建原 Gold 中不存在的 action/actor ID。

## 7 个去重组合的结论

| 规则 | 活动 | action 处理 | actor 处理 | 涉及 pair |
|---|---|---|---|---|
| article22 | Retrieve identity and contact details | 当前候选无对应 | 保留人工选择 | syn_incorrect_actor_03, syn_out_of_order_03 |
| article20 | Retrieve available data of the data subject | 保留人工选择 | AI 判为 Controller 执行；保留 data subject 权利主体 | syn_incorrect_actor_06, syn_out_of_order_06 |
| article20 | Communicate data and elaborations | 保留人工选择 | AI 判为 Controller 执行；保留 data subject 权利主体 | syn_incorrect_actor_07, syn_missing_action_09 |
| article17 | Communicate the withdraw | 拒绝：通知对象不同 | 保留人工选择 | syn_incorrect_actor_09 |
| article16 | Rectify data | 保留人工选择 | AI 判为 Controller 执行；保留 data subject 权利主体 | syn_incorrect_actor_10, syn_missing_action_10, syn_out_of_order_09 |
| article17 | Check if withdrawn data are relevant | 条件检查；不等同执行删除 | 保留人工选择 | syn_missing_action_07 |
| article16 | Communicate the rectification | 拒绝：通知不等同实际更正 | 仅确认流程执行者 Controller | syn_missing_action_08 |

## 逐项理由

### article22 / Retrieve identity and contact details

当前 article22 候选中没有收集身份及联系方式的动作。宽泛的保障措施不能据此指定为该活动；按当前候选集判为无对应。

### article20 / Retrieve available data of the data subject

保留 data subject 为接收数据的权利主体；将已持有数据的 controller 判为检索/提供数据的执行方。不是将 receive 的主语改成 controller。

### article20 / Communicate data and elaborations

以直接传输中 from one controller 的源端控制者对应发送方 Data Controller；data subject 仍为权利主体，Third Party 对应另一控制者沿用已接受的候选假设。

### article17 / Communicate the withdraw

BPMN 通知的接收者为 Data subject；原候选要求 inform controllers。对象明确不同，拒绝该候选，当前规则集合内无合适替代。

### article16 / Rectify data

保留 data subject 为权利主体；依据 obtain from the controller 将 controller 判为实现更正的相对执行方，并与 Data Controller 对应。该关系是 AI 补充推断。

### article17 / Check if withdrawn data are relevant

检查数据相关性归为删除流程的适用条件检查，可关联 erase personal data 的背景，但不等同于执行删除；action_id 保留空并明确类型。

### article16 / Communicate the rectification

Rectify data 与 Communicate the rectification 是独立活动；通知数据主体不能替代实际更正。当前 article16 动作候选无独立通知项，判为无对应。
确认此通知节点属于 Data Controller；当前 article16 无对应通知动作，故只确认流程执行者，不声明已获得该通知义务的法规 actor 绑定。

## 10 项顺序的结论

| pair | 决定 | 理由 |
|---|---|---|
| syn_out_of_order_01 | 仅流程顺序 | 描述泄露与通知不是“检索主体必须先于首次通知”的明文动作对；s008 还允许分阶段补充信息，不采纳该严格法规顺序。 |
| syn_out_of_order_02 | 仅流程顺序 | 两个检索活动均关联同一个 describe 动作；不能生成 action 先于自身的关系。 |
| syn_out_of_order_03 | 仅流程顺序 | 身份联系方式检索和收集同意没有两个对应的法规动作候选，流程先后不能补成法规顺序。 |
| syn_out_of_order_04 | 仅流程顺序 | 保障合法利益与基于同意的条件，不构成“先检查合法利益再收集同意”的两个法规动作及强制顺序。 |
| syn_out_of_order_05 | 仅流程顺序 | 获取访问权与提供副本描述权利和履行行为；原文没有指定两个 BPMN 步骤的先后，保留流程关系。 |
| syn_out_of_order_06 | 仅流程顺序 | 接收数据和直接传输是不同实现安排；所给原文没有要求先执行本流程的检索活动再通信。 |
| syn_out_of_order_07 | 仅流程顺序 | 停止业务流程与停止使用都只是 erase 的支持步骤候选，缺少两个不同的法规动作，不能填 A 先于 A。 |
| syn_out_of_order_08 | 仅流程顺序 | 后端通知数据主体与 inform controllers 接收者不符；没有正确的通知动作端点。 |
| syn_out_of_order_09 | 仅流程顺序 | 有更正动作，但当前 article16 动作集合没有更正后通知的端点，不能据流程连线增加法规顺序。 |
| syn_out_of_order_10 | 仅流程顺序 | 检索处理信息和对外提供数据之间的先后来自流程实现，不是当前原文明确的两个法规动作次序。 |

## 使用范围

这是参考资料可见、目标 activity 可见的 AI 补充判定，不是盲测预测，不是正式 Gold。
不作为自动 Ours 的输入，不自动导入 oracle 或任何评价器；当前任务没有待人工操作。
只读查阅了用户此次明确要求的归档候选成员，未解压、恢复或重开旧批次。
判定以当前给定规则与候选集合为范围；“没有支持的对应/顺序”不等于声称全部法规中绝无相关要求。

## 原文定位（现有 Gold 记录，供解释字段）

### gdpr_article16_s001

The data subject shall have the right to obtain from the controller without undue delay the rectification of inaccurate personal data concerning him or her.

- actions: gdpr_article16_s001.c1.action.1 = obtain from the controller; gdpr_article16_s001.c1.action.2 = the rectification of inaccurate personal data concerning him or her
- actors: gdpr_article16_s001.c1.actor.1 = The data subject

### gdpr_article16_s002

Taking into account the purposes of the processing, the data subject shall have the right to have incomplete personal data completed, including by means of providing a supplementary statement.

- actions: gdpr_article16_s002.c1.action.1 = have incomplete personal data completed
- actors: gdpr_article16_s002.c1.actor.1 = the data subject

### gdpr_article20_s001

The data subject shall have the right to receive the personal data concerning him or her, which he or she has provided to a controller, in a structured, commonly used and machine-readable format and have the right to transmit those data to another controller without hindrance from the controller to which the personal data have been provided, where the processing is based on consent pursuant to point (a) of Article 6(1) or point (a) of Article 9(2) or on a contract pursuant to point (b) of Article 6(1); and the processing is carried out by automated means.

- actions: gdpr_article20_s001.c1.action.1 = receive the personal data concerning him or her
- actors: gdpr_article20_s001.c1.actor.1 = The data subject
- actions: gdpr_article20_s001.c2.action.1 = transmit those data to another controller
- actors: gdpr_article20_s001.c2.actor.1 = The data subject

### gdpr_article20_s002

In exercising his or her right to data portability pursuant to paragraph 1, the data subject shall have the right to have the personal data transmitted directly from one controller to another, where technically feasible.

- actions: gdpr_article20_s002.c1.action.1 = have the personal data transmitted directly from one controller to another
- actors: gdpr_article20_s002.c1.actor.1 = the data subject

### gdpr_article22_s005

In the cases referred to in points (a) and (c) of paragraph 2, the data controller shall implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests, at least the right to obtain human intervention on the part of the controller, to express his or her point of view and to contest the decision.

- actions: gdpr_article22_s005.c1.action.1 = implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests
- actors: gdpr_article22_s005.c1.actor.1 = the data controller

### gdpr_article17_s001

The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay and the controller shall have the obligation to erase personal data without undue delay where one of the following grounds applies.

- actions: gdpr_article17_s001.c1.action.1 = obtain from the controller the erasure of personal data concerning him or her
- actors: gdpr_article17_s001.c1.actor.1 = The data subject
- actions: gdpr_article17_s001.c2.action.1 = erase personal data
- actors: gdpr_article17_s001.c2.actor.1 = the controller

### gdpr_article17_s003

The data subject withdraws consent on which the processing is based according to point (a) of Article 6(1), or point (a) of Article 9(2), and where there is no other legal ground for the processing.

- actions: []
- actors: []

### gdpr_article17_s008

Where the controller has made the personal data public and is obliged pursuant to paragraph 1 to erase the personal data, the controller, taking account of available technology and the cost of implementation, shall take reasonable steps, including technical measures, to inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data.

- actions: gdpr_article17_s008.c1.action.1 = take reasonable steps; gdpr_article17_s008.c1.action.2 = inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data
- actors: gdpr_article17_s008.c1.actor.1 = the controller

## 来源哈希

| 来源 | SHA-256 |
|---|---|
| data/development/stage3_synth/stage3_binding_human_decisions_v1.json | 1434da07946484e7bae95e7af959930d3f154c375df733ae146bbdd54191ce9f |
| data/gold/stage3/gdpr7_gold_rule_records_v1.json | 7cf896abdb6e420e46efd297a8e183bcdc4c15834aa9567eb88d1af60eec627a |
| data/predictions/gdpr7_direct_llm_v1/predictions.json | b625692d1e4e85b22f0c2e428a46a7c6cd49a2cc4b77a10f6c8e8d25adec50a1 |
| data/development/stage3_synth/stage3_paired_benchmark_v1.json | 8205371ee71af75ae9179481fe87e972e2e70650c0985661bbff8d183f1a3fc5 |
