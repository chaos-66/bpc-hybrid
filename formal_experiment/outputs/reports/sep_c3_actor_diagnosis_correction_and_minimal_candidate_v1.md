# SEP-C3 actor 最小修复候选与诊断修正 v1（离线，零 API）

- 状态：`offline_candidate_ready_not_enabled`；真实 API=0，未补跑、未重试、未新增模型推理。
- 默认版本不变：旧 v6 `prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md` 仍是默认 Direct-LLM prompt。
- 本轮没有启用候选、没有修改其他字段规则、没有调整示例数量、没有重写 E、没有改 Gold/evaluator/后处理。
- 机器可核对证据：
  - `outputs/reports/sep_c3_actor_diagnosis_recompute_v1.json`
  - `outputs/reports/sep_c3_actor_fix_candidate_offline_check_v1.json`
- 候选文件：
  - `prompts/sun_compat/direct_llm_sun_record_prompt_v6_actor_fix_candidate_v1_2026_09_16.md`

## 1. 修正后的简短诊断

### 1.1 已确认事实

按当前同一 coarse 五字段 mean F1 口径，从已保存 `canonical_predictions.jsonl` 重算旧版 2026-08-30 factorial 结果，得到：

| arm | mean F1 | actor F1 | action F1 | condition F1 | constraint F1 | exception F1 |
|---|---:|---:|---:|---:|---:|---:|
| D-full-0813 | 0.785030442 | 0.708309 | 0.918501 | 0.840531 | 0.757812 | 0.700000 |
| D-no-semantic-examples-0813 | 0.769143182 | 0.569676 | 0.912217 | 0.865155 | 0.761826 | 0.736842 |
| D-no-semantic-guidance-0813 | 0.803302330 | 0.763666 | 0.885487 | 0.844649 | 0.777148 | 0.745562 |
| D-no-explicit-json-contract-0813 | 0.807580535 | 0.697793 | 0.940069 | 0.818713 | 0.763146 | 0.818182 |

主要含义：

1. 旧版已经不是完整版一定最高：旧版删 S（`D-no-semantic-guidance-0813`）=0.803302、删 J（`D-no-explicit-json-contract-0813`）=0.807581，均高于旧版 full=0.785030。因此，当前新版删除 S/J 后分数更高的现象，不能全部归因于这次精简；旧版已经存在类似方向。
2. 旧版删 E（`D-no-semantic-examples-0813`）=0.769143，低于旧版 full，支持保留示例这一判断。但该臂的预声明操作是把全部六条语义 input-output 示例替换为一条非语义 key/type 模板，不是只删除完整 JSON 形式。示例的语义内容、答题示范和 JSON shape 同时变化，所以不能直接证明完整 JSON 形式是旧版 E 唯一有效原因。
3. 旧版 factorial 是 2026-08-30 批次、从旧 v6 做单因素修改；当前 modular_v1 是 2026-09-15 批次、整体压缩并重排 S/E/J，且删除范围和组合方式不同：
   - 旧 `D-no-semantic-guidance`：只删规则 9-19、25-27，保留 1-8、20-24、user envelope 和六条示例。
   - 当前 101：删整个 S 模块。
   - 旧 `D-no-explicit-json-contract`：删规则 1-5 及 schema 相关表述。
   - 当前 110：删 J 模块（输出组织两条）。
   - 旧 D-full 的 E 是六条完整 JSON 示例；当前 111 是压缩 E。
   因此历史与当前批次、删除范围、示例形态都不同，不能跨版本做某一句导致某个 F1 差的直接单句因果归因。

从同一批实际文件重算的新版 111 诊断：

- 新版 111 actor 预测 span=130，未匹配预测 span（FP）=84；其中 72 个位于 Gold actor 为空的样本。
- 旧版 D-full-0813 actor 预测 span=82，FP=35；其中 31 个位于 Gold actor 为空的样本。
- 150 个样本中有 109 个 Gold actor 为空；111 在 56 个空 Gold 样本里有 actor 预测，旧版为 27 个。
- 新版 111 clauses 总数=228；旧版 D-full-0813=240。整体条款没有增加，因此新版 actor 过抽不能由 clauses 变多解释。
- 旧版 D-full-0813 在 `estg_000028` 的 actors 实际为 `[]`；新版 111 在该样本预测 `The income`、`the tax to be assessed`，011 只剩 `the tax to be assessed`。此前报告中旧版也抽出 The income 等的说法已修正。
- 旧版 D-full-0813 原始输出：107 条裸 JSON、43 条带 Markdown fence；新版 111：150 条裸 JSON、0 条 fence。parser 会先处理 fence，不能据此解释 F1 变化。

必须区分两种 actor 命中数：

| 版本 | actor 预测 span | 预测 span 命中数 `matched_predictions` | Gold span 命中数 `matched_ground_truth` | actor F1 |
|---|---:|---:|---:|---:|
| 旧 D-full-0813 | 82 | 47 | 38 | 0.708309 |
| 新版 111 | 130 | 46 | 39 | 0.515814 |

新版比旧版多 48 个 actor 预测 span，但预测 span 命中数反而少 1，Gold span 命中数只多 1。这个变化主要是 precision collapse（过抽），不是 recall 改善。后续诊断和报告不能把 `matched_predictions` 与 `matched_ground_truth` 混用。

### 1.2 主要怀疑

- actor 过抽是已确认的主要问题；其表现是大量额外 actor 集中在 Gold actor 为空的样本。
- 当前 S 相关规则集在 111 组合下可能放大 actor 过抽：101 删除 S 后 actor FP 从 84 降到 43。但 101 也丢失大量 constraint，因此不能把 S 整体删除当作修复方案。
- 当前压缩 E 可能同时改变字段边界和 actor 示范锚定；但旧版 factorial 只支持示例有作用，不足以证明完整 JSON 形式是唯一原因。
- 输出顺序、强调程度和批间生成波动仍可能参与，但现有单次已保存预测无法隔离。

### 1.3 尚不能确定

- 无法从现有单次消融中把 actor 过抽归因到某一条具体 S/E/J 文本。
- 旧 v6 没有同发布窗口的 EStG-150 重复运行，provider 端生成漂移不能严格排除。
- 删除 S/J 在旧版也更高，说明它们不是本轮精简新引入的唯一因素；当前模块组合的交互作用仍不能由历史 factorial 替代判断。
## 2. 本轮最小修复目标与候选范围

目标是减少 actor 过抽，同时保留合法 actor，不是让 actor 越删越少。候选只修改 actor 判定措辞和规则优先关系，具体约束：

- 基于旧 v6 复制；保留旧版六个示例及其内容。
- 保留 condition/constraint/exception 既有指导（规则 12-14、25-27 原样）。
- 保留输出接口、坐标规则、ID 规则、后处理和 evaluator。
- 只修改 system prompt 的规则 10、18、21；不修改 user prompt template，不修改示例，不新增示例。
- 候选未启用；旧 v6 默认不变。

## 3. 逐条修改前后对照

### 规则 10：先确认 role，再抽最小 mention

修改前（旧 v6）：actor 是最小的 explicit noun phrase or pronominal mention that bears or performs the norm；主语代词是真实 actor mention。

修改后（候选）：先按 `(a) 角色是否存在 -> (b) 最小 explicit 名词短语/代词 -> (c) 指代、被动、并列` 的顺序。明确写出：

- 不因某个词是名词、位于主语位置就自动当 actor；
- person、organization、institution 及其他 legal/compliance role 都可以是 eligible actor，不限定自然人；
- 没有明确 performer/norm bearer 时用 `actors=[]`，不从 affected object、recipient、amount、document、income、action 或 world knowledge 推断；
- 只有确认角色后，才抽取最小 explicit noun phrase/pronominal mention；
- 指代存在的 actor 不能被误写成 `actors=[]`，应保留 span 并按规则 17 标记 unresolved。

解决什么错误：针对看到主语/名词就填 actor、受事/对象/金额/文件被处理对象升为 actor、组织等合法 role 被漏掉、以及指代不明被错误处理为 actor 不存在。

### 规则 18：被动句没有明确执行者时不补 actor

修改前：passive no expressed performer 时不推断 actor，`actors=[]`，action map 的 actor_id=null；显式 by-phrase 例外。

修改后：保留原规则，并补写：

- 不因 passive verb 的 grammatical subject 或 affected object/recipient/amount/document 位于主语位置，就把它升为 actor；
- 不从 action 或 world knowledge 补出被省略的执行者。

解决什么错误：针对 Gold actor=[] 的被动/受事主语样本被预测出 `The income`、`the tax to be assessed`、`The report` 等 actor。

### 规则 21：确认 actor 身份后再做并列拆分

修改前：Store coordinated actors and actions as separate spans；不要在 scope ambiguous 时假设 cross-product。

修改后：先确认每个并列项是否 independently explicit performer/norm bearer；确认后才存为 separate spans。明确写出：

- 不因出现 and 就把所有并列名词拆成 actor；
- coordinated affected objects、amounts、documents 或其他 non-actor coordinates 留在各自字段。

解决什么错误：针对把所有并列名词都拆成 actor 的过抽，同时保留真正的并列执行者。
## 4. 实际 system / user 消息差异

离线用 `prompt_loader.load_prompt` 对旧 v6 和候选做了实际消息级比较，结果见 `outputs/reports/sep_c3_actor_fix_candidate_offline_check_v1.json`。

- 旧 v6 prompt SHA-256：`3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895`
- 候选 prompt SHA-256：`df8d4249821b8e66f14414adef725c7624731ccd18f3c46fb8b368e577d1f51e`
- `user_prompt_template_unchanged = true`
- `examples_block_unchanged = true`；六个示例的 JSON 内容逐字不变。
- 对同一 sample 渲染出的 user message，`rendered_user_message_unchanged = true`，用户消息 unified diff 为空。
- system message 的实际 unified diff 只涉及规则 10、18、21；完整 diff 保存在上述 JSON 的 `system_diff_unified`。除这三处外没有其他 system 差异。候选文件前部三个 HTML 注释行原有的行尾空白已归一化；这些行不进入 system/user 消息，不影响上述消息级比较。

## 5. 离线自我检查

### 5.1 规则自检

- 仍可能看到主语就填 actor 吗？候选明确要求先判断 role、后抽 mention，并写明 noun/主语位置本身不是 actor 依据；不把 subject 自动映射为 actor。
- 会误删合法代词、组织、规范承担者吗？候选保留 pronoun is a real actor mention when text presents it in that role，保留 organizations/institutions/legal roles；规则 17 未改，unresolved reference 继续保留 span。
- 与旧版示例、空数组约定、被动句规则冲突吗？六条示例逐字不变；规则 18 保留 `actors=[]` 和 by-phrase 例外；规则 10 允许定义主语不成为 actor。
- 会把指代不确定错误处理成 actor 不存在吗？规则 10(c) 明确禁止把 explicit actor mention with unresolved reference 转成 `actors=[]`；该情况按规则 17 保留并标记。
- 与 condition/constraint/exception 既有指导冲突吗？规则 12-14、25-27 未改；候选 diff 只动了 actor 相关规则。

### 5.2 独立合成例句的期望行为

以下只用于规则检查，不是模型实测结果，也不是正式 few-shot 示例：

| 合成例句 | 期望 actor | 依据 |
|---|---|---|
| The controller must notify the data subject. | `The controller` | 明确规范承担者 |
| The tax office shall refund the amount. | `The tax office` | organization 是合法 explicit role |
| The report must be filed within 72 hours. | `[]` | passive no expressed performer；报告是被处理对象 |
| The report must be filed by the controller. | `the controller` | 显式 by-phrase 提供执行者 |
| It may cover a shorter period if a business is opened. | `It` | 合法代词；reference unresolved 仍保留并标记 |
| The controller and the processor must notify the data subject. | `The controller`, `the processor` | 两个 coordinate 都 independently explicit actor |
| The controller must retain the report and the records. | `The controller` | 并列 affected objects 不拆成 actor |
| The income must be taxed. | `[]` | grammatical subject 且为被处理对象，不自动成为 actor |
| Personal data means information about a person. | `[]` | definition 的主语不必然为 norm bearer |
| They must notify the data subject. | `They` | role 存在但指代不明，不是 actor 不存在 |

候选示例解析检查：六个示例仍可被 `prompt_loader` 读取；六个 JSON 均通过 `validate_canonical` 的 schema 和 cross-field 检查。候选 system message 不包含 `estg_`、`Gold`、`synthetic_` 等按样本/gold 决定输出的 marker。

## 6. 未改变的条件与交付边界

- 旧 v6 仍是默认版本；候选未注册、未启用、未运行。
- 本轮真实 API=0；没有补跑、重试或新增模型推理。
- 未修改 Gold、evaluator、后处理、坐标规则、输出接口、其他字段规则、示例数量或消息顺序。
- 历史预测、metrics、manifest 未覆盖；旧版 factorial 和当前 modular 结果仍按原文件保留。
- 不宣称候选提升 F1；上述合成期望只是规则检查，不是实验结论。
- 若后续要验证，仍需用户另行授权真实调用，并使用同一冻结输入、Gold、evaluator 和采样参数。
