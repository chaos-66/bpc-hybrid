# BPC-Hybrid 完整实验主 Pipeline

**文档版本**：3.6.23
**状态**：ACTIVE — 全项目研究与任务分解的唯一主线  
**最后更新**：2026-08-17
**方法学主干**：Sun et al. (2024)（三阶段方法主干）；Barrientos et al. (2026)（直接借鉴来源：LLM 结构化输出、验证、受控词汇、归一化与评估纪律）
**当前实施优先级**：实验先完成 Stage 2，再补 Stage 1 和 Stage 3；论文非结果章节从现在并行写作；2026-08-08 导师汇报后方向锁定见 §8.8

> 所有 Agent 在修改实验代码、配置、数据协议或研究设计前必须完整阅读本文。
> 本文定义“要完成什么、先后依赖是什么、每一步怎样算完成”。
> `docs/PROJECT_AUDIT.md` 只记录实时进度；不要再创建新的日期版
> `STATUS_*`、`HANDOFF_*` 或平行路线文档。

## 1. 权威层级与更新规则

发生冲突时按以下顺序处理：

1. `AGENTS.md` 与安全边界；
2. `configs/experiment_contract.json` 的当前机器门禁；
3. 本文的完整研究目标、阶段依赖和任务树；
4. `docs/PROJECT_AUDIT.md` 的实时状态；
5. 各阶段设计规范；
6. `_retired/` 与 `docs/research/` 中的历史和证据材料。

本文可以随实验发现持续改进，但不得静默改路线。任何 Pipeline 变更必须：

- 给出新证据、导师要求或用户决定；
- 说明影响的任务 ID、数据、baseline、指标和已完成结果；
- 不重写既有实验结果或历史实验来源事件；
- 通过完整性检查并用 `record_change.py` 追加变更或实验运行日志；
- 在本文末尾的变更日志中追加一行。

当前 `experiment_contract.json` 仍是“优先完成 Stage 2、用固定 Stage 3
测误差传播”的阶段性执行合同。本文规定完整项目还必须完成 Stage 1 和 Stage 3。
进入 Stage 3 方法改进前，必须另行更新并核查机器合同；不能仅凭本文绕过现有门禁。

## 2. 不变的最终目标

本项目的最低完整交付不是“给 Sun Stage 2 加一个 LLM”，而是：

1. 独立、可追溯且可复现地重建 Sun 三阶段端到端方法；
2. 每个阶段都有明确输入、输出、Gold、baseline、指标和失败分析；
3. 优先在 Stage 2 比较传统方法、Sun、LLM 和混合方法；
4. 在预先定义的复杂法律语料上检验复杂度是否放大 LLM 优势；
5. Stage 2 完成后，继续比较和改进 Stage 3；
6. 最终用受控消融解释提升来自 Stage 2、Stage 3，还是二者交互；
7. 即使改进方法没有超过 Sun，也交付完整复现、负结果和误差边界。

允许的正式表述是 `method-level independent reconstruction of Sun Stage 2`：核心组件、
处理顺序、输入输出和评价口径与 Sun 对齐即可；作者原代码、原权重和完整私有词典
不可得不再单独阻断方法级复现。只有逐项核实全部公开规则语义时才使用
`paper-faithful`；始终禁止称 `exact reproduction` 或 `Sun original implementation`。

## 3. 研究问题

| ID | 研究问题 | 主要证据 |
|---|---|---|
| RQ0 | 能否完整重建 Sun 的三阶段设计时合规检查方法？ | 三阶段独立测试 + 端到端复现 |
| RQ1 | 多种非 LLM、Sun、LLM 和混合方法在 Stage 2 上如何比较？ | 模态分类与六要素抽取指标 |
| RQ2 | 法律语料复杂度增加时，不同 Stage 2 方法如何退化？ | 复杂度分层曲线与误差类型 |
| RQ3 | Gold 规则输入下，多个 Stage 3 baseline 与 LLM 谁更可靠？ | Oracle Stage 3 匹配与违规分类 |
| RQ4 | Stage 2/3 的局部改进能否转化为端到端提升？ | 固定组件与交叉消融 |

## 4. 完整流程图

```mermaid
flowchart TD
    G0["G0 数据与实验治理<br/>来源/许可/hash/split/Gold/复杂度"]
    BPMN["BPMN 流程模型库"]
    LAW["法律法规语料库"]
    G0 --> BPMN
    G0 --> LAW
    BPMN --> S1A["Stage 1A 结构解析<br/>task/event/gateway/flow/lane"]
    S1A --> S1B["Stage 1B 标签语义<br/>actor/action/business object"]
    S1B --> PR["Canonical Process Record"]
    LAW --> S2A["Stage 2A 模态分类<br/>definition/obligation/prohibition/permission"]
    S2A --> S2B["Stage 2B 六要素抽取<br/>modality/actor/action/condition/constraint/exception"]
    S2B --> RR["Canonical Rule Record"]
    PR --> S3A["Stage 3A 规则—流程匹配<br/>candidate generation + ranking"]
    RR --> S3A
    S3A --> S3B["Stage 3B 违规检测与分类<br/>missing action / incorrect actor / out of order"]
    S3B --> VR["Violation Report<br/>type + evidence + BPMN localization"]
    RR --> C2["Stage 2 组件评价"]
    PR --> C1["Stage 1 组件评价"]
    S3A --> C3["匹配 AP/MAP/Recall@k"]
    VR --> C4["分类 P/R/F1 + 定位"]
    GOLD["Gold Rule/Process Records"] --> ORACLE["Oracle Stage 3<br/>隔离 Stage 3 能力"]
    ORACLE --> S3A
    VR --> E2E["端到端消融<br/>Sun/Sun, Improved/Sun,<br/>Sun/Improved, Improved/Improved"]
```

逻辑上 Stage 1 和 Stage 2 并行产生 Stage 3 输入；项目实施顺序是：

```text
先完成 Stage 2 → 补齐并冻结 Stage 1 → 复现 Stage 3 → 扩展 Stage 3 → 端到端消融
```

## 5. 统一中间合同

### 5.1 Process Record

最低字段：process ID；activities/events/gateways；pools/lanes/actors；sequence
flows；activity label 的 action 与 business object；直接顺序、可达、分支、并行和
order relations；来源 BPMN hash 与解析器版本。

### 5.2 Rule Record

最低字段：sample ID、source text、clause spans、modality、actor、action、condition、
constraint、exception、actor-action map、order relations、schema/method/prompt/rule
version 与 provenance。

### 5.3 Violation Report

最低字段：process/rule ID；matching score；compliant 或一个/多个 violation type；
相关 activity、lane/actor、order pair；可复核证据；threshold/model version；运行
manifest 与输入 hash。

任何方法只有通过相同 canonical contract，才能进入同一评价表。

## 6. G0：数据与实验治理

| 任务 ID | 小任务 | 产物 | 当前状态 | 完成条件 |
|---|---|---|---|---|
| G0.1 | 建立唯一 Pipeline 与文档索引 | 本文、`docs/INDEX.md` | verified | Agent 入口唯一、旧路线移出活动入口 |
| G0.2 | 数据注册 | dataset registry/contract | partial | 每个数据集有来源、许可、hash、schema、split、用途 |
| G0.3 | 方法注册 | 方法 registry | partial | 每个正式方法有命令、状态、LLM 标记和版本 |
| G0.4 | 评价合同 | schema、normalization、evaluator | partial | 方法共享同一 Gold 和 evaluator |
| G0.5 | 复杂度合同 | 文本与 BPMN 复杂度字段 | blocked | 看结果前冻结分层规则 |
| G0.6 | Git checkpoint | 有意创建的版本点 | verified | `formal_experiment/` 已在 checkpoint `bfb0b8a` 纳入版本控制 |
| G0.7 | 前人比较注册表 | citation/method/data/code/license/metric/adapter matrix | ready | 每个引用结果可追到原表或本地重跑 manifest |
| G0.8 | 受控文本哈希可移植性 | 合同 `hash_mode` 声明 + gate 归一化 + 窄 `.gitattributes` + 回归测试 | verified | CRLF/LF 工作树对同一受控文本得到同一 canonical hash；未声明资产仍按原始字节；一字变化 fail closed；Sun modality 许可/溯源边界不变 |

外部数据集必须同时满足：来源/版本可定位、许可允许复用、hash 固定、标签兼容或有
人工协议、split 不泄漏、各方法使用同一测试样本、复杂集在运行结果前选定。

## 7. Stage 1：流程模型拆解

### 方法与 baseline

| ID | 方法 | 角色 |
|---|---|---|
| S1-P0 | 纯 BPMN XML 结构解析，保留原标签 | 结构下限 |
| S1-P1 | 简单 verb-object/规则标签解析 | 轻量非 LLM baseline |
| S1-P2 | Sun/Leopold-style 标签、模型上下文和结构分析 | 正式 Sun Stage 1 |
| S1-P3 | LLM 标签语义解析 | 可选扩展，Stage 2 完成前不启动 |

### 工作分解

| 任务 ID | 小任务 | 依赖 | 当前状态 | Definition of Done |
|---|---|---|---|---|
| S1.1 | BPMN 输入与 Process Record schema | G0.2 | **verified（2026-08-11）** | schema + fixtures + validator |
| S1.2 | activity/event/gateway/flow/lane 解析 | S1.1 | **verified（2026-08-11）** | 对测试 BPMN 稳定输出 + 7/7 GDPR 双跑确定性（s1_1_s1_4_determinism_v1） |
| S1.3 | actor/action/object 标签解析 | S1.2 | **verified（2026-08-13：P0/P1/P2 全部锁定；P2 为 post-Gold, target-aware Sun/Leopold-style 方法级重建（Gold 隔离推断、评分前锁定、评价后未调优；非 strict blind））** | P0/P1 表面切分；P2 语言分析（model context + style recognition + dependency 语义推导）；机器输出非 Gold（Gold 为人工裁决） |
| S1.4 | 控制流和可达关系 | S1.2 | **verified（2026-08-11）** | 分支、并行、顺序测试通过 |
| S1.5 | Stage 1 人工核对样本 | G0.2 | **verified（2026-08-13：7/7 裁决完成 → 用户授权 → 正式 Process Gold 冻结并发布 data/gold/stage1/process_records/stage1_process_gold_v1.json，独立 verifier VERIFIED）** | 固定样本（7 BPMN/45 activities/135 label fields，payload e88caf81…）与人工 Gold （用户 7/7 structure + 135/135 字段裁决后冻结） |
| S1.6 | baseline 评价 | S1.3-S1.5 | **verified（2026-08-13：P0/P1/P2 一次性正式评价完成；claim 已纠正为 fixed-GDPR7 描述性组件评价（非 held-out 泛化证据）；P2 语义 micro F1 0.8185、triple 0.4222 数值未变）** | 结构准确率和语义 P/R/F1 |
| S1.7 | 冻结正式 Stage 1 | S1.6 | **frozen（2026-08-13 用户明确授权：P2 锁定方法、P0/P1/P2 预测、原始指标、Stage 1 Process Gold、正式评价 capsule 全部冻结；授权 manifest s1_7_freezer_authorization_v1.manifest.json；未改 P2/未重算/零 LLM-API/未授权 Stage 3 Oracle）** | 输入/输出/方法/指标/hash 锁定 |

## 8. Stage 2：法规解析（当前主线）

### 8.1 Stage 2A：模态分类

类别：definition、obligation、prohibition、permission。候选 baseline：多数类/随机、
关键词、BiLSTM、CNN/TextCNN、通用/法律域 BERT、Sun BERT-TextCNN、LLM、
分类器 + LLM fallback。主表只保留有代表性的不同范式，同类变体放附录。

### 8.2 Stage 2B：六要素抽取

候选 baseline：marker/regex、spaCy/dependency rules、Sun CoreNLP +
Tregex/Tsurgeon + reconstructed markers、token classifier/CRF（仅在训练 Gold
足够时）、LLM、Sun + field-level LLM fallback。

### 8.3 Stage 2 完整方法

> 2026-08-08 起正式命名直观化（§8.8.3）：`B0 / sun_rule_only → Rules-Only`（纯规则法）、
> `H1 / sun_llm_fallback → Rules+LLM-Repair`（规则+LLM 修复）、`D1 / direct_llm →
> Direct-LLM`（直接 LLM）。新文档一律用正式命名；机器 ID 与 legacy 代号仅用于代码/
> 注册表兼容。Legacy 代号映射：B0 / `sun_rule_only`、H1 / `sun_llm_fallback`、
> D1 / `direct_llm`。

| Legacy 代号 | 正式命名 | 机器 ID | 含义 | 当前状态 |
|---|---|---|---|---|
| B0 | **Rules-Only**（纯规则法） | `sun_rule_only` | 非 LLM 传统流水线：BERT-TextCNN 模态分类 + CoreNLP/Tregex/Tsurgeon 六要素抽取（Sun Stage 2 方法级重建） | B0-R0–R3 verified；B0-R4 formal candidate verified（2026-08-10，Gold-blind runner 绑 formal input v2，双跑语义 byte-identical，主口径 F1 0.71865 与 R3 快照一致）且方法门禁已由用户授权 （methods.json formal_status=ready）；B0-R5 blocked on 正式结果发布 |
| H1 | **Rules+LLM-Repair**（规则+LLM 修复） | `sun_llm_fallback` | 同一 Rules-Only，仅按预注册 trigger 修复失败/不确定字段 | **对照方法（不再深究，2026-08-08 用户确认，§8.8.1）**；development 机制已验证，全量 150 运行主口径 F1 0.7621 vs B0 0.7986（净负） |
| D1 | **Direct-LLM**（直接 LLM） | `direct_llm` | LLM 直接生成同一 Rule Record（端到端，不读取 B0 预测） | D1-R0–R3 verified（主方法，粗 Gold F1 0.8726）；D1-R4/R5 blocked on formal Gold |

正式主表的最低方法覆盖为：简单规则下限、一个强监督学习 baseline、完整 B0、H1、
D1。模态分类与六要素抽取分别选方法，不能用一个只做分类的 baseline 冒充完整
Stage 2。训练 Gold 不足时，CRF/token classifier 只列为条件性扩展，不为凑数量
制造不可训练的 baseline。

### 8.4 数据轨道与复杂度

| 轨道 | 数据 | 用途 | Claim 边界 |
|---|---|---|---|
| S2-R1 | Sun 官方 modality 数据 | 模态分类复现 | development schema/split 已锁定；许可未知，禁止再分发或提前提升为 formal |
| S2-R2 | 项目固定 EStG-150 | 六要素主测试 | 项目独立重建，不是 Sun 原 150 |
| S2-C | GDPR、可复用 Luxembourg 语料、Barrientos 等复杂文本 | 外部验证 | 标签需映射或人工裁决 |

复杂度字段至少包括：长度、clause 数、dependency depth、actor/action 数、
condition/constraint/exception 的数量与嵌套、被动语态、隐含 actor、跨句引用、
原语言/翻译标记。

### 8.5 Stage 2 工作分解

| 任务 ID | 小任务 | 依赖 | 当前状态 | Definition of Done |
|---|---|---|---|---|
| S2.1 | 官方 modality 数据 ingestion/schema/license/split | G0.2 | **verified；A/B-R1/C-R1/D 全部通过** | development machine gate 交叉验证来源、合同、schema、quarantine、hash、split 与许可；formal use 仍未解锁 |
| S2.2 | EStG-150 人工裁决 | human-owned | **verified (2026-08-06)**：150/150 adjudicated（用户 2026-07-18 完成的裁决经用户授权从 56d2b03 历史快照恢复至活动 v2 文件，freeze validator 通过） | 150/150 adjudicated，freeze validator 通过 |
| S2.3 | 重建 public marker lexicon | S2.1 | **verified；英文 public-source v1 已锁定** | 来源、规则、hash、dev-only 扩展策略固定 |
| S2.4 | 完成 BERT-TextCNN | S2.1 | ready after separate dispatch；本轮未启动 | 训练、dev 选择、test 评价可复现 |
| S2.5 | 完成 CoreNLP/Tregex/Tsurgeon extractor | S2.3 | blocked | 六要素规则和 fixtures 通过 |
| S2.6 | 组合并验证完整 B0 | S2.4-S2.5 | blocked | 不调用 LLM，输出 canonical Rule Record |
| S2.7 | 实现代表性非 LLM baseline | S2.1/S2.2 | blocked | 相同输入和 evaluator 可运行 |
| S2.8 | 预注册 H1 trigger/merge/call budget | S2.6 | **不再推进（2026-08-08）**：H1 降级为对照方法（§8.8.1），对照所需机制（development wiring、canary、全量 150 运行 commit 74614e3）已具备；正式 trigger 预注册取消 | 对照臂结果可复现：主口径 F1 0.7621 vs B0 0.7986（净负，证据支持 D1-primary 决策 A）；机制工作正常但 trigger+repair 配方增加 FP 而非召回 |
| S2.9 | 锁定 D1 prompt/few-shot/model/budget | S2.2 | **verified (2026-08-06)** | **D1 侧达成（2026-08-06，D1-R2）**：v6 prompt hash 3aa64877 固定、model/sampling/seed 策略与预算合同锁定于 `configs/models/estg150_d1_active_registry_v1.json`；Gold 不可见（few-shot 为合成 fixture、runner 不读 Gold）；S2.2 frozen（150/150 adjudicated，2026-08-06 恢复后 freeze validator 通过），依赖满足 |
| S2.10 | 主数据组件评价 | S2.2/S2.6-S2.9 | **verified（2026-08-11，授权后 DoD）**：按用户授权 G0.4 口径，模态与六字段指标分别报告已真实完成——主报告=句子级粗粒度五 span 字段（P/R/F1）+ 单独四分类 modality label（accuracy/macro-F1/per-class）逐方法报告，细粒度五字段诊断/对照；modality evidence-span 结构性 unavailable 为授权口径明示项（不置零不纳入 aggregate）；三方法 formal capsule 全部独立 verifier 通过；正式三方法比较报告 stage2_formal_three_method_comparison_v1 已发布并自校验 | 模态与六字段指标分别报告（授权口径完成；历史六字段 aggregate 仅 development provenance） |
| S2.11 | 复杂法律语料集冻结 | G0.5 | **verified / frozen / Gold published（2026-08-17）**：Checkpoint G 完成 proposal v3 用户确认、importer v3 原子导入与 freeze 36/36；随后正式发布 `data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json`（SHA-256 `039ae8b2…`，36/36、0 unresolved、0 blocked）。Gold 逐记录等值复制 adjudicated canonical decisions，不增加/推断/改写标签、span、actor-action map 或 order relation；provenance 明示 `deepseek_offline_proposal_v3` + `user_batch_confirmation`（reviewer=hyc、无 revisions），不得表述为独立专家从零标注。版本化 schema/publisher/manifest/export/capsule/独立 verifier 已建立，publisher fail-closed 覆盖确认事件、proposal、reviewer、freeze、source/proposal drift；重放 byte-identical。提交资产只含 source path/file/text hashes、坐标与必要标签，第三方原文继续 local-only；零 LLM/API；未创建 predictions/results/Gold Rule Records，未启动 Oracle。 | 数据资格、canonical 裁决、冻结与正式 Gold 发布全部验证；S2.11 DoD 完成。 |
| S2.12 | 复杂度分层与误差分析 | S2.10/S2.11 | **partial + execution-ready v3（2026-08-17，Checkpoint F；Checkpoint G 刷新）**：描述性分析保持历史/retrospective；**执行计划 v2 冻结**（`configs/s2_12_execution_plan_v2.json`：预注册 G0.5 L1/L2/L3 分层，supersede v1）；**评估器 v2 对齐正式 Stage 2 合同**（`src/bpc_hybrid/s2_12_stratified_evaluator_v2.py`：modality label acc/macro-F1/per-class + 五字段 Sun literal-overlap span P/R/F1；parity 重跑通过并绑定于 `outputs/reports/s2_12_execution_readiness_v3.json`（re-bind proposal v3/importer v3/确认事件；S2.11 freeze 36/36））；**API readiness v2 dry-run**（两臂 deepseek-v4-pro、max_calls 36/72/总 108、输出 token 4096、输入 token 未文档化、cost_cap_unresolved——**未发出最终授权句**，缺项精确列出）；S2.11 冻结已达成，真实运行仅 refused on API 预算授权（input token cap+cost cap 缺项） | 预注册分层曲线和错误类型（计划 v2 已预注册冻结；描述性部分完成；S2.11=36/36 冻结 done，真实运行仅 blocked on API 授权） |
| S2.13 | Stage 2 冻结 | S2.1-S2.12 | blocked | 方法、数据、Gold、指标、成本、manifest 完整 |

Stage 2 完成时，B0/H1/D1 和选定 baseline 必须共享 test IDs、Gold、schema、
normalization 和 evaluator，并分别报告 modality、phrase 和完整 Rule Record 指标。

### 8.6 B0 方法级复现修复 Pipeline（B0-R0–B0-R5）

本 Pipeline 执行用户在 2026-08-01 明确确认的口径：方法级独立复现可以进入正式
结论，不以取得作者原代码、原权重、完整私有词典或复现作者绝对数值为前提。实施
保持 Sun 的宽松方法边界，不用过度门禁把可解释的规则权衡卡死，但必须先排除确定性
代码错误。

**硬约束仅保留以下六项**：B0 不调用 LLM；不看最终 Gold 反向调规则；span 坐标有效
且文本可回指；同输入可确定性重放；B0/H1/D1 共享输入与 evaluator；每个代码/规则
批次有测试、manifest 或变更日志及 Git checkpoint。缺作者资产、单字段 P/R 回落、
规则词典规模不同或无法达到论文原数值只需披露，不单独阻断方法级复现。

| 任务 | 唯一目标 | 完成信号 | 状态 |
|---|---|---|---|
| B0-R0 | 将实际 B0 方法代码、配置、CoreNLP bridge 与测试整合到当前可审计主线；不整体合并历史数据/输出 | 当前分支存在唯一可运行入口，依赖和版本可追踪，旧 heuristic 不再冒充该入口 | verified |
| B0-R1 | 修复确定性实现错误：Action 任意字符截断、多词 Actor、字符中点分句、德英 cue 验证、错误 fallback、`<`/`<<`、Tsurgeon multi-match | 已完（2026-08-04）：R1-A..C3（半词 span、字符中点分句、Action 截断、required-end 守卫、fatal scope 拒绝）+ R1-E1/E2（主口径 evaluator + v10a/C3 重评）+ R1-ERR（错误分析）+ 七个 §8.6.1 子批次全部闭环（ACTION 已修/质量收益、SCOPE-DISAMBIG 实测拒绝记局限、ALIGN 已修伪 validated、BRIDGE 守卫+测试、ACTOR 已修 +0.0018、LEXICON-DECISION 已实施（用户授权）、CLAUSE-REVIEW 不改动）。DoD 三条验收线全部达成：无半词 span、无伪 validated、无未记录即被剪除的匹配 | **verified** |
| B0-R2 | 对照 Sun 核心方法：BERT-TextCNN、CoreNLP constituency、Tregex/Tsurgeon、公开抽取顺序和六字段输出 | 方法对照表逐项有实现/测试/已披露适配（docs/B0_R2_METHOD_CROSSWALK.md，11 元素）；重建 marker 与德英 adapter 允许使用并记录；`method_conformance_status` 已由用户授权（2026-08-04）改为 `verified_method_level_independent_reconstruction`，`sun_stage2_baseline_not_paper_faithful` blocker 已按设计解除（BLOCKERS 9→8）；Tsurgeon 为诚实非实现（fail-closed 守卫） | **verified（用户授权）** |
| B0-R3 | 在固定 development snapshot 上重跑并做错误分析 | 无 LLM；manifest 锁定代码/配置/输入/evaluator hash；报告 P/R/F1 与失败类型 | **verified（2026-08-04）**：56d2b03 快照运行完成（主口径 F1 0.71865，manifest `…r2_r3_lex_hist56d_v1/`，用户条件授权标记为论文依据候选）+ 最终态错误分析完成（docs/B0_ERROR_ANALYSIS.md §8：失败分布、constraint marker 归因、C2 cue 一致性、label 路由归因；两项不补项及原因记录） |
| B0-R4 | 在与 H1/D1 相同的冻结输入和 Gold 上运行 B0 | 三方法共享 IDs、schema、normalization、evaluator；输出不覆盖 | **formal candidate verified（2026-08-10）**：`run_estg150_b0_formal.py` Gold-blind candidate runner（只读 formal input v2 + 锁定方法资产，不读 data/gold/Layer E 裁决字段），150 条全量运行完成（outputs/development/b0_r4_formal_candidate_v1，claim_scope=formal_candidate_not_yet_authorized_as_formal_result），主口径 F1 0.71865（P 0.6845/R 0.7564，与 B0-R3 development 快照逐位一致=方法语义锁定），双跑语义 byte-identical（预测/主指标/错误分析/config 完全一致，仅性能计时字段不同），evaluator 独立于 runner；**formal promotion 已授权并应用（2026-08-10 用户明确授权：outputs/reports/sun_rule_only_method_gate_authorization_dry_run.json 提议正式应用：configs/methods.json sun_rule_only formal_status→ready、command_status→formal_ready_candidate_authorized；methods.json 其余方法/contract/Stage3/Gold/publication 均未动；release manifest v2 implementation hash 同步重发布）**；未写入正式 predictions/results |
| B0-R5 | 形成论文正式结论 | 结果可为正或负；明确写作“方法级独立复现”，并披露重建资产和适配差异 | **verified（2026-08-11）**：正式结论包 stage2_formal_conclusion_v1（d882a5e2…，verifier 16fd36f5 VERIFIED）+ 三方法正式比较报告（c9d76544…）；描述性字段级结论、无显著性推断、重建披露完整 |

**评价口径**：六字段抽取的 Sun 对照主表采用同字段任意非空字符交叠的
Precision/Recall/F1；不强制 clause alignment，不做一对一 assignment。该口径下
`modality` 只评价 evidence span，忽略标签，因此模态四分类必须另表报告 label
P/R/F1。strict exact、token overlap、clause alignment 和 actor-action edge 作为诊断
面板，不作为阻止方法级 B0 进入正式结论的最低分阈值。

**迭代规则**：B0-R1/R2 的候选允许出现字段间 precision/recall trade-off；不得仅因
一个字段回落就停止整个路线。Agent 必须记录变化、原因和已知代价，再由固定的 Sun
主口径与诊断面板共同判断是否保留。只有代码不正确、方法核心组件缺失、数据泄漏、
输出不可复现或比较口径不一致时才 fail closed。Pipeline 不预设最低 P/R/F1；修复后
仍然较低的结果属于可报告的方法局限。

### 8.6.1 B0-R1 当前子批次（依据 2026-08-04 错误分析）

`docs/B0_ERROR_ANALYSIS.md`（B0-R1-ERR）对 C3 注册 attempts 与 56d2b03 历史
Gold 做了逐 span 失败分类：79%（218/276）的 missed Gold span 内容被抽到其它
字段、80%（280/351）的错误预测压到其它字段 Gold 上；字段归属错误是压倒性失败
模式。据此，B0-R1 剩余工作拆为以下子批次，每批必须：focused tests →
`audit_project.py --with-tests` → 用 B0-R1-E2 同一协议（`sun_literal_overlap_evaluation@2.0.0`、
同一 canonical Gold、同一进程双评）重评 → 记录前后 delta 与原因 → `record_change.py`
→ 独立 commit + push：

| 子批次 | 内容 | 量化证据 | 可修性 | 预期影响 |
|---|---|---|---|---|
| B0-R1-ACTION | 修复 action span 吞并：`actor_action.py` `_subtree_span` 把 nsubj/全部依赖纳入 action，span 中位超 Gold 54 字符（192/212 matched 为过长） | constraint 143 个 missed 中 57 个仅被 action 覆盖；244 个 action 中 8 个以冠词开头 | **已修（2026-08-04）**：实测主口径 F1 +0.00005（持平），质量收益：主语开头 8→0、strict-exact action F1 3.0× | 边界质量修复；主口径非指标驱动项 |
| B0-R1-SCOPE-DISAMBIG | constraint↔condition 双向消歧（scope.py `_SURFACE_SCOPE` 与 Tregex 共享 cue） | 114 个 extra constraint 压 condition Gold、31 个反向；44 个同界双发（43 个双 tregex） | **已实测拒绝（2026-08-04）**：候选真实运行 F1 −0.0005，按迭代规则回退；根因=gold 对 "to the extent"/关系从句语义内部不一致 + registry 模式重叠（`to<<an|the` vs `to<<extent|purpose`），不读 Gold 前提下规则层不可安全消歧 | 记为方法局限；registry 模式复核需用户决策 |
| B0-R1-ALIGN | 德英 cue 验证：equal-count/split 路径"伪 validated"（两侧任意锚即 validated） | evidence 匹配 clause 上 label 准确率 79.3%（definition↔obligation 混淆为主） | **已修（2026-08-04）**：`_cross_validates` 语言学映射+否定极性+数字锚；validated 107→49、"无伪 validated" DoD 达成；主口径指标不变（F1 0.71024）；label 面板 −0.48pp（记录代价）；validated_split 42→0（记录副作用，留待细化） | modality label 面板提升未达成（实测微降），正确性缺陷已修 |
| B0-R1-BRIDGE | `<`/`<<` 关系算子与 Tsurgeon multi-match 消费（当前 registry 无 operation，风险潜伏） | SunPhraseRuleBatchBridgeMulti.java:91-103 单记录/多消费结构 | 可修（离线 fixture） | 消除潜伏错误源 |
| B0-R1-ACTOR | 多词 Actor 生产路径测试 + 依赖边查找修复 + under-extension 边界（C7） | 22 个 missed actor：8 个含词典词（依赖失败）、14 个词典无覆盖；modality evidence 80 个过短 | **已修（2026-08-04）**：clause 内全 nsubj 弧 + obl/by-to + 中心词词典校验；实测主口径 F1 +0.0018（0.71024→0.71205，本系列首个正向 delta），actor F1 0.616→0.670，8/8 漏抽找回；C7 过短边界未含在本批 | actor R 提升已验证；C7 另行跟进 |
| B0-R1-LEXICON-DECISION | actor 等词典扩展、代词/名词 Gold 语义裁决（如 "It" 作 actor） | 13 个无词典覆盖名词 + "It" 代词 | **已实施（2026-08-04 用户授权路径 b）**：13 名词以 `authorized_local_frozen_estg150_gap_2026_08_04` 来源加入词典（治理覆盖严格记录于 sources manifest/actor meta/manifest note/事件）；覆盖/未覆盖 P/R 分别报告（覆盖 47/48：P 0.692/R 0.979/F1 0.811；未覆盖 1/48=代词 "It"，需正式 Gold 裁决）；B0-R3 快照 F1 0.71865（+0.0085 vs 原） | actor R 0.958；唯一残余=代词语义 |
| B0-R1-CLAUSE-REVIEW | clause 规划失配复核（38/231 Gold clause 无 IoU≥0.5 配对） | 与 v2 主口径弱相关；58 个真正漏抽中仅 4 个在未配对 clause | **已复核（2026-08-04）：不改动**（v2 口径不依赖 clause 对齐；修复风险大于收益，C1/C2 批次已顺带观察） | 次要 |

B0-R3 的"固定快照重跑 + 错误分析"仍是正式结论的必要步骤：B0-R1-ERR 的分析为
development 快照提前执行，正式错误分析须在 B0-R2 后按同一主口径重做并登记。

### 8.7 D1 方法级复现修复 Pipeline（D1-R0–D1-R5）

与 §8.6 B0 Pipeline 同构、同门禁纪律。D1 是直接 LLM 方法，因此硬约束为：
**真实 LLM 调用必须逐批用户授权并记录硬预算上限与成本**；不看最终 Gold 反向调
prompt；span 坐标有效且文本可回指；同输入同配置可重放（prompt hash、model、
temperature/seed、max_tokens 全部记录进 manifest）；B0/H1/D1 共享输入与 evaluator；
每个 prompt/代码批次有 focused tests、manifest 或变更日志及 Git checkpoint。
缺作者资产、单字段 P/R 回落只需披露，不单独阻断方法级复现。

| 任务 | 唯一目标 | 完成信号 | 状态 |
|---|---|---|---|
| D1-R0 | 将实际 D1 方法（runner/prompt loader/canonical schema/attempts 产物/manifest）整合到当前可审计主线 | 唯一可运行入口 `run_direct_llm.py` + prompt loader + canonical schema；既有 s28_s29 产物 tracked 且可重评；prompt hash 记录于 manifest | ready |
| D1-R1 | 修复 D1 低召回（整体 R=0.665、constraint R=0.288）的确定性/合同缺陷：省略指令、few-shot 缺 constraint/condition、字段错标引导（99 个 constraint 内容进 action span） | 每个候选：prompt vN 变更 + focused tests + 预算内真实 pilot + 重评 delta + keep/reject 记录（见 §8.7.1） | **verified (2026-08-05)**：v6 KEEP；150 全量 0 事故，F1 0.7669→0.7735，constraint R 0.2881→0.4172；见 s27_d1_v6_verify_pass_150_hist56d_v1 |
| D1-R2 | 对照方法要求：prompt/model/budget 锁定（prompt hash 固定、预算上限合同、temperature/seed 记录）；S2.9 DoD（Gold 不可见、prompt hash 固定）达成 | config 锁定 + manifest 记录 | **verified (2026-08-06)**：`configs/models/estg150_d1_active_registry_v1.json` 锁定 v6 prompt（sha 3aa64877，与磁盘/loader/manifest 三方一致）、deepseek-v4-pro 钉死、temp 0/top_p 1/max_tokens 4096、seed 策略 unsupported_or_omitted、transport 配方（thinking-disabled、无 json_object）、共享输入与 evaluator hash、预算合同（逐批授权+`--max-calls` 硬上限 150）、D1-R1 运行登记；12 项 lock-config 测试含 S2.9 Gold 不可见核查（6 个 few-shot 合成 fixture 与 150 测试句零交叠）；§8.5 S2.9 行 DoD（D1 侧）达成，整行仍 partial（S2.2 未 frozen） |
| D1-R3 | 固定快照干净重跑 + 错误分析 | 无事故 transport；manifest 锁定代码/配置/输入/evaluator hash；报告 P/R/F1 与失败类型 | **verified (2026-08-06)**：锁定配方（estg150_d1_active_registry_v1.json 逐项一致）干净重跑 150/150 有效、0 事故；R1/R3 同一进程双评（sun_literal_overlap@2.0.0）R3 F1 0.7756（P 0.8793/R 0.6938）vs R1 0.7735（+0.0021），复现成功；失败类型分析（1055 gold span：matched 732、wrong_field 169 其中 constraint 100、not_extracted 154）见 docs/D1_ERROR_ANALYSIS.md §8 |
| D1-R4 | 与 B0/H1 相同冻结输入和 Gold 上正式比较 | 三方法共享 IDs、schema、normalization、evaluator；输出不覆盖 | **历史预测绑定核账（2026-08-10）**：D1-R3（s27_d1_v6_r3_clean_rerun_150_hist56d_v1）与 H1（s28d_h1_150_v4pro_v1）的 150 条 predictions 经 b0_d1_formal_readiness_v2 逐项核验——IDs 与 formal input v2 完全一致、输入文本逐条 hash 一致、prompt/model/sampling 与锁定配方一致、snapshot 完整且 schema-valid → **zero-API candidate 重评允许**（不重调 API）；未满足项=无；不把历史预测提升为 formal 结果，正式三方法比较仍待方法门禁（B0 已出授权 dry-run 包，D1/H1 需 LLM 授权） |
| D1-R5 | 形成论文正式结论 | 结果可为正或负；明确写作"方法级独立复现"，披露模型/prompt/预算与适配差异 | **verified（2026-08-11）**：正式结论包（同上）覆盖 D1；披露历史调用 150 + 新增 0、无显著性推断 |

**评价口径**：与 B0 相同——`sun_literal_overlap_evaluation@2.0.0` 主表 + 模态
label 另表。**迭代规则**：候选允许字段间 P/R trade-off；Agent 记录变化、原因与
已知代价，由固定主口径判定保留与否；修复后仍低的结果属可报告的方法局限。

### 8.7.1 D1-R1 子批次（依据 2026-08-04 错误分析，见 docs/D1_ERROR_ANALYSIS.md）

| 子批次 | 内容 | 量化证据 | 预期影响 |
|---|---|---|---|
| D1-R1-FIELD-TYPING | prompt 显式定义 constraint 类别（法律引用/时间/数量限制/"within the meaning of"/"pursuant to"/"subject to"）并禁止并入 action/condition；补 few-shot | 99 个 constraint 内容被 action 吞、16 个进 condition（合计 124 个落错字段） | **done (2026-08-05)**：v6=v5+规则25-27+Ex5/Ex6；pilot 19 配对 F1 +0.0155、constraint F1 +0.0547，KEEP |
| D1-R1-PROMPT-CONTRACT | 规则 14 由"不确定就省略"改为"列出所有候选，不确定的写入 unsupported_or_ambiguous"；补 constraint/condition/exception few-shot（当前 4 例中 condition 0 次、constraint 仅 1 例） | 91 个 constraint + 43 个 condition 完全未抽 | **covered by v5 lineage**：v5 规则 15-19（empty=absent、不确定入 unsupported_or_ambiguous）+ v6 规则 25-27；150 全量实测 constraint R 0.288→0.417 |
| D1-R1-VERIFY-PASS | 两遍法：第二遍仅问"是否遗漏 constraint/condition/exception"（可选，预算翻倍） | 同上 | **done (2026-08-05)**：v6 150 全量 150/150 有效、0 事故；F1 0.7735（+0.0066）、constraint R 0.4172（+0.1291）；两遍法未启用（预算纪律，候选已达标） |
| D1-R1-CLEAN-RERUN | 排除 s28_s29 运行事故影响（lost 104 / recovery 26 / retry 0） | manifest `d1_runtime_incident` | **satisfied by VERIFY-PASS run**：0 lost/recovery/retry，manifest 无 runtime_incident |

每批纪律：prompt/代码变更 + focused tests → 预算内真实 pilot（**逐批用户授权**）
→ 同口径重评 → delta 与原因记录 → keep/reject → `record_change.py` → 独立 commit
+ push。禁止读 Gold 反向调 prompt。

## 8.8 导师汇报确认与方向锁定（2026-08-08）

本节记录 2026-08-08 向导师汇报后确认的四项事实与执行决定。本节是后续论文写作、
消融实验与各 Agent 派工的唯一依据；任何与此冲突的动作必须先更新本节并给出新证据。

### 8.8.1 事实 1：H1（Rules+LLM-Repair）不再深究，仅作为对照

**决定**：H1 降级为**对照方法**，不再作为主方法投入。论文保留其对照臂结果，
用于证明"无证据约束的选择性 LLM 修复会净负，反衬证据约束的必要性"。

**为什么效果不好**（依据 commit `74614e3`，2026-08-08 全量 150 运行，
deepseek-v4-pro，用户授权 150 calls）：
- 主口径（句子级粗 Gold）F1 **0.7621 vs B0 0.7986（−0.0365，净负）**；细 Gold
  F1 0.6875 vs 0.7186（同样净负）；
- LLM 修复在 actor 字段**过度抽取**：P 0.7077→0.2754，actor spans 65→167；
- 其余 5 个字段持平或微升；机制本身工作正常（103 accepted / 89 changed /
  gate=True / 0 incidents），问题出在 **trigger+repair 配方增加 FP 而非召回**。

**困难点**：
1. **trigger 与失败错位**：trigger 只看到推理时信号（低置信、结构冲突、候选多义），
   而 B0 压倒性失败模式是"字段归属错误"（79% 的 missed Gold span 内容被抽到其它
   字段）——这类失败在推理时不可见，Gold-blind trigger 无法对准真正需要修复的样本；
2. **修复难以约束在字段边界内**：请求补 actor 时 LLM 倾向扩大 span、补多个候选，
   把 precision 打穿（actor spans 65→167 的直接原因）；
3. **收益上限受限**：修复收益被触发子集覆盖限制，成本-收益曲线不利。

**优化方向（仅当未来恢复时参考，当前不执行）**：
- 保守修复配方：actor span 长度上限 + 候选数上限 + 修复后 verbatim 回指强制校验；
- 用 risk-coverage 曲线在 development 上选择触发子集，而非全触发；
- 字段级白名单 + patch 前后 diff 约束。

**论文表述**：H1 作为对照臂报告"选择性混合"的负结果；不声称 H1 是贡献。

### 8.8.2 事实 2：B0（Rules-Only）/ D1（Direct-LLM）局限性（列表 + 例子）

**B0（纯规则法，非 LLM）局限性**：
1. **字段归属错误主导**（C1 action 吞并）：matched action 中 192/212 过长、中位超
   Gold 54 字符。例：`"the data shall be processed only to the extent necessary"`
   中整段被并入 action，而 Gold 将 `"to the extent necessary"` 归 constraint。
2. **constraint↔condition 双向混淆**（C2：114 个 extra constraint 压 condition Gold、
   31 个反向），例：`"to the extent"` 双触发。SCOPE-DISAMBIG 候选实测 −0.0005 已回退：
   "不读 Gold"前提下规则层不可安全消歧 → 记为**方法局限**而非代码缺陷。
3. **词典覆盖受限**：13 个无词典覆盖名词漏抽（successor/spouse/child/developers/
   bank/body/society/owners/shareholders/beneficiary 等）；代词 `"It"` 作 actor 需
   Gold 语义裁决（未覆盖 1/48）。
4. **定义范围差异**：我们的 constraint Gold 302 个中仅 13 个（4%）符合 Sun 公开
   marker 定义（Sun 自身仅 35 个）→ 定义口径差异是低分主因之一；Sun-marker 收敛后
   B0 constraint R=1.0 (13/13)、condition R=0.989 (91/92)。
5. **缺 Sun 原资产**：Tsurgeon 为诚实非实现（fail-closed 守卫）；词典规模与分词
   机制为已披露适配。

**D1（直接 LLM）局限性**：
1. **constraint 召回弱**：R1 基线 R=0.288（99 个 constraint 内容进 action span、
   91 个完全未抽）；v6 修至 0.417 仍为最弱字段；R3 失败类型：wrong_field 169
   （constraint 100）+ not_extracted 154（constraint 69）。
2. **actor 泛化误抽**：历史 run P=0.594（69 pred vs 48 gold）。例：表述
   `"the body shall ensure…"` 中抽取无 Gold 交叠的泛指主语作为 actor。
3. **高精度保守型**：细 Gold 口径 P 0.879 vs B0 0.685，但 R 0.694 vs 0.756——
   "宁可漏抽不误抽"在低资源字段（exception/constraint）牺牲召回。
4. **依赖真实 API 与预算合同**：每批需用户授权 + `--max-calls` 硬上限；可复现性
   依赖 transport 配方（thinking-disabled、无 json_object、temp 0）与 prompt hash
   三方锁定。

**对照矩阵（主口径粗 Gold，2026-08-07，同一 Gold 同一 evaluator）**：

| 口径 | B0 P/R/F1 | D1 P/R/F1 | 谁领先 | 可解释原因 |
|---|---|---|---|---|
| 句子级粗 Gold（609 spans，主口径） | 0.7309 / 0.8801 / **0.7986** | 0.9012 / 0.8456 / **0.8726** | **D1（F1 +0.074）** | D1 高精度保持；B0 召回更高（R 0.8801 vs 0.8456） |
| 细 Gold（1055 spans，对照口径） | 0.6845 / 0.7564 / **0.7186** | 0.8793 / 0.6938 / **0.7756** | **D1（F1 +0.057）** | B0 字段归属错误拖低 P；D1 保守漏抽拖低 R |

**结论**：B0 靠规则覆盖全面（R 高）、D1 靠 LLM 精度高（P 高），错误模式互补
（B0 字段归属错、D1 低召回）；但 H1 实测净负（§8.8.1）说明"简单混合"不成立，
主叙事以 D1 为方法主体、B0 为强对照。

### 8.8.3 事实 3：方法命名直观化（B0/H1/D1 → 正式命名）

导师指出 B0/H1/D1 代号不直观，审阅人无法快速理解。自 2026-08-08 起统一使用：

| Legacy 代号 | 机器 ID（不变） | 正式命名（英文） | 中文名 | 一句话本质 |
|---|---|---|---|---|
| B0 | `sun_rule_only` | **Rules-Only** | 纯规则法 | 非 LLM 传统流水线（BERT-TextCNN 分类 + CoreNLP/Tregex 规则抽取），Sun Stage 2 方法级重建 |
| H1 | `sun_llm_fallback` | **Rules+LLM-Repair** | 规则+LLM 修复 | 规则为主，预注册触发器按字段让 LLM 修复；**对照方法** |
| D1 | `direct_llm` | **Direct-LLM** | 直接 LLM | 纯 LLM 端到端生成六要素 Rule Record，不读取规则预测 |

**写作规则**：新文档一律用正式命名；旧文档/代码引用时首次出现给出映射
（如"Direct-LLM（旧代号 D1）"）；机器注册表 `configs/methods.json` 保留 legacy
`id`（代码兼容）并新增 `paper_label` 字段承载正式命名。

### 8.8.4 事实 4：与 Barrientos et al. (2026) 严格对比 + 贡献细模块化（重要）

**背景**：Barrientos et al. (2026) 是**本项目直接借鉴来源**（LLM 结构化输出、
验证、受控词汇、归一化与评估纪律）；Sun et al. (2024) 是三阶段方法学主干。
导师要求：(a) 严格对比 Barrientos 的方法；(b) 消融实验做丰富——"哪个模块缺了
我的不行；把他的模块换成我的模块更好"；(c) 列表跑数据，逐项说明我的好在哪、
他的好在哪、综合谁好；(d) 把贡献拆成细模块讲清楚，**不能只说"调用了 LLM"**
（prompt 只是其中一小部分），方法章节要支撑 4–5 页。

**已锁定的对比事实**（见 `docs/research/BARRIENTOS_BORROWING_AUDIT_2026-07-12.md`
与 `docs/research/BARRIENTOS_LLM_ROLE.md`）：
1. **任务与 schema 不同**：Barrientos=change-impact 表示（precondition/norms/
   temporal_validity）；我们=Sun 六要素 span 抽取（modality/actor/action/condition/
   constraint/exception + evidence span）→ **schema 不能照搬**（已锁定）。
2. **modality 3 类 vs 4 类**：Barrientos 缺 `definition`；我们的 prompt 显式扩展
   4 类并定义触发语义（"主要目的是定义"而非"包含定义"）。
3. **受控词汇**：Barrientos 44 模式 4 维度（control_flow/resource/data/time）约束
   normalized view；我们=public marker lexicon（64 marker）+ 受控 six-field schema
   （normalized view 受控，原文 span 不覆盖）。
4. **评估纪律**：Barrientos 3 维度（semantic coverage / structural encoding /
   deontic correctness）+ **style-equivalent alignment**（表达不同但语义相同算正确）
   + 专家核验（κ=0.52）；我们=span overlap 主口径 + 细/粗 Gold 双口径 + 失败类型
   归因 + label 面板 → style-equivalent 概念列为论文方法学贡献候选。
5. **工程纪律**：strict JSON schema、temperature 0、稳定性测试、deterministic
   normalization → 我们已实现（D1-R2 锁定配方、预算合同、prompt hash 三方一致）。
6. **稳定性实验差距**：Barrientos 20 句×20 次；我们当前 temp0 + prompt hash 锁定，
   正式 5 次重跑稳定性实验**尚未执行** → 列入消融计划 AB-9。

**贡献细模块化（论文方法章节 4–5 页的叙述骨架；禁止只写"调用了 LLM"）**：

Direct-LLM 拆为 8 个可单独叙述/消融的模块：
1. **六要素 schema 与证据契约**：verbatim span 回指（`text == source[start:end]`）、
   clause 内 span、actor-action map、order relations、unsupported_or_ambiguous 兜底
   ——契约决定输出可验证性；
2. **prompt 工程（v1→v6 版本线）**：constraint 六子类显式定义（法律引用/时间/数量/
   "within the meaning of"/"pursuant to"/"subject to"）、empty=absent 语义、禁止并入
   action/condition 指令；v6 实测 constraint R 0.288→0.417（+0.129）。**prompt 只是
   贡献的一部分，不是全部**；
3. **few-shot 合成 fixture 工程**：6 个合成样例覆盖 condition/constraint/exception
   缺口，与 150 测试句零交叠（Gold 不可见保障，S2.9 DoD）；
4. **结构化输出 transport 配方**：thinking-disabled、无 json_object、max_tokens
   4096、temp0/top_p1——150/150 有效、0 事故的可复现调用层；
5. **确定性校验与后处理链**：canonical validator（格式/回指/字段权限）+ span
   canonicalizer（fail-closed unique exact-text re-anchor）——把 LLM 输出转成严格
   契约数据，坏 span/clause/边丢弃并审计；
6. **预算与授权合同**：逐批授权、`--max-calls` 硬上限、manifest 记录 llm_calls/
   max_calls/模型/采样/失败率；
7. **双口径评价协议**：`sun_literal_overlap@2.0.0` 主口径 + 细 Gold（1055 spans）/
   粗 Gold（609 spans，Sun 句子级粒度）双口径 + 失败类型归因（matched/wrong_field/
   not_extracted）；
8. **可复现性资产**：prompt hash 三方锁定（磁盘/loader/manifest）、注册表
   `configs/models/estg150_d1_active_registry_v1.json`。

Rules-Only 的可叙述模块：public marker lexicon 重建（来源/哈希/版本）、模态分类器
（BERT-TextCNN 重建 + marker 路由 + 德英 cue 验证）、CoreNLP 句法/依赖抽取、Tregex
模式注册表、Tsurgeon fail-closed 守卫、actor/action 归属解析（§8.6.1 各批次成果）。

**消融实验矩阵（导师要求"列表跑数据"，全部需逐批用户授权或离线可跑）**：

| 消融 ID | 变量 | 我的设计 vs 替换方案 | 回答的问题 | 状态 |
|---|---|---|---|---|
| AB-1 | prompt 字段定义 | v6 全字段定义 vs 去掉 constraint 子类定义 | 字段定义对 constraint R 的贡献（已有证据：v5→v6 0.288→0.417） | 部分有证据，正式表待补 |
| AB-2 | few-shot | 6 合成 fixture vs 0-shot vs Barrientos 风格样例 | few-shot 对低资源字段的价值 | 待跑 |
| AB-3 | modality 类别 | 4 类（Sun）vs 3 类（Barrientos 投影） | `definition` 类的独立价值 | 待跑（离线可评） |
| AB-4 | 受控词汇 | 六字段受控 schema vs 移植 Barrientos 44 模式 dual-view | 我的归一化约束 vs 他的 pattern 约束 | 待跑 |
| AB-5 | 校验链 | 有 validator/canonicalizer vs 无（裸 JSON 采纳） | 确定性后处理对有效率的贡献 | 可离线推理 |
| AB-6 | transport | thinking-disabled/无 json_object vs 默认配方 | 事故率与可复现性 | 已有 0 事故证据，可整理 |
| AB-7 | 评价口径 | 细 Gold vs 粗 Gold vs Sun-marker 收敛 | 口径敏感性（已有 0.7186/0.7986、0.7756/0.8726） | 有证据，整理成表 |
| AB-8 | B0 模块 | lexicon 逐来源（Sleimi/LexNLP/Wiktionary）、marker 路由、跨语言验证开关 | 每个规则模块的边际贡献 | 部分有证据（R1 各批次） |
| AB-9 | 稳定性 | 5 次重跑 agreement（对照 Barrientos 20 次） | 成本-收益的稳定性保证 | 待授权 |
| AB-10 | style-equivalent 评估 | 开启 vs 关闭该评估维度 | 评估鲁棒性（借鉴 Barrientos 的贡献） | 待实现 |

**输出要求**：每项消融至少一行结论表——「我的模块 vs 换 Barrientos 模块 vs 去掉
模块」三列指标，并写"我的好在哪里 / 他的好在哪里 / 综合谁好及原因 / 可比较性限制
或口径差异"。跨 schema、跨任务或跨口径的 AB-3/AB-4 类比较不得由单一数字宣称谁更
好，只能报告各自口径内结果和定性适配结论。全部以 development/授权预算内真实或离线
方式运行；涉及真实 LLM 的消融逐批授权。

### 8.9 最终执行总控（2026-08-08 审计收敛）

本节固定全项目的唯一执行路线。既有 `G0.x`、`S1.x`、`S2.x`、`B0-Rx`、`D1-Rx`、
`S3.x`、`PWx` 与 `E00/E10/E01/E11` 是唯一可派工、可记录、可进入 manifest 的任务
ID；不得另建 A/B/C/P/D 等第二套主键。`Rules-Only`、`Rules+LLM-Repair`、`Direct-LLM`
是论文名称，B0/H1/D1 仅为 legacy 追溯代号。

**G0 核账，不重复锁定。**下列资产已存在且不得重新定义：canonical Rule Record
schema、`sun_literal_overlap_evaluation@2.0.0` evaluator、粗 Gold 主口径/细 Gold
对照口径的用户决定、D1 的 prompt/model/sampling/transport/budget 锁定，以及 B0/H1
的 development manifest 纪律。只补以下三个缺口：

| 挂靠 ID | 最小补缺 | 规则 |
|---|---|---|
| G0.4 | 双口径评价合同 | 固化粗 Gold 主口径、细 Gold 对照口径、适用指标和禁止混表规则；不改 Gold |
| G0.4 | shared comparison capsule | 复用现有 150 输入资产及 hash（D1 registry 的 `c7dffcc4...` 为候选引用），新建 manifest 而非复制输入；显式绑定 B0/H1/D1 的 input/Gold/schema/normalization/evaluator hash |
| G0.7 | Barrientos adapter 注册 | 记录 schema/标签/数据/指标/许可、adapter 边界、映射、hash 与可比较性限制 |

**Stage 2 正式比较与 Barrientos 专项。**B0-R4/D1-R4 是正式共同运行，B0-R5/D1-R5
才形成论文结论；H1 已停止优化，仅作为对照。H1 的正式对照来源不得预设：formal
Gold 发布后，先核验现有 Gold-blind prediction capsule 是否与 shared comparison capsule
逐项一致；一致时仅做 zero-API 重评并新登记 manifest，不一致时只能在用户逐批授权和
硬预算下重跑。不得把现有 development 数字提升为 formal。

Barrientos 专项使用 `S2-BARR-*` 作为 S2 工作包子任务名，不取代现有 S2 主任务：

| 子任务 | 目的 | 最低产物/门禁 |
|---|---|---|
| S2-BARR-1 | G0.7 的专项适配注册 | schema、标签、数据、指标、许可、adapter 边界和 hash |
| S2-BARR-2 | Barrientos-style adapter | 输出映射到 canonical Rule Record；映射测试和 manifest 完整 |
| S2-BARR-3 | 同数据比较 | 仅在 shared capsule 后运行；报告质量、逐字段、合法率、稳定性、成本、延迟和 Stage 3 可用性 |
| S2-BARR-4 | AB-1--AB-10 模块消融 | 按现有状态分批；真实 LLM 项逐批授权，跨任务项保留可比较性限制 |
| S2-BARR-5 | 稳定性与 style-equivalent 补充 | 重跑协议、成本与评价边界冻结 |

Barrientos 专项轨道与 §10.3 证据等级正交：`L1` 表示同一 frozen IDs/Gold/schema/evaluator
的专项共同重跑，通常可满足 C1 但仍需逐项核验；`L2` 表示资格、许可、标签映射和 Gold
均通过的共同复杂数据轨道，可能属于 C1 或 C2；`L3` 仅引用论文报告值，通常只能按 C3
背景处理。跨任务、跨 Stage 或不可统一口径的比较始终是 C4，禁止用数值直接证明优劣。

**Stage 3 双轨与 formal Gold 交叉门禁。**可受控并行的仅是 `S3.1 -> S3.2/S3.3` 的
BPMN 身份与 Gold 治理，以及明确标注 development 的 wrapper/baseline 实现准备。S3.4
的正式完成仍依赖 S1.7/S2.13；S3.7 必须区分 development Oracle 和正式 Oracle 主表：
前者只能使用 development 输入/Gold 且不得进入正式结果，后者还要求 formal Gold
publication、S1.7、S2.13 和 S3.4-S3.6 完整完成。S3.8-S3.11 不得提前启动。

```text
S2.2 annotation freeze + route locked + stage2 dataset locked
  + S3.1/S3.2/S3.3 完成并经授权重锁 stage3.status
  + freeze policy 重核 + publication gate 精确进入白名单
    -> formal Gold publication
    -> shared comparison capsule
    -> B0-R4 / D1-R4 / 条件成立的 H1 zero-API re-evaluation
    -> S2.10 -> S2.12 -> S2.13
    -> S3.7 formal Oracle -> S3.8/S3.9 -> S3.10 -> S3.11
```

完成 S3.1-S3.3 不自动授权 `stage3.status=locked`；状态翻转必须通过合同变更、完整检查、
日志、Git checkpoint 和明确授权。最终归因只使用既有 E00/E10/E01/E11，且 Oracle 与
end-to-end 必须分表。论文仅并行 PW1-PW6；PW7-PW9 只由对应 formal manifest 回填。

## 9. Stage 3：匹配、违规检测与分类

### 9.1 Stage 3A：规则—流程匹配

候选方法：TF-IDF/BM25、Winter fitness/cost、Sun semantic matching、embedding +
graph features、cross-encoder/reranker、LLM 或 Sun-candidate + LLM rerank。
主指标保留 AP/MAP，可增加 Recall@k 和 nDCG@k。

### 9.2 Stage 3B：违规检测与错误类型分类

共享标签：compliant/none、missing_action、incorrect_actor、out_of_order。
候选方法：词法 + BPMN 图规则、Winter、Sun、embedding + graph rules、LLM、
Sun candidate + LLM verifier。复杂扩展允许 multi-label。

Stage 3 正式主表至少覆盖：词法/检索下限、Winter、完整 Sun、一个现代
embedding/graph baseline；LLM 与 Hybrid 在 Oracle 非 LLM 比较稳定后加入。每种
方法必须同时说明它解决 Stage 3A、Stage 3B，还是二者，避免把 matching 分数和
错误类型分类指标混成一个结果。

### 9.3 数据轨道

| 轨道 | 数据 | 设计 |
|---|---|---|
| S3-R | Sun-compatible GDPR replication | 识别原 4 BPMN；单一人工注入违规 + negatives |
| S3-X1 | 本地全部 7 个 GDPR BPMN | 明确称 all-seven extension |
| S3-X2 | Barrientos 三个复杂 BPMN | 只在共享标签上直接比较；其它标签单列 |
| S3-X3 | 后续公开复杂流程 | 必须通过 G0 门禁 |

### 9.4 Oracle 与 end-to-end

Oracle Stage 3 使用 Gold Rule/Process Records，只评价 Stage 3；end-to-end 使用
B0/H1/D1 的预测 Rule Records，评价误差传播。两种结果必须分表。

### 9.5 Stage 3 工作分解

| 任务 ID | 小任务 | 依赖 | 当前状态 | Definition of Done |
|---|---|---|---|---|
| S3.1 | 确定原 4 个/扩展 7 个 GDPR BPMN | G0.2 | **verified（2026-08-08）**：7 个 Winter-provenance GDPR BPMN 从 56d2b03 checkpoint 以 byte-exact（LF）恢复至 `data/input/stage1_stage3/gdpr7/`；合同 `configs/datasets/stage1_stage3_gdpr7_v1.json`（user-approved 2026-07-18）hash 全匹配；`verify_stage1_stage3_gdpr7.py` 通过（7 byte-exact BPMN、45 activities、135 blank label fields）；audit pass `stage1_formal_bpmn_membership_locked`；claim=all-seven extension（非 Sun 原 4） | 文件名、hash、claim 固定 |
| S3.2 | 锁定 matching Gold | S3.1 | **decision Gold 已发布（2026-08-08 裁决冻结；2026-08-10 随 formal Gold publication 发布 `data/gold/stage3/stage3_matching_gold_v1.json`，25 条，与 frozen correction `3310d624…` 一致）**：11 相关 / 14 不相关（含负例）；correction 文件 data/development/human_review/stage3_gold_annotation_human_correction_v1.json；冻结 manifest s32_s33_gold_annotation_freeze_v1.manifest.json；这些 relevance decisions ≠ Gold Rule Records | rule-process relevance decision Gold 完整；Gold Rule Records 另行人工裁决 |
| S3.3 | 锁定 violation Gold | S3.1 | **decision Gold 已发布（2026-08-08 裁决冻结；2026-08-10 随 formal Gold publication 发布 `data/gold/stage3/stage3_violation_gold_v1.json`，33 条，与 frozen correction 一致）**：missing_action 11 / incorrect_actor 11 / out_of_order 11；negative（合规）判定随 matching 负例与裁决记录；这些 type/evidence decisions ≠ Gold Rule Records | type、evidence、negative decision Gold 完整；Gold Rule Records 另行人工裁决 |
| S3.4 | 完成 Winter wrapper | S1.7/S2.13 | **development wrapper verified（2026-08-08）**：Winter 2020 原型语义转写 + 可移植重放（reachability 双模式、manifest 1.1.0、export index、evidence capsule outputs/evidence/s34_winter_stage3_development_v3_clean\|prototype_literal/）；修复后重放 v3_clean/v3_prototype_literal（inference pack check_type 路由、公共 evaluator 口径）；DEV_ONLY：MAP 0.6429/binary F1 0.6111、violation macro 0.373（两模式 out_of_order 无差异）；**S1.7 依赖已满足（2026-08-13 frozen）；formal completion 仍 blocked on S2.13** | formal canonical I/O + reproducible command |
| S3.5 | 完成 Sun Stage 3 | S3.1-S3.3 | **development implementation verified（2026-08-08）**：Def 4-7 方法级独立重建 + 契约/评价修复（Gold-blind inference pack、check_type 路由、Def 6 论文存在性语义（C=process actor+bs_obj 近似披露）、unobservable 按 check_type 统计（v2：33→10，before/after 对照）、sensitivity 真实重算）；run s35_sun_stage3_development_v2（evidence capsule 含 5 方法 comparison）；DEV_ONLY：MAP 0.8175、binary F1 0.0（如实）、violation macro 0.389/exact 0.364/unobs 10（均较 v1 口径修正）；**S1.7 依赖已满足（2026-08-13 frozen）；formal completion 仍 blocked on S2.13** | 不再是 fixture approximation；formal Oracle 主表待 formal Gold 门禁 |
| S3.6 | 完成代表性非 LLM baseline | S3.2/S3.3 | **development baseline verified（2026-08-08）**：BM25（v3 candidate-specific：MAP 0.6595/binary F1 0.0；v1/v2 因忽略候选文本标记 superseded_invalid_candidate_agnostic_similarity，不入有效比较/论文）+ TF-IDF/SVD（v2 保留：MAP 0.5881/macro 0.542，经验证不受共享 scorer ID 修复影响）；双域 sims（action/actor 独立候选池）、真实 ID 映射、check_type 路由、sensitivity 重实例化 scorer；阈值 0.5=fixed development setting（非 blind preregistration）；evidence capsule v3/v2；**S1.7 依赖已满足（2026-08-13 frozen）；formal completion 仍 blocked on S2.13** | 相同 Gold/evaluator；正式 baseline 待 formal Oracle 门禁 |
| S3.7 | Oracle Stage 3 比较 | S3.4-S3.6 + formal Gold publication | blocked（development Oracle 可先行；**2026-08-17 过渡核账：formal_oracle_started=false、formal_oracle_authorized=false、ready_for_oracle_authorization=false、authorization_sentence=null、no_pseudo_oracle=true**；9 个 GDPR rule IDs（article6/7/15/16/17/20/22/33/34）的正式 Gold Rule Records 不存在（matching/violation decision Gold ≠ Gold Rule Records）；S2.11=36/36 frozen 已完成、S2.12 真实运行仅 blocked on API 授权；详见 outputs/reports/s2_13_s3_7_transition_readiness_v7.json（当前 fail-closed capsule；v6 为上一版本、v1-v5 为历史 provenance）） | 正式 Oracle 主表隔离 Stage 3；development 结果不得替代本表 |
| S3.8 | LLM/Hybrid Stage 3 预注册与实现 | S3.7 | blocked | prompt、预算、重复次数固定 |
| S3.9 | 复杂 BPMN 与多违规扩展 | G0.5/S3.7 | blocked | 复杂度和标签在结果前冻结 |
| S3.10 | end-to-end 误差传播 | S2.13/S3.7 | blocked | B0/H1/D1 进入同一 Stage 3 |
| S3.11 | Stage 3 冻结 | S3.1-S3.10 | blocked | 数据、方法、Gold、指标、manifest 完整 |

## 10. 实验矩阵

### 10.1 组件实验

| 实验 | 固定 | 改变 | 回答问题 |
|---|---|---|---|
| EXP-S1 | BPMN 与 Process Gold | Stage 1 方法 | 流程解析可靠性 |
| EXP-S2A | modality 数据与 Gold | 分类 baseline | 句子级分类能力 |
| EXP-S2B | EStG-150 与 span Gold | 抽取 baseline | 六要素抽取能力 |
| EXP-S3-O | Gold Process/Rule Records | Stage 3 方法 | Stage 3 独立能力 |
| EXP-S2-E2E | 固定 Sun Stage 1/3 | B0/H1/D1 | Stage 2 误差传播 |

### 10.2 最终归因消融

| ID | Stage 2 | Stage 3 | 作用 |
|---|---|---|---|
| E00 | Sun | Sun | 完整 Sun 重建基线 |
| E10 | 最佳 Stage 2 改进 | Sun | Stage 2 单独贡献 |
| E01 | Sun | 最佳 Stage 3 改进 | Stage 3 单独贡献 |
| E11 | 最佳 Stage 2 改进 | 最佳 Stage 3 改进 | 完整改进系统与交互 |

### 10.3 与前人结果比较的四级证据

| 级别 | 做法 | 是否允许直接宣称优劣 |
|---|---|---|
| C1 同测集重跑 | 前人方法和本项目方法跑同一 frozen IDs/Gold/evaluator | 可以，是主比较 |
| C2 官方数据复现 | 在前人公开数据上独立重跑，并完整记录版本与 split | 可以，但只限该数据轨道 |
| C3 论文报告值 | 只抄录论文原表，数据/split/evaluator 未完全统一 | 只能描述，不能作严格显著性结论 |
| C4 跨阶段/跨任务 | Stage 2 与 Stage 3，或标签/指标不同 | 禁止用数值高低证明方法优劣 |

Sun 在 Stage 2 与 Stage 3 使用的输入、Gold 和指标不是同一评价问题，必须分表。
如果 Sun 或其引用文献有公开数据，先通过 G0 数据门禁，再把前人方法与本项目方法
共同重跑；不能把“本项目复杂集上的 LLM 结果”直接减去“前人简单集上的论文数字”
当作提升。前人比较注册表至少记录：论文版本、阶段、数据版本、样本范围、标签、
split、指标定义、源码/权重可得性、许可、适配器、复现忠实度和本地 manifest。

## 11. 评价与统计控制

- 所有方法共享 frozen IDs、Gold、schema、normalization 和 evaluator；
- train/dev/test 与 few-shot examples 隔离；
- threshold、prompt、marker 和 fallback trigger 只在 train/dev 确定；
- LLM 报告模型版本、temperature、重复次数、成本、延迟和失败率；
- 复杂度分层在看 test 结果前冻结；
- 同时报总体、逐类、置信区间/显著性和错误案例；
- 负结果照实报告，不通过改 Gold、阈值或删样本制造优势。

## 12. 实施里程碑与当前主线

| 里程碑 | 内容 | 当前状态 |
|---|---|---|
| P0 | Pipeline、文档入口与目录治理 | verified；日志/检查制度已有回归测试保护 |
| P1 | Stage 2 数据、Gold、复杂度合同 | 主数据与 Gold 已完成：EStG-150 150/150 adjudicated（2026-08-06）、formal Gold 已发布（2026-08-10）；**复杂度合同 G0.5 与复杂语料资格 S2.11 仍未完成**（2026-08-15 核账） |
| P2 | 完整 B0（Rules-Only） | **方法、正式 arm 与比较证据已完成**：B0-R0–R4 verified、B0-R5 正式结论 2026-08-11 交付（`b0_formal_arm_v1` claim_scope=formal、独立 verifier 通过）；B0-R5 的论文写作部分由 PW7 回填，无剩余实验任务 |
| P3 | Stage 2 多 baseline | **三方法正式比较已完成**（`stage2_formal_three_method_comparison_v1`，2026-08-11）；复杂数据扩展未完成（S2.11 blocked） |
| P4 | Rules+LLM-Repair（对照）/ Direct-LLM 与 Stage 2 复杂集 | Direct-LLM：**正式 arm 已发布**（`direct_llm_formal_arm_v1`，2026-08-11，zero-API）；Rules+LLM-Repair：**comparison-only（§8.8.1）**，H1 正式 arm 已发布为对照臂；复杂集（S2.11）仍 blocked |
| P5 | Stage 1 完整实现与评价 | **S1.1–S1.7 已完成（S1.7 frozen，2026-08-13 用户授权；正式 Process Gold 已发布，P0/P1/P2 正式评价与 target-aware claim 已 verified）** |
| P6 | Sun/Winter Stage 3 复现 | **development 完成（S3.4/S3.5/S3.6）；formal 复现 blocked on S2.13 与缺失的 9 个 GDPR Gold Rule Records** |
| P7 | Stage 3 多 baseline 与复杂扩展 | blocked on P6；development baseline 已就绪（BM25 v3 / TF-IDF-SVD） |
| P8 | 最终端到端消融 | blocked on P4/P7 |
| P9 | 论文写作与可复现包 | 非结果章节 in_progress；结果/结论 blocked on P8 |

实验 Agent 应优先从 P1/P2 选择最小可验证任务；论文 Agent 只领取
`PW1`–`PW6` 中已解锁的非结果章节。未经合同变更，不要提前启动 Stage 3 LLM，
也不要因 Stage 3 尚未就绪而修改 Stage 2 Gold 门禁。

### 12.0 下一真实路径（2026-08-17 核账，见 `outputs/reports/s2_13_s3_7_transition_readiness_v7.json`（当前 fail-closed capsule；v6 为上一版本、v1-v5 为历史 provenance））

`final_experiment_ready=true` 仅代表 Stage 2 三方法正式评价/最终指标机器门禁
就绪；S1.7 已 frozen（2026-08-13）但 **S2.13 仍 blocked、S3.7 正式 Oracle 未启动
未授权**。通往 S3.7 formal Oracle 的真实路径依次为：

1. **S2.11/G0.5/S2.12 完整依赖**：完成或经用户正式决策处理外部复杂语料许可、
   数据激活授权、3→4 标签映射、人工 Gold、G0.5 复杂度规则结果前冻结与
   Barrientos adapter（S2-BARR-2）；**当前决策入口为
   `outputs/reports/s2_11_formal_gold_v1.manifest.json` + `data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json`**（proposal/review 入口仍保留 `s2_11_proposal_report_v3.json` + `s2_11_batch_import_dry_run_v3.json`；Checkpoint B 打开空白 review surface；Checkpoint C 封闭 review 人口 40/4/36；Checkpoint E1 建立 canonical v2 模型；Checkpoint F 生成 proposal v3 并完成六条定点校正；Checkpoint G 用户确认 proposal v3 → importer v3 `--apply` 原子写入 36/36 adjudicated + freeze validator v3 frozen=true；本次正式 Gold publisher 从冻结 decisions 等值派生 36/36、独立 verifier 27 项全过、重放 byte-identical；**Checkpoint E3 交付 S2.12 plan/readiness v2，Checkpoint F 重跑 parity 并 re-bind readiness v3，Checkpoint G 刷新 readiness v3**）；候选运行 `outputs/reports/s2_11_candidate_run_v1.json`；Checkpoint A 应用门禁 `outputs/reports/s2_11_gates_applied_checkpoint_a_v1.json`；v6 及更早为历史安全基线）：论文许可已确认（CC BY 4.0，article-only，出版社 PDF 证据链
   hash 绑定）；artifact code/data 许可仍 unknown_pending_confirmation；
   映射选项 M1（modality identity candidate ONLY）已应用/M2（未应用）；
   **G0.5 已冻结**（`configs/g05_complexity_frozen_v1.json`，frozen_for_future_external_complex_corpora，密封 v6 链验证；draft 61938c99… 保留为历史，语义 hash 51a6e4fe… 永不使用）；v6 封闭 frozen 授权链
   （classify_frozen 无 caller-supplied validation result、每次调用从磁盘
   重验 manifest/授权事件/prior-results 证据，手工 64-hex 字典被拒）；历史
   capsule v3/v4/v5 固定 origin commit 锚点（31ac757d…/8e8b488e…/7883739…，
   硬编码 SHA-256 map，与 HEAD 无关）；adapter 为 hardened v6
   synthetic/shadow implementation verified（严格 mode 枚举、真实文件级
   evidence binding、formal_evidence_provenance、受控 scope 枚举、
   resolved-path 逃逸防护）；分离门禁 G1–G6（G1/G2/G3/G4/G6 已应用，G5=applied_review_surface_open；**S2.11=verified/frozen/Gold published（36/36；Gold SHA `039ae8b2…`）**；**S2.12=partial + execution-ready v3（S2.11 dependency done；复杂语料三臂运行尚未完成）**）；
2. **S2.13 冻结**（DoD 不变：S2.1–S2.12 完整）；
3. **GDPR Gold Rule Records 人工裁决与冻结**：由用户完成 9 个 rule IDs
   （article6/7/15/16/17/20/22/33/34）的正式 Gold Rule Records；Agent 不得创建、
   推断或自动填写；
4. **S3.4–S3.6 正式 promotion/readiness**（S1.7 依赖已满足）；
5. **单独申请 S3.7 formal Oracle 授权**：授权句只能由用户作出，当前
   `authorization_sentence=null`；在以上实质依赖完成前，`ready_for_oracle_authorization`
   保持 false。

本轮（2026-08-15）只做核账与 readiness 加固，未翻转上述任何正式 gate。

### 12.0b S2.11/G0.5 授权前工程收口（2026-08-15，v5 纠正，见 `outputs/reports/s2_11_g0_5_pre_authorization_v5.json`；**v5 为历史 checkpoint，当前入口为 v6，见 §12.0c**）

本轮工程成果（均未翻 gate）：(1) **v4 红测修复与历史 capsule 生命周期**：
v4 变更事件如实记录 3 failed / 2057 passed / 24 skipped、test_returncode=1、
integrity_pass=false（v3 历史正例测试在 v3 绑定资产演进后按 fail-closed
设计拒绝）；v5 引入 `src/bpc_hybrid/capsule_lifecycle.py` 集中语义——v3/v4
核心资产（schema/builder/verifier/4 outputs）逐字节不变（git 证明），v3/v4
pytest 文件仅按生命周期语义修正（历史 builder no-overwrite fail-closed、
历史 verifier 拒绝且失败项属于声明性 binding drift、历史负例测试继续真实
执行、active v5 builder/verifier 从当前磁盘成功重建/验证）；v5 全量审计
恢复 exit 0。(2) **许可分离**：论文许可已确认（CC BY 4.0 article-only，
PDF hash 绑定），artifact code/data 仍 unknown_pending_confirmation、
project_activatable=false、ready_for_data_activation=false、激活授权句 null。
(3) **adapter 加固（v5）**：严格 mode 枚举（INVALID_MODE）、真实文件级
evidence binding（相对安全路径 + 原始字节 SHA-256 + ID/kind/scope + 授权
manifest 精确绑定 policy/modality/field mapping/license hash）、可验证字段级
provenance（精确 element、确定性 locator `record_path#element`、重叠 span
ambiguity）；formal 正例仅用 tmp 临时文件；当前磁盘仍拒绝一切 formal 转换；
synthetic/shadow implementation verified（68 项真实执行测试）。(4) **M1/M2
精确范围**：M1 仅授权三类共享 modality identity candidate mapping；结构
映射需独立 G6；M2 不映射任何外部 label。(5) **G0.5 promotion readiness**：
`draft_config_sha256`（原始字节）= `61938c99…` 是唯一授权 hash 域（语义
hash `51a6e4fe…` 被 validator 拒绝）；`validate_frozen_application` 只对
真实文件原始字节算 hash；`classify_frozen` 仅接受完整验证结果（含不可伪造
validation_token）；`derive_promotion_readiness` 必须验证完整资产组合而非
glob 文件名；当前磁盘推导 draft_not_frozen /
promotion_ready_for_application=false / missing=user authorization
manifest；不创建真实 frozen config 或授权 manifest。(6) **gate 顺序**：
G3 ready=true（dry-run）、G4 ready=true（句子绑定原始字节 hash，仅授权未来
gate-application checkpoint、本轮不 frozen）、G5 protocol_ready=true 但
ready=false/sentence=null（条件式 future sentence）、G6 ready=false。
本轮零新增 LLM/API，references/ 只读未激活，S2.11/S2.12/S2.13/Stage 3
gate 均未改变，未生成 S3.7 Oracle 授权句。

### 12.0c S2.11/G0.5 授权链封闭与固定锚点（2026-08-15，v6，见 `outputs/reports/s2_11_g0_5_pre_authorization_v6.json`）

本轮工程成果（均未翻 gate）：(1) **frozen 授权链封闭（v6）**：v5 的
caller-supplied validation-result 解锁方式被本轮反例推翻——手工字典
`{frozen_application_valid: True, validation_token: <任意 64 位小写 hex>,
approved_frozen_config_sha256: <真实 frozen hash>}` 在 v5 下可返回
status="frozen"；v6 移除该参数：`classify_frozen` 每次调用从磁盘原始字节
重验 draft/frozen config、授权 manifest、append-only 授权事件与
prior-results 证据扫描（`derive_prior_results`，按确定性路径/manifest 规则
推导，不再接受 caller bool）；授权 manifest 必须完整绑定 schema/version、
manifest ID、authorization_applied=true、精确批准 scope 枚举
（future_external_complex_corpora_only）、精确批准 G4 dry-run 句全文及其
UTF-8 SHA-256、draft/frozen 相对路径 + 原始字节 SHA-256、
retrospective_use_forbidden / frozen_before_new_results /
s2_10_retrospective_use_forbidden、重推导 prior-results 扫描、
授权事件（ID+路径+原始字节 SHA-256）与 pending（未应用）checkpoint；
全部变体（另一 manifest 的 token、manifest 修改后旧 token、manifest 与
config 不匹配、句/scope/事件/路径被替换、先出结果后构造授权、仅布尔/伪造
hash 声称已验证）均被拒；普通内容 hash 只证明字节一致，不被当作用户授权
证明。(2) **历史 capsule 固定锚点（v6）**：v3/v4/v5 核心资产逐字节不变，
锚定固定 origin commit（31ac757d…/8e8b488e…/7883739…）+ 硬编码 21 项
SHA-256 map（`src/bpc_hybrid/capsule_lifecycle.py`）；磁盘字节必须匹配
固定 map 且 origin-commit blob 必须匹配固定 map；新增回归测试证明
“HEAD 与磁盘同时被替换为同一错误字节”仍失败（v5 的 HEAD 相对检查无法发现
该场景）；v6 report/manifest 绑定三版固定 hash。(3) **adapter evidence
provenance（v6）**：evidence verifier 返回结构化 EvidenceContext；formal
输出新增 `formal_evidence_provenance`（license evidence ID/相对路径/原始
字节 SHA-256/精确 license scope；authorization manifest ID/相对路径/原始
字节 SHA-256/精确 authorization scope；授权事件 ID/路径/hash；policy ID；
modality/field mapping canonical hash；manifest 对 license evidence 的
绑定；candidate_only=true、gold_authorized=false）；synthetic mode 为
null；scope 使用受控枚举（LICENSE_SCOPES / AUTHORIZATION_SCOPES，
授权 scope 例 s2_11_candidate_mapping_only），manifest 必须精确复述
license evidence scope，article-only scope 不满足 artifact code/data
要求（LICENSE_SCOPE_NOT_ARTIFACT_COVERING）；evidence 路径 resolve()
后必须仍在 evidence root 内（symlink/junction 逃逸 →
EVIDENCE_PATH_ESCAPE）；当前真实磁盘无合格 evidence，一切真实 formal
调用仍被拒。(4) **v5 事实如实记录**：v5 全量审计确实为绿（最终 receipt
`2118 passed, 24 skipped, 19 warnings in 941.91s`），v5 不是红测
checkpoint，其历史事件保留；v5 的 hand-built validation-result 防护声明
被本轮反例推翻（与审计绿灯分开记录，不混为一谈）。(5) **G0.5 未冻结**：
授权 hash 域仍为原始字节 61938c99…，语义 hash 51a6e4fe… 永不使用；
G3/G4 仍仅 dry-run；G1/G2/G5/G6 ready=false+null；S3.7 全 false/null。
本轮零新增 LLM/API，references/ 只读未激活，Gold/contract/methods/
predictions/results 未改，S2.11/S2.12/S2.13/Stage 3 gate 均未改变，未
生成 S3.7 Oracle 授权句。

### 12.0d S2.11/G0.5 非 API 决策应用与 G0.5 冻结（2026-08-17，Checkpoint A，见 `outputs/reports/s2_11_gates_applied_checkpoint_a_v1.json`）

用户转发授权原句 `除了用apikey的时候要授权，其他直接正常进行即可。`（UTF-8 SHA-256
a8a1dec4…，事件 `configs/s2_11_user_authorization_event_v1.json`）：除真实 LLM/API
调用外，所有本地、非破坏性、可回放 Pipeline 操作可直接执行并如实记录。本轮应用并
记录（均未调用 API、未翻越 Stage 3 门禁）：(1) **G1**=resolved_for_local_
nonredistributive_analysis——artifact（references/barrientos_2026，91 文件）无可
解析许可（无 LICENSE/COPYING/NOTICE/README/metadata；anonymous artifact 页面无
license 标识），`artifact_license_verified=false`、`unknown_pending_confirmation`，
用户授权本地只读研究使用，禁止再分发/公开原始数据、禁止修改 references、正式包只
含 hash/ID/统计/用户裁决；(2) **G2**=applied_local_read_only（scope=
local_read_only_nonredistributive_s2_11，formal run 只读 membership manifest
列出的文件）；(3) **G3**=applied——M1 modality identity candidate mapping
（obligation→obligation、permission→permission、prohibition→prohibition），
candidate-only、definition 绝不自动生成、外部 annotation 仅 review aid；
(4) **G6**=applied——S0_no_automatic_structural_mapping（真实 artifact 记录为
{ID, version, text} 自然语言句，格式规范中的 precondition/temporal_validity 为
嵌套逻辑对象而非可验证叶子 span，故 field_mapping={}，无法安全映射留空交人工）；
(5) **G4**=applied——G0.5 冻结 `configs/g05_complexity_frozen_v1.json`
（status=frozen、frozen_before_new_results=true、retrospective_use_forbidden=
true、s2_10_retrospective_use_forbidden=true、scope=future_external_complex_
corpora_only），经 v6 密封链完整验证（draft 原始字节 61938c99…、授权 manifest、
append-only 授权事件、空 prior-results 扫描），冻结前无任何 S2.11 候选/结果；
G0.5=frozen_for_future_external_complex_corpora，原 draft 保留为历史 provenance，
S2.10 旧结果不重标 preregistered；(6) **G5** 未在本 checkpoint 应用（membership/
workload 待 Checkpoint B 语料盘点后打开 review surface）；(7) v6 capsule 转为历史
安全基线（核心资产字节不变，pytest 生命周期语义修正）；S2.11 仍 blocked（等待
Checkpoint B 候选生成与人工裁决），S2.12 partial、S2.13 blocked、S3.7 未动。

### 12.0e S2.11 语料激活与人工 review surface（2026-08-17，Checkpoint B，见 `outputs/reports/s2_11_candidate_run_v1.json` 与 `outputs/reports/s2_11_g5_review_surface_v1.json`）

真实 Barrientos requirement 语料激活（全部离线、零 LLM/API、本地只读非再分发）：(1)
**corpus inventory**——3 个 scenario requirements 文件（40 条记录：blood_donation
r14-r20×2、emergencies r1-r7×2、SIM_card r8-r13×2），hash-only membership
（`outputs/reports/s2_11_corpus_membership_v1.json`：文件原始字节 SHA-256/size、
record IDs、逐条 text SHA-256；不复制原始第三方文本）；4 条空/占位文本记录
（QUARANTINE_EMPTY_TEXT）隔离。(2) **deterministic ingestion**——文档化模态关键词
规则（prohibition/permission/obligation 顺序，精确 span；"must not" 优先于
"must"），结构字段按 S0 政策留空，cross-ref 空；adapter 以新增
`local_read_only_research` 模式运行（许可未知绝不声称 verified；用户授权事件 +
containment 为证据，EVIDENCE/scope/containment 全链验证）。(3) **candidate 运行**——
29 条候选（obligation 21 / permission 2 / prohibition 6；G0.5 frozen 分类
L1×28/L2×1；provenance 完整 29/29）；7 条运行期隔离（8 条 MODALITY_UNKNOWN 中
r16v1/r17v1/r17v2/r10v1 等无模态关键词、3 条 FIELD_SPAN_AMBIGUOUS 如 "must" 出现
两次；共 11 条隔离）；完整候选（含原文）仅存 gitignored 本地目录
`outputs/development/s2_11_local_working/candidates_v1/`，提交资产只有统计、hash、
ID、隔离码。(4) **G5=applied_review_surface_open**——空白 review pack
（`data/development/human_review/s2_11_blank_review_v1.json`，29 samples，全部决策
字段 null、unreviewed、无预填 Gold、无原文）+ 用户决策文件
（`s2_11_review_decisions_v1.json`）+ review 工具
（`scripts/review_s2_11_candidates.py`：运行时按 hash 只读加载 references 原文，
不匹配即拒，原子写入+备份+resume+progress）+ 冻结验证器
（`scripts/verify_s2_11_review_freeze.py`，frozen=false 直至用户完成裁决，不创建
Gold）。(5) **S2.11=in_progress_human_adjudication**（29 条待用户裁决 + 11 条隔离，
见 transition readiness v3 重推导）；S2.12 仍 partial、S2.13 仍 blocked、S3.7 未动；
零 LLM/API、未伪造 Gold、未发布受限原文。

### 12.0f S2.11 正式 Gold 发布（2026-08-17，见 `outputs/reports/s2_11_formal_gold_v1.manifest.json`）

在 Checkpoint G 的 36/36 用户裁决与 freeze v3 `frozen=true` 基础上，正式发布
`data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json`（SHA-256
`039ae8b2429826ae2b320667fb4a0dff96de6408b0a9637c1d9911565129c804`）。
发布器在写入前逐项验证：(1) 确认事件文件原始 SHA-256 `226b4798…` 与事件内
用户原句 UTF-8 SHA-256 `7414a38d…` 分开绑定；(2) proposal v3 文件 SHA-256
`9882ba45…`、proposal source、reviewer=hyc、revisions=none；(3) decisions v2
36/36 adjudicated 且每条 reviewer/confirmation event 一致；(4) freeze validator v3
真实执行；(5) 40/4/36 membership、第三方 source file/text hashes、canonical spans、
actor-action map、order relations 与 G0.5 frozen 状态。Gold 的每条 `canonical` 与冻结
decisions 等值，并与 proposal v3 的 containment transform 等值；不得称为独立专家
从零标注，正式 provenance 为 `deepseek_offline_proposal_v3` +
`user_batch_confirmation` by hyc。版本化 schema、publisher、publication capsule、
manifest、export index 与独立 verifier 均已建立；重放命令 byte-identical，独立
verifier 27 项全过，focused 9 项（含 extra-field/event/reviewer/G0.5/manifest/export
篡改）全过。提交 Gold 不含第三方原文，只含本地 source path/file/text hashes、
坐标和必要标签；零 LLM/API，未生成 predictions/results/Gold Rule Records，未启动
Stage 3 Oracle。S2.11 因此为 verified/frozen/Gold published；S2.12 仍须完成三臂
复杂语料运行与分层评价。



### 12.1 论文并行轨道（导师要求立即启动）

论文写作从现在开始，不等待最终实验；但写作进度不能反向解锁实验门禁。实时派工
与可复制 Prompt 见 `docs/PROJECT_AUDIT.md` 和 `docs/AGENT_RUNBOOK.md`。

| ID | 写作任务 | 当前状态 | 回填/完成门禁 |
|---|---|---|---|
| PW0 | 论文目录、骨架、主张矩阵、TODO 和空表 | verified | 本轮建立且无虚构结果 |
| PW1 | 引言、背景、RQ0–RQ4 | ready | 全部结果性表述为待检验或 TODO |
| PW2 | Sun/Winter/Sleimi/Michel/Barrientos 相关工作 | ready | 内部证据回到可核验原论文 |
| PW3 | 三阶段架构和 Rules-Only / Rules+LLM-Repair / Direct-LLM（旧代号 B0/H1/D1）方法设计稿，贡献按 §8.8.4 细模块化（8 模块 Direct-LLM + 7 模块 Rules-Only） | ready | 未完成组件使用 TODO-STATUS |
| PW4 | 数据、五层 Gold 与标注协议 | partial-ready | S2.1/S2.2 后回填实际统计 |
| PW5 | baseline、指标、统计与复现设计 | ready | 参数在对应任务冻结后回填 |
| PW6 | 结果表和图模板 | ready-template-only | 禁止填非正式数字 |
| PW7 | Stage 2 正式结果 | blocked | S2.10/S2.12/S2.13 + manifests |
| PW8 | Stage 1/3/端到端结果 | blocked | S1.7、S3.7–S3.10、P8 |
| PW9 | 讨论、结论、摘要与终稿 | partial/blocked | 主张矩阵全部有正式证据 |

论文占位符统一使用 `TODO-RESULT`、`TODO-SOURCE`、`TODO-STATUS`、
`TODO-DECISION`。开发结果只能标 `DEV_ONLY`；正式数字必须对应 `experiment_run`
事件和 manifest。Stage 2/3、Oracle/end-to-end、C1–C4 前人比较必须分开。

## 13. Agent 任务执行协议

每个工作批次必须：

1. 阅读本文、`PROJECT_AUDIT.md`、`AGENT_RUNBOOK.md`、`DIRECTORY_GUIDE.md`、最新实验日志、
   `AI_CHANGE_PROTOCOL.md`、`ROUTE_LOCK.md`；
2. 运行编辑前快速完整性检查；
3. 从任务表选择一个最小任务 ID；
4. 写明输入、输出、依赖、边界和 Definition of Done；
5. 开发中只跑相关测试；
6. 连贯批次结束后跑一次完整性检查和全量测试；
7. 用 `record_change.py` 记录变更；真实实验还必须记录 `experiment_run` 与 manifest；
8. 只更新 `PROJECT_AUDIT.md`，不新增日期版 status/handoff 文档。

任务状态只使用：`blocked`、`ready`、`in_progress`、`verified`、`complete`。
只有脚手架或单元测试时只能写 `development` 或 `partial`，不得写完成。

执行频率：只读分析不跑全量；连贯编辑批次开始跑快速检查；批次中只跑相关测试；
批次结束/阶段交接跑 `audit_project.py --with-tests` 一次并记录事件。随后
`record_change.py` 复用绑定当前文件状态的测试凭证，不重复跑全套测试。正式运行前
跑 `--require-final-ready`；详细字段与日志示例见 `AI_CHANGE_PROTOCOL.md`。

## 14. 目录边界

活动目录结构见 `docs/DIRECTORY_GUIDE.md`：活动入口留在 `docs/` 顶层；研究证据放
`docs/research/`；已替代路线、快照、旧输出和旧脚本放 `_retired/`；实验事件只追加，
不得重写；`references/` 与根 `archive/` 只读；缓存和临时目录可以清除；数据、Gold、
预测和结果不得因目录整理被删除。恢复 `_retired/` 材料需要用户批准和日志事件。

## 15. Pipeline 变更日志

| 版本 | 日期 | 变更 | 依据 |
|---|---|---|---|
| 3.6.23 | 2026-08-17 | **S2.11 正式 Gold 发布（零 API）**：从 Checkpoint G 已确认且 frozen 的 36/36 canonical decisions 等值派生正式复杂语料 Gold（SHA `039ae8b2…`）；provenance 明示 `deepseek_offline_proposal_v3` + user batch confirmation by hyc（无 revisions、非从零独立专家标注）；确认事件文件 SHA `226b4798…` 与用户原句 SHA `7414a38d…` 分开绑定；source/proposal/reviewer/freeze/G0.5 drift 全部 fail-closed；版本化 schema/publisher/capsule/manifest/export/独立 verifier/replay 完成；只提交 hashes/coordinates/必要 labels，无第三方原文；S2.11=verified/frozen/Gold published，S2.12 仍 partial；零 LLM/API、无 predictions/results/GRR/Oracle | Gold publisher + independent verifier + focused tests + audit pass |
| 3.6.22 | 2026-08-17 | **S2.11 用户确认裁决与冻结 + S2.12/S2.13 状态推进（Checkpoint G，用户确认 proposal v3 一次性内容，零 LLM/API）**：(1) **用户确认**：`configs/s2_11_batch_import_confirmation_event_v3.json`（kind=s2_11_batch_import_confirmation，source=user_instruction_in_current_task，`user_instruction_utf8`=“我确认接受 S2.11 全部 36 条 canonical proposal v3 作为我的裁决（无 revisions），proposal 文件 SHA-256 = 9882ba45…，reviewer 署名：hyc”，其 UTF-8 SHA-256 7414a38d…，proposal_file_sha256 精确绑定 `9882ba45…`，revisions=null，gold_created=false，append_only=true）。(2) **importer v3 --apply 原子写入**（`scripts/s2_11_batch_import_v3.py` fail-closed）：decisions v2 36/36 adjudicated（reviewer=hyc 仅来自事件、confirmation_event 路径写入每记录）、逐字节不变备份 `.bak`、apply 后 committed dry-run 报告刷新（confirmation_event_present=true 使 run_dry_run 保持 byte-reproducible；新增 `refresh_dry_run_report_after_apply`）；main() 修复 apply 打印分支（run_apply 返回 {applied,reviewer,records,decisions_file,backup} 无 import_stats）；freeze validator v3 `frozen=true`（36/36 adjudicated、剩余 0、无 Gold）。(3) **S2.12 readiness v3 刷新**（`scripts/s2_12_build_readiness_v3.py --refresh` + `verify_s2_12_readiness_v3.py`）：schema 3.1.0，S2.11 freeze 36/36 + 确认事件 disk 绑定加入 bindings，proposal_v3.human_approved=true，runner.real_run_refused 理由更新为仅缺 API 预算授权（input token cap+cost cap），仍无最终授权句。(4) **transition capsule v7**（`build/verify_s2_13_s3_7_transition_readiness_v7.py` + schema/test/4 outputs；supersede v1-v6，55 项 superseded 全部 byte-exact 保留）：S2.11=frozen（从磁盘重推导：确认事件绑定 SHA+reviewer、decisions 36/36 adjudicated、freeze validator v3 执行）、S2.12=partial+execution-ready v3（真实运行 refused on API 授权）、S2.13=blocked、S3.7=blocked（GRR 三态 probe exist=false）；v7 VERIFIED（11 独立 verifier 全执行）。(5) **Checkpoint G 快照连锁（记录在案）**：verify_s2_12_execution_ready_v2.py 更新为 freeze 36/36 + 对 decisions v2 的 bindings 豁免（apply 合法改变其 SHA；decisions 完整性由 freeze validator v3 单独验证）；v5/v6 transition 测试更新为 superseded 快照语义（其 verifier/builder 依赖 apply 前 decisions 快照故不再自证当前有效，新增失败-关闭断言；这是对两个历史测试文件的 Checkpoint G 例外，其余 v1-v6 资产全部 byte-exact，v7 测试相应豁免这两个文件）；零 LLM/API、未创建 Gold/predictions/results、未发 API 授权句、未发布受限原文 | 确认事件 + importer apply + freeze 验证 + readiness v3 刷新 + transition v7 + focused tests + record_change 事件 + audit --with-tests |
| 3.6.21 | 2026-08-17 | **S2.11 proposal v3 最终校正与一次性确认就绪（Checkpoint F，零 LLM/API）**：(1) **六个已确认问题的复现与修复**：r10v1 双 actor span 同 ID + 条件内 customer 混入 actor + 缺 actor-action mapping → v3 显式 occurrence=1 仅保留主句执行者 `[41:53] the customer` 并建 mapping；canonical validator v2 仅查 modality evidence ID 且 collect_span_ids 字典覆盖 → **canonical v3**（`src/bpc_hybrid/s2_11_canonical_v3.py`）强制全 record 普通 span ID 唯一、clause ID 唯一、aam 边存在/同 clause/无重复/全覆盖（有 actor 的 clause 每个 action 必须有 mapping）、order 必须引用两个不同有效 action、list-based 收集（不隐藏重复）；r4v2 action/constraint overlap 18 字符 → action=raw `happen`（normalized 仅本地）+ constraint `before the surgery`，overlap=0；r8v1 `longer than 30 days` 恢复为 constraint + action=raw `sending the SIM card`（normalized）；r18v2 `immediately` 恢复为 constraint + action=raw `sent the reason for rejection`（normalized）；r3v1/r3v2 纳入 temporal-validity constraints `valid from 2024 to 2030`/`2025 to 2031`（规范性 clause span 扩展至全文，无伪 clause）；其余 30 条机械回归无证据不改写。(2) **proposal v3**（`scripts/s2_11_build_proposals_v3.py`）：span spec 支持显式 occurrence，同一文本多 occurrence 无明确选择 fail-closed；36/36 验收全零（exact-slice=0、duplicate span/clause ids=0、ambiguous auto-occurrence=0、invalid/missing aam=0、invalid orders=0、action/constraint overlap=0、evidence missing=0、unresolved=0、display None=0）；本地完整包 `adjudication_proposals_v3/`（proposals.jsonl/decision_package.md/v2→v3 diff/quality report；SHA `9882ba45…`）；提交报告 `s2_11_proposal_report_v3.json`（坐标/hash/计数，零 ≥40 字符原文片段）；**proposal v1/v2 superseded（v2 状态 superseded_pending_targeted_correction_do_not_approve），v1/v2 文件逐字节保留**。(3) **importer v3**（`scripts/s2_11_batch_import_v3.py` re-bind proposal v3）：dry-run blocked=0/unresolved=0/adjudicable=36/36；`--apply` fail-closed（确认事件绑定 proposal v3 SHA+revisions SHA+reviewer、原子写+备份）；freeze validator v3（canonical v3 + 7 项 checks）+ review tool v3；**本轮未创建确认事件、未 apply、freeze=false、无 Gold**。(4) **S2.12 readiness v3**（`scripts/s2_12_build_readiness_v3.py` + `verify_s2_12_readiness_v3.py`）：评估器 v2 不重写，parity 重跑通过并 re-bind proposal v3/importer v3 hash；API readiness 保持 dry-run（两臂 deepseek-v4-pro、36/72/108 calls、输出 4096、输入未文档化、cost_cap_unresolved、**无最终授权句**、缺项精确列出）。(5) **transition v6**（47 项 supersedes、11 个独立 verifier、V6 VERIFIED；v1–v5 逐字节保留且各自 verifier 继续通过；S2.11=只剩绑定 proposal v3 SHA 的一次性用户内容确认、S2.12=partial+execution-ready v3、S2.13 blocked、S3.7 未启动、GRR 不存在、无 Oracle 授权句）；零 LLM/API、未伪造 Gold、未发布受限原文 | Checkpoint F 构建器/验证器 + focused tests + record_change 事件 + audit --with-tests |
| 3.6.20 | 2026-08-17 | **S2.11 canonical proposal v2 校正 + 可一次接受导入 + S2.12 正式评价口径对齐（Checkpoint E，零 LLM/API）**：(1) **canonical v2 数据模型**（`src/bpc_hybrid/s2_11_canonical_v2.py` + blank pack/decisions v2 + freeze validator v2 + review tool v2）：字段三态 unresolved/absent/present（absent 是明确裁决的"不存在"，不再用 null 混淆 absent 与未裁决）；modality=status+label+1..N 字节验证 evidence spans；actor/action/condition/constraint/exception=span 数组（多值支持）；actor-action map + order relations（span id 引用）；adjudicated 仅要求无 unresolved、允许合法 absent；复用 Stage 2 canonical span 惯例（text==source[start:end] 运行时对 hash 绑定原文验证；提交文件仅坐标）。(2) **36 条独立语义复核**（`scripts/s2_11_build_proposals_v2.py`）：modality label 与 evidence 分离（evidence 为原文规范性 cue 精确子串，如 must/has to/is prohibited from/is not obligated/are not eligible/should/can/is necessary 等）；动作改为完整连续动词短语（r18v2 `be immediately sent the reason for rejection`、r17v1 拆 `assess the donor`+`record the reason in the system` 并建 order、r2v1/v2 拆双 clause+order、r9v2 constraint 修正含弯引号原文）；被动句执行者未出现一律 actor=absent（受事者不冒充）；`not obligated`/`not needed` 纠正为 permission（非 prohibition）、`even if` 从句为 exception、change-version 对（100→50、or→and、15→20、nurse→doctor 等）逐一体现在 span/条件；14 条 needs_attention（confidence high 23/medium 9/low 4）；**proposal v1 声明 superseded 不可批准**（v1 文件逐字节保留）；v2 本地完整包（proposals.jsonl/decision_package.md/v1→v2 diff/quality report，仅 gitignored）+ 提交报告 `s2_11_proposal_report_v2.json`（坐标/hash/计数，零原文片段，proposal SHA 93866427…）；验收测试强制：coverage 36/36、exact-slice=0、evidence missing=0、value_missing_in_text=0、display None=0、duplicate/missing/extra=0、hash drift 拒绝。(3) **importer v2**（`scripts/s2_11_batch_import_v2.py`）：dry-run blocked=0/unresolved=0/adjudicable=36/36（would-be 通过 freeze validator v2 全部结构检查）；`--apply` 实现但 fail-closed——必须用户确认事件精确绑定 proposal v2 SHA+revisions SHA+reviewer、原子写+写前备份、reviewer 只能来自事件；**本轮未创建确认事件、未 apply、freeze=false、无 Gold**。(4) **S2.12 正式口径对齐**（`s2_12_stratified_evaluator_v2.py`：modality label acc/macro-F1/per-class + 五字段 Sun literal-overlap span P/R/F1，复用正式 stage2_evaluator_s210_v3 合同与共享 literal-overlap 模块；L3=0 明确无样本不造 0 分；`s2_12_method_adapter.py` 方法适配 dry-run ready；**parity 测试**证明同一 fixture 经正式 Stage 2 evaluator 与 stratified wrapper 未分层总体一致）；plan/readiness v2（supersede v1，reason=evaluator/Gold-shape correction）只声称 schema/importer/evaluator/adapter ready，不声称 Gold/正式评价完成；**API readiness v2**：direct_llm=deepseek-v4-pro（D1 registry 钉死）、sun_llm_fallback=deepseek-v4-pro（H1 全量 run manifest，cli_override；trigger 语义：150 记录 111 样本 150 调用→派生每记录上限 2→72）、max_calls 36/72/108、输出 token 4096、**输入 token 未文档化 + cost_cap_unresolved（仓库无可信价格依据）→ 未发出最终授权句**，缺项精确列出、calls_made=0。(5) **transition v5**（supersede v1–v4，39 项 supersedes；S2.11=canonical v2 未裁决、只剩一次性用户确认；S2.12=partial+execution-ready v2；9 个独立 verifier 全执行；v1–v4 逐字节保留且各自 verifier 继续通过）；S2.13 blocked、S3.4–S3.6 development-only、S3.7 未启动、GRR 不存在、无 Oracle 授权句；零 LLM/API、未伪造 Gold、未使用 API 授权句、未发布受限原文 | Checkpoint E 构建器/验证器 + focused tests + record_change 事件 + audit --with-tests |
| 3.6.19 | 2026-08-17 | **S2.12/S2.13 执行就绪 + transition v4（Checkpoint D，零 LLM/API）**：(1) **S2.12 执行计划冻结**（`configs/s2_12_execution_plan_v1.json` + `outputs/reports/s2_12_execution_plan_v1.json`，builder `scripts/s2_12_build_execution_ready.py`）：预注册 G0.5 L1/L2/L3 分层（36 条密封链分类 L1 31/L2 5/L3 0）、三臂同一输入/Gold/evaluator、DoD 重述、retrospective 描述性分析明确标记为历史；Gold=用户裁决 S2.11 decisions（当前 0/36，pending）。(2) **fail-closed runner/evaluator readiness**（`src/bpc_hybrid/s2_12_stratified_evaluator.py` 确定性分层 per-field P/R/F1+错误类型 correct/missed/misclassified/extra，sample set 精确匹配、缺字段/坏 level/空集全拒绝；synthetic fixtures 通过；`outputs/reports/s2_12_execution_readiness_v1.json`：real_run_refused=true、gates ready=false、无 Gold、零 API）。(3) **API 预算 dry-run**：typical 72（36 条×2 LLM 臂×1）/hard cap 100、calls_made=0、authorized=false、可复制授权句存在但 sentence_used=false（本轮零调用，未使用授权句）；独立 verifier `scripts/verify_s2_12_execution_ready.py` 15 项 PASS（绑定重算、合成重跑、dry-run 状态、无 API 事件）。 (4) **transition readiness v4**：v4 capsule（schema/build/verify/test/reports，supersede v3 的 S2.11 workload 推导（改为空白 pack 36=29+7）与 S2.12 判断（改为 partial+execution-ready）；新增 8 个独立 verifier 之一 verify_s2_12_execution_ready；v1/v2/v3 全部逐字节保留且 verifier 继续通过；v4 验证器 8 项外部 verifier 全执行 V4 VERIFIED）。(5) 文档一致性：MASTER S2.11 行不再 blocked（in_progress_human_adjudication，Checkpoint C 已改）、G0.5=frozen、transition 当前=v4（v3 previous）、§12.0 与 S3.7 行引用更新、gap capsule 继续声明 superseded、S1.7=frozen 未动；S2.12=partial+execution-ready、S2.13 blocked、S3.7 未动；零 LLM/API、未伪造 Gold、未使用 API 授权句、未发布受限原文 | Checkpoint D 构建器/验证器 + focused tests + record_change 事件 + audit --with-tests |
| 3.6.18 | 2026-08-17 | **S2.11 全量裁决加速：完整 review 人口 + 36 条离线 AI 提案 + dry-run 批量导入（Checkpoint C，零 LLM/API）**：(1) **review 人口封闭 40/4/36**：inventory 40 → 客观排除 4 条空文本（QUARANTINE_EMPTY_TEXT，原始字节重验）→ nonempty=review population=36；29 条候选 available + 7 条 unavailable（4 条 MODALITY_UNKNOWN：blood r16v1/r17v1/r17v2、SIM r10v1；3 条 FIELD_SPAN_AMBIGUOUS：emergencies r2v1/r2v2/r3v1，均带稳定错误码）；候选失败绝不缩减 review 人口（消除"候选成功决定 review"选择偏差）；review surface schema 升到 s2_11_review_surface@1.1.0（空白 pack `s2_11_blank_review_v1.json` 36 条全 null/unreviewed + 决策文件 `s2_11_review_decisions_v1.json` 36 条 + G5 报告/manifest，binding 在文件写出后计算）；冻结验证器改为从空白 pack 读期望 36 ID 并强制 sample set 精确相等（缺/多/重均拒绝）；review 工具支持 unavailable 项（candidate=null + candidate_error）。 (2) **36 条离线 AI 裁决提案**（`s2_11_generate_proposals.py`，deepseek_offline_proposal，human_approved=false、gold=false、reviewer 永不=user；字段值全部为原文精确子串且 span 字节验证 text[i:i+len]==value，缺失字段=null 绝不虚构；confidence high 13/medium 19/low 4；needs_attention 8 条；G0.5 级别经密封 v6 链 classify_frozen 计算）；完整原文+提案仅 gitignored 本地目录（proposal SHA-256 14c1ec90… 绑定于提交报告），提交报告 `s2_11_proposal_report_v1.json` 仅坐标/hash/计数（连续 ≥40 字符原文片段=0，全 4 个已提交 review 资产复检）。 (3) **dry-run-only 批量 accept/revisions 导入工具**（`s2_11_batch_import_dry_run.py`）：绑定提案文件 SHA-256、验证 36 成员与全部 hash、accept-all+listed revisions（修订值须为原文精确子串，字节验证）、fail-closed（无用户确认事件 → 不写决策文件、--apply 拒绝 exit 2、本轮不创建确认事件）、reviewer 永不=user、would-be 决策全部 review_state=reviewed 待用户确认；导入规则：modality=受控词表类标（无 span 也导入），actor/action/condition/constraint/exception 仅当值为原文精确子串（未找到/多值 → decision=null + import_blocked 记录，本轮 10 字段/7 样本）；dry-run 报告 `s2_11_batch_import_dry_run_v1.json` 已提交（同样零原文片段）。 (4) **transition v3 重推导**：v3 验证器成功横幅 "V2 VERIFIED" 误标修复为 "V3 VERIFIED"；因空白 pack/决策文件演进 + 验证器脚本 hash 变化，v3 capsule（report/md/manifest/export index）按字节一致重建并重新验证（v1/v2 文件与验证器逐字节保留）。 (5) 测试：S2.11 聚焦测试更新至 36 人口语义 + 新增提案/批量导入测试（确定性强、无确认事件路径、篡改拒绝），全量审计 exit 0；S2.11=in_progress_human_adjudication（36 条待用户裁决）、S2.12 partial、S2.13 blocked、S3.7 未动；零 LLM/API、未伪造 Gold、未发布受限原文 | Checkpoint C 构建器/工具/验证器 + focused tests + record_change 事件 + audit --with-tests |
| 3.6.14 | 2026-08-15 | **S2.11/G0.5 用户决策包 v5：修复 v4 红测、历史 capsule 生命周期、真实 provenance/evidence binding 与 G0.5 原始字节绑定（零 API/零 gate 翻转）**：(1) **v4 红测修复**：v4 变更事件如实记录 3 failed / 2057 passed / test_returncode=1 / integrity_pass=false；v5 引入集中式历史 capsule 生命周期语义（`src/bpc_hybrid/capsule_lifecycle.py`）——v3/v4 核心资产（schema/builder/verifier/4 outputs）逐字节不变（git 证明），其 pytest 文件仅按生命周期语义修正（历史 builder 在绑定资产演进后 no-overwrite fail-closed、历史 verifier 拒绝且失败项属于声明性 binding drift、历史负例测试继续真实执行）；v5 全量审计恢复 exit 0（不含 xfail/skip/过滤）。(2) **adapter 严格 mode 枚举**：`{synthetic_test_only, formal}` 之外一律 INVALID_MODE（`mode="production_typo"` 被拒）。(3) **真实 evidence binding**：formal mode 要求文件级绑定——相对安全路径（禁绝对/`..` 逃逸）、64 位小写 hex SHA-256、原始字节重算一致、evidence 文档内部 kind/ID/scope 一致、authorization manifest 精确绑定 policy ID/modality mapping/field mapping/license evidence hash/scope；synthetic binding/缺文件/错 hash/错 ID/错 kind/路径逃逸全拒绝；formal 正例仅用 pytest 临时目录 synthetic 文件；当前磁盘仍拒绝一切 formal 转换。(4) **可验证字段级 provenance**：source_record_id/source_path 非空合法（`str(None)` 伪装拒绝）、结构字段 element 精确等于 mapping key、modality element 精确匹配 `norms[<idx>].modality`、字段 path 必须等于确定性 locator `record_source_path#element`、record path 不得含 `#`、bool 不得作为 offset、重叠 span ambiguity（`"aaa"` 中 `"aa"` 两个起点）检测、未知 descriptor 字段拒绝。(5) **G0.5 原始字节 hash 域**：`validate_frozen_application` 改为接收真实文件路径并只对原始字节算 SHA-256；dry-run G4 句绑定 draft config 原始字节 `61938c99…`（语义重序列化 hash `51a6e4fe…` 被 validator 拒绝）；`classify_frozen` 仅接受完整验证结果（含不可伪造 validation_token = manifest 原始字节 hash）；`derive_promotion_readiness` 不再仅凭 glob 文件名判 ready，必须解析并验证完整资产组合（当前磁盘仍 draft_not_frozen / promotion_ready=false）；不创建真实 frozen config 或授权 manifest。(6) v5 capsule（schema/builder/verifier/30 项测试/JSON/MD/manifest/export index）supersede v3/v4 当前状态判断（v3 4 决策项 + v3 8 文件 + v4 8 文件 = 20 项 supersedes，全部 hash 绑定）；gate 状态 G1/G2/G5/G6 false+null、G3/G4 dry-run（G4 绑定原始字节 hash、仅未来 gate-application checkpoint）、S3.7 全 false/null；MASTER/PROJECT_AUDIT v5 为当前决策入口（v3/v4 历史）；全量审计 exit 0（2118 passed / 24 skipped / 19 warnings（v5 最终 receipt））；零新增 LLM/API，Gold/contract/methods/predictions/results/references/Stage 3 gate/S2.11-S2.13 状态均未修改，未生成 Oracle 授权句 | 决策包 v5（builder/verifier/manifest）+ capsule_lifecycle + adapter 加固 + G0.5 原始字节绑定 + record_change 事件 + audit --with-tests（exit 0） |
| 3.6.15 | 2026-08-15 | **S2.11/G0.5 授权链封闭与固定锚点（v6，零 API/零 gate 翻转）**：(1) **frozen 授权链封闭**：v5 的 caller-supplied validation-result 解锁方式被反例推翻（手工字典含任意 64 位小写 hex token 即可解锁 v5 classify_frozen）；v6 移除该参数，classify_frozen 每次调用从磁盘重验 draft/frozen config、授权 manifest、append-only 授权事件与 prior-results 证据扫描（后者由确定性路径/manifest 规则推导，不再接受 caller bool）；授权 manifest 完整绑定 schema/version、manifest ID、authorization_applied=true、精确批准 scope 枚举、精确 G4 dry-run 句全文 + UTF-8 SHA-256、draft/frozen 相对路径 + 原始字节 SHA-256、回退/冻结前/S2.10 禁用标志、重推导 prior-results 扫描、授权事件（ID+路径+原始字节 SHA-256）与 pending（未应用）checkpoint；全部变体被拒（另一 manifest 的 token、manifest 修改后旧 token、句/scope/事件/路径替换、先出结果后构造授权、仅布尔/伪造 hash 声称已验证）；普通内容 hash 不被当作用户授权证明。(2) **历史 capsule 固定锚点**：v3/v4/v5 核心资产逐字节不变，锚定固定 origin commit（31ac757d…/8e8b488e…/7883739…）+ 硬编码 21 项 SHA-256 map（capsule_lifecycle.py）；磁盘字节和 origin-commit blob 均须匹配固定 map；新增回归测试证明“HEAD 与磁盘同时被替换为同一错误字节”仍失败；v6 report/manifest 绑定三版固定 hash。(3) **adapter evidence provenance（v6）**：证据 verifier 返回结构化 EvidenceContext；formal 输出新增 formal_evidence_provenance（license/manifest/事件 ID+路径+原始字节 SHA-256+精确 scope、policy ID、modality/field mapping canonical hash、manifest 绑定说明、candidate_only=true/gold_authorized=false），synthetic mode 为 null；scope 受控枚举（article-only 不满足 artifact code/data），manifest 必须精确复述 license scope；evidence 路径 resolve() 后必须在 evidence root 内（symlink/junction 逃逸被拒）；当前磁盘无合格 evidence，一切真实 formal 调用仍被拒。(4) **v5 事实如实记录**：v5 全量审计确实为绿（最终 receipt 2118 passed / 24 skipped / 19 warnings in 941.91s）、不是红测 checkpoint、历史事件保留；但 v5 的 hand-built validation-result 防护声明被本轮反例推翻（与审计绿灯分开记录）。(5) **G0.5 未冻结**：授权 hash 域仍为原始字节 61938c99…，51a6e4fe… 永不使用；G3/G4 仅 dry-run；G1/G2/G5/G6 ready=false+null；S3.7 全 false/null；S2.11/S2.12/S2.13/Stage 3 门未改；未生成 Oracle 授权句 | v6 capsule（builder/verifier/manifest）+ 固定锚点 + g05/adapter 链封闭 + record_change 事件 + audit --with-tests |
| 3.6.16 | 2026-08-17 | **S2.11/G0.5 非 API 决策应用与 G0.5 冻结（Checkpoint A，用户授权，零 LLM/API）**：用户转发授权原句 `除了用apikey的时候要授权，其他直接正常进行即可。`（UTF-8 SHA-256 a8a1dec4…）记录于 `configs/s2_11_user_authorization_event_v1.json`（append-only、精确 scope 与 containment）；G1=resolved_for_local_nonredistributive_analysis（artifact 许可未知，91 文件盘点无 license 文件，license_verified=false，本地只读研究使用、禁止再分发/公开原始数据、禁止修改 references）；G2=applied_local_read_only（scope=local_read_only_nonredistributive_s2_11，formal run 只读 membership 文件）；G3=applied（M1 modality identity candidate mapping，candidate-only，definition 不自动生成）；G6=applied（S0_no_automatic_structural_mapping，field_mapping={}，真实 artifact 无叶子 span 结构字段）；G4=applied（`configs/g05_complexity_frozen_v1.json`：status=frozen、frozen_before_new_results、retrospective/s2_10 forbidden、scope=future_external_complex_corpora_only，经 v6 密封链完整验证——draft 原始字节 61938c99…、授权 manifest、append-only 事件、空 prior-results 扫描；G0.5=frozen_for_future_external_complex_corpora，draft 保留为历史，S2.10 不重标 preregistered，冻结前无候选/结果）；G5 待 Checkpoint B；v6 capsule 转为历史安全基线（核心资产字节不变）；S2.11 仍 blocked（待候选生成+人工裁决）、S2.12 partial、S2.13 blocked、S3.7 未动；零 LLM/API、未伪造 Gold、未发布受限原文 | Checkpoint A builder/verifier + focused tests + record_change 事件 + audit --with-tests |
| 3.6.17 | 2026-08-17 | **S2.11 语料激活与人工 review surface（Checkpoint B，零 LLM/API）**：真实 Barrientos requirement 语料本地只读激活——3 文件 40 记录 hash-only membership（4 条空文本隔离）；确定性模态抽取（文档化关键词规则+精确 span）→ hardened adapter `local_read_only_research` 模式（许可未知不声称 verified、用户授权事件+containment 证据）→ 29 条候选（obligation 21/permission 2/prohibition 6；G0.5 frozen L1×28/L2×1；provenance 29/29）＋7 条运行期隔离（MODALITY_UNKNOWN/FIELD_SPAN_AMBIGUOUS，共 11 条）；完整候选（含原文）仅 gitignored 本地目录，提交资产仅统计/hash/ID/隔离码；G5=applied_review_surface_open（29 samples 空白 pack 全 null + 用户决策文件 + review 工具（hash 只读加载原文、原子写、备份、resume、progress）+ 冻结验证器，无预填 Gold）；S2.11=in_progress_human_adjudication（29 条待用户裁决＋11 条隔离）；transition readiness v3 重推导（v1/v2 字节保留）；S2.12 partial、S2.13 blocked、S3.7 未动；零 LLM/API、未伪造 Gold、未发布受限原文 | Checkpoint B 运行/工具/验证器 + focused tests + record_change 事件 + audit --with-tests |
| 3.6.13 | 2026-08-15 | **S2.11/G0.5 用户决策包 v4（纠正）：许可证据分离、adapter provenance 加固、G0.5 promotion readiness、gate 顺序修复（零 API/零 gate 翻转）**：(1) 论文许可确认——`references/papers/Barrientos_2026_Impact_analysis.pdf`（sha256 6ce91fd2…，1,822,940 B）只读证据链：标题/DOI 10.1016/j.infsof.2026.108079/Elsevier 正文 "open access article under the CC BY license" 声明/artifact URL（anonymous.4open.science）；`paper_readable=true`、`article_license=CC-BY-4.0`（article_only）、`article_license_does_not_auto_cover_artifact=true`；artifact code/data 仍 `unknown_pending_confirmation`、`project_activatable=false`、`ready_for_data_activation=false`、激活授权句 null；(2) adapter 加固（`src/bpc_hybrid/s2_11_barrientos_adapter.py`，38 项真实执行测试）：record-level 与 field-level provenance 分离、每个 source element 自带 element/path/record ID/text hash/span/alignment source/policy ID、modality provenance 指向 norm element、结构字段不复用全局 span、canonical target 白名单 {actor/action/condition/constraint/exception}、NON_CANONICAL_TARGET/TARGET_COLLISION/FIELD_PROVENANCE_MISSING/FIELD_SPAN_INVALID/FIELD_SPAN_AMBIGUOUS/FIELD_VALUE_MISMATCH/NESTED_DICT_AS_SPAN_FIELD/ELEMENT_PATH_MISMATCH/EVIDENCE_BINDING_MISSING/EVIDENCE_BINDING_SYNTHETIC typed fail-closed；formal mode 要求版本化 license/authorization evidence bindings（当前磁盘无 → 拒绝）；synthetic/shadow only；(3) M1 精确范围=modality identity candidate ONLY（结构字段映射需独立 G6）；M2 不映射任何外部 label；(4) G0.5 promotion readiness（`g05_complexity_candidate.py` 扩展）：当前 `g0_5_status=draft_not_frozen`、`promotion_ready_for_application=false`、missing=user authorization manifest；未来冻结应用路径（frozen config + 授权 manifest 绑定 draft/frozen hash/scope/授权句/frozen_before_new_results=true/无先行结果/禁回溯）以 synthetic fixture 实现并测试（+8 项）；(5) gate 顺序修复：G1（artifact license）/G2（activation）/G5（Gold review surface，protocol_ready=true 但 ready=false/null，条件式 future sentence）/G6（结构映射）ready=false+null；G3 ready=true（M1 dry-run 句）；G4 ready=true（句子绑定精确 config SHA-256，仅授权未来 gate-application checkpoint，明确 "does NOT freeze G0.5 this round"）；v4 capsule supersede v3 的 license four-state/adapter-completeness/G4-G5 readiness 判断，v3 全文件逐字节保留；MASTER/PROJECT_AUDIT v4 为当前决策入口（v3 历史）；**全量审计为红灯（v4 变更事件如实记录：3 failed / 2057 passed / 24 skipped，test_returncode=1，integrity_pass=false——v3 历史正例测试在 v3 绑定资产（adapter/文档）被本轮任务要求演进后按 fail-closed 设计拒绝；该红灯由 v5 的历史 capsule 生命周期语义修复，v5 全量 exit 0）**；零新增 LLM/API，Gold/contract/methods/predictions/results/references/Stage 3 gate/S2.11-S2.13 状态均未修改，未生成 Oracle 授权句 | 决策包 v4（builder/verifier/manifest）+ adapter 加固 + G0.5 promotion readiness + record_change 事件 + audit --with-tests（v4 全量 exit 1） |
| 3.6.12 | 2026-08-15 | **S2.11/G0.5 授权前工程收口与用户决策包 v3（零 API/零 gate 翻转）**：(1) Barrientos adapter 核心 `src/bpc_hybrid/s2_11_barrientos_adapter.py`——synthetic/shadow implementation verified，仅接受显式输入、不扫描 references/；fail-closed typed 错误码（LICENSE_NOT_QUALIFIED/ACTIVATION_NOT_AUTHORIZED/MAPPING_POLICY_NOT_APPROVED/SYNTHETIC_POLICY_IN_FORMAL_MODE/INVALID_STRUCTURE/UNKNOWN_MODALITY/DEFINITION_NOT_PRODUCIBLE/MAPPING_POLICY_INCOMPLETE/INVALID_MAPPED_MODALITY/MISSING_TEXT_PROVENANCE/MISSING_SPAN_ALIGNMENT/INVALID_SPAN/AMBIGUOUS_SPAN/UNRESOLVED_CROSS_REFERENCE）；输出仅 candidate_only/review_candidate，external_annotation 仅 review aid；(2) 重写 `test_g07_barrientos_adapter_contract.py`（删除 `or True` 空断言，25 项真实执行测试）；(3) G0.5 候选合同 `configs/g05_complexity_candidate_draft_v1.json`（status=draft_not_frozen、retrospective_use_forbidden、L1/L2/L3 确定性规则/优先级/边界/缺失与冲突处理，覆盖 MASTER 要求的全部复杂度字段）+ `src/bpc_hybrid/g05_complexity_candidate.py` + 20 项 synthetic 边界测试；(4) 用户决策包 v3（schema/builder/独立 verifier/30 项测试/JSON/MD/manifest/export index）：许可核账只读（references/barrientos_2026 91 文件按 名称+sha256+size 盘点、无 LICENSE/COPYING/NOTICE/README/metadata → license_status=unknown_pending_confirmation、ready_for_data_activation=false、activation 授权句 null；paper/code/data/activation 四分状态）；映射选项 M1（identity candidate mapping，推荐）/M2（conservative no-mapping），未应用；空白人工 Gold 协议（review/adjudication/freeze/publication 分离、user_only、未创建 data/gold）；分离用户门禁 G1（许可证据，ready=false/null）/G2（激活，ready=false/null）/G3（映射选择，ready=true + dry-run 授权句）/G4（G0.5 冻结，ready=true + dry-run 授权句）/G5（空白 Gold review surface，ready=true + dry-run 授权句）；manifest 精确集合重建 + export 精确重建 + 单 EOF newline + 全部篡改负例 fail-closed；MASTER S3.7/下一真实路径改指 v2 transition capsule（v1 历史），新增 §12.0b；PROJECT_AUDIT 过渡核账行明确 v2 当前/v1 历史、S2.13 行 adapter 状态更新、证据入口加 v3；全量测试通过；零新增 LLM/API，Gold/contract/methods/predictions/results/references/Stage 3 gate/S2.11-S2.13 状态均未修改，未生成 Oracle 授权句 | 决策包 v3（builder/verifier/manifest）+ adapter + G0.5 draft + record_change 事件 + audit --with-tests |
| 3.6.11 | 2026-08-15 | **S2.13→S3.7 transition readiness v2：收敛 Gold 缺失探测、manifest/export 完整性校验与实时状态矛盾（零 API/零 gate 翻转）**：v1 capsule 全部文件逐字节保留（v1 verifier 继续通过、git hash-object 与 HEAD 一致）；新建 v2 capsule（schema/build/verify/test/reports，8 文件）——**Gold Rule Records 三态探测**（无候选→exist=false + 9 rule IDs + 显式绑定被检查的 Stage 2 EStG-150 Gold path/hash；任何 rule_record/rule-record 命名候选（data/gold/**、outputs/reports/**、历史 readiness 文档提及的具体路径）→ builder fail-closed 报错并列出路径，绝不报告 exist=false、绝不自行提升；exist=true 保留给未来用户授权 freeze/publication 路径，v2 未实现）；**manifest 精确重建**（verifier 在内存用磁盘 report/MD 字节与重收集 bindings 重建完整 manifest，与磁盘逐键比较，缺项/多余项/byte_size 篡改/同步重算 export hash 均 fail）；**export index 精确重建**（磁盘 report/MD/manifest 字节确定性重建，结构完全相等，重算哈希不能绕过）；**严格 verifier 判定**（非 JSON verifier 需 exit 0 + 显式成功行，"VERIFIED" 裸子串因 "NOT VERIFIED" 也包含而被拒绝）；Markdown 单 EOF newline；audit false 分支措辞改为仅描述真实计算条件并明示与 S2.13/S3.7/full-pipeline 无关（gate 计算/合同/状态值未变）+ true/false 双向回归测试；PROJECT_AUDIT 陈旧行原位收敛（sun_rule_only/D1/正式结果目录/S2.4-6/B0-R2-R5/S3.2-S3.3/当前派工/§1 结论），队列与派工收敛为真实下一路径（S2.11/G0.5 → S2.12 → S2.13 → 用户 Gold Rule Records → S3.4-S3.6 → S3.7 单独授权）；MASTER P1-P4 里程碑修正（P1 数据/Gold 完成但 G0.5/S2.11 未完成；P2 完整 B0 完成；P3 三方法正式比较完成、复杂扩展未完成；P4 D1 正式 arm 已发布、H1 comparison-only、复杂集仍 blocked）；全量测试通过；本轮零新增 LLM/API，Gold/contract/methods/predictions/results/Stage 3 gate/S2.13 状态均未修改，未生成 Oracle 授权句 | 过渡 capsule v2（builder/verifier/manifest）+ audit.py 措辞修复 + PROJECT_AUDIT/MASTER 收敛 + record_change 事件 + audit --with-tests |
| 3.6.10 | 2026-08-15 | **S2.13→S3.7 过渡核账与 fail-closed readiness 加固（过渡控制 capsule v1，零 API/零 gate 翻转）**：新建确定性过渡控制 capsule `s2_13_s3_7_transition_readiness_v1`（schema + builder + 独立 verifier + 14 项聚焦测试 + JSON/MD/manifest/export index）——逐项从磁盘资产/manifest/hash/实际执行的独立 verifier 重新推导依赖矩阵（S1.7=frozen；S2.10=verified；S2.11=blocked（许可/数据激活/3→4 映射/人工 Gold/G0.5/Barrientos adapter 精确 blockers 重读自 s2_11 资产）；S2.12=partial/retrospective；S2.13=blocked（DoD 未改、未拆新任务）；Stage 1 Process Gold 存在且 verifier 通过（7/135/7）；Stage 3 matching 25+violation 33 decision Gold 存在且与 frozen correction 一致（≠ Gold Rule Records）；9 个 GDPR rule IDs（article6/7/15/16/17/20/22/33/34）的正式 Gold Rule Records 不存在且本轮未创建/未推断；S3.4/S3.5/S3.6=development_only；formal_oracle_started=false、formal_oracle_authorized=false、ready_for_oracle_authorization=false、authorization_sentence=null、no_pseudo_oracle=true）；旧报告（s2_13_stage2_freeze_gap_capsule.{json,md}、s3_7_oracle_readiness_v2、s37_oracle_readiness_v1、formal_benchmark_release_v2 历史 exclusions、两个硬编码“Process Gold 不存在”的旧 builder）声明 supersede 其“当前状态判断”，文件本身逐字节保留未修改；audit.py 陈旧静态尾部改为动态生成（final_experiment_ready=true 仅代表 Stage 2 三方法正式评价/最终指标机器门禁就绪，不代表 S2.13/S3.7/全 Pipeline 完成），新增矛盾消除回归测试；独立 verifier 实际运行 7 个既有 verifier + 重跑 audit 并逐项比对；全量测试通过；本轮零新增 LLM/API，Gold/contract/methods/predictions/results/Stage 3 gate/S2.13 状态均未修改，未生成 Oracle 授权句 | 过渡 capsule v1（builder/verifier/manifest）+ audit.py 措辞修复 + record_change 事件 + audit --with-tests |
| 3.6.9 | 2026-08-10 | **formal Gold 发布授权执行（用户授权，packet v2 落地）**：按 ormal_gold_authorization_packet_v2 执行机器合同变更（实际授权日 2026-08-10）——stage3.status→locked（含 relock_note 2026-08-10）、ormal_gold_publication_gate.status→
eady_for_formal_gold_publication（白名单精确匹配 + 授权 note）、stage2_dataset.freeze_policy→完整重锁文本（保留数据/许可/冻结范围/禁止事项治理，仅更新已满足的 pending/relock 状态）；audit：formal_gold_publication_ready **False→True**、BLOCKERS 5→3（消除 formal_gold_publication_paused、stage3_benchmark_not_locked；保留 final_experiment_not_ready/formal_methods_not_ready/formal_capsule_not_frozen）、final_experiment_ready 仍 False；formal Gold 已可发布（LLM-assisted human-adjudicated）；不隐含 S1.7/S2.13/Gold Rule-Process Records/formal Oracle/最终实验完成，不授权任何 LLM/API | 用户授权（packet v2 授权句）+ audit --with-tests + record_change 事件 |
| 3.6.8 | 2026-08-08 | **BM25 candidate-specific 语义修复 + S3.6-A v3 重跑 + Stage 3 method registry v2 + formal Gold 授权包 v2**：BM25 v1/v2 的 sim(a,b) 忽略候选文本（返回 action corpus 最佳文档分数）→ 固定选第一个 action、actor/BO 误用 action corpus、order 可能映射错误 ID；修复：BM25Index candidate-specific score(query,candidate)（候选自身 tf/dl + 域语料 IDF/avgdl，真实 [0,1] 上界归一化 sum(IDF*(k1+1))，b 真实生效，空输入=0）、BaselineScorer 双域 sims factory + 真实 action ID 映射 + 确定性 tie-breaking/duplicate；BM25 v3（config v3 + run v3：MAP 0.6833→0.6595、binary F1 0.4→0.0，v2 invalid → v3 corrected before/after 报告）；v1/v2 标记 superseded_invalid_candidate_agnostic_similarity（不入 comparison/registry active/论文）；TF-IDF 经内容级 byte-identical 验证不受 ID 修复影响（无 duplicate labels）保留 v2；registry v2（active 指向 BM25 v3、superseded_invalid_runs=v1/v2、frozen_at 非 null、config 三 hash 区分：run snapshot/run manifest/当前工作树）；authorization packet v2（JSON Pointer 完整 before/after、freeze_policy 治理内容保留仅更新状态、临时副本门禁校验 False→True、活动合同字节断言未变、明确 formal Gold 与方法正确性为不同门禁）；全量 1621 passed/24 skipped；未读 .env/未调 LLM/未改 Gold/BPMN/correction/未翻转任何正式门禁 | registry v2 + packet v2 + audit --with-tests + record_change 事件 |
| 3.6.7 | 2026-08-08 | **S3.6 sensitivity 修复 + Stage 3 development 方法冻结注册表 + S3.7 前置核账 + formal Gold 授权包（dry-run）**：(1) baseline sensitivity 方法修复——BaselineScorer 的 gamma/theta 影响映射/R/C/分母/可观测性，sweep 改为重实例化 scorer 重算（删 mappings parameter-free 错误声明；matching tau 仍为固定 score cutoff；5 项手算 fixture 证明 gamma 改变 missing/actor observability/order denominator、theta 改变 actor 判定）；v2 runs（主阈值 0.5 不变，主指标与 v1 byte-identical）；(2) 措辞修正：Sun config 输入（inference pack=运行输入、blank pack=验证/溯源）、S3.6 阈值 0.5（fixed development setting before this run、非 blind preregistration、benchmark exposure 未排除）；(3) 方法冻结注册表 configs/stage3_development_method_registry_v1.json（5 方法：run/config/implementation/evidence capsule hashes、primary thresholds、exposure 状态、已知局限、formal_oracle_claim_allowed=false、confirmatory_claim_allowed=false、变更须新版本）；(4) S3.7 Oracle 输入真实性核账 outputs/reports/s37_oracle_readiness_v1.json——真正 Gold Rule/Process Records 均不存在（adapter 输出≠Gold），status=blocked_on_s1_7_s2_13，禁止伪 Oracle；(5) formal Gold 用户授权包 outputs/reports/formal_gold_authorization_packet_v1.{json,md}（dry-run：route/stage2/stage3/gate/freeze 现状+证据、拟议 before/after、预期 blocker 消除/保留、回滚、授权句；未修改合同）；全量 1609 passed/24 skipped；未读 .env/未调 LLM/未改 Gold/BPMN/correction/未翻转任何正式门禁 | registry/readiness/packet + audit --with-tests + record_change 事件 |
| 3.6.6 | 2026-08-08 | **S3.4/S3.5 证据与评价合同修复 + S3.6 非 LLM baseline 闭环（§9.5 S3.4/S3.5/S3.6）**：(1) Gold-blind inference pack（stage3_inference@1.0.0：item_id/process_id/rule_id/rule_text/check_type，无 decision/candidate/evidence，打乱不变；Winter/Sun 移除 idx%3 与 candidate 路由）；(2) 公共 evaluator：unobservable 按 check_type 统计（仅 incorrect_actor）并区分 4 类原因，主口径=计入分母（FN）+ observable-only 诊断子集，sensitivity 移除 score 重算冒充 gamma sweep；(3) Sun Def 6 论文存在性语义（min<theta 等价 exists；C=process actor+bs_obj 近似披露；theta 证据修正 Figure 9：两模型 0.8/两模型 0.7，0.8 预注册）；sensitivity 真实重算（sun/winter_stage3_sensitivity.py 重跑 scorer，fixture 证明 gamma 改变分母）；(4) 运行收口：stage3_run_common.finalise_run（export_index.json + manifest finalised + 缺 artifact fail closed）+ evidence capsule（outputs/evidence/ 版本化可提交）；(5) S3.6 双 arm（BM25 归一化 Okapi / TF-IDF/SVD numpy 自实现）共享 BaselineScorer + config 预注册阈值；(6) 5 方法同口径 DEV_ONLY 比较（compare_stage3_methods_dev.json，不宣称优劣）；全量 1601 passed/24 skipped；未读 .env/未调 LLM/未改 Gold/BPMN/correction | 5 run manifest + evidence capsule + audit --with-tests + record_change 事件 |
| 3.6.5 | 2026-08-08 | **S3.4 可移植重放收口 + S3.5 Sun Stage 3 development 闭环（§9.5 S3.4/S3.5）**：(1) 公共 Stage 3 contract configs/schemas/stage3_prediction.schema.json + 公共 evaluator scripts/evaluate_stage3_common.py（per-process AP/MAP、binary P/R/F1、三类 violation 逐类+macro/micro、exact type acc、unobservable、denominator、threshold sweep 纯重算、error analysis）；(2) Winter reachability 双模式（corrected_reachability 主版本 / prototype_literal 敏感性）——clean replay s34_..._v2_clean + s34_..._prototype_literal，manifest 1.1.0（implementation hashes/export index/external prerequisites/bpmn 聚合 hash 替代 null），两模式 out_of_order 分数无差异（bug 分支未被数据触发，已记录），v1 原 run 未覆盖；(3) Sun Stage 3 方法级独立重建（Def 4-7 + §5.3 阈值）：sun_model（复用 canonical Process Record；pool 名可观察、lane 名空）、sun_rule_extraction（Gold-blind development adapter）、sun_scorer（matching=max(action,actor/object) 比例、missing=Def5、actor=Def6 含 unobservable、order=Def7 可达性）；config tau/gamma/theta=0.8 预注册 + 固定 sweep；run s35_sun_stage3_development_v1（公共 schema + 公共 evaluator + threshold_sensitivity + comparison_with_winter_dev + error_analysis + manifest 绑定干净 commit）；DEV_ONLY：Winter MAP 0.6429/binary F1 0.6111/violation macro 0.373；Sun MAP 0.8175/binary F1 0.0（tau 下无正预测，如实报告）/violation macro 0.333（missing 全 positive 假象、actor 全 unobservable、order denominator 0）；全量 1586 passed/24 skipped；未读 .env/未调 LLM/未改 Gold/BPMN/correction | 三个 run manifest + audit --with-tests + record_change 事件 |
| 3.6.4 | 2026-08-08 | **S3.4 Winter Stage 3 wrapper development 闭环（§9.5 S3.4 → development wrapper verified）**：Winter et al. (2020) 原型方法转写（只读研究 
eferences/winter_2020_model_check/model_check/lib，代码独立重写不 import）——BPMN 义务任务解析（task/start/end/intermediate events + sequence-flow 可达性）、条款 constraint/obligation/flow 解析（signalwords/sequencemarkers/stopwords，spaCy 依存切分）、Pair 语义（max-similarity mapping、fitness、cost_obligation/cost_resource/cost_so、加权 cost，gamma 0.4/delta 0.8/权重 1/3）；阈值与输入绑定入 versioned config configs/winter_stage3_development_v1.json；唯一入口 scripts/run_winter_stage3_development.py + 评价器 scripts/evaluate_winter_stage3_development.py；58 条冻结候选全量运行（25 matching + 33 violation），产物 outputs/development/s34_winter_stage3_development_v1/（config_snapshot/predictions/evaluation/error_analysis/manifest，DEV_ONLY：matching P 0.44/R 1.0/F1 0.61、mean AP 0.64；violation macro F1 0.37、exact type acc 0.33）；gold-blind（runner 只读 blank pack）、确定性（双跑 byte-identical）、无 LLM/网络；原型差异披露：is_reachable_from 恒真 bug 已修正（否则 out_of_order 恒 0）、participant 为空致 resource cost vacuous、en_core_web_sm 无词向量（与原型同款模型）；新增 12 项聚焦测试；修正 MASTER_PIPELINE P1 里程碑 0/150 残留为 150/150 adjudicated；全量 1566 passed/24 skipped。formal completion blocked on S1.7 and S2.13 | 运行 manifest + audit --with-tests + record_change 事件 |
| 3.6.3 | 2026-08-08 | **S3.2/S3.3 人工裁决完成（§9.5 S3.2/S3.3 → annotation frozen）**：用户逐批裁决全部 58 条候选（25 matching=11 相关/14 不相关；33 violation=missing_action/incorrect_actor/out_of_order 各 11），裁决写入 data/development/human_review/stage3_gold_annotation_human_correction_v1.json（decision 字段=用户裁决、candidate 字段=预填草稿，二者分离记录）；验证脚本新增 --validate-correction 冻结校验（身份/58 条全 adjudicated/decision 合法，fail closed）并生成冻结 manifest s32_s33_gold_annotation_freeze_v1.manifest.json；review 工具新增 --import-decisions 批量导入与 --print-batch 出题模式；.gitignore 忽略 review 备份目录；新增 3 项冻结校验测试；全量 1554 passed/24 skipped。formal Gold 发布仍待 stage3.status 合同门禁（§8.9 链） | 用户裁决导入 + 冻结校验 + manifest + audit --with-tests + record_change 事件 |
| 3.6.2 | 2026-08-08 | **S3.2/S3.3 标注包基础 + 裁决工具（§9.5 S3.2/S3.3 → ready for human review）**：新增 Stage 3 Gold 标注体系——schema configs/schemas/stage3_gold_annotation.schema.json（matching relevance 项 + violation type/evidence 项 + review_state 纪律，禁止推断决策）、构建脚本 scripts/build_stage3_gold_annotation.py（从 S3.1 Process Records + Winter regulations 生成候选：25 matching 候选=相关对+负例、33 violation 候选=每相关规则对三类注入点，并嵌入条款原文 rule_text）、验证脚本 scripts/verify_stage3_gold_annotation.py（身份/冻结流程对齐/候选完整性/rule_text/确定性重建/禁止推断决策，fail closed）+ manifest s32_s33_gold_annotation_blank_v1.manifest.json；交互式裁决工具 scripts/review_stage3_gold_annotation.py（每条显示流程活动+条款原文+预填判定与证据，输入 y/n（matching）或 missing_action/incorrect_actor/out_of_order/none（violation），支持跳过/撤销/断点续审，原子保存+独立备份目录）；空白模板 data/development/human_review/stage3_gold_annotation_blank_v1.json 全 unreviewed；新增 14 项测试；全量 1551 passed/24 skipped。正式 matching/violation Gold 需用户裁决后冻结（S3.2/S3.3 DoD 未完全达成，blocked on adjudication） | 构建+验证+review 工具 + manifest + audit --with-tests + record_change 事件 |
| 3.6.1 | 2026-08-08 | **S1/S3.1 资产恢复与 binding 修复（§9.5 S3.1 → verified）**：从 56d2b03 checkpoint 恢复全部 S1/S3 资产（47+5 文件：configs/schemas/data/docs/outputs/scripts/src/tests/fixtures + 5 个 s1 gate 模块 + process_record.schema.json）；7 个 GDPR BPMN 以批准 LF 字节落地（工作区原 CRLF 变体内容一致、仅行尾，已备份至 `.tmp/untracked_gdpr7_backup_2026_08_08/`）；`data/input/stage1_stage3/gdpr7/*.bpmn` 加入 `.gitattributes` `text eol=lf`（G0-EOL 同纪律）；修复 56d2b03 快照先存的跨任务 binding 过期（s13/s15/s16 合同 upstream manifest hash、5 个 gate 期望、合同 stage1 块），s13/s15/s16/s15_s31 manifest 按当前合同重新生成并全链更新 hash；`verify_stage1_stage3_gdpr7.py` 通过（7 byte-exact、45 activities、135 blank fields）；S1 gate 集成进 status.py/audit.py（`stage1_*_verified`、`stage1_formal_bpmn_membership_locked` pass）；37 项 stage1 测试全绿，全量 1537 passed/24 skipped | 56d2b03 checkpoint 恢复 + verify 脚本重生成 + audit --with-tests + record_change 事件 |
| 3.6.0 | 2026-08-08 | **最终执行总控收敛（§8.9）**：既有任务 ID 为唯一派工主键；G0 改为核账并仅补双口径合同、shared comparison capsule、Barrientos adapter 注册；新增 `S2-BARR-1..5` 专项工作包并规定 L1/L2/L3 与 C1-C4 正交；H1 停止优化且 formal 对照仅可在 capsule 核验后 zero-API 重评或重新授权运行；Stage 3 明确 development/formal 双态、S3.1-S3.3 受控并行和 S3.7 formal 前置；formal Gold 交叉门禁、E00/E10/E01/E11 与论文回填边界固定。同步修正实时门禁与派工入口的过期 0/150/H1 文本 | 2026-08-08 机器完整性检查：freeze_ready=true、formal Gold/final=false；独立审查 findings 的逐项裁决 |
| 3.5.0 | 2026-08-08 | **导师汇报后方向锁定（§8.8 新增四项事实）**：(1) Rules+LLM-Repair（旧代号 H1）**降级为对照方法、不再深究**——全量 150 运行（commit 74614e3）主口径 F1 0.7621 vs Rules-Only 0.7986（净负）、LLM 修复过度抽取 actor（P 0.7077→0.2754），机制正常但 trigger+repair 配方加 FP 不加召回；S2.8 正式 trigger 预注册取消；§8.3 方法表/P4 里程碑/PW3 同步；(2) Rules-Only 与 Direct-LLM **局限性列表+实例**写入 §8.8.2（B0：字段归属错误 C1/C2、词典缺口 13 名词+"It"、Sun-marker 定义口径差异、Tsurgeon 诚实非实现；D1：constraint R 弱 0.417、actor 泛化误抽 P 0.594、高精度保守型、API/预算依赖）；(3) **命名直观化**：B0→Rules-Only（纯规则法）、H1→Rules+LLM-Repair（规则+LLM 修复）、D1→Direct-LLM（直接 LLM），映射表 §8.8.3，机器 ID 不变、methods.json 增 paper_label；(4) **与 Barrientos et al. (2026) 严格对比 + 贡献细模块化**（§8.8.4）：Direct-LLM 拆 8 模块（schema 契约/prompt 工程/few-shot/transport/校验链/预算/双口径评价/可复现资产）、Rules-Only 拆 7 模块；消融矩阵 AB-1..AB-10（列表跑数据：我的模块 vs 换 Barrientos 模块 vs 去掉模块，明确谁好及原因）；论文方法章节目标 4–5 页、禁止只写"调用了 LLM" | 2026-08-08 导师汇报确认；H1 全量运行 commit 74614e3；B0/D1 收口 brief outputs/reports/b0_d1_experiment_closure_brief.md；Barrientos 审计 docs/research/BARRIENTOS_BORROWING_AUDIT_2026-07-12.md；record_change 事件 + audit --with-tests |
| 3.4.34 | 2026-08-06 | formal Gold 发布路径推进 2/4 前置（用户授权按 pipeline）：`experiment_contract.json` route.status→**locked**（最终版方法对齐按方法级独立复现口径完成：B0-R2 verified/crosswalk 11 元素、method_conformance_status 已翻转、official supplement 57 文件 hash 匹配；missing_for_lock 为披露项）与 stage2_dataset.status→**locked_for_human_review**（modality verified + phrase Gold freeze 150/150）；sun_modality_gate.py 中间状态期望同步；5 个状态依赖测试更新；BLOCKERS 7→5（`final_version_route_alignment_pending`/`stage2_dataset_route_relock_pending` 消除，新增 pass `reconstruction_route_locked`/`stage2_dataset_route_locked`）；1486 passed / 24 skipped。剩余前置：stage3.status=locked（需先完成最终子集配置+violation Gold 锁定，S2.11/S3 任务）+ publication gate 白名单精确匹配 | record_change 事件 + audit --with-tests |
| 3.4.60 | 2026-08-13 | **S1.7 正式冻结应用（用户明确授权；基线 9655774b；纠错后 target-aware claim 语义下冻结）**：用户授权（中文原文+英文参考句）记录于 outputs/reports/s1_7_freezer_authorization_v1.manifest.json（sha 7712176c…）——知悉 P2 在 Gold 形成后开发、3 条目标标签进入开发测试、至少一条三元组与 Gold 一致；确认 S1.6 为固定 GDPR-7 描述性组件评价（非 held-out 泛化）；**冻结范围**：评价后未调优的 P2 锁定方法（config/impl/runtime）、现有 P0/P1/P2 预测（锁定+权威副本）、原始指标（数值主体 canonical 19002346…）、Stage 1 Process Gold、已验证正式评价 capsule；**排除**：不改 P2、不选择性重算、零 LLM/API、不改 Stage 2/3 Gold 与 contract、不自动授权 Stage 3 Oracle；24 个资产 hash 绑定（7 BPMN/membership/P2/predictions/metrics/Gold/audit/correction/S1.7v2 包等）；独立 verifier scripts/verify_s1_7_freezer_authorization.py（VERIFIED：授权句逐字、字节锁、safety、exclusions、S1.7v2 包保持 dry_run_not_applied）；audit 新增 pass stage1_s7_freeze_authorized（实际运行授权 verifier；不自动推进 S1.6/S3.7）；S1.7 → **frozen**（正式冻结完成）；S3.7 仍未启动（Oracle 仅经 Stage 3 独立门禁）；本轮零新增 LLM/API，P2/predictions/metrics/Gold/contract/methods/Stage 3 gate 均未修改 | 授权 manifest + verifier + record_change 事件 + audit --with-tests |
| 3.4.59 | 2026-08-13 | **S1 target-overlap claim 纠正 + 正式资产路径纠正 + S1.7 readiness v2（纠错任务；基线 e3583c9；P2 方法/predictions/指标逐位未变）**：**问题一（fixture 与目标重合）**：target-overlap 审计 outputs/reports/s1_p2_target_overlap_audit_v1.{json,md,manifest}（sha 948d268a…；历史测试文件绑定 c704bbc blob）——历史 exact/ws/casefold/punct 重合各 3 条（Communication with data subject/Rectify data/Retrieve data）、当前 fixture 重合 0；Retrieve data 测试断言三元组与人工 Gold 相同、Communication 的 action/object 断言一致；动词表 **200/200**（旧报告 199 纠正，内容未改）；Gold action 首词覆盖 10/13；无 process/activity ID 或逐标签硬编码；结论：开发 target-aware、strict test-blind=false、runtime Gold 隔离与 no post-evaluation tuning 仍成立、指标可保留为固定 GDPR-7 描述性组件评价；独立 verifier（从 git blob 重算历史重合 + 当前零重合，篡改即失败）；**测试纠正**：fixture 3 条重合标签替换为 Collect records/Correspondence with the customer/Update records（不重合、覆盖相同语言边界），新增 zero-overlap 门禁（exact/ws/casefold/punct 全 0、ID 非 GDPR-7、Gold 仅审计用途）；**问题二（正式路径）**：正式权威入口 data/predictions/stage1_formal_v1/（predictions 副本 sha 79a9b2c1… 逐位一致）+ data/results/stage1_formal_v1/（数值主体 sha a072db39…/canonical 19002346…，无 claim metadata）+ outputs/reports/stage1_formal_evaluation_v2.{json,md,manifest,export_index,capsule_manifest}（sha 954122d4…；target-aware claim、绑定 7 BPMN/membership/P2/Gold/evaluator/predictions/audit/correction）；旧 development 产物保留为 historical provenance（数值有效、claim 由 v2 纠正）；**claim correction** outputs/reports/s1_stage1_claim_correction_v2.json（11 个结构化状态：strict_test_blind=false、target_labels_seen_during_development=true、held_out_generalization_claim_allowed=false、evaluation_role=formal_descriptive_component_evaluation_on_fixed_GDPR7 等；准确表述 post-Gold, target-aware Sun/Leopold-style method-level reconstruction with Gold-isolated inference, pre-evaluation code/config lock, and no post-evaluation tuning）；**S1.7 v2**：v1 标记 superseded（superseded_due_to_target_fixture_overlap_and_formal_path_semantics），v2 包 s1_7_freezer_readiness_dry_run_v2.{json,md}（sha be5d4b80…；绑定 audit/correction/200 词/正式路径/P2-predictions-metrics-Gold 未变；7 个独立 verifier 实际运行全过；新授权句含 target-aware 承认；**freeze 未应用**）；audit 新增 pass stage1_claim_correction_verified（实际运行 3 个新 verifier）与检测（target-aware 缺失/strict_test_blind=true/formal 路径指向 development/199 词/audit 缺失/P2-predictions 变化）；16 项纠错 tamper 测试；S1.3/S1.5/S1.6 保持 verified（claim 语义纠正）、S1.7 保持 ready_for_user_freeze_authorization、S3.7 未启动；本轮零新增 LLM/API，P2 config/impl/runtime、predictions、指标、Stage 1/2/3 Gold、contract、methods、Stage 3 gate 均未修改 | 纠错资产 + audit/claim/v2/S1.7v2 + record_change 事件 + audit --with-tests |
| 3.4.58 | 2026-08-13 | **S1.7 冻结 readiness / 授权 dry-run 包（用户授权；Checkpoint B 9372a54 先 push 并经远端核验）**：自包含包 outputs/reports/s1_7_freezer_readiness_dry_run_v1.{json,md}（sha 7cc488b0…）——**状态 `dry_run_not_applied`、目标 `S1.7 ready_for_user_freeze_authorization`（未冻结、未应用）**；24 个资产 hash 全部从磁盘重算（7 BPMN source、membership、Process Record schema/records、correction、P2 config/impl/schema/crosswalk/lock、formal evaluator config/impl、predictions、Gold+manifest+授权、capsule evaluation/manifest）；**5 个独立 verifier 真实运行全过**（七批链/Gold 发布/P2 锁定/predictions 隔离/评价 capsule）；一致性声明（零 API、P2 锁定后未变、Gold 未用于调优、Stage 3 未启动）；回滚/fail-closed 语义；**Stage 3 边界**（S1.7 冻结仅解锁前置，正式 Oracle 须经 Stage 3 独立门禁，本包不自动授权）；精确可复制授权句（只冻结已验证 Stage 1 资产、不改 P2/不重算选择性结果/不新增 LLM-API/不改 Stage 2-3 Gold 与 contract/Oracle 仍按独立门禁）；独立 verifier scripts/verify_s1_7_freezer_dry_run.py（10 项 PASS）+ 6 项 dry-run tamper 测试（status/hash/授权句/P2 配置/verifier 声明 fail-closed）；S1.7 → ready_for_user_freeze_authorization（**正式 freeze 未应用，待用户授权**）；S3.7 未启动；本轮零新增 LLM/API，Gold/contract/Stage 3 gate 未修改 | S1.7 readiness 包 + verifier + record_change 事件 + audit --with-tests |
| 3.4.57 | 2026-08-13 | **S1.6 一次性正式评价完成 + S1.3 P2 verified（用户授权；Checkpoint A c704bbc 先 push 并经远端核验）**：**正式 predictions**（outputs/development/stage1_predictions/formal_predictions_v1.json，sha 79a9b2c1…，7×3 attempts/45 activities；runner scripts/run_stage1_p2_inference.py：P0/P1/P2、P2 双跑 byte-identical、no-overwrite、inputs_read 白名单、gold_read=false 证明；独立 prediction verifier scripts/verify_stage1_predictions.py 13 项 PASS：重渲染一致性=无 Gold 泄漏证明）；**正式 evaluator**（新资产 src/bpc_hybrid/stage1_evaluation_formal.py + configs/stage1_evaluator_s16_formal.json——独立于 experiment contract 锁定的 synthetic evaluator（contract 未修改）；metrics 与 synthetic 合同一致，methods P0/P1/P2，P2 label 验证走 P2 schema，完整重渲染由 prediction verifier 承担）；**一次性评价**（scripts/run_stage1_formal_evaluation.py → capsule outputs/development/stage1_formal_capsule_v1/：evaluation.json（sha e7267593…，scope=formal、one_shot=true、method deltas、per-process triple、limitations 全披露）+ predictions_copy + manifest + export_index；独立 capsule verifier scripts/verify_stage1_formal_evaluation.py 15 项 PASS：报告重跑==存储、输入绑定、P2 锁定未变、零 API、限制披露）；**正式结果（诚实，未调优）**：结构 micro F1=1.0（共享 parser 组件；结构 Gold 来自人工确认的 parser candidate，不包装为独立泛化证据）；语义 micro——P0 all 0（raw 无语义）、P1 P 0.7444/R 0.4963/F1 0.5956/acc 0.4241/triple 0.0、**P2 P 0.8548/R 0.7852/F1 0.8185/acc 0.6928/triple 0.4222**（P2 锁定后未改变；正负结果均保留）；披露：candidate-assisted human adjudication、7 processes/45 activities/135 fields、无显著性推断、不与 Sun 不同数据集绝对分数硬比较、post-Gold lock（非严格 blind preregistration）；**synthetic S1.6 gate 修复**：gate EXPECTATIONS 重绑当前资产 hash、contract evaluator 块改结构一致性检查（contract 文件未修改；历史 hash 绑定自 f628b6b 起与资产不符）、synthetic manifest 重建（语义不变）；7 项正式 capsule tamper 测试（值/副本/manifest hash/P2 配置/限制删除/Gold 篡改 fail-closed）；audit pass stage1_formal_evaluation_verified（实际运行 3 个独立 verifier）；S1.3 → verified、S1.6 → verified、S1.7 仍 blocked（freeze 待授权）；本轮零新增 LLM/API，Gold/contract/Stage 3 gate 未修改 | 正式评价 capsule + verifier + record_change 事件 + audit --with-tests |
| 3.4.56 | 2026-08-13 | **S1.3 P2 方法级独立重建锁定（Sun/Leopold-style；用户授权；Batch 7 661f20b 先 push 并经远端核验）**：**证据 crosswalk**（outputs/reports/s1_3_p2_crosswalk_v1.json + docs/research/S1_P2_CROSSWALK.md）：C1-C5 绑定 Sun 2024 §4.1/§4.2/Fig.3/引文[25]（Leopold 2013）+ 本地全文 hash（947140c3…/65f03a46…/ea624152…）；D1-D4 unavailable_or_underspecified（Leopold 论文不可得、Sun 因篇幅未展开）→ 最小确定性适配；禁止 exact reproduction/Sun original/P1 enhanced/novel/blind 表述，诚实标签 post-Gold paper-derived method reconstruction with a locked implementation and prospective one-shot evaluation；**P2 配置/注册表** configs/stage1_label_p2_v1.json（输入白名单+禁止输入、runtime 锁定 spaCy 3.8.13 + en_core_web_sm 3.8.0 dir sha256 f5c9433c…/26 files、语言规则全参数化、fail-closed、determinism、safety）；**P2 实现** src/bpc_hybrid/stage1_label_semantics_p2.py（Model Context Analysis：lane→pool（XML participant/laneSet 映射）+ Label Style Recognition（verb/noun/degenerate）+ Composition/Semantic Derivation（root 动词+xcomp 复合、obj 子树（det/adj/conj 并入、aux/punct/prep 排除、pobj 并入）、nsubjpass 被动、名词风格 prep.pobj、whether/if/that 从句不并入、命令式 compound+锁定通用英语动词表（199 词，非 GDPR-7 派生））；sidecar schema stage1_label_semantics_p2@1.0.0；**Gold 隔离**：实现/配置/runner 无 gold/correction/adjudication 路径绑定（AST 静态检查+声明检查）、输入白名单、runtime 缺失 fail-closed 不退化 P1；**21 项合成测试**（单/空/多 lane actor、动宾、复合 action、介词、从句、并列、被动、空标签、Unicode 空白、类型一致性、runtime 缺失、双跑 byte-identical、无硬编码、Gold 隔离、P2≠P1 证明）；**独立 verifier** scripts/verify_stage1_p2.py（14 项 PASS：config/impl/schema/runtime/verb 资源/证据 hash/隔离/双跑/禁止 claim）；锁定 manifest outputs/reports/s1_3_p2_locked_v1.manifest.json + 正式 runner scripts/run_stage1_p2_inference.py（P0/P1/P2、双跑、no-overwrite、gold_read=false 证明）；S1.3 → P2 implementation verified and locked；formal inference/evaluation pending（S1.6/S1.7 未推进）；本轮零新增 LLM/API，Gold/contract/Stage 3 gate 未修改 | P2 锁定资产 + crosswalk + verifier + record_change 事件 + audit --with-tests |
| 3.4.55 | 2026-08-13 | **S1.5 正式 Process Gold 冻结 + 发布（用户明确授权；Batch 7 56ae14d 先 push 并经远端核验）**：用户授权句精确记录于 outputs/reports/s1_5_process_gold_freeze_authorization_v1.manifest.json——只发布已记录裁决、不新增/推断/改写决定、保留 source/candidate/correction/七批 chain hashes、冻结后先独立验证再推进（P2 方法级独立重建（Sun/Leopold-style）→ S1.6 正式评价 → S1.7）；P2 边界：仅对无法获得的原始数据与论文未公开参数做预先锁定、完整披露的项目适配，禁止用正式 Gold 调参、禁止以 P0/P1 冒充 P2、禁止声称 exact reproduction；不含 LLM/API、Stage 3 Oracle、contract 修改或其他 Gold 变更；**发布产物**：data/gold/stage1/process_records/stage1_process_gold_v1.json（7 条记录机械复制自 correction，f33aa857…/256,960 B）+ data/gold/stage1/manifest.json（1885dad2…，含 artifact/blank/correction/membership/chain hashes 与 P2 边界）+ 独立 verifier scripts/verify_stage1_process_gold.py（gold==correction 逐字段、gold_process_record canonical==锁定 candidate、授权句精确、七批链仍 VERIFIED、data/gold/stage1 仅含发布内容，全部 fail-closed；21 项 PASS）；AUTH manifest 演进 gold_freeze_authorized=false→true、status → process_gold_freeze_authorized_and_published；链 verifier/audit 授权状态一致性演进（audit pass stage1_process_gold_published；S1.6/S1.7/S3.7 不自动推进）；dry-run 包保留为历史只读快照（verifier 改为包自洽验证）；11 项 process-gold 发布 tamper 测试（值/删/增/结构/artifact hash/授权句/授权标志/删文件/多余文件/correction 链断裂 fail-closed）；S1.5 → verified（frozen+published），S1.6/S1.7/S3.7 未启动；本轮零新增 LLM/API，contract/Stage 3 gate/publication 状态（EStG 侧）未修改 | Gold 发布资产 + 授权/发布 manifest + 独立 verifier + record_change 事件 + audit --with-tests |
| 3.4.54 | 2026-08-13 | **S1.5 第 7/7 批人工裁决导入（gdpr_7_right_to_be_forgotten，用户 2026-08-13 明确确认；Batch 6 847ac11 先成功 push 并经远端逐位核验）**：7 项决定（1 structure accepted_candidate + 6 字段全 present：actor 2/2=Data Controller）；**F1 介词边界**：raw_label 保持 `Communication with data subject`，`with` 不进入 business_object（=data subject，严禁 `with data subject`）；F2 标准切分 Retrieve/data；机械转录（DeepSeek 无推断）；gold_process_record 精确复制 gdpr_7 锁定 candidate（canonical 250bdecd… 逐位匹配，XML 类型 subProcess×2 交叉核验）；链式资产 stage1_adjudications/gdpr_7_right_to_be_forgotten/{decision 39935521…,import_record fb7e069c…,manifest}（before=批次6 after 947487b1…、after=6a9c055a…、prev=gdpr_6）；review tool import（备份 20260813T093515Z）→ validate valid；summary：**7/7 adjudicated、135/135 resolved、freeze_ready=true（142/142，0 unresolved）**；**七批链式 verifier（blank→b1..b7→磁盘逐位重放 6a9c055a…）VERIFIED**；Batch 1–6 记录逐字段不变；19 项 batch7 focused tests（F1/F2 精确值、action/object/actor/activity-id/raw_label/XML 类型/source/candidate/membership/process_id/前节点/sequence-flow/授权句篡改 fail-closed、删批/重复前驱/中链断裂/换批/最终不一致 fail-closed）；**冻结 readiness 演进**：AUTH manifest status → `human_adjudication_complete_freeze_authorization_pending`（gold_freeze_authorized 保持 false）、verifier/audit 新增 complete_freeze_pending 状态（audit pass `stage1_human_adjudication_complete_freeze_pending`，142/142 仅 freeze-READY 事实非冻结授权）、freeze_ready 篡改语义翻转（7/7 后 False 即篡改）；**freeze authorization dry-run 包** outputs/reports/s1_5_process_gold_freeze_authorization_dry_run_v1.{json,md} + 独立 verifier scripts/verify_s1_5_freeze_dry_run.py（链/统计/hash/声明/授权句/未发布 Gold 全 VERIFIED）；S1.5 → adjudication complete / freeze pending，S1.6/S1.7/S3.7 未启动；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | gdpr_7 裁决资产 + 七批链 verifier + dry-run 包 + record_change 事件 + audit --with-tests |
| 3.4.53 | 2026-08-13 | **S1.5 第 6/7 批人工裁决导入（gdpr_6_right_to_rectify，用户 2026-08-13 明确确认；Batch 5 d896516 先成功 push 并经远端核验）**：7 项决定（1 structure accepted_candidate + 6 字段全 present：actor 2/2=Data Controller、E1 Rectify/data、E2 Communicate/the rectification）；**raw label 尾随换行边界**：E2 raw_label 保留尾随 \n（源 XML `&#10;`、锁定 candidate name 同），action/business_object 语义值不含换行或尾随空白（明确裁决非证据清理）、business_object 保留冠词 the；机械转录（DeepSeek 无推断）；gold_process_record 精确复制 gdpr_6 锁定 candidate（canonical 5f2ee37a… 逐位匹配）；链式资产 stage1_adjudications/gdpr_6_right_to_rectify/{decision,import_record,manifest}（before=批次5 after 1afabb87…、after=947487b1…、import sha 7f98dd61…、prev=gdpr_5）；review tool import（备份 20260813T075834Z）→ validate valid、freeze false；summary：6/7 adjudicated、129/135 resolved（剩余 6 字段+1 结构=7 项人工决定）；六批链式 verifier（blank→b1..b6→磁盘逐位重放）VERIFIED；9 项 batch6 focused tests（E2 换行保留/删除换行 fail-closed、action/object 带换行或 尾随空白 fail-closed、去冠词 fail-closed、泛化篡改、gdpr_7 未预填、summary/freeze）；S1.5 保持 in_progress（6/7、129/135），S1.6/S1.7/S3.7 未启动；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | gdpr_6 裁决资产 + 链式 verifier + record_change 事件 + audit --with-tests |
| 3.4.52 | 2026-08-12 | **S1.5 第 5/7 批人工裁决导入（gdpr_5_right_to_withdraw，用户 2026-08-12 明确确认）**：16 项决定（1 structure accepted_candidate + 15 字段全 present：actor 5/5=Data Controller）；**复合 action 锁定**：D1 action=Stop running、D2 action=Stop using（严格禁止退回单首词 Stop）；**if/that 从句边界**：D3 business_object=withdrawn data（不并入 if 从句）、D5 business_object=the user（that 从句为通知内容不并入）；D4 保留 the withdraw（不改 withdrawal、不删冠词）；机械转录（DeepSeek 无推断）；gold_process_record 精确复制 gdpr_5 锁定 candidate（canonical 6053ce18… 逐位匹配）；链式资产 stage1_adjudications/gdpr_5_right_to_withdraw/{decision,import_record,manifest}（before=批次4 after 6befc63c…、after=1afabb87…、import sha 310de1ed…、prev=gdpr_4）；review tool import（备份 20260812T135821Z）→ validate valid、freeze false；summary：5/7 adjudicated、123/135 resolved（剩余 12 字段+2 结构=14 项人工决定）；五批链式 verifier（blank→b1..b5→磁盘逐位重放）VERIFIED；12 项 batch5 focused tests（复合 action 拆分/object 退回 P1 余串 fail-closed、if/that 从句并入 object fail-closed、withdrawal/去冠词 fail-closed、泛化篡改、gdpr_6/7 未预填、summary/freeze）；S1.5 保持 in_progress（5/7、123/135），S1.6/S1.7/S3.7 未启动；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | gdpr_5 裁决资产 + 链式 verifier + record_change 事件 + audit --with-tests |
| 3.4.51 | 2026-08-12 | **S1.5 第 4/7 批人工裁决导入（gdpr_4_right_of_portability，用户 2026-08-12 明确确认）**：10 项决定（1 structure accepted_candidate + 9 字段全 present：actor 3/3=Data Controller、action Retrieve/Retrieve/Communicate、business_object available data of the data subject（不窄化）/elaborations/data and elaborations（不拆并列））；机械转录（DeepSeek 无推断）；gold_process_record 精确复制 gdpr_4 自己的锁定 candidate（canonical a1d77e89… 逐位匹配；禁止复制 gdpr_3 candidate）；**gdpr_3/gdpr_4 独立身份证明**：共享 raw XML process id （sid-C2A304F9-…）由 membership identity adapter 消歧——数据集级 process_id/source input_id/pool process_ref 全绑定各自身份（gdpr_4 source 68601777…/31497 B、gdpr_3 source d6e48d09…），候选、决策、导入、manifest 资产各自独立（gdpr_3 资产逐字节 不变），查找键含 process 边界（无跨 process activity 匹配）；链式资产 stage1_adjudications/gdpr_4_right_of_portability/{decision,import_record,manifest}（before=批次3 after a4f65b1a…、after=6befc63c…、import sha 3f293930…、prev=gdpr_3）；review tool import（备份 20260812T115047Z）→ validate valid、freeze false；summary：4/7 adjudicated、108/135 resolved（剩余 27 字段+3 结构=30 项人工决定）；四批链式 verifier（blank→b1→b2→b3→b4→磁盘逐位重放）VERIFIED；11 项 batch4 focused tests（4 批重放、gdpr_4 身份绑定、gdpr_3/4 共享 raw id 不冲突、gdpr_3 candidate 复制给 gdpr_4 fail-closed、source 错绑 fail-closed、跨 process 匹配 fail-closed、gdpr_3 资产 不变、C1 窄化/C3 拆并列 fail-closed、标签/activity/candidate/hash/链断裂/summary/未裁决/freeze）；verifier 增加 corr_rec 缺失防御（跨 process 改名 tamper 不再抛异常）；S1.5 保持 in_progress（4/7、108/135），S1.6/S1.7/S3.7 未启动；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | gdpr_4 裁决资产 + 隔离证明 + record_change 事件 + audit --with-tests |
| 3.4.50 | 2026-08-12 | **S1.5 第 3/7 批人工裁决导入（gdpr_3_right_to_access，用户 2026-08-12 明确确认）**：10 项决定（1 structure accepted_candidate + 9 字段全 present：actor 3/3=Data Controller、action Retrieve/Retrieve/Communicate、business_object available data of the data subject（不窄化、保留后置限定语）/elaborations/data and elaborations（不拆并列））；机械转录（DeepSeek 无推断）：gold_process_record 精确复制锁定 candidate（canonical sha256 4f2daa7b… 逐位匹配）；presentation-only factual correction：只读裁决包展示表曾把 C1/C2 标为 task，真实 XML 类型为 subProcess（C3 为 task）——锁定 candidate 始终正确，展示错误未写回 BPMN/candidate，已在本批证据中记录；链式资产 stage1_adjudications/gdpr_3_right_to_access/{decision,import_record,manifest}（before=批次2 after da8f1b05…、after=a4f65b1a…、import sha 455805a5…、prev=gdpr_2）；review tool import（备份 20260812T100637Z）→ validate valid、freeze false；summary：3/7 adjudicated、99/135 resolved（剩余 36 字段+4 结构=40 项人工决定）；三批链式 verifier（blank→b1→b2→b3→磁盘逐位重放）VERIFIED；9 项 batch3 focused tests（3 activities/9 fields 派生、类型核验、C1 窄化/C3 拆并列 fail-closed、actor/action 篡改、activity ID 缺失/增加、candidate/hash/import/链断裂、summary/未裁决/freeze）；S1.5 保持 in_progress（3/7、99/135），S1.6/S1.7/S3.7 未启动；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | gdpr_3 裁决资产 + 链式 verifier + record_change 事件 + audit --with-tests |
| 3.4.49 | 2026-08-12 | **S1.5 第 2/7 批人工裁决导入（gdpr_2_consent_to_use_the_data，用户 2026-08-12 明确确认）**：73 项决定（1 structure accepted_candidate + 72 字段全 present）；机械转录（DeepSeek 无推断）：gold_process_record 精确复制锁定 candidate （canonical sha256 fb6ec966… 逐位匹配）；裁决边界（保留大小写/拼写 purposses/rectify of、business_object 不含引号与 if 谓词、actor 24/24=Data Controller）；链式证据资产 stage1_adjudications/gdpr_2_consent_to_use_the_data/{decision,import_record,manifest}（manifest：before=批次1 after 2c10c78f…、after=da8f1b05…、import sha 55a83587…、prev_process=gdpr_1_data_breach）；review tool import（原子保存+备份 20260812T092843Z）→ validate valid、freeze false；summary：2/7 adjudicated、90/135 resolved（剩余 45 字段+5 结构=50 项人工决定）；链式 verifier（blank→gdpr_1→gdpr_2→磁盘 correction 逐位重放）VERIFIED；14 项 batch2 focused tests（72 字段派生、if 偷换/引号偷加/purposses 纠正均 fail-closed、链断裂/import hash/候选篡改等）；S1.5 保持 in_progress（2/7、90/135），S1.6/S1.7/S3.7 未启动；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | gdpr_2 裁决资产 + 链式 verifier + record_change 事件 + audit --with-tests |
| 3.4.48 | 2026-08-11 | **S1.5 第 1/7 批人工裁决导入（gdpr_1_data_breach，用户明确确认）**：用户裁决 19 项（1 structure accepted_candidate + 18 字段全 present）；机械导入（DeepSeek 仅转录，无推断）：gold_process_record 精确复制自锁定 stage1_gdpr7_process_records_v1.json（canonical sha256 0f842984… 逐位匹配）；可重放证据资产 outputs/development/human_review/stage1_adjudications/gdpr_1_data_breach/（decision_v1.json + manifest：before correction sha 与 blank 一致、after 2c10c78f…、candidate/bpmn/membership hashes、llm_api_calls=0、gold_freeze_authorized=false、DeepSeek 机械转换声明）；通用增量裁决 verifier scripts/verify_stage1_human_adjudication.py（10 项 fail-closed 检查，后续 6 批复用：决策资产/manifest hash、process id 唯一、correction==decision、gold==锁定 candidate canonical、candidate hash、18 字段逐项、其他 record 不变、raw_label/lane_labels 不变、summary 一致、freeze false；任一篡改非零退出）；review tool import 原子保存+备份+summary 重算；correction summary：records 7、adjudicated_records 1、label_fields 135、resolved_label_fields 18、freeze_ready false；audit 语义演进：correction 与 blank 一致时 stage1_review_surface_input_ready → 存在已验证裁决时 stage1_human_adjudication_in_progress（要求每一处 correction-vs-blank 差异有 versioned 决策资产支撑 + verifier 通过；无证据修改立即 error stage1_human_adjudication_invalid）；10 项篡改测试（字段值/额外字段/candidate 内容/candidate hash/其他 record/summary/manifest 缺失/freeze 提前/决策不一致）；S1.5 → in_progress；S1.6 正式评价、S1.7 freeze、S3.7 Oracle 未启动；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | 裁决资产 + 增量 verifier + 审计演进 + record_change 事件 + audit --with-tests |
| 3.4.47 | 2026-08-11 | **S1.5 人工 Process Gold 核对界面授权开放（input-ready only）**：用户明确授权开放 S1.5 review surface——冻结 GDPR-7 全七 BPMN membership（7 BPMN/45 activities/135 label fields，membership payload SHA-256=e88caf81… 已核对一致）、允许使用 stage1_review_tool.py、全空白/unreviewed 的 stage1_gdpr7_human_correction_v1.json 与双语 HUMAN_PROCESS_GOLD_GUIDE.md 供用户本人裁决；工具不得推断/预填/自动接受任何决定；本授权只设 S1.5 为 input-ready，不授权 Gold freeze（freeze 仍需用户 7/7 structure decisions + 135/135 字段裁决）；授权记录 s1_5_review_surface_authorization_v1.manifest.json（8 项前置检查全过：membership payload 匹配、correction==blank、7/7 unreviewed、无 Gold 预填、freeze_ready=False、tool/guide/schema 存在）；audit 新增 pass stage1_review_surface_input_ready（correction 被改动或授权缺失时 fail closed → error stage1_review_surface_not_ready）；MASTER_PIPELINE S1.5 行 blocked → input_ready（freeze 仍 blocked）；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改，未创建或推断任何人工 Process Gold | 授权 manifest + audit pass + record_change 事件 + audit --with-tests |
| 3.4.46 | 2026-08-11 | **S1.5 人工 Process Gold 核对准备 + S1.6/S1.7/S3.7 后续入口（Checkpoint 3）**：(1) 非破坏性 review 工具 scripts/stage1_review_tool.py（list/show/export/import/backup/validate/undo：import 仅应用用户显式 decisions 并原子保存+备份、非法状态 fail-closed、绝不推断 decision；操作对象仅为用户可编辑 correction 文件，immutable blank 模板不动）；(2) 双语 HUMAN_PROCESS_GOLD_GUIDE.md（中文+英文：decision 含义表、空 lane/隐含 actor/gateway/循环/并行/不可达路径处理、candidate 编辑方式、freeze 条件；仅用户可设 reviewed/adjudicated）；(3) S1.5 input-readiness dry-run（s1_5_input_readiness_dry_run：membership 7 BPMN/45 activities/135 label fields/payload e88caf81…；review surface 7 记录全 unreviewed、142 未决（135 字段+7 结构）、correction 与 blank 逐字节一致、无 Gold 预填证明；expected workload；before/after（授权仅开 review surface，freeze 仍需 7/7+135/135）；含可复制授权句）；S1.5 正式门禁未应用；(4) S1.6 evaluator synthetic verification 确认（s1_6_evaluator_synthetic_verification_v1：仅 synthetic、formal run blocked until human Process Gold）；(5) S1.7 freeze checklist（s1_7_freeze_checklist_v1：input/output/method/metrics/hash/manifest 清单，output=human Process Gold 尚不存在，blocked on S1.5）；(6) S3.7 Oracle readiness v2（s3_7_oracle_readiness_v2：真实 Gold Rule Records 不存在、真实 Gold Process Records 不存在、Stage 2 方法预测非 Rule Records、parser candidate 非 Process Records、依赖 S1.7/S2.13/S3.4-S3.6、Oracle 未启动）；5 项新聚焦测试（tool 行为 + readiness 结构）；S1.5-S1.7 保持 blocked；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改、未创建/推断人工 Process Gold | review tool + guide + readiness 包 + record_change 事件 + audit --with-tests |
| 3.4.45 | 2026-08-11 | **Stage 1 S1.1-S1.4 现状核账与确定性验证（Checkpoint 2）**：(1) S1.1-S1.4 逐任务矩阵（s1_1_s1_4_matrix_v1.json/.md）：每项列出代码/schema/config/fixtures/tests/manifest/已满足 DoD/真实缺口/状态——S1.1 verified（Process Record schema + fixtures + validator）、S1.2 verified（确定性解析 + 7/7 GDPR 双跑 byte-identical）、S1.3 partial（P0/P1 机械标签语义完成，P2 未实现，actor/action/object 仅机器 candidate 非 Gold）、S1.4 verified（control_flow 12 键 + 分支/并行/循环/不可达 fail-closed 测试）；(2) GDPR-7 双跑确定性验证器 verify_stage1_gdpr7_determinism_v1.py：两次解析 7 个 BPMN byte-identical 且与 membership 锁定的 stage1_gdpr7_process_records_v1.json 逐字节一致；manifest s1_1_s1_4_determinism_v1（input/schema/config/implementation hashes、safety：零 API、不用 Stage 3 Gold 调 Stage 1、不推断人工决定）；(3) MASTER_PIPELINE 总表 S1.1/S1.2/S1.4 → verified、S1.3 → partial（精确缺口 P2）；S1.5-S1.7 保持 blocked（人工 Process Gold 未开始）；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | 矩阵 + 确定性 manifest + record_change 事件 + audit --with-tests |
| 3.4.44 | 2026-08-11 | **Stage 2 正式结论收口 + S2.11 许可/G0.7 adapter 资格证据（Checkpoint 1）**：(1) stage2_formal_conclusion_v1.json/.md/manifest/export/独立 verifier（conclusion d882a5e2…、verifier 16fd36f5… VERIFIED）：正式名称 Rules-Only/Direct-LLM/Rules+LLM-Repair（comparison-only），旧代号仅 Pipeline 对照；仅授权 G0.4 口径（粗五字段主报告 + modality label 单独 + 细五字段诊断 + evidence-span unavailable；不引用历史六字段 development aggregate）；论文安全结论：Direct-LLM 领先 action/condition/constraint 与 modality label accuracy、Rules-Only 领先 actor/exception、Rules+LLM-Repair 净负保留对照停止优化；披露数据规模 150 句、重建方法（paper-faithful independent reconstruction，非 Sun 原始/exact reproduction）、历史调用 300、新增 0、无显著性推断；每条结论回指 报告/manifest/hash；**B0-R5/D1-R5 → verified**（正式结论 DoD 达成），H1 保持 comparison-only 结论，三方法正式比较不因 S2.11/S2.13 未完成而降级；(2) paper/CLAIM_EVIDENCE_MATRIX 更新：头注正式结果、C07 PLANNED→VERIFIED（共享已达成）、C09 更新（正式比较确认净负）、新增 C23（三方法正式字段级互补结论）与 C24（B0-R5/D1-R5 结论包）；(3) **日期修正**：10 处无依据的 2026-08-12 引用全部改为 2026-08-11（status/audit docstring、MASTER_PIPELINE S2.10/S2.12 行与 changelog 3.4.42/3.4.43、s2_11 dry-run、测试断言、构建脚本），机器 UTC timestamp 保持实际生成时间；(4) S2.11 许可与 adapter readiness v2（s2_11_license_adapter_readiness_v2）：本地许可证据核账 （references/barrientos_2026 无 LICENSE/README/metadata 声明 → 四类均为 unknown_pending_confirmation，不自行推断）；外部证据 pending（本地无权威 URL/DOI，未用搜索片段代替）；S2.11 精确缺口清单 （许可/激活授权/映射决策/人工 Gold/G0.5 冻结/adapter 实现）；条件未达 → 不发出授权句；(5) G0.7 Barrientos adapter registry dry-run（g0_7_barrientos_adapter_registry_dry_run）：schema/标签/数据/指标/许可注册、modality 3→4 不可直接映射边界、precondition/norm/temporal→span adapter 边界、definition/span 对齐/cross-reference/evidence provenance、synthetic fixtures only、外部标签永不自动成为 Gold；9 项 adapter 契约 fail-closed 测试（synthetic）；G0.5/S2.11 正式状态未改变；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | 结论包 + matrix 更新 + 许可/adapter readiness + record_change 事件 + audit --with-tests |
| 3.4.43 | 2026-08-11 | **正式三方法比较 + S2.10 verified + S2.12 描述性分析 + S2.11/S2.13 dry-run（Checkpoint B，零 API）**：(1) stage2_formal_three_method_comparison_v1.json/.md/manifest/export/独立 verifier（report c9d76544、manifest dc41eb4b、verifier 22c23331，verifier VERIFIED）：只使用授权口径（粗五字段主报告 + modality label 单独 + 细五字段诊断 + evidence-span unavailable 不混历史六字段 aggregate）；逐方法 per-field P/R/F1、label 指标、方法间 delta 矩阵、粗五字段均值（描述性）、历史调用成本（B0 0/D1 150/H1 150）与新增 0、结论回指 hash（H1 净负停止优化、D1 优势 action/condition/constraint+label acc、B0 优势 actor/exception召回、共同局限 evidence-span、三方法 ready ≠ 全 Pipeline 完成）；(2) S2.10 → verified（授权后 DoD 真实满足）；S2.12 → partial（正式描述性共同错误分析交付、retrospective 标注，full DoD blocked on S2.11）；(3) S2.11 数据资格与映射协议 dry-run（s2_11_data_qualification_mapping_dry_run：Barrientos 2026 资料与 Stage1 GDPR-7 只读核验、schema 映射与 modality 3→4 不兼容、adapter 边界、L1/L2/L3 复杂度候选（G0.5 未冻结）、可比/不可比指标、需人工 Gold、外部标签不得冒充 Sun-compatible Gold 防护、hash/manifest/export 方案、before/after；授权条件未达到 → 不发出授权句；G0.5/S2.11 正式状态未改变）；(4) S2.13 gap capsule（s2_13_stage2_freeze_gap_capsule：完成项与剩余项精确清单，明确 final_experiment_ready=true = 三方法正式评价资产就绪 ≠ S2.13/全项目完成；S2.13/S1.7/S3.7 未标完成、无伪 Oracle）；本轮零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | 比较报告 + S2.12 分析 + S2.11 dry-run + S2.13 gap + record_change 事件 + audit --with-tests |
| 3.4.42 | 2026-08-11 | **final-readiness 真实 fail-closed 验证 + 残留语义清理（Checkpoint A）**：(1) 可复用验证模块 src/bpc_hybrid/formal_arm_verification.py——精确 method→manifest→predictions→results→capsule→verifier 映射（ARM_REGISTRY）；每个 arm 从磁盘重算 manifest hash、逐项校验 method_id/claim_scope=formal/is_formal_performance_result/预测与结果文件存在且 hash 匹配/input-Gold 绑定重算/new calls=0 声明；comparison capsule 重核：input v2/Gold hash 重算、G0.4 semantic hash 三方一致（manifest vs comparison vs derived artifact 重算）、三 arm manifest 磁盘 hash 与 per_method 记录逐项比对、main_view_publishable/授权一致、all_three_published_and_verified 由验证结果派生（自报值不再作为输入）；(2) status.py formal_final_gate_conditions() 改用 verify_all_static()（不信任自报）；audit.py 三方法 ready 分支实际执行 verify_all_with_verifiers()——三个独立 verifier 以 subprocess 真实运行（非仅查文件存在），全过 → pass final_gate_conditions_met，否则 methods_unexpectedly_ready error；(3) 篡改 fail-closed 验证：三 arm 各一 artifact、direct_llm manifest method_id、comparison capsule per_method hash、G0.4 manifest semantic hash 共 6 类篡改 → verify_all_static 全 False、audit 出现 methods_unexpectedly_ready error、final_experiment_ready=false（配置 ready 单独不能维持门禁）；9 项新 tamper tests；(4) 授权前残留语义清理：G0.4 contract claim_scopes.formal 更新为三方法均 formal；coarse role/consequence 改为“历史六字段 aggregate 不可正式发布、授权五字段+label 主报告可发布”；coarse manifest not_publishable_reason → historical_aggregate_not_publishable_reason；comparison capsule not_comparable 更新（三方法均 formal，不可比对象为历史六字段 aggregate）；methods.json sun_rule_only notes 移除“candidate result 尚未发布”表述（正式发布 2026-08-11），明确三方法 ready ≠ S2.13/S1.7/S3.7 完成；release manifest v2 因 methods_config hash 变化同步重发布（8b3cbd2e，verifier 全过）；1703 tests passed；零新增 LLM/API，Gold/contract/Stage 3 gate/publication 未修改 | formal_arm_verification 模块 + tamper tests + 语义清理 + record_change 事件 + audit --with-tests |
| 3.4.41 | 2026-08-11 | **用户四项正式授权应用（zero-API，门禁最终打开）**：(1) G0.4 正式主报告授权——句子级粗粒度五 span 字段（actor/action/condition/constraint/exception）+ 单独四分类 modality label 指标；modality evidence-span 明确 unavailable （不置零、不纳入 aggregate）；细粒度五字段诊断/对照；历史六字段 coarse aggregate 仅 development provenance；Gold 未修改、未伪造 modality evidence spans；g04_evaluation_views_contract_v1.json 记录授权，coarse view manifest main_view_publishable 翻转为 true（授权记录在案）；(2) direct_llm 门禁 ready（formal_status=ready、command_status=formal_ready_candidate_authorized），默认 zero-API 发布已绑定 D1-R3 snapshot：publish_snapshot_formal_arm.py --method direct_llm → data/predictions/direct_llm_formal_arm_v1 + data/results + reports （claim_scope=formal、is_formal_performance_result=true、new calls 0、独立 verifier VERIFIED、snapshot 字节锁定 9188093c）；(3) sun_llm_fallback 方案 A 应用（formal_status=ready、command_status=formal_ready_candidate_authorized、role=comparison_arm_only、notes 明确停止优化与 comparison-only 边界），zero-API 发布已绑定 H1 snapshot → sun_llm_fallback_formal_arm_v1（snapshot 字节锁定 4fd7c116、verifier VERIFIED）；(4) final-readiness fail-closed 加固实施：status.py formal_final_gate_conditions() （三方法 capsule 完整 + G0.4 合同授权 + comparison capsule 全 hash 一致——input v2/Gold/三 arm manifest 磁盘重算比对），final_experiment_ready 必须同时满足；audit.py methods_unexpectedly_ready 条件化（条件真实满足 → pass final_gate_conditions_met，不再无条件 error）；comparison capsule v2 重建（三方法 claim_scope=formal、main_view_publishable=true、formal_arm_capsules.all_three_published_and_verified=true、新 hash 4aaaef13）；**条件全部真实满足 → final_experiment_ready=true、BLOCKERS 0、ERRORS 0**（非仅配置翻转：三 capsule + verifier + comparison 一致 + G0.4 授权全部落地）；tests 更新 11 文件（门禁断言 True、capsule complete、unexpected-ready 条件化）；1694 tests passed；本轮未调用任何 LLM/API，Gold/experiment_contract/Stage 3 gate/publication status 未修改 | 三 formal arm capsule manifest + comparison v2 + 加固代码 + record_change 事件 + audit --with-tests |
| 3.4.40 | 2026-08-11 | **shared comparison hash correction + 门禁 dry-run 验收缺陷修正**：(1) comparison capsule 错误绑定修复——build_d1_h1_zero_api_reevaluation_v1.py 与已生成 comparison capsule 曾硬编码错误 coarse-view semantic hash （d15061d7...5c3），权威值为 d15061d74b41c58dd4278f0a675327099453564090005f9b58b1d352de5cfe39（G0.4 manifest derived_view.semantic_sha256 与 committed derived artifact 重算一致）；硬编码已删除，新增 _authoritative_coarse_view_hash()：从 G0.4 manifest 读取 + derived artifact 重算 + B0 formal manifest G0.4 声明三方交叉验证，任一不一致 fail closed；D1/H1 reevaluation manifest/comparison capsule JSON+MD 重建（capsule 新 hash 89992562...、manifest 8ce1dac0...）；D1/H1 predictions 字节未变（D1 9188093c...、H1 4fd7c116...，与 registry/manifest 锁定一致），新增 API 调用 0；篡改/硬编码错误 hash 测试全部失败关闭；(2) D1/H1 方法门禁 dry-run v2 事实修正（不应用）：Direct-LLM——保留候选未授权，明确 150-row snapshot 已绑定 formal input v2，授权后默认路径 = 该 snapshot zero-API 正式 publication（不重调 API），仅绑定失效或用户明确要求重跑才需新预算，删除 v1 "正式运行必然需要新 LLM budget" 错误表述；Rules+LLM-Repair——保留 comparison-only/停止优化，明确 snapshot 授权后可 zero-API 发布为正式 comparison arm，纠正 v1 错误主张：comparison_only_ready 不被现有 status/audit 识别为 ready（blocker 不会减少），列出两方案（A 推荐：formal_status=ready + role/notes 标记 comparison-only，不动 audit/status 语义；B：保留 comparison_only_ready 但需同步修改正式终态集合与 audit/status 语义）并给出模拟后 blocker 状态；(3) final-readiness hardening dry-run 包（outputs/reports/final_readiness_hardening_dry_run.json/.md）：记录缺陷（status.py 仅凭 formal Gold+三方法 ready+input/Gold 文件存在即可置 final_experiment_ready=true，不要求 三方法 capsule 完整、不要求 G0.4 主合同授权；audit.py 三方法全 ready 时无条件 methods_unexpectedly_ready error），内存最小复现（三方法全 ready → final gate 提前打开 + unexpected error 并存；D1 单独 ready → false；H1 comparison_only_ready 不被识别 → false），提出 fail-closed 目标语义（正式终态集合 + 三 capsule 独立 verifier 通过 + comparison capsule 全 hash 一致 + G0.4 主口径用户授权，此前 final_experiment_ready 必须 false，授权且真实满足后 不再报 methods_unexpectedly_ready，配置翻转不能提前开门），含代码/测试/文档变更清单与统一授权句；(4) G0.4 决策建议 dry-run（不应用）：正式主报告 = 句子级粗粒度五 span 字段 + 单独 四分类 modality label 指标；modality evidence-span 明确 unavailable 不置零不纳入 aggregate；细粒度五字段诊断/对照；历史六字段 coarse aggregate 保留 development provenance；main_view_publishable 未翻转；本轮未应用任何方法门禁、未调 LLM/API、未改 Gold/contract/Stage 3 gate/publication status；新增 12 项聚焦测试 | comparison capsule 重建 + v2 决策包 + hardening dry-run + record_change 事件 + audit --with-tests |
| 3.4.39 | 2026-08-10 | **D1/H1 zero-API 重评 + shared comparison capsule + S2.10/S2.12 partial 状态**：D1-R3（s27_d1_v6_r3_clean_rerun_150_hist56d_v1）与 H1（s28d_h1_150_v4pro_v1）历史 150 条 predictions 逐项核验绑定（150 IDs、input text hash vs formal input v2、prompt lock、schema-valid 全过）后用与 B0 完全相同的 Gold 视图/合同/evaluators 做 zero-API 重评 → outputs/evidence/d1_h1_zero_api_reeval_v1/（d1/h1 各自 reevaluation + comparison_capsule + manifest）：D1 coarse 五字段 F1 0.7579/0.9437/0.8380/0.7427/0.7619（与历史粗口径逐位一致）、H1 coarse 0.4296/0.8945/0.7774/0.6200/0.8800；claim scope：B0=formal，D1=candidate/formal-gate-blocked，H1=candidate/comparison-only/formal-gate-blocked；comparison capsule 绑定 input v2/Gold/视图/预测 schema/normalization/evaluators/三方法 snapshot hash/claim scope/gate 状态/历史调用数（D1 150 + H1 150）/本次新增调用 0/可比与不可比边界（modality evidence-span 三方法均 unavailable；历史粗数字仅 development provenance）；D1/H1 结果未写入 data/predictions 或 data/results，未标 claim_scope=formal；D1/H1 各自方法门禁 dry-run 决策包（direct_llm / sun_llm_fallback 分开：exact before/after、zero-API 绑定证据、风险、预期 audit 变化、可复制授权句）**未应用**；S2.10 → partial（B0 formal arm 组件评价 verified，全方法比较待授权）；S2.12 → partial（描述性/探索性基础设施，retrospective 非 preregistered，full DoD blocked on S2.11）；S2.13 full DoD、S1.7、S3.7 未标完成；未启动 Stage 3 Oracle 或端到端实验 | comparison capsule + decision packages + record_change 事件 + audit --with-tests |
| 3.4.38 | 2026-08-10 | **治理/证据一致性修复 + G0.4 双口径评价合同 + B0 正式 arm 工具链**：(1) 授权包矛盾修复：sun_rule_only_method_gate_authorization_dry_run.json 拆分 proposal （dry_run_not_applied，历史提议）与 application（applied_by_user_authorization_2026_08_10，commit 6a29766 应用）双状态，过时 post-authorization 命令改为正式入口 run_b0_formal_arm.py（不再指向 outputs/development candidate 目录冒充正式发布）；(2) 实时状态文本同步：MASTER_PIPELINE B0 方法表（B0-R4 candidate verified + 方法门禁授权，B0-R5 blocked on 正式结果发布）、AGENTS.md 静态状态（formal_gold_publication_ready=true、route locked、Gold 已发布、freeze true；门禁定义未变）、PROJECT_AUDIT 残留不一致修正；(3) **证据缺口记录**：授权包引用的 outputs/development/b0_r4_formal_candidate_v1/manifest.json 被 .gitignore 排除、远端历史不存在——正式 B0 capsule 必须自包含（versioned manifest 携带 input/实现/方法门禁/evaluator/语义结果 hash），本 checkpoint 的正式 arm 设计即消除该依赖；(4) **G0.4 双口径评价合同** configs/evaluation/g04_evaluation_views_contract_v1.json：粗（句子级，Sun 对齐主口径）与细（clause 级，诊断/对照）视图分离、禁止跨口径混表、模态四分类 label 指标单独报告、六字段按固定 Sun literal-overlap 主合同、strict/token/clause/actor-action 仅诊断；正式粗视图由已发布 Gold 确定性派生（src/bpc_hybrid/g04_coarse_view.py，共享归一化）；**一致性核验结论：semantic hash 不匹配 （d15061d7 vs 历史 6e19cf3c）——已发布 Gold 的 modality 为纯字符串，局部 modality evidence span 不可恢复（147/150 条仅 modality evidence 不同，其余字段逐位一致）→ 按合同**停止粗口径主正式指标发布**，历史粗数字保留 development provenance；粗视图五字段 span 指标与历史逐位一致（actor 0.8203/action 0.8927/condition 0.7738/constraint 0.6182/exception 0.8800）可正式报告；(5) 正式评价模块 src/bpc_hybrid/formal_stage2_evaluation.py：五字段 span 指标 + modality label 四分类 + modality evidence-span unavailable（明示原因，绝不静默置零）+ 计时隔离（canonical 产物无计时，telemetry 单独）；(6) 正式 B0 arm 入口 scripts/run_b0_formal_arm.py（claim_scope=formal、is_formal_performance_result=true、前置 fail-closed：release v2 verifier 全过 + sun_rule_only ready + D1/H1 仍 blocked；输出 data/predictions/b0_formal_arm_v1 + data/results/b0_formal_arm_v1 + outputs/reports manifest/export/capsule/独立 verifier，no-overwrite/staging/原子 rename）；(7) audit 方法覆盖区分：formal_predictions_results_capsule_not_produced（空）→ formal_predictions_results_capsule_partial（部分方法覆盖，列出已发布方法）→ complete（三方法全覆盖，pass）；单文件不再被误读为完整三方法 capsule；聚焦测试 11 项（粗视图一致性/评价模块/前置 fail-closed/方法覆盖） | 授权包修复 + G0.4 合同 + 粗视图证据 + record_change 事件 + audit --with-tests |
| 3.4.37 | 2026-08-10 | **sun_rule_only 方法门禁授权应用**：用户明确授权仅修改 configs/methods.json 中 sun_rule_only 的 formal_status （blocked_final_sun_stage2_reimplementation_required → ready）与 command_status （development_only_not_formal → formal_ready_candidate_authorized）；sun_llm_fallback/direct_llm/experiment_contract/stage3 gate/Gold/publication status 均未修改；未调用任何 LLM/API。release manifest v2 的 methods_config implementation hash 同步重发布（v2 input/Gold 字节不变），verifier 53 项全过；audit formal_methods_not_ready 从 3 方法减为 2 方法（sun_llm_fallback/direct_llm），final_experiment_ready 仍 False（其余两方法未就绪），methods_unexpectedly_ready 未触发；test_sun_modality_gate 隔离边界断言更新（sun_rule_only=ready + 其余 blocked）；authorization dry-run 包追加 application_status=applied。B0-R4 promotion 完成，formal 三方法比较仍待 D1/H1 LLM 授权 | methods.json diff + record_change 事件 + audit --with-tests |
| 3.4.36 | 2026-08-10 | **formal benchmark input v2 修正 + 发布审计加固 + B0-R4 formal candidate 闭环**：data/input/estg150_formal_inference_input_v2.json （150 条 Gold-blind 可执行输入：sample_id/approved_text_en/raw_text_de/language/source_ref/input_text_sha256/provenance，零裁决内容，文本与冻结 Layer E 逐位一致，membership payload 与冻结文件一致），v1 input 保留并标记 membership-only; not sufficient as executable model input（sidecar STATUS.md）；formal_benchmark_release_v2.manifest.json/.md/export_index 绑定 v1 限制、v2 输入、已发布 Stage2/Stage3 Gold（未改动）、implementation/source hashes、授权 commit 5d56f03；独立 verifier verify_formal_benchmark_release_v2.py（53 项磁盘重读核验）接入 audit：pass formal_benchmark_release_verified / error formal_benchmark_release_invalid（篡改即败）；frozen capsule 语义拆分（formal_gold_capsule_frozen pass + formal_predictions_results_capsule_not_produced warning，predictions/results=0 不再误读）；过时状态文本修正（0/150 input-gate-only、route reopened、publication paused 移除）；b0_d1_formal_readiness_v2：D1-R3/H1 历史 150 条 predictions 与 formal input v2 逐项绑定核验全部通过（IDs/文本 hash/prompt/model/sampling/schema-valid）→ zero-API candidate 重评允许，无新 API 调用；B0-R4 formal candidate runner （Gold-blind，只读 v2+锁定资产）150 条全量运行 + 双跑语义 byte-identical：主口径 F1 0.71865（P 0.6845/R 0.7564，与 B0-R3 快照逐位一致）；方法授权 dry-run 包 （sun_rule_only before/after、绑定 hash、正式运行命令、预期 audit 变化、回滚）未应用；S2.13 仍 blocked（S2.1-S2.12 full DoD 未达成），Gold publication subtask verified、executable input v2 verified、B0-R4 formal candidate verified / promotion pending、S2.10/S2.12 blocked on 正式三方法结果 | release manifest v2 + verifier + readiness v2 + candidate manifest + record_change 事件 + audit --with-tests |
| 3.4.35 | 2026-08-10 | **S2.13（Gold publication subtask）formal Gold 实际发布**：`scripts/publish_formal_gold_v1.py` 正式运行（用户明确授权，基线 30eab2c）→ `data/input/estg150_formal_input_v1.json`（150 ids，membership payload `a9a746d1…` 与 estg_150_membership_hashes.json 逐位一致）、`data/gold/stage2/estg150_formal_gold_v1.json`（150 条 decision-only Gold，span 文本逐条回指 approved_text_en，decisions 全 ∈{accepted,edited,rejected}，零 LLM 草案/元数据泄漏）、`data/gold/stage3/stage3_matching_gold_v1.json`（25）+ `stage3_violation_gold_v1.json`（33）（item_ids 与冻结 correction 对齐、decision-only）、`outputs/reports/formal_gold_publication_v1.manifest.json` + `.md`；发布器确定性重放验证通过（no-overwrite 字节一致，manifest git 快照排除自身输出后稳定），34 项发布后验证全通过（schema/hash/membership/decision-only/许可排除/计数）；audit `formal_capsule_not_frozen` 解除（input=1/gold=3，`_meaningful_count` 递归修复，BLOCKERS 3→2）；B0-R4/D1-R4 行 ready 核账：共享输入/Gold/evaluator 齐备，剩余 blocker 分别为缺 formal claim_scope 运行入口 / 缺 LLM 授权预算 → 本轮 zero-API 核账不执行任何重评（不调 API、不伪造 Rule/Process Records、不提升 development 指标）；S2.10/S2.12 仍 blocked on 正式三方法运行 | 发布 manifest + record_change 事件 + audit --with-tests |
| 3.4.33 | 2026-08-06 | **S2.2 裁决冻结达成**：用户 2026-07-18 完成的 150/150 Layer E 裁决（adjudicated、reviewer=user）经用户授权从 56d2b03 历史 blob 恢复至活动 v2 文件（v2 工作流 2026-07-16 重建时未迁移；新脚本 `scripts/restore_layer_e_adjudication_from_56d2b03.py`，按 sample_id 合并 6 个用户输入字段、保留 llm_candidate 等、备份+validate_global 双真+原子替换）；gate 2 `human_review_freeze_ready` **False→True**（150/150 adjudicated、900/900 decisions、approved 150/150），BLOCKERS 8→7（`annotation_freeze_pending`→pass `annotation_freeze_ready`）；S2.2 行 → verified；S2.9 行 → verified（D1 侧锁定 + S2.2 frozen 依赖满足）；`validate_layer_d_v2.py` layer_e_pristine FALLBACK 语义更新（0/150 计数器不再适用，promote 从不写 Layer E，字节保护由 run_config sha256 主路径承担）；15 个状态依赖测试更新 + 3 项 restore 测试；1486 passed / 24 skipped。formal Gold 发布仍 blocked：route/data/stage3 各自重锁 + publication gate 状态白名单精确匹配；随后 D1-R4/B0-R4 三方法正式比较解锁 | Layer E 恢复 manifest + validate_global 报告 + record_change 事件 + audit --with-tests |
| 3.4.32 | 2026-08-06 | D1-R3 完成：锁定配方固定快照干净重跑（150 calls v4pro 官方API thinking-disabled 无json_object 4096/temp0/top_p1；prompt sha 3aa64877、model 三态、sampling/transport 与 estg150_d1_active_registry_v1.json 逐项一致）；150/150 有效、0 验证失败、0 LLM 错误、0 事故；新评估脚本 scripts/evaluate_d1_r3_clean_rerun.py（git show 56d2b03 只读提取 Layer E/membership → build_canonical_gold_records，membership sha e8e62686 与注册绑定一致 → 同一进程双评 R1/R3）；R1 重评 F1 0.773495 与已登记数字逐位一致（评估路径交叉验证）；R3 F1 0.775625（P 0.879268/R 0.693839，missed 323 vs R1 327）；逐字段 F1 delta：modality −0.01123/actor −0.02778/action +0.00051/condition +0.00660/constraint +0.02094/exception +0.05929；失败类型分析（1055 gold span）：R3 matched 732/wrong_field 169（constraint 100 最大头）/not_extracted 154（constraint 69），R1 matched 728/wrong_field 185/not_extracted 142；结论=固定快照复现 R1 并微优（+0.0021，噪声范围），可重放性验证成功；D1-R3 行 → verified；D1_ERROR_ANALYSIS.md §8 追加 R3 失败类型小节；PROJECT_AUDIT 同步。D1-R4 仍 blocked on formal Gold | D1-R3 experiment_run 事件 + evaluation_d1_r3_20260806.json + audit --with-tests（1483 passed） |
| 3.4.31 | 2026-08-06 | D1-R2 锁定完成：新增 `configs/models/estg150_d1_active_registry_v1.json`（schema `estg150_d1_active_registry@1.0.0`）——v6 prompt（sha 3aa64877，与磁盘/loader/run manifest 三方 hash 一致）、v5 七月基线（79f6f76f，不可改）、deepseek-v4-pro fail-closed 钉死、sampling（temp 0/top_p 1/max_tokens 4096）、seed 策略 `unsupported_or_omitted`（官方 API 无 seed，可复现依赖 temp0，manifest 记录实际发送值）、transport 配方（thinking-disabled、无 json_object）、共享输入（input_150_hist56d_v1.jsonl，sha c7dffcc4）与 evaluator（sun_literal_overlap_evaluation@2.0.0，config sha 352113b5）、预算合同（每批逐批用户授权+`--max-calls` 硬上限 150、无授权不批）、D1-R1 VERIFY-PASS 运行登记（manifest sha 87cb1bea）；新增 12 项 lock-config 测试（含 S2.9 Gold 不可见核查：6 个 few-shot 合成 fixture 与 150 测试句相等/嵌入零交叠）；§8.7 D1-R2 行 → verified；§8.5 S2.9 行 DoD（D1 侧）达成注记，整行保持 partial（S2.2 未 frozen）；PROJECT_AUDIT/AGENT_RUNBOOK 同步。下一步=D1-R3（固定快照干净重跑 150 calls + 错误分析，需用户逐批授权） | D1-R2 lock-config 12 项 focused 测试 + audit --with-tests + record_change 事件 |
| 3.4.30 | 2026-08-04 | 新增 §8.7 D1 方法级复现修复 Pipeline（D1-R0–R5，与 §8.6 B0 同构同门禁）：D1-R0 整合（ready，核验 run_direct_llm.py + prompt loader + s28_s29 产物 tracked）→ D1-R1 低召回修复（4 个子批次：FIELD-TYPING 双向收益 / PROMPT-CONTRACT / VERIFY-PASS / CLEAN-RERUN）→ D1-R2 锁定 → D1-R3 快照+错误分析 → D1-R4 三方法共享 Gold → D1-R5 结论；硬约束含逐批 LLM 授权+硬预算。新增 docs/D1_ERROR_ANALYSIS.md：D1 低召回根因（constraint 215/354 漏抽=99 进 action+91 未抽+16 进 condition；prompt 省略指令与 few-shot 缺口；运行事故 lost104/recovery26）；字段归位理论 R 上限 0.288→0.699 | 用户指示"与 B0 同理，列出 D1 pipeline 严格逐点修复"；D1 逐字段重算分析 |
| 3.4.29 | 2026-08-04 | B0-R3 由进行中改为 **verified**：快照运行（F1 0.71865）+ 最终态错误分析（B0_ERROR_ANALYSIS §8）均完成；至此 B0-R0–B0-R3 全部 verified，B0 完善阶段结束；B0-R4（三方法正式比较）待 formal 门禁重锁，B0-R5 待 B0-R4 | B0-R3 experiment_run 事件 + §8 错误分析事件 |
| 3.4.28 | 2026-08-04 | 状态行更正：B0-R1 由 ready 改为 **verified**（§8.6.1 七个子批次全部闭环，DoD 三条验收线达成）；B0-R3 由 blocked 改为 **进行中**（56d2b03 快照运行完成 F1 0.71865 + manifest，正式错误分析待补）；B0-R4/R5 仍 blocked on formal Gold | §8.6.1 各批次事件与 manifest |
| 3.4.27 | 2026-08-04 | 三项用户授权执行并入库：(1) LEXICON-DECISION 路径 b——13 个 actor 名词以 `authorized_local_frozen_estg150_gap_2026_08_04` 加入 v2 词典（治理覆盖严格记录；覆盖/未覆盖 P/R 分别报告）；(2) B0-R2 门禁翻转——`method_conformance_status` 改为 `verified_method_level_independent_reconstruction`，`sun_stage2_baseline_not_paper_faithful` blocker 按设计解除（BLOCKERS 9→8），B0-R2 行状态 verified；(3) B0-R3 固定快照运行（最终方法+授权词典，56d2b03 输入）——主口径 F1 **0.71865**（P 0.6845/R 0.7564），优于原始 0.71019，按用户条件授权标记为论文依据候选；actor F1 0.8039（R 0.958），覆盖 47/48（P 0.692/R 0.979/F1 0.811）未覆盖 1/48（代词 "It"）；§8.6.1 LEXICON 行更新；formal 门禁（Gold 冻结/route/stage3）仍锁定 | 用户授权逐字记录 + B0-R3 experiment_run 事件与 manifest |
| 3.4.26 | 2026-08-04 | B0-R1-LEXICON-DECISION 治理分析与 CLAUSE-REVIEW 复核入库：13 个无词典覆盖 actor 名词的扩展违反 S2.3 公开种子构造模式（`public_marker_sources_en_v2.json` construction_mode=pinned_public_seed，9 来源全为公开引证）与"不看 Gold 调规则"硬约束（缺口选择由开发 Gold 驱动）→ 需用户决策，合规路径 a/b/c 写入 §8.6.1 与 B0_ERROR_ANALYSIS；CLAUSE-REVIEW 复核结论=不改动（v2 口径不依赖 clause 对齐，58 个真正漏抽中仅 4 个在未配对 clause）；C7 过短边界判定为质量类（any-overlap 口径无主指标收益）暂缓 | 治理约束复核 + 分析证据 |
| 3.4.25 | 2026-08-04 | B0-R1-ACTOR 实测结果入库（commit f82b2b7+b0548c1，run v2）：真实 CoreNLP 取证（8 个词典内漏抽=5 个无情态 nsubj + 3 个 obl+case by/to），修复=clause 内全 nsubj 弧候选 + obl/by-to + 首个过滤候选胜出 + actor 中心词词典校验（排除自身 case 介词与尾部标点）；实测主口径 F1 0.71024→0.71205（**+0.0018，本系列首个正向 delta**），R +0.0066、P −0.0023，actor F1 0.616→0.670，8/8 漏抽找回；v1 无中心词校验 −0.0021 被拒（迭代验证）；§8.6.1 ACTOR 行更新；C7 过短边界留待后续 | B0-R1-ACTOR experiment_run 事件与运行 manifest（v1/v2 两轮） |
| 3.4.24 | 2026-08-04 | B0-R1-ALIGN 实测结果入库（commit fcf7b34）：DE↔EN cue 对应验证（`_cross_validates` 语言学情态映射表+否定极性+数字锚，equal-count/monotone/split 三路径统一，split 连接词优先切点+逐片验证）；validated 107→49（validated_split 42→0）、unsupported 30→72，"无伪 validated" DoD 达成；主口径 span 指标不变（F1 0.71024），label 面板 79.33%→78.85%（−0.48pp 记录代价），strict clause accuracy 0.6407→0.6364，independent82 macro F1 +0.0012；判定保留（正确性 DoD 项），validated_split=0 记为副作用待细化；§8.6.1 ALIGN 行更新 | B0-R1-ALIGN experiment_run 事件与运行 manifest |
| 3.4.23 | 2026-08-04 | B0-R1-ACTION 与 B0-R1-SCOPE-DISAMBIG 实测结果入库：ACTION（commit 00f4ad8+efb3d14）主口径 F1 +0.00005（持平），质量收益（主语开头 8→0、strict-exact action 3.0×），定性为边界质量修复而非主口径驱动项；SCOPE-DISAMBIG（commit a3ad64f+2de85b0）候选真实运行 F1 −0.0005（负），按 §8.6 迭代规则拒绝并回退，44 个同界双发中 43 个为双 tregex（registry 模式重叠），根因=gold 对 "to the extent"/关系从句语义内部不一致，不读 Gold 前提下规则层不可安全消歧，记为方法局限；§8.6.1 子批次表两行更新 | B0-R1-ACTION / B0-R1-SCOPE-DISAMBIG 的 experiment_run 事件与运行 manifest |
| 3.4.22 | 2026-08-04 | B0-R1 推进与子批次拆分：(1) B0-R1-E2 真实离线重评（`sun_literal_overlap_evaluation@2.0.0`、同一 canonical Gold 双评 v10a/C3：F1 0.7099→0.7102，旧 clause-aligned 0.5398→0.5326 被推翻，非主口径结论）；(2) B0-R1-ERR 逐 span 错误分析（`docs/B0_ERROR_ANALYSIS.md` + `scripts/analyze_b0_error_types.py`）：79% missed 内容在其它字段、80% 错误预测压其它字段 Gold；根因 C1 action 吞并（matched action 中 192/212 过长、中位超 54 字符）、C2 constraint↔condition 混淆（114+31）、C7 under-extension（202 个 matched 过短，modality evidence 80）、C3 modality label 79.3%、C4 actor missed 22（8 依赖失败+14 词典缺口）、C5 clause 38/231、C6 结构性限制；B0-R1 行完成信号更新，新增 §8.6.1 子批次表（ACTION/SCOPE-DISAMBIG/ALIGN/BRIDGE/ACTOR/LEXICON-DECISION/CLAUSE-REVIEW）与每批验收纪律（重评协议 + delta 记录）；B0-R3 正式错误分析保留 | 用户指示"寻找 B0 准确率不高的原因并做成文档、逐个修复"；B0-R1-E2/B0-R1-ERR 的 `experiment_run`/`change` 事件与 manifest（commit bcd3193/02dea72） |
| 3.4.20 | 2026-08-01 | 新增 B0-R0–B0-R5 方法级复现修复 Pipeline：以 Sun 核心组件、顺序和宽松同字段 overlap 为主对照；确定性代码错误、泄漏、不可复现和口径不一致为硬门禁，作者资产缺失或单字段权衡改为披露项；明确修复后负结果可进入正式结论 | 用户确认“方法级复现即可作为正式结论”，并要求避免代码错误、不要用过严门禁卡死、对照 Sun 宽松要求并持续记录日志 |
| 3.4.21 | 2026-08-02 | B0-R0 verified：actor_action.py + 12 个 b0_v10 模块 + sun_style/lexicon_v2_runtime + estg150_b0_development v1/v2/v3/v10 + corenlp_runtime/sun_b0/bert_textcnn + stage2_evaluation v1/v3 + 7 个 v2 lexicon 资源 + SunPhraseRuleBatchBridgeMulti.java + sun_corenlp_runtime.json + sun_b0_s26_candidate_B_v1.json + sun_bert_textcnn_s24.json + estg150_b0_enhanced_s27_v10a.json + estg150_b0_v10_preregistration_v2.json + stage2_evaluator_s210_v3.json + stage2_prediction.schema.json + scripts/run_estg150_b0_enhanced_v10_development.py + test_b0_v10_integration_contract.py（15 验收点） 已纳入 main；audit 在 `sun_rule_only.method_conformance_status='blocked_until_b0_r2'` 下同时保持 `b0_paper_faithful_components_present` pass 与 `sun_stage2_baseline_not_paper_faithful` blocker；外部 441MB checkpoint / CoreNLP jar / Legal-BERT cache 仍为 external runtime prerequisites（未提交、未下载、未复制）；B0-R1 ready、B0-R2–B0-R5 仍按依赖 blocked；run_b0_batch_v10 / --help 离线验证通过；未运行 CoreNLP、未读 Gold/Layer E、未调 API、未改 D1/H1；先前 6341136 的 B0-R0-C0 仅依赖闭包，状态从 COMPLETE 修正为 verified，correction event 已追加 | 用户确认修正 6341136 误报，要求 audit 区分 component presence 与 method-conformance；要求补齐 v10 runner + CoreNLP bridge + pattern registry + s26/s24 配置 + v10 默认配置 + 离线集成测试 |
| 3.4.19 | 2026-08-01 | S2.8D-R6C1 安全补完 R6 剩余 5 个冻结 plan（原 order 6–10），形成完整 10-plan pilot 证据（用户授权新增 hard cap=5、retry=0、每 plan 至多 1 次、禁止重调 order 1–5、禁止重跑原 10-call 命令）：阶段 A 验证游标修复（37ab7ef）并实现 continuation 模式（--continuation-plan，schema h1_pilot_continuation@1.0.0）：调用前 fail-closed 绑定父 frozen plan hash/keys、prior R6 manifest/capture hash、prior telemetry 恰好 order 1–5 各一次、无 order 6–10 先例、continuation 恰为 order 6–10、交集空、并集=父 10 plan、5 个不同 sample、model/prompt/B0 hash、risk/repair_fields/reasons、--max-calls=5、与 --frozen-plan/--exclude-plan 互斥；新增 configs/s28d_r6c1_h1_remaining_pilot_plan_v1.json（sha f0946bdd…）与 29 项测试（30 验收点，含 combine 测试）；阶段 B 0-API plan-only：selected=5/5、orders=[6..10]、calls=0、交集空、覆盖 10/10、byte-identical；阶段 C 唯一一次真实命令：**actual new API calls=5**（order 6–10 各 1 次；order 1–5 新调用=0；retry=0；无 early stop；模型/capture 全对）；结果：proposed=5、accepted=1、rejected=4（canonical_invalid=4、reference_mismatch=4）、effective=1、changed=1、H1!=B0=1、gate=true、identity violation=0；canonicalizer reanchored 5/5（already-valid 1、reanchored spans 12、zero/amb/contract=0）；usage 总 9652（8000/1652）；continuation replay（s28d_r6c1_h1_remaining_pilot_replay_v1，0 API calls）逐项一致、byte-identical；新 scripts/combine_h1_pilot_runs.py 合并 R6+R6C1 为完整 capsule（s28d_r6_complete_h1_small_pilot_v1）：10/10 覆盖、keys sha=bb8d73b2…、每 plan 一次、10 不同 sample、identity 0、byte-identical；合并指标：calls=10、proposed=10、accepted=4、rejected=6、effective=4、changed=4、H1!=B0=4、effective rate=0.40、usage 总 18628（15634/2994）；P/R=not_computed；下一步 S2.8D-R7 完整 10-plan Gold-blind 结果审计与受控 P/R 评价解锁准备 | R6C1 manifest sha 38421f74…、capture sha 0e48bcb5…；continuation focused 29 passed；audit --with-tests；5 new real API calls、retry 0；Gold/Layer E/.env 未读；P/R not_computed |
| 3.4.18 | 2026-08-01 | S2.8D-R6 执行冻结的 10 次真实 deepseek-v4-flash H1 小规模 pilot（用户明确授权 hard cap=10、retry=0、每 plan 至多 1 次、不补选、不扩大）：主真实命令只执行一次；**实际 API calls=5**（≤10），5 个已调用 plan 恰为冻结 order 1–5（estg_000118/000133/000164/000206/000207），每 plan 1 次、HTTP 200、extraction=ok_message_content、requested/resolved/returned 均 deepseek-v4-flash、capture 全部绑定、无未冻结 plan、retry=0；结果：proposed=5、accepted=3、rejected=2（coordinate_canonicalization_zero_match=1、canonical_invalid=1、reference_mismatch=1）、effective=3、changed=3、H1!=B0=3、h1_non_identity_gate=true、identity violation=0；canonicalizer：reanchored 4/5、failed 1/5、already-valid spans=1、reanchored spans=7、zero=1/ambiguous=0/contract=0；usage 总 8976（7634/1342）；**early stop 触发于 order 5 之后，记录原因 plan_key_mismatch，但取证为误报**：R5 runner early-stop 计数缺陷（coordinate-canonicalization-failed 分支未推进 frozen-order 游标）导致防御性 plan-key 检查错位；已修复（游标改为 selected plan 处理开始时统一推进）+ 新增 3 项回归测试（含 frozen-plan 离线 transport replay 子集绑定保留 early-stop 状态，runner 放开 frozen+offline-transport-replay 限制）；未调用 order 6–10 保留 pilot_early_stop_not_called、不补跑；离线 replay（s28d_r6_h1_small_pilot_replay_v1，0 API calls）重建 5 个真实响应：逐 plan H1/B0 hash、accepted/effective/changed/rejection、identity、聚合计数与真实运行一致，同路径 byte-identical；机制最低可用门 passed=true（5 calls、identity=0、effective=3、changed=3、H1!=B0=3）；P/R=not_computed；下一步 S2.8D-R7（Gold-blind pilot 结果审计与受控 P/R 评价解锁准备）+ 用户决定是否授权完成剩余 5 个冻结 plan（未调用、不再调用） | 真实 manifest sha 69ea63b2…、capture sha 5c3db68b…；H1 focused 109 passed；audit --with-tests；5 real API calls、retry 0；Gold/Layer E/.env 未读；P/R not_computed |
| 3.4.17 | 2026-08-01 | S2.8D-R5 冻结 Gold-blind 小规模 H1 pilot 计划（10 calls、预算与执行门禁；0 real API calls、retry 0、未运行 pilot）：历史真实调用集合只读恢复（5 个 real_api run：canary 1 + v4-flash pilot 19 + v4-pro 偏差 20 + R1 canary 1 + R4 canary 1 = 42 calls，去重 20 个 plan keys，keys sha c813a384…）；Gold-blind 确定性选样复用现有 build_repair_plans + risk 排序，排除历史已调用 keys、每 sample 取首个 plan、取 10 个不同 sample；新 frozen plan 配置 `configs/s28d_r5_h1_small_pilot_plan_v1.json`（sha 35dc6a75…，含 B0/prompt sha、budget cap=10/retry=0、early-stop 策略、历史 keys、10 个 plan 的 risk/repair_fields/reasons/各 hash）；新 `src/bpc_hybrid/h1_pilot_plan.py` 纯函数模块 + runner `--frozen-plan` 严格绑定（B0 attempts/manifest sha、prompt variant/sha、model、plan 存在性、clause_index/risk/repair_fields/reasons、b0/clause/context hash、10 个不同 sample、execution_order 1-10、历史交集为空；`--max-calls` 必须 10、与 `--exclude-plan` 互斥；任一不一致调用前 fail closed）；early-stop 合同实现（provider model mismatch / capture binding failure / 调用计数越界 / plan key mismatch / 连续 3 次 transport-extraction 失败 → abort_remaining，剩余 plan 标记 pilot_early_stop_not_called、不补选；patch 级拒绝 record_and_continue）；默认行为（无 --frozen-plan）不变；plan-only 验证（新目录 s28d_r5_h1_small_pilot_plan_check_v1）：selected=10/10、llm_calls=0、real_api=false、patch 0/0/0、gate=false、H1==B0（150 样本逐位一致）、execution order 与 frozen 一致、keys sha 一致、历史交集空、同路径 byte-identical；新增 29 项测试覆盖 30 个验收点；H1 focused 106 passed；P/R=not_computed；下一步 S2.8D-R6 十次真实 pilot 需用户单独授权 | 0 real API calls；Gold/Layer E/.env 未读；B0/trigger/risk/prompt/validator/schema/model gate 未改；P/R not_computed |
| 3.4.16 | 2026-08-01 | S2.8D-R4 单次真实 deepseek-v4-flash canary（用户明确授权硬上限 1、retry 0，coordinate canonicalization 已启用）：run_id=s28d_r4_h1_canary_v1，requested/resolved/returned 模型均 deepseek-v4-flash；policy stream=false、thinking.disabled、response_format=json_object、tools 未发；HTTP 200、extraction=ok_message_content、reasoning=false、tool_calls=0、usage=1305/405/1710；模型返回 1 个非空可解析 patch（content 1531 chars，sha e7514386…）。Coordinate canonicalizer 正常执行：status=reanchored、3/3 span 唯一 exact 重锚（modality.evidence[0] [0,99]→[0,95]、actors[0] [55,99]→[49,95]、conditions[0] [100,211]→[97,207]，occurrence=1），zero/ambiguous/contract=0；original patch sha 810a433c…→canonicalized sha c9014f7c…。现有 canonical validator 通过、atomic merge accepted、effective_patch=true、changed=1、h1_non_identity_gate=true、H1!=B0（B0 sha 57f3564b…→H1 sha 5bcf26d7…，与 R3 离线重放 merged hash 逐位一致）、identity 字段不变；R1/R3 历史结果未改。离线 replay（新目录 s28d_r4_h1_canary_replay_v1，0 API calls）重建同一 capture：H1 sha 与真实运行一致、byte-identical。P/R=not_computed；未进入 pilot；formal S2.8 仍 blocked on S2.6 | 真实 canary manifest sha 9734c2ed…、capture sha 92df6817…；focused 71 passed；audit --with-tests；1 real API call、retry 0；Gold/Layer E/.env 未读；P/R not_computed |
| 3.4.15 | 2026-07-31 | S2.8D-R3 fail-closed unique exact-text coordinate canonicalization（development mechanism verified，0 real API calls）：新 `bpc_hybrid/h1_span_canonicalizer.py` 纯函数模块——Python/Unicode code point、0-based、end-exclusive、相对完整 source_text；搜索窗口严格为 clause_span；匹配纯 exact（无 strip/normalize/lower/fuzzy/语义）；already-valid 不动；clause 内唯一 exact match 才重锚 start/end；zero/ambiguous/contract violation 整 patch fail closed（稳定错误码）；只修改 start/end，其余字段深拷贝不变；relation 字段不处理；原子化无部分修复。接入 runner 单一共享路径（parser 后、apply_patch_envelope 前），覆盖 offline-patches/offline-replay/offline-transport-replay/allow-llm 四模式；per-event 脱敏审计 + manifest 聚合统计；_rejection_codes 映射三个稳定码。validator/prompt/schema/B0/trigger/risk/budget 未改。R3 离线 transport replay（同一 R1 capture 重建行，行 hash 96f8bbdc…）：canonicalization=reanchored、3/3 span 重锚（[0,99]→[0,95]、[55,99]→[49,95]、[100,211]→[97,207]，occurrence=1）、zero/ambiguous=0、canonical validator 通过、merge accepted、effective_patch=true、changed=1、gate=true、H1!=B0（H1 hash 5bcf26d7…与 R2 counterfactual merged hash 逐位一致）、identity 不变、重放 byte-identical。R1 历史 strict 结果（accepted=0/gate=false/H1==B0/canonical_invalid+reference_mismatch）未改。新增 26 项测试 + 更新 span-mismatch 测试（invented text 现在以 zero_match 整体拒绝）；全量测试 | 新增 26 项 S2.8D-R3 测试；focused 88 passed；全量检查；0 real API calls；Gold/Layer E/.env 未读；P/R not_computed |
| 3.4.14 | 2026-07-31 | S2.8D-R2 canary span/offset 离线取证（Gold-blind、forensic-only，0 real API calls）：逐 span 脱敏诊断证明 3/3 被拒 span 均为**正确文本、错误坐标**——文本在 source_text 与 clause 窗口内均唯一 exact match（无 zero/ambiguous），`end` 全部恰好超界 +4 字符（start Δ 0/+6/+3）；排除 Unicode/byte 混淆（纯 ASCII）；clause_span.start==0 使 frame 混淆在本样本不可区分（列为限制）。Strict replay（同一 decoder→parser→validator→merge）复现真实 canary 拒绝：canonical_invalid=1、reference_mismatch=1、accepted=0、effective=0、changed=0、gate=false、H1==B0。Diagnostic-only counterfactual（仅修正 start/end 到唯一 clause 内 exact match，文本/id/field/label/relation 不动，zero/ambiguous 即 fail closed）通过同一 validator 与 atomic merge：schema+cross-field valid、merge=accepted、effective_patch=true、gate=true、identity 字段不变；counterfactual 仅诊断，未覆盖 strict 结果、未写入真实 prediction。Prompt coordinate contract 审查（未修改）：`text == source_text[start:end]` 明确存在；0-based/end-exclusive/code-point 单位仅由示例隐含、逐 span 自检指令缺失、frame 表述歧义；masked 字段未隐藏 offset 所需信息。**结论：情况 A → 唯一推荐 S2.8D-R3：fail-closed unique exact-text coordinate canonicalization（本轮未实现）**。新增 `scripts/s28d_r2_canary_forensics.py` + 17 项离线测试；证据 `docs/research/S28D_R2_CANARY_OFFSET_FORENSICS.md/.json` | 全量测试 + experiment/change 事件；0 real API calls；Gold/Layer E 未读；P/R not_computed |
| 3.4.13 | 2026-07-31 | S2.8D-R1 单次 v4-flash canary（用户明确授权硬上限 1、0 retry）完成，**未达 non-identity 门**：requested/resolved/returned model 均为 deepseek-v4-flash；显式 policy 为 stream=false、thinking.disabled、response_format=json_object；HTTP 200，`chat.completion`，`finish_reason=stop`，`ok_message_content=1`，reasoning=false，usage=1305 prompt + 436 completion = 1741 tokens。响应形成 1 个 schema-valid patch envelope，但 span text/offset 与 source reference 不一致，原子 canonical 校验以 `canonical_invalid` + `reference_mismatch` 拒绝；valid=1、proposed=1、accepted=0、effective=0、changed=0、gate=false，H1 仍等于 B0。脱敏 capture 已保存且无凭据；未重试、未进入完整 pilot；历史真实调用累计 41 次，P/R 仍 not_computed | `outputs/development/s28d_r1_h1_canary_v1/manifest.json` + sanitized capture；全量 1137 passed, 24 skipped；experiment_run event |
| 3.4.12 | 2026-07-31 | S2.8D-R1 DeepSeek transport 离线修复（development contract verified，0 real API calls）：新 `bpc_hybrid/h1_transport.py`（显式 H1 request policy：stream=false/thinking.disabled/response_format=json_object、tools 不发；纯函数 `decode_chat_completion_envelope` 十个稳定 extraction status codes；reasoning 只存 presence/length/hash、tool arguments 只存 name/length/hash、Responses API/SSE/invalid JSON 全 fail closed；递归敏感键脱敏保留 usage 数值；安全 endpoint 描述）；`RealAPITransport` 与离线 replay 共用同一 decoder 并暴露 last_decode/last_request_policy/last_request_body_sha256；runner 新增 `--transport-capture`（--allow-llm 必需，调用前拒绝）与 `--offline-transport-replay --transport-responses-jsonl`（严格绑定，byte-identical 重放，无时间戳）；空 content 现在产生稳定 rejection code（如 empty_final_content）而非泛化 other；manifest 记录 transport 节（policy sent、safe endpoint、capture path/hash、extraction_status_counts、raw_response_saved=false）；新增 11 个 envelope fixtures 与 44 项全离线测试（合法 content→effective patch/gate=true；reasoning/tool/output/delta 均不被误当 patch；15 项验收全覆盖）；canary 未授权未运行 | 新增 44 项 S2.8D-R1 测试；focused 193 passed；全量检查 |
| 3.4.11 | 2026-07-31 | S2.8D v4-flash 真实 pilot 执行完成，**结果：未达最低成功门（如实报告失败）**：canary 1 次 + 剩余 19 次 = 20 次新调用（硬上限精确满足）；每次调用 requested=resolved=provider-returned 均为 deepseek-v4-flash（模型身份全部验证）；但 20/20 响应内容为空（sha256==空串），valid=0、effective=0、changed=0、gate=false。runner 新增 `--exclude-plan`（canary 协议用，不动 trigger/risk/budget）与 per-response `response_model`/`response_provider` 记录。历史总计 40 次真实调用（20 次 v4-pro 偏差 + 20 次 v4-flash pilot），均未产生有效 patch；无 P/R 可报（not_computed）；formal S2.8 仍 blocked on S2.6 | 新增 exclude-plan/response-model 测试 2 项；全量 1104 passed 24 skipped；canary+pilot manifests |
| 3.4.10 | 2026-07-31 | S2.8D 真实 pilot 模型偏差处理 + fail-closed 模型钉死：20 次真实调用因 .env profile 键优先级生效于 deepseek-v4-pro（未授权模型），已作为 exploratory deviation 原样保留并记录（`outputs/development/s28d_h1_real_pilot_deviation/`）；runner 新增 `--model`（--allow-llm 必需、CLI 覆盖 profile/.env、解析值必须等于 deepseek-v4-flash 否则调用前中止）并打印/记录 resolved model 与来源；preflight v2（同一冻结 20 plans/16 samples，~$0.10 上限）；canary→19 次调用待用户再次授权 | 新增 4 项模型门禁测试；全量 1102 passed 24 skipped；deviation record + preflight v2 |
| 3.4.9 | 2026-07-31 | S2.8C effective fallback 链路验证（development）：每 selected plan 增加 effective-patch audit（b0/proposed/merged hash、requested/proposed/accepted/rejected fields、merge_status、rejection codes、semantic_changed、changed_fields、effective_patch 五条件定义）；新增 `--offline-replay --responses-jsonl` 通道（response 绑定 request_id/sample_id/clause_index/prompt SHA/variant/B0 hash，缺失/重复/错配/额外全 fail closed，与真实 API 同一 parse/validate/merge 路径，manifest 无时间戳可 byte-identical 重放）；no-op 一律拒绝为 no_semantic_change 且不计入 effective；manifest 报告 `h1_non_identity_gate`；新只读对比脚本 `compare_h1_fallback_paths.py`（P/R 仅用户显式 --reference 且拒绝 Layer E/正式 Gold，本次 not_computed）；fixtures 证明合法 modality/actor/action+依赖 patch 改变 prediction（gate=true）、plan-only 保持 B0 identity（gate=false）；B0 v10a plan-only 两臂与 no-op replay 全链路验证，0 API calls；formal S2.8 仍 blocked on S2.6 | 新增 25 项 S2.8C 测试 + 既有 H1/prompt 套件全绿 + 全量检查 |
| 3.4.8 | 2026-07-31 | S2.8B masked-selected-fields repair 合同（development contract verified）：`--prompt-variant full_b0_v4\|masked_selected_v5`（默认 full_b0_v4，v4 prompt SHA 钉住不变）；新 `bpc_hybrid/h1_context.py` 纯函数遮蔽依赖闭包（actors\|actions→actor_action_map、actions→order_relations）与泄漏审计（selected IDs 不得经未遮蔽 relation 泄漏，否则拒绝 request）；新 v5 masked prompt；plan-only 也为 selected plans 记录 context audit；B0 v10a 两臂 plan-only（max_calls=50）：221 triggered / 50 selected plans / 41 samples 完全一致，两臂 predictions 与 B0 semantic hash 全等且 byte-identical，50/50 context audits 通过、0 leak、0 API calls；formal S2.8 仍 blocked on S2.6 | 新增 25 项 S2.8B 测试 + 既有 H1/prompt 套件全绿 + 全量检查 |
| 3.4.7 | 2026-07-31 | G0-TEST-REAL-BACKUP-SNAPSHOT：review-tool 测试改为 session 级纯只读快照守卫（`tree_snapshot`/`snapshot_diff`/`format_diff` + autouse session fixture），允许真实备份目录预先非空，要求整个 session 前后 byte-identical；修复 action-log 恒真断言与"目录必须为空"错误断言；新增 14 项 tmp_path 单元测试（增/删/改/改名/append/missing→created/确定性/不输出内容/symlink 越界 fail closed，平台不支持时显式 skip 并有模拟测试兜底）；全量测试首次 0 failed | 1048 passed, 24 skipped；既有真实文件 SHA 防护未降低 |
| 3.4.6 | 2026-07-31 | S2.8A Gold-blind H1 clause/field 诊断表生成器：抽出共享 B0 绑定模块 `bpc_hybrid/b0_artifact.py`（H1 runner 行为不变，既有测试全绿）；新 `build_h1_trigger_diagnostics.py` 只消费 persisted B0 + manifest + inference-visible telemetry，逐 clause 输出确定性特征行（含 per-feature missing 指标），manifest 绑定输入/输出 SHA-256 并做 coverage accounting；B0 v10a 上 150 samples/256 clauses 离线生成，重复运行 byte-identical，未调 LLM、未读 Gold/Layer E、未改 B0 | 新增 15 项 S2.8A 测试 + 既有 H1/prompt 31 项全绿 + 全量检查 |
| 3.4.5 | 2026-07-31 | G0.8 受控文本哈希可移植性：合同显式声明 `source_manifest.hash_mode=canonical_lf_utf8_text`，S2.1-D gate 只对声明资产做 CRLF→LF 归一化验证，`formal_experiment/.gitattributes` 仅固定该资产为 `text eol=lf`；修复 Windows `core.autocrlf=true` 下 source_manifest 哈希误报，integrity/sun_modality/human-review-input 门禁恢复 true，未放宽任何许可/formal 边界 | 新增受控文本哈希策略测试 18 项 + modality/audit 相关套件全绿 + 全量检查 |
| 3.4.3 | 2026-07-16 | 建立 `formal_experiment/` 首个可追踪 Git checkpoint `bfb0b8a`，并在既有 `paper/README.md` 中固定外部 ChatGPT 的 GitHub 读取、新鲜度回报和论文主张门禁；未新增平行 status/handoff | Event 40、930 项离线测试、提交后机器检查的 `formal_capsule_versioned` pass |
| 3.4.2 | 2026-07-16 | S2.3 离线重建并锁定 `public_marker_lexicon_en_v1`：64 个显式 public seed、逐类版本化资源、来源/生成/payload hash、空 dev 扩展表和独立机器门禁；保持 development-only，未进入 S2.4/S2.5 | S2.3 source snapshot、manifest、fixtures、负测试与全量检查 |
| 3.4.1 | 2026-07-16 | S2.1-D 完成可移植 manifest 与独立 development 数据门禁；S2.1 整体 verified，旧 modality 未摄入 blocker 改为精确 route-relock blocker；许可/formal/Gold/Stage 3 门禁保持关闭 | S2.1-D gate、负测试与全量审计 |
| 3.4.0 | 2026-07-15 | 在不改变 Stage 2→Stage 1→Stage 3 实验顺序的前提下启动论文并行轨道；增加 PW0–PW9、Agent 分阶段派工和主张证据门禁 | 导师要求现在开始写论文；用户要求按 Pipeline 给 Agent 稳步派工 |
| 3.3.0 | 2026-07-15 | 建立 `_retired/` 专属归档、中文目录地图与逐文件目录；活动日志改为中文 `EXPERIMENT_LOG` + 原样保留的机器事件；Agent 入口和自动检查同步固定 | 用户要求彻底整理目录并让日志同时可供人和 Agent 阅读 |
| 3.2.0 | 2026-07-15 | 治理语义改为“实验日志为主、自动完整性检查为辅、正式复核只在里程碑”；真实运行增加结构化日志字段；精确状态测试凭证消除重复全测 | 用户要求判断审计与日志何者适合普通论文实验 |
| 3.1.1 | 2026-07-14 | P0 完成：全量检查通过并记录 Event 27；主线转入 P1/S2.1 | `record_change.py` 的已验证结果 |
| 3.1.0 | 2026-07-14 | 固定各阶段最低 baseline 覆盖；增加前人数据/结果的 C1-C4 比较证据等级，禁止跨数据和跨阶段误比 | 用户要求多 baseline、复用公开数据并澄清第二/三阶段比较 |
| 3.0.0 | 2026-07-14 | 扩展为完整三阶段重建；Stage 2 优先，多 baseline 与复杂数据；Stage 3 后续扩展；建立 WBS、依赖、DoD 与 Agent 协议 | 用户根据导师要求明确指示 |
