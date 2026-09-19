# SEP-C3：R_C 字段边界与 recovery 口径复核

日期：2026-09-19。使用既有 A/B/C/D 600-call 预测，新增 API=0。
这是离线证据分析，不修改 Gold、评价器、已保存预测或活动 Prompt；所有解释为 AI 复核，不是人工裁决。
逐案坐标、来源哈希、计数与判定依据见同名 JSON。

## 1. 对 Prompt Design 的直接结论

已有数据支持一个更具体的局部设计目标：**避免把适用条件整体改标为 constraint，同时保留真正的嵌套 constraint。**
这个目标比“只保留 time”更符合已观察案例，但仍未证明某句新指令能够改善净效果，也不能解释全部 FP 或 actor 副作用。

本次新增的实质发现有两项：

1. 19 条 condition 覆盖丢失记录中，8 条、5 个独立样本出现明确的整段字段迁移：原 condition 原样进入 constraint，迁移片段不命中任何细粒度 Gold constraint。另有合法嵌套、混合范围和单纯漏抽，不能一律当作同一种错误。
2. 原 52 条 coarse recovery 中，37 条至少精确恢复一个细粒度 Gold constraint；另有 3 条完全只命中合并区间的空隙。因此，不能把“未恢复整个 coarse 区间”直接解释为“抽出的短语不完整”，也不能把所有 coarse recovery 当成真实约束恢复。

研究参照仍为 B = common + E + R_A；正式默认仍为 v6。本报告不启动、缩编或恢复任何新调用计划。

## 2. 口径：指标复现与语义解释分开

既有实验将同一样本、同一字段的 Gold spans 合并成一个 `[min(start), max(end))` 区间，再以同字段任意非空字符交集判断命中。合并区间包括原 spans 之间的空隙。

本次保持该口径，独立核对四臂 condition/constraint 的 48 个整数计数，0 mismatch；52 条 recovery 的样本、方向和新增命中片段与原报告一致。随后回到已发布的细粒度 Gold spans，检查命中位置及字段归属。这是语义来源核查，不发布新主指标、不替换旧分数。

计数单位为“比较方向 × sample_id”。两方向重复出现的样本不是独立证据。下文的精确命中指同一 `(start, end, text)`；它只证明恢复了一个标注短语，不代表该样本所有约束均正确。

## 3. condition 丢失：全量枚举与逐案解释

| 比较 | Gold condition 覆盖：前→后 | 丢失 | 恢复 | 净变化 |
|---|---:|---:|---:|---:|
| A→C | 99→91 | 9 | 1 | -8 |
| B→D | 97→88 | 10 | 1 | -9 |

合计 19 条丢失记录、13 个独立样本，6 个样本在两个方向重复。两方向恢复的均为 `estg_000134`。19 条丢失记录的 variant condition 均为空。

其中 15 条、9 个独立样本出现新增 constraint 与丢失的 condition 区域相交；15 条都能命中实际细粒度 condition，并非全部由 coarse 空隙造成。11 条至少有一个新增 constraint 与 baseline condition 完全相同。

逐案分类如下。表中样本省略共同前缀 `estg_`；分类描述观察到的字段及范围变化，不推断模型内部机制。

| 类型 | 比较记录 / 独立样本 | 完整样本清单及方向 | 设计含义 |
|---|---:|---|---|
| condition-only 整段迁移 | 8 / 5 | 000039、000052、000108：双方向；000161、000210：B→D | 存在明确的字段归属目标，但不代表这些样本的其他新增 constraint 都错误 |
| Gold 已有嵌套或双字段覆盖 | 3 / 2 | 000028：双方向；000037：B→D | condition 漏抽是真问题；新增 constraint 不能因此一律删除 |
| condition 与 constraint 范围合并 | 4 / 2 | 000060、000106：双方向 | 合法约束内容和过宽范围并存，需要区分完整命题与局部限制 |
| 丢失但没有新增重叠 constraint | 4 / 4 | 000121、000231、000509：A→C；000124：B→D | 无法用“condition 被搬到 constraint”解释，不归入同一修补目标 |

关键对照：

- **000052**：`insofar as ... do not exceed ... 10% ... preceding business year` `[38,198)` 原样从 condition 进入 constraint；该样本细粒度 Gold constraint 为空。数量、时间、法律引用词同时出现，仍不足以决定字段。已有两个 constraint FP 被替换成一个，FP 从 2 降到 1，但 condition 丢失，说明只看 FP 净值也会漏掉问题。
- **000104**：`up to 20% of the acquisition or production costs` `[118,166)` 本来就是 Gold constraint，两个方向均有 recovery。不能据 000052 的错误禁止数量限制。
- **000028**：新增 constraint `[26,100)` 精确对应 Gold constraint，内部还有 Gold condition `[55,100)`。目标应是保留两层结构，不能规定“同一段文字只能属于一个字段”。
- **000060**：新增 `[134,335)` 把原 condition `[134,250)` 与时间限制 `[251,335)` 合到一起。它包含正确约束内容，但失去了字段边界。
- **000106**：四年期限 `[122,141)` 和法律引用 `[227,274)` 本来就嵌套在 Gold conditions 内。禁止从 condition 中提取 constraint 会损失这些合法内容。
- **000210**：6 个新增 constraint 命中 coarse condition，其中只有 4 个命中真实细粒度 condition；另外 2 个落在 condition 合并空隙。整段迁移证据是原 condition `[7,75)` 被原样移入，不能将 6 个片段全部记作这种错误。

这里的 19 条“覆盖丢失”不等同于既有 18 条 condition “全对→非全对” regression：A→C 的 10 条 regression 中，000112 是新增 FP 而非 Gold 覆盖丢失；B→D 的 10 条覆盖丢失中，000037、000161 的 baseline 已含 FP，不属于全对。两种统计各自保持原定义。

## 4. 52 条 recovery：细粒度来源揭示的校正

| 对新增命中片段的检查 | 比较记录数 |
|---|---:|
| 既有 coarse recovery 总数 | 52 |
| 至少与一个实际细粒度 Gold constraint 相交 | 49 |
| 其中至少精确恢复一个细粒度 Gold constraint | 37 |
| 完全只命中 coarse 合并空隙 | 3 |

3 条空隙命中为 `000247` 的 A→C、B→D，以及 `000293` 的 A→C：

- **000247**：新增 `[32,96)`，但真实 Gold constraints 为 `[0,9)` 与 `[153,197)`，没有交集。
- **000293**：新增 `excluding those under Section 13 ...` `[392,461)`，精确对应 Gold exception，位于三个 Gold constraints 的合并空隙中。它仍按冻结评价器记为 recovery；不能据此声称恢复了一个 legal-reference constraint。

这不撤销所有 legal-reference 收益。例如 **000222** 新增 `(Section 1, no. 3, lit. d)` `[126,152)`，确实覆盖细粒度 Gold constraint `[127,151)`。类型计数需要保留这种逐案区别，不能由一条反例反向推出某类全部无效。

原语义复核中的 `21 complete / 29 partial / 2 overlap-only` **不应再直接充当单个短语质量或 Prompt 边界设计的依据**：

- 原 partial/overlap-only 中有 **21 条**至少精确恢复一个细粒度 Gold constraint。未恢复全部约束与单个短语不完整是两个问题。
- B→D **000664** 原标 overlap-only，但 `wholly or partially` `[101,120)` 就是完整的细粒度 Gold constraint；同时 `solely` 与 `also` 仍需分别分析，不能由一个正确片段推成整条正确。
- B→D **000776** 原标 overlap-only，但 `in particular` `[49,62)` 精确对应已冻结 Gold constraint。认为它语义过弱属于需说明的标注解释争议，不能写成“没有恢复任何 Gold constraint”。

原报告及标签作为历史记录保留；本报告给出附加解释和明确限制，不修改人工标注。既有 time/legal/purpose 等多标签数量仍不等于各条 wording 的因果贡献，也不作为重新筛选类型的依据。

## 5. 哪些指导应保留，哪些设计应排除

| 指导或拟议改动 | 当前判断 | 依据与限制 |
|---|---|---|
| common + E + R_A | 继续作为 B 研究参照 | 本次没有新运行，不能升级为稳定最优或正式替换 |
| 区分适用条件与动作限制 | 值得作为局部设计目标 | 8 条 condition-only 迁移提供可定位目标；不保证一句新指令即可解决 |
| condition 内允许嵌套 constraint，并保留 condition | 必须在候选审查中保留 | Gold 000028/000106 支持；E5 已有示例，不应声称这是尚未教过的新规则 |
| temporal-only | 仍无依据 | 非时间真实 recovery 存在；时间与数量词也会出现在 condition 中 |
| 字段互斥、所有重叠都禁止 | 排除 | 与嵌套 Gold 和 E5 冲突 |
| 一律扩展到整个 coarse Gold 区间 | 排除 | coarse 合并范围包含间隙和其他字段，不是目标短语边界 |
| 一律删除短词或 discourse cue | 排除这种笼统规则 | isolated only 的 FP 仍存在，但 000776 的 in particular 已被 Gold 标为 constraint |
| 再重复“完整短语，不要 only” | 尚不是有新增信息的干预 | 旧 R_C 第二句已明确要求，实际仍出现此类错误 |
| 整体恢复 S | 无新增支持 | 可参考 S5/S6 的语义区别，但不能把本次观察当成恢复整个 S 的证据 |

旧 R_C 第一条同时使用“when … the regulated action applies”和多种类型提示；S5 的 condition 定义也涉及“whether/when the norm applies”，而 S6 强调“already applicable action”。这提供了一个**措辞边界可能模糊**的假设。现有实验比较的是整个 R_C block，没有逐句消融，不能认定这几个词造成了迁移。

**下一步限定为一个离线候选审查任务**：围绕“适用命题保持为 condition；只把其中有独立限制作用的短语提为 constraint”形成一份最小改动草案，并逐条解释上述失败例和正例。不得把 E5 已有内容简单重复后称为新机制；不得加入针对 sample_id 的特判。

在给出可冻结 wording 前，优先澄清 000052/000104 的数量边界对照、000106 的嵌套边界、000776 的短语标签政策。这 4 个样本组成新审查队列，问题与完整原文在 JSON 中；它不覆盖或改写旧 7 条 manual-review 标记，不代表人工已完成裁决。如果无法提出兼容这些正反例的通用解释，就保留 B 收口，不创建新模块。

本次未证明新候选能改善分数；没有冻结新 wording、没有确定新 arms 或调用预算。actor 六例副作用仍未解释，未来若提出实验，其保留/删除标准须同时覆盖 constraint 收益、FP、condition 与 actor 的变化，且在调用前明确。本报告不授权 API。

## 6. 附带发现：source_text 复制异常

600 条 canonical records 中，4 条的 `source_text` 在目标正文后追加了 E 示例：A/000044、A/000720、C/000035、C/000044；涉及 3 个独立样本。保存的 validation 仍为 true。因此，既有“调用成功、计数一致”不能被扩写成“所有接口语义都完全正确”。

本次逐条核对全部 600 条记录五字段 spans：均在原始目标正文以内，且与原始正文对应切片一致；这 4 条的原文前缀也未改变。condition/constraint 48 项计数完全复现。本发现不改变本报告的坐标分析，未修写预测或重评旧结果；复制异常的生成环节仍未定位。

## 7. 可追溯性与完成范围

- 核心来源：已发布 `data/gold/stage2/estg150_formal_gold_v1.json`、四臂 `canonical_predictions.jsonl`、既有 phase2 summary、52-case semantic review、coarse transform 与 literal-overlap evaluator；同名 JSON 逐一保存 SHA-256。
- 产物：本 Markdown 与同名 JSON；包含 19 条 condition 丢失案例、52 条 recovery 细粒度来源检查、原文与细粒度 Gold 快照、4 条 source-copy 异常及计数核对。
- 验证：来源哈希、坐标/切片、计数、枚举集合和报告内容检查；纯分析产物，不运行项目审计、代码测试或新实验。
- 完成的是这一批离线边界归因；没有声称全部语义争议、actor spillover、跨运行方差或整个 SEP-C3 已完成。
- 原始 raw/prediction 目录仍受既有 Git ignore 约束。本报告的提交不等于全部历史原始响应都已远端备份。
