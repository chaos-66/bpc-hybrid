# GDPR7 六要素人工裁决工作流指南（V1）

**2026-09-09 当前状态**：用户已在会话中确认74句AI预填稿，当前已确认人工值为
`gdpr7_human_confirmed_v1/confirmed_rule_items.json`，说明见同目录 `人工确认结果.md`。
74/74句已确认；绑定事件为 `gdpr7_prefill_confirmation_20260909.json`。
使用 `python formal_experiment/scripts/import_gdpr7_confirmed_prefill_v1.py --check` 核验。
本文下方介绍的是历史 blank/v1 工作流；旧v1/v2文件原样保留，不用其空决定覆盖已确认内容。
本次尚未发布正式Gold或运行Oracle。

> 面向**人类评审员（reviewer）**的简明操作说明。配套裁决面文件：
> `data/development/human_review/gdpr7_six_element_review_blank_v1.json`
> （schema `gdpr7_six_element_review_surface@1.0.0`，当前状态 `blank_unreviewed`）。
> 本指南只解释“如何裁决”，**不代填任何决定**。

---

## 1. 这份材料是什么

本项目要建立 **9 段 GDPR 条款的句子级六要素 Gold Rule Records（人工裁决）**。
本裁决面是第一步：它把每一条句子和一个 **development-only 的确定性抽取候选
（candidate）** 摆在一起，等人类评审员逐句给出决定。候选**不是 Gold**，也
**永远不会被自动提升为 Gold**。

裁决面覆盖的规则文本来自冻结的 Stage-3 推理包
`data/development/human_review/stage3_gold_inference_v1.json`（sha256
`4182c1f6ba8e28665c6dd14a2573b227e0c6b65c1df0041fcd1ae7dab5cf03c4`，
25 个 matching 项 + 33 个 violation 项，9 条规则文本、每条唯一）。

## 2. 9 条规则文本是什么

GDPR（欧盟《通用数据保护条例》）下列条款（以冻结推理包中的英文条款文本为准，
全部为公开法律文本）：

| 规则 id | 条款 |
|---|---|
| `article6` | 处理的合法性（lawfulness of processing） |
| `article7` | 同意的条件（conditions for consent） |
| `article15` | 数据主体的访问权（right of access） |
| `article16` | 更正权（right to rectification） |
| `article17` | 被遗忘权/删除权（right to erasure） |
| `article20` | 数据可携权（right to data portability） |
| `article22` | 自动化决策（automated individual decision-making） |
| `article33` | 个人数据泄露通知监管机构（notification of a personal data breach） |
| `article34` | 个人数据泄露告知数据主体（communication to the data subject） |

## 3. 为什么需要六要素 Rule Records（同法 Stage 2 ↔ Stage 3 与正式 Oracle）

- 项目三阶段框架中，**Stage 2** 把法规句子解析成结构化 **Rule Record（六要素
  + 原文位置）**；**Stage 3** 用 Rule Record 与流程模型比对，检测违规。
- 现有三方法（`sun_rule_only` / `sun_llm_fallback` / `direct_llm`）的正式 Stage 2
  预测都在 EStG-150（税法句子）上，**没有接任何 GDPR 流程**；而 GDPR 条款上没有
  任何 Stage 2 方法产物。要在 **同法同域（GDPR 条款 → GDPR-7 流程）** 上做
  Stage 2 → Stage 3 的端到端比较，必须先有：句子级 Gold-blind 输入（已有，
  `data/input/gdpr7_stage2_input_v1.json`，74 句）和**人工裁决的六要素 Gold
  Rule Records**——后者目前不存在，是正式 Oracle 与语料级 Stage 2 评价的
  前提（见 `docs/research/RESEARCH_EVIDENCE_REVIEW_2026-09-06.md` §3.5）。
- 裁决面只提供“句子 + 候选”，不携带任何 Gold 决定、expected violation 或
  面板标签，保证评审员看到的是最小裁决界面。

## 4. 句子构成：74 句

9 条规则文本用与 S3.9-EXT 面板规则绑定相同的确定性分句（spaCy
`en_core_web_sm` 句子边界 + 空白折叠 + 跳过空句），共 **74 句**：

| 规则 id | 句子数 | 规则 id | 句子数 |
|---|---|---|---|
| `article6` | 10 | `article20` | 5 |
| `article7` | 8 | `article22` | 6 |
| `article15` | 13 | `article33` | 10 |
| `article16` | 2 | `article34` | 7 |
| `article17` | 13 | **合计** | **74** |

每条句子的 `sample_id` 形如 `gdpr_article33_s001`（第 1 句）、
`gdpr_article15_s002`（第 2 句）……`sentence_idx` 从 0 开始，`char_span` 是
句子在规则文本中的字符区间，`text_sha256` 是句子文本的 sha256。

## 5. 六要素字段的含义（本项目口径）

对每条句子，候选给出最多六个字段。**除 modality 是受控标签外，其余五个字段
（actor/action/condition/constraint/exception）都期望是句子的逐字文本
（verbatim substring）**：值应是 `sentence_text` 中连续出现的原文片段（含相同
大小写与标点），便于之后做 span 回指与 Oracle 一致性校验。

| 字段 | 含义（本项目定义） | 取值期望 |
|---|---|---|
| `modality` | 句子的规范力类别，4 类受控标签：**definition（定义）/ obligation（义务）/ permission（允许）/ prohibition（禁止）** | 受控标签之一；确定性候选只在出现 `shall/must/may` 等标记时给出 obligation/permission/prohibition，对无道义标记的定义/描述句候选为 `null` |
| `actor` | 规范指向的主体（如 the controller / the data subject / the processor） | 句子逐字文本 |
| `action` | 主体必须做 / 可以做 / 被禁止做的主要行为（动词短语） | 句子逐字文本 |
| `condition` | 规范适用/触发的前提条件（in the case of / where / when / if / unless 等引导） | 句子逐字文本 |
| `constraint` | 时间/数量/方式等限制（not later than 72 hours、without undue delay、at least 等） | 句子逐字文本 |
| `exception` | 规范不适用的例外或免责情形（unless / except / shall not be required 等） | 句子逐字文本 |

候选还附带 `constraint_kind` / `exception_kind`（如 `time_limit`、
`unless_clause`）——它们是确定性抽取的**派生标签，不是裁决字段**，评审员不
需要也不应该改它们。

`candidate` 对象内有两个固定标签：

- `"candidate_source": "deterministic_development_extraction_v1"`——候选来自
  确定性开发抽取（`extract_six_element_sentences`），不是任何模型预测；
- `"is_gold": false`——候选永远不是 Gold。

## 6. 如何使用裁决面文件

对每条句子，文件里是固定结构：

```
sample_id / sentence_idx / char_span / text_sha256 / sentence_text
  ├─ candidate   ← 只读，永不修改
  └─ review
       ├─ modality  { decision, edited_value }
       ├─ actor     { decision, edited_value }
       ├─ action    { decision, edited_value }
       ├─ condition { decision, edited_value }
       ├─ constraint{ decision, edited_value }
       ├─ exception { decision, edited_value }
       ├─ review_state
       └─ notes
```

评审员**只做两件事**：

1. 把 `review.<field>.decision` 改为三种值之一：`accepted`（采纳候选值）、
   `edited`（修正）、`rejected`（判该句无此要素）；
2. 当 `decision == "edited"` 时，把修正后的值写入 `review.<field>.edited_value`
   （modality 写受控标签；其余五个字段写句子逐字文本）。

**禁止**：修改 `candidate`（及其 `constraint_kind`/`exception_kind`）、
`sample_id`/`sentence_idx`/`char_span`/`text_sha256`/`sentence_text` 等身份与
证据字段；不要在 `review` 之外新增任何列。

## 7. 哪些字段可以合法缺失

不是每句都有全部六个要素。句子确实没有某个要素时，该要素在最终 Rule Record
中就不存在，这是合法的：

- 候选为 `null` 且句子确实没有该要素 → `decision: "accepted"`（接受“无此要素”）；
- 候选给了非空值但句子实际没有该要素 → `decision: "rejected"`（作废该候选）。

即“缺失”通过 `accepted`（空）或 `rejected` 表达，不需要硬造一个值。

## 8. 禁止事项（三条硬边界）

1. **模型预测 / 合成标签 / 确定性抽取不得自动提升为 Gold。** 候选的
   `candidate_source` 标签记录其来源；任何自动化产物只有经人类逐项裁决后才能
   进入 Gold Rule Records。确定性抽取尤其只是“开发候选”，与冻结面板锁定的
   rule_element 一致不等于它是 Gold。
2. **任何 agent 都不得替用户设定决定。** 评审决定（accepted/edited/rejected
   及 edited_value）只能由人类评审员写入；agent 可以做的是：构建裁决面、
   校验格式、解释候选、导入用户明确提供的决定。
3. 当前裁决面保持 `status: "blank_unreviewed"`、所有 `decision`/`edited_value`
   为 `null`、`review_state` 为 `"unreviewed"`。构建器与验证器都会
   **fail-closed**：任何非空决定都会使校验失败。

## 9. 工作示例（仅供说明，绝不写入裁决面）

以 `article33` 第 1 句为例（`sample_id = gdpr_article33_s001`，
`sentence_idx = 0`，`char_span = [0, 370]`，该句全长 370 字符）。

**原文（仅引用前 189 个字符，“…”表示截断）**：

> In the case of a personal data breach, the controller shall without undue
> delay and, where feasible, not later than 72 hours after having become aware
> of it, notify the personal data breach …

（续文大意：…通知第 55 条所指的监管机构，除非该泄露不太可能对自然人权利与
自由构成风险。）

**候选（`candidate_source = deterministic_development_extraction_v1`,
`is_gold = false`）**：

| 字段 | 候选值 |
|---|---|
| `modality` | `obligation`（"the controller **shall** … notify"） |
| `actor` | `the controller` |
| `action` | `notify the personal data breach` |
| `condition` | `In the case of a personal data breach` |
| `constraint` | `not later than 72 hours`（kind `time_limit`） |
| `exception` | `unless the personal data breach is unlikely to result in a risk to the rights and freedoms of natural persons`（kind `unless_clause`） |

**示例决定（仅示例；illustrative only，未写入也不得写入裁决面 JSON）**：

```json
{
  "modality":   { "decision": "accepted", "edited_value": null },
  "actor":      { "decision": "accepted", "edited_value": null },
  "action":     { "decision": "edited",
                  "edited_value": "notify the personal data breach to the supervisory authority competent in accordance with Article 55" },
  "condition":  { "decision": "accepted", "edited_value": null },
  "constraint": { "decision": "accepted", "edited_value": null },
  "exception":  { "decision": "accepted", "edited_value": null },
  "review_state": "reviewed",
  "notes": "示例：把候选 action 补全为更完整的逐字动词短语（仍为句子原文片段）。"
}
```

上例只用于向评审员演示字段语义与填写方式，**不是**对裁决面的修改。裁决面文件
在交付时保持全空（所有 `decision` / `edited_value` 为 `null`）。

## 10. 配套文件与验证命令（在 `formal_experiment/` 下运行）

- 构建器：`scripts/build_gdpr7_review_surface_v1.py`
  （默认输出上述裁决面；已存在时拒绝覆盖，需 `--overwrite`）
- 验证器：`scripts/validate_gdpr7_review_surface_v1.py --check`
  （检查 9 规则 / 74 句 / sample 顺序与输入包一致 / 逐句文本与哈希一致 /
  所有决定为 null 且 `review_state == "unreviewed"`；通过退出码 0）
- 聚焦测试：`python -m pytest tests/test_gdpr7_review_surface_v1.py -q`

评审完成后，下游冻结/导入工具将只依据 `review.*.decision` 与
`review.*.edited_value` 组装人工裁决的六要素 Rule Records——本裁决面文件自身
永远只作为编辑表面，不由自动化进程改写。
