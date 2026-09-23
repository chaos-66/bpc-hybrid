# Stage 3 绑定参考数据与自动预测职责核对

日期：2026-09-23。只读分析；不是新审核批次，不是 Gold，不恢复已归档材料。
只读取活动区的最终人工决定、既有规则记录和 benchmark；不改任何决定或原始来源。

## 核对结果

- 30/30 项人工决定保持完成；25 个非空 action ID、22 个非空 actor ID 均存在于对应规则。
- 30 个目标 activity ID 与 30 个已选 lane ID 均存在于对应 control BPMN。
- 5 个空 action 合并为 4 个法规—活动组合；8 个空 actor 合并为 4 个组合；二者交集 1 个，合计 7 个组合。
- 原规则 Gold 与既有 Direct-LLM 输出的 order_relations 均为 0；已确认的 10 项顺序全部是 process-only。
- ID 存在只证明引用有效，不证明语义对应正确，也不代表允许将人工绑定用于预测。

## 哪些需要语义判断

以下表只定位现有空值及其来源，不撤销用户的既有确认，也不自动要求再次审核。
未来若建设绑定评测集，必须区分“有匹配”“经人工确认无匹配”“适用性不足/证据不足”；
已接受 null 本身不够区分后两种状态。完整标注不意味着每一格都必须存在正向匹配。

| 编号 | 规则 | BPMN 活动 | 空字段 | 涉及 pair |
|---|---|---|---|---|
| 1 | article22 | Retrieve identity and contact details | action | syn_incorrect_actor_03, syn_out_of_order_03 |
| 2 | article20 | Retrieve available data of the data subject | actor | syn_incorrect_actor_06, syn_out_of_order_06 |
| 3 | article20 | Communicate data and elaborations | actor | syn_incorrect_actor_07, syn_missing_action_09 |
| 4 | article17 | Communicate the withdraw | action | syn_incorrect_actor_09 |
| 5 | article16 | Rectify data | actor | syn_incorrect_actor_10, syn_missing_action_10, syn_out_of_order_09 |
| 6 | article17 | Check if withdrawn data are relevant | action | syn_missing_action_07 |
| 7 | article16 | Communicate the rectification | action/actor | syn_missing_action_08 |

### Action：先核对适用规则，不强配相似词

- article22 / Retrieve identity and contact details：当前 article22 动作记录没有该活动的直接同名要求；要确认关联条款是否充分，而非从剩余 ID 中随便选一个。
- article17 / Communicate the withdraw：需要区分撤回/删除流程中的通知对象和法规动作的对象。
- article17 / Check if withdrawn data are relevant：可能是判断适用条件的实现步骤，不能自动当成独立法规义务动作。
- article16 / Communicate the rectification：不能把流程中的通知步骤自动等同于法规中获得更正的权利。
以上是 AI 的问题定位，不是新增 Gold 裁决；后续有新依据时才提交最小补充项。

### Actor：权利主体与流程执行者不一定相同

article16、article20 的现有 actor 标注包括 data subject，已审流程执行者则为 Data Controller。
两者差异不能直接证明 Rule Gold 漏标。需要先约定字段是法规句子的权利主体，还是履行义务的执行者；
如确需额外的执行者关系，应新增有出处的角色/关系标注，不能为了与 lane 一致而改掉正确的原 span。
在这个定义澄清前，保持原 null，不自动创建 controller actor ID。

## 10 项流程顺序：不是 10 条已经证实遗漏的法规顺序

| pair | 规则 | 已确认的流程顺序 |
|---|---|---|
| syn_out_of_order_01 | article33 | Retrieve breached subjects → Notify national authority |
| syn_out_of_order_02 | article33 | Retrieve breached data → Retrieve breached subjects |
| syn_out_of_order_03 | article22 | Retrieve identity and contact details → Collect consent information |
| syn_out_of_order_04 | article22 | Check if legitimate interests are presents → Collect consent information |
| syn_out_of_order_05 | article15 | Retrieve available data of the data subject → Communicate data and elaborations |
| syn_out_of_order_06 | article20 | Retrieve available data of the data subject → Communicate data and elaborations |
| syn_out_of_order_07 | article17 | Stop running BPs using withdrawn data → Stop using withdrawn data |
| syn_out_of_order_08 | article17 | Stop using withdrawn data → Communicate the withdraw |
| syn_out_of_order_09 | article16 | Rectify data → Communicate the rectification |
| syn_out_of_order_10 | article15 | Retrieve elaborations → Communicate data and elaborations |

只有原文支持两个法规动作及其先后关系，才能新增法规顺序标签。控制流程的布局、技术依赖、
“without undue delay”等时限文字，都不能单独用来制造两个 action 的 before/after 关系。
当前只能保留为流程结构扰动诊断；不能将该表改称法规顺序 Gold，也不能只删除难例后宣称三类全覆盖。

## 程序职责核对

| 模块 | 当前事实 | 可用范围 |
|---|---|---|
| scripts/run_stage3_binding_oracle_v1.py | 直接使用人工 action/lane、指定 activity ID 和 order_pair；Direct Rule Record 的 ID 匹配只进诊断信息 | supplied-binding oracle 诊断，不是端到端 Ours |
| src/bpc_hybrid/sun_stage3/sun_scorer.py | 已有 _best_action_match、_best_actor_match 和 out_of_order 的端点匹配 | 现有自动匹配基础；本轮未重新评测 |
| src/bpc_hybrid/s3_action_matching_v3.py | 已有动作结构与候选匹配实现 | 开发实现，不等于新 30-pair 正式验证已完成 |
| src/bpc_hybrid/s3_semantic_grounding_v1.py | 已有 Top-K 自动动作 grounding；同时含旧 fallback 路径 | 仅记录代码存在；用户取消的规则先行 LLM fallback 不恢复 |

后续自动预测只能从待测 Rule Record、BPMN 和事先冻结的方法配置产生绑定；
人工绑定、mutation target、expected lane、order_pair 与违规答案由评测侧持有。
不得用 Gold action ID 的字符串相等代替预测 span 与参考 span 的对齐，也不得用这 30 对调参后称为独立测试。
不能因补完参考标注就自动宣称优于基线；还需要相同输入条件下的实际预测与冻结评价。

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
