# B0 错误分析报告（为什么 B0 的 P/R 不高）

> 任务：B0-R1-ERR（错误分析与成因文档）；B0-R1-ACTION/SCOPE-DISAMBIG/ALIGN/BRIDGE/ACTOR 已按 §8.6.1 逐批实测（2026-08-04）
> 状态：development only，非正式结果
> 数据基准：C3 注册 attempts（`s27_estg150_b0_enhanced_v10a_r1a_c3_hist56d_v1/b0_attempts.json`，tracked，SHA-256=c694f7cd…），与 56d2b03 历史 Layer E 构建的同一 canonical Gold（用户授权只读；不读当前 Layer E）
> 复现：`python -m scripts.analyze_b0_error_types`（`scripts/analyze_b0_error_types.py`）

## 1. 摘要

B0 在正确的 Sun literal-overlap v2 主口径下基线 **F1≈0.710**（P=0.684，R=0.738）；经 B0-R1 五批修复后当前 **F1≈0.712**（P=0.683，R=0.744）。对全部 1055 个 Gold span 与 1111 个预测 span 做逐 span 失败分类后，低分原因可归结为 **5 个量化成因 + 1 组结构性限制**：

| 编号 | 成因 | 量化证据 | 可修性 |
|---|---|---|---|
| C1 | **Action span 过度吞并**（动作 span 吞掉主语与句尾约束内容） | constraint 的 143 个 missed 中 108 个内容其实在别的字段里，其中 57 个被 action 覆盖；matched 的 212 个 action 中 **192 个为过长，中位超出 54 字符、最大 739** | **已修**（质量收益；主口径持平） |
| C2 | **constraint↔condition 双向字段混淆** | constraint 的 178 个 misclassified 中 152 个压到别的字段 Gold 上，其中 114 个压在 condition 上 | **实测候选被拒**（gold 语义差异+registry 重叠，记局限） |
| C7 | **Under-extension（span 过短）** | matched 的 779 个 Gold span 中 202 个被预测短于 Gold（中位短 14 字符）：modality evidence 80、constraint 51、condition 50、action 16 | 待修（边界/evidence 范围） |
| C3 | **模态四分类 label 混淆**（独立面板） | evidence 匹配上的 clause label 准确率 79.3%；definition↔obligation 混淆 16+7 | **已修**（伪 validated 消除；主口径不变；面板 −0.48pp） |
| C4 | **Actor 抽取不足** | 22 个 missed：8 个含词典词（依赖句法失败，可修）、14 个词典无覆盖（需决策） | **已修 8/8**（主口径 F1 +0.0018）；14 个待 LEXICON-DECISION |
| C5 | **Clause 规划失配** | 231 个 Gold clause 中 38 个（16%）无 pred clause 以 IoU≥0.5 配对 | 低优先级（v2 口径不依赖 clause 对齐） |
| C6 | **结构性限制**（缺 Sun 原资产、词典规模、Gold 语义差异、H1 回落 B0） | 见 §5.6 | 需资产/需用户决策/需正式 Gold |

**最重要结论：constraint 字段（F1=0.489）之所以是短板，不是因为"抽不到"，而是因为"抽错地方"——被 action 吞掉（C1）和被 condition 抢走（C2）合计解释了其绝大多数错误。**

### 1.1 修复结果总表（原因 → 修复 → 实测影响）

| 成因 | 根因（file:line 证据） | 修复方法 | 实测影响（主口径 v2，同 Gold） | 为什么是这个结果 |
|---|---|---|---|---|
| C1 action 吞并 | `actor_action.py` `_subtree_span` 把 nsubj/全部依赖纳入 action 子树 | 排除 nsubj/agent/clausal 依赖（12 类）；`safe_action_slice` 保持 | F1 持平（+0.00005）；主语开头 action 8→0；strict-exact 3.0× | any-overlap 口径对边界不敏感：被吞内容本就不计入 constraint recall，修复只改善边界质量（诊断面板可见） |
| C2 字段混淆 | scope/registry 双发：44 个同界双发（43 个双 tregex，`to<<an|the` vs `to<<extent|purpose` 重叠）；gold 对 "to the extent"/关系从句语义内部不一致（33 个 condition 匹配依赖 that/which/who 标记） | 候选：交叉字段同界去重（lexicon 优先） | **F1 −0.0005，拒绝回退** | 规则在真实管线只触发 1 次且移除的是已匹配唯一覆盖；任何偏向都对称损失匹配；不读 Gold 前提下规则层无法安全消歧 → 方法局限 |
| C3 伪 validated | `alignment.py` equal-count/split 路径"两侧任意锚即 validated"（de:/en: 命名空间永不交集） | `_cross_validates`：语言学 DE→EN 情态映射表 + 否定极性一致 + 数字锚；split 连接词优先切点+逐片验证 | validated 107→49（DoD"无伪 validated"达成）；主口径不变；label 面板 −0.48pp | 修复的是正确性缺陷（路由输入不再伪验证）；label 面板微降因 unsupported +8 落回 record 级路由（1-2 clause 噪声级），validated_split 42→0 为记录副作用 |
| C4 actor 漏抽 | ①actor 提取被 action-head 门控（5/8 的 nsubj 挂在无情态动词）；②只认 obl:agent/nmod:agent，而 CoreNLP 4.5.10 标 obl+case by/to（3/8）；③首个弧优先遮蔽 by-agent；④修饰词命中（"business year of a bookkeeping farmer"） | ①clause 内全 nsubj/nsubj:pass 弧候选；②obl/nmod+case by/to；③首个通过过滤器的候选胜出；④actor 中心词必须为词典 surface；排除自身 case 介词与尾部标点 | **F1 +0.0018（0.71024→0.71205，系列首个正向）**；actor F1 0.616→0.670；8/8 漏抽找回；FP 29→17 | 直接改变字段内"抽到与否"（主口径敏感项）：+7 matched_gt；中心词校验把修饰词 FP 砍半；v1 无校验 −0.0021 被拒（迭代验证） |
| C5 clause 失配 | `plan_clause_units_v4` 输出 249 vs Gold 231，38 个 Gold clause 无 IoU≥0.5 配对 | 未实施（低优先级） | — | v2 口径不依赖 clause 对齐；58 个真正漏抽中仅 4 个在未配对 clause |

修复批次产物：ACTION=`…r1b_actionfix_hist56d_v1/`、SCOPE-DISAMBIG（负面证据）=`…r1b_scope_disambig_hist56d_v1/`、ALIGN=`…r1b_align_hist56d_v1/`、ACTOR=`…r1b_actor_hist56d_v2/`；每批事件与 manifest 见 `EXPERIMENT_EVENTS.jsonl`。

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
| B0（C3 基线） | 0.681 | 0.741 | 0.710 | 56d2b03 历史快照；v10a 与 C3 几乎相同（ΔF1=+0.0003） |
| B0（ACTOR-v2 当前） | 0.683 | 0.744 | **0.712** | B0-R1 五批修复后；同 Gold 同口径 |
| D1（deepseek v4pro，直接 LLM） | 0.907 | 0.664 | 0.767 | P 高 R 低；constraint R=0.288 最低 |
| H1（B0+LLM 回退） | 0.681 | 0.741 | 0.710 | **与 B0 基线完全相同**：H1 的 LLM patch 全部被验证器/merge 拒绝，全部回落 B0（S2.8D 历史），不构成独立结果 |

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

### C1. Action span 过度吞并 —— 【已修，实测为质量收益（主口径持平）】

- 现象：action span 从主语开始、延伸到句尾，把 constraint/condition 内容一起吞掉。
- 证据（注册 C3 产物 + 本分析）：
  - `estg_000003`：Gold constraint `a shorter period`，预测 action 为整句 `It may cover a shorter period if …`（0-37）；
  - `estg_000021`：Gold constraint `in such a quantity that actually precludes a sale`，预测 action 为 `sold and are granted only in such a quantity that actually precludes a sale. 21.`；
  - 244 个 action 中 8 个以冠词开头（如 `The actuarial reserve shall be calculated in accordance with…`），即主语被包进 action；
  - 定量：constraint 的 143 个 missed 中 57 个只被 action 覆盖（另 16 个被 action+condition、10 个被 modality 等），合计绝大多数 missed 与 action 吞并有关；
  - 边界方向：matched 的 212 个 action Gold span 中 **192 个（91%）预测长于 Gold，中位超出 54 字符、均值 69、最大 739**——这是全系统最稳定、量级最大的单一缺陷，不只是"偶尔吞 constraint"。
- 代码位置：`b0_v10/actor_action.py:39-54`（`_subtree_span` 把 nsubj/obl 等**所有**依赖子树节点纳入 action 范围）、`actor_action.py:127-171`（head 子树 + `safe_action_slice` max_chars=80 向右取到最右安全边界）。
- **实测（2026-08-04，B0-R1-ACTION）**：修复 = `_subtree_span` 排除 nsubj/nsubj:pass/csubj/obl:agent/nmod:agent/advcl/ccomp/mark/discourse/parataxis/cc/conj。真实运行后主口径 F1 0.71019→0.71024（**+0.00005，持平**），delta 仅发生在 action 字段（+1 matched_p / −1 matched_gt），其余五字段全 0（隔离性验证）；**质量收益**：主语开头 action 8→0，strict-exact action F1 0.0122→0.0367（3.0×）。结论：**C1 是边界质量修复，不是 v2 any-overlap 主口径的指标驱动项**——主口径只对字段归属/抽到与否/invalid 敏感，对边界不敏感；修复产物 `outputs/development/s27_estg150_b0_enhanced_v10a_r1b_actionfix_hist56d_v1/`。
- 残余：`if 1.` 之类从句尾仍偶有进入 action（真实 parse 中编号/从句依赖关系不同），属小项。

### C7. Under-extension（span 过短）—— 【可修】

- 现象：与 C1 相反，**202 个已匹配的 Gold span 被预测得比 Gold 短**（中位短 14 字符、均值 36、最大 307），主要分布在 modality evidence（80 个）、constraint（51）、condition（50）。
- 代码位置：modality evidence 只取到情态词附近（`b0_v10/modality.py` evidence 范围、`definition_resolver.py` evidence 选择），condition/constraint 的 `safe_window_end`/scope 截断语义。
- 预期影响：改善已匹配 span 的边界质量（containment/partial 占比下降、exact 上升）；不影响 matched 计数，但提升语义覆盖与诊断面板。
- 风险：与 C1 相反方向，修改边界逻辑时需同时防止过修（C1）与不足（C7），用重评逐批验证。

### C2. constraint↔condition 双向字段混淆 —— 【实测：候选被拒，记为方法局限】

- 现象：同一段文本在 Gold 里是 condition、预测写成 constraint（114 个），或反之（31 个）。
- 代码位置：`b0_v10/scope.py:37-49`（`_SURFACE_SCOPE` 打字）、`resources/corenlp/sun_phrase_patterns_v3_enhanced.json:56-60,69-78`（condition 与 constraint 的 Tregex 模式大量共享 cue，如 `PP=constraint << to << an|the` 与 `PP=condition << to << extent|purpose|case` 同时捕获 "to the extent"）。
- **实测（2026-08-04，B0-R1-SCOPE-DISAMBIG）**：候选规则 = 交叉字段同界 span 去重（恰好一侧 lexicon 时 lexicon 字段胜出）。真实运行后 F1 0.71019→0.70964（**−0.0005，负**）：规则在真实管线只触发 1 次（44 个同界双发中 43 个为双 tregex，按设计跳过），且移除的是 1 个**已匹配**的 condition 唯一覆盖。按 §8.6 迭代规则（固定主口径判定）**拒绝**，scope.py 已回退，运行产物保留为负面证据（`outputs/development/s27_estg150_b0_enhanced_v10a_r1b_scope_disambig_hist56d_v1/`）。
- **拒绝的机制证据**：(1) 33 个已匹配 condition span 完全依赖 that/which/who 关系代词条件标记（删即失 R）；(2) gold 对 "to the extent"/关系从句语义内部不一致（同短语在不同样本分别标 condition/constraint，个别位置双标注）；(3) 双 tregex 同界对无论偏向哪边都对称损失匹配（估 −0.003 F1）。在不"看 Gold 反向调规则"的硬约束下，规则层无法安全消除。
- 残余方向：registry 模式层复核（去掉 constraint 对 "to the extent" 的捕获，收益约 4-6 FP）需用户决策；其余为方法-vs-Gold 语义分歧，按 Pipeline 披露为方法局限（论文可写，与 D1 constraint R=0.288 同性质）。

### C3. 模态四分类 label 混淆 —— 【已修（B0-R1-ALIGN），实测面板 −0.48pp，主口径不变】

- 现象：evidence 匹配的 208 个 clause 中，label 准确率 79.3%；混淆集中在 definition↔obligation（16+7）与 permission/prohibition（5+3）。
- 代码位置：`b0_v10/definition_resolver.py`（definition_structure 路由）、`b0_v10/alignment.py:92-114,162-209`（equal-count/monotone 路径的"伪 validated"：两侧各出现任意锚即标 validated，不校验 DE↔EN 语义对应 → 路由输入不可靠）。
- **实测（2026-08-04，B0-R1-ALIGN）**：修复 = `_cross_validates`（语言学 DE→EN 情态映射表 + 否定极性一致 + 共享数字锚；equal-count/monotone/split 三路径统一；split 改连接词优先切点并逐片验证）。真实运行：validated 107→49（validated_split 42→0）、unsupported 30→72、"无伪 validated" DoD 达成；**主口径 span 指标完全不变**（F1 0.7102368，evidence span 不受 label 路由影响）；label 面板 79.33%→78.85%（**−0.48pp，约 2 个 clause**），strict clause accuracy 0.6407→0.6364，independent82 macro F1 +0.0012。
- **判定**：保留（修复的是 B0-R1 明确列出的确定性缺陷"德英 cue 验证/无伪 validated"，属正确性 DoD 项；主口径不变；label 面板 −0.48pp 为记录的已知代价，1-2 个 clause 噪声级；validated_split=0 为记录的副作用，留待后续细化——split 路径逐片验证后无 cue 片段（如主语前缀）无法验证导致全部降级 unsupported）。
- 产物：`outputs/development/s27_estg150_b0_enhanced_v10a_r1b_align_hist56d_v1/`。

### C4. Actor 抽取不足 —— 【已修（B0-R1-ACTOR），实测主口径 F1 +0.0018】

- 现象：GT=48，missed=22（R=0.54）。22 个 missed 中 8 个含词典词（可修）、14 个不含（需决策）。
- 代码位置：`b0_v10/actor_action.py`（actor 提取被 action-head 门控；只认 nsubj*/obl:agent/nmod:agent）。
- **取证（2026-08-04，真实 CoreNLP 解析）**：8 个词典内漏抽的机制——(a) 5/8 的 nsubj 弧挂在无情态、非 ROOT 的动词上（分词/从句内普通动词/无情态被动谓词），被 action-head 门控挡住；(b) 3/8 是被动 by-agent/与格 to-recipient，CoreNLP 4.5.10 basicDependencies 标为 `obl`+case by/to，且"首个弧优先"让非词典主语遮蔽了 by-agent。
- **实测修复**：候选扩展为 clause 内全部 nsubj/nsubj:pass 弧（无 action head 时也发 actor，不发边）+ action head 的 obl/nmod with by/to case；首个通过过滤器的候选胜出；actor 子树排除自身 case 介词与尾部标点；**中心词（nsubj 依赖 token）必须为词典 surface**（拒绝"the business year of a bookkeeping farmer"这类修饰词命中）。
- **实测结果**：主口径 F1 0.71024→**0.71205（+0.0018，本系列首个正向主口径 delta）**，R +0.0066、P −0.0023；actor 字段 F1 0.616→0.670（R 0.542→0.688）；8 个漏抽全部找回；中心词校验把候选 FP 从 29 砍到 17。v1（无中心词校验）实测 −0.0021 被拒，v2 保留。
- 产物：`outputs/development/s27_estg150_b0_enhanced_v10a_r1b_actor_hist56d_v2/`。残余：14 个无词典覆盖的 actor（spouse/successor/bank 等）仍需 LEXICON-DECISION。

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
