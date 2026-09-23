# Stage 3 binding: final human approval packet v1

This packet contains only items that still require substantive human judgment. Mechanical conversions and human-confirmed fields are not included. For each option below, choose exactly one simple action:

- `ACCEPT` = accept the AI recommendation shown;
- `CHANGE TO <id>` = replace it with the id you specify;
- `N/A` = no legal binding is applicable.

Pairs requiring approval: 19 / 30.

---

## Pair `syn_incorrect_actor_03`

- rule: `article22`
- process: `gdpr_2_consent_to_use_the_data`
- target violation type: `incorrect_actor`
- regulation text: "The data subject shall have the right not to be subject to a decision based solely on automated processing, including profiling, which produces legal effects concerning him or her or similarly significantly affects him or her. Paragraph 1 shall not apply if the decision is necessary for entering into, or performance of, a contract between the data subject and a data controller. Paragraph 1 shall not apply if the decision is authorised by Union or Member State law to which the controller is subject and which also lays down suitable measures to safeguard the data subject's rights and freedoms and legitimate interests. or Paragraph 1 shall not apply if the decision is based on the data subject's explicit consent. In the cases referred to in points (a) and (c) of paragraph 2, the data controller shall implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests, at least the right to obtain human intervention on the part of the controller, to express his or her point of view and to contest the decision. Decisions referred to in paragraph 2 shall not be based on special categories of personal data referred to in Article 9(1), unless point (a) or (g) of Article 9(2) applies and suitable measures to safeguard the data subject's rights and freedoms and legitimate interests are in place."
- target BPMN activity: `sid-17C48064-C83F-44C6-998A-8DB69B109E8D` "Retrieve identity and contact details" (lane `sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB` "")
- predecessors: sid-AB0B4F0A-B4F9-4379-9225-B4F27DFD6BC6 ()
- successors: sid-BB1531A1-D98A-4DB2-92CB-0DEE27831568 ()

### Action binding (unresolved)

Relevant Direct-LLM Rule Record action candidates:

* `gdpr_article22_s001.c1.action.p01`: "have the right not to be subject to a decision" (modality=obligation, sample=gdpr_article22_s001)
* `gdpr_article22_s002.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article22_s002)
* `gdpr_article22_s003.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article22_s003)
* `gdpr_article22_s004.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article22_s004)
* `gdpr_article22_s005.c1.action.p01`: "implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests" (modality=obligation, sample=gdpr_article22_s005)
* `gdpr_article22_s005.c1.action.p02`: "obtain human intervention on the part of the controller" (modality=obligation, sample=gdpr_article22_s005)
* `gdpr_article22_s005.c1.action.p03`: "express his or her point of view" (modality=obligation, sample=gdpr_article22_s005)
* `gdpr_article22_s005.c1.action.p04`: "contest the decision" (modality=obligation, sample=gdpr_article22_s005)
* `gdpr_article22_s006.c1.action.p01`: "be based on special categories of personal data referred to in Article 9(1)" (modality=prohibition, sample=gdpr_article22_s006)

**AI recommendation:** `N/A` (status `no_supported_candidate`, authority `ai_proposed_unresolved`).

- candidate span evidence: "The data subject shall have the right not to be subject to a decision based solely on automated processing, including profiling, which produces legal effects concerning him or her or similarly significantly affects him or her."
- confidence: not recorded (status/evidence-based AI resolution)

Evidence/reason: 当前 article22 候选中没有收集身份及联系方式的动作。宽泛的保障措施不能据此指定为该活动；按当前候选集判为无对应。

Options: `ACCEPT` / `CHANGE TO <rule_action_id>` / `N/A`

---

## Pair `syn_incorrect_actor_06`

- rule: `article20`
- process: `gdpr_4_right_of_portability`
- target violation type: `incorrect_actor`
- regulation text: "The data subject shall have the right to receive the personal data concerning him or her, which he or she has provided to a controller, in a structured, commonly used and machine-readable format and have the right to transmit those data to another controller without hindrance from the controller to which the personal data have been provided, where the processing is based on consent pursuant to point (a) of Article 6(1) or point (a) of Article 9(2) or on a contract pursuant to point (b) of Article 6(1); and the processing is carried out by automated means. In exercising his or her right to data portability pursuant to paragraph 1, the data subject shall have the right to have the personal data transmitted directly from one controller to another, where technically feasible. The exercise of the right referred to in paragraph 1 of this Article shall be without prejudice to Article 17. That right shall not apply to processing necessary for the performance of a task carried out in the public interest or in the exercise of official authority vested in the controller. The right referred to in paragraph 1 shall not adversely affect the rights and freedoms of others."
- target BPMN activity: `sid-2E045BBD-9F82-497F-8458-49AA9129F991` "Retrieve available data of the data subject" (lane `sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F` "")
- predecessors: sid-1FE17422-E502-4D46-B8C9-0BB2FFADCA39 ()
- successors: sid-A98B48ED-872F-48D6-BA09-BDEA8568525A ()

### Actor / lane binding (unresolved)

Relevant Direct-LLM Rule Record actor candidates:

* `gdpr_article20_s001.c1.actor.a01`: "The data subject" (sample=gdpr_article20_s001)
* `gdpr_article20_s002.c1.actor.a01`: "the data subject" (sample=gdpr_article20_s002)
* `gdpr_article20_s004.c1.actor.a01`: "That right" (sample=gdpr_article20_s004)
* `gdpr_article20_s005.c1.actor.a01`: "The right referred to in paragraph 1" (sample=gdpr_article20_s005)

- candidate actor span evidence: "the controller to which the personal data have been provided"
- right-holder reference: `gdpr_article20_s001.c1.actor.1` "The data subject"
- confidence: not recorded (status/evidence-based AI resolution)

**AI recommendation:** rule actor `N/A`; process executor `Data Controller`; expected lane `sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F` "" (status `inferred_counterparty_executor`).

Evidence/reason: 保留 data subject 为接收数据的权利主体；将已持有数据的 controller 判为检索/提供数据的执行方。不是将 receive 的主语改成 controller。

Options: `ACCEPT` / `CHANGE TO <rule_actor_id>` / `CHANGE LANE TO <lane_id>` / `N/A`

---

## Pair `syn_incorrect_actor_07`

- rule: `article20`
- process: `gdpr_4_right_of_portability`
- target violation type: `incorrect_actor`
- regulation text: "The data subject shall have the right to receive the personal data concerning him or her, which he or she has provided to a controller, in a structured, commonly used and machine-readable format and have the right to transmit those data to another controller without hindrance from the controller to which the personal data have been provided, where the processing is based on consent pursuant to point (a) of Article 6(1) or point (a) of Article 9(2) or on a contract pursuant to point (b) of Article 6(1); and the processing is carried out by automated means. In exercising his or her right to data portability pursuant to paragraph 1, the data subject shall have the right to have the personal data transmitted directly from one controller to another, where technically feasible. The exercise of the right referred to in paragraph 1 of this Article shall be without prejudice to Article 17. That right shall not apply to processing necessary for the performance of a task carried out in the public interest or in the exercise of official authority vested in the controller. The right referred to in paragraph 1 shall not adversely affect the rights and freedoms of others."
- target BPMN activity: `sid-BB84BABD-20ED-4C97-B755-BDA101C57A8D` "Communicate data and elaborations" (lane `sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F` "")
- predecessors: sid-A98B48ED-872F-48D6-BA09-BDEA8568525A ()
- successors: sid-8CDC510A-396C-41A5-B5F0-EFD74BAE4C0D ()

### Actor / lane binding (unresolved)

Relevant Direct-LLM Rule Record actor candidates:

* `gdpr_article20_s001.c1.actor.a01`: "The data subject" (sample=gdpr_article20_s001)
* `gdpr_article20_s002.c1.actor.a01`: "the data subject" (sample=gdpr_article20_s002)
* `gdpr_article20_s004.c1.actor.a01`: "That right" (sample=gdpr_article20_s004)
* `gdpr_article20_s005.c1.actor.a01`: "The right referred to in paragraph 1" (sample=gdpr_article20_s005)

- candidate actor span evidence: "from one controller to another"
- right-holder reference: `gdpr_article20_s001.c2.actor.1` "The data subject"
- confidence: not recorded (status/evidence-based AI resolution)

**AI recommendation:** rule actor `N/A`; process executor `Data Controller`; expected lane `sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F` "" (status `inferred_counterparty_executor`).

Evidence/reason: 以直接传输中 from one controller 的源端控制者对应发送方 Data Controller；data subject 仍为权利主体，Third Party 对应另一控制者沿用已接受的候选假设。

Options: `ACCEPT` / `CHANGE TO <rule_actor_id>` / `CHANGE LANE TO <lane_id>` / `N/A`

---

## Pair `syn_incorrect_actor_09`

- rule: `article17`
- process: `gdpr_5_right_to_withdraw`
- target violation type: `incorrect_actor`
- regulation text: "The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay and the controller shall have the obligation to erase personal data without undue delay where one of the following grounds applies. The personal data are no longer necessary in relation to the purposes for which they were collected or otherwise processed. The data subject withdraws consent on which the processing is based according to point (a) of Article 6(1), or point (a) of Article 9(2), and where there is no other legal ground for the processing. The data subject objects to the processing pursuant to Article 21(1) and there are no overriding legitimate grounds for the processing, or the data subject objects to the processing pursuant to Article 21(2). The personal data have been unlawfully processed. The personal data have to be erased for compliance with a legal obligation in Union or Member State law to which the controller is subject. The personal data have been collected in relation to the offer of information society services referred to in Article 8(1). Where the controller has made the personal data public and is obliged pursuant to paragraph 1 to erase the personal data, the controller, taking account of available technology and the cost of implementation, shall take reasonable steps, including technical measures, to inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for exercising the right of freedom of expression and information. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for compliance with a legal obligation which requires processing by Union or Member State law to which the controller is subject or for the performance of a task carried out in the public interest or in the exercise of official authority vested in the controller. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for reasons of public interest in the area of public health in accordance with points (h) and (i) of Article 9(2) as well as Article 9(3). Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for archiving purposes in the public interest, scientific or historical research purposes or statistical purposes in accordance with Article 89(1) in so far as the right referred to in paragraph 1 is likely to render impossible or seriously impair the achievement of the objectives of that processing. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for the establishment, exercise or defence of legal claims."
- target BPMN activity: `sid-BB5F1C3A-DCD5-4C17-90CF-503D23B048FB` "Communicate the withdraw" (lane `sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C` "")
- predecessors: sid-1A48D305-CB15-4C57-A988-B39ED62DE531 (Stop using withdrawn data)
- successors: sid-BBE4AD40-63CE-49C4-84D5-180971257813 ()

### Action binding (unresolved)

Relevant Direct-LLM Rule Record action candidates:

* `gdpr_article17_s001.c1.action.p01`: "obtain from the controller the erasure of personal data concerning him or her" (modality=obligation, sample=gdpr_article17_s001)
* `gdpr_article17_s001.c2.action.p02`: "erase personal data" (modality=obligation, sample=gdpr_article17_s001)
* `gdpr_article17_s003.c1.action.p01`: "withdraws consent" (modality=obligation, sample=gdpr_article17_s003)
* `gdpr_article17_s005.c1.action.p01`: "processed" (modality=obligation, sample=gdpr_article17_s005)
* `gdpr_article17_s006.c1.action.p01`: "erased" (modality=obligation, sample=gdpr_article17_s006)
* `gdpr_article17_s007.c1.action.p01`: "collected" (modality=definition, sample=gdpr_article17_s007)
* `gdpr_article17_s008.c1.action.p01`: "take reasonable steps, including technical measures, to inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data" (modality=obligation, sample=gdpr_article17_s008)
* `gdpr_article17_s009.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article17_s009)
* `gdpr_article17_s010.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article17_s010)
* `gdpr_article17_s011.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article17_s011)
* `gdpr_article17_s012.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article17_s012)
* `gdpr_article17_s013.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article17_s013)

**AI recommendation:** `N/A` (status `candidate_recipient_mismatch`, authority `ai_proposed_unresolved`).

- candidate span evidence: "Where the controller has made the personal data public and is obliged pursuant to paragraph 1 to erase the personal data, the controller, taking account of available technology and the cost of implementation, shall take reasonable steps, including technical measures, to inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data."
- confidence: not recorded (status/evidence-based AI resolution)

Evidence/reason: BPMN 通知的接收者为 Data subject；原候选要求 inform controllers。对象明确不同，拒绝该候选，当前规则集合内无合适替代。

Options: `ACCEPT` / `CHANGE TO <rule_action_id>` / `N/A`

---

## Pair `syn_incorrect_actor_10`

- rule: `article16`
- process: `gdpr_6_right_to_rectify`
- target violation type: `incorrect_actor`
- regulation text: "The data subject shall have the right to obtain from the controller without undue delay the rectification of inaccurate personal data concerning him or her. Taking into account the purposes of the processing, the data subject shall have the right to have incomplete personal data completed, including by means of providing a supplementary statement."
- target BPMN activity: `sid-2D1BF282-F735-4BE0-996F-4D9C7DBED814` "Rectify data" (lane `sid-95D07626-A357-422E-830F-B1E57917DB74` "")
- predecessors: sid-EC693640-2075-44F6-8609-7C4FDCB2A7C0 ()
- successors: sid-F9E3B912-20D2-4AD2-B92F-811216B4F746 (Communicate the rectification
)

### Actor / lane binding (unresolved)

Relevant Direct-LLM Rule Record actor candidates:

* `gdpr_article16_s001.c1.actor.a01`: "The data subject" (sample=gdpr_article16_s001)
* `gdpr_article16_s002.c1.actor.a01`: "the data subject" (sample=gdpr_article16_s002)

- candidate actor span evidence: "the controller"
- right-holder reference: `gdpr_article16_s001.c1.actor.1` "The data subject"
- confidence: not recorded (status/evidence-based AI resolution)

**AI recommendation:** rule actor `N/A`; process executor `Data Controller`; expected lane `sid-95D07626-A357-422E-830F-B1E57917DB74` "" (status `inferred_counterparty_executor`).

Evidence/reason: 保留 data subject 为权利主体；依据 obtain from the controller 将 controller 判为实现更正的相对执行方，并与 Data Controller 对应。该关系是 AI 补充推断。

Options: `ACCEPT` / `CHANGE TO <rule_actor_id>` / `CHANGE LANE TO <lane_id>` / `N/A`

---

## Pair `syn_missing_action_07`

- rule: `article17`
- process: `gdpr_5_right_to_withdraw`
- target violation type: `missing_action`
- regulation text: "The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay and the controller shall have the obligation to erase personal data without undue delay where one of the following grounds applies. The personal data are no longer necessary in relation to the purposes for which they were collected or otherwise processed. The data subject withdraws consent on which the processing is based according to point (a) of Article 6(1), or point (a) of Article 9(2), and where there is no other legal ground for the processing. The data subject objects to the processing pursuant to Article 21(1) and there are no overriding legitimate grounds for the processing, or the data subject objects to the processing pursuant to Article 21(2). The personal data have been unlawfully processed. The personal data have to be erased for compliance with a legal obligation in Union or Member State law to which the controller is subject. The personal data have been collected in relation to the offer of information society services referred to in Article 8(1). Where the controller has made the personal data public and is obliged pursuant to paragraph 1 to erase the personal data, the controller, taking account of available technology and the cost of implementation, shall take reasonable steps, including technical measures, to inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for exercising the right of freedom of expression and information. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for compliance with a legal obligation which requires processing by Union or Member State law to which the controller is subject or for the performance of a task carried out in the public interest or in the exercise of official authority vested in the controller. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for reasons of public interest in the area of public health in accordance with points (h) and (i) of Article 9(2) as well as Article 9(3). Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for archiving purposes in the public interest, scientific or historical research purposes or statistical purposes in accordance with Article 89(1) in so far as the right referred to in paragraph 1 is likely to render impossible or seriously impair the achievement of the objectives of that processing. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for the establishment, exercise or defence of legal claims."
- target BPMN activity: `sid-A9B97678-298C-4EE7-82A3-836179299938` "Check if withdrawn data are relevant" (lane `sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C` "")
- predecessors: sid-C8822EE6-038D-4B46-B701-088DCA525E81 ()
- successors: sid-F4998816-41A2-476E-9C55-4E097F0388E4 ()

### Action binding (unresolved)

Relevant Direct-LLM Rule Record action candidates:

* `gdpr_article17_s001.c1.action.p01`: "obtain from the controller the erasure of personal data concerning him or her" (modality=obligation, sample=gdpr_article17_s001)
* `gdpr_article17_s001.c2.action.p02`: "erase personal data" (modality=obligation, sample=gdpr_article17_s001)
* `gdpr_article17_s003.c1.action.p01`: "withdraws consent" (modality=obligation, sample=gdpr_article17_s003)
* `gdpr_article17_s005.c1.action.p01`: "processed" (modality=obligation, sample=gdpr_article17_s005)
* `gdpr_article17_s006.c1.action.p01`: "erased" (modality=obligation, sample=gdpr_article17_s006)
* `gdpr_article17_s007.c1.action.p01`: "collected" (modality=definition, sample=gdpr_article17_s007)
* `gdpr_article17_s008.c1.action.p01`: "take reasonable steps, including technical measures, to inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data" (modality=obligation, sample=gdpr_article17_s008)
* `gdpr_article17_s009.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article17_s009)
* `gdpr_article17_s010.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article17_s010)
* `gdpr_article17_s011.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article17_s011)
* `gdpr_article17_s012.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article17_s012)
* `gdpr_article17_s013.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article17_s013)

**AI recommendation:** `N/A` (status `condition_check_not_action`, authority `ai_proposed_unresolved`).

- candidate span evidence: "The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay and the controller shall have the obligation to erase personal data without undue delay where one of the following grounds applies."
- confidence: not recorded (status/evidence-based AI resolution)

Evidence/reason: 检查数据相关性归为删除流程的适用条件检查，可关联 erase personal data 的背景，但不等同于执行删除；action_id 保留空并明确类型。

Options: `ACCEPT` / `CHANGE TO <rule_action_id>` / `N/A`

---

## Pair `syn_missing_action_08`

- rule: `article16`
- process: `gdpr_6_right_to_rectify`
- target violation type: `missing_action`
- regulation text: "The data subject shall have the right to obtain from the controller without undue delay the rectification of inaccurate personal data concerning him or her. Taking into account the purposes of the processing, the data subject shall have the right to have incomplete personal data completed, including by means of providing a supplementary statement."
- target BPMN activity: `sid-F9E3B912-20D2-4AD2-B92F-811216B4F746` "Communicate the rectification
" (lane `sid-95D07626-A357-422E-830F-B1E57917DB74` "")
- predecessors: sid-2D1BF282-F735-4BE0-996F-4D9C7DBED814 (Rectify data)
- successors: sid-F79BAA93-9FEF-40EC-BBC6-2F9A11AB0F28 ()

### Action binding (unresolved)

Relevant Direct-LLM Rule Record action candidates:

* `gdpr_article16_s001.c1.action.p01`: "obtain from the controller without undue delay the rectification of inaccurate personal data concerning him or her" (modality=obligation, sample=gdpr_article16_s001)
* `gdpr_article16_s002.c1.action.p01`: "have the right to have incomplete personal data completed" (modality=obligation, sample=gdpr_article16_s002)

**AI recommendation:** `N/A` (status `candidate_activity_mismatch`, authority `ai_proposed_unresolved`).

- candidate span evidence: "The data subject shall have the right to obtain from the controller without undue delay the rectification of inaccurate personal data concerning him or her."
- confidence: not recorded (status/evidence-based AI resolution)

Evidence/reason: Rectify data 与 Communicate the rectification 是独立活动；通知数据主体不能替代实际更正。当前 article16 动作候选无独立通知项，判为无对应。

Options: `ACCEPT` / `CHANGE TO <rule_action_id>` / `N/A`

### Actor / lane binding (unresolved)

Relevant Direct-LLM Rule Record actor candidates:

* `gdpr_article16_s001.c1.actor.a01`: "The data subject" (sample=gdpr_article16_s001)
* `gdpr_article16_s002.c1.actor.a01`: "the data subject" (sample=gdpr_article16_s002)

- candidate actor span evidence: "not recorded"
- right-holder reference: `gdpr_article16_s001.c1.actor.1` "The data subject"
- confidence: not recorded (status/evidence-based AI resolution)

**AI recommendation:** rule actor `N/A`; process executor `Data Controller`; expected lane `sid-95D07626-A357-422E-830F-B1E57917DB74` "" (status `process_executor_only`).

Evidence/reason: 确认此通知节点属于 Data Controller；当前 article16 无对应通知动作，故只确认流程执行者，不声明已获得该通知义务的法规 actor 绑定。

Options: `ACCEPT` / `CHANGE TO <rule_actor_id>` / `CHANGE LANE TO <lane_id>` / `N/A`

---

## Pair `syn_missing_action_09`

- rule: `article20`
- process: `gdpr_4_right_of_portability`
- target violation type: `missing_action`
- regulation text: "The data subject shall have the right to receive the personal data concerning him or her, which he or she has provided to a controller, in a structured, commonly used and machine-readable format and have the right to transmit those data to another controller without hindrance from the controller to which the personal data have been provided, where the processing is based on consent pursuant to point (a) of Article 6(1) or point (a) of Article 9(2) or on a contract pursuant to point (b) of Article 6(1); and the processing is carried out by automated means. In exercising his or her right to data portability pursuant to paragraph 1, the data subject shall have the right to have the personal data transmitted directly from one controller to another, where technically feasible. The exercise of the right referred to in paragraph 1 of this Article shall be without prejudice to Article 17. That right shall not apply to processing necessary for the performance of a task carried out in the public interest or in the exercise of official authority vested in the controller. The right referred to in paragraph 1 shall not adversely affect the rights and freedoms of others."
- target BPMN activity: `sid-BB84BABD-20ED-4C97-B755-BDA101C57A8D` "Communicate data and elaborations" (lane `sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F` "")
- predecessors: sid-A98B48ED-872F-48D6-BA09-BDEA8568525A ()
- successors: sid-8CDC510A-396C-41A5-B5F0-EFD74BAE4C0D ()

### Actor / lane binding (unresolved)

Relevant Direct-LLM Rule Record actor candidates:

* `gdpr_article20_s001.c1.actor.a01`: "The data subject" (sample=gdpr_article20_s001)
* `gdpr_article20_s002.c1.actor.a01`: "the data subject" (sample=gdpr_article20_s002)
* `gdpr_article20_s004.c1.actor.a01`: "That right" (sample=gdpr_article20_s004)
* `gdpr_article20_s005.c1.actor.a01`: "The right referred to in paragraph 1" (sample=gdpr_article20_s005)

- candidate actor span evidence: "from one controller to another"
- right-holder reference: `gdpr_article20_s001.c2.actor.1` "The data subject"
- confidence: not recorded (status/evidence-based AI resolution)

**AI recommendation:** rule actor `N/A`; process executor `Data Controller`; expected lane `sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F` "" (status `inferred_counterparty_executor`).

Evidence/reason: 以直接传输中 from one controller 的源端控制者对应发送方 Data Controller；data subject 仍为权利主体，Third Party 对应另一控制者沿用已接受的候选假设。

Options: `ACCEPT` / `CHANGE TO <rule_actor_id>` / `CHANGE LANE TO <lane_id>` / `N/A`

---

## Pair `syn_missing_action_10`

- rule: `article16`
- process: `gdpr_6_right_to_rectify`
- target violation type: `missing_action`
- regulation text: "The data subject shall have the right to obtain from the controller without undue delay the rectification of inaccurate personal data concerning him or her. Taking into account the purposes of the processing, the data subject shall have the right to have incomplete personal data completed, including by means of providing a supplementary statement."
- target BPMN activity: `sid-2D1BF282-F735-4BE0-996F-4D9C7DBED814` "Rectify data" (lane `sid-95D07626-A357-422E-830F-B1E57917DB74` "")
- predecessors: sid-EC693640-2075-44F6-8609-7C4FDCB2A7C0 ()
- successors: sid-F9E3B912-20D2-4AD2-B92F-811216B4F746 (Communicate the rectification
)

### Actor / lane binding (unresolved)

Relevant Direct-LLM Rule Record actor candidates:

* `gdpr_article16_s001.c1.actor.a01`: "The data subject" (sample=gdpr_article16_s001)
* `gdpr_article16_s002.c1.actor.a01`: "the data subject" (sample=gdpr_article16_s002)

- candidate actor span evidence: "the controller"
- right-holder reference: `gdpr_article16_s001.c1.actor.1` "The data subject"
- confidence: not recorded (status/evidence-based AI resolution)

**AI recommendation:** rule actor `N/A`; process executor `Data Controller`; expected lane `sid-95D07626-A357-422E-830F-B1E57917DB74` "" (status `inferred_counterparty_executor`).

Evidence/reason: 保留 data subject 为权利主体；依据 obtain from the controller 将 controller 判为实现更正的相对执行方，并与 Data Controller 对应。该关系是 AI 补充推断。

Options: `ACCEPT` / `CHANGE TO <rule_actor_id>` / `CHANGE LANE TO <lane_id>` / `N/A`

---

## Pair `syn_out_of_order_01`

- rule: `article33`
- process: `gdpr_1_data_breach`
- target violation type: `out_of_order`
- regulation text: "In the case of a personal data breach, the controller shall without undue delay and, where feasible, not later than 72 hours after having become aware of it, notify the personal data breach to the supervisory authority competent in accordance with Article 55, unless the personal data breach is unlikely to result in a risk to the rights and freedoms of natural persons. Where the notification to the supervisory authority is not made within 72 hours, it shall be accompanied by reasons for the delay. The processor shall notify the controller without undue delay after becoming aware of a personal data breach. The notification referred to in paragraph 1 shall at least describe the nature of the personal data breach including where possible, the categories and approximate number of data subjects concerned and the categories and approximate number of personal data records concerned. The notification referred to in paragraph 1 shall at least communicate the name and contact details of the data protection officer or other contact point where more information can be obtained. The notification referred to in paragraph 1 shall at least describe the likely consequences of the personal data breach. The notification referred to in paragraph 1 shall at least describe the measures taken or proposed to be taken by the controller to address the personal data breach, including, where appropriate, measures to mitigate its possible adverse effects. Where, and in so far as, it is not possible to provide the information at the same time, the information may be provided in phases without undue further delay. The controller shall document any personal data breaches, comprising the facts relating to the personal data breach, its effects and the remedial action taken. That documentation shall enable the supervisory authority to verify compliance with this Article."
- target BPMN activity: `sid-20C5FDD3-8014-432D-8595-CD780D866E38` "Retrieve breached subjects" (lane `sid-4035AA0F-2D62-46AC-A369-4151026920A3` "")
- predecessors: sid-CD9ABA3B-996B-4F9A-A701-7F4C125A91F0 (Retrieve breached data)
- successors: sid-9FECC45C-033C-4750-9436-4DA0648C4B43 ()

### Rule-side order relation (unresolved)

- benchmark process pair: `sid-20C5FDD3-8014-432D-8595-CD780D866E38` "Retrieve breached subjects", `sid-0F3D7191-F96A-45A1-B616-EC78A870BACF` "Notify national authority"
- control BPMN order: `forward only`
- variant BPMN order: `backward only`
- AI recommendation: `N/A` (`ineligible_no_rule_order`)
- confidence: 1.0

- regulation/order evidence: "In the case of a personal data breach, the controller shall without undue delay and, where feasible, not later than 72 hours after having become aware of it, notify the personal data breach to the supervisory authority competent in accordance with Article 55, unless the personal data breach is unlikely to result in a risk to the rights and freedoms of natural persons."
- regulation/order evidence: "The notification referred to in paragraph 1 shall at least describe the nature of the personal data breach including where possible, the categories and approximate number of data subjects concerned and the categories and approximate number of personal data records concerned."
- regulation/order evidence: "Where, and in so far as, it is not possible to provide the information at the same time, the information may be provided in phases without undue further delay."

Evidence/reason: 描述泄露与通知不是“检索主体必须先于首次通知”的明文动作对；s008 还允许分阶段补充信息，不采纳该严格法规顺序。

Options: `ACCEPT N/A` / `DEFINE before=<rule_action_id> after=<rule_action_id>`

---

## Pair `syn_out_of_order_02`

- rule: `article33`
- process: `gdpr_1_data_breach`
- target violation type: `out_of_order`
- regulation text: "In the case of a personal data breach, the controller shall without undue delay and, where feasible, not later than 72 hours after having become aware of it, notify the personal data breach to the supervisory authority competent in accordance with Article 55, unless the personal data breach is unlikely to result in a risk to the rights and freedoms of natural persons. Where the notification to the supervisory authority is not made within 72 hours, it shall be accompanied by reasons for the delay. The processor shall notify the controller without undue delay after becoming aware of a personal data breach. The notification referred to in paragraph 1 shall at least describe the nature of the personal data breach including where possible, the categories and approximate number of data subjects concerned and the categories and approximate number of personal data records concerned. The notification referred to in paragraph 1 shall at least communicate the name and contact details of the data protection officer or other contact point where more information can be obtained. The notification referred to in paragraph 1 shall at least describe the likely consequences of the personal data breach. The notification referred to in paragraph 1 shall at least describe the measures taken or proposed to be taken by the controller to address the personal data breach, including, where appropriate, measures to mitigate its possible adverse effects. Where, and in so far as, it is not possible to provide the information at the same time, the information may be provided in phases without undue further delay. The controller shall document any personal data breaches, comprising the facts relating to the personal data breach, its effects and the remedial action taken. That documentation shall enable the supervisory authority to verify compliance with this Article."
- target BPMN activity: `sid-CD9ABA3B-996B-4F9A-A701-7F4C125A91F0` "Retrieve breached data" (lane `sid-4035AA0F-2D62-46AC-A369-4151026920A3` "")
- predecessors: sid-337FA953-A28B-42B0-92AE-AAA0FC87B690 ()
- successors: sid-20C5FDD3-8014-432D-8595-CD780D866E38 (Retrieve breached subjects)

### Rule-side order relation (unresolved)

- benchmark process pair: `sid-CD9ABA3B-996B-4F9A-A701-7F4C125A91F0` "Retrieve breached data", `sid-20C5FDD3-8014-432D-8595-CD780D866E38` "Retrieve breached subjects"
- control BPMN order: `forward only`
- variant BPMN order: `backward only`
- AI recommendation: `N/A` (`ineligible_no_rule_order`)
- confidence: 1.0

- regulation/order evidence: "The notification referred to in paragraph 1 shall at least describe the nature of the personal data breach including where possible, the categories and approximate number of data subjects concerned and the categories and approximate number of personal data records concerned."

Evidence/reason: 两个检索活动均关联同一个 describe 动作；不能生成 action 先于自身的关系。

Options: `ACCEPT N/A` / `DEFINE before=<rule_action_id> after=<rule_action_id>`

---

## Pair `syn_out_of_order_03`

- rule: `article22`
- process: `gdpr_2_consent_to_use_the_data`
- target violation type: `out_of_order`
- regulation text: "The data subject shall have the right not to be subject to a decision based solely on automated processing, including profiling, which produces legal effects concerning him or her or similarly significantly affects him or her. Paragraph 1 shall not apply if the decision is necessary for entering into, or performance of, a contract between the data subject and a data controller. Paragraph 1 shall not apply if the decision is authorised by Union or Member State law to which the controller is subject and which also lays down suitable measures to safeguard the data subject's rights and freedoms and legitimate interests. or Paragraph 1 shall not apply if the decision is based on the data subject's explicit consent. In the cases referred to in points (a) and (c) of paragraph 2, the data controller shall implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests, at least the right to obtain human intervention on the part of the controller, to express his or her point of view and to contest the decision. Decisions referred to in paragraph 2 shall not be based on special categories of personal data referred to in Article 9(1), unless point (a) or (g) of Article 9(2) applies and suitable measures to safeguard the data subject's rights and freedoms and legitimate interests are in place."
- target BPMN activity: `sid-17C48064-C83F-44C6-998A-8DB69B109E8D` "Retrieve identity and contact details" (lane `sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB` "")
- predecessors: sid-AB0B4F0A-B4F9-4379-9225-B4F27DFD6BC6 ()
- successors: sid-BB1531A1-D98A-4DB2-92CB-0DEE27831568 ()

### Action binding (unresolved)

Relevant Direct-LLM Rule Record action candidates:

* `gdpr_article22_s001.c1.action.p01`: "have the right not to be subject to a decision" (modality=obligation, sample=gdpr_article22_s001)
* `gdpr_article22_s002.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article22_s002)
* `gdpr_article22_s003.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article22_s003)
* `gdpr_article22_s004.c1.action.p01`: "apply" (modality=prohibition, sample=gdpr_article22_s004)
* `gdpr_article22_s005.c1.action.p01`: "implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests" (modality=obligation, sample=gdpr_article22_s005)
* `gdpr_article22_s005.c1.action.p02`: "obtain human intervention on the part of the controller" (modality=obligation, sample=gdpr_article22_s005)
* `gdpr_article22_s005.c1.action.p03`: "express his or her point of view" (modality=obligation, sample=gdpr_article22_s005)
* `gdpr_article22_s005.c1.action.p04`: "contest the decision" (modality=obligation, sample=gdpr_article22_s005)
* `gdpr_article22_s006.c1.action.p01`: "be based on special categories of personal data referred to in Article 9(1)" (modality=prohibition, sample=gdpr_article22_s006)

**AI recommendation:** `N/A` (status `no_supported_candidate`, authority `ai_proposed_unresolved`).

- candidate span evidence: "The data subject shall have the right not to be subject to a decision based solely on automated processing, including profiling, which produces legal effects concerning him or her or similarly significantly affects him or her."
- confidence: not recorded (status/evidence-based AI resolution)

Evidence/reason: 当前 article22 候选中没有收集身份及联系方式的动作。宽泛的保障措施不能据此指定为该活动；按当前候选集判为无对应。

Options: `ACCEPT` / `CHANGE TO <rule_action_id>` / `N/A`

### Rule-side order relation (unresolved)

- benchmark process pair: `sid-17C48064-C83F-44C6-998A-8DB69B109E8D` "Retrieve identity and contact details", `sid-141B6C65-D86C-443C-BC7F-05783264AF77` "Collect consent information"
- control BPMN order: `forward only`
- variant BPMN order: `backward only`
- AI recommendation: `N/A` (`ineligible_no_rule_order`)
- confidence: 1.0

- regulation/order evidence: "The data subject shall have the right not to be subject to a decision based solely on automated processing, including profiling, which produces legal effects concerning him or her or similarly significantly affects him or her."
- regulation/order evidence: "or Paragraph 1 shall not apply if the decision is based on the data subject's explicit consent."
- regulation/order evidence: "In the cases referred to in points (a) and (c) of paragraph 2, the data controller shall implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests, at least the right to obtain human intervention on the part of the controller, to express his or her point of view and to contest the decision."

Evidence/reason: 身份联系方式检索和收集同意没有两个对应的法规动作候选，流程先后不能补成法规顺序。

Options: `ACCEPT N/A` / `DEFINE before=<rule_action_id> after=<rule_action_id>`

---

## Pair `syn_out_of_order_04`

- rule: `article22`
- process: `gdpr_2_consent_to_use_the_data`
- target violation type: `out_of_order`
- regulation text: "The data subject shall have the right not to be subject to a decision based solely on automated processing, including profiling, which produces legal effects concerning him or her or similarly significantly affects him or her. Paragraph 1 shall not apply if the decision is necessary for entering into, or performance of, a contract between the data subject and a data controller. Paragraph 1 shall not apply if the decision is authorised by Union or Member State law to which the controller is subject and which also lays down suitable measures to safeguard the data subject's rights and freedoms and legitimate interests. or Paragraph 1 shall not apply if the decision is based on the data subject's explicit consent. In the cases referred to in points (a) and (c) of paragraph 2, the data controller shall implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests, at least the right to obtain human intervention on the part of the controller, to express his or her point of view and to contest the decision. Decisions referred to in paragraph 2 shall not be based on special categories of personal data referred to in Article 9(1), unless point (a) or (g) of Article 9(2) applies and suitable measures to safeguard the data subject's rights and freedoms and legitimate interests are in place."
- target BPMN activity: `sid-1C0F89DD-F7D8-403C-B629-EBBCC78D6CE0` "Check if legitimate interests are presents" (lane `sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB` "")
- predecessors: sid-1C0EC338-56FF-4F27-9494-BC470B1BC93B ()
- successors: sid-B80CDCB8-79EA-45F1-BBE3-32DCC77D4372 ()

### Rule-side order relation (unresolved)

- benchmark process pair: `sid-1C0F89DD-F7D8-403C-B629-EBBCC78D6CE0` "Check if legitimate interests are presents", `sid-141B6C65-D86C-443C-BC7F-05783264AF77` "Collect consent information"
- control BPMN order: `forward only`
- variant BPMN order: `backward only`
- AI recommendation: `N/A` (`ineligible_no_rule_order`)
- confidence: 1.0

- regulation/order evidence: "or Paragraph 1 shall not apply if the decision is based on the data subject's explicit consent."
- regulation/order evidence: "In the cases referred to in points (a) and (c) of paragraph 2, the data controller shall implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests, at least the right to obtain human intervention on the part of the controller, to express his or her point of view and to contest the decision."

Evidence/reason: 保障合法利益与基于同意的条件，不构成“先检查合法利益再收集同意”的两个法规动作及强制顺序。

Options: `ACCEPT N/A` / `DEFINE before=<rule_action_id> after=<rule_action_id>`

---

## Pair `syn_out_of_order_05`

- rule: `article15`
- process: `gdpr_3_right_to_access`
- target violation type: `out_of_order`
- regulation text: "The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the following information the purposes of the processing. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the categories of personal data concerned. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the recipients or categories of recipient to whom the personal data have been or will be disclosed, in particular recipients in third countries or international organisations. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and where possible, the envisaged period for which the personal data will be stored, or, if not possible, the criteria used to determine that period. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the existence of the right to request from the controller rectification or erasure of personal data or restriction of processing of personal data concerning the data subject or to object to such processing. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the right to lodge a complaint with a supervisory authority. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and where the personal data are not collected from the data subject, any available information as to their source. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the existence of automated decision-making, including profiling, referred to in Article 22(1) and (4) and, at least in those cases, meaningful information about the logic involved, as well as the significance and the envisaged consequences of such processing for the data subject. Where personal data are transferred to a third country or to an international organisation, the data subject shall have the right to be informed of the appropriate safeguards pursuant to Article 46 relating to the transfer. The controller shall provide a copy of the personal data undergoing processing. For any further copies requested by the data subject, the controller may charge a reasonable fee based on administrative costs. Where the data subject makes the request by electronic means, and unless otherwise requested by the data subject, the information shall be provided in a commonly used electronic form. The right to obtain a copy referred to in paragraph 3 shall not adversely affect the rights and freedoms of others."
- target BPMN activity: `sid-2E045BBD-9F82-497F-8458-49AA9129F991` "Retrieve available data of the data subject" (lane `sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F` "")
- predecessors: sid-1FE17422-E502-4D46-B8C9-0BB2FFADCA39 ()
- successors: sid-A98B48ED-872F-48D6-BA09-BDEA8568525A ()

### Rule-side order relation (unresolved)

- benchmark process pair: `sid-2E045BBD-9F82-497F-8458-49AA9129F991` "Retrieve available data of the data subject", `sid-BB84BABD-20ED-4C97-B755-BDA101C57A8D` "Communicate data and elaborations"
- control BPMN order: `forward only`
- variant BPMN order: `backward only`
- AI recommendation: `N/A` (`ineligible_no_rule_order`)
- confidence: 1.0

- regulation/order evidence: "The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the following information the purposes of the processing."
- regulation/order evidence: "The controller shall provide a copy of the personal data undergoing processing."

Evidence/reason: 获取访问权与提供副本描述权利和履行行为；原文没有指定两个 BPMN 步骤的先后，保留流程关系。

Options: `ACCEPT N/A` / `DEFINE before=<rule_action_id> after=<rule_action_id>`

---

## Pair `syn_out_of_order_06`

- rule: `article20`
- process: `gdpr_4_right_of_portability`
- target violation type: `out_of_order`
- regulation text: "The data subject shall have the right to receive the personal data concerning him or her, which he or she has provided to a controller, in a structured, commonly used and machine-readable format and have the right to transmit those data to another controller without hindrance from the controller to which the personal data have been provided, where the processing is based on consent pursuant to point (a) of Article 6(1) or point (a) of Article 9(2) or on a contract pursuant to point (b) of Article 6(1); and the processing is carried out by automated means. In exercising his or her right to data portability pursuant to paragraph 1, the data subject shall have the right to have the personal data transmitted directly from one controller to another, where technically feasible. The exercise of the right referred to in paragraph 1 of this Article shall be without prejudice to Article 17. That right shall not apply to processing necessary for the performance of a task carried out in the public interest or in the exercise of official authority vested in the controller. The right referred to in paragraph 1 shall not adversely affect the rights and freedoms of others."
- target BPMN activity: `sid-2E045BBD-9F82-497F-8458-49AA9129F991` "Retrieve available data of the data subject" (lane `sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F` "")
- predecessors: sid-1FE17422-E502-4D46-B8C9-0BB2FFADCA39 ()
- successors: sid-A98B48ED-872F-48D6-BA09-BDEA8568525A ()

### Actor / lane binding (unresolved)

Relevant Direct-LLM Rule Record actor candidates:

* `gdpr_article20_s001.c1.actor.a01`: "The data subject" (sample=gdpr_article20_s001)
* `gdpr_article20_s002.c1.actor.a01`: "the data subject" (sample=gdpr_article20_s002)
* `gdpr_article20_s004.c1.actor.a01`: "That right" (sample=gdpr_article20_s004)
* `gdpr_article20_s005.c1.actor.a01`: "The right referred to in paragraph 1" (sample=gdpr_article20_s005)

- candidate actor span evidence: "the controller to which the personal data have been provided"
- right-holder reference: `gdpr_article20_s001.c1.actor.1` "The data subject"
- confidence: not recorded (status/evidence-based AI resolution)

**AI recommendation:** rule actor `N/A`; process executor `Data Controller`; expected lane `sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F` "" (status `inferred_counterparty_executor`).

Evidence/reason: 保留 data subject 为接收数据的权利主体；将已持有数据的 controller 判为检索/提供数据的执行方。不是将 receive 的主语改成 controller。

Options: `ACCEPT` / `CHANGE TO <rule_actor_id>` / `CHANGE LANE TO <lane_id>` / `N/A`

### Rule-side order relation (unresolved)

- benchmark process pair: `sid-2E045BBD-9F82-497F-8458-49AA9129F991` "Retrieve available data of the data subject", `sid-BB84BABD-20ED-4C97-B755-BDA101C57A8D` "Communicate data and elaborations"
- control BPMN order: `forward only`
- variant BPMN order: `backward only`
- AI recommendation: `N/A` (`ineligible_no_rule_order`)
- confidence: 1.0

- regulation/order evidence: "The data subject shall have the right to receive the personal data concerning him or her, which he or she has provided to a controller, in a structured, commonly used and machine-readable format and have the right to transmit those data to another controller without hindrance from the controller to which the personal data have been provided, where the processing is based on consent pursuant to point (a) of Article 6(1) or point (a) of Article 9(2) or on a contract pursuant to point (b) of Article 6(1); and the processing is carried out by automated means."
- regulation/order evidence: "In exercising his or her right to data portability pursuant to paragraph 1, the data subject shall have the right to have the personal data transmitted directly from one controller to another, where technically feasible."

Evidence/reason: 接收数据和直接传输是不同实现安排；所给原文没有要求先执行本流程的检索活动再通信。

Options: `ACCEPT N/A` / `DEFINE before=<rule_action_id> after=<rule_action_id>`

---

## Pair `syn_out_of_order_07`

- rule: `article17`
- process: `gdpr_5_right_to_withdraw`
- target violation type: `out_of_order`
- regulation text: "The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay and the controller shall have the obligation to erase personal data without undue delay where one of the following grounds applies. The personal data are no longer necessary in relation to the purposes for which they were collected or otherwise processed. The data subject withdraws consent on which the processing is based according to point (a) of Article 6(1), or point (a) of Article 9(2), and where there is no other legal ground for the processing. The data subject objects to the processing pursuant to Article 21(1) and there are no overriding legitimate grounds for the processing, or the data subject objects to the processing pursuant to Article 21(2). The personal data have been unlawfully processed. The personal data have to be erased for compliance with a legal obligation in Union or Member State law to which the controller is subject. The personal data have been collected in relation to the offer of information society services referred to in Article 8(1). Where the controller has made the personal data public and is obliged pursuant to paragraph 1 to erase the personal data, the controller, taking account of available technology and the cost of implementation, shall take reasonable steps, including technical measures, to inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for exercising the right of freedom of expression and information. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for compliance with a legal obligation which requires processing by Union or Member State law to which the controller is subject or for the performance of a task carried out in the public interest or in the exercise of official authority vested in the controller. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for reasons of public interest in the area of public health in accordance with points (h) and (i) of Article 9(2) as well as Article 9(3). Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for archiving purposes in the public interest, scientific or historical research purposes or statistical purposes in accordance with Article 89(1) in so far as the right referred to in paragraph 1 is likely to render impossible or seriously impair the achievement of the objectives of that processing. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for the establishment, exercise or defence of legal claims."
- target BPMN activity: `sid-07817A82-69C2-45A1-9ABC-277F17D93747` "Stop running BPs using withdrawn data" (lane `sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C` "")
- predecessors: sid-32DED13A-06FA-4A9D-BC9D-2B13766E878D ()
- successors: sid-614A49D9-5B63-4E26-9D17-123A91008776 ()

### Rule-side order relation (unresolved)

- benchmark process pair: `sid-07817A82-69C2-45A1-9ABC-277F17D93747` "Stop running BPs using withdrawn data", `sid-1A48D305-CB15-4C57-A988-B39ED62DE531` "Stop using withdrawn data"
- control BPMN order: `forward only`
- variant BPMN order: `backward only`
- AI recommendation: `N/A` (`ineligible_no_rule_order`)
- confidence: 1.0

- regulation/order evidence: "The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay and the controller shall have the obligation to erase personal data without undue delay where one of the following grounds applies."

Evidence/reason: 停止业务流程与停止使用都只是 erase 的支持步骤候选，缺少两个不同的法规动作，不能填 A 先于 A。

Options: `ACCEPT N/A` / `DEFINE before=<rule_action_id> after=<rule_action_id>`

---

## Pair `syn_out_of_order_08`

- rule: `article17`
- process: `gdpr_5_right_to_withdraw`
- target violation type: `out_of_order`
- regulation text: "The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay and the controller shall have the obligation to erase personal data without undue delay where one of the following grounds applies. The personal data are no longer necessary in relation to the purposes for which they were collected or otherwise processed. The data subject withdraws consent on which the processing is based according to point (a) of Article 6(1), or point (a) of Article 9(2), and where there is no other legal ground for the processing. The data subject objects to the processing pursuant to Article 21(1) and there are no overriding legitimate grounds for the processing, or the data subject objects to the processing pursuant to Article 21(2). The personal data have been unlawfully processed. The personal data have to be erased for compliance with a legal obligation in Union or Member State law to which the controller is subject. The personal data have been collected in relation to the offer of information society services referred to in Article 8(1). Where the controller has made the personal data public and is obliged pursuant to paragraph 1 to erase the personal data, the controller, taking account of available technology and the cost of implementation, shall take reasonable steps, including technical measures, to inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for exercising the right of freedom of expression and information. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for compliance with a legal obligation which requires processing by Union or Member State law to which the controller is subject or for the performance of a task carried out in the public interest or in the exercise of official authority vested in the controller. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for reasons of public interest in the area of public health in accordance with points (h) and (i) of Article 9(2) as well as Article 9(3). Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for archiving purposes in the public interest, scientific or historical research purposes or statistical purposes in accordance with Article 89(1) in so far as the right referred to in paragraph 1 is likely to render impossible or seriously impair the achievement of the objectives of that processing. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for the establishment, exercise or defence of legal claims."
- target BPMN activity: `sid-1A48D305-CB15-4C57-A988-B39ED62DE531` "Stop using withdrawn data" (lane `sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C` "")
- predecessors: sid-614A49D9-5B63-4E26-9D17-123A91008776 ()
- successors: sid-BB5F1C3A-DCD5-4C17-90CF-503D23B048FB (Communicate the withdraw)

### Rule-side order relation (unresolved)

- benchmark process pair: `sid-1A48D305-CB15-4C57-A988-B39ED62DE531` "Stop using withdrawn data", `sid-BB5F1C3A-DCD5-4C17-90CF-503D23B048FB` "Communicate the withdraw"
- control BPMN order: `forward only`
- variant BPMN order: `backward only`
- AI recommendation: `N/A` (`ineligible_no_rule_order`)
- confidence: 1.0

- regulation/order evidence: "The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay and the controller shall have the obligation to erase personal data without undue delay where one of the following grounds applies."
- regulation/order evidence: "Where the controller has made the personal data public and is obliged pursuant to paragraph 1 to erase the personal data, the controller, taking account of available technology and the cost of implementation, shall take reasonable steps, including technical measures, to inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data."

Evidence/reason: 后端通知数据主体与 inform controllers 接收者不符；没有正确的通知动作端点。

Options: `ACCEPT N/A` / `DEFINE before=<rule_action_id> after=<rule_action_id>`

---

## Pair `syn_out_of_order_09`

- rule: `article16`
- process: `gdpr_6_right_to_rectify`
- target violation type: `out_of_order`
- regulation text: "The data subject shall have the right to obtain from the controller without undue delay the rectification of inaccurate personal data concerning him or her. Taking into account the purposes of the processing, the data subject shall have the right to have incomplete personal data completed, including by means of providing a supplementary statement."
- target BPMN activity: `sid-2D1BF282-F735-4BE0-996F-4D9C7DBED814` "Rectify data" (lane `sid-95D07626-A357-422E-830F-B1E57917DB74` "")
- predecessors: sid-EC693640-2075-44F6-8609-7C4FDCB2A7C0 ()
- successors: sid-F9E3B912-20D2-4AD2-B92F-811216B4F746 (Communicate the rectification
)

### Actor / lane binding (unresolved)

Relevant Direct-LLM Rule Record actor candidates:

* `gdpr_article16_s001.c1.actor.a01`: "The data subject" (sample=gdpr_article16_s001)
* `gdpr_article16_s002.c1.actor.a01`: "the data subject" (sample=gdpr_article16_s002)

- candidate actor span evidence: "the controller"
- right-holder reference: `gdpr_article16_s001.c1.actor.1` "The data subject"
- confidence: not recorded (status/evidence-based AI resolution)

**AI recommendation:** rule actor `N/A`; process executor `Data Controller`; expected lane `sid-95D07626-A357-422E-830F-B1E57917DB74` "" (status `inferred_counterparty_executor`).

Evidence/reason: 保留 data subject 为权利主体；依据 obtain from the controller 将 controller 判为实现更正的相对执行方，并与 Data Controller 对应。该关系是 AI 补充推断。

Options: `ACCEPT` / `CHANGE TO <rule_actor_id>` / `CHANGE LANE TO <lane_id>` / `N/A`

### Rule-side order relation (unresolved)

- benchmark process pair: `sid-2D1BF282-F735-4BE0-996F-4D9C7DBED814` "Rectify data", `sid-F9E3B912-20D2-4AD2-B92F-811216B4F746` "Communicate the rectification
"
- control BPMN order: `forward only`
- variant BPMN order: `backward only`
- AI recommendation: `N/A` (`ineligible_no_rule_order`)
- confidence: 1.0

- regulation/order evidence: "The data subject shall have the right to obtain from the controller without undue delay the rectification of inaccurate personal data concerning him or her."
- regulation/order evidence: "Taking into account the purposes of the processing, the data subject shall have the right to have incomplete personal data completed, including by means of providing a supplementary statement."

Evidence/reason: 有更正动作，但当前 article16 动作集合没有更正后通知的端点，不能据流程连线增加法规顺序。

Options: `ACCEPT N/A` / `DEFINE before=<rule_action_id> after=<rule_action_id>`

---

## Pair `syn_out_of_order_10`

- rule: `article15`
- process: `gdpr_3_right_to_access`
- target violation type: `out_of_order`
- regulation text: "The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the following information the purposes of the processing. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the categories of personal data concerned. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the recipients or categories of recipient to whom the personal data have been or will be disclosed, in particular recipients in third countries or international organisations. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and where possible, the envisaged period for which the personal data will be stored, or, if not possible, the criteria used to determine that period. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the existence of the right to request from the controller rectification or erasure of personal data or restriction of processing of personal data concerning the data subject or to object to such processing. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the right to lodge a complaint with a supervisory authority. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and where the personal data are not collected from the data subject, any available information as to their source. The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the existence of automated decision-making, including profiling, referred to in Article 22(1) and (4) and, at least in those cases, meaningful information about the logic involved, as well as the significance and the envisaged consequences of such processing for the data subject. Where personal data are transferred to a third country or to an international organisation, the data subject shall have the right to be informed of the appropriate safeguards pursuant to Article 46 relating to the transfer. The controller shall provide a copy of the personal data undergoing processing. For any further copies requested by the data subject, the controller may charge a reasonable fee based on administrative costs. Where the data subject makes the request by electronic means, and unless otherwise requested by the data subject, the information shall be provided in a commonly used electronic form. The right to obtain a copy referred to in paragraph 3 shall not adversely affect the rights and freedoms of others."
- target BPMN activity: `sid-7CABF962-BFAE-4BFD-9C33-E7ED63548824` "Retrieve elaborations" (lane `sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F` "")
- predecessors: sid-1FE17422-E502-4D46-B8C9-0BB2FFADCA39 ()
- successors: sid-A98B48ED-872F-48D6-BA09-BDEA8568525A ()

### Rule-side order relation (unresolved)

- benchmark process pair: `sid-7CABF962-BFAE-4BFD-9C33-E7ED63548824` "Retrieve elaborations", `sid-BB84BABD-20ED-4C97-B755-BDA101C57A8D` "Communicate data and elaborations"
- control BPMN order: `forward only`
- variant BPMN order: `backward only`
- AI recommendation: `N/A` (`ineligible_no_rule_order`)
- confidence: 1.0

- regulation/order evidence: "The data subject shall have the right to obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed, and, where that is the case, access to the personal data and the following information the purposes of the processing."
- regulation/order evidence: "The controller shall provide a copy of the personal data undergoing processing."

Evidence/reason: 检索处理信息和对外提供数据之间的先后来自流程实现，不是当前原文明确的两个法规动作次序。

Options: `ACCEPT N/A` / `DEFINE before=<rule_action_id> after=<rule_action_id>`

---

## Approval result format

Return one line per pair, for example:

```text
syn_incorrect_actor_03: action=N/A; actor=ACCEPT
syn_out_of_order_01: order=ACCEPT N/A
```

No ID should be searched by the user; every option above is already printed with its exact id.

