# SEP-C3 Constraint Refinement v2：调用价值审查

审查日期：2026-09-19。结论：**当前 5 arms × 150 = 750 calls 方案不通过，不启动真实调用。**

用户要求“不可随意跑数据，确保该数据是有用的才跑”。本次审查发现，支撑 temporal-only
设计的核心 taxonomy 存在确定的分类错误和覆盖偏差。先纠正解释比增加调用更有价值。
本报告是已有证据的离线审查，不是新实验、冻结协议或新的活动状态页；实时状态见
`docs/PROJECT_AUDIT.md`。新增 API=0，未修改 Gold、prompt、预测、评价器或原 taxonomy。

## 1. 证据来源与核验范围

- 历史证据提交：`fb96071`（父提交 `009ca09`），本地分支
  `codex/sep-c3-evidence-consolidation` 指向该提交；其 worktree 当前为 detached HEAD。
  本轮审查时该分支没有配置 upstream，不能声称该证据已远端备份。
- 读取位置：仓库根目录下 `.tmp/sep_c3_evidence_consolidation/formal_experiment/`。
  下列 `outputs/reports/sep_c3_targeted_refinement_v1_*` 文件均从该证据树读取：
  `case_analysis.jsonl`、`actor_taxonomy.json`、`constraint_taxonomy.json`、
  `constraint_recovery_fp_groups.json`、`metric_reconciliation.json`、
  `consistency_audit.json`、`phase2_summary.json`。
- 分类实现：该提交的 `scripts/consolidate_sep_c3_targeted_refinement_v1.py`，
  重点检查 `LEXICAL_PATTERNS`、`_recovery_category`、`classify_constraint_case`、
  `build_constraint_taxonomy` 与 `build_recovery_fp_groups`。
- 独立只读计算：读取当前仓库 `outputs/development/sep_c3_targeted_refinement_v1/`
  下 A/B/C/D 的 600 条 canonical 预测，以同字段字符区间非空交集重算
  3,000 个样本×arm×字段的 Gold 数、预测数、匹配预测数及匹配 Gold 数；
  与 case table 全部一致。各 arm 均有 150 条 canonical、150 条 raw，
  canonical 样本集合与 case table 相同；五字段 canonical span 与 case table 相同。
- 独立重算 mean F1：A=0.7245765762、B=0.7806397668、C=0.7558491301、
  D=0.7858022396。没有重新发送请求，也没有运行项目审计或代码测试套件。
- 历史 `metric_reconciliation.json` 有 127 项、0 mismatch；历史 consistency
  报告有 66 个通过的 check。此次复用历史完整性结论，并完成上述独立计数核对；
  不把本次计数核对冒充全部历史检查的重跑。
- case table、两份 taxonomy、reconciliation、consistency 五个读取文件经 LF
  归一化后均与 `git show fb96071:<path>` 字节相同。关键 SHA-256（LF）如下：

| 文件后缀 | SHA-256 |
|---|---|
| `case_analysis.jsonl` | `5b47cd74096f4f62cd9fb5335ec547c43dd4c972cdc3e3f5c48e6dcff2bb7f14` |
| `constraint_taxonomy.json` | `24c45364570a6e44abfd5b6b1e125efa1672556bea8c88c162c2895924b4a6d1` |
| `actor_taxonomy.json` | `ea3f5ab67ac30f5866be6ac9a0ab07da8289f3a8c3ed27f33d95492b468597f0` |

本次逐案阅读包括全部 40 条 taxonomy recovery、未收录的 12 条 recovery、全部
7 条 `manual_review_required=true` 记录，以及 B→D 的全部 6 条 actor regression。
下述语义判断是 **AI 离线复核意见，不是人工 adjudication**；原人工复核标记保持原样。

## 2. 可以保留的结果

| 比较 | 已核对的事实 | 解释边界 |
|---|---|---|
| A→B | actor F1 0.6314→0.7672；22 个完全纠正、3 个 regression；22 中 19 个 Gold 空时清空预测、3 个移除 object/resource | 支持保留 R_A 的方向；一次运行不等于跨运行已证明稳定 |
| A→C | constraint missed Gold 60→38；未匹配预测 27→50 | recall 增益与 FP 增加均真实存在 |
| B→D | constraint missed Gold 53→30；未匹配预测 26→58 | R_A 背景下仍有相同权衡 |
| B→D | actor F1 0.7672→0.7284；6 个 regression 均为 Gold 空、B 空、D 新增 actor | 这是可观察表型，不能据此判定模型内部原因 |
| recovery/FP 分组 | A→C：22 个 recovery 且 FP 数不增加、5 个 recovery 且 FP 数增加、14 个 FP 数增加且无 recovery；B→D：18、7、18 | 分组按样本内数量差定义，不表示语义已人工确认或所有 span 均干净 |

B→D 的 6 个 actor regression：`estg_000004`、`000021`、`000105`、`000209`、
`000302`、`000505`。其中 `000209` 新增 2 个 actor，其余各 1 个。

旧 100 与新 A 的漂移报告仍支持：150/150 request body hash 相同，137/150 raw
内容不同、58/150 canonical semantics 不同。应保留同批交错成对比较；这些材料
不能识别服务端修订、路由或随机性的具体原因。

**600 calls 可以保留为可追溯的研究记录；taxonomy 的语义结论不能随完整性 PASS
一起被认定为正确。** 该面板已用于错误分析与 prompt 选择，应如实称为开发/探索证据，
不能把仓库内部 formal Gold 命名当作新方案的独立盲测资格。

## 3. “time 占 33、legal reference 为 0”不能用作设计前提

### 3.1 分类规则存在系统性歧义

`time` 正则包含 `to`、`within`、`by`、`from`、`may`、`19xx/20xx`。
`_recovery_category` 对**被覆盖的整个 coarse Gold span**进行词匹配，并按
time → quantity → purpose → legal reference → exclusivity 优先返回一个标签。

因此它会把数量上限中的 `to`、法律引用中的 `within`、情态动词 `may`、法律名称
中的年份当作时间；quantity 的任意数字又会抢占 legal reference；purpose 的
`for/to` 也不等于目的语义。分类不直接判断新增预测实际恢复了什么语义。

| 样本 / 比较 | 原标签 | 可核对的预测片段或事实 | 审查意见 |
|---|---|---|---|
| `000104` A→C、B→D | time | `up to 20%` | 数量上限，`to` 误触发时间 |
| `000046` B→D | time | `up to 12%` / `up to 18%` | 数量上限，非时间 |
| `000030` B→D | time | `within the meaning of paragraph 1` | 法律引用限定，`within` 非时间 |
| `000222` A→C | quantity | `Section 1, no. 3, lit. d` | 法律引用，数字优先规则误分 |
| `000206` B→D | time | `within the meaning of paragraph 1` | 实际恢复的是法律引用片段 |
| `000800` B→D | time | `Section 4(4)` / `Income Tax Act 1988` | 实际新增预测是法律引用；长 Gold 内另有时间语义不能归因给它 |
| `000031` A→C | time | `by double-entry bookkeeping` | 方法/方式；该 arm 并未恢复 Gold 中的财年比较片段 |
| `000247` A→C、B→D | time | 新预测为不可扣除类别限定；Gold 内有 `may` | 不能解释成时间恢复 |
| `000433` A→C | purpose | `simultaneously with the issuance` | 明确时间关系反而被漏分到 purpose |
| `000776` B→D | time | `in particular` | coarse overlap 命中，不是完整时间约束恢复 |

这些不是边缘歧义，已足以反驳“legal reference 未观察到 recovery”，也使
“33 个 time recovery”失去语义可靠性。不要用另一套未校准关键词重算一个看似
精确的新 time 百分比。

### 3.2 计数单位与覆盖范围

- 原 recovery 标签合计是 **40** 条比较记录：time 33、quantity 2、purpose 3、
  other 2；不是 39 条独立案例。40 条去重为 **28 个 sample_id**。
- time 33 = A→C 17 + B→D 16；跨比较去重为 **23 个 sample_id**，有 10 个样本
  同时出现在两组。不能把两组看成 33 个独立支持证据。
- `build_constraint_taxonomy` 只保留 whole-field correctness 从错到对或从对到错
  的记录；有 recovery 但仍然存在 FP 的 `unchanged_wrong` 被排除。
- 从全部 150 条 case table 独立按 Gold span 覆盖变化枚举得到 **52 条 recovery
  比较记录、37 个独立样本**，与分组中的 A→C 27、B→D 25 一致。
  原 taxonomy 因上述选择条件缺失 **12 条 / 9 个样本**。
- 缺失记录：`000037` A→C/B→D；`000055` B→D；`000112` B→D；`000164` A→C；
  `000210` B→D；`000546` A→C/B→D；`000569` A→C/B→D；`000716` A→C；
  `000773` B→D。`000546` 的 `pursuant to subsection 2 or 3` 是漏掉的法律引用恢复。

### 3.3 overlap 得分不等于语义恢复

冻结评价器按同字段任意非空字符交集独立计算预测匹配与 Gold 覆盖，不要求一对一，
也不要求完整语义。coarse Gold 可跨多个短语/子句，因此多个短预测可能命中同一
长 Gold。`000776` 的 `in particular` 可被记为 recovery；`000786` 的孤立 `only`
处于 Gold 区间内，可计为匹配预测。这些事实不能支持“完整约束已恢复”或“边界正确”。

保留冻结主指标和全部既有结果；新设计所需的语义/完整短语诊断应与主指标分列，
不回改 Gold、匹配规则或历史分数。

## 4. 全部 manual-review 标记案例的复核意见

共 **7 条比较记录 / 6 个独立样本**：actor 1 条，constraint 6 条。

| 样本 / 字段 / 比较 | 离线复核结果 |
|---|---|
| `000037` actor C→D | 同时删除两处 `the fund`、新增 `business expenses`；属于有效 actor 丢失与非 actor 新增的混合错误，原 `uncertain` 不应硬压成单一类别 |
| `000027` constraint A→C、B→D | 新增 `only for part of the calendar year` 确为 temporal 片段，但在冻结 Gold constraint 外，FP 结论成立；源句是截断上下文，不能仅据 Gold 未覆盖就断言语义“无关”，需人工判断作用范围 |
| `000080` constraint B→D | 删去两个括注、新增 `at the time of receipt`；FN 保持 0、FP 1→0。收益是删除未匹配括注，不是 recall recovery；`span_boundary_changed` 没完整解释该变化 |
| `000509` constraint B→D | 删除一个 Gold 外限定与时间片段，改为税率依据；FN 0→0、FP 1→0。是 FP 清理伴随内容替换，不能表述为同一短语边界微调 |
| `000786` constraint B→D | 新增两条 Gold 外片段；其中“与银行目的无关”因 `to` 被错标 temporal。应保留“FP 增加”的计数事实，语义更接近用途/资格描述；孤立 `only` 命中长 Gold，另列边界问题 |
| `000854` constraint A→C | 仅删除 `in exceptional cases`，没有新增 span；FP 1→0、FN 0→0。属于移除不当约束片段，原 `span_boundary_changed` 标签不准确 |

必须扩大后续语义复核范围：**`manual_review_required=false` 不代表分类可靠**。
上述 recovery 明显误分项多数为 false；只复核原 true 队列不能保护下一轮设计。

## 5. 750 次方案的信息价值判定

五臂结构本身能表达一个 2×2 T/G 因子比较加旧 R_C 参照，但尚未证明它值得执行：

| arm | 可以回答的问题 | 当前价值判断 |
|---|---|---|
| BASE | 同批基线表现及新修补的净收益 | 进入新比较时应保留；不能直接复用上批 B 当作同批对照 |
| RC1 | 候选是否比旧 R_C 更好 | 只有确实要作此主张时需要同批重跑；不能因为历史 D 已有就直接横比 |
| T | temporal-only 本身是否有用 | 原主要依据已被错分削弱，暂不满足启动条件 |
| G | guard 单独的主效应以及 T×G 交互 | 仅在“解释独立主效应/交互”是必要研究问题时保留；只做最终候选选择时非必需 |
| TG | 组合是否达到预设净收益与副作用要求 | 尚无冻结措辞、独立可判定的成功标准，暂不满足启动条件 |

若未来目标只是比较一个经过离线筛选的候选，BASE + 候选是 300 次；若必须同时证明
比 RC1 更干净，三臂是 450 次。这只是按完整 150 面板计算的选择成本，**不是现在
建议或授权运行 300/450 次**。若目标是严格估计 T、G 与交互，删 G 又会损失可识别性；
不能一边节省该 arm，一边保留完整机制主张。

750 次也只有每臂一次/每样本一次，不能自动解决跨运行不确定性。交错成对比较减少
批次混杂，但不能证明唯一内部机制或跨模型稳定性。已有漂移也不能机械充当新实验的
方差估计。当前没有预先声明的最小有用增益、允许退步幅度或可据以确定样本量的分析。

## 6. 重新判定是否值得调用的条件

1. 对现有 **52 条 recovery 比较记录**逐条绑定实际新增且命中 Gold 的预测片段，
   区分时间、数量、法律引用、用途、方式、混合与仅 overlap 命中；允许多标签和
   不确定，不用单标签关键词优先级代替语义。人类争议项保持未裁决。
2. 对 FP 及 actor spillover 保留明确反例；候选不得只照顾成功案例。时间规则也会
   误抽 action/condition 中的时间片段，不能把 temporal-only 当作天然 precision guard。
3. 先确定实际决策：只选一个更好的 prompt，还是确实需要独立 T/G 主效应与交互。
   每个新增 arm 必须对应改变保留/拒绝决定的问题；不默认恢复五臂全量。
4. 冻结候选措辞、共同 R_A、输入/Gold/模型/解析器/评价器绑定与同批成对执行方式；
   明确主比较、完整 150 分母、失败处理、费用/调用硬上限和停止条件。
   旧 v1 的 `call_cap=750` 只属于旧 suite，不能挪给新五臂。
5. 在调用前确定成功与退步界限：constraint 的增益与 FP，actor/其他字段退步，
   孤立 cue 与完整短语质量，以及无效输出。成对不确定性按 sample_id 作为单位，
   保留同一样本所有 arms 的关联；一次选优仍按探索性结果报告。

不要求新实验保证“正提升”；有价值意味着无论结果好坏，都能改变一个预先明确的
研究/保留决定。目前纠正 taxonomy 就已改变了 T 方案的证据基础，因此本轮停在
**NO-GO：解释依据不可靠、实验问题与验收标准未冻结**，新增调用为零。
