# SEP-C3 固定原始响应后处理归因 v1（离线，零新增 API）

> 状态：`offline_attribution_only_no_api_no_rerun`。本报告只对已保存 raw 响应做确定性离线重放；不生成模型响应、不修改处理逻辑/阈值、不覆盖历史结果。

## 0. 结论摘要

### 已确认 / 不能归因 / 具体缺陷

**已确认**
- 旧 v6 与 111 的 JSON/fence 解析失败均为 0；旧版 43/150 带 Markdown fence、107/150 裸 JSON，111 为 150/150 裸 JSON；fence 差异不进入五字段 F1。
- 输出适配器对旧 v6 的 actor span 数、坐标和文本无增删移；111 的 relay 嵌套形状必须经 adapter 展开，关闭 adapter 会让 canonicalizer 丢弃 742 个 field span 和 247 条边，但 validator 观察到 0 条 invalid，得到 0 分。这是接口依赖，不是 adapter 的语义抽取贡献。
- canonicalizer 只做坐标重锚、span/clause/edge 删除，不新增 actor。旧 v6 actor span 87→82（删 5、重锚 60），111 actor span 136→130（删 6、重锚 104）；coordinate 与清理在实现中耦合，不能分别虚构独立 F1 贡献。
- 111 最终 canonical actor FP=84；由于后处理从不新增 actor，这 84 个 FP 全部已在原始响应中存在。旧 v6 对应 final actor FP=35。actor 过抽首先是模型输出/prompt 组合问题，不是后处理新增。
- 111 保存路径使用 adapter+canonicalizer、未启用最终 canonical validator；最终 validator 会拒绝 1/150 条（estg_000861，order_relations[0].evidence 被模型输出为 object 而非 array）。完整链分数为 0.725473（149/150 成功）；已保存路径分数为 0.726206（150/150 request_status=ok，但 1 条 validator-invalid observed）。

**不能归因**
- 不能根据 raw→canonical actor 总数下降 5/6 就说后处理修正了语义 actor 误抽；其中多数是坐标重锚，删除项还包含 1 个 exact text 命中 Gold 的跨版本共同删除样本 estg_000103。
- 不能把关闭坐标重锚后的接口失效（149/150 validator rejected 或新 111 关闭 adapter 后 0 分）解释成语义能力来自后处理；这些是 schema/接口依赖造成的整条拒绝或空输出。
- 现有证据不能把 actor 过抽归因到某一句 E/S/J 文本，也不能隔离坐标重锚、span 删除和 edge 清理各自对 F1 的独立贡献。
- 不能把 0.726206 写成完整后处理链分数；它是当前 modular runner 保存路径分数，完整 validator 链为 0.725473。

**具体后处理缺陷定位**
- 具体路径差异：scripts/run_sep_c3_modular_ablation_v1.py 使用 run_barrientos_ablation_suite_v2.parse_same_response/_prediction_row，只执行 relay adapter + span canonicalizer，没有调用 stage2_canonical.validate_canonical；scripts/run_d_full_postprocessing_ablation_v1.py 的完整链会调用该 validator。
- 证据：111 重放中 estg_000861 在 adapter+canonicalizer 后 schema_valid=true、cross_field_valid=false，错误为 clauses[0].order_relations[0].evidence must be an array；保存路径 request_status=ok，完整链应整条拒绝。旧 v6 0 条 validator-invalid，故两条路径同分。
- 本轮只交付定位证据，不修改处理链、补跑或覆盖已保存预测。

## 1. 同口径后处理结果表

主指标为 coarse sentence-level actor/action/condition/constraint/exception 五字段 F1 算术平均；每行均保留 150 条分母。`validator invalid observed` 是最终验证观察到但未必被拒绝的记录数。

| 条件 | arm | 成功/失败 | validator invalid observed | actor | action | condition | constraint | exception | mean F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 仅 JSON/fence + 最终验证门（无 adapter/canonicalizer） | 旧 v6 D-full-0813 | 1/149 | 149 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 仅 JSON/fence + 最终验证门（无 adapter/canonicalizer） | 新版 modular_v1 111 | 1/149 | 149 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 有输出适配器、无坐标重锚，经最终验证门（=完整链去 canonicalizer） | 旧 v6 D-full-0813 | 1/149 | 149 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 有输出适配器、无坐标重锚，经最终验证门（=完整链去 canonicalizer） | 新版 modular_v1 111 | 1/149 | 149 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| adapter+canonicalizer、未启用最终验证门（111 已保存路径） | 旧 v6 D-full-0813 | 150/0 | 0 | 0.708309 | 0.918501 | 0.840531 | 0.757812 | 0.700000 | 0.785030 |
| adapter+canonicalizer、未启用最终验证门（111 已保存路径） | 新版 modular_v1 111 | 150/0 | 1 | 0.515814 | 0.928697 | 0.813301 | 0.741638 | 0.631579 | 0.726206 |
| adapter+canonicalizer+最终 schema/cross-field 验证（完整链） | 旧 v6 D-full-0813 | 150/0 | 0 | 0.708309 | 0.918501 | 0.840531 | 0.757812 | 0.700000 | 0.785030 |
| adapter+canonicalizer+最终 schema/cross-field 验证（完整链） | 新版 modular_v1 111 | 149/1 | 1 | 0.518722 | 0.927192 | 0.808236 | 0.741638 | 0.631579 | 0.725473 |
| 完整链去输出适配器（接口依赖对照） | 旧 v6 D-full-0813 | 150/0 | 0 | 0.708309 | 0.918501 | 0.840531 | 0.757812 | 0.700000 | 0.785030 |
| 完整链去输出适配器（接口依赖对照） | 新版 modular_v1 111 | 150/0 | 0 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |

## 2. actor 变化追踪

| arm | raw actor spans | after adapter | after canonicalizer | saved/final | raw→adapter add/remove/reanchor | adapter→canonicalizer add/remove/reanchor | final actor FP | raw actor FP diagnostic |
|---|---:|---:|---:|---:|---|---|---:|---:|
| 旧 v6 D-full-0813 | 87 | 87 | 82 | 82 | 0/0/0 | 0/5/60 | 35 | 39 |
| 新版 modular_v1 111 | 136 | 136 | 130 | 130 | 0/0/0 | 0/6/104 | 84 | 89 |

`raw actor FP diagnostic` = 最终 canonical actor FP + 被 canonicalizer 删除且其 exact text 不在 Gold actor 文本集中的 span 数；仅作追踪，不是新的主评价指标。

## 3. 代表性样本

- `estg_000028`：Gold actors=[]；旧 v6 raw/adapter/canonical/saved actors=[] / [] / [] / []；111 raw/adapter/canonical/saved actors=['The income', 'the tax to be assessed'] / ['The income', 'the tax to be assessed'] / ['The income', 'the tax to be assessed'] / ['The income', 'the tax to be assessed']。
- `estg_000037`：Gold actors=['the fund must be subject to state supervision;\nbb) the fund']；旧 v6 raw/adapter/canonical/saved actors=['the insured person', 'the fund', 'the fund'] / ['the insured person', 'the fund', 'the fund'] / ['the insured person', 'the fund', 'the fund'] / ['the insured person', 'the fund', 'the fund']；111 raw/adapter/canonical/saved actors=['business expenses', 'the fund', 'the fund'] / ['business expenses', 'the fund', 'the fund'] / ['business expenses', 'the fund'] / ['business expenses', 'the fund']。
- `estg_000103`：Gold actors=['the tax office']；旧 v6 raw/adapter/canonical/saved actors=['the tax office'] / ['the tax office'] / [] / []；111 raw/adapter/canonical/saved actors=['the tax office'] / ['the tax office'] / [] / []。
- `estg_000861`：Gold actors=[]；旧 v6 raw/adapter/canonical/saved actors=['the liquidation gain'] / ['the liquidation gain'] / ['the liquidation gain'] / ['the liquidation gain']；111 raw/adapter/canonical/saved actors=['a taxpayer falling under Section 7(3) who has resolved to dissolve'] / ['a taxpayer falling under Section 7(3) who has resolved to dissolve'] / ['a taxpayer falling under Section 7(3) who has resolved to dissolve'] / ['a taxpayer falling under Section 7(3) who has resolved to dissolve']。
  111 最终 validator invalid：`clauses[0].order_relations[0].evidence must be an array`；保存路径 request_status=`ok`。

## 4. 归因限制

- raw actor span 语义 FP 追踪对 canonicalizer 删除项使用 exact text 与 Gold actor 文本集的诊断匹配，不是独立的新 evaluator；主指标仍只使用现有 coarse evaluator 对成功 canonical 行的评分。
- 旧 v6 与 111 不是同一生成批次，无法排除 provider 端漂移；本报告不做单句 prompt 因果判断。
- 所有 150 条始终保留在分母；被 validator 拒绝或解析失败的记录按空预测处理。

## 5. 输入与复现

- `input`：`D:\Paper\experiment\bpc-hybrid\formal_experiment\data\input\estg150_formal_inference_input_v2.json`；SHA-256 `52a73aa1109970b6c4fbc17214b0828ed0dd64b330001e884cdc803b1ce81dc2`
- `gold`：`D:\Paper\experiment\bpc-hybrid\formal_experiment\data\gold\stage2\estg150_formal_gold_v1.json`；SHA-256 `c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100`
- `old_raw`：`D:\Paper\experiment\bpc-hybrid\formal_experiment\outputs\development\barrientos_ablation_suite_v2\D-full-0813\repeat-01\raw_responses.jsonl`；SHA-256 `b45ea6ef530c80162bd2b60fb7877c8728beabcdecc772fe8ff9e338d3bf5dce`
- `old_canonical_predictions`：`D:\Paper\experiment\bpc-hybrid\formal_experiment\outputs\development\barrientos_ablation_suite_v2\D-full-0813\repeat-01\canonical_predictions.jsonl`；SHA-256 `2dc036c3c72f54e194ad9882aac5b78f2fd0e0a7f9fbdf44dc73baa31ce23195`
- `new_raw`：`D:\Paper\experiment\bpc-hybrid\formal_experiment\outputs\development\sep_c3_modular_ablation_v1\111\repeat-01\raw_responses.jsonl`；SHA-256 `6f9f8023032f12697aeec20ac87d962d599889da26c20bffcfe901c20260b129`
- `new_canonical_predictions`：`D:\Paper\experiment\bpc-hybrid\formal_experiment\outputs\development\sep_c3_modular_ablation_v1\111\repeat-01\canonical_predictions.jsonl`；SHA-256 `abf05abcd4d058f285d726e16a1b02eeffb174897bdca48f4876c8d32714d857`

分析脚本：`scripts/analyze_sep_c3_postprocessing_attribution_v1.py`
