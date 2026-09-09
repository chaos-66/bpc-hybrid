# Stage 3 Oracle：正确规则下检查器能力（零 API）

**run_id**：`s3_oracle_gold_rules_v1`
**状态**：`Oracle isolation run on the frozen development evaluation surface; NOT the formal S3.7 main table (S2.13 and S3.4-S3.6 formal promotion still pending)`

## 问题

给检查器**正确的规则**（用户人工确认的 74 句 / 92 条规范 → 正式 Gold Rule Records），它能找出多少流程错误？本报告把 Stage 2 误差从链路中移除，只测 Stage 3 本身。

## 规则来源

- Gold Rule Records：`data/gold/stage3/gdpr7_gold_rule_records_v1.json` sha256 `7cf896abdb6e420e46efd297a8e183bcdc4c15834aa9567eb88d1af60eec627a`
- Oracle 胶囊：`data/predictions/gdpr7_human_rule_record_v1/predictions.json` sha256 `9d86e1b4360a8ef2d9acfacdda4cd3b5d7e2e35f7f3de68eeebaa0a793432500`
- 92 条规范全部进入检查器；每条规范保留自己的情态标签（不是 obligation-only 投影）。

## 1. 原三类（33 条人工 violation Gold，7 个冻结流程）

| 规则来源 | macro-F1 | exact | detected | missed | wrong-type | unobservable |
|---|---:|---:|---:|---:|---:|---:|
| oracle | 0.3333 | 0.3333 | 11 | 22 | 0 | 11 |
| oracle_obligation_only | 0.3175 | 0.3030 | 10 | 23 | 0 | 11 |
| reference | 0.3889 | 0.3636 | 12 | 21 | 0 | 10 |

### 逐类型（oracle，全部情态）

| 类型 | support | P | R | F1 |
|---|---:|---:|---:|---:|
| missing_action | 11 | 1.000 | 1.000 | 1.000 |
| incorrect_actor | 11 | 0.000 | 0.000 | 0.000 |
| out_of_order | 11 | 0.000 | 0.000 | 0.000 |

### oracle − reference

| 指标 | Δ |
|---|---:|
| macro_f1 | -0.0556 |
| exact_type_accuracy | -0.0303 |
| detected | -1.0000 |
| missed | +1.0000 |
| wrong_type | +0.0000 |
| unobservable | +1.0000 |
| per_type_f1.missing_action | +0.0000 |
| per_type_f1.incorrect_actor | -0.1667 |
| per_type_f1.out_of_order | +0.0000 |

## 1b. 为什么 incorrect_actor 不可观察（Definition 6 动作映射诊断）

| 规则 | 策略 | rule actions | 映射>gamma | actor-action 对 | 对映射>gamma | Def6 可观察 |
|---|---|---:|---:|---:|---:|---|
| article15 | oracle_all_modalities | 14 | 1 | 19 | 1 | yes |
| article16 | oracle_all_modalities | 3 | 0 | 2 | 0 | no |
| article17 | oracle_all_modalities | 4 | 0 | 3 | 0 | no |
| article20 | oracle_all_modalities | 5 | 0 | 3 | 0 | no |
| article22 | oracle_all_modalities | 3 | 0 | 1 | 0 | no |
| article33 | oracle_all_modalities | 10 | 1 | 3 | 0 | no |
| article34 | oracle_all_modalities | 7 | 0 | 3 | 0 | no |
| article6 | oracle_all_modalities | 10 | 0 | 2 | 0 | no |
| article7 | oracle_all_modalities | 7 | 1 | 2 | 0 | no |
| article15 | oracle_obligation_only | 2 | 0 | 1 | 0 | no |
| article16 | oracle_obligation_only | 0 | 0 | 0 | 0 | no |
| article17 | oracle_obligation_only | 3 | 0 | 2 | 0 | no |
| article20 | oracle_obligation_only | 1 | 0 | 0 | 0 | no |
| article22 | oracle_obligation_only | 1 | 0 | 1 | 0 | no |
| article33 | oracle_obligation_only | 9 | 1 | 3 | 0 | no |
| article34 | oracle_obligation_only | 5 | 0 | 1 | 0 | no |
| article6 | oracle_obligation_only | 6 | 0 | 1 | 0 | no |
| article7 | oracle_obligation_only | 6 | 1 | 1 | 0 | no |
| article15 | reference | 13 | 2 | 13 | 2 | yes |
| article16 | reference | 2 | 1 | 2 | 1 | yes |
| article17 | reference | 7 | 0 | 7 | 0 | no |
| article20 | reference | 5 | 0 | 5 | 0 | no |
| article22 | reference | 6 | 1 | 6 | 1 | yes |
| article33 | reference | 10 | 1 | 10 | 1 | yes |
| article34 | reference | 7 | 0 | 7 | 0 | no |
| article6 | reference | 10 | 0 | 10 | 0 | no |
| article7 | reference | 8 | 0 | 7 | 0 | no |

> Definition 6（incorrect_actor）只有在“规则动作映射到流程动作且相似度 > gamma(0.8)”时才可观察。人工确认规则使用完整法律短语（例：`implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests`），其与流程活动标签的相似度低于阈值，因此该检查项在本数据上大多不可观察。这是**检查器输入口径**的局限（规则记录的动作粒度 vs 流程标签粒度），不是人工规则错误。

## 2. 四类扩展（40 个受控合成变体 + 40 个合规对照）

| 后端 | variant exact | macro | control FP rate | paired acc |
|---|---:|---:|---:|---:|
| Winter-style extension | 0.2250 | 0.3409 | 0.2500 | 0.1000 |
| Sun-style extension | 0.0250 | 0.0454 | 0.0000 | 0.0250 |
| BM25 extension | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| TF-IDF/SVD extension | 0.1250 | 0.2063 | 0.1000 | 0.1000 |

> 四类扩展是**合成受控面板**（development-only）；Winter/Sun 原论文未定义这四类，一律写 `Winter-style extension` / `Sun-style extension`。它提供合规对照，是唯一能测误报（FP）的面板。

### 2b. 面板变体与人工规则的绑定覆盖

| 后端 | 唯一命中 | 多义取首 | 人工规则未覆盖 | 未覆盖变体 |
|---|---:|---:|---:|---|
| winter | 20 | 9 | 11 | syn_v2_constraint_violated_02, syn_v2_exception_not_handled_07, syn_v2_exception_not_handled_08, syn_v2_exception_not_handled_09 … |
| sun | 20 | 9 | 11 | syn_v2_constraint_violated_02, syn_v2_exception_not_handled_07, syn_v2_exception_not_handled_08, syn_v2_exception_not_handled_09 … |
| bm25 | 20 | 9 | 11 | syn_v2_constraint_violated_02, syn_v2_exception_not_handled_07, syn_v2_exception_not_handled_08, syn_v2_exception_not_handled_09 … |
| tfidf_svd | 20 | 9 | 11 | syn_v2_constraint_violated_02, syn_v2_exception_not_handled_07, syn_v2_exception_not_handled_08, syn_v2_exception_not_handled_09 … |

> 该面板按 **dev 抽取的六要素读法**构造变体，因此有变体作用于人工确认规则**并未标注**的字段（如某些句子的 constraint/exception 为空），此时 Oracle 臂不猜、不补，直接记为未覆盖并计入分母。这进一步说明：四类面板数字对人工规则臂是**偏差比较面**，不能用来判断人工规则的质量。

## 3. 依赖与边界

- `s2_13_stage2_freeze` = `blocked on S2.12 API arms (not required for this isolation run)`
- `s3_4_s3_6_formal_promotion` = `pending`
- `gold_rule_records_published` = `True`
- `formal_s3_7_authorization` = `not granted; this run is an isolation evaluation`

## 4. 复现

```powershell
python formal_experiment/scripts/run_s3_oracle_gold_rules_v1.py
```

零 LLM/API/网络；未修改 Gold、阈值、流程或既有预测。
