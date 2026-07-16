# 当前实验总览与 Agent 交接（2026-07-12）

本文档是当前最简洁的交接入口。它记录已经确认的事实、用户决定、研究边界和下一步，
避免后续 Agent 把“代码提供者”“代码内容”和“Sun 论文完整方法”混为一谈。

## 1. 研究目标

只修改 Sun et al. (2024) 的 Stage 2 法规解析，比较三组：

- B0：按最终论文独立重建的完整非 LLM Sun Stage 2；
- H1：同一个 B0 + 预注册 trigger 的 LLM fallback；
- D1：纯 LLM 替换整个 Stage 2。

三组使用相同输入、人工 Gold、schema、evaluator 和完全不变的 Stage 3。研究不仅
比较 Stage 2 六要素 P/R/F1，还要验证改进是否传递到 Stage 3 的 AP/MAP 与
missing-action、incorrect-actor、out-of-order P/R/F1。

## 2. 导师包身份：来源与内容必须分开

### 已确认事实

- 导师明确说明 `references/合规性检查模型代码/` 来自 Sun 论文作者，因此其
  **提供来源**应记录为 Sun-author-provided package；
- 该包中的 `model_check/` 与本地 Winter et al. (2020) prototype 比较后，112 个
  非缓存文件的相对路径和 SHA-256 全部相同，差异数为 0；
- 导师包额外文件是缓存/工程文件及独立的 `Logs_for_Neo4J` 材料；
- `model_check` 使用 spaCy、signal words、sequence markers、clause、`gamma`/
  `delta`、obligation/resource/sequence-order cost；
- 包中没有 BERT-TextCNN、CoreNLP、Tregex/Tsurgeon、Sun 六要素完整实现、完整
  marker 或训练模型。

### 正确解释

该包可以由 Sun 作者提供，同时其 `model_check` 内容仍是 Winter 原型的直接副本。
最合理且不越过证据的解释是：作者提供了论文使用/继承的合规检查基础资产，但没有
提供 Sun 论文新增的完整 Stage 2。无法仅凭文件内容判断作者当时的打包意图，也不应
指控作者；只报告可核验事实。

允许的称呼：

> Sun-author-provided compliance-checking package whose `model_check`
> subtree is byte-identical to the Winter 2020 prototype.

禁止的称呼：

- Sun 完整源码；
- Sun Stage 2 原始实现；
- 导师拿到的是错误代码；
- Winter 与 Sun 整体方法完全相同。

## 3. Sun 相比 Winter 真正改了什么

| 环节 | Winter | Sun | 结论 |
|---|---|---|---|
| 法规句子筛选 | signal words/关键词 | BERT-TextCNN 四类 modality | Sun 的重要新增 |
| 法规结构 | clause 级 spaCy 解析 | 六要素 span + rule record | Sun 的核心新增 |
| 句法工具 | spaCy dependency/clause | CoreNLP + Tregex/Tsurgeon + marker | 明显不同 |
| 检查内容 | obligation/resource/order cost | missing action/incorrect actor/out-of-order | 概念基本对应 |
| BPMN/相似度/阈值 | 已有 matching/checking 骨架 | 继承并接收更细 rule record | Stage 3 相近，输入更精细 |

因此，Sun 整体方法不等于 Winter；但 Sun 的主要创新确实集中在 Stage 2，Stage 3
大量继承 Winter 的思想和资产。这正好支持本研究“只修改 Stage 2、冻结 Stage 3”。

## 4. 用户已锁定的路线

1. 不等待 Sun 原 marker，使用 Sleimi、LexNLP、Wiktionary/Wiktextract 等公开来源
   重建，并记录来源、版本、生成规则和哈希；
2. 用户本人负责六要素 Gold 的最终人工判断；Agent 只能准备候选和审核工具，不能
   自动批准；
3. 不等待 Sun 完整源码，根据论文独立重写，数据可以不同但方法必须一致；
4. BERT-TextCNN 按 Sun 结构重新训练，不追求作者原 checkpoint；
5. 德文 EStG 通过固定、可审核的流程翻译为英文；保存德文原文和翻译 provenance，
   英文译文冻结后再标 span；
6. ~~暂不写实现代码；当前阶段先完成路线、数据、审核和 Stage 3 评价设计。~~
   **已被 §12 当面解锁决定（2026-07-12 14:25）覆盖**：授权立刻开始 B0
   paper-faithful 重建实现代码；真实 LLM/自动 Gold/正式 data 写入仍需单独
   授权（见 §12）。实现 B0 时也必须遵守 §11 的安全与 claim 边界。

完整约束见 `USER_DECISION_LOCK_2026-07-12.md`（含 14:25 解锁条目）。

## 5. Barrientos 的准确角色

Barrientos/RC4PC 不直接提取 Sun 六要素。它输出 precondition、norms、modality、
action、temporal validity 及 control-flow/data/resource/time patterns。它只用于借鉴：

- strict JSON schema；
- controlled vocabulary；
- 原文 evidence span；
- deterministic normalization；
- temperature 0 与多次运行稳定性；
- schema validation 和错误记录。

Sun exception 没有 Barrientos 一等对应字段，必须单独保留。不得写“Barrientos 已
提供 Sun 六要素抽取方法”。

## 6. Marker 与数据现状

- condition/constraint：LexNLP 有公开 trigger，可直接形成可复现种子；
- actor：可按 Sleimi 方法从固定 Wiktionary dump 自动生成；
- modality：论文种子和公开 deontic 数据可辅助；
- exception：仍最薄弱，只能由公开种子和 development-only 审核扩展；
- 原 Sun 150 IDs、443 phrase spans、完整 marker 仍未取得，但已不再是继续实验的
  前置条件；
- **正式 benchmark 已锁定为唯一 EStG-150**：见 §16（2026-07-12 17:15
  用户决定）。membership = 现有 `estg_selected_150_de.jsonl` 的 150 个
  legacy `record_id`；用户审核后作为 independently reconstructed
  EStG-150 benchmark 使用，不重新抽样、不并行 old 150 / new 150。
- 旧 `estg150_review_pack_v1.jsonl` 现已明确为 **retired as editing
  surface**（保留为 provenance），活动编辑面是
  `data/development/human_review/estg_150_canonical_review_v1.json`。

## 7. Stage 3 比较规则

Sun 作者稿在 violation checking 中与 Winter 比较：Winter P/R/F1 为
0.58/0.89/0.70，Sun 为 0.77/0.83/0.80；matching 部分报告 AP/MAP，主要用于
阈值评价。

本研究最低必做是 B0/H1/D1 进入同一个冻结 Stage 3。数据不同，因此不直接用本研究
绝对值与 Sun Table 12 争胜；主结论是 H1/D1 相对 B0 的 downstream 增量。

Winter 可作为第四个可选增强 baseline：若使用原完整程序，它是 external baseline；
若只将 Winter-style Stage 2 接到统一 Stage 3，必须明确称 controlled baseline。
Winter 不是证明本研究 LLM 贡献的最低要求。

## 8. 当前已有资产

- Sun 最终版元数据和官方参考文献表；本地全文是较早作者稿；
- Sun 官方 Archive.org `Decision_Logic_data.zip`，含 EStG raw/CSV/HTML；
- Sun 官方 `input 2.zip`，57 个有效 Stage 3 输入；
- Sun-author-provided package，其 `model_check` 是 Winter 直接副本；
- Winter/Agostinelli GDPR BPMN 和法规输入；
- Barrientos prompt、schema、expert material；
- 已完成 Sun 44 条直接引用和关键二阶资源审计。

## 9. 当前未完成项

1. ~~官方 EStG 数据尚未正式引入活动数据并完成 schema/许可/split 审计~~ —
   **EStG-150 v1 已建立**，详见 §16；唯一审核文件 +
   prepared/membership hash + schema + 验证器均已就位；
2. ~~德文到英文的正式翻译协议、模型/工具、质量审核和冻结规则尚未最终
   落地~~ — **已取消重新翻译**（§16），候选英文固定使用现有
   `estg_selected_150_en_llm_translated.jsonl`，待人工审核时确认
   approved_text_en；
3. ~~新的 150 句抽样策略与空白人工审核包尚未锁定~~ — **已取消重新抽样**
   （§16），membership 由 legacy 150 决定，不再切 old 150 / new 150；
4. public-source marker lexicon 尚未生成和冻结；
5. 最终 B0、H1、D1 尚未实现；
6. Stage 3 使用四个还是七个 GDPR BPMN、threshold 和 violation Gold 尚未锁定；
7. 真实翻译/LLM/API 未授权、未运行。

## 10. 下一位 Agent 的工作顺序

1. 先读本文件、`AGENTS.md`、`ROUTE_LOCK.md`、
   `USER_DECISION_LOCK_2026-07-12.md`、**`docs/ESTG150_DATA_MAP.md`**、
   `docs/STATUS_SNAPSHOT_2026-07-12.md`、§16；
2. **不要**重新抽样、**不要**重新翻译（§16）；候选英文固定使用
   `estg_selected_150_en_llm_translated.jsonl`；审核活动只发生
   在 `data/development/human_review/estg_150_canonical_review_v1.json`；
3. 明确 Stage 3 四/七 BPMN 路线、threshold 和 Gold 需求；
4. §16 数据协议与路线 v2 重锁经用户确认并通过门禁后，才开始完整 B0 实现；
5. B0 稳定后才预注册 H1 trigger、D1 prompt 和真实调用预算。

## 11. 安全与 claim 边界

- 唯一活动目录是 `formal_experiment/`；`references/` 和 `archive/` 只读；
- 不自动产生/批准 Gold；
- 不运行真实翻译或 LLM/API，除非用户再次明确授权并设置预算；
- 不把当前 heuristic runner 当正式 Sun baseline；
- 允许称 `paper-faithful independent reconstruction`；
- 禁止称 Sun original、exact reproduction 或导师包是 Sun 完整源码。

机器状态以 `python formal_experiment/scripts/audit_project.py` 为准；当前
**4 门禁（2026-07-13 Event 22 拆分）**：
- `human_review_input_ready = true`（输入已就绪；用户可开始人工审核
  Layer E；不是 Sun 原始 150，不是 exact reproduction；
  membership_payload_sha256=8573e105...0d7）
- `human_review_freeze_ready = false`（150/150 尚未全部裁决）
- `formal_gold_publication_ready = false`（route v2 仍 reopened；
  official modality 数据 / Stage 3 / freeze_policy 尚未重新锁定）
- `final_experiment_ready = false`（同上 + 三方法 + 冻结 input/gold）
- `integrity_pass = true`

---

## 16. 2026-07-12 17:15 用户决定：唯一 EStG-150 单一数据集

用户决定：

- 项目只有一套需要使用的 150 条 EStG 法规记录；
- 唯一 membership = 现有 `estg_selected_150_de.jsonl` 的 150 个 legacy
  `record_id`；
- 英文翻译、旧 Gold draft、旧 review pack 都只是这同一套 150 的不同
  表示或旧处理版本，**不是不同数据集**；
- 禁止重新抽样、替换 sample membership、产生“old 150/new 150”并行
  路线；
- 这 150 条经过用户逐条审核后，将作为本研究自己重建的固定 benchmark
  使用，称为 **independently reconstructed EStG-150 benchmark**；
  不是 Sun 论文原始且未公开的 150 条；
- “冻结”只表示实验期间所有方法使用同一个已审核版本和 hash；以后发
  现错误可以建立 v2，**不能静默修改 v1**。

本会话交付的 EStG-150 v1 资产：

| 文件 | 类型 | 用途 |
|---|---|---|
| `docs/ESTG150_DATA_MAP.md` | doc | 唯一 150 的数据地图 + ID 映射证明 + hash |
| `data/development/estg/estg_150_membership_hashes.json` | data | membership_payload_sha256 + 150 per-record raw_de sha256 |
| `data/development/estg/estg_150_prepared_v1.jsonl` | data | 低风险清洗后的 prepared view (raw_de/cleaned_de/candidate_en 并排) |
| `data/development/human_review/estg_150_canonical_review_v1.json` | data | **唯一人工编辑源**：150 records，初始全 `needs_review`，clauses 空，approved_en 空 |
| `configs/schemas/estg_150_canonical_review.schema.json` | schema | 严格 JSON Schema + additionalProperties:false |
| `scripts/validate_canonical_review.py` | tool | 三门 gate: format_valid / review_ready / freeze_ready |
| `scripts/estg150_review_tool.py` | tool | 离线 stdlib 审核 UI（启动命令：`python scripts/estg150_review_tool.py`） |
| `scripts/clean_estg150_german.py` | tool | 低风险清洗（已跑：n_text_changed=0） |
| `scripts/build_canonical_review.py` | tool | 一次性 build canonical review from prepared |
| `scripts/compute_estg_membership_hashes.py` | tool | 一次性计算 membership payload sha256 |

被显式标记为 **SUPERSEDED** 的旧文档（保留为 provenance，不要照做）：

- `docs/EStG_150_SAMPLING_PROTOCOL.md` — 重新抽样计划 cancelled。
- `docs/DATA_TRANSLATION_PROTOCOL.md` — 重新翻译计划未授权；候选英文
  用现有 `estg_selected_150_en_llm_translated.jsonl`。

被显式标记为 **retired as editing surface**（保留为 provenance，不删
除，不继续作为正式入口）：

- `data/development/human_review/estg150_review_pack_v1.jsonl`
- `data/development/human_review/estg150_review_pack_user_audit_v1.jsonl`
- `data/development/human_review/estg150_review_pack_user_audit_v1.json`

旧三个自动 Gold 保留为 development provenance，不删除，不作为正确答
案，不预填进 canonical review：

- `data/development/estg/estg_gold_150_llm_draft.jsonl`
- `data/development/estg/estg_gold_150_v1_backup.jsonl`
- `data/development/estg/estg_gold_150_v2_distribution_targeted.jsonl`

---

## 12. 2026-07-12 14:25 用户当面解锁 B0 实施代码

用户当面向 AI 助手授权：立刻开始 B0 paper-faithful 重建实现代码，同时由用户
开始审核旧 `estg150_review_pack_v1.jsonl`（选项 ①，以带 override 标记的副本形式）。
AI 助手按用户要求执行了：

- 更新 `docs/USER_DECISION_LOCK_2026-07-12.md` §5（B0 已授权；真实 LLM/自动 Gold/
  正式 data 写入仍单独授权；旧 pack 与新 pack 正式审核仍 paused）
- 跑 `audit_project.py --with-tests`：integrity_pass=true，513 passed, 22 skipped
- 跑 `scripts/record_change.py`：记入 `docs/AUDIT_LOG.md` + `docs/AUDIT_EVENTS.jsonl`

**本会话产生的 6 个新交付物**（`audit_event_id` 9 与 10 已记录）：

| 文件 | 类型 | 状态 | 用途 |
|---|---|---|---|
| `data/development/human_review/estg150_review_pack_user_audit_v1.jsonl` | data | **SUPERSEDED** by §16；保留为 provenance | 选项① override 副本；结果不进入正式 Gold |
| `docs/B0_RECONSTRUCTION_DESIGN.md` | design draft | awaiting user + mentor | B0 paper-faithful 重建的方法级设计（13 章 + 6 周排期） |
| `docs/DATA_TRANSLATION_PROTOCOL.md` | design draft | **SUPERSEDED** by §16；保留为 provenance，不作为正式入口 | 德英翻译协议（DeepL+GPT-4 双源 + 5 步 + provenance） |
| `docs/EStG_150_SAMPLING_PROTOCOL.md` | design draft | **SUPERSEDED** by §16；保留为 provenance，不作为正式入口 | 150 句新抽样协议（Sun 4 标准 + 分层） |
| `docs/HUMAN_GOLD_REVIEW_PACK_SCHEMA_v2.md` | design draft | awaiting user + mentor | 新审核包 schema v2（_meta 行 + 状态机 + 冻结流程） |
| `scripts/build_user_override_review_pack.py` | tool | ready | 重新生成 override 副本的可重跑脚本 |

**所有交付物都是"不污染数据"的纯设计/方案/工具**：
- 未触碰原 `estg150_review_pack_v1.jsonl`
- 未写入 `data/{input,gold,predictions,results}/`
- 未调用真实 LLM/翻译/API
- 未修改 `references/` 或 `archive/`

---

## 13. 2026-07-12 14:55 状态快照写入

为让任何未来 Agent 30 秒内能完整接手项目，本会话追加了：

- 更新本文件 §12（见上）
- 新建 `docs/STATUS_SNAPSHOT_2026-07-12.md`（人类可读一页状态 + 嵌入 JSON 块）
- 机器可读快照同步写入 `docs/AUDIT_EVENTS.jsonl`（event_id=10）

---

## 14. 下一位 Agent 第一天（30 秒）必读

1. **本文件** `docs/CURRENT_HANDOFF_2026-07-12.md`（你现在读的）
2. `docs/STATUS_SNAPSHOT_2026-07-12.md`（一页全状态）
3. `docs/USER_DECISION_LOCK_2026-07-12.md`（用户锁定的决定 + 14:25 更新说明）
4. `docs/ROUTE_LOCK.md`（路线 v2 状态）
5. `python scripts/audit_project.py --with-tests`（机器状态确认）

然后**按需**读：
- `docs/B0_RECONSTRUCTION_DESIGN.md`（如需动 B0 代码）
- `docs/DATA_TRANSLATION_PROTOCOL.md`（**已 SUPERSEDED by §16，仅作 provenance**，不要再依其做新翻译）
- `docs/EStG_150_SAMPLING_PROTOCOL.md`（**已 SUPERSEDED by §16，仅作 provenance**，不要再依其重新抽样）
- `docs/HUMAN_GOLD_REVIEW_PACK_SCHEMA_v2.md`（如需动审核包）
- `docs/AI_CHANGE_PROTOCOL.md`（任何代码改动前）

---

## 15. 当前进度速查

| 项 | 状态 |
|---|---|
| 4 个设计文档 | ✅ 已交付，待你 + 导师审（其中 EStG_150_SAMPLING_PROTOCOL 与 DATA_TRANSLATION_PROTOCOL 已被 §16 替换为 SUPERSEDED） |
| Override 副本（150+1 行） | ✅ 已生成，**仅供熟悉，不进 Gold**（§16） |
| B0 实施代码 | 🟡 §16 路线 v2 重锁 + 文档批准后开始 |
| 真实 LLM/翻译/正式 Gold | ⛔ 仍未授权 |
| 旧 pack 正式审核 | ⛔ 仍未授权（旧 pack 已 retired as editing surface，见 §16） |
| **EStG-150 v1 单一数据集交付**（§16） | ✅ membership + prepared + 唯一 canonical review + schema + validator + 5 工具脚本 + 2 测试；**用户审核尚未开始（150/150 needs_review）** |
| 新 pack 生成 | ⛔ 已取消（§16 决定不重新抽样、不并行 pack） |
| Stage 3 BPMN/threshold/Gold 冻结 | ⛔ 等 B0 稳定后开始 |
| H1/D1 预注册 | ⛔ 等 B0 稳定后开始 |

---

## 17. 2026-07-12 21:30 v2 工作流：5 层 LLM-assisted 人工修正

### 用户最终需求（明确禁止误解）

1. 保留唯一 EStG-150 membership，不重新抽样（沿用 §16）。
2. 旧 LLM 候选作为**只读 LLM 候选层**；不直接当 Gold。
3. 用户**只编辑**复制出来的人工修正文件；复制不等于批准。
4. 中文翻译 + 英文回译只辅助用户理解，**不得**进入 span offset、Gold、evaluator。
5. 最终 Gold 是 **LLM-assisted, human-adjudicated Gold**；论文不得称"完全从零人工标注"。

### 5 层数据模型

| 层 | 文件 | 角色 | 可写？ |
|---|---|---|---|
| A. 德文原文 | `data/development/estg/estg_selected_150_de.jsonl` | 原始 150 | 永久只读 |
| B. 英文翻译候选 | `data/development/human_review/estg_150_translation_en_v1.jsonl` | LLM 翻译 + provenance | 永久只读 |
| C. LLM 六要素候选 | `data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl` | 从旧 `estg_gold_150_llm_draft.jsonl` 重建 | 永久只读 |
| D. 中文核对辅助 | `data/development/human_review/estg_150_review_aids_zh_v1.jsonl` | 中文 + 回译（目前全 null） | 永久只读 |
| **E. 人工修正** | `data/development/human_review/estg_150_human_correction_v1.json` | 唯一可编辑文件 | ✅ |

旧 `estg_150_canonical_review_v1.json` **不删**，标记为 retired workflow draft，保留为 provenance。

### 本任务交付物

| 文件 | 类型 | 用途 |
|---|---|---|
| `data/development/human_review/estg_150_translation_en_v1.jsonl` | data | Layer B（immutable） |
| `data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl` | data | Layer C（immutable） |
| `data/development/human_review/estg_150_review_aids_zh_v1.jsonl` | data | Layer D（immutable，全 null） |
| `data/development/human_review/estg_150_human_correction_v1.json` | data | **Layer E（唯一可编辑）** |
| `data/development/human_review/ESTG150_REVIEW_WORKFLOW_V1.md` | doc | 工作流说明 |
| `scripts/build_estg150_review_layers.py` | tool | 5 层生成器 |
| `scripts/validate_human_correction.py` | tool | Layer E 校验 |
| `scripts/estg150_review_tool.py` (rewrite) | tool | 中文 UI + 两标签页 + 4 缺陷修复 |
| `tests/test_estg_150_review_tool.py` (rewrite) | test | 24 个测试（17 流程 + 6 防污染 + 1 smoke） |
| `docs/HUMAN_GOLD_GUIDE.md` (rewrite) | doc | v2 审核指南 |
| `docs/ROUTE_LOCK.md` (rewrite) | doc | 路线锁 + 数据集单源 |
| `formal_experiment/src/formal_experiment/audit.py` (patch) | src | 加 D1 根目录脚本 blocker + 改写 human review 文案 |
| `formal_experiment/src/formal_experiment/paths.py` (patch) | src | 加 HUMAN_CORRECTION_FILE 常量 |
| `formal_experiment/src/formal_experiment/status.py` (patch) | src | 加 human_correction_v2 summary |
| `prompts/sun_compat/dry_run_zh_gloss.md` (new) | prompt | Layer D 未来真实 LLM 的离线 prompt（**dry-run only**） |
| `prompts/sun_compat/dry_run_six_element.md` (new) | prompt | Layer C 未来真实 LLM 的离线 prompt |
| `prompts/sun_compat/dry_run_back_translation.md` (new) | prompt | Layer D 未来回译的离线 prompt |
| `scripts/dry_run_llm_estimate.py` (new) | tool | 离线估算调用数 / token / 费用；不调真实 API |
| `docs/LLM_BUDGET_PROPOSAL_2026-07-12.md` (new) | doc | 真实 LLM 调用预算 + 授权命令 |

### 已修复的工具缺陷（14 项）

1. 德文 / 英文分别独立 `text_review` 决策，不共用
2. 原 `candidate_text_en` 不可被工具覆盖
3. 新增 clause 时 modality 不默认 obligation（4-way combobox 强制）
4. 强制 modality 选择器（4 类）
5. span ID 在 clause 内**跨字段**唯一（不是 `len(actors)+len(actions)+1`）
6. condition / constraint / exception 连续添加也不重复
7. span 必须落在 clause_span 内（validator 拦截）
8. actor_action_map / order_relations 可编辑（JSON 文本框）
9. 每次保存自动跑 validator
10. validator 失败可保存草稿，但禁止标 reviewed / adjudicated
11. reviewed / adjudicated 前必须确认 translation + 6 fields 都已决策 + validator 通过
12. 关闭窗口前未保存修改提醒
13. 撤销最近一次操作（50 步 stack）
14. 每次保存前 backup 到 `outputs/development/human_review/review_backups/`

### 不可触碰（按你之前要求）

- event 17 **不修改、不删除**，仅在本事件中说明其 changed_paths 覆盖问题
- D1 根目录脚本（`build_d1_prompt.py` / `build_few_shot.py` / `verify_d1_few_shot.py`）
  仅作为单独 blocker 记入 audit，**不顺手处理**
- references/ 和 archive/ 完全未触碰
- 真实 LLM/API **未调用**
- `.env` **未读取**
- 旧 `estg_150_canonical_review_v1.json` SHA-256 完全不变

### 当前 layer E 状态（audit 真实值）

- records: 150
- approved_text_en: 0/150
- translation unreviewed: 150/150
- six-element unreviewed: 900/150（6 字段 × 150 条）
- review_state: needs_review=150
- format_valid: true
- review_ready: false
- freeze_ready: false

### 启动命令

```powershell
# 重新生成 5 层（layer A 永远不动；layer B/C/D/E 重建）
python formal_experiment/scripts/build_estg150_review_layers.py

# 启动人工修正工具
python formal_experiment/scripts/estg150_review_tool.py

# 校验
python formal_experiment/scripts/validate_human_correction.py

# 全测试
python -m pytest formal_experiment/tests/

# 审计
python formal_experiment/scripts/audit_project.py --with-tests
```

### 真实 LLM 调用：未执行，需要单独授权

详见 `docs/LLM_BUDGET_PROPOSAL_2026-07-12.md`：默认建议使用一个**不参与 B0/H1/D1 最终比较**的独立 annotation model；如果未来使用 D1 同一模型，必须在论文披露 + 盲审样本 + 报告锚定偏差。
