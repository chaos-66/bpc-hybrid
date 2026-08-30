# 受控消融矩阵 AB-1–AB-10 与 Barrientos 消融套件（现状与结构化结论）

**版本**：v3（2026-08-30）
**状态**：Barrientos A/B/C 离线套件与 D/E 1140-call 固定计划均已运行；Direct-LLM
后处理三模块离线单因素已完成；新一轮三个 Prompt 单因素已冻结为独立 450-call
计划但尚未执行。**不得**把 prepared 写成 completed。
**依据**：`MASTER_PIPELINE.md` §8.8.4 消融矩阵；`docs/research/
BARRIENTOS_BORROWING_AUDIT_2026-07-12.md`；`docs/EVAL_3DIM_SPEC.md`；
`outputs/development/barrientos_ablation_suite_v1/`；
`outputs/development/b0_module_removal_ablation_v1/`；
`outputs/reports/barrientos_ablation_comparison_v1.json`。
**命名**：Rules-Only（旧代号 B0）、Direct-LLM（旧代号 D1）、Rules+LLM-Repair
（旧代号 H1）。机器 ID 仅为兼容保留。
**纪律**：跨 schema/跨任务比较（AB-3/AB-4 等）不得用单一 F1 宣称综合优劣，只能
报告各自口径内结果与定性适配结论；涉及真实 LLM 的消融逐批用户授权。

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
- 固定计划 1140/1140 已完成。D-full P/R/F1=0.8203/0.7289/0.7719；旧
  no-fewshot/minimal/Barrientos-style 的锁定六字段结果为0，但 no-fewshot 原始响应
  诊断证明其中混入坐标接口崩溃，不能把0直接解释为语义贡献。
- 2026-08-30 新增严格 Prompt 单因素 v2（`prompts/sun_compat/ablation_v2/`）：
  语义示例→纯结构模板、只删详细语义规则、只删显式 JSON 纪律；3×150=450 calls，
  复用同 release D-full 基线，不重复调用。独立合同当前 `authorization=null`，状态为
  `prepared_not_executed`。

## 总表（一行/一组结构化结论）

| 消融 | 我的完整模块 | 换成 Barrientos 模块 | 去掉模块 | 我的优势 | Barrientos 优势 | 综合结论 | 可比较性限制 |
|---|---|---|---|---|---|---|---|
| AB-1 详细语义规则 | Six-field prompt v6 的规则9–19、25–27 | 移植其 prompt（3 类 modality、RC4PC 字段定义） | **严格 v2 臂**只删规则9–19、25–27，输出纪律和六个示例保持 | 历史 v5→v6：constraint R 0.2881→0.4172（+0.1291）；严格臂待运行 | 其字段定义更适合 change-impact，不解决 Sun 六字段边界 | v2 prompt/hash/150条计划已冻结；真实结果待450-call批次 | 历史 v5对比是开发证据；最终单因素结论只用 v2 同模型/同150/同Gold结果 |
| AB-2 语义示例 | 6 个 Gold-blind 合成输入—输出 fixture | Barrientos-style 示例属于跨 schema 模块替换 | **严格 v2 臂**把六个语义例子替换为纯 key/type 结构模板 | Gold 零交叠；结构模板可避免输出格式崩溃污染语义归因 | 其示例贴近 change-impact 任务 | 旧 no-fewshot 锁定0分已运行，但原始146/150非空、兼容桥F1=0.526，故仅证明接口贡献；严格语义示例臂待450-call批次 | v2是受控替换而非纯删除；必须如实披露 |
| AB-3 modality 类别 | 4 类（Sun，含 definition，明确“主要目的是定义”） | 3 类投影（obligation/permission/prohibition，Barrientos enum） | — | definition 独立价值可被度量 | 3 类更贴近其数据 | **已完成（2026-08-22，离线）**：formal Gold 231 clauses 中 definition=39（obligation 97/permission 62/prohibition 33），三类共享子集 = 97/62/33，definition 覆盖率损失 16.88%（39/231）；definition 不并入其它类；结果见 suite C | 跨 schema 类别数比较属 C4，禁止用单一 macro-F1 宣称优劣；只能报告投影后各自口径 |
| AB-5 校验链 | adapter + span canonicalizer + canonical validator | 其 strict JSON schema 校验 | 每次仅去一个模块 | exact-text回指与fail-closed审计 | 其 schema 原生适配自己的表示 | **2026-08-30同一D-full raw离线单因素**：full F1 .7719；−adapter Δ0；−canonicalizer F1 0（149/150 invalid）；−validator Δ0（0 upstream invalid observed） | “Δ0”仅是该响应集无分数增量，不等于兼容/安全模块普遍无用 |
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
