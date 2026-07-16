# EStG 德文→英文 翻译协议（v1, **SUPERSEDED for re-translation**）

**日期**：2026-07-12
**状态**：**SUPERSEDED** for new translation runs as of 2026-07-12 17:15
by user decision. The translation already produced
(`estg_selected_150_en_llm_translated.jsonl`) is retained as the **one
candidate English** for each of the 150 records; re-translation is not
authorized in this session. The official EStG text under
`references/datasets/` is used **only** for read-only source-mapping,
not as a translation source.
**授权来源**：`docs/USER_DECISION_LOCK_2026-07-12.md` D5 +
2026-07-12 17:15 user final decision.

---

## 1. 一句话目标

把 EStG 法规文本从德文翻译为英文，**每条记录保留德文原文、英文译文、翻译
provenance、冻结状态**。正式 Gold 的 span 字符 offset 全部基于**冻结的英文
译文**，任何译文变更必须使旧 span 失效并触发重审。

---

## 2. 翻译工具选择

| 候选 | 优点 | 缺点 | 推荐度 |
|---|---|---|---|
| **DeepL Pro** | 法律/正式语体质量高、价格低、术语一致 | 黑盒、API 限速 | ⭐⭐⭐⭐⭐ 主推 |
| GPT-4 / Claude Opus | 长上下文 + 复杂句更好 | 贵、不稳定、policy 风险 | ⭐⭐⭐ 备选 |
| Google Cloud Translation | 便宜、易集成 | 质量中等 | ⭐⭐ 备用 |
| 本地 NLLB / Marian | 隐私好、零成本 | 质量差于商业 | ⭐ 兜底 |

**推荐组合**：DeepL Pro 为主，复杂长句（>50 词/嵌套 3 层以上）转 GPT-4。

---

## 3. 翻译流程

```
输入：EStG 原文（已 OCR 修复、UTF-8、句子已分）
            │
            ▼
┌────────────────────────────────────────────┐
│ 第 1 步：自动分句                            │
│ ─ 工具：自写规则 + spaCy（不依赖 Sun）       │
│ ─ 输出：每条 = 1 个规范化句子                │
│ ─ 记录：split_method + spaCy 版本           │
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│ 第 2 步：初次翻译（DeepL / GPT-4）           │
│ ─ 关键开关：formality = "formal"             │
│ ─ 关键开关：preserve_formatting = true       │
│ ─ 关键开关：tag_handling = "xml"             │
│ ─ 记录：tool / model / version / 调用时间   │
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│ 第 3 步：术语对齐                            │
│ ─ 维护 `resources/glossary.json`             │
│   （德文短语 → 强制英文翻译）                 │
│ ─ 关键术语：shall/may/must not, Anspruch,    │
│   Verpflichtung, Berechtigung, Ausnahme,    │
│   Bedingung, Beschränkung                    │
│ ─ 第 2 步后再做一次"术语替换"以保证一致     │
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│ 第 4 步：质量自检（机器）                    │
│ ─ 检查 1：英文长度 vs 德文长度（异常比例）   │
│ ─ 检查 2：术语词典覆盖率（必须 100%）        │
│ ─ 检查 3：括号/编号/§ 引用是否保留           │
│ ─ 失败：标 `pending_human_review`            │
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│ 第 5 步：用户抽查（人工）                    │
│ ─ 抽样 30% 由用户直接审                      │
│ ─ 重点审：modal、negation、condition、        │
│   exception、actor/action 边界               │
│ ─ 通过：标 `text_review.status=approved`     │
│ ─ 失败：标 `rejected` 并回第 2 步            │
└────────────────┬───────────────────────────┘
                 │
                 ▼
         冻结的英文译文（`text_review.approved_text_en`）
```

---

## 4. 每条记录的 provenance 字段

每条审核包记录至少含：

```json
{
  "source": {
    "source_text_de": "干净的德文原文（OCR 修复后）",
    "candidate_text_en": "第 2 步的初译",
    "translation_provenance": {
      "primary_tool": "deepl",
      "primary_model": "DeepL Pro 2026-06-15",
      "secondary_tool": "gpt-4",
      "secondary_trigger": "length_ratio>2.5 OR clause_depth>=3",
      "glossary_version": "v3",
      "glossary_sha256": "abc123...",
      "deepl_call_id": "uuid-...",
      "deepl_cost_estimate_usd": 0.012,
      "translation_date_utc": "2026-07-12T...",
      "translator_agent_version": "build_translation_v1"
    }
  },
  "text_review": {
    "status": "approved|needs_review|rejected",
    "reviewer": "username",
    "reviewed_at": "ISO 8601",
    "corrected_text_de": "OCR 修复后的德文",
    "approved_text_en": "最终冻结的英文译文",
    "notes": "..."
  }
}
```

**每条 provenance 都进 audit log，文件级 + 记录级双重记录**。

---

## 5. 字符 offset 验证规则

1. **English 译文**是 `text[start:end]` 字符串切片的唯一真值源
2. Python slice 语义：`text[start:end]` 不含 `end` 位置字符
3. `end <= len(text)`，否则 span 无效
4. 任何 `text_review.approved_text_en` 改动 → 旧 span 全部失效 → 触发**全文重审**
5. 验证脚本 `scripts/validate_translation_offsets.py` 必须 pass 才能进入正式审核

---

## 6. 失败回退策略

| 失败模式 | 回退 |
|---|---|
| DeepL 整批 fail | 切到 GPT-4 整批重译，记录成本 |
| 单条 fail | 用户重译 + 记录人审 |
| glossary 与原文冲突 | glossary 优先（法律术语统一） |
| 译文与德文长度差 > 3 倍 | 标 `length_outlier`，强制人审 |
| 同一句多版本译文 | 取最新 `approved_text_en`，旧版本保留在 `_meta.translation_history` |

---

## 7. 与其他线的关系

| 关系 | 决定 |
|---|---|
| B0 实现 | 必须基于冻结的英文译文跑；不污染 |
| 旧 `estg150_review_pack_v1.jsonl` | **不能复用**其 candidate_text_en（开发用，质量不达冻结标准） |
| 用户审核新数据 | 第 5 步必须用户亲自过 |
| H1/D1 prompt | 全部基于冻结英文，**不**给 LLM 德文原文 |

---

## 8. 实施步骤（建议 1-2 周）

| 步骤 | 任务 | 输出 |
|---|---|---|
| 1 | 写 `scripts/translate_estg.py`（DeepL wrapper + glossary） | 翻译脚本 |
| 2 | 写 `resources/glossary.json` 种子（50 个核心术语） | 词典种子 |
| 3 | 在 EStG_raw.txt 上跑第 1-4 步（自动） | `data/development/estg/.../en_translated_v1.jsonl` |
| 4 | 用户抽审 30%（约 50 句） | 部分 `text_review.status=approved` |
| 5 | 全文 150 句冻结 | `data/input/estg_150_frozen_v1.jsonl` |
| 6 | 跑 offset 验证 | 全部 150 句 pass |

---

## 9. 边界声明

- 不声称译文与 Sun 论文原 150 句翻译一致（Sun 翻译流程未公开）
- 不主张本协议比 Sun 更好；只主张**完全可复现**
- 翻译模型版本、API key 不进入 Git（用 `.env`，已在 `.gitignore`）
- 翻译成本按月聚合进 audit log

---

## 10. 待用户确认（RESOLVED — SUPERSEDED）

All open questions in this section are resolved by the 2026-07-12 17:15
user final decision: re-translation is **not** authorized in this
session. The candidate English for the 150 is the existing
`estg_selected_150_en_llm_translated.jsonl`. The user is now authorized
to begin **reviewing and editing** that English (approving, correcting,
or marking `needs_adjudication`) inside
`data/development/human_review/estg_150_canonical_review_v1.json` using
`scripts/estg150_review_tool.py`. Re-translation with new tools is a
future decision, not this session's task.
