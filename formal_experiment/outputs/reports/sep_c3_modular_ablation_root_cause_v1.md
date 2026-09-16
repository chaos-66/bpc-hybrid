# SEP-C3 模块化 E/S/J 退步根因诊断 v1（离线，零 API）

- 状态：offline_diagnosis_only；真实 API=0，未补跑、未重试、未做 LLM 辅助分析、未新增模型推理。
- 默认版本不变：旧 v6 `prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md` 仍为默认 Direct-LLM prompt。
- 边界：本报告只诊断，不启用 `modular_v1`；不把两模块建议直接落成新 prompt；单次消融不写成某一句文本的因果结论。
- 主要依据：旧 D-full-0813 与 `modular_v1` 的 111/011/101/110 已保存 raw/canonical/ledger/manifest；冻结 Stage 2 Gold；`sep_c3_modular_evaluation.py`；Barrientos PDF 与 artifact prompts。

## 0. 结论摘要

1. Barrientos 原文的 FULL/NO-PATTERNS 不是本项目的 E/S/J 消融。原文只报告省略允许模式清单后模型频繁虚构不存在模式/命名不一致的定性观察；Table 5 的 Step 1 P/R/F1 是完整方法主结果，不是消融 F1。artifact 的 NO-PATTERNS 还同时删除了 Control-Flow Exclusivity Rule，剩余文本只是重编号，因此也不是纯词表单因素。本项目的 `barrientos_ablation_suite_v2` 是在我们自己的 runner、模型、任务和 evaluator 上做的借鉴实验，不是作者原消融。
2. 新版 111 从旧 v6 的 0.7850 降到 0.7262（five-field mean F1，-0.0588）。退步最大来源是 actor 过抽：旧 v6 actor F1=0.7083、82 个预测 span；111 actor F1=0.5158、130 个预测 span。actor 一项贡献了均值差的大约 65%。
3. actor 核心定义没有被压缩：旧 v6 第 10/18/21 条与 S 模块第 3/10/13 条语义基本一致。不能把退步归因于某句 actor 定义被压缩。现行证据是：S 模块在当前精简组合中伴随大量额外 actor；删除 S 后 actor 预测从 130 降到 89、actor F1 从 0.5158 升到 0.6757；但残余被动/受事主语错误仍在，且删除 S 会显著丢 constraint。
4. 删除 E/S/J 都比 111 高，但都没有恢复到旧 v6：011=0.7470、101=0.7611、110=0.7355，仍比旧 v6 低 0.0381/0.0240/0.0495。因此正确结论不是删模块更好，而是 `modular_v1` 的模块职责和组合方式当前有冲突；删模块只暴露了部分冲突。
5. 推荐：J 降为所有版本共有的最低输出约定，不再作为实验因素；保留 S 与 E 两个可消融因素（候选 B）。但当前 E 不能原样保留，必须重建为完整 JSON 示例；S 也要收窄 actor/边界规则并恢复旧版具体线索。不要为了凑两模块把 E 合并进 S，因为现有成对结果显示 E 和 S 的作用不同。
6. 本轮不宣布两模块已经更好；下一次只能在用户另行授权真实调用后，按预先声明的口径验证。

## 1. Barrientos 原文消融 vs 本项目实际消融

### 1.1 原文实际删除了什么、观察到了什么

| 项目 | 事实 | 来源 |
|---|---|---|
| 原文消融 | 省略 Controlled Vocabulary / explicitly list the allowed compliance patterns；观察模型频繁生成不存在的 pattern 和同一概念命名不一致 | `references/papers/Barrientos_2026_Impact_analysis.pdf` p.9 §5.1；提取文本 line 1145-1151 |
| 原文是否给消融 F1 | 没有。该段是定性观察，没有 P/R/F1、样本数或重复次数 | 同上；`barrientos_paper_ablation_preflight_v1.json` |
| artifact 对照 | `formalize_requirements_prompt_no_patterns.txt` 同时删除 44 项 Allowed Compliance Patterns 和 Control-Flow Exclusivity Rule；剩余 rule 仅重编号 3/4/5->1/2/3；仍保留 do NOT invent new patterns 但清单已不存在 | 两份 artifact prompt 直接 diff；preflight 已记录 |
| Table 5 是什么 | 完整方法在 Emergencies / SIM Card / Blood Donation 三数据上的 Step 1/2/3 主评价。Step 1 Formalization 的 Precondition/Norm F1 约为 0.83-1.00（如 Emergencies precondition 0.94、norm 0.91；Blood Donation precondition 0.90、norm 1.00），不是模块贡献 | PDF p.11 Table 5 |

### 1.2 本项目 `barrientos_ablation_suite` 到底是什么

- 它是我们的借鉴/适配实验，不是作者原消融：数据、runner、模型（论文 GPT-4.1，我们 DeepSeek-V4-Pro-0813）、输出 schema、evaluator 都不同。
- `BARR-FULL` 使用作者原始 prompt，但在我们 runner 和 evaluator 下跑 36 条 Barrientos 记录；不是论文复现的精确结果。
- `OURS-FULL` / `OURS-BARRIENTOS-MODULE` 是我们自己的任务/格式与 Barrientos 风格模块互换，不是作者 FULL/NO-PATTERNS。
- `D-full-0813`、`D-no-fewshot-0813`、`D-minimal-0813`、`D-barrientos-style-0813` 是 EStG-150 上我们的 prompt/few-shot 模块，不是 Barrientos 消融。
- 作者原 FULL/NO-PATTERNS 的真实运行在本项目未执行；只有 `barrientos_paper_ablation_preflight_v1` 的 0-call 准备，且该计划后来已被研究定位撤回，不得当作已完成消融。
- 汇报时必须按任务/output/evaluator 分表：作者原生任务、我们原生任务、共享三类 modality 目标，不能跨表比 F1。

### 1.3 作者任务/输出/删除信息 vs 我们的 E/S/J

| 维度 | Barrientos 原文 | 本项目 |
|---|---|---|
| 任务 | 把自然语言合规需求形式化为 precondition/norms/temporal_validity，并比较前后版本 | 从 EStG 句子抽取 Sun-compatible 五 span 字段 |
| 输出 | JSON：id/precondition/norms/action/dimension/compliance_pattern/temporal_validity | JSON：clauses/modality/actor/action/condition/constraint/exception/offsets |
| 消融删除 | allowed pattern whitelist + artifact 里的 control-flow exclusivity | E=示例模块，S=语义规则模块，J=输出组织模块 |
| 可比性 | 不是同一任务、同一评价单位 | S/E/J 是我们自己的消融因素 |

结论：不能用 Barrientos 删除 pattern 清单有效直接支持删除我们的 S 更好；两者删除内容、任务和观察指标都不同。

## 2. 新旧实际发送内容与处理方式核对

### 2.1 请求、模型、采样、截断、后处理可比性

- 已按当前 prompt 重放 request body，并和已保存 raw 的 `request_body_sha256` 对齐：旧 D-full 与 111 都精确匹配，说明保存的请求就是当前 prompt 渲染出来的实际请求体。
- 模型与采样：均为 `deepseek-v4-pro`，记录发布窗口 `DeepSeek-V4-Pro-0813`，`temperature=0.0`、`top_p=1.0`、`max_tokens=4096`、`stream=False`、`thinking=disabled`、`retry=0`。
- 输入：同为冻结 EStG-150 `data/input/estg150_formal_inference_input_v2.json`；Gold 同为 `data/gold/stage2/estg150_formal_gold_v1.json`。
- 评价：旧版不是直接拿它原来的 `evaluation.json`（那个是六字段 overall micro F1=0.7719）和新版比较；本次诊断把旧 D-full 和 111/011/101/110 都用同一个 `evaluate_coarse` 重评。主指标为 `coarse_five_field_mean_f1`，即 actor/action/condition/constraint/exception 五项 F1 的算术平均；`coarse_five_field_micro` 和 `modality_label_macro_f1` 只作旁证，不能混进主指标。
- 后处理：新版 runner 直接复用旧 `run_barrientos_ablation_suite_v2` 的 `parse_same_response`、adapter、`canonicalize_record_coordinates` 和 `_prediction_row`；新旧使用同一固定 evaluator。旧版 raw 有 43/150 带 Markdown fence（107/150 为裸 JSON），新版四臂均为 150/150 bare JSON；parser 会先去 fence，再 canonicalize，因此 fence 差异不进入 F1。
- 生成波动：旧 v6 在本项目没有同一 0813 发布窗口的 EStG-150 重复运行；因此不能完全排除 provider 端漂移。可用的 Barrientos 36 条 OURS-FULL 五次重复整体 F1 约 0.874±0.003，说明 temperature=0 下仍有小波动，但与本轮 actor 0.19 F1 差和大量成对样本差异相比量级较小，只作旁证，不能代替 EStG 重复。

### 2.2 长度和实际内容变化

| 内容 | 旧 v6 实际发送 | 新 111 实际发送 |
|---|---:|---:|
| system 平均字符 | 6,172 | 5,562 |
| user 平均字符 | 9,942 | 2,782 |
| 合计平均字符 | 16,114 | 8,344（-48.2%） |
| 六条完整 JSON 示例 | 有，约 9k 字符 | 无 |
| 五条紧凑示例 | 无 | 有，约 2.3k 字符 |
| 具体约束/条件线索清单 | 旧 rule 25-27 | 合并进 S rule 6/8，删掉部分具体线索 |
| 最终自检清单 | 旧 rule 24 | 无独立清单 |
| JSON 输出纪律 | 旧 rule 1-5 + 用户模板 | common 的接口描述 + J 两条 |

逐项实质变化：

| 类别 | 旧内容 | 新内容 | 可能影响字段 | 现成结果 |
|---|---|---|---|---|
| 纯去重/搬移 | 旧 rule 6-23 分散在 system | 基本原义搬入 S rule 1-15，坐标/ID 规则搬到 common | 理论上不改变语义 | S 删除后 constraint 明显掉，说明 S 并非纯重复 |
| 删具体识别线索 | 旧 rule 25 明列 legal references / within N / at least / purpose / only；旧 rule 27 明列 if/when/unless/provided that/to the extent that | S rule 6 只保留功能分类和 include its marker；S rule 5 只保留通用定义 | constraint、condition | 111 constraint 179 span vs 旧 254；111 condition miss 29、FP 样本 19 |
| 删完整输出示例 | 六条完整 JSON，含 top-level/空数组/坐标/method/validation；示例 5 专门演示 legal-reference constraint | 五条 bullet 摘要，无完整 JSON，无 legal-reference constraint 示例 | actor、constraint、exception、action | 旧 factorial 中把六示例换成纯结构模板，actor F1 -0.1317；新版 111 actor 也大幅下降 |
| 示例增删 | 示例 1/2/3/4/6 的完整版本 | E1-E5 压缩版；无示例 5 | constraint、边界控制 | 111 出现了条件漏抽、约束 span 定位变化 |
| 指令顺序/强调 | 输出纪律在前，语义规则中段，约束线索在最后强调；用户模板有 Return complete canonical JSON 和示例说明 | common 在前，S 在中，J 在 system 末尾，E 在 user 末尾；无独立 Return 前导 | 所有字段，尤其输出形式 | raw bare-JSON 反而 111 150/150，不能把 fence 说成退步原因 |
| 精确输出约束改写 | exactly these top-level keys and no others | common 写 required fields，J 只写 bare JSON/完整对象 | schema/format | 新版原始 bare-JSON 仍 150/150；J 删除后仍 150/150 |
| 语义组合变化 | 旧版为长 system + 六完整示例；核心 actor 定义完整 | actor 定义几乎逐句相同；变化在示例形态、线索清单、顺序和组合长度 | actor 等 | 不能归因于 actor 定义被压缩；主因需看示例/组合与生成波动 |

关键反例：旧 v6 第 10 条和新 S 第 3 条的 actor 定义几乎逐句一致；旧第 18 条和新第 10 条的 passive 规则也一致；旧第 21 条和新第 13 条的 coordination 规则一致。故 actor 定义被压缩不是已确认原因。

## 3. 指标与逐字段错误定位

### 3.1 主表（同一 evaluator，five-field mean F1）

| arm | mean F1 | micro F1 | actor F1 | action F1 | condition F1 | constraint F1 | exception F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| old v6 D-full-0813 | 0.7850 | 0.8224 | 0.7083 | 0.9185 | 0.8405 | 0.7578 | 0.7000 |
| 111 | 0.7262 | 0.7902 | 0.5158 | 0.9287 | 0.8133 | 0.7416 | 0.6316 |
| 011（删 E） | 0.7470 | 0.8032 | 0.5132 | 0.9128 | 0.8306 | 0.7723 | 0.7059 |
| 101（删 S） | 0.7611 | 0.8144 | 0.6757 | 0.9285 | 0.8468 | 0.6876 | 0.6667 |
| 110（删 J） | 0.7355 | 0.7970 | 0.4770 | 0.9250 | 0.8226 | 0.7770 | 0.6761 |

单字段对均值差的贡献：

| 对比 | actor | action | condition | constraint | exception | mean 差 |
|---|---:|---:|---:|---:|---:|---:|
| old - 111 | +0.0385 | -0.0020 | +0.0054 | +0.0032 | +0.0137 | +0.0588 |
| 011 - 111 | -0.0005 | -0.0032 | +0.0035 | +0.0061 | +0.0149 | +0.0208 |
| 101 - 111 | +0.0320 | -0.0000 | +0.0067 | -0.0108 | +0.0070 | +0.0349 |
| 110 - 111 | -0.0078 | -0.0007 | +0.0019 | +0.0071 | +0.0089 | +0.0093 |

### 3.2 actor：过抽是主因，S 删除只修一部分

- 111 actor 预测 span 130 个，旧 v6 82 个；111 actor FP span 84 个，旧 35 个；111 有 63 个样本至少一个 actor FP，旧 30 个。
- 成对比较：111 相比旧 v6 有 43 个样本 actor span 更多，36 个样本只有 111 有额外 FP 而旧版没有，只有 1 个样本只有 111 命中、旧版没命中。这不是漏抽为主，是新增误报为主。
- 删除 S 后（101）actor 预测 89 个、FP 43 个；37 个样本从 111 有额外 FP 变成 101 没有额外 FP，同时有 7 个样本反向新增 FP；actor F1 从 0.5158 升到 0.6757。删除 S 能清掉相当一部分额外 actor，但不能全清，且 101 actor F1 仍低于旧版 0.7083。
- 删除 E（011）actor 预测 124 个、FP 80 个，和 111 几乎同级；E 不是 actor 过抽的主要来源。删除 J（110）actor 更差。
- 典型模式：
  - `estg_000293`：Gold actor=[]；111 预测 `The following income`；101 删除 S 后为 []。说明 S 相关规则集在当前组合下会推动把指代性主语/受事 NP 当成 actor。
  - `estg_000035`：Gold actor=[]；111 和 110 预测 `The excess of business receipts over business expenses`；old/011/101 均为 []。该例显示 E 与 S 的组合或生成波动可造成同类误报，不能只归因于 S 单独一句。
  - `estg_000028`：Gold actor=[]；旧 v6 D-full-0813 的 actors 实际为空；101/111/110 预测 `The income`、`the tax to be assessed`，011 只留下 `the tax to be assessed`。这是残余被动/受事主语错误，删除 S 和 E 都没有完全修掉，说明公共/示例层还需要更强的 passive/affected-object 边界约束。
  - `estg_000037`：Gold 有 `the fund`；111 只命中一个 fund 且添加 `business expenses`；101 能恢复两个 fund，但又添加 `business expenses` 和 `the insured person`。说明 S 删除也会恢复漏抽 actor，actor 不是单向 S 越多越坏。
- 现有分析报告用 `estg_000664` 作为删 S 修正 actor 的例子不够干净：101 仍预测 `Certain income...`、`taxation`、`the tax base or the tax`，只去掉了 `The following`。因此应写成 S 删除能减少部分 actor FP，不能写成删 S 修复该类全部 actor 错误。

### 3.3 condition / constraint / exception

- condition：111 miss 29、旧 27；111 的额外 FP 样本 19、旧 12。011 删除 E 后，相对 111 多恢复 11 个 condition 命中、少 2 个命中，condition F1 +0.0173。代表例 `estg_000028`：Gold condition=`when taking into account the converted income`；111 condition=[]；011 恢复该 span。
- constraint：111 预测 179、命中 94、miss 41；旧预测 254、命中 106、miss 29。新版 FP 更少（37 vs 68），但 recall 更低。101 删除 S 后丢了 18 个 111 本来命中的 constraint，只有 2 个反向恢复，constraint F1 -0.0541。代表例 `estg_000028`：Gold 含 `at the tax rate...` 与 `than that which...`；111 两个都在；101 constraint=[]。说明 S 确实携带 constraint 识别/定位信号，不能永久删除。
- exception：111 预测 8、命中 6，旧预测 9、命中 7；011 删除 E 去掉 2 个 exception FP 且保留 6 个命中，exception F1 +0.0743。代表例 `estg_000210`：Gold exception=`excluding the generation of electrical energy, gas or heat`；111 exception=[]；011 恢复。但 exception 样本量只有 11，结论强度有限。
- action：111 F1=0.9287 略高于旧 0.9185；011/101/110 都略低于 111。E/S/J 的组合对 action 有正贡献，删除任一模块都不提升 action。

### 3.4 原始响应 vs canonical 后处理

- 直接解析 raw actor span：旧 v6 87->canonical 82；111 136->130；101 94->89。canonicalizer 只删/移少量 span，上述 actor 过抽在 raw 模型输出中已经存在，不是后处理新增。
- 旧版 raw 有 43/150 Markdown fence；新版四臂全部 150/150 bare JSON。旧版 parser 去 fence 后正常，新版 raw 格式优势不改变主 F1。
- 因此本轮未发现退步来自后处理差异的证据；错误主要来自模型输出与 prompt 组合。

## 4. 为什么精简后退步，为什么删除模块反而更高

### 4.1 精简后退步的原因排序

1. 已确认主因：actor 过抽。111 新增 48 个 actor span，其中 84 个是 FP；旧版新命中只有 1 个成对样本。actor 单项解释了均值差的约 65%。因 actor 核心定义未变，不能归因于某句 actor 定义压缩。
2. 有成对案例支持的主要怀疑：E 的压缩示例改变了字段边界和输出风格。新版示例从六条完整 JSON 变成五条 bullet，删除了 legal-reference constraint 示例和完整 JSON 形状。结果是 111 constraint 预测明显少于旧版、condition/exception 出现漏抽；011 删除 E 后 condition/exception 恢复、constraint F1 +0.0307。但 E 同时保住 action，因此 E 不是没用，而是当前实现方式造成偏置。
3. 有成对案例支持的主要怀疑：S 在当前精简组合中放大了 actor/condition 错误，但保留了 constraint 线索。101 删除 S 后 actor F1 +0.1599、condition F1 +0.0335，可 constraint F1 -0.0541。说明 S 内部存在字段间冲突，不能整体判有效或无效。
4. J 当前没有主指标增量。110 删除 J 后 mean +0.0093，低于预先声明的 0.01 贡献阈值；raw bare-JSON 仍 150/150。J 只有输出组织信息，没有 actor/condition/constraint 语义信息，删除后的 F1 变化更可能是 prompt 长度/顺序/生成的间接效应，不能解释为 J 有语义贡献。
5. 尚不能确定的解释：指令顺序、强调程度和生成波动。新版把 J 放 system 末尾、把 E 放 user 末尾，删除了旧版最终自检和用户模板中的 Return complete canonical JSON。这些变化可能影响字段召回，但现有单次实验无法隔离。旧 v6 没有同发布窗口 EStG-150 重复，不能完全排除 provider 端漂移。

### 4.2 为什么删除模块反而更高

- 删除 E 更高：因为当前 E 的紧凑示例带来条件/约束/异常的漏抽和定位偏置；去掉它让 S 的通用规则和模型自身判断恢复了一部分 condition/exception。代价是 action 变差。
- 删除 S 更高：因为当前 S 放大了 actor 过抽和 condition 漏抽；去掉后 actor/condition 改善。代价是 constraint recall 大跌。
- 删除 J 更高一点：因为 J 只是两条输出组织句，主指标上没有有效语义增量，F1 变化低于 0.01 且不改变 bare-JSON 合法率。
- 但三个删除臂都仍低于旧 v6；所以删除模块更好只说明当前模块组合有冲突或冗余，不能说明删除后的 prompt 可以作为新默认。

## 5. 三模块还是两模块：建议

### 5.1 推荐候选 B，但要区分功能块和实验因素

- J 降为公共最低输出约定：把 return one bare JSON object 和 empty/uncertain 也返回完整对象放进 common，不再做 J=0/1 消融。依据：当前 J 删除 mean +0.0093，低于 0.01 阈值；raw bare-JSON 删除 J 后仍 150/150；J 没有语义内容。
- 保留 S 与 E 作为两个实验因素。这与用户建议两模块一致，但含义不是把三块文本删成两块，而是：J 是常量接口，S/E 是两个可检验因素。
- 不要现在直接启用两模块新 prompt。当前 E 是误导性的紧凑示例；必须先重建 E，再验证 S/E。旧 v6 继续保持默认。

### 5.2 J 是否提供公共接口之外的有效信息

- 当前没有可归因的有效语义信息。J 删掉后主指标反而 +0.0093，raw JSON 合法率不降；说明 common 已承担最低输出接口。
- 但 J 承担的功能不能直接删除：应把它并入 common，成为所有版本的固定约定，避免把一个只影响格式的开关混进语义消融。

### 5.3 E 是否提供 S 无法表达的示范，还是重复/误导

- E 有独立作用，但当前实现误导。旧 factorial 中把六条完整示例替换为结构模板后，actor F1 从 0.7083 降到约 0.5697（同 coarse 口径重评；原六字段 micro 口径下 actor Δ=-0.1317），说明示例对 actor 边界有独立价值。
- 新版紧凑 E 没有达到旧六示例的锚定效果：在都删除 S 的情况下，旧完整示例 actor F1=0.7637，而新版紧凑 E actor F1=0.6757。新版 E 还伴随 condition/constraint/exception 漏抽和定位问题。
- 因此不能把 E 合并进 S 后只留一个语义规则模块；那会失去规则文本和工作示例之间的独立对照，也无法隔离示例造成的字段偏置。E 应保留为独立实验因素，但必须重写。

### 5.4 S 哪些规则有效，哪些与错误有关

- 有效信号：S 是 constraint 的主要承载者。删除 S 后 constraint F1 从 0.7416 降到 0.6876，111 命中的 18 个 constraint 在 101 中消失。
- 与错误相关：S 删除后 actor 和 condition 明显改善。需要重点复查 actor/coordination/clause/字段边界相关规则的组合效应，而不是单独断言某一句有罪。单次消融不能证明具体哪一行是原因。
- 修复方向：S 应保留字段定义、范围、歧义、规范关系、约束线索，但收窄容易把语法主语/受事 NP 当 actor 的规则；增加明确的反例边界（passive 无执行者、受事/对象主语、the following、coordinated NP 不自动拆 actor）。同时恢复旧 rule 25-27 的具体 constraint/condition 线索。

### 5.5 合并到底解决什么问题

- 若把 E 合并进 S，只是把规则和示例放进同一个 prompt 文件，不能消除当前字段间冲突；还会让下一次实验无法判断改善来自规则还是示例。因此不推荐为凑数量而合并。
- 真正的两因素架构应是：common（含 J 的接口约定）+ S 规则 + E 示例，实验上只改变 S/E。这样既能减少 J 这个无效开关，又能保留 E/S 的独立可识别性。

## 6. 下一次最应该修的内容（按优先级，不整体重写）

P0. 重建 E 为完整 JSON 示例，不从当前 bullet 版微调。
- 恢复旧 v6 六条完整 JSON 示例的语义边界，尤其 legal-reference constraint 示例；全部示例保持 synthetic，不取自 Gold。
- 增加 actor 硬负例：passive 无执行者时 actors=[]；受事/对象主语不得升为 actor；the following/指代短语不得当 actor；coordinated NP 不自动拆成多个 actor。
- 目的：修 actor 锚定、condition/constraint 边界和 exception 漏抽；同时保留当前 action 优势。
- 不要同时改 S，否则下一次仍无法归因。

P1. 收窄 S 的 actor/边界规则，并恢复具体线索。
- 保留 S 的 field definitions、scope、ambiguity、normalized、order_relation、constraint 线索。
- 恢复旧 rule 25-27 的具体线索列表：legal references、time/duration、quantity、purpose、exclusivity、condition markers；把过于抽象的功能判断改回线索+边界双层描述。
- 为 passive/affected-object/determiner/coordination 加入显式负边界，和 P0 的 actor 示例配套。
- 仍不启用新 prompt；只作为下一轮预声明候选。

P2. 把 J 并入 common，J 不再作为实验因素。
- common 中加入 return one bare JSON object; no fences/prefix/explanation; empty/uncertain still complete object。
- 如果下一次验证需要保留 J 开关做别的目的，也应把它和语义消融分开，不混进主结论。

P3. 下一次验证的最小协议（需另行授权，本轮不调用 API）。
- 同一冻结 EStG-150 输入、同一 Gold、同一 `evaluate_coarse`、同一 DeepSeek-V4-Pro-0813/参数。
- 先预声明主指标仍是 five-field mean F1，不被 micro 或 raw JSON 合法率替代。
- 至少比较：旧 v6 默认；修复后 full（common+S+E）；S 删除；E 删除。若 J 已并入 common，不再做 J 删除臂。
- 验收重点：full 不得比旧 v6 差超过 0.01；S/E 各自应有可解释的字段贡献；actor FP 必须显著低于 111；constraint recall 不得再出现 101 级坍塌。
- 因为这是新真实调用，必须先取得用户授权和预算记录；本轮只写清最小待验证问题。

## 7. 已查清 / 主要怀疑 / 尚待验证

### 已查清

- Barrientos 原文消融的实际删除内容、定性观察、以及 Table 5 是主实验而非消融；本项目 suite 是借鉴实验，作者 FULL/NO-PATTERNS 未在本项目执行。
- 新旧实际请求与已保存 request hash 对齐；模型/采样/输入/Gold/evaluator/后处理链可比。
- five-field mean F1 与 micro F1 已分离；旧 evaluation.json 的 0.7719 没有拿来和新版 mean 直接比较。
- actor 核心定义在两版中基本一致；111 退步主因是 actor 过抽，而不是 actor 定义被压缩。
- 111 actor FP 在 raw 模型输出中已经存在，不是 canonicalizer 新增。
- 011 改善 condition/constraint/exception，101 改善 actor/condition 但损伤 constraint，110 变化低于预设 0.01 阈值且不改善 bare-JSON。

### 有成对案例支持的主要怀疑

- 当前紧凑 E 造成字段边界/漏抽偏置：condition 011 恢复 11 个命中；constraint/exception 删除 E 后 F1 改善；legal-reference constraint 示例和完整 JSON 示例的删除是候选原因。
- 当前 S 在当前组合中放大 actor 过抽和 condition 错误：删除 S 后 actor F1 +0.1599；但 S 又承载 constraint 线索，删除后 constraint F1 -0.0541。
- 现有 `estg_000664` 不能证明删 S 完全修复 actor；它只去掉一部分 FP。

### 尚待验证

- 具体是哪一条 S/E 文本或哪一条示例造成上述字段偏置；现有单次消融不能定位到句子。
- provider 端生成漂移占多少；EStG-150 缺少同发布窗口重复，无法严格排除。
- 重建 E、收窄 S、J 并入 common 后是否能恢复到旧 v6 以上；必须等用户授权的下一次真实验证。
- 两实验因素架构是否确实减少冲突；当前只能证明 J 作为实验因素没有必要，不能证明两模块更好。

## 8. 交付边界

- 旧 v6 默认版本未改；`modular_v1` 仍是已实测未通过候选。
- 本轮实际 API=0；未补跑、未重试、未新增模型推理。
- 本报告只记录离线诊断和下一步建议；未新增审批流程、实验框架或并行 pipeline，未修改 Gold、未覆盖历史结果。
- 报告文件：`formal_experiment/outputs/reports/sep_c3_modular_ablation_root_cause_v1.md`。

## 9. 诊断修正（2026-09-16，离线零 API）

本节只修正事实与结论边界，不覆盖第 1-8 节保留的历史结果、manifest 和实验记录。若本节与上文冲突，以本节为准；配套重算见 `outputs/reports/sep_c3_actor_diagnosis_recompute_v1.json`。

### 9.1 旧版 factorial 按当前 coarse 五字段 mean F1 重算

| arm | mean F1 | actor F1 | action F1 | condition F1 | constraint F1 | exception F1 |
|---|---:|---:|---:|---:|---:|---:|
| D-full-0813 | 0.785030442 | 0.708309 | 0.918501 | 0.840531 | 0.757800 | 0.700000 |
| D-no-semantic-examples-0813 | 0.769143182 | 0.569742 | 0.912211 | 0.865189 | 0.761786 | 0.736842 |
| D-no-semantic-guidance-0813 | 0.803302330 | 0.763710 | 0.885523 | 0.844575 | 0.777108 | 0.745563 |
| D-no-explicit-json-contract-0813 | 0.807580535 | 0.697758 | 0.940116 | 0.818723 | 0.763120 | 0.818182 |

结论修正：

- 旧版删除 S/J 后分数更高的现象已经存在：旧 D-no-semantic-guidance=0.803302、旧 D-no-explicit-json-contract=0.807581，均高于旧 D-full=0.785030。因此当前新版删除 S/J 后分数更高，不能全部归因于这次精简。
- 旧版删除 E 后为 0.769143，低于旧版 full。这支持保留示例有作用，但不能直接证明完整 JSON 形式是唯一有效原因，因为该臂把六条语义 input-output 示例替换为一条非语义 key/type 模板，语义内容、答题示范和 JSON shape 同时变化。
- 旧版 factorial（2026-08-30，从旧 v6 做单因素修改）与当前 modular_v1（2026-09-15，压缩并重排 S/E/J）在批次、删除范围和示例形态上不同：旧 no-semantic-guidance 只删规则 9-19、25-27，当前 101 删整个 S 模块；旧 no-explicit-json-contract 删规则 1-5，当前 110 删 J 模块（输出组织两条）；旧 D-full 用六条完整 JSON 示例，当前 111 用压缩 E。因此不能跨版本直接做某一句导致某个 F1 差的单句因果归因。

### 9.2 新增诊断事实

- 新版 111 actor 预测 span=130，FP=84；其中 72 个 FP 位于 Gold actor 为空的样本。旧版 D-full-0813 actor 预测 span=82，FP=35；其中 31 个位于 Gold actor 为空的样本。150 个样本中有 109 个 Gold actor 为空；111 在 56 个空 Gold 样本里有 actor 预测，旧版为 27 个。
- 新版 111 clauses 总数=228，旧版 D-full-0813=240。整体条款没有增加，因此 actor 过抽不能由 clauses 变多解释。
- 旧版 D-full-0813 在 `estg_000028` 的 actors 实际为 `[]`；新版 111 预测 `The income`、`the tax to be assessed`；011 只剩 `the tax to be assessed`。第 3.2 节的相关错误说法已在本节修正。
- 旧版 D-full-0813 原始输出为 107 条裸 JSON、43 条带 Markdown fence；新版 111 为 150 条裸 JSON、0 条 fence。第 2.1 节的 fence 计数已修正；parser 会先处理 fence，格式差异不进入主 F1。
- 必须区分预测 span 命中数与 Gold span 命中数：旧版 actor 预测 span=82、matched_predictions=47、matched_ground_truth=38；111 actor 预测 span=130、matched_predictions=46、matched_ground_truth=39。111 多 48 个预测 span，但预测 span 命中数少 1、Gold span 命中数只多 1，主因是 precision collapse，不是 recall 改善。

### 9.3 主要怀疑与尚不能确定

- 主要怀疑仍是 actor 过抽：额外 actor 大量位于 Gold actor 为空的样本。当前 S 在 111 组合下可能放大该问题，因为 101 删除 S 后 actor FP 从 84 降到 43；但 101 同时丢失 constraint，不能把删除 S 当作修复。
- 尚不能确定具体哪一条 S/E/J 文本或示例造成过抽；旧版 factorial 说明 S/J 删除效应不是本轮新出现，当前组合的交互作用仍不能由旧版单因素实验替代。
- 旧 v6 缺少同发布窗口的 EStG-150 重复运行，provider 端生成漂移不能严格排除。
