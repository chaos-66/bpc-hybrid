# EStG 150 新审核包 Schema 设计（草案 v1）

**日期**：2026-07-12
**状态**：draft, awaiting user + mentor approval
**作用**：定义新审核包 `estg_150_review_pack_v2.jsonl` 的完整 schema，配合 B1/B2 协议
**授权来源**：`docs/USER_DECISION_LOCK_2026-07-12.md` D2 + `HUMAN_GOLD_GUIDE.md`

---

## 1. 一句话目标

定义新空白审核包（`estg_150_review_pack_v2.jsonl`）的**完整字段、状态机、验证
规则、冻结流程**，使 B0/H1/D1 三组方法共享同一份冻结 Gold。

---

## 2. 与旧 pack 的关系

旧 pack (`estg150_review_pack_v1.jsonl`) 是 development-only，schema 1.0.0
基本可用，但：
- 数据来源旧 OCR + 旧 LLM 翻译（数据脏）
- 状态字段名 `do_not_auto_score` 是被动防御
- 没有 `_meta` 顶层说明
- 没有 provenance 嵌套字段

新 pack (`estg_150_review_pack_v2.jsonl`) 升级到 schema 2.0.0：
- 数据来源 EStG_raw.txt + DeepL/GPT-4（数据干净）
- 状态机显式
- 加 `_meta` 行（首行）
- 加 provenance 嵌套
- 字符 offset 规则文档化

**严禁**把 v1 的 150 条内容直接搬到 v2。

---

## 3. 顶层结构

```jsonl
{"_type": "meta", "schema_version": "2.0.0", "frozen_at": null, ...}
{"sample_id": "estg_00001", "source": {...}, "text_review": {...}, "clauses": [...], "annotation_review": {...}}
{"sample_id": "estg_00002", ...}
...
{"sample_id": "estg_00150", ...}
```

- 第 1 行：`_type=meta` 顶层说明
- 第 2-151 行：150 条 sample 记录
- 每行 1 个 JSON object（无 trailing comma）

---

## 4. _meta 行字段

```json
{
  "_type": "meta",
  "schema_version": "2.0.0",
  "pack_id": "estg_150_review_pack_v2",
  "created_at_utc": "2026-07-12T...",
  "frozen_at_utc": null,
  "source_protocol": "_retired/docs/2026-07/EStG_150_SAMPLING_PROTOCOL.md",
  "translation_protocol": "_retired/docs/2026-07/DATA_TRANSLATION_PROTOCOL.md",
  "audit_session_id": "estg_150_v2_2026_07_12",
  "promotion_blocked": true,
  "promotion_blocked_until": "user_full_approval_and_route_v2_relock",
  "reviewer_pool": ["user"],
  "expected_record_count": 150,
  "linked_translation_glossary_sha256": "...",
  "linked_lexicon_versions": {
    "condition": "v1",
    "constraint": "v1",
    "actor": "v1",
    "modality": "v1",
    "action": "v1",
    "exception": "v1-dev"
  }
}
```

---

## 5. 每条 sample 字段

```json
{
  "schema_version": "2.0.0",
  "sample_id": "estg_00001",
  "do_not_auto_score": true,

  "source": {
    "source_name": "EStG 1988 (raw from Archive.org)",
    "source_sha256": "185385186533FCDB...",
    "source_section": "§ X Abs. Y Satz Z",
    "source_paragraph_id": "p_1234",
    "ordinal_in_paragraph": 3,
    "source_text_de": "干净的德文原文",
    "candidate_text_en": "DeepL/GPT-4 初译",
    "translation_provenance": {
      "primary_tool": "deepl",
      "primary_model": "DeepL Pro 2026-06-15",
      "secondary_tool": "gpt-4",
      "secondary_trigger": "length_ratio>2.5 OR clause_depth>=3",
      "glossary_version": "v3",
      "glossary_sha256": "abc123...",
      "translation_date_utc": "2026-07-12T...",
      "translator_agent_version": "build_translation_v1"
    },
    "selection_policy": "New sample per EStG_150_SAMPLING_PROTOCOL. NOT Sun et al.'s original sample.",
    "stratification_target_modality": "obligation"
  },

  "text_review": {
    "status": "needs_review|approved|rejected",
    "reviewer": null|"username",
    "reviewed_at": null|"ISO 8601",
    "corrected_text_de": null|"OCR 修复后德文",
    "approved_text_en": null|"冻结英文",
    "notes": null|"..."
  },

  "clauses": [],
  "annotation_review": {
    "status": "needs_review|reviewed|adjudicated|rejected",
    "reviewer": null|"username",
    "reviewed_at": null|"ISO 8601",
    "confidence": null|1-5,
    "no_normative_clause_reason": null|"...",
    "notes": null|"..."
  }
}
```

---

## 6. clause 内字段（每个 sample 可拆 0-N 个 clause）

```json
{
  "clause_id": "estg_00001_c01",
  "clause_span": {"value": "...", "start": 0, "end": 51},

  "modality": {
    "label": "obligation|prohibition|permission|definition",
    "evidence": [{"value": "shall", "start": 13, "end": 18}]
  },

  "actors": [
    {"id": "a01", "value": "The taxpayer", "start": 0, "end": 12}
  ],
  "actions": [
    {"id": "p01", "value": "file the return", "start": 19, "end": 34}
  ],
  "conditions": [
    {"id": "c01", "value": "within 30 days", "start": 35, "end": 49}
  ],
  "constraints": [],
  "exceptions": [],

  "actor_action_map": [
    {"actor_id": "a01", "action_id": "p01"}
  ],
  "order_relations": [
    {
      "before_action_id": "p01",
      "after_action_id": "p02",
      "evidence": [{"value": "thereafter", "start": 50, "end": 60}]
    }
  ]
}
```

---

## 7. 字符 offset 规则

1. **唯一真值源**：`text_review.approved_text_en` 字符串
2. **Python slice 语义**：`text[start:end]` 不含 `end` 位置字符
3. **范围**：`0 <= start < end <= len(text)`
4. **验证**：`text[start:end] == value`（必须完全一致）
5. **禁止**：负数 / 越界 / 浮点 / 修改 text 但不改 offset
6. **失败处理**：验证失败 → 标 `invalid_span` + 阻塞 freeze

**验证脚本**：`scripts/validate_estg_human_review.py`（已存在，扩展 schema 2.0 支持）

---

## 8. 多分句规则

- 一个独立 modality/action 单元 = 一个 clause
- 并列动作若共享同一 modality 但**分别对应 BPMN 行为** → 拆多个 clause
- 纯修饰、例示、非规范性说明 → 不单独成 clause
- 一句无规范性子句 → `clauses: []` + `no_normative_clause_reason`

**示例**（来自 `HUMAN_GOLD_GUIDE.md`，保留为参考）：
```
"The taxpayer shall file the return within 30 days."
→ 1 个 clause（1 个 modality + 1 个 actor + 1 个 action + 1 个 constraint）
```

---

## 9. 状态机

```
            ┌────────────────────┐
            │  needs_review      │  ← 初始
            └────────┬───────────┘
                     │
       ┌─────────────┼──────────────┐
       │             │              │
       ▼             ▼              ▼
   approved      reviewed       rejected
   (text)        (annotation)   (任何阶段)
       │             │              │
       └──────┬──────┘              │
              ▼                     │
        adjudicated                  │
        (二次裁决)                    │
              │                     │
              ▼                     │
            FROZEN                  │
       (进入正式 Gold)               │
                                    ▼
                                不进 Gold
```

**严格规则**：
- 只有 `reviewed` / `adjudicated` 可进入正式 Gold
- 任何状态转换必须由**人**完成（Agent 只能校验/提醒）
- `rejected` 后该 sample 进入"重抽队列"（不在原 pack 修改）

---

## 10. 验证流程

```powershell
# 单条编辑后
python scripts/validate_estg_human_review.py data/development/human_review/estg_150_review_pack_v2.jsonl

# 全部 150 条审完后
python scripts/validate_estg_human_review.py data/development/human_review/estg_150_review_pack_v2.jsonl --require-freeze-ready
python scripts/audit_project.py --with-tests
```

只有两个命令都通过 + 用户明确说"freeze" → 才进入 `data/gold/estg_150_frozen_v2.jsonl`。

---

## 11. 冻结流程

```
draft (150 条 needs_review)
    ↓ 用户审 + 改
user_completed (150 条 reviewed 或 adjudicated)
    ↓ validate --require-freeze-ready + audit --with-tests
freeze_candidate (全部通过)
    ↓ 用户明确说"freeze"
frozen (写入 data/gold/estg_150_frozen_v2.jsonl)
    ↓ audit event
locked_for_experiment
```

**任何冻结后修改 = 走新 pack 版本（v3）**，不修改 v2。

---

## 12. 字段约束表

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| sample_id | string | ✓ | `^estg_\d{5}$` |
| source.source_text_de | string | ✓ | 非空 |
| source.candidate_text_en | string | ✓ | 非空 |
| text_review.status | enum | ✓ | needs_review/approved/rejected |
| text_review.approved_text_en | string | 条件 | status=approved 时必填 |
| clauses | array | ✓ | 元素数 >= 0 |
| annotation_review.status | enum | ✓ | needs_review/reviewed/adjudicated/rejected |
| annotation_review.confidence | int | 条件 | status=reviewed 时必填，1-5 |

---

## 13. 与旧 schema 的兼容

- 旧 v1 记录字段名 100% 保留（避免破坏 dev 工具）
- 新 v2 加 `_meta`、provenance、stratification 等可选字段
- v1 文件不被读取为正式审核（路径白名单）

---

## 14. 实施步骤（建议 1 周）

| 步骤 | 任务 | 输出 |
|---|---|---|
| 1 | 写 `configs/schemas/estg_150_review_pack_v2.schema.json` | JSON Schema |
| 2 | 扩展 `validate_estg_human_review.py` 支持 2.0.0 | 升级版 validator |
| 3 | 写 `scripts/build_estg_150_v2_pack.py`（基于 B1/B2 输出） | 空白 pack 生成器 |
| 4 | 生成新空白 pack | `data/development/human_review/estg_150_review_pack_v2.jsonl` |
| 5 | 用户开始审核 | reviewed 数逐日增加 |
| 6 | 150/150 reviewed → freeze | `data/gold/estg_150_frozen_v2.jsonl` |

---

## 15. 边界声明

- 不从旧 v1 pack 复制任何内容到 v2
- Agent **不**自动批准任何状态转换
- 字段扩展**不**破坏 v1 文件
- 冻结后**不**修改

---

## 16. 待用户确认

- [ ] schema 2.0.0 字段集是否完整？
- [ ] 状态机是否清晰？
- [ ] 字符 offset 规则是否同意？
- [ ] 冻结流程是否合理？
- [ ] 字段约束是否过严 / 过松？
- [ ] 是否需要额外字段（re-annotation 记录、adjudication 记录）？

**收到用户确认后开始第 1-4 步实施**。
