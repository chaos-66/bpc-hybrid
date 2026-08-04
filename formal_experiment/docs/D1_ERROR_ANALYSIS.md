# D1 错误分析报告（为什么 D1 的召回率低）

> 任务：D1-R0/R1-ERR（错误分析与成因文档；不实施 prompt 修改）
> 状态：development only，非正式结果
> 数据基准：`outputs/development/s28_s29_deepseek_v4pro_sun_literal_v1/d1_attempts.json`（tracked，deepseek-v4pro，150 samples ×1 repeat）与 56d2b03 历史 canonical Gold（同一对象，同 B0）
> 口径：`sun_literal_overlap_evaluation@2.0.0`（与 B0 完全一致）

## 1. 摘要

D1 整体 **P=0.907 / R=0.665 / F1=0.767**。低召回的结构性原因：**系统性地欠抽 + constraint 字段错标**。354 个漏抽 Gold span 中 **constraint 占 215 个（61%）**，其中 99 个内容其实被抽到了（落在 action span 里）、91 个完全没抽、16 个进了 condition。

**关键分解**：若只把 124 个"已抽到但落错字段"的内容归位到 constraint，constraint R 从 0.288 → **0.699**；若再补 91 个漏抽 → 接近 1.0。即 D1 的 constraint 召回问题 ≈ 2/3 是"字段放错"、1/3 是"真没抽"。

## 2. 数据与方法

- 与 B0 同一 canonical Gold（56d2b03 历史 Layer E，150 条、1055 个 Gold span、231 clause）；D1 attempts 150 条 request_status 全 ok，sample_ids 与 Gold 完全一致。
- 失败分类与 B0 相同（missed/misclassified + 子类；matched 质量另计）。

## 3. 逐字段失败分布（D1，v2 口径）

| 字段 | gold | pred | matched_gt | P | R | missed: 别字段 | missed: 全无 | misclassified: 压别字段 | misclassified: 无Gold |
|---|---|---|---|---|---|---|---|---|---|
| modality | 231 | 256 | 209 | 0.973 | 0.905 | 11 | 11 | 1 | 6 |
| actor | 48 | 69 | 42 | 0.594 | 0.875 | 4 | 2 | 5 | 23 |
| action | 247 | 221 | 210 | 0.950 | 0.850 | 22 | 15 | 9 | 2 |
| condition | 214 | 135 | 148 | 0.911 | 0.692 | 23 | 43 | 7 | 5 |
| constraint | 302 | 97 | 87 | 0.845 | 0.288 | 124 | 91 | 13 | 2 |
| exception | 13 | 5 | 5 | 1.000 | 0.385 | 3 | 5 | 0 | 0 |

## 4. 根因

### D1-C1. constraint 字段错标（124 个，最大单一原因）——【可修：prompt 合同层】

- 99 个 constraint 内容被并入 **action span**（如 estg_000003 "a shorter period"、estg_000027 "to an annual amount" 落在 action 里）、16 个进 condition、其余零星。
- 机制：与 B0 的 C1 同类——action span 过度扩展把约束内容吞掉；LLM 侧没有"法律引用/时间/数量限制属于 constraint 不属于 action"的引导。
- prompt 证据：`prompts/sun_compat/direct_llm_sun_record_prompt.md` 的 few-shot 中 constraint 仅出现 1 次且为简单时间约束（"within 72 hours"）；condition 出现 **0 次**；exception 1 次。
- 预期：字段归位对 constraint R 是 **+124 的纯增益**，同时 action 的 FP 减少（P 升）——双向收益。

### D1-C2. 系统性欠抽（91 constraint + 43 condition 完全未抽）——【可修：prompt 合同层】

- prompt 规则 14："Do NOT invent content. If a field cannot be determined, omit it"——面向精确的保守指令，模型倾向少报。
- 修改方向：改为"列出所有候选；不确定的写入 `unsupported_or_ambiguous` 并给原因"；补 constraint/condition/exception 的 few-shot（法律引用类 "pursuant to Section 5"、"within the meaning of Section 11(1)"、数量类 "in such a quantity that…"、条件类 "if/when/unless"）。
- 风险：候选变多可能引入 FP，P 需实测（与 B0 迭代规则一致，不允许 Gold 反向调 prompt）。

### D1-C3. 运行事故（次要，已记录）——【可修：干净重跑】

- s28_s29 manifest `d1_runtime_incident`：本地 validator KeyError 导致 lost_result_count=104、恢复调用 26、max_retries=0；部分样本由恢复调用产生，质量可能受影响。
- 处理：transport 加固后用当前 runner 干净重跑基线（属 D1-R1-CLEAN-RERUN）。

### D1-C4. actor 字段 P 低（0.594）——【已披露，非本批目标】

- 69 pred vs 48 gold：23 个无 Gold 交叠的 actor 被多抽（LLM 把非 actor 主语也列为 actor）。这是 D1 的 P 侧问题，不在"提 R 不降 P"目标内；记录待后续。

## 5. 修复路线（§8.7.1 子批次，按收益排序）

| 顺序 | 子批次 | 内容 | 预期 |
|---|---|---|---|
| 1 | D1-R1-FIELD-TYPING | constraint 类别显式定义 + 禁止并入 action/condition + 补 few-shot | constraint R 0.288→0.699 上限，action P 升（双向） |
| 2 | D1-R1-PROMPT-CONTRACT | 规则 14 改写（省略→列举+标记）+ constraint/condition/exception few-shot | 补 91+43 漏抽；P 需实测 |
| 3 | D1-R1-VERIFY-PASS | 两遍法自检（可选，预算翻倍） | 进一步 R |
| 4 | D1-R1-CLEAN-RERUN | 干净 transport 重跑基线 | 排除事故影响 |

每批必须：prompt 变更 + focused tests → **预算内真实 LLM pilot（逐批用户授权）** →
同口径重评 → delta 与原因 → keep/reject → 事件 → commit → push。禁止读 Gold 调 prompt。

## 6. 与 B0 的对比（论文可写）

- B0：P 低 R 高（0.683/0.744，constraint P=0.461 R=0.527）——过度抽取 + 字段错标；
- D1：P 高 R 低（0.907/0.665，constraint P=0.845 R=0.288）——欠抽 + 字段错标；
- 两者在 constraint 上失败模式互补，且都有"字段错标"成分（B0 的 C2 / D1 的 C1），同源提示：字段语义（尤其 constraint）是 EStG 六要素抽取的公共难点。

## 7. 附录：数据出处

- D1 attempts：`outputs/development/s28_s29_deepseek_v4pro_sun_literal_v1/d1_attempts.json`（tracked）
- 指标：同目录 `metrics.json`（schema `sun_table8_literal_overlap_evaluation@2.0.0`，历史注册）；本文数字为本轮用 56d2b03 canonical Gold 重算（与注册值一致：overall P 0.9068/R 0.6645/F1 0.7669）
- 全部数字为 development only；任何 prompt 修改需授权 pilot 验证后才可进入正式口径。
