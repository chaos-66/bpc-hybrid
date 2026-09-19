# SEP-C3 Constraint Refinement v2 语义复核报告

审查日期：2026-09-19。状态：**AI 离线语义复核，不是 human-approved，也不是人工 adjudication**。

本轮新增 API=0；未修改 Gold、prompt、评价器、历史预测和原 taxonomy。目标是校正 recovery 语义归因并判断 Constraint Repair 是否值得继续设计。

## 1. 结论摘要

- A→C recovery **27** 条比较记录；B→D **25** 条；合计 **52** 条比较记录、**37** 个独立 sample_id、**52** 个恢复 Gold span。两个方向有 **15** 个样本重合，不能把跨方向重复样本当作独立证据。
- 原 taxonomy 只收录 **40** 条 recovery / **28** 个样本，漏掉 **12** 条 / **9** 个样本；原 time 桶为 **33** 条 / **23** 个样本，但旧规则把 to、within、may、法律年份、数字等误归 time。
- 校正后按实际新增命中片段做多标签语义复核：time **14**、legal_reference **12**、purpose **10**、quantity **8**、manner **8**、other **25**、exclusivity **2**、undetermined **1**（多标签，合计大于 52）。R_C 收益分散在多个语义类型，legal reference recovery 明确存在。
- 恢复完整度：完整可解释 **21** 条，部分内容 **29** 条，仅 overlap 命中 **2** 条。大量 recovery 来自长 Gold 的局部 overlap，而非完整约束恢复。
- FP 侧：A→C 未匹配预测 27→50，新出现未匹配 span 36 个、删除 13 个，净 +23；B→D 26→58，新出现 43 个、删除 11 个，净 +32。既有 span 替换，也有真实净增加。
- **校正后不支持 temporal-only 设计前提**；证据也不足以提出一个有明确目标的单一最小改动。建议采用 **B：以 B 为本轮研究参照收口，保留旧 R_C 的混合结果，不强行创造新模块**。

## 2. 证据版本与核验范围

- 原整理证据提交：`fb96071`；本地证据树：`.tmp/sep_c3_evidence_consolidation/formal_experiment`。当前持久化预测：`formal_experiment/outputs/development/sep_c3_targeted_refinement_v1`。
- 本轮逐项重算当前 A/B/C/D canonical predictions 与 coarse Gold 的 150×4×5 字段计数，共 18,000 个计数检查，0 mismatch；recovery 与 FP 枚举逐案一致。
- 证据文件 hash 如下（LF 归一化；原始 hash 见 JSON）。

| 文件 | SHA-256 (LF normalized) |
|---|---|
| `.tmp/sep_c3_evidence_consolidation/formal_experiment/outputs/reports/sep_c3_targeted_refinement_v1_case_analysis.jsonl` | `5b47cd74096f4f62cd9fb5335ec547c43dd4c972cdc3e3f5c48e6dcff2bb7f14` |
| `.tmp/sep_c3_evidence_consolidation/formal_experiment/outputs/reports/sep_c3_targeted_refinement_v1_constraint_taxonomy.json` | `24c45364570a6e44abfd5b6b1e125efa1672556bea8c88c162c2895924b4a6d1` |
| `.tmp/sep_c3_evidence_consolidation/formal_experiment/outputs/reports/sep_c3_targeted_refinement_v1_actor_taxonomy.json` | `ea3f5ab67ac30f5866be6ac9a0ab07da8289f3a8c3ed27f33d95492b468597f0` |
| `.tmp/sep_c3_evidence_consolidation/formal_experiment/outputs/reports/sep_c3_targeted_refinement_v1_constraint_recovery_fp_groups.json` | `8d7820a05d2ca34cdcab85cac332f0822852a6d12a256a02c17329bea50a8ec9` |
| `formal_experiment/data/gold/stage2/estg150_formal_gold_v1.json` | `c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100` |

当前 A/B/C/D canonical 文件原始 SHA-256：

| arm | canonical_predictions.jsonl SHA-256 |
|---|---|
| A | `79a5ee8fcbf1e2a0b9e5ed4494cd68caa8fc886903cf5c67286cb1746b5e2072` |
| B | `b8e17d1df134d290954f435e3af470223fc073d73f700c4bfab4470e78ef594a` |
| C | `ecf81425de36a0c58cb74faa38a7bff69d5be85d73f56c733a77cb329e3e4a20` |
| D | `380a15968d141ae5dbef6fe789c231c729c1f46e047f403e9c6a3fa66bab4ac0` |

- 计数单位说明：recovery 比较记录 = 样本×方向；独立样本 = sample_id 去重；恢复 Gold span = 该方向下由 missed 变为 matched 的 Gold constraint span 数。
- 评价器仍使用冻结的任意非空字符交集；语义复核不改变冻结分数，也不把 overlap 得分自动升格为完整语义恢复。

## 3. Recovery 全量枚举与旧 taxonomy 校正

| 方向 | 比较记录 | 独立 sample_id | 恢复 Gold span |
|---|---:|---:|---:|
| A→C | 27 | 27 | 27 |
| B→D | 25 | 25 | 25 |
| **合计** | **52** | **37** | **52** |

两方向交集样本数为 15；跨方向重复样本只在独立样本数中计一次。

- 旧 taxonomy：40 条 recovery / 28 个独立样本；pair 分布 A→C 22、B→D 18。
- 旧标签计数：`{"recall_recovery_time": 33, "recall_recovery_other": 2, "recall_recovery_purpose": 3, "recall_recovery_quantity": 2}`。旧 time 共 33 条 / 23 个独立样本。
- 校正后实际 recovery：52 条 / 37 个独立样本；漏收记录：`estg_000037|A_to_C, estg_000037|B_to_D, estg_000055|B_to_D, estg_000112|B_to_D, estg_000164|A_to_C, estg_000210|B_to_D, estg_000546|A_to_C, estg_000546|B_to_D, estg_000569|A_to_C, estg_000569|B_to_D, estg_000716|A_to_C, estg_000773|B_to_D`。

### 3.1 校正后多标签语义分布

| 语义标签 | 任意出现次数 | A→C | B→D |
|---|---:|---:|---:|
| time | 14 | 9 | 5 |
| legal_reference | 12 | 5 | 7 |
| quantity | 8 | 5 | 3 |
| purpose | 10 | 5 | 5 |
| manner | 8 | 4 | 4 |
| exclusivity | 2 | 1 | 1 |
| other | 25 | 13 | 12 |
| undetermined | 1 | 0 | 1 |

恢复完整度：

| 方向 | complete_interpretable | partial_content | overlap_only |
|---|---:|---:|---:|
| A_to_C | 12 | 15 | 0 |
| B_to_D | 9 | 14 | 2 |

旧 time 桶按同一套实际片段复核后，多标签分布为：`{"other": 14, "legal_reference": 7, "manner": 7, "quantity": 7, "time": 12, "purpose": 6, "exclusivity": 2, "undetermined": 1}`；可见 time 只是其中一个类别，且旧 time 桶并不可靠。

## 4. 逐条 recovery 语义复核

下表每行对应一条比较记录；完整 source_text、baseline/variant 完整预测、new hit span、理由和不确定性保存在 JSON 对应 `recovery_cases` 项中。这里的 baseline/variant 只截断显示，Gold 和 new hit 保留较短原文。

### A→C（27 条）

| sample_id | source excerpt | Gold span | baseline -> variant (hits) | labels | completeness | reason |
|---|---|---|---|---|---|---|
| `estg_000028` | The income shall be taxed at the tax rate that results when taking into account the converted income; however, the tax to be assessed may not be higher than that which would result from the taxation of all emoluments. | at the tax rate that results when taking into account the converted income; however, the tax to be assessed may not be higher than that which would result from the taxation of a... | [] -> at the tax rate that results when taking into account the converted income | other | partial_content | 新增命中片段是税率/税基计算条件；Gold 长 span 后半段的税额上限未恢复。原 time 标签由 when/to 等词误触。 |
| `estg_000031` | (1) Profit is the difference, to be determined by double-entry bookkeeping, between the business assets at the end of the financial year and the business assets at the end of the preceding financial year. | to be determined by double-entry bookkeeping, between the business assets at the end of the financial year and the business assets at the end of the preceding financial year | [] -> to be determined by double-entry bookkeeping | manner | partial_content | 新增片段为按复式记账确定的计量方法；Gold 还包含财年期末/期初资产比较，未恢复。原 time 标签不正确。 |
| `estg_000033` | ns or losses from the disposal or withdrawal and other changes in value of land that is part of the fixed assets are not to be taken into account. | that is part of the fixed assets | [] -> from the disposal or withdrawal and other changes in value of land that is part of the fixed assets | other | complete_interpretable | 新增预测片段覆盖 Gold「属于固定资产」这一资产范围条件，并附带处置/价值变动语境；未观察到旧标签所指的时间恢复。 |
| `estg_000037` | In any event, business expenses shall include: 1. a) contributions by the insured person to compulsory insurance in the statutory health, accident and pension insurance, and b) compulsory contributions to welfare and support institutions... | 1. a) contributions by the insured person to compulsory insurance in the statutory health, accident and pension insurance, and b) compulsory contributions to welfare and support... | In any event -> to the extent that these institutions serve health, old-age, invalidity and survivors’ provision; subject to the following conditions | purpose, other | partial_content | 新增命中两个条件/目的片段（机构服务范围、但书条件），只覆盖长清单 Gold 的一小部分；同时新增未匹配片段，属于 recovery+FP。 |
| `estg_000040` | Dependants also include spouses and children (Section 106). (ee) The contributions, together with direct benefits within the meaning of Section 3(1) item 15, must not exceed 10% of the total wages and salaries of the beneficiaries. | spouses and children (Section 106). (ee) The contributions, together with direct benefits within the meaning of Section 3(1) item 15, must not exceed 10% of the total wages and ... | [] -> 10% of the total wages and salaries of the beneficiaries | quantity | partial_content | 新增片段是 10% 工资/薪金上限，属于数量约束；Gold 还包含受益人/法律引用等内容，未完整恢复。原 time 是 to/within 误分。 |
| `estg_000061` | Furthermore, it must be ensured through additions or deductions and through appropriate balance sheet items that other changes in the profit determination principles (e.g., regarding the commercial law principles of orderly bookkeeping w... | through additions or deductions and through appropriate balance sheet items that other changes in the profit determination principles (e.g., regarding the commercial law princip... | [] -> through additions or deductions and through appropriate balance sheet items; upon the change in the profit determination method; on a tax-neutral basis; to the higher going-concern value | manner, time, other | partial_content | 新增四个片段分别覆盖加计/减计和资产负债表项目的 manner、利润确定方法变更的 time、税中性/持续经营价值的其他条件；长 Gold 远未完整恢复。 |
| `estg_000075` | manent establishment), the business assets transferred abroad shall be measured at the values that would have been applied in the case of a supply or other service to a business entirely independent of the taxpayer, if  — the foreign bus... | at the values that would have been applied in the case of a supply or other service to a business entirely independent of the taxpayer | [] -> at the values that would have been applied in the case of a supply or other service to a business entirely independen... | other | complete_interpretable | 新增片段与 Gold 的独立交易/估值标准完全一致，属于可解释的其他约束恢复；没有 time、legal reference 或 purpose 的新增证据。 |
| `estg_000077` | r place of management abroad may, under the following conditions, be recognized in the year of acquisition at a value of 90% of the acquisition costs: a) The funds are used for a permanent establishment abroad which serves the distributi... | in the year of acquisition at a value of 90% of the acquisition costs: a) The funds are used for a permanent establishment abroad which serves the distribution, setting up or se... | [] -> in the year of acquisition; at a value of 90% of the acquisition costs; for a permanent establishment abroad which serves the distribution, setting up or servicing of goods produced in Austria; acquired upon formation... | time, quantity, purpose, other | partial_content | 新增多个片段覆盖购置年度、90% 账面价值、境外常设机构用途和形成/增资条件等；Gold 是长清单，只恢复了部分语义，多标签并列。 |
| `estg_000103` | ng a tax-exempt amount, the tax office shall set the taxpayer a grace period of two weeks for submission of the list. | two weeks | [] -> of two weeks | time | complete_interpretable | 新增片段 of two weeks 恢复了两周期限，属于完整时间约束。 |
| `estg_000104` | of depreciable fixed assets, the taxpayer may claim an investment allowance of up to 20% of the acquisition or production costs as a profit-reducing deduction. | up to 20% of the acquisition or production costs as a profit-reducing deduction | [] -> of up to 20% of the acquisition or production costs | quantity | partial_content | 新增片段 up to 20% 是数量上限；Gold 还包含作为减少利润的扣除未恢复。原 time 由 to 误触。 |
| `estg_000134` | (7) Hidden reserves may be allocated to a tax-free reserve in the year of their disclosure, provided that no transfer is effected in the same business year. | in the year of their disclosure | [] -> in the year of their disclosure | time | complete_interpretable | 新增片段与 Gold 披露年度一致，属于完整时间约束。 |
| `estg_000145` | Taxpayers who determine their profit in accordance with Section 4(3) may apply in the tax return for an amount to be left tax-free for the notional severance pay claims existing at the end of the business year. | in the tax return for an amount to be left tax-free for the notional severance pay claims existing at the end of the business year | [] -> in the tax return; for the notional severance pay claims existing at the end of the business year | time, purpose | partial_content | 新增片段覆盖在纳税申报中的期间和为名义遣散费的目的；Gold 中免税留存金额未完整恢复。 |
| `estg_000148` | their profit pursuant to Section 4(1) or Section 5 may form pension provisions for written, legally binding, and irrevocable pension commitments. | for written, legally binding, and irrevocable pension commitments | [] -> for written, legally binding, and irrevocable pension commitments | purpose | complete_interpretable | 新增片段完整覆盖 Gold 的为书面、有约束力且不可撤销的养老金承诺这一用途/资格条件，不是时间恢复。 |
| `estg_000164` | between the residence and the place of work of up to 20 km, these expenses are generally compensated by the transport tax credit (Section 33(5) and Section 57(3)). b) If the one-way distance between the residence and the place of work pr... | generally compensated by the transport tax credit (Section 33(5) and Section 57(3)). b) If the one-way distance between the residence and the place of work predominantly travell... | [] -> by the transport tax credit (Section 33(5) and Section 57(3)); instead of the flat-rate amounts under lit. b | legal_reference, other | partial_content | 新增命中片段包括交通税收抵免法律条号和代替 b 项定额的适用方式；长 Gold 清单的其他规则未恢复。同时新增未匹配的 20 km 条件，属于 recovery+FP。 |
| `estg_000222` | taxpayer has died in the meantime. c) A subsequent taxation of loan repayments (Section 1, no. 3, lit. d) must be carried out if it is determined that the statutory requirements for re | Section 1, no. 3, lit. d | [] -> (Section 1, no. 3, lit. d) | legal_reference | complete_interpretable | 新增片段完整恢复 Gold 的法律条号引用，直接反驳 legal reference=0；原 quantity 标签由数字优先规则误分。 |
| `estg_000232` | isition of such profit participation certificates or shares may not be deducted under Section 1(4); in these cases, the ten-year period for subsequent taxation runs from the time of the deposit of those profit participation certificates ... | under Section 1(4); in these cases, the ten-year period for subsequent taxation runs from the time of the deposit of those profit participation certificates or shares whose acqu... | [] -> under Section 1(4); from the time of the deposit of those profit participation certificates or shares whose acquisition costs were deduct... | legal_reference, time | partial_content | 新增片段覆盖 Section 1(4) 法律引用和自存入时起的时间起点；Gold 中十年期间等仍缺失，故为部分恢复。 |
| `estg_000247` | Otherwise, expenses and outlays that are not deductible from the individual categories of income may, if the statutory requirements are met, be deducted as special expenses or extraordinary burdens. 9. | Otherwise, expenses and outlays that are not deductible from the individual categories of income may, if the statutory requirements are met, be deducted as special expenses or e... | [] -> that are not deductible from the individual categories of income | other | partial_content | 新增片段是不属于各类所得的范围限定，属于条件/范围而非时间；Gold 其余扣除规则未恢复。原 time 由 may/to 误分。 |
| `estg_000283` | A business trip occurs when an employee  — leaves their duty station (office, permanent establishment, factory premises, warehouse, etc.) on the employer’s orders to perform work duties, or — works so far away from their permanent place ... | their duty station (office, permanent establishment, factory premises, warehouse, etc.) on the employer’s orders to perform work duties, or — works so far away from their perman... | [] -> on the employer’s orders; to perform work duties; so far away from their permanent place of residence (family home) that they cannot reasonably be expected to return t... | purpose, manner, other | partial_content | 新增片段覆盖雇主指令、履行工作职责和远离住所无法每日返回等定义条件，属于目的/方式和范围语义；长 Gold 未完整恢复。 |
| `estg_000293` | not fall within the income categories referred to in Section 2(1) to (4): 1. a) profit shares (dividends), interest and other distributions from shares or interests in limited liability companies; b) similar distributions and patronage r... | profit shares (dividends), interest and other distributions from shares or interests in limited liability companies; b) similar distributions and patronage refunds from interest... | [] -> excluding those under Section 13 of the Corporate Income Tax Act 1988 | legal_reference | partial_content | 新增片段是排除《公司所得税法》第13条的法律引用/例外，长 Gold 的所得清单其余部分未恢复。原 time 不正确。 |
| `estg_000433` | dit (Section 57(2)) on the employee’s first wage tax card, it must be cancelled simultaneously with the issuance of a wage tax card for the spouse. | simultaneously with the issuance of a wage tax card for the spouse | [] -> simultaneously with the issuance of a wage tax card for the spouse | time | complete_interpretable | 新增片段完整恢复与配偶工资税卡签发同时的时间关系；原 purpose 标签由 to/for 误分。 |
| `estg_000505` | e first and second sentences are exceeded, such other emoluments shall be taxed like current emoluments according to the wage tax scale; in this respect, a monthly wage payment period shall be assumed. | like current emoluments according to the wage tax scale; in this respect, a monthly wage payment period | [] -> according to the wage tax scale; in this respect; a monthly wage payment period | manner, time, other | partial_content | 新增片段覆盖工资税表适用方式、月度工资支付期间和指代性 in this respect；其中 in this respect 基本是 overlap 命中，Gold 的完整比较语义未恢复。 |
| `estg_000546` | (4) An annual adjustment pursuant to subsection 2 or 3 shall not take place if the income from employment is assessed for income tax p | pursuant to subsection 2 or 3 | [] -> pursuant to subsection 2 or 3 | legal_reference | complete_interpretable | 新增片段完整恢复 Gold 依照第2或3款的法律引用；该条为原 taxonomy 漏收记录，且伴随新增未匹配的法律引用而仍为 unchanged_wrong。 |
| `estg_000569` | The tax office may, however, upon application, permit that the tax-exempt income components pursuant to Section 3 and the inc | upon application | [] -> upon application | other | complete_interpretable | 新增片段 upon application 完整恢复程序性条件/申请方式；原 taxonomy 漏收，且变体还有其他未匹配预测，属于 recovery+FP。 |
| `estg_000572` | nnot exceptionally be determined, the wage payment period shall be deemed to be at least the actually expended working time. | at least the actually expended working time | [] -> at least the actually expended working time | quantity | complete_interpretable | 新增片段至少实际工作时间恢复了最低数量/计算基准，属于完整数量语义。 |
| `estg_000664` | The following shall apply to this provision:  — Certain income, in particular foreign income, may be wholly or partially excluded from the tax base or taxed at a reduced tax rate, or  — taxation may be based solely on the amount correspo... | to this provision:  — Certain income, in particular foreign income, may be wholly or partially excluded from the tax base or taxed at a reduced tax rate, or  — taxation may be b... | [] -> wholly or partially; solely on the amount corresponding to domestic consumption; also | quantity, exclusivity, other | partial_content | 新增片段只包含全部或部分、仅按国内消费数额以及话语词 also，仅覆盖长 Gold 的碎片语义，不能认定完整约束恢复。 |
| `estg_000716` | ot take place if: 1. the building society transfers the amount to be recovered, with the consent of the taxpayer, to the competent Regional Finance Directorate; 2. in the cases of paragraph (6 | with the consent of the taxpayer | [] -> with the consent of the taxpayer | other | complete_interpretable | 新增片段经纳税人同意完整恢复 Gold 的同意条件；原 taxonomy 漏收，且伴随四个新增未匹配片段，属于 recovery+FP。 |
| `estg_000816` | es from the calendar year; in such case, the profit shall be taken into account when determining income for the calendar year in which the business year ends. | when determining income for the calendar year in which the business year ends | [] -> when determining income for the calendar year in which the business year ends | time | complete_interpretable | 新增片段完整恢复在营业年度结束的日历年度确定所得时这一时间/期间关系。 |

### B→D（25 条）

| sample_id | source excerpt | Gold span | baseline -> variant (hits) | labels | completeness | reason |
|---|---|---|---|---|---|---|
| `estg_000030` | (3) Income within the meaning of paragraph 1 items 10 and 11 shall be taken into account when determining the tax for the employee's other i | within the meaning of paragraph 1 items 10 and 11 | [] -> within the meaning of paragraph 1 items 10 and 11 | legal_reference | complete_interpretable | 新增片段完整恢复第1款第10/11项含义内的法律引用限定；原 time 由 within/year 误分。 |
| `estg_000031` | (1) Profit is the difference, to be determined by double-entry bookkeeping, between the business assets at the end of the financial year and the business assets at the end of the preceding financial year. | to be determined by double-entry bookkeeping, between the business assets at the end of the financial year and the business assets at the end of the preceding financial year | [] -> to be determined by double-entry bookkeeping; between the business assets at the end of the financial year and the business assets at the end of the preceding fina... | manner, other | partial_content | 新增两个片段分别覆盖复式记账方法和财年期末/期初资产比较；前者是方式，后者是范围/基准。Gold 仍未被完整恢复。 |
| `estg_000033` | ns or losses from the disposal or withdrawal and other changes in value of land that is part of the fixed assets are not to be taken into account. | that is part of the fixed assets | [] -> from the disposal or withdrawal and other changes in value of land that is part of the fixed assets | other | complete_interpretable | 新增片段覆盖 Gold 属于固定资产的范围条件，属于其他/资产范围语义。 |
| `estg_000037` | In any event, business expenses shall include: 1. a) contributions by the insured person to compulsory insurance in the statutory health, accident and pension insurance, and b) compulsory contributions to welfare and support institutions... | 1. a) contributions by the insured person to compulsory insurance in the statutory health, accident and pension insurance, and b) compulsory contributions to welfare and support... | for the purpose of old-age and survivors’ provision. -> to the extent that these institutions serve health, old-age, invalidity and survivors’ provision; subject to the following conditions | purpose, other | partial_content | 新增命中条件/目的片段，只覆盖长清单 Gold 的一小部分；FP 数量由 1 增至 2，属于 recovery+FP。 |
| `estg_000040` | Dependants also include spouses and children (Section 106). (ee) The contributions, together with direct benefits within the meaning of Section 3(1) item 15, must not exceed 10% of the total wages and salaries of the beneficiaries. | spouses and children (Section 106). (ee) The contributions, together with direct benefits within the meaning of Section 3(1) item 15, must not exceed 10% of the total wages and ... | [] -> together with direct benefits within the meaning of Section 3(1) item 15 | legal_reference | partial_content | 新增片段是与第3(1)条第15项含义内的直接给付一起的法律引用组合条件；10% 上限等 Gold 内容未由该片段恢复。 |
| `estg_000046` | d if the invention is already protected by patent law. — The research allowance generally amounts to up to 12% of research expenditures. — An increased research allowance of up to 18% may be claimed if the inventions are not made availab... | generally amounts to up to 12% of research expenditures. — An increased research allowance of up to 18% | [] -> up to 12% of research expenditures; of up to 18% | quantity | partial_content | 新增片段覆盖 12% 和 18% 两档数量上限，属于数量约束；长 Gold 句子只恢复了比例部分。原 time 由 to 误分。 |
| `estg_000055` | ntal, trust, brokerage, distribution and administration costs must be allocated evenly over the period of the prepayment, unless they relate only to the current and the following year. | evenly over the period of the prepayment | [] -> evenly over the period of the prepayment | manner, time | complete_interpretable | 新增片段在预付期间内均匀分摊完整恢复分摊方式/时间范围；原 taxonomy 漏收，且伴随新增未匹配片段。 |
| `estg_000061` | Furthermore, it must be ensured through additions or deductions and through appropriate balance sheet items that other changes in the profit determination principles (e.g., regarding the commercial law principles of orderly bookkeeping w... | through additions or deductions and through appropriate balance sheet items that other changes in the profit determination principles (e.g., regarding the commercial law princip... | [] -> through additions or deductions and through appropriate balance sheet items; upon the change in the profit determination method; on a tax-neutral basis; to the higher going-concern value | manner, time, other | partial_content | 新增片段覆盖加计/减计与资产负债表方式、方法变更时点、税中性和持续经营价值；长 Gold 只部分恢复。 |
| `estg_000077` | r place of management abroad may, under the following conditions, be recognized in the year of acquisition at a value of 90% of the acquisition costs: a) The funds are used for a permanent establishment abroad which serves the distributi... | in the year of acquisition at a value of 90% of the acquisition costs: a) The funds are used for a permanent establishment abroad which serves the distribution, setting up or se... | [] -> in the year of acquisition; at a value of 90% of the acquisition costs; for a permanent establishment abroad which serves the distribution, setting up or servicing of goods produced in Austria; acquired upon formation... | time, quantity, purpose, legal_reference, other | partial_content | 新增片段覆盖购置年度、90% 价值、境外常设机构用途、形成/增资条件及 letter (b) 法律引用，是典型多语义碎片恢复，非 temporal-only。 |
| `estg_000082` | To the extent that the input tax can be deducted (Section 12(1) of the Value Added Tax Act 1972), it does not form part of the acquisition or production costs of the asset on the acquisition or production of which it is incurred, and sha... | Section 12(1) of the Value Added Tax Act 1972), it does not form part of the acquisition or production costs of the asset on the acquisition or production of which it is incurre... | [] -> on the acquisition or production of which it is incurred | other | partial_content | 新增片段是在其发生购置/生产时的范围从句，Gold 中的第12(1)条法律引用未被该片段恢复。 |
| `estg_000104` | of depreciable fixed assets, the taxpayer may claim an investment allowance of up to 20% of the acquisition or production costs as a profit-reducing deduction. | up to 20% of the acquisition or production costs as a profit-reducing deduction | [] -> of up to 20% of the acquisition or production costs | quantity | partial_content | 新增片段为 20% 上限，Gold 中扣除性质未恢复；原 time 由 to 误得。 |
| `estg_000112` | n of a business, a part of a business or an interest of a partner who is deemed to be an entrepreneur (co-entrepreneur). — For used assets which are intended, directly or indirectly, for transfer for | to be an entrepreneur (co-entrepreneur) | [] -> Upon acquisition of a business, a part of a business or an interest of a partner who is deemed to be an entrepreneur ... | other | complete_interpretable | 新增长片段包含 Gold 被视为企业家的身份定义，属于其他/主体资格；原 taxonomy 漏收，且伴随 3 个新增未匹配片段。 |
| `estg_000134` | (7) Hidden reserves may be allocated to a tax-free reserve in the year of their disclosure, provided that no transfer is effected in the same business year. | in the year of their disclosure | [] -> in the year of their disclosure | time | complete_interpretable | 新增片段与 Gold 披露年度一致，属于完整时间约束。 |
| `estg_000145` | Taxpayers who determine their profit in accordance with Section 4(3) may apply in the tax return for an amount to be left tax-free for the notional severance pay claims existing at the end of the business year. | in the tax return for an amount to be left tax-free for the notional severance pay claims existing at the end of the business year | [] -> in the tax return; for the notional severance pay claims existing at the end of the business year | time, purpose | partial_content | 新增片段覆盖纳税申报期间和名义遣散费目的，Gold 中留存金额等未完整恢复。 |
| `estg_000148` | their profit pursuant to Section 4(1) or Section 5 may form pension provisions for written, legally binding, and irrevocable pension commitments. | for written, legally binding, and irrevocable pension commitments | [] -> for written, legally binding, and irrevocable pension commitments | purpose | complete_interpretable | 新增片段完整恢复为书面、有约束力、不可撤销的养老金承诺这一用途/资格条件。 |
| `estg_000206` | If these expenses in total — are lower than the relevant maximum amount, half of the expenses shall be deducted as special expenses — are equal to or higher than the relevant maximum amount, half of the maximum amount shall be deducted a... | half of the expenses shall be deducted as special expenses — are equal to or higher than the relevant maximum amount, half of the maximum amount shall be deducted as special exp... | [] -> within the meaning of paragraph 1 items 2 to 4 | legal_reference | partial_content | 新增片段恢复第1款第2至4项含义内的法律引用限定；长 Gold 中费用/最高额计算部分未恢复。原 time 由 within 误分。 |
| `estg_000210` | ck corporations within the meaning of paragraph 1 item 4 are stock corporations having their registered seat and place of management in the country, aa) which belong to the "Trade" or "Industry" sections of a chamber of commerc | having their registered seat and place of management in the country | [] -> having their registered seat and place of management in the country | other | complete_interpretable | 新增片段完整恢复 Gold 住所和经营管理地在国内的地域/主体范围条件；原 taxonomy 漏收，且伴随 5 个新增未匹配片段。 |
| `estg_000247` | Otherwise, expenses and outlays that are not deductible from the individual categories of income may, if the statutory requirements are met, be deducted as special expenses or extraordinary burdens. 9. | Otherwise, expenses and outlays that are not deductible from the individual categories of income may, if the statutory requirements are met, be deducted as special expenses or e... | [] -> that are not deductible from the individual categories of income | other | partial_content | 新增片段是不属于各类所得的范围限定，属于条件/范围而非时间；Gold 其余规则未恢复。 |
| `estg_000283` | A business trip occurs when an employee  — leaves their duty station (office, permanent establishment, factory premises, warehouse, etc.) on the employer’s orders to perform work duties, or — works so far away from their permanent place ... | their duty station (office, permanent establishment, factory premises, warehouse, etc.) on the employer’s orders to perform work duties, or — works so far away from their perman... | [] -> on the employer’s orders; to perform work duties; so far away from their permanent place of residence (family home) that they cannot reasonably be expected to return t... | purpose, manner, other | partial_content | 新增片段覆盖雇主指令、工作职责和远离住所等定义条件；长 Gold 未完整恢复。 |
| `estg_000546` | (4) An annual adjustment pursuant to subsection 2 or 3 shall not take place if the income from employment is assessed for income tax p | pursuant to subsection 2 or 3 | [] -> pursuant to subsection 2 or 3 | legal_reference | complete_interpretable | 新增片段完整恢复依照第2或3款的法律引用；原 taxonomy 漏收，且伴随新增未匹配法律引用。 |
| `estg_000569` | The tax office may, however, upon application, permit that the tax-exempt income components pursuant to Section 3 and the inc | upon application | [] -> upon application | other | complete_interpretable | 新增片段 upon application 完整恢复程序性条件；原 taxonomy 漏收，且伴随两个新增未匹配片段。 |
| `estg_000664` | The following shall apply to this provision:  — Certain income, in particular foreign income, may be wholly or partially excluded from the tax base or taxed at a reduced tax rate, or  — taxation may be based solely on the amount correspo... | to this provision:  — Certain income, in particular foreign income, may be wholly or partially excluded from the tax base or taxed at a reduced tax rate, or  — taxation may be b... | [] -> wholly or partially; solely; also | exclusivity | overlap_only | 新增命中只有 wholly or partially、solely、also 等碎片/孤立排他 cue，未恢复 Gold 中的完整范围或税基规则；冻结指标记为 recovery，但不足以认定语义恢复。 |
| `estg_000773` | is held exclusively, directly or indirectly, by corporations under public law, activities conducted in a separate set of accounts within the meaning of subsection (3) shall be deemed a single activity, even if the individual activities l... | activities conducted in a separate set of accounts within the meaning of subsection (3) | [] -> in a separate set of accounts within the meaning of subsection (3) | legal_reference, other | partial_content | 新增片段命中的是独立账套、第(3)款含义内，属于法律引用/账户范围；Gold 中 activities conducted 未恢复。原 taxonomy 漏收，且伴随新增未匹配片段。 |
| `estg_000776` | An exercise of public authority shall be assumed in particular where services are involved the acceptance of which the recipient is obliged to accept by virtue of a statutory or official order. | in particular where services are involved the acceptance of which the recipient is obliged to accept by virtue of a statutory or official order | [] -> in particular | undetermined | overlap_only | 新增命中仅为话语标记 in particular，落在 Gold 区间内但没有恢复任何具体约束语义；是 overlap 得分的典型反例。 |
| `estg_000800` | apply as long as the sponsoring undertaking suspends the contribution payments (Section 4(4) no. 2 of the Income Tax Act 1988). d) The pension commitments of the fund may not exceed 80% of the last current active remuneration. e) The ben... | (Section 4(4) no. 2 of the Income Tax Act 1988). d) The pension commitments of the fund may not exceed 80% of the last current active remuneration. e) The beneficiary must also ... | [] -> Section 4(4) no. 2 of the Income Tax Act 1988 | legal_reference | partial_content | 新增片段恢复 Section 4(4) no.2 / Income Tax Act 1988 法律条号；Gold 中养老基金承诺、既得权益等主要内容未恢复。原 time 由年份和 may 等误分。 |

> 完整逐条理由和 uncertainty 不再在 Markdown 表里重复；请以同目录 JSON 的 `recovery_cases[*].reason` 与 `uncertainty` 为准。所有标签均是 AI 离线意见，不是人工裁决。

## 5. 失败侧：新未匹配、删除未匹配与 FP 净变化

### 5.1 汇总

| 方向 | missed Gold | 未匹配预测 | 新出现未匹配 span | 删除未匹配 span | FP 净变化 |
|---|---:|---:|---:|---:|---:|
| A_to_C | 60→38 | 27→50 | 36 | 13 | +23 |
| B_to_D | 53→30 | 26→58 | 43 | 11 | +32 |

| 方向 | recovery 且 FP 不增 | recovery 且 FP 增 | FP 增但无 recovery | FP 降且无 recovery |
|---|---:|---:|---:|---:|
| A_to_C | 22 | 5 | 14 | 4 |
| B_to_D | 18 | 7 | 18 | 4 |

- 新出现未匹配 span 与删除未匹配 span 按 `(start,end,normalized_text)` 区分；FP 净变化 = 变体未匹配数 - 基线未匹配数，不能把 span 替换直接说成新增 FP。
- 孤立 cue：A→C 新未匹配中出现 5 次 `only`；B→D 出现 4 次 `only`。另有手工复核案例 `000786` 的 `only` 落在长 Gold 内，虽匹配但仍属边界/overlap 问题。
- 其他字段重抽为 constraint 的候选例子：`000002` 的 action 片段 `for that calendar year...`、`000071` 的 `For registered traders`、`000112`/`000210` 的主体/条件短语、`000507` 的 exception-like 短语。结构上跨字段重叠计数只能作诊断，不能仅凭 Gold 未覆盖就断言语言上无关。
- 结构诊断（仅启发式）：新未匹配 constraint span 与 coarse Gold 其他字段相交的出现次数为 A→C action 11、condition 24；B→D action 13、condition 26、actor 1、exception 1。一个 span 可交多个字段，不能仅凭 Gold 未覆盖就断言语言上无关。
- 时间短语 FP 例子：`000027` 的 `only for part of the calendar year`、`000004` 的 `prior` 和 `by official notice`、`000539` 的 `before carrying out an annual adjustment`/`in due time`、`000209` 的时间限定。temporal-only 不能自动充当 precision guard。

### 5.2 发生新未匹配或删除未匹配的案例

| sample / dir | unmatched | delta | recovery | new unmatched spans | removed unmatched spans |
|---|---:|---:|---|---|---|
| `estg_000004` A_to_C | 0→1 | +1 | no | only |  |
| `estg_000027` A_to_C | 0→1 | +1 | no | only for part of the calendar year |  |
| `estg_000037` A_to_C | 1→2 | +1 | yes | for the purpose of old-age and survivors’ provision |  |
| `estg_000038` A_to_C | 0→1 | +1 | no | also |  |
| `estg_000039` A_to_C | 0→1 | +1 | no | to the extent that they are required under the articles of association for benefit entitlements of current and former... |  |
| `estg_000052` A_to_C | 2→1 | -1 | no | insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit... | together with contributions within the meaning of item 6; a total of 10% of the profit of the immediately preceding business year |
| `estg_000055` A_to_C | 0→1 | +1 | no | not subject to capitalization for advisory, suretyship, borrowed funds, guarantee, rental, trust, brokerage, distribu... |  |
| `estg_000106` A_to_C | 0→1 | +1 | no | only |  |
| `estg_000108` A_to_C | 1→2 | +1 | no | to the extent that they directly serve the business purpose or are intended for residential purposes of employees of ... |  |
| `estg_000109` A_to_C | 0→1 | +1 | no | only |  |
| `estg_000112` A_to_C | 3→3 | +0 | no | which are intended, directly or indirectly, for transfer for consideration to the seller (sale and lease back) or for...; acquired by a group company within a group as defined by Section 15 of the Stock Corporation Act 1965 | for consideration to the seller; within a group as defined by Section 15 of the Stock Corporation Act 1965 |
| `estg_000118` A_to_C | 0→1 | +1 | no | only |  |
| `estg_000130` A_to_C | 0→1 | +1 | no | only |  |
| `estg_000131` A_to_C | 1→1 | +0 | no | only if the management or the registered office is located in the domestic territory | only |
| `estg_000164` A_to_C | 0→1 | +1 | yes | For a one-way distance between the residence and the place of work of up to 20 km |  |
| `estg_000209` A_to_C | 1→2 | +1 | no | within two years after the registration of the resolution on the reduction of the share capital; for the purpose of repaying parts of the share capital | within two years after the registration of the resolution on the reduction of the share capital for the purpose of re... |
| `estg_000210` A_to_C | 1→0 | -1 | no |  | excluding the generation of electrical energy, gas or heat |
| `estg_000393` A_to_C | 0→6 | +6 | no | in total; does not exceed the amount of 10,000 S; pursuant to Section 18(6) and (7); in order to avoid double taxation; within the meaning of Section 3(1) item 10 or 11; subject to withholding tax |  |
| `estg_000414` A_to_C | 5→0 | -5 | no |  | under Section 39; under Section 41; under Section 83(2); under Section 95(2); under Section 72 |
| `estg_000539` A_to_C | 0→3 | +3 | no | upon application of the employee; before carrying out an annual adjustment; in due time |  |
| `estg_000546` A_to_C | 0→1 | +1 | yes | pursuant to Section 41 |  |
| `estg_000569` A_to_C | 0→3 | +3 | yes | pursuant to Section 3; referred to in Section 26; in another manner |  |
| `estg_000601` A_to_C | 0→1 | +1 | no | in respect of whom it is doubtful whether they are employees of the business |  |
| `estg_000716` A_to_C | 0→4 | +4 | yes | to the competent Regional Finance Directorate; in the cases of paragraph (6); within the meaning of Section 18(1) item 3; by or for the persons referred to in paragraph (2) |  |
| `estg_000854` A_to_C | 1→0 | -1 | no |  | in exceptional cases |
| `estg_000002` B_to_D | 0→1 | +1 | no | for that calendar year in which the business year ends |  |
| `estg_000004` B_to_D | 0→3 | +3 | no | only; prior; by official notice |  |
| `estg_000027` B_to_D | 0→1 | +1 | no | only for part of the calendar year |  |
| `estg_000037` B_to_D | 1→2 | +1 | yes | subject to state supervision; for the purpose of old-age and survivors’ provision | for the purpose of old-age and survivors’ provision. |
| `estg_000039` B_to_D | 0→1 | +1 | no | to the extent that they are required under the articles of association for benefit entitlements of current and former... |  |
| `estg_000052` B_to_D | 2→1 | -1 | no | insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit... | together with contributions within the meaning of item 6; a total of 10% of the profit of the immediately preceding business year |
| `estg_000055` B_to_D | 0→1 | +1 | yes | not subject to capitalization for advisory, suretyship, borrowed funds, guarantee, rental, trust, brokerage, distribu... |  |
| `estg_000071` B_to_D | 0→1 | +1 | no | For registered traders |  |
| `estg_000080` B_to_D | 1→0 | -1 | no |  | (deemed acquisition cost) |
| `estg_000087` B_to_D | 0→1 | +1 | no | on the basis of a merger that does not result in liquidation taxation |  |
| `estg_000106` B_to_D | 0→1 | +1 | no | only |  |
| `estg_000108` B_to_D | 1→2 | +1 | no | to the extent that they directly serve the business purpose or are intended for residential purposes of employees of ... |  |
| `estg_000112` B_to_D | 0→3 | +3 | yes | For low-value assets written off pursuant to Section 13; For used assets which are intended, directly or indirectly, for transfer for consideration to the seller (sale and le...; For used assets acquired by a group company within a group as defined by Section 15 of the Stock Corporation Act 1965 |  |
| `estg_000113` B_to_D | 0→1 | +1 | no | in accordance with its designated purpose |  |
| `estg_000128` B_to_D | 1→3 | +2 | no | only; in a domestic permanent establishment |  |
| `estg_000130` B_to_D | 0→1 | +1 | no | only |  |
| `estg_000146` B_to_D | 3→1 | -2 | no |  | in a continuously maintained record; together with the profit declaration for the relevant business year |
| `estg_000161` B_to_D | 0→1 | +1 | no | only under the following conditions |  |
| `estg_000164` B_to_D | 0→1 | +1 | no | For a one-way distance between the residence and the place of work of up to 20 km |  |
| `estg_000209` B_to_D | 1→3 | +2 | no | within two years after the registration of the resolution on the reduction of the share capital; for the purpose of repaying parts of the share capital; (Sections 219 and 245 of the Stock Corporation Act 1965, Section 2 of the Federal Act on the Transformation of Commer... | within two years after the registration of the resolution on the reduction of the share capital for the purpose of re... |
| `estg_000210` B_to_D | 0→5 | +5 | yes | for which guarantees regarding value or dividend claims are provided; within the meaning of paragraph 1 item 4; which belong to the "Trade" or "Industry" sections of a chamber of commerce; whose main business focus, according to the articles of association and the preparatory acts or the actual management...; for which no general deficiency guarantees for the event of insolvency have been assumed |  |
| `estg_000218` B_to_D | 0→1 | +1 | no | In the case of a reduction in deductible insurance premiums (Section 1(2), last sentence) |  |
| `estg_000347` B_to_D | 2→2 | +0 | no | of up to and including 50 S; exceeding 50 S | remainders of up to and including 50 S; remainders exceeding 50 S |
| `estg_000393` B_to_D | 0→1 | +1 | no | in total does not exceed the amount of 10,000 S |  |
| `estg_000507` B_to_D | 0→1 | +1 | no | regardless of whether they are based on judicial or extrajudicial settlements, and also in cases where they are not g... |  |
| `estg_000509` B_to_D | 1→0 | -1 | no |  | that does not fall under subsections 1 to 8 |
| `estg_000546` B_to_D | 0→1 | +1 | yes | pursuant to Section 41 |  |
| `estg_000569` B_to_D | 0→2 | +2 | yes | pursuant to Section 3; referred to in Section 26 |  |
| `estg_000659` B_to_D | 1→1 | +0 | no | from which no withholding of tax on wages, on capital yield, or under Sections 99 to 101 is to be made | on their income from which no withholding of tax on wages, on capital yield, or under Sections 99 to 101 is to be made |
| `estg_000773` B_to_D | 0→1 | +1 | yes | exclusively, directly or indirectly, by corporations under public law |  |
| `estg_000786` B_to_D | 0→2 | +2 | no | that are unrelated to the purpose of the bank; do not benefit any board member, managing director, or supervisory board member through disproportionately high remun... |  |

### 5.3 全部 7 条原 manual-review 记录

| sample / field / dir | 原标记 | 可核对变化 | 离线复核意见 |
|---|---|---|---|
| `estg_000027` constraint A_to_C | `unrelated_temporal_phrase_fp` manual=true | missed 0→0; unmatched 0→1 | added: only for part of the calendar year; removed: []。原人工标记保持不变；本行是 AI 离线复核意见。 |
| `estg_000027` constraint B_to_D | `unrelated_temporal_phrase_fp` manual=true | missed 0→0; unmatched 0→1 | added: only for part of the calendar year; removed: []。原人工标记保持不变；本行是 AI 离线复核意见。 |
| `estg_000080` constraint B_to_D | `span_boundary_changed` manual=true | missed 0→0; unmatched 1→0 | added: at the time of receipt; removed: (continuation of book values); (deemed acquisition cost)。原人工标记保持不变；本行是 AI 离线复核意见。 |
| `estg_000509` constraint B_to_D | `span_boundary_changed` manual=true | missed 0→0; unmatched 1→0 | added: in accordance with the wage tax rate schedule; removed: that does not fall under subsections 1 to 8; a monthly wage payment period。原人工标记保持不变；本行是 AI 离线复核意见。 |
| `estg_000786` constraint B_to_D | `unrelated_temporal_phrase_fp` manual=true | missed 0→0; unmatched 0→2 | added: that are unrelated to the purpose of the bank; do not benefit any board member, managing director, or supervisory board member through disproportionately high remun...; only; removed: []。原人工标记保持不变；本行是 AI 离线复核意见。 |
| `estg_000854` constraint A_to_C | `span_boundary_changed` manual=true | missed 0→0; unmatched 1→0 | added: []; removed: in exceptional cases。原人工标记保持不变；本行是 AI 离线复核意见。 |
| `estg_000037` actor C_to_D | `uncertain` manual=true | missed 0→1; unmatched 0→1 | 同时删除有效 actor 并新增非 actor 短语，属于混合错误；不应硬压成单一类别。原人工标记保持不变。 |

### 5.4 B→D 的 6 个 actor regression

| sample_id | Gold actor | B actor | D 新增 unmatched actor |
|---|---|---|---|
| `estg_000004` | [] | [] | the tax office |
| `estg_000021` | [] | [] | employees in tobacco processing establishments |
| `estg_000105` | [] | [] | the investment allowances |
| `estg_000209` | [] | [] | Shares issued as a result of a capital increase; capital reductions by a stock corporation or a limited liability company as the legal predecessor of the stock corpor... |
| `estg_000302` | [] | [] | The following income |
| `estg_000505` | [] | [] | such other emoluments |

这 6 个 regression 的共同表型是 Gold actor 空、B actor 空、D 新增 1 个（`000209` 新增 2 个）actor；这是可观察关联，不是已经证明的模型内部机制。

## 6. 设计取舍判断

### 6.1 校正后是否仍有充分证据支持 temporal-only？

没有。旧 time 33 条中，实际片段复核后仍可标 time 的只是一部分；同一批旧 time 还包含 legal_reference、quantity、manner、other、purpose 和 overlap-only。更重要的是，time-like 短语也出现在新未匹配预测中，例如 only for part of the calendar year、prior、by official notice、before carrying out an annual adjustment。因此 temporal-only 既覆盖不全，也不是天然的 precision guard。

### 6.2 R_C 收益是否分散在多个语义类型？

是。52 条实际新增命中中，多标签计数为 time 14、legal_reference 12、purpose 10、quantity 8、manner 8、other 25、exclusivity 2、undetermined 1。legal reference recovery 明确存在，原 taxonomy 的 legal reference=0 结论必须撤回。

### 6.3 主要失败更接近类型选择、作用范围、短语完整性，还是其他问题？

不是单一类型选择问题。观察到的组合是：(a) 长 Gold 下只恢复局部内容或只取得 overlap，作用范围和短语完整性不足；(b) 孤立 cue-only 和其他字段内容被重抽为 constraint，造成 precision 损失；(c) FP 既有 span 替换也有净增加，不能只看新 span 数量；(d) B→D 还伴随 actor 侧 regression / 不稳定表型。没有证据支持只校正类型标签或只加 temporal guard 就能得到明确净收益。

### 6.4 当前证据是否足以提出一个有明确目标的小改动？

不足以。该面板是单次运行的开发/探索证据，不是独立盲测，也没有预先冻结的最小有用增益、允许退步幅度或成功/停止标准。一个最小改动需要同时说明目标语义类型、作用范围和短语完整性、FP 容忍度、actor 侧保护；当前证据无法识别哪一项单一改动会改善净价值。继续跑更多 arms 只会增加调用，不会自动获得识别性。

## 7. 最终建议

**B. 证据不足或收益不值得继续追。** 建议以 B 为本轮研究参照收口，保留旧 R_C 的混合结果，不强行创造新模块。不要默认安排 750 次，也不要自动改成 300/450 次。

## 8. 未决事项与边界

- Human adjudication of the AI semantic labels and disputed scope cases remains pending; this report is not human-approved.
- The coarse Gold merges spans per sentence and the evaluator uses any non-empty character intersection; full-phrase quality must be assessed separately from the frozen metric.
- The six B→D empty-Gold actor regressions are an observed phenotype; internal model cause is not identified.
- Run-to-run and service-side variance cannot be estimated from this single panel.
- 本报告和同目录 JSON 都不改变 Gold、评价器、历史预测和原 taxonomy；所有语义标签均为 AI 离线复核意见，不是 human-approved。
