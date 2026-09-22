# Stage 3 标注候选：AI 初审后交人工复核

已逐项核对 30/30 个 pair。按你的宽松标准，合理准备步骤和可解释歧义保留，只修正明确的动作、执行者或通知对象错配。

**先看下方 30 项简表。“建议保留 / 建议修正”都是我的意见，还没有替你确认。**

- 13 项保留原绑定，14 项建议修正至少一个绑定字段，3 项维持原来的空 action。
- 动作：20 项保留原非空候选，5 项替换，2 项清空，3 项保留原 null；最终 25 项有候选、5 项为 null。
- 执行者：19 项保留，3 项改用已有控制者 span，8 项因缺少控制者 span 而留空；30 个 control lane 全部保留。
- 顺序：10/10 组活动顺序正确；属于流程顺序，尚未确认法规顺序。

状态仍为 proposal_awaiting_human_review。本报告仅供复核，未作为实验输入，未改原 proposal、blank、benchmark 或 Gold；未调用外部 LLM/API、未运行实验。

## 具体修正

1. **执行者区分权利享有人与履行方（11 项）**：IA-05/06/07/10、MA-08/09/10、OO-05/06/09/10。原数据主体 span 本身不是抽取错误，但不能据此说控制者任务由数据主体执行。article15 的 3 项改用已有控制者 span；article16/20 的 8 项缺少控制者 span，actor ID 留空，同时保留 Data Controller 文字建议和 lane。
2. **通知对象不符（IA-09）**：Communicate the withdraw 实际发给 Data subject，原规则要求通知其他 controllers 删除数据，action 留空。
3. **通知不能代替实际更正（MA-08）**：Communicate the rectification 与 Rectify data 是不同节点；现有 article16 无通知动作，action 留空。
4. **恢复完整句的含义（MA-06、OO-07）**：take reasonable steps 后接“通知其他控制者”，不能泛指内部停业务流程。改为 erase personal data 的支持步骤候选；停机不等于已经删除。
5. **使用更符合流程视角的已有动作（IA-07、MA-09、OO-05）**：控制者向第三方传数据改用 article20_s002 的直接传输候选；取回实际数据改用 article15_s001.c2 的数据访问候选，避免绑成仅确认是否处理数据。

以上项目有交集，合计修正 14 个 pair。

## 宽松保留的解释

- 收集泄露数据/主体、取回补充信息等保留为规则动作的准备步骤，不因原分数低于 0.50 直接否定。
- article22 的撤回权/更正权告知、合法利益检查保留为权利保障候选；BPMN 未独立证明 article22 的特定适用条件，词语相似不等于全部义务已完成。
- Stop using withdrawn data 保留为删除流程支持候选；停止使用不与物理擦除作等价声明。
- article20 的 Third Party 暂按可携带场景中的另一控制者理解，供你复核。

## 30 项简表

IA = syn_incorrect_actor_；MA = syn_missing_action_；OO = syn_out_of_order_。编号补两位可还原完整 pair_id。表中控制者指流程执行方。

| Pair | 目标活动 | 我的意见 | 推荐动作含义 | 执行者候选 |
|---|---|---|---|---|
| IA-01 | Retrieve breached subjects | 建议保留 | 描述泄露情况（取数为准备步骤） | 保留控制者 |
| IA-02 | Handle delay | 建议保留 | 附上延迟原因 | 保留控制者 |
| IA-03 | Retrieve identity and contact details | 维持空值 | 未找到合适 action，保留空值 | 保留控制者 |
| IA-04 | Add "existence of the right to withdraw" | 建议保留 | 保障数据主体权利（宽松解释） | 保留控制者 |
| IA-05 | Retrieve elaborations | 建议修正 | 访问数据及补充信息（准备步骤） | 改用已有控制者 span |
| IA-06 | Retrieve available data of the data subject | 建议修正 | 接收个人数据的权利（准备步骤） | 控制者；actor ID 留空 |
| IA-07 | Communicate data and elaborations | 建议修正 | 改为：控制者之间直接传输数据 | 控制者；actor ID 留空 |
| IA-08 | Stop using withdrawn data | 建议保留 | 删除个人数据（仅支持步骤候选） | 保留控制者 |
| IA-09 | Communicate the withdraw | 建议修正 | 清空：原动作明确不符 | 保留控制者 |
| IA-10 | Rectify data | 建议修正 | 更正不准确的个人数据 | 控制者；actor ID 留空 |
| MA-01 | Retrieve breached subjects | 建议保留 | 描述泄露情况（取数为准备步骤） | 保留控制者 |
| MA-02 | Retrieve breached data | 建议保留 | 描述泄露情况（取数为准备步骤） | 保留控制者 |
| MA-03 | Add "existence of the right to withdraw" | 建议保留 | 保障数据主体权利（宽松解释） | 保留控制者 |
| MA-04 | Add "existence of the right to rectify of personal data" | 建议保留 | 保障数据主体权利（宽松解释） | 保留控制者 |
| MA-05 | Communicate data and elaborations | 建议保留 | 向数据主体提供数据副本 | 保留控制者 |
| MA-06 | Stop running BPs using withdrawn data | 建议修正 | 改为：删除个人数据（仅支持步骤候选） | 保留控制者 |
| MA-07 | Check if withdrawn data are relevant | 维持空值 | 未找到合适 action，保留空值 | 保留控制者 |
| MA-08 | Communicate the rectification | 建议修正 | 清空：原动作明确不符 | 控制者；actor ID 留空 |
| MA-09 | Communicate data and elaborations | 建议修正 | 改为：控制者之间直接传输数据 | 控制者；actor ID 留空 |
| MA-10 | Rectify data | 建议修正 | 更正不准确的个人数据 | 控制者；actor ID 留空 |
| OO-01 | Retrieve breached subjects | 建议保留 | 描述泄露情况（取数为准备步骤） | 保留控制者 |
| OO-02 | Retrieve breached data | 建议保留 | 描述泄露情况（取数为准备步骤） | 保留控制者 |
| OO-03 | Retrieve identity and contact details | 维持空值 | 未找到合适 action，保留空值 | 保留控制者 |
| OO-04 | Check if legitimate interests are presents | 建议保留 | 保障数据主体权利（宽松解释） | 保留控制者 |
| OO-05 | Retrieve available data of the data subject | 建议修正 | 改为：访问数据及补充信息（准备步骤） | 改用已有控制者 span |
| OO-06 | Retrieve available data of the data subject | 建议修正 | 接收个人数据的权利（准备步骤） | 控制者；actor ID 留空 |
| OO-07 | Stop running BPs using withdrawn data | 建议修正 | 改为：删除个人数据（仅支持步骤候选） | 保留控制者 |
| OO-08 | Stop using withdrawn data | 建议保留 | 删除个人数据（仅支持步骤候选） | 保留控制者 |
| OO-09 | Rectify data | 建议修正 | 更正不准确的个人数据 | 控制者；actor ID 留空 |
| OO-10 | Retrieve elaborations | 建议修正 | 访问数据及补充信息（准备步骤） | 改用已有控制者 span |

## 10 组顺序复核

下列方向在 control 中成立，在 variant 中反转，全部保留；规则动作端点只是建议，没有填入 decision_order 字段。

| Pair | 流程方向（before → after） | 规则动作端点情况 |
|---|---|---|
| OO-01 | Retrieve breached subjects → Notify national authority | 有不同 action 候选，法规先后仍待确认 |
| OO-02 | Retrieve breached data → Retrieve breached subjects | 两端落在同一 action，不能填 A → A |
| OO-03 | Retrieve identity and contact details → Collect consent information | 至少一端缺少合适规则动作 |
| OO-04 | Check if legitimate interests are presents → Collect consent information | 至少一端缺少合适规则动作 |
| OO-05 | Retrieve available data of the data subject → Communicate data and elaborations | 有不同 action 候选，法规先后仍待确认 |
| OO-06 | Retrieve available data of the data subject → Communicate data and elaborations | 有不同 action 候选，法规先后仍待确认 |
| OO-07 | Stop running BPs using withdrawn data → Stop using withdrawn data | 两端落在同一 action，不能填 A → A |
| OO-08 | Stop using withdrawn data → Communicate the withdraw | 至少一端缺少合适规则动作 |
| OO-09 | Rectify data → Communicate the rectification | 至少一端缺少合适规则动作 |
| OO-10 | Retrieve elaborations → Communicate data and elaborations | 有不同 action 候选，法规先后仍待确认 |

OO-02 的 breached data / subjects 都指向同一个 describe 动作；OO-07 的两个停用步骤也都只宽松关联 erase。流程有先后，不代表法规动作可以自我先于。

## 逐项理由

相同 rule + 活动合并说明；精确动作/角色 ID、原候选和结构证据保存在同名 JSON。

| 涉及 Pair | 我的动作审核理由 |
|---|---|
| IA-01, MA-01, OO-01 | 保留。收集受影响主体可作为描述泄露性质及主体数量的准备步骤，不要求活动名逐字对应；不声称收集本身已完成通知义务。 |
| IA-02 | 保留。子流程含 72 hours 触发及向 National Authority 发送延迟通知，支持延迟说明义务的实现候选。 |
| IA-03, OO-03 | 保留 null。当前 article22 动作集合没有身份/联系方式收集动作，不因候选为空而强行补齐。 |
| IA-04, MA-03 | 宽松保留为保护权利的配套告知措施。不能仅凭 rights 同词证明等价；article22_s005 有特定适用条件，BPMN 未独立证明条件成立。本候选不表示一般同意告知已经履行 article22 全部要求。 |
| IA-05, OO-10 | 保留为实现数据及补充信息访问权的准备步骤。规则从权利享有人视角表述，流程由控制者执行；两者是权利与履行方关系，不是同一执行者。 |
| IA-06, OO-06 | 宽松保留为保障数据可携带/接收权的准备步骤。receive 的权利主体为数据主体，实际取数由控制者完成，不把二者当成同一 actor。 |
| IA-07, MA-09 | 修正为 article20_s002 的控制者之间直接传输。BPMN 由 Data Controller 发往 Third Party，比原数据主体自行 transmit 的视角更相符；Third Party 是否为另一控制者仍属场景假设。 |
| IA-08, OO-08 | 宽松保留为删除/撤回处理链中的支持步骤。停止使用不等于已经物理擦除，修正原证据中直接等同的说法；活动名本身不能证明完整删除义务已履行。 |
| IA-09 | 清空原 action。BPMN messageFlow 明确发给 Data subject，原规则要求 inform controllers（通知其他控制者），接收对象不同；当前 article17 动作集合没有向本人反馈完成的动作。 |
| IA-10, MA-10, OO-09 | 保留。目标直接执行数据更正。规则中数据主体享有请求更正权，流程中的实际更正执行者是控制者。 |
| MA-02, OO-02 | 保留。收集泄露数据可作为描述数据类别和数量的准备步骤，与收集主体可以共同支持同一较宽规则动作。 |
| MA-04 | 宽松保留为保护权利的配套告知措施。活动是告知更正权，不是实际更正；article22 的适用条件尚未由 BPMN 单独证明。 |
| MA-05 | 保留。BPMN 消息发给 Data Subject，与控制者提供数据副本相符；elaborations 是该活动额外承载的信息。 |
| MA-06, OO-07 | 改为 erase personal data 的支持步骤。原 article17_s008 的 take reasonable steps 在完整句中专为通知其他控制者，不能脱离 to inform 的目的泛指任意内部停机；停机本身仍不能证明已删除数据。 |
| MA-07 | 保留 null。流程中该检查决定是否先停业务流程；现有规则动作集合无对应检查，不把 condition span 当作 action id。 |
| MA-08 | 清空原 action。流程把 Rectify data 与向 Data Subject 发送更正反馈分成两个节点，通知不能代替实际更正；当前 article16 动作集合无独立通知动作。 |
| OO-04 | 宽松保留为 safeguard 的可能检查步骤。流程中它也可能指处理依据的合法利益检查，不能仅因 legitimate interests 同词就确定为数据主体利益保障；保留歧义供人工判断，不提升原置信度。 |
| OO-05 | 修正为 article15_s001.c2 的数据访问动作。原候选是获得是否处理数据的 confirmation，而目标取回实际数据；保留为访问权的准备步骤。 |

## 文件核对与使用说明

- [完整 JSON 审核件](stage3_binding_annotation_agent_review_v1.json)：每项包含 original_proposal、recommended_proposal、agent_review。
- 原 proposal 两份逐字节相同。27 个原 action ID、30 个原 actor ID 均能定位到现有 Rule Records，文本一致。
- 30 个活动名、30 个 lane/participant 归属、60 个 control/variant 文件角色哈希及 10 组顺序反转全部核对通过；推荐的非空 span 均来自对应 rule 的现有集合。
- 当前 lane name 全为空。candidate_lane 是 lane ID，Data Controller 是 participant name；blank 的 decision_expected_lane 文档写 lane name。导入人工决定前仍需明确字段表示，不能把 ID 冒充已有 name；本轮不改 schema。
- 原 confidence 仅为来源主观分数，未重新校准；替换项分数也不是正确率。
- JSON 的 raw_file_sha256_at_review 为本次工作区原始字节指纹；其他环境若改变行尾，应区分字节差异与内容差异。
- 按审核制品范围核对内容、引用、结构和 SHA256，未跑实验 audit、代码测试或全量测试。scoped Git checkpoint 作为本轮变更记录。

## 你的复核

可以直接按上表回复接受建议，或列出要改的编号（如 IA-09、MA-08）。本报告尚无你的签核，未代写 reviewed / adjudicated 状态。

原有 3 个 null 加本次清空的 2 个 action，共 5 个空 action；另有 8 个空 actor span。接受本轮意见也不自动补齐这些字段、产生法规顺序或生成 Gold。
