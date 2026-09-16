# 受控消融矩阵 AB-1–AB-10 与 Barrientos 消融套件（现状与结构化结论）

> **2026-09-14 用户取消规则＋LLM全部后续实验**：Rules+LLM-Repair / H1 /
> `sun_llm_fallback` 的消融、复跑、优化和新增评价全部取消。下方已完成 H1 结果仅
> 为历史记录；未执行的 H1 项统一按取消处理，不能再列为“待授权/待补跑”。规则先行
> 的 LLM 修复/fallback 不作为替代任务重新派发。Direct-LLM 的 E/S/J 八组合与
> 原始响应后处理分析继续属于 SEP-C3，尚无新调用授权。

> **2026-09-06 撤回说明（覆盖下列 2026-09-05 段）：原生 FULL/NO-PATTERNS 两提示
> 360 次（36×2×5）执行方案已被用户撤回（用户澄清：这是对其意图的误解，不得执行；
> Barrientos 是 Stage 2 的**方法借鉴来源**，Sun 才是整体改进对象，项目不承担“必须
> 整体优于 Barrientos”、也不把原样复现其原生提示作为正式对照）。入口脚本/独立合同/
> 预检报告保留为历史证据（checkpoint `2c5181e`），状态=withdrawn；真实 API=0 不变，
> 任何执行需用户另行明确授权。下列 2026-09-05 段仅为历史记录。本文其余已实测行
> （AB-1/2/3/5/5b/9、D/E 1140、后处理与 450-call 单因素）不受影响。**

> **2026-09-05 来源与后续范围纠正**：用户要求后续按 Barrientos 原文收敛。
> 新增原生 FULL/NO-PATTERNS 两提示执行准备（36×2×5；真实API未授权/未运行），
> 其 artifact 同时去掉44模式清单与控制流冗余限制，不是纯词表单因素。
> 此项是 Barrientos artifact 换模型复现，不等于本文 AB-4 六字段受控词汇贡献
> 已验证。重点统计名单外模式、维度错配、格式与非空可用率；原 schema 不限制
> `compliance_pattern` enum，所以“JSON合法100%”不能代替模式合法率。
> 原文PDF/XML消融已定位，但现有样例两版提示还含措辞差异；该阶段仍未启动。
> 详细预检见 `outputs/reports/barrientos_paper_ablation_preflight_v1.md`；下文历史
> 结果保留，新消融真实数值仍为TODO，不继续为了凑齐AB编号追加实验。

**版本**：v5（2026-09-17）；新增 SEP-C3 已有结果入文，v4/v3 的计划与批次保留为历史段。
本次只整理已有证据，零新增实验/API，不改变历史 AB 数字或原接受标准。
**状态**：Barrientos A/B/C 离线套件、D/E 1140-call 固定计划、Direct-LLM 后处理
三模块离线单因素与三个 Prompt 单因素 450-call 批次均已运行。Prompt 批次失败0，
实际成本 $3.3650。结论按正、负与字段权衡如实报告。
**依据**：`MASTER_PIPELINE.md` §8.8.4 消融矩阵；`docs/research/
BARRIENTOS_BORROWING_AUDIT_2026-07-12.md`；`docs/EVAL_3DIM_SPEC.md`；
`outputs/development/barrientos_ablation_suite_v1/`；
`outputs/development/b0_module_removal_ablation_v1/`；
`outputs/reports/barrientos_ablation_comparison_v1.json`。
**命名**：Rules-Only（旧代号 B0）、Direct-LLM（旧代号 D1）、Rules+LLM-Repair
（旧代号 H1）。机器 ID 仅为兼容保留。
**纪律**：跨 schema/跨任务比较（AB-3/AB-4 等）不得用单一 F1 宣称综合优劣，只能
报告各自口径内结果与定性适配结论；涉及真实 LLM 的消融逐批用户授权。

## SEP-C3 当前结果：四臂已运行并拒绝新版，最小候选仅离线准备（2026-09-17 入文）

本节对应主 Pipeline SEP-C3 / PW7 的结果与归因回填，正文位置为 §6.6.1、§7.3.2，
主张矩阵为 C48/C49。主指标固定为 coarse sentence-level 五字段 F1 算术平均，
不使用下方历史方案的六字段 overall，也不把 modality 分类混入。

| 版本/操作 | mean F1 | 证据状态 |
|---|---:|---|
| 旧 v6 full | 0.785030 | 历史 D-full-0813 预测，同口径核对 |
| 新版 modular_v1 111 | 0.726206 | 150 条真实调用，拒绝替换默认 |
| 新版删 E：011 | 0.746955 | 150 条真实调用 |
| 新版删 S：101 | 0.761056 | 150 条真实调用 |
| 新版删 J：110 | 0.735539 | 150 条真实调用 |
| 新版 000/001/010/100 | — | 未执行；不据此启动补跑 |
| 旧 v6 actor 最小修复候选 | — | 未注册、未启用、未实测；不能填写性能 |

- 2026-09-15 四臂各一次、共 600 次真实调用，失败/重试/样本重复发送均为 0。
  完整候选下降 0.058825；三个模块都未达到保留版至少高 0.01 的原接受标准。
  旧 v6 默认不变；既有调用授权已经用于该批次，不延续到后继候选。
- 历史旧版删 E/S/J 的同口径分数分别为 0.769143/0.803302/0.807581。
  删除 S/J 的方向并非本次精简才出现。旧 E=0 是六条语义示例换一条结构模板，
  不能解释成只删除 JSON 形式。历史和新版的删除范围、示例及批次不同，分表使用。
- actor 预测 82→130，FP 35→84，其中空 actor Gold 样本内 FP 31→72；
  canonical clause 数 240→228。主要表现为 precision 下降，具体文字因果未确定。
  删除 S 虽改善 actor，却损伤 constraint，不能据此全删语义规则。
- 候选只改旧 v6 的规则 10/18/21；六个示例、user template 与其他字段规则不变。
  规则 21 已保留 actors=[] 时的 action 并列拆分。J 转公共固定约定、S/E 为因素
  仍是待验证组织方案，未生成新的实测组合；不据此宣称八组合或新设计已完成。
- 证据：`outputs/evidence/sep_c3_modular_ablation_v1/manifest.json`、
  `outputs/reports/sep_c3_actor_diagnosis_recompute_v1.json`、
  `outputs/reports/sep_c3_actor_fix_candidate_offline_check_v1.json`。
  单次结果不支持生成稳定性或跨版本交互因果结论；人工期望答案不作为模型验证。

## SEP-C1-B 历史 E/S/J 2^3 方案与预算准备（2026-09-14，该完整设计未运行）

**历史状态**：prepared_not_run。本节记录基于旧 v6 的完整八组合与预算准备，
不是上方 modular_v1 已执行四臂的状态，也不是当前派工或调用授权。下列因素、
六字段指标和 2400-call 建议保留作历史来源；当前诊断以本文件上方五字段主口径
及已执行结果为准，不将旧四臂与新版拼成完整组合，不自动补跑任何缺失组合。

### 因素定义与共同最低任务/输出接口

- **E 为语义输入输出示例**：冻结 v6 prompt 的 `## Examples` 六个合成 input-output
  示例，以及 user template 中的 `{few_shot_block}`。E=0 时用已登记的 non-semantic
  structural template 替换示例，保留可解析输出形状但不提供语义示范。
- **S 为详细六要素语义规则**：system prompt 中 `Six-element semantics` 标题与规则
  9-14、`Missing, uncertain, passive, and reference rules` 标题与规则 15-19、
  `Field-typing precision (D1-R1)` 标题与规则 25-27。S=0 只删除这些文本。
- **J 为显式 JSON/结构格式说明**：合同介绍、`Output discipline` 标题与规则 1-5、
  规则 24 中 schema-only 措辞、user template 中 canonical JSON 措辞。J=0 只删除
  这些显式格式纪律，不删除共同接口。
- **共同最低任务/输出接口 C（八个组合都保留）**：角色与任务句；规则 6-8 的
  source-only、精确 span 与 normalized 约束；规则 20-23 的 clause/coordination/
  ID 约束；规则 24 的 span/reference/no-inference 语义部分；input envelope
  （input mode/sample_id/source_id/source_text）。E=1 时六个示例、E=0 时 structural
  template 始终提供可解析 JSON 对象形状，`stage2_prediction.schema.json@1.0.0`
  仍出现在输出示例或模板中。因此 **J=0 不会破坏共同输出契约**，但会失去额外的
  JSON-only/键集合/validation 占位纪律。

### 八组合、已有证据与可复用判断

| E S J | 因子状态 | 现有臂/证据 | 可复用性判断 |
|---|---|---|---|
| 111 | E1 S1 J1 | `D-full-0813`，150 calls，prompt SHA `3aa64877...`，真实执行 | 配置匹配，可作单因素历史基线/构造校验；不作为主 2^3 因子单元 |
| 011 | E0 S1 J1 | `D-no-semantic-examples-0813`，prompt SHA `261d7b23...` | 同上；E=0 是结构模板替换，已在 manifest 披露 |
| 101 | E1 S0 J1 | `D-no-semantic-guidance-0813`，prompt SHA `fa5e9f00...` | 同上；S 删除文本与本节定义一致 |
| 110 | E1 S1 J0 | `D-no-explicit-json-contract-0813`，prompt SHA `0b7b93ad...` | 同上；输出契约由六示例保留，合法率 1.0 |
| 100 | E1 S0 J0 | 无配置相同臂 | 待运行 |
| 010 | E0 S1 J0 | 无配置相同臂 | 待运行 |
| 001 | E0 S0 J1 | 无配置相同臂 | 待运行 |
| 000 | E0 S0 J0 | 无配置相同臂 | 待运行 |

**不可直接拼成完整组合的原因**：现有四条臂来自同一 2026-08-30 批次，每臂只有
1 次，且恰好覆盖 `111/011/101/110` 四个至少两个因素为 1 的格子。该旧批次与
高阶层因子模式完全混杂；若把它们与缺失四格拼成一个 2^3，批次/时间效应会直接
进入主效应和交互项。现有结果可以在单因素历史对照中复用，但不能在未说明混杂
的情况下冒充完整组合。若只追求组合覆盖而非无偏交互，可用它们构造非推荐的
复用变体；其调用数和费用另列在预算表，不作为主授权范围。

### 推荐设计、重复与采样

- **推荐主设计**：同一批次重跑 8 个组合 x 固定 150 条 EStG-150 样本 x 2 次重复
  = **2400 次新增调用**；不复用旧四臂作为因子单元。每条样本在每个 arm/repeat 中
  各调用一次，共 16 个 arm-repeat 观测；全 2^3 模型含 8 个参数，残差自由度 8。
- **固定样本**：`data/input/estg150_formal_inference_input_v2.json`，150 条，
  SHA256 `52a73aa1109970b6c4fbc17214b0828ed0dd64b330001e884cdc803b1ce81dc2`。
- **Gold/evaluator**：Stage 2 正式冻结 Gold/evaluator 口径不变；evaluator
  `sun_literal_overlap_evaluation@2.0.0`，配置 SHA256
  `352113b568c6075c8b01dafa5fdf2e5ab4a1454bb10933cd2f9c27f5c008cc3f`；真 Gold
  以冻结 commit `56d2b03` 的 Layer E + membership 构建，等价正式发布件
  `estg150_formal_gold_v1.json` SHA256
  `c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100`。
- **采样参数**：`deepseek-v4-pro`（登记 release `DeepSeek-V4-Pro-0813`），
  temperature=0、top_p=1、max_tokens=4096、retry=0、stream=false、
  thinking.type=disabled、response_format=null；只在北京时间闲时执行；API arm
  不读取 Gold，预测锁定后才评价。
- **重复含义**：两次为 provider-level 复跑，不是独立样本；主分析同时报告
  repeat 内差异，不以 repeat 替代 150 条样本的配对结构。
- **推荐先不做第三重复**。若门控（失败率或重复差异）触发，再单独申请
  +1200 calls；不得在一批内自动续跑。

### 评价指标、失败计数与预定分析

- **主指标**：每次 arm/repeat 的 `overall.f1`（Sun literal-overlap 六字段
  statement-level 口径）。**次指标**：六个字段的 P/R/F1、无效/失败计数、
  合法输出率；modality 分类 label 不在本 factorial 主表中（该 evaluator
  只看 evidence span），仍按 Stage 2 单独表报告。
- **失败定义与计数**：网络/API error、空响应、非 JSON、schema/cross-field
  invalid、identity 不符、无法进入 canonical six-field record，均计失败并保留在
  150 条分母中；evaluator 对 invalid attempt 按空抽取处理。逐 arm/repeat 报
  `failed_count`、`valid_output_rate`、`invalid_attempt_count`。任一 arm/repeat 内失败率
  >5% 标记不稳定，>10% 暂停该组合的因子解释；同时报完整案例敏感性分析
  （剔除该 arm/repeat 内失败样本后重算），但不得用剔除结果替换主分母。
- **主效应/交互模型**：以 arm-level `overall.f1` 为响应，编码 E,S,J 取 0/1，
  拟合全因子模型
  `Y = mu + aE + bS + cJ + ab(E*S) + ac(E*J) + bc(S*J) + abc(E*S*J) + error`。
  主效应为边际均值差（E=1 减 E=0，以此类推）；交互项按差中之差定义并明确
  报告。重复提供纯重复误差；不做未预注册的 p 值或显著性声明。
- **不确定性**：按 150 个 sample_id 做整簇 bootstrap（B=10,000，所有 arm 共享
  同一重抽样），每次重算全部 8 个 arm 的 evaluator 并重新拟合模型，报告主效应和
  交互效应的 percentile 95% CI；同时报告 repeat-level min/max/SD。若 CI 包含 0，
  只写无区间证据，不写无效应。
- **口径冻结**：因素文本、组合构造、样本、重复次数、采样参数、指标、失败处理、
  主/交互分析在运行前锁定；运行后不改因子/阈值/指标；负结果与失败组合照实报告。

### 新增调用数与预算上限

| 方案 | 新增 calls | 预计 input tokens | input cap(x1.5) | output cap(4096/次) | USD cap(peak) | CNY off-peak envelope | 预期成本(线性外推，非上限) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **推荐：同批次 8x150x2** | **2400** | 8,687,550 | 13,031,325 | 9,830,400 | **67.36** | **229.63** | $16.11 / 54.92 元 |
| 非推荐复用变体（旧四臂 repeat-02 + 缺失四格 x2） | 1800 | 5,841,713 | 8,762,570 | 7,372,800 | 48.92 | 166.76 | $11.39 / 38.84 元 |
| 可选第三重复（全 8x150x1） | +1200 | 4,343,775 | 6,515,663 | 4,915,200 | +33.68 | +114.81 | +$8.05 / +27.46 元 |

**单臂 estimate（每 150 calls，渲染 body UTF-8 bytes/3 向上取整）**：

| E S J | 臂 | 预计 input tokens |
|---|---|---:|
| 111 | D-full-0813 | 880,149 |
| 011 | E0/S1/J1 | 432,849 |
| 101 | E1/S0/J1 | 703,149 |
| 110 | E1/S1/J0 | 829,690 |
| 100 | E1/S0/J0 | 652,495（计划） |
| 010 | E0/S1/J0 | 383,395（计划） |
| 001 | E0/S0/J1 | 255,849（计划） |
| 000 | E0/S0/J0 | 206,199（计划） |

**计算依据与边界**：
- input token：按现有 runner 的 `render all requests -> JSON body -> ceil(UTF-8
  bytes/3)` 计算；111/011/101/110 的单臂值与既有 450-call 预算逐项一致；缺失四臂
  由冻结 v6 prompt 与已登记 v2 变换确定性组合生成，属计划估算，创建 prompt 后
  必须重新渲染并替换为最终值；组合生成脚本/规则未在本轮写成可执行 prompt。
- input cap = 预计 input x 1.5；output cap = calls x 4096；USD cap 与 CNY envelope
  按 2026-08-30 项目记录价格快照计算并乘 1.2 向上取整。
- **价格来源与日期**：`https://api-docs.deepseek.com/zh-cn/quick_start/pricing/`；
  peak：input cache-miss 1.32 USD/1M、output 3.96 USD/1M；off-peak CNY：
  input 4.5、output 13.5 每 1M。该快照由 2026-08-30 项目合同记录，**本轮
  2026-09-14 未联网复核**；执行前必须再次核验，若价格或模型 release 变化则停止
  并重新授权，不得用本表旧价直接调用。
- **扣除重跑量的条件**：只有状态完成且 prompt/input/evaluator/model release/
  采样参数全部匹配，才允许把旧结果计入同一分析。本轮旧四臂虽配置匹配，但其
  设计状态是 4 个单因素臂加 1 个共享 baseline、每臂 1 次、旧批次与至少两个因素
  为 1 的格子完全混杂，不满足主 2^3 组合的均衡状态，故主推荐预算不扣除它们；
  非推荐复用变体才把这 600 次旧结果扣为 repeat-01，扣后新增 1800 次。
- **预期成本**：利用既有 450-call 批次的实际 usage 按 E/S/J 因子线性外推，
  只作预算参考，不作为硬上限；硬上限以 caps 表为准。

### 后续最小执行范围与授权材料

- 下一实现批次（仍未执行）：在现有 v2 builder/runner 上新增缺失四臂，生成
  八臂 manifest、prompt hashes 和重新渲染 token 预算；扩展执行器到
  `8 arms x repeat-01/02`，加入同一授权/账本/off-peak/失败停止门；跑零 API
  的 dry-run 和预算门，不调用真实 API。
- 授权材料：见 `docs/API_AUTHORIZATION_REQUEST.md` 第 14 节的草案句和 caps；用户
  亲自发出逐字授权句并创建授权事件后才可调用；本轮不创建授权事件、不执行。
- 若复用门禁发现旧臂 prompt/input/evaluator/model release 任一不匹配，旧的
  600 次也不得复用；主推荐方案本身不依赖旧结果，调用上限不变。
- **所有 000-111 真实运行/评价保持待运行**；未取得真实 arm manifest 前，不得
  在论文中写任何组合的消融结果。

## Barrientos 消融套件 v2（2026-08-22，零 API）——离线完成 + D/E wired

### 实验 A：Direct-LLM 校验链（离线近似敏感性分析；锁定 D1-R3 响应，fine Gold literal-overlap v2）

| 条件 | overall F1 | action F1 | 合法输出率 | span 越界 | unanchored | broken edges | 说明 |
|---|---:|---:|---:|---:|---:|---:|---|
| `full_locked`（完整链） | 0.7756 | 0.8800 | 1.0 | 0 | 0 | 140 | 锁定 D1-R3 fine 结果（复现一致） |
| `schema_only_approx`（首现锚定，无确定性重锚） | 0.7733 | 0.8705 | 1.0 | 0 | 0 | 140 | **近似**（raw JSON 未持久化） |
| `raw_approx`（首现锚定 + 丢无法回指 span） | 0.7733 | 0.8705 | 1.0 | 0 | 0 | 140 | **近似** |

- 锁定响应统计：150/150 合法（1.0）；span canonicalizer 状态 reanchored=126 /
  degraded=23 / unchanged=1；重锚 span 总数 966；dropped spans=42、dropped
  clauses=0、dropped edges=18；被 canonicalizer 改变/恢复的样本 = 149/150。
- Full vs Schema-only 绝对增量：overall F1 +0.0024；action 字段 +0.0095
  （其余字段 0.0）。**结论（有数据）**：校验+确定性后处理是真实贡献模块——它把
  966 个 span 坐标重锚到唯一精确文本、恢复/改变 149/150 个样本的坐标一致性，
  并把 action 字段 F1 提高约 1 个百分点；但**在 span-overlap 主口径下总体增量
  较小（+0.0024）**，因为重锚主要影响坐标精确性而不改变文本覆盖。
- **命名与边界（v2 修正）**：本实验统一称“离线近似敏感性分析”；仅
  `full_locked` 是真实锁定结果；`schema_only_approx`/`raw_approx` 由
  post-canonical 输出构造，**不得称为精确 raw-response 消融**（原始模型 JSON 未
  持久化于锁定 s27 产物）。

### 实验 B：Rules-Only 模块去除（同一 EStG-150 / 同 Gold / 同 evaluator；full 复刻锁定 v10a；v2 补结构指标）

| 条件 | overall F1 | ΔF1 | modality label acc | label macro-F1 | gold map 可解析率 | predicted map 内部有效 | map 变化样本 | 说明 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Full | 0.7186 | — | 0.7316 | 0.700 | 0.2 | 1.0 | — | 复刻锁定 v10a fine 口径 |
| no_lexicon_extensions | 0.7120 | −0.0066 | 0.7316 | 0.700 | 0.2 | 1.0 | 12 | 仅 public tier；actor 词典扩展移除 |
| no_modality_classifier | 0.7186 | 0.0 | 0.6797 | **0.581** | 0.2 | 1.0 | 0 | span 不变；label/macro 明显下降（marker-only） |
| no_actor_action_ownership | 0.7186 | 0.0 | 0.7316 | 0.700 | 0.2 | 1.0 | 12 | 只改 map（12 样本），不改 span/label |
| no_multi_match_guard | 0.7239 | +0.0053 | 0.7316 | 0.700 | 0.2 | 1.0 | 0 | 首候选消费反而略升 span F1（副作用披露） |
| no_de_en_alignment_validation | 0.7186 | 0.0 | 0.7316 | 0.700 | 0.2 | 1.0 | 0 | 只改 route，无可测影响（如实） |

- **v2 结构指标说明（诚实边界）**：冻结 EStG-150 Gold 的 actor-action map 使用
  未能解析的短 ID（`a01`/`c1_action_1`/`None`），**gold 与预测的精确 ID 级对比
  不可计算**（gold map 可解析率仅 0.2）；因此结构层报告的是：predicted map 内部
  有效性（1.0，预测边均引用自身 clause 内的 actor/action）、map 相对 full 的
  变化样本数（no_lexicon/no_ownership=12）、以及每 flag 的变化案例。span 指标
  **不覆盖结构 map**，本套件明确标注该边界。
- 结论（有数据）：span 覆盖主要由 lexicon+tregex+校验链贡献；classifier 主要
  贡献 modality label（acc −0.0519、macro −0.119）；DE-EN 验证在本数据上无可测
  增量；multi-match guard 的首候选消费副作用为 +0.0053（不是保守守卫的净收益
  证据）。

### 实验 C：四类 vs 三类 modality 投影（formula Gold 231 clauses）

- 四类：definition 39 / obligation 97 / permission 62 / prohibition 33。
- 三类共享子集：obligation 97 / permission 62 / prohibition 33；definition
  被排除 39 条，覆盖率损失 = 39/231 = 16.88%。
- **定义不并入其它类**；这是 schema 覆盖差异比较，不是 Barrientos 方法性能比较。

### 实验 D/E：prompt/few-shot 与同数据模块替换（v2：1140/1140 已执行）

- 输入已修正：`configs/ablations/e_same_data_input_contract_v2.json` ——
  **36 条唯一版本化 ID（如 r10v1/r10v2）直接派生自冻结 S2.12 复杂语料输入**，
  36/36 唯一、无空/`-` 占位文本、每条绑定 source file/text/Gold hashes；
  v1 的错误“38 条非空”合同已废弃（当时把 4 条 `-` 占位记录算入并把版本行当
  重复）。
- D 四臂均在 DeepSeek-V4-Pro-0813 同一 release window 真实运行：D-full / D-no-fewshot /
  D-minimal / D-barrientos-style，各 150 条；旧 Preview D-full 不作基线。
  E 三臂（E-ours / E-barrientos-faithful / E-module-swapped）+ 共享指标协议 +
  E-ours 与 E-barrientos-faithful 各 5 次稳定性（首轮计入）。
- 固定计划 1140/1140 已完成。D-full P/R/F1=0.8203/0.7289/0.7719；no-fewshot/minimal/Barrientos-style 的锁定六字段结果为0。**逐臂 parse 率必须分开写**：full parse ok=1.000；no-fewshot parse ok=0.980、Barrientos-style parse ok=0.993——这两臂“可解析但 canonical 六字段非空率=0”（坐标接口/格式失配，no-fewshot 另有原始响应诊断）；minimal（极简任务+JSON）parse ok=**0.000**（根本无可解析 JSON）。**不能把三个零分臂一概写成“可解析、仅接口失配”**，也不能把 0 直接解释为语义贡献为 0。
- 2026-08-30 严格 Prompt 单因素 v2 已完成（`prompts/sun_compat/ablation_v2/`）：
  语义示例→纯结构模板、只删详细语义规则、只删显式 JSON 纪律；3×150=450/450
  calls，失败0，复用同 release D-full 基线。完整/三删除臂 F1 分别为
  0.7719/0.7650/0.7759/0.7790；报告见 `d1_prompt_factorial_results_v1.{json,md}`。

## 总表（一行/一组结构化结论）

| 消融 | 我的完整模块 | 换成 Barrientos 模块 | 去掉模块 | 我的优势 | Barrientos 优势 | 综合结论 | 可比较性限制 |
|---|---|---|---|---|---|---|---|
| AB-1 详细语义规则 | Six-field prompt v6 的规则9–19、25–27 | 移植其 prompt（3 类 modality、RC4PC 字段定义） | **严格 v2 臂**只删规则9–19、25–27，输出纪律和六个示例保持 | action F1：full 0.8603，删除后0.8086（Δ−0.0518） | 其字段定义更适合 change-impact，不解决 Sun 六字段边界 | **已完成**：overall full 0.7719，删除后0.7759（Δ+0.0040）；详细规则未显示总体正增益，但保护 action、牺牲部分其他字段 | 单次150条描述性结果；不得由局部正/负 delta 推成普遍结论 |
| AB-2 语义示例 | 6 个 Gold-blind 合成输入—输出 fixture | Barrientos-style 示例属于跨 schema 模块替换 | **严格 v2 臂**把六个语义例子替换为纯 key/type 结构模板 | **已完成**：overall 0.7719→0.7650（Δ−0.0069），actor 0.6865→0.5548（Δ−0.1317）；示例有小幅总体、显著 actor 字段贡献 | 其示例贴近 change-impact 任务 | 旧 no-fewshot 0分只证明接口混杂；严格结构保持臂才支持语义示例贡献 | v2是结构保持替换而非纯删除；单次150条描述性结果 |
| AB-3 modality 类别 | 4 类（Sun，含 definition，明确“主要目的是定义”） | 3 类投影（obligation/permission/prohibition，Barrientos enum） | — | definition 独立价值可被度量 | 3 类更贴近其数据 | **已完成（2026-08-22，离线）**：formal Gold 231 clauses 中 definition=39（obligation 97/permission 62/prohibition 33），三类共享子集 = 97/62/33，definition 覆盖率损失 16.88%（39/231）；definition 不并入其它类；结果见 suite C | 跨 schema 类别数比较属 C4，禁止用单一 macro-F1 宣称优劣；只能报告投影后各自口径 |
| AB-5 校验链 | adapter + span canonicalizer + canonical validator | 其 strict JSON schema 校验 | 每次仅去一个模块 | exact-text回指与fail-closed审计 | 其 schema 原生适配自己的表示 | **2026-08-30同一D-full raw离线单因素**：full F1 .7719；−adapter Δ0；−canonicalizer F1 0（149/150 invalid）；−validator Δ0（0 upstream invalid observed） | “Δ0”仅是该响应集无分数增量，不等于兼容/安全模块普遍无用 |
| AB-5b 显式 JSON 契约 | prompt 中的仅JSON/固定键/schema纪律 | Barrientos strict-JSON/schema纪律 | 只删明文 JSON 纪律，保留语义规则与六例 | 当前 arm 未显示准确率/合法率增益 | Barrientos 原生 schema 校验更贴合其表示 | **已完成**：full 0.7719；删除后0.7790（Δ+0.0071），合法率两者均1.0 | 只说明当前模型+示例+150条上未测得增益；不能称安全纪律普遍无用 |
| AB-4 受控词汇 | Six-field 受控 schema（normalized view 受控，原文 span 不覆盖）+ public marker lexicon | 移植其 44 模式 dual-view（control_flow/resource/data/time） | 无受控 schema（裸输出） | schema 受控 + verbatim span 回指 | 44 模式分类更适合 change-impact 表示层 | **待运行**（需实现 dual-view adapter 与消融脚本，真实 LLM 项逐批授权） | C4 跨 schema；pattern 层与 six-field 层不对齐 |
| AB-6 transport | thinking-disabled、无 json_object、temp0/top_p1、max_tokens4096、stream=false | 默认 transport（provider 默认 thinking / json_object） | — | **已有历史证据**：D1-R3 干净重跑 150/150 有效、0 事故（lost=recovery=retry=0）；实证官方端点在默认 thinking 下返回空内容、json_object 下形状不同 | 论文未披露 transport 细节 | 锁定配方唯一、0 事故；默认配方事故率/形状差异为已披露动机 | 官方端点行为跨版本可能变化，需重验 |
| AB-7 评价口径 | 细 Gold（1055 spans 对照）/ 粗 Gold（609 spans，Sun 句子级主口径）/ Sun-marker 收敛 | 其 Step-specific P/R/F1 + strict JSON + self-consistency | 单一口径 | **已有历史证据**（见 §口径表）：细 0.7186 vs 0.7756、粗 0.7986 vs 0.8726；Sun-marker 收敛后 B0 constraint R 1.0 (13/13)、condition R 0.989 (91/92) | 其主指标为结构化表示合法性与稳定率，与 span 口径不可直接换算 | 口径敏感性已有正式归因证据（2026-08-07 用户决策 + formal comparison）；两种口径必须分表 | 细/粗同 Gold 可 C1；span vs 结构化指标跨任务 C4 |
| AB-8 Rules-Only 模块 | public marker lexicon / BERT-TextCNN / marker routing+DE-EN cue 验证 / CoreNLP / Tregex / Tsurgeon guard / actor-action 归属 / 确定性评价 | 其 44 模式分类 / LLM 结构化输出 | 逐模块去掉 | **已有历史证据 + 2026-08-22 实验 B（real offline，同一 150/同一 Gold/同一 evaluator）**：full 0.7186；no_lexicon −0.0066（actor 词典扩展移除）、no_modality_classifier label acc 下降（span 口径不变）、no_multi_match_guard +0.0053（首候选消费副作用，如实披露）、其余 0.0（只改 map/route 不改 span） | 其模块面向 change-impact 表示，与六要素抽取模块不对应 | 逐模块去除矩阵已跑（B）；每个模块贡献/副作用按数据如实报告 | C4：Barrientos 模块与 B0 模块语义不同，逐模块替换需 adapter |
| AB-9 稳定性 | OURS-FULL 36条×5次、temp0、prompt hash锁定 | Barrientos 36条×5次、pairwise distance≤2 self-consistency | — | 同协议同输入重复运行已完成 | 其论文给出原生 self-consistency 定义 | **已完成**：BARR-FULL / OURS-FULL / OURS-BARRIENTOS-MODULE 各36×5；稳定性只报告同一arm内部一致性 | 稳定性不是准确率，不用于跨方法F1排名 |
| AB-10 style-equivalent | 关闭（主表为 span-overlap 字面匹配） | 其专家协议的 style-equivalent alignment 概念 | — | 主指标不受风格差异污染 | 允许“表达不同语义相同”算正确（更宽容） | **待实现**（需新一代价指标与匹配规则，明确为辅助敏感性分析，不冒充主指标） | 只能作为敏感性分析分表；不得冒充论文主表 |

## AB-7 口径表（已有历史证据，development 归因，2026-08-07 用户决策 + formal 横向）

| 口径 | Rules-Only P/R/F1 | Direct-LLM P/R/F1 | 谁领先（描述性） | 依据 |
|---|---|---|---|---|
| 细 Gold（1055 spans，对照口径） | 0.6845 / 0.7564 / **0.7186** | 0.8793 / 0.6938 / **0.7756** | Direct-LLM F1 +0.057 | B0-R3/D1-R3 同口径；formal comparison 细字段诊断沿用 |
| 粗 Gold（609 spans，Sun 句子级主口径） | 0.7309 / 0.8801 / **0.7986** | 0.9012 / 0.8456 / **0.8726** | Direct-LLM F1 +0.074 | 2026-08-07 归因；formal 三方法对照沿用粗五字段 |
| Sun-marker 收敛（constraint/condition） | constraint R 1.0 (13/13)、condition R 0.989 (91/92) | — | P 侧不可解读（单边收敛） | `s27_b0_coarse_gold_cc_v1` / `s27_coarse_gold_marker_converged_v1` |

结论：我们的 Gold 有 302 个 constraint，仅 13 个（4%）符合 Sun Table-4 marker
定义 → 低分主因是 constraint 定义口径差异（定义范围宽约 8–23 倍），不是“抽不到”。

## AB-6 证据（已有历史证据，非正式）

- D1-R1 VERIFY-PASS（s27_d1_v6_verify_pass_150_hist56d_v1）：150/150 有效、0
  事故，F1 0.7669→0.7735。
- D1-R3 干净重跑（s27_d1_v6_r3_clean_rerun_150_hist56d_v1）：150/150 有效、0
  事故、lost/recovery/retry=0；F1 0.7756。
- transport 配方锁定于 `configs/models/estg150_d1_active_registry_v1.json`。

## AB-8 证据（已有历史证据，B0-R1 各批次）

| 批次 | 内容 | 实测 |
|---|---|---|
| B0-R1-ACTION | action span 吞并修复（排除 nsubj 等依赖） | 主语开头 action 8→0、strict-exact 3.0×；主口径持平 |
| B0-R1-SCOPE-DISAMBIG | constraint↔condition 消歧候选 | 实测 −0.0005 被拒（记方法局限） |
| B0-R1-ALIGN | 德英 cue 验证（伪 validated 消除） | validated 107→49、主口径不变 |
| B0-R1-BRIDGE | `<`/`<<` 语义 + multi-match fail-closed | 真实 bridge 测试通过 |
| B0-R1-ACTOR | 多词 actor + 依赖边查找 | 主口径 +0.0018、actor F1 0.616→0.670 |
| B0-R1-LEXICON-DECISION | 13 名词词典扩展（用户授权） | actor R 0.958 |

## 报告纪律

1. 未跑项的“待运行/待授权”状态不构成结果；不得在论文/仓库写入这些项的数值。
2. 跨 schema 比较只允许定性 + 各自口径内数字；任何更严格的翻译需明确 adapter。
3. 本矩阵随实验结果推进更新状态列；每次更新走 `record_change.py` + Git checkpoint。
