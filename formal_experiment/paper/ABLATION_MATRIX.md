# 受控消融矩阵 AB-1–AB-10（现状与结构化结论）

**版本**：v1（2026-08-20）
**状态**：设计矩阵；仅“已有历史证据”项可引用既有结果；其余一律标“待运行”/“待授权”，
**不得**把“已经设计矩阵”写成“已经完成实验”。
**依据**：`MASTER_PIPELINE.md` §8.8.4 消融矩阵；`docs/research/
BARRIENTOS_BORROWING_AUDIT_2026-07-12.md`；`docs/EVAL_3DIM_SPEC.md`。
**命名**：Rules-Only（旧代号 B0）、Direct-LLM（旧代号 D1）、Rules+LLM-Repair
（旧代号 H1）。机器 ID 仅为兼容保留。
**纪律**：跨 schema/跨任务比较（AB-3/AB-4 等）不得用单一 F1 宣称综合优劣，只能
报告各自口径内结果与定性适配结论；涉及真实 LLM 的消融逐批用户授权。

## 总表（一行/一组结构化结论）

| 消融 | 我的完整模块 | 换成 Barrientos 模块 | 去掉模块 | 我的优势 | Barrientos 优势 | 综合结论 | 可比较性限制 |
|---|---|---|---|---|---|---|---|
| AB-1 prompt 字段定义 | Six-field prompt v6 含 constraint 六子类显式定义（法律引用/时间/数量/within the meaning/pursuant to/subject to），empty=absent、禁止并入 action/condition | 移植其 prompt（3 类 modality、RC4PC 字段定义） | v5（无 v6 规则 25–27） | **已有历史证据**：v5→v6 实测 constraint R 0.2881→0.4172（+0.1291），Overall F1 0.7669→0.7735 | 其字段定义针对 change-impact 表示，不解决 Sun 六要素 constraint 归属 | 字段定义对 constraint R 有可测量贡献（历史证据）；正式“去掉定义”对照 arm 需授权真实验证 | 训练/测试同一 150 + 同 Gold 可 C1；但 v5 baseline 是 development、非 formal 对照 arm——正式表需补跑 |
| AB-2 few-shot | 6 个 Gold-blind 合成 fixture（覆盖 condition/constraint/exception 缺口，与 150 测试句零交叠） | 0-shot；或 Barrientos-style 样例（可能引入测试句/领域偏置） | 0-shot | 合成 + 零交叠保障（S2.9 DoD），不泄漏 Gold | 无 Gold-invisible 设计；其样例更贴近真实 change-impact 场景 | **待运行**（需授权真实 LLM 臂：v6+fixtures vs 0-shot vs Barrientos-style） | 不同 few-shot 集跨模型/跨预算可比性受限 |
| AB-3 modality 类别 | 4 类（Sun，含 definition，明确“主要目的是定义”） | 3 类投影（obligation/permission/prohibition，Barrientos enum） | — | definition 独立价值可被度量 | 3 类更贴近其数据 | **离线可评、正式结果待运行**（2026-08-20 核账）：正式 Gold/Predictions 的 modality 均为 4 类 label（gold=plain string 如 `obligation`、pred=label+evidence），输入已具备；formal Gold 231 clauses 中 definition=39（obligation 97/permission 62/prohibition 33），投影有实质内容；需要一个 4→3 投影脚本 + 显式映射规则（definition 如何处理：剔除或并入其最邻近类）并注册 manifest；当前无脚本无结果 | 跨 schema 类别数比较属 C4，禁止用单一 macro-F1 宣称优劣；只能报告投影后各自口径 |
| AB-4 受控词汇 | Six-field 受控 schema（normalized view 受控，原文 span 不覆盖）+ public marker lexicon | 移植其 44 模式 dual-view（control_flow/resource/data/time） | 无受控 schema（裸输出） | schema 受控 + verbatim span 回指 | 44 模式分类更适合 change-impact 表示层 | **待运行**（需实现 dual-view adapter 与消融脚本，真实 LLM 项逐批授权） | C4 跨 schema；pattern 层与 six-field 层不对齐 |
| AB-5 校验链 | canonical validator（格式/回指/字段权限）+ span canonicalizer（fail-closed unique exact-text re-anchor）+ 确定性后处理 | 其 strict JSON schema 校验 | 裸 JSON 直接采纳 | 已有历史证据：H1 span canonicalizer 离线 replay 3/3 重锚、validator 通过、merge accepted（S2.8D-R3，0 API calls）；D1-R1/R3 150/150 有效、0 事故 | 论文只报告 strict-JSON 合法性，未逐字段 re-anchor | validator/canonicalizer 的高有效率与坐标恢复作用已有间接证据；“去掉校验链”的对照 arm 需专门实验（可离线用锁定输出估计，正式结论待运行） | 有效/回指率可 C1 比较；坏 span 拒绝逻辑逐方法披露 |
| AB-6 transport | thinking-disabled、无 json_object、temp0/top_p1、max_tokens4096、stream=false | 默认 transport（provider 默认 thinking / json_object） | — | **已有历史证据**：D1-R3 干净重跑 150/150 有效、0 事故（lost=recovery=retry=0）；实证官方端点在默认 thinking 下返回空内容、json_object 下形状不同 | 论文未披露 transport 细节 | 锁定配方唯一、0 事故；默认配方事故率/形状差异为已披露动机 | 官方端点行为跨版本可能变化，需重验 |
| AB-7 评价口径 | 细 Gold（1055 spans 对照）/ 粗 Gold（609 spans，Sun 句子级主口径）/ Sun-marker 收敛 | 其 Step-specific P/R/F1 + strict JSON + self-consistency | 单一口径 | **已有历史证据**（见 §口径表）：细 0.7186 vs 0.7756、粗 0.7986 vs 0.8726；Sun-marker 收敛后 B0 constraint R 1.0 (13/13)、condition R 0.989 (91/92) | 其主指标为结构化表示合法性与稳定率，与 span 口径不可直接换算 | 口径敏感性已有正式归因证据（2026-08-07 用户决策 + formal comparison）；两种口径必须分表 | 细/粗同 Gold 可 C1；span vs 结构化指标跨任务 C4 |
| AB-8 Rules-Only 模块 | public marker lexicon / BERT-TextCNN / marker routing+DE-EN cue 验证 / CoreNLP / Tregex / Tsurgeon guard / actor-action 归属 / 确定性评价 | 其 44 模式分类 / LLM 结构化输出 | 逐模块去掉 | **已有历史证据**：B0-R1 七子批次（ACTION 边界质量、ALIGN 伪 validated 消除、ACTOR +0.0018、LEXICON-DECISION R 0.958、BRIDGE 守卫） | 其模块面向 change-impact 表示，与六要素抽取模块不对应 | 各模块边际贡献部分有证据（R1 各批次），正式逐模块去除矩阵未跑 | C4：Barrientos 模块与 B0 模块语义不同，逐模块替换需 adapter |
| AB-9 稳定性 | temp0 + prompt hash 三方锁定（D1-R2）；同协议 5 次独立重跑未执行 | 36 条 × 5 次完整运行、Step 1 pairwise distance≤2 self-consistency | — | 设计已锁定；未有 5-run 数据 | 论文已有完整 5-run self-consistency 报告 | **待授权**（需要同协议 5 次正式重跑 + self-consistency/field-span agreement 报告） | 对齐其 5-run 设计；field-span agreement 口径为本项目自定 |
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
