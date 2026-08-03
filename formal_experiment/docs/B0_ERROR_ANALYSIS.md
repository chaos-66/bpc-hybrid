# B0 错误分析报告（为什么 B0 的 P/R 不高）

> 任务：B0-R1-ERR（错误分析与成因文档；本轮不实施修复）
> 状态：development only，非正式结果
> 数据基准：C3 注册 attempts（`s27_estg150_b0_enhanced_v10a_r1a_c3_hist56d_v1/b0_attempts.json`，tracked，SHA-256=c694f7cd…），与 56d2b03 历史 Layer E 构建的同一 canonical Gold（用户授权只读；不读当前 Layer E）
> 复现：`python -m scripts.analyze_b0_error_types`（`scripts/analyze_b0_error_types.py`）

## 1. 摘要

B0 在正确的 Sun literal-overlap v2 主口径下 **F1≈0.71**（P=0.684，R=0.738）。对全部 1055 个 Gold span 与 1111 个预测 span 做逐 span 失败分类后，低分原因可归结为 **5 个量化成因 + 1 组结构性限制**：

| 编号 | 成因 | 量化证据 | 可修性 |
|---|---|---|---|
| C1 | **Action span 过度吞并**（动作 span 吞掉主语与句尾约束内容） | constraint 的 143 个 missed 中 108 个内容其实在别的字段里，其中 57 个被 action 覆盖；matched 的 212 个 action 中 **192 个为过长，中位超出 54 字符、最大 739** | **可修**（收益最大） |
| C2 | **constraint↔condition 双向字段混淆** | constraint 的 178 个 misclassified 中 152 个压到别的字段 Gold 上，其中 114 个压在 condition 上 | 部分可修（消歧规则；有 P/R trade-off 风险） |
| C7 | **Under-extension（span 过短）** | matched 的 779 个 Gold span 中 202 个被预测短于 Gold（中位短 14 字符）：modality evidence 80、constraint 51、condition 50、action 16 | 可修（边界/evidence 范围） |
| C3 | **模态四分类 label 混淆**（独立面板） | evidence 匹配上的 clause label 准确率 79.3%；definition↔obligation 混淆 16+7 | 可修（B0-R1-ALIGN 路由） |
| C4 | **Actor 抽取不足** | 22 个 missed：8 个含词典词（依赖句法失败，可修）、14 个词典无覆盖（需决策） | 部分可修 |
| C5 | **Clause 规划失配** | 231 个 Gold clause 中 38 个（16%）无 pred clause 以 IoU≥0.5 配对 | 低优先级（v2 口径不依赖 clause 对齐） |
| C6 | **结构性限制**（缺 Sun 原资产、词典规模、Gold 语义差异、H1 回落 B0） | 见 §5.6 | 需资产/需用户决策/需正式 Gold |

**最重要结论：constraint 字段（F1=0.489）之所以是短板，不是因为"抽不到"，而是因为"抽错地方"——被 action 吞掉（C1）和被 condition 抢走（C2）合计解释了其绝大多数错误。**

## 2. 数据与方法

- 评价口径：`sun_literal_overlap_evaluation@2.0.0`（statement 级、同字段任意非空字符交叠、无 clause alignment、无一对一 assignment；modality 只评 evidence span）。出处：`MASTER_PIPELINE.md` §8.6 与 `configs/evaluation/sun_table8_literal_overlap_v2.json`。
- Gold：`build_canonical_gold_records`（当前 HEAD `estg150_b0_development.py:157`）从 56d2b03 历史 Layer E + membership 构建，150 条、1055 个 Gold span（六字段合计）、231 个 Gold clause。
- 预测：C3 注册 attempts（150 条、1111 个 span、249 个 clause），与 Gold 同一进程、同一 Gold 对象评价（详见 B0-R1-E2 manifest `s27_estg150_b0_v10a_vs_r1a_c3_sun_literal_v2_hist56d_v1/manifest.json`）。
- 失败分类定义：
  - `missed`（Gold span 无同字段预测相交）：子类 `content_in_other_field`（内容被其它字段的预测覆盖）与 `no_overlap`（完全没抽到）；
  - `misclassified`（预测 span 无同字段 Gold 相交）：子类 `overlaps_other_field_gold`（压到别的字段 Gold 上）与 `no_gold_overlap`（与任何 Gold 都不相交）；
  - 匹配质量：exact（起止完全一致）/ containment（一方包含另一方）/ partial（部分交叠）。
- 六字段合计：GT=1055，pred=1111，matched_gold=779，missed=276，matched_pred=760，misclassified=351。

## 3. 总体表现（B0 / D1 / H1）

| 方法 | P | R | F1 | 备注 |
|---|---|---|---|---|
| B0（v10a=C3） | 0.681 | 0.741 | 0.710 | v10a 与 C3 在 v2 口径下几乎相同（ΔF1=+0.0003） |
| D1（deepseek v4pro，直接 LLM） | 0.907 | 0.664 | 0.767 | P 高 R 低；constraint R=0.288 最低 |
| H1（B0+LLM 回退） | 0.681 | 0.741 | 0.710 | **与 B0 完全相同**：H1 的 LLM patch 全部被验证器/merge 拒绝，全部回落 B0（S2.8D 历史），不构成独立结果 |

D1 数据出处：`outputs/development/s28_s29_deepseek_v4pro_sun_literal_v1/metrics.json`（tracked）；B0 数据出处：B0-R1-E2 重评产物。

## 4. 失败类型分布（C3，逐 span 分类）

| 字段 | GT | pred | matched_gold | missed | missed: 在别字段 | missed: 全无 | matched_pred | misclassified | 错: 压别字段 | 错: 无 Gold |
|---|---|---|---|---|---|---|---|---|---|---|
| modality | 231 | 249 | 208 | 23 | 21 | 2 | 207 | 42 | 24 | 18 |
| actor | 48 | 35 | 26 | 22 | 14 | 8 | 25 | 10 | 4 | 6 |
| action | 247 | 244 | 212 | 35 | 31 | 4 | 208 | 36 | 33 | 3 |
| condition | 214 | 239 | 163 | 51 | 42 | 9 | 157 | 82 | 64 | 18 |
| constraint | 302 | 330 | 159 | 143 | 108 | 35 | 152 | 178 | 152 | 26 |
| exception | 13 | 14 | 11 | 2 | 2 | 0 | 11 | 3 | 3 | 0 |
| **合计** | **1055** | **1111** | **779** | **276** | **218** | **58** | **760** | **351** | **280** | **71** |

要点：

- **79%（218/276）的 missed Gold span 内容其实被抽到了，只是落错了字段**；真正完全没抽到的只有 58 个。
- **80%（280/351）的错误预测压到了别的字段的 Gold 上**——字段归属错误是压倒性的失败模式，其次是边界/吞并，真正"凭空捏造"的只有 71 个。
- 匹配质量：exact=230，containment=420，partial=129；其中 constraint/action 以 containment 为主（action 的 112/212 是包含型），即**边界过宽**问题在已匹配项里同样普遍。

字段混淆方向（最显著组合）：

| 方向 | 数量 | 含义 |
|---|---|---|
| Gold constraint ← pred action | 57+ | constraint 内容被 action span 吞掉（C1 主证据） |
| pred constraint → Gold condition | 114 | constraint 过度抽取压到 condition（C2 主证据） |
| pred condition → Gold constraint | 31 | condition 过度抽取压到 constraint（C2 反向） |
| Gold action ← pred modality | 18 | 动作内容被 modality evidence 覆盖 |

## 5. 根因清单

### C1. Action span 过度吞并 —— 【可修，预期收益最大】

- 现象：action span 从主语开始、延伸到句尾，把 constraint/condition 内容一起吞掉。
- 证据（注册 C3 产物 + 本分析）：
  - `estg_000003`：Gold constraint `a shorter period`，预测 action 为整句 `It may cover a shorter period if …`（0-37）；
  - `estg_000021`：Gold constraint `in such a quantity that actually precludes a sale`，预测 action 为 `sold and are granted only in such a quantity that actually precludes a sale. 21.`；
  - 244 个 action 中 8 个以冠词开头（如 `The actuarial reserve shall be calculated in accordance with…`），即主语被包进 action；
  - 定量：constraint 的 143 个 missed 中 57 个只被 action 覆盖（另 16 个被 action+condition、10 个被 modality 等），合计绝大多数 missed 与 action 吞并有关；
  - 边界方向：matched 的 212 个 action Gold span 中 **192 个（91%）预测长于 Gold，中位超出 54 字符、均值 69、最大 739**——这是全系统最稳定、量级最大的单一缺陷，不只是"偶尔吞 constraint"。
- 代码位置：`b0_v10/actor_action.py:39-54`（`_subtree_span` 把 nsubj/obl 等**所有**依赖子树节点纳入 action 范围）、`actor_action.py:127-171`（head 子树 + `safe_action_slice` max_chars=80 向右取到最右安全边界）。
- 为什么这样设计：动词子树天然包含宾语与状语；Sun 原方法的 action 是短语级（VP），而这里取整棵子树，超出发话短语。
- 预期影响：修复后 constraint 的 missed 显著下降、action 的 P 上升；注意 action 的 containment 匹配（112 个）中部分会变成 partial/exact，需重评确认 trade-off。
- 风险：需要真实 CoreNLP 输出验证子树边界；改动属于行为变化，必须重跑 v2 重评并记录 delta。

### C7. Under-extension（span 过短）—— 【可修】

- 现象：与 C1 相反，**202 个已匹配的 Gold span 被预测得比 Gold 短**（中位短 14 字符、均值 36、最大 307），主要分布在 modality evidence（80 个）、constraint（51）、condition（50）。
- 代码位置：modality evidence 只取到情态词附近（`b0_v10/modality.py` evidence 范围、`definition_resolver.py` evidence 选择），condition/constraint 的 `safe_window_end`/scope 截断语义。
- 预期影响：改善已匹配 span 的边界质量（containment/partial 占比下降、exact 上升）；不影响 matched 计数，但提升语义覆盖与诊断面板。
- 风险：与 C1 相反方向，修改边界逻辑时需同时防止过修（C1）与不足（C7），用重评逐批验证。

### C2. constraint↔condition 双向字段混淆 —— 【部分可修，有 trade-off 风险】

- 现象：同一段文本在 Gold 里是 condition、预测写成 constraint（114 个），或反之（31 个）。
- 代码位置：`b0_v10/scope.py:37-49`（`_SURFACE_SCOPE` 打字：`within/before/after/until/prior to…` → TEMPORAL_LIMIT；`if/when/where/once/in case` → CONDITION_SUBORDINATOR）、`resources/corenlp/sun_phrase_patterns_v3_enhanced.json:56-60,69-78`（condition 与 constraint 的 Tregex 模式大量共享 `in/upon/on/after/before/to`、`subject to`、`for … purpose` 等 cue）。
- 本质：法律条款中时间/条件边界在语义上就是模糊的（"within 30 days if…" 同时含两种语义）；Gold 的裁决是人工语义判定。
- 预期影响：消歧规则（如连词优先、`if` 优先于 `within`）可减少 114+31 中的一部分；但**必然伴随 P/R trade-off**，MASTER_PIPELINE §8.6 允许字段间 trade-off，需逐次重评验证净收益。
- 风险：可能伤及 constraint 的 R（它已是最弱字段）；需小步实验。

### C3. 模态四分类 label 混淆 —— 【可修，独立面板】

- 现象：evidence 匹配的 208 个 clause 中，label 准确率 79.3%；混淆集中在 definition↔obligation（16+7）与 permission/prohibition（5+3）。
- 代码位置：`b0_v10/definition_resolver.py`（definition_structure 路由）、`b0_v10/alignment.py:92-114,162-209`（equal-count/monotone 路径的"伪 validated"：两侧各出现任意锚即标 validated，不校验 DE↔EN 语义对应 → 路由输入不可靠）。
- 注意：此面板不影响六字段 span 主表，但影响论文中模态四分类报告。
- 预期影响：DE/EN cue 验证修复后 label 混淆下降；这是 B0-R1 明确列出的"德英 cue 验证"待办。

### C4. Actor 抽取不足 —— 【部分可修】

- 现象：GT=48，missed=22（R=0.54）。22 个 missed 中：
  - **8 个含词典词**（`the employee`×2、`the Federal Minister…`、`an employee`、`the person performing the activity`、`the person required to make the deduction`、`the taxpayer`(estg_000206)、`the recipient`）→ 词典能接受、但 nsubj→动词 依赖边未找到或 clause 边界把它切走 → **依赖/句法失败，可修**；
  - **14 个不含词典词**（`the legal successor`、`the spouse`、`A child`、`The bank`×2、`The building society`×2、`The audit body`、`The beneficiary`、`the owners or shareholders`、`It`(estg_000003) 等）→ 词典覆盖不足 → **需用户决策**（扩展词典为公开 marker，S2.3 边界禁止训练数据）；
  - 部分 actor 同时被 C1 的 action 吞并（如 estg_000206 的 `the spouse shall not be entitled…` 被 action 覆盖）。
- 代码位置：`b0_v10/actor_action.py:66-76`（`filter_actor_span` 要求至少一个词在 `lexicon.actor_surfaces`，且 14 词上限）、`resources/lexicon/actor_markers_en_v2.json`（37 个 surface）。
- 预期影响：修复依赖边查找后可回收 8 个 missed；词典扩展由用户决定。

### C5. Clause 规划失配 —— 【低优先级】

- 现象：231 个 Gold clause，193 个（84%）有 pred clause 以 IoU≥0.5 配对，**38 个（16%）无配对**；pred 侧共 249 个 clause。
- 代码位置：`b0_v10/segmentation.py`、`estg150_b0_development_v3.py plan_clause_units_v4`（B0-R0 的 v2→v3 clause-planner 换用曾导致旧 diagnostic 口径下的差异；v2 主口径不依赖 clause 对齐，影响被摊薄）。
- 处理建议：v2 口径下优先级低；但 clause 边界影响 C1/C2 的 span 生成，修复 C1/C2 时一并观察。补充核查：58 个"完全没抽到"的 span 中仅 4 个位于未配对 clause（clause 失配不是漏抽主因）。

### C6. 结构性限制 —— 【需资产 / 需用户决策 / 需正式 Gold】

1. **Sun 原代码/词典/权重不可得**：无法 exact reproduction；方法级独立复现是允许的正式表述（`MASTER_PIPELINE.md` §2）。→ 不可修，属披露项。
2. **词典规模**：actor 37、modality 29、condition 34、constraint 45、exception 16、public marker 共 161 个激活项；扩展属用户决策（公开 marker lexicon 为 dev-only，禁止训练/评测数据回流）。→ 需用户决策。
3. **Gold 语义与方法的差异**：如 Gold 把代词 `It`(estg_000003)、`A child` 等标为 actor；把 `a shorter period` 标为 constraint。方法以"名词短语 + 词典 + 依赖关系"为 actor 判据。这类差异需人工 Gold 裁决后再定论是方法缺陷还是 Gold 语义。→ 需正式 Gold/用户裁决。
4. **H1 回落 B0**：H1 的 LLM patch 全部被离线验证器/原子 merge 拒绝（S2.8D 事件历史），与 B0 本身无关；H1 改进是独立任务（transport/span canonicalizer 方向），不在 B0 修复范围内。

## 6. 修复路线建议（按预期收益排序；本轮不实施）

该路线已并入 `MASTER_PIPELINE.md` §8.6.1（B0-R1 子批次表），本处为速查：

| 顺序 | 批次 | 内容 | 预期影响（定性） | 风险 |
|---|---|---|---|---|
| 1 | B0-R1-ACTION | 修复 action 子树吞并（排除 nsubj/obl，收紧到 VP 范围） | constraint missed 大降、action P 升、actor R 升 | 需 CoreNLP 运行验证；行为变化 |
| 2 | B0-R1-SCOPE-DISAMBIG | constraint↔condition 消歧规则（小步、逐次重评） | 字段混淆 114+31 部分回收 | P/R trade-off，需净收益验证 |
| 3 | B0-R1-ALIGN | DE/EN cue 验证（equal-count/split 伪 validated 修复） | modality label 准确率升 | 影响 modality 路由计数 |
| 4 | B0-R1-BRIDGE | `<`/`<<`、multi-match/Tsurgeon 消费 | 消除潜伏错误源 | 当前 registry 无 operation，风险潜伏 |
| 5 | B0-R1-ACTOR | 多词 Actor 生产路径测试 + 依赖边查找 + C7 过短边界 | actor R、modality/constraint/condition 边界质量 | 需 CoreNLP 运行验证 |
| 6 | （决策项） | actor 词典扩展（LEXICON-DECISION）、clause 规划复核 | actor R、clause 匹配 | 需用户授权/正式 Gold |

每个批次必须：focused tests → `audit_project.py --with-tests` → 用 B0-R1-E2 同一协议重评（同一 canonical Gold、同一进程双评）→ 记录前后 delta 与原因 → `record_change.py` → 独立 commit + push。

## 7. 与 D1/H1 的关系（供导师汇报参考）

- D1 的短板与 B0 不同：D1 是 **P 高 R 低**（R=0.664），constraint R=0.288、exception R=0.385 —— LLM 漏抽而非错抽；B0 是 **R 高 P 低**（P=0.684），错抽为主。两者失败模式互补，这本身是论文可写的结果。
- H1 当前等于 B0：H1 的 LLM 修正从未被接受，属于 H1 管线问题，不是 B0 问题；若 H1 的 patch 通道修复，H1 才可能真正高于 B0。
- 因此"B0 为什么只有 0.71"的直接答案是：**字段归属错误（C1+C2）占绝对主导**——修好这两项，B0 的 P 预计可显著回升；剩余的天花板由词典规模与 Gold 语义裁决（C4/C6）决定。

## 8. 附录：复现与数据出处

- 分析脚本：`formal_experiment/scripts/analyze_b0_error_types.py`（只读；`git show 56d2b03:<path>` 取历史 Layer E/membership，临时目录在 `formal_experiment/.tmp/`，自动清理）。
- 评价结果：`formal_experiment/outputs/development/s27_estg150_b0_v10a_vs_r1a_c3_sun_literal_v2_hist56d_v1/`（v10a_metrics.json / c3_metrics.json / delta.json / manifest.json，全部 tracked）。
- 关键 hash：canonical Gold semantic `5d7ec7f6…`；canonical membership `e8e62686…`（与注册绑定一致）；C3 attempts `c694f7cd…`；56d2b03 = `56d2b03a1fb4e206db5bb92a8eb5ed51b942b650`。
- 全部数字为 development only；正式结论需 B0-R3（固定快照运行）与正式 Gold 冻结后。
