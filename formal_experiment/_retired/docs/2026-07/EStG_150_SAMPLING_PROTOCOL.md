# EStG 150 句抽样协议（v1, **SUPERSEDED — re-sampling cancelled**）

**日期**：2026-07-12
**状态**：**SUPERSEDED** as of 2026-07-12 17:15 by user decision.
The re-sampling plan in this document is **cancelled**.
The single EStG-150 benchmark is now the
`estg_selected_150_de.jsonl` membership, treated as one fixed
independently reconstructed benchmark — see `docs/ESTG150_DATA_MAP.md`.
This document is retained for provenance only; **do not** act on its
old sections.
**授权来源**：`docs/USER_DECISION_LOCK_2026-07-12.md` + `ROUTE_LOCK.md` +
2026-07-12 17:15 user final decision.

---

## 1. 一句话目标（SUPERSEDED — kept for provenance only）

The old plan was: "按 Sun et al. (2024) 论文原 4 个标准从 EStG 法规文本中
**重新抽样** 150 句".

**This plan is cancelled.** The single EStG-150 benchmark in this
project is **not** a fresh 150. It is the existing
`estg_selected_150_de.jsonl` 150 legacy record_ids, taken once and
treated as a fixed membership. New sampling is forbidden, replacing
sample membership is forbidden, producing a parallel "old 150 / new 150"
split is forbidden. See `docs/ESTG150_DATA_MAP.md` for the data map
and §6 of this document for the only allowed use of the local official
EStG text.

The remainder of this document (sections 2-7) is preserved verbatim as
historical provenance. It must not be used as a plan.

---

## 2. Sun 论文原 4 标准

| 标准 | Sun 论文描述 | 本研究实现 |
|---|---|---|
| **complete** | 句子结构完整（主谓宾） | 自写完整度检测器（POS + dep） |
| **sequential** | 与前后句逻辑连贯 | 仅抽 paragraph 边界内的句（paragraph-internal） |
| **contains a legal act** | 包含法律行为（shall/may/forbid 等） | marker 候选至少 1 个命中 |
| **longer than 20 words** | > 20 词 | 简单长度过滤 |

**Sun 原文出处**（待终版核对）：Section 5.2，参考 `references/papers/extracted/sun_2024_full_text.txt`。

---

## 3. 数据源

| 候选 | 来源 | 状态 | 推荐 |
|---|---|---|---|
| **EStG_raw.txt** | Archive.org `Decision_Logic_data.zip`（官方 Sun 补充包） | 已下载、SHA256 已审计 `185385186533...` | ⭐⭐⭐⭐⭐ 主推 |
| `estg.html` | 同包 | 已下载 | 备选（结构化但格式噪声多） |
| 旧 `estg_selected_150_de.jsonl` | development 旧文件 | **不推荐**（OCR 来源不同、Sun ID 不一致） | ⛔ 弃用 |
| 自抓 Bundesfinanzministerium | 公开 | 需审核 license | 备选 |

**主推**：`EStG_raw.txt`（与 Sun 同一来源）。

---

## 4. 抽样流程

```
输入：EStG_raw.txt（UTF-8 干净版）
            │
            ▼
┌────────────────────────────────────────────┐
│ 第 1 步：句子切分 + paragraph 标记           │
│ ─ 工具：自写分句（避免 spaCy 偏向）         │
│ ─ 输出：sentences.jsonl                     │
│   {sentence_id, text, paragraph_id,        │
│    section_id, ordinal_in_paragraph}       │
│ ─ 记录：split_method, 工具版本              │
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│ 第 2 步：4 标准过滤（顺序重要）              │
│ ─ 2.1 长度 > 20 词                         │
│ ─ 2.2 包含至少 1 个 legal-act marker       │
│       （shall/may/must not/darf/nicht      │
│        等 10 个候选）                       │
│ ─ 2.3 paragraph-internal（不取首句/末句）  │
│ ─ 2.4 完整度检测（主谓宾启发式）            │
│ ─ 输出：candidate_pool.jsonl（约 800-1200 句）│
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│ 第 3 步：分层抽样                            │
│ ─ 目标：150 句                              │
│ ─ 分层依据：modality 分布（obligation /     │
│   prohibition / permission / definition）   │
│ ─ 目标分布（基于 Sun 论文表）：             │
│   obligation   50% (~75 句)                 │
│   prohibition  20% (~30 句)                 │
│   permission   20% (~30 句)                 │
│   definition   10% (~15 句)                 │
│ ─ 抽样方法：每层内按 hash 排序取前 N        │
│   （确定性、可复现）                        │
│ ─ 记录：stratification_seed, 排序 hash      │
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│ 第 4 步：用户抽审（10% 抽样 = 15 句）       │
│ ─ 验证：是否真的 complete + sequential     │
│ ─ 验证：是否含明确 legal act                │
│ ─ 失败：标 outlier，重抽                    │
└────────────────┬───────────────────────────┘
                 │
                 ▼
         冻结的 150 句（`estg_150_frozen_v1.jsonl`）
```

---

## 5. sample_id 命名规则

格式：`estg_NNNNN`

- `NNNNN` = 5 位 zero-padded 序号（00001-00150）
- 序号基于**抽样阶段 hash 排序**的位置，**不是** Sun 原 150 句的 ID
- 一旦冻结，**永不**改 ID（即使被替换也保留占位）

**与旧 pack ID 关系**：完全独立。可能与旧 `estg_000001` ~ `estg_000150` 数值重叠但内容不同，**禁止混用**。

---

## 6. 字段（每条 sample）

```json
{
  "sample_id": "estg_00001",
  "source": {
    "source_name": "EStG 1988 (raw from Archive.org)",
    "source_sha256": "185385186533FCDB...",
    "source_section": "§ X Abs. Y Satz Z",
    "source_paragraph_id": "p_1234",
    "ordinal_in_paragraph": 3,
    "source_text_de": "干净的德文原文",
    "candidate_text_en": "DeepL/GPT-4 初译"
  },
  "stratification": {
    "target_modality": "obligation",
    "stratification_seed": 42,
    "stratification_layer_size": 75,
    "selection_rank_in_layer": 1
  },
  "selection_policy": "New sample per DATA_TRANSLATION_PROTOCOL + EStG_150_SAMPLING_PROTOCOL. Not Sun et al.'s original sample."
}
```

**关键**：显式记 `selection_policy`，防止误以为是 Sun 原 150 句。

---

## 7. 与旧 pack 的关系（明确切割）

| 项 | 旧 pack | 新 pack |
|---|---|---|
| 路径 | `data/development/human_review/estg150_review_pack_v1.jsonl` | `data/input/estg_150_frozen_v1.jsonl`（待生成） |
| 抽样源 | 历史 OCR（可能乱码） | 官方 EStG_raw.txt（干净） |
| 翻译 | 旧 LLM 自动（无 provenance） | DeepL/GPT-4 + glossary + provenance |
| ID 含义 | 历史序号 | 新 hash 排序序号 |
| 与 Sun 关系 | **不**是 | **不**是（但结构对齐 Sun 4 标准） |
| 用途 | development-only | 正式 input |

**严禁把旧 pack 的 150 条 ID 直接搬到新 pack**。

---

## 8. 与旧 150 句 Gold 数值的关系

Sun 论文报告：modality 82 / actor 118 / action 147 / condition 46 / constraint 35
/ exception 15 = 443 短语 span。

**新 150 句不要求 Gold 数量与 Sun 完全一致**：
- 数据不同 → 分布不同是正常的
- 但应在 `data/input/.../selection_metadata.json` 中**记录目标分布**，便于后续 Gold 审核时做合理性检查

---

## 9. 实施步骤（建议 1 周）

| 步骤 | 任务 | 输出 |
|---|---|---|
| 1 | 写 `scripts/sample_estg_150.py`（分句 + 4 标准 + 分层） | 抽样脚本 |
| 2 | 在 EStG_raw.txt 上跑 | `data/development/estg/.../candidates.jsonl` |
| 3 | 用户抽审 15 句 | `.../outliers.json` |
| 4 | 重抽到 150 句 | `data/input/estg_150_frozen_v1.jsonl` |
| 5 | 跑 audit + 记录 | audit event |

---

## 10. 边界声明（SUPERSEDED — kept for provenance）

The original §10 plan is **cancelled**. The actual operational rules
for the EStG-150 v1 membership are:

- There is **one** 150. Do not run a second sampling; do not split into
  "old 150 / new 150".
- The membership is the sorted legacy `record_id`s of
  `estg_selected_150_de.jsonl`. See `docs/ESTG150_DATA_MAP.md`.
- The official EStG text under `references/datasets/estg_1988.pdf` and
  `references/datasets/estg_1988_raw.txt` is used **only** for
  read-only 1-to-1 source location mapping and for low-risk German text
  cleaning, never for re-selection.
- The user-editing surface is
  `data/development/human_review/estg_150_canonical_review_v1.json`.
- Old review pack, old auto-Gold files, and old translation are
  development provenance only. They are not pre-filled and not deleted.
- The benchmark must be called an **independently reconstructed
  EStG-150**, not Sun et al.'s original 150.
- "Frozen" means the v1 file's `format_valid` is true and its
  `membership_payload_sha256` matches
  `estg_150_membership_hashes.json`; future v2 must be a new file with a
  new payload SHA, never silent in-place edits to v1.

---

## 11. 待用户确认（RESOLVED — SUPERSEDED）

All open questions in this section are now resolved by the
2026-07-12 17:15 user final decision:

- ~~分层分布（50/20/20/10）~~ — **N/A**, no re-sampling.
- ~~抽样方法（hash 排序）~~ — **N/A**, no re-sampling.
- ~~抽审比例（10% = 15 句）~~ — **N/A**, no re-sampling.
- ~~替换 1 句是否需要审计~~ — **N/A**, no replacement; future v2 must
  be a new file, never silent in-place edits to v1.
- ~~150 句之外是否要 buffer~~ — **N/A**, no buffer.

The user has authorized start of the **canonical review** workflow on
the existing 150 — see `data/development/human_review/estg_150_canonical_review_v1.json`
and the offline review tool `scripts/estg150_review_tool.py`.
