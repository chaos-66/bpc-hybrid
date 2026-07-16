# Project Status Snapshot — 2026-07-12 14:55

> ⚠ **SUPERSEDED**（2026-07-13 11:30 Event 22 后追加的醒目提示）
> 本快照是 **2026-07-12 14:55** 写入的历史快照。本快照第 §2 报告的
> `human_review_ready=false`、`final_experiment_ready=false` 是当时的
> 状态机（只有"已完整审核"和"全部完成"两个布尔）。**该状态语义已被
> 2026-07-13 11:30 路线锁升级（Event 21）+ 2026-07-13 11:30 四门禁
> 再对齐（Event 22）取代**。
>
> 当前真实状态（**以 `python formal_experiment/scripts/audit_project.py`
> 为准**）：
> - `human_review_input_ready = true`（输入已就绪，可以开始人工审核）
> - `human_review_freeze_ready = false`（150/150 尚未裁决）
> - `formal_gold_publication_ready = false`（route/data/stage3 仍 reopened）
> - `final_experiment_ready = false`
> - `integrity_pass = true`
>
> 本快照正文（14:55 写入的历史内容）**保持不变**，仅在顶部追加
> 上述 SUPERSEDED 提示，方便未来 Agent 看清时间线。
>
> 当前活跃权威源：`docs/ROUTE_LOCK.md` §5.1（4 门禁表）、
> `docs/HUMAN_GOLD_GUIDE.md` §4.1.1、`docs/CURRENT_HANDOFF_2026-07-12.md`、
> `docs/AUDIT_LOG.md`、`docs/AUDIT_EVENTS.jsonl`。

> **状态**：历史快照，**点对点冻结**。除 §14:55 写入的 6 个新交付物与状态数字
> 外，请勿依据本文档判断 14:55 之后的状态；任何 14:55 之后的事实请以
> `docs/CURRENT_HANDOFF_2026-07-12.md`、`docs/AUDIT_LOG.md`、
> `docs/AUDIT_EVENTS.jsonl` 为准。
>
> **目的**：让任何未来 Agent 30 秒内完整接手项目。所有关键事实 + 6 个新交付物 +
> 当前门禁状态，一页搞定。
>
> 权威源：`docs/CURRENT_HANDOFF_2026-07-12.md`（含 §12-15）、`docs/USER_DECISION_LOCK_2026-07-12.md`（含 14:25 更新）、`docs/AUDIT_LOG.md`（人类可读）、`docs/AUDIT_EVENTS.jsonl`（机器可读）。
>
> 机器状态入口：`python formal_experiment/scripts/audit_project.py --with-tests`

---

## 1. 一句话项目定位

BPM 合规性检查中**只改 Sun et al. (2024) Stage 2 法规文档解析**，比较 B0（论文级
独立重建）/ H1（重建 + LLM 字段粒度 fallback）/ D1（纯 LLM 替换）三组在**同一
冻结 Stage 3**上的端到端增量。目标会议：CCF C 类（首选 BPM / APSEC）。

---

## 2. 机器状态（audit 真实值）

```
integrity_pass          = true   ✅ 可继续受控开发
human_review_ready      = false  ⛔ 正式 Gold 审核 paused
final_experiment_ready  = false  ⛔ 不可出最终指标
0 errors / 8 blockers / 4 warnings / 8 passes
tests: 513 passed, 22 skipped
git_commit: 469f840bd23e86f6be699f83698d84ef85fcf4ac
```

---

## 3. 8 个 Blocker（按解锁难度排）

| # | code | 状态 | 下一步 |
|---|---|---|---|
| 1 | final_version_route_alignment_pending | 路线 v2 重锁中 | 等用户/导师确认本快照内 4 个设计文档 |
| 2 | stage2_dataset_alignment_pending | 官方 modality 数据未引入 | 走 B1/B2 协议后引入 |
| 3 | formal_human_review_paused | 旧 pack + 新 pack 正式审核均 paused | 路线 v2 重锁 + 数据/审核协议冻结后 |
| 4 | formal_methods_not_ready | 三组方法仍 blocked | B0 实施 + H1/D1 预注册后 |
| 5 | sun_stage2_baseline_not_paper_faithful | B0 当前是 heuristic runner | 走 `B0_RECONSTRUCTION_DESIGN.md` 后 |
| 6 | formal_capsule_not_frozen | input/gold/predictions/results 0 行 | 用户审核 150 + 走 schema v2 后 |
| 7 | stage3_benchmark_not_locked | BPMN subset/threshold/violation Gold 未锁 | 等 B0 稳定 |
| 8 | formal_capsule_not_versioned | 无 intentional Git checkpoint | 数据/审核冻结后打 tag |

---

## 4. 6 个新交付物（2026-07-12 14:25-14:55）

| 文件 | 大小 | 类型 | 状态 | 用途 |
|---|---|---|---|---|
| `data/development/human_review/estg150_review_pack_user_audit_v1.jsonl` | 222KB | data | ready | 选项① override 副本，150+1 行；用户可审，结果不进入正式 Gold |
| `docs/B0_RECONSTRUCTION_DESIGN.md` | ~9KB | design | awaiting | B0 paper-faithful 重建方法级设计（13 章 + 6 周排期） |
| `docs/DATA_TRANSLATION_PROTOCOL.md` | ~6KB | design | awaiting | 德英翻译协议（DeepL+GPT-4 + 5 步 + provenance） |
| `docs/EStG_150_SAMPLING_PROTOCOL.md` | ~7KB | design | awaiting | 150 句新抽样协议（Sun 4 标准 + 分层 + 与旧 pack 切割） |
| `docs/HUMAN_GOLD_REVIEW_PACK_SCHEMA_v2.md` | ~9KB | design | awaiting | 新审核包 schema v2（_meta + 状态机 + 冻结流程） |
| `scripts/build_user_override_review_pack.py` | 2KB | tool | ready | override 副本可重跑生成器 |

**所有交付物"零污染"**：
- ✅ 未修改原 `estg150_review_pack_v1.jsonl`
- ✅ 未写入 `data/{input,gold,predictions,results}/`
- ✅ 未调用真实 LLM / 翻译 / API
- ✅ 未触碰 `references/` 或 `archive/`
- ✅ 每步走 `audit_project.py --with-tests` + `record_change.py`

---

## 5. 用户已锁的 7 项决定（含 14:25 新增）

| 序号 | 决定 | 文档 |
|---|---|---|
| D1 | 公开来源重建 marker | `USER_DECISION_LOCK` §1 |
| D2 | 用户本人做六要素 Gold | `USER_DECISION_LOCK` §1 |
| D3 | 按论文独立重写 Sun Stage 2 | `USER_DECISION_LOCK` §1 |
| D4 | 重训 BERT-TextCNN | `USER_DECISION_LOCK` §1 |
| D5 | 德文 EStG → 英文工作语言 | `USER_DECISION_LOCK` §1 |
| **D6** | **B0 实施代码已授权**（**2026-07-12 14:25 新增**） | `USER_DECISION_LOCK` §5 + 顶部 changelog |
| **D7** | **用户可审旧 pack override 副本**（不进 Gold） | 本快照 + script banner |

**仍未授权（需要单独授权）**：
- 真实翻译 / LLM / API 批处理
- 自动产生或批准 Gold
- 直接写入 `data/{gold,predictions,results}/`
- 跳过 `audit_project.py` 或 `record_change.py`
- 删除/移动 `archive/` 或 `references/` 文件
- 旧 pack 或新 pack 正式人工 Gold 审核

---

## 6. 创新点（CCFC 卖点）

| 优先级 | 创新点 | 类型 |
|---|---|---|
| 1 | 资源贡献：可复现的 marker lexicon + provenance | 资源/工程 |
| 2 | 方法贡献：field-level selective fallback + dual-view（原文 span + 规范化 pattern） | 方法 |
| 3 | 方法学贡献：frozen control variables + downstream propagation analysis | 方法学 |
| 4 | 消融体系：4 × 3 × 3 = 36 组（B0/H1/D1 各自变体） | 实验 |

完整说明：`docs/STAGE2_LLM_INNOVATION_DESIGN.md` + `docs/CCF_C_POSITIONING_AND_SUPERVISOR_FIGURE.md`

---

## 7. 路线状态

```
路线 ID: sun_2024_final_version_stage2_reconstruction
状态:    reopened_for_final_version_alignment (v2 重锁中)
claim:   paper-faithful independent reconstruction of the final published Sun Stage 2
forbid:  Sun original / exact reproduction / 导师包 = Sun 完整源码
```

---

## 8. 未来 Agent 第一天（30 秒）必读

1. 本快照（你现在读的）
2. `docs/CURRENT_HANDOFF_2026-07-12.md`（权威源，含 §1-15）
3. `docs/USER_DECISION_LOCK_2026-07-12.md`（含 14:25 更新）
4. `docs/ROUTE_LOCK.md`（路线 v2）
5. `python formal_experiment/scripts/audit_project.py --with-tests`（机器状态确认）

**按需**读：B0/翻译/抽样/审核包 4 个设计文档

---

## 9. 机器可读 JSON 快照

```json
{
  "snapshot_at_utc": "2026-07-12T06:55:00Z",
  "snapshot_by": "AI assistant per user verbal authorization",
  "session_id": "mvs_4982f5cb0e694b4a8e85d7d6d5c06ced",
  "machine_state": {
    "integrity_pass": true,
    "human_review_ready": false,
    "final_experiment_ready": false,
    "errors": 0,
    "blockers": 8,
    "warnings": 4,
    "passes": 8,
    "tests_passed": 513,
    "tests_skipped": 22,
    "git_commit": "469f840bd23e86f6be699f83698d84ef85fcf4ac"
  },
  "route": {
    "id": "sun_2024_final_version_stage2_reconstruction",
    "status": "reopened_for_final_version_alignment",
    "method_status": {
      "sun_rule_only": "blocked_final_sun_stage2_reimplementation_required",
      "sun_llm_fallback": "blocked_until_faithful_baseline_data_and_triggers_are_locked",
      "direct_llm": "blocked_until_official_data_output_contract_and_evaluator_are_locked"
    }
  },
  "user_authorizations_2026_07_12": {
    "D1_public_marker_reconstruction": true,
    "D2_user_gold_review": true,
    "D3_paper_faithful_reimplementation": true,
    "D4_retrained_bert_textcnn": true,
    "D5_german_to_english": true,
    "D6_b0_implementation_code_authorized_at_1425": true,
    "D7_user_can_audit_legacy_pack_via_override_copy": true
  },
  "still_locked": {
    "real_llm_api": false,
    "automatic_gold": false,
    "formal_data_writes": false,
    "skip_audit_or_record_change": false,
    "formal_human_gold_review": false
  },
  "deliverables_this_session": [
    {
      "path": "data/development/human_review/estg150_review_pack_user_audit_v1.jsonl",
      "kind": "data",
      "status": "ready",
      "audit_event_id": 9
    },
    {
      "path": "docs/B0_RECONSTRUCTION_DESIGN.md",
      "kind": "design",
      "status": "awaiting_user_mentor_approval",
      "audit_event_id": 9
    },
    {
      "path": "docs/DATA_TRANSLATION_PROTOCOL.md",
      "kind": "design",
      "status": "awaiting_user_mentor_approval",
      "audit_event_id": 9
    },
    {
      "path": "docs/EStG_150_SAMPLING_PROTOCOL.md",
      "kind": "design",
      "status": "awaiting_user_mentor_approval",
      "audit_event_id": 9
    },
    {
      "path": "docs/HUMAN_GOLD_REVIEW_PACK_SCHEMA_v2.md",
      "kind": "design",
      "status": "awaiting_user_mentor_approval",
      "audit_event_id": 9
    },
    {
      "path": "scripts/build_user_override_review_pack.py",
      "kind": "tool",
      "status": "ready",
      "audit_event_id": 9
    },
    {
      "path": "docs/USER_DECISION_LOCK_2026-07-12.md",
      "kind": "decision",
      "status": "updated_at_1425",
      "audit_event_id": 8
    },
    {
      "path": "docs/CURRENT_HANDOFF_2026-07-12.md",
      "kind": "handoff",
      "status": "updated_with_sections_12_to_15",
      "audit_event_id": 10
    },
    {
      "path": "docs/STATUS_SNAPSHOT_2026-07-12.md",
      "kind": "snapshot",
      "status": "first_written",
      "audit_event_id": 10
    }
  ],
  "what_was_NOT_changed": [
    "data/development/human_review/estg150_review_pack_v1.jsonl (source preserved)",
    "data/input/ (still empty)",
    "data/gold/ (still empty)",
    "data/predictions/ (still empty)",
    "data/results/ (still empty)",
    "references/ (read-only)",
    "archive/ (read-only)",
    "any LLM/API/translation call"
  ],
  "waiting_on_user": [
    "Approve 4 design drafts (B0 + translation + sampling + review-pack schema)",
    "Mentor review of 4 design drafts",
    "User audit of estg150_review_pack_user_audit_v1.jsonl (optional, familiarization only)"
  ]
}
```

---

## 10. 实验路线速查（4 条线 + 6 周排期 + 解锁依赖）

### 4 条并行线

| 线 | 目标 | 优先级 | 起始依赖 | 解锁的 blocker |
|---|---|---|---|---|
| **A 线 B0 复现** | paper-faithful 重建 B0（句子级 BERT-TextCNN + 短语级 CoreNLP/Tregex/Tsurgeon） | 🔴 高 | 4 个设计文档批准 | #5 sun_stage2_baseline_not_paper_faithful |
| **B 线 数据/审核** | 德英翻译 + 150 句新抽样 + 新审核包 schema v2 | 🔴 高 | B1/B2/B3 协议批准 | #2 stage2_dataset_alignment_pending, #3 formal_human_review_paused |
| **C 线 Stage 3** | BPMN subset (4/7) + threshold + violation Gold 冻结 | 🟡 中 | B0 端到端跑通 | #7 stage3_benchmark_not_locked |
| **D 线 H1/D1** | trigger 预注册 + prompt 预注册 + 真实 LLM 调用 | 🟢 低 | B0 完整跑通 + 用户授权 LLM | #4 formal_methods_not_ready |

### 6 周排期（来自 B0_RECONSTRUCTION_DESIGN §10）

| 周次 | 任务 | 里程碑 | 验证命令 |
|---|---|---|---|
| **W1** | A2 marker lexicon 模块 + A3 BERT-TextCNN 训练脚本 | 4 类词典冻结 + dev F1 跑出 | `audit --with-tests` |
| **W1** | B1 DeepL wrapper + glossary 种子 | 翻译脚本可重跑 | `audit --with-tests` |
| **W2** | A4 CoreNLP wrapper + Tregex/Tsurgeon | 句子级 + 短语级独立跑通 | `audit --with-tests` |
| **W2** | B2 抽样脚本跑出 150 句 | candidates.jsonl 生成 | `audit --with-tests` |
| **W3** | A5 六要素抽取（按 Sun 顺序） | 单元测试过 | `pytest tests/` |
| **W3** | B3 新审核包 schema v2 生成器 | 空 pack 生成 | `audit --with-tests` |
| **W4** | A6 rule record + Stage 3 adapter 联调 | 端到端 1 句 | `audit --with-tests` |
| **W4** | C1 Stage 3 BPMN subset 决定 | 配置冻结 | `audit --with-tests` |
| **W5** | A7 B0 在 150 句 + GDPR-50 全量 | 完整 baseline 数字 | 报 B0 指标 |
| **W5** | C2 threshold + violation Gold 决定 | Stage 3 配置完成 | `audit --with-tests` |
| **W5** | D1 H1 trigger + D2 D1 prompt 预注册 | 不调 LLM，prompt 写好 | `audit --with-tests` |
| **W6** | A8 failure case + 报告 | 36 组消融完整 | 论文初稿 |
| **W6** | 用户授权真实 LLM（独立动作） | budget + 触发条件冻结 | `record_change --llm-api authorized_called` |
| **W6+** | D3 跑 H1 + D3 跑 D1 | 端到端三组结果 | 最终表 |

### 解锁依赖图

```
4 个设计文档批准
        │
        ├──> A2 marker lexicon  (W1) ──┐
        ├──> A3 BERT-TextCNN 训练 (W1)  │
        ├──> B1 翻译脚本  (W1)          │
        ├──> B2 抽样脚本  (W2)          ├──> B0 在干净数据跑通 (W4)
        └──> B3 审核包 schema v2 (W3)   │
                                        │
用户审核 150 句 ─────────────────────────┘
                                        │
                                        ├──> C 线 Stage 3 冻结 (W4-W5)
                                        ├──> D1/D2 H1/D1 预注册 (W5)
                                        └──> 用户授权 LLM (W5-W6)
                                                │
                                                ▼
                                        三组端到端 Stage 3 (W5-W6)
                                                │
                                                ▼
                                        消融 + 论文 (W6+)
```

### 串行 vs 并行

- **W1-W3**：A 线 + B 线**严格并行**（不互相依赖，可同时跑）
- **W4**：A 线主，B 线为辅
- **W5-W6**：C/D 线解锁后 4 条线全开
- **关键串行点**：B0 跑通（→ 解锁 C/D 线）→ Stage 3 冻结（→ 端到端）→ LLM 授权（→ H1/D1 跑）

### 立即可动（无需等任何审批）

| 任务 | 状态 | 说明 |
|---|---|---|
| 审 4 个设计文档 | 🟡 你 + 导师 | 10-20 分钟/份 |
| 审 override 副本 | 🟡 你 | 熟悉 EStG 文本 |
| 提 B1/B2/B3 协议的修改建议 | 🟡 你 | 改完我重写 |

### 动代码前必读

```powershell
# 每次改代码前
git status --short
python formal_experiment/scripts/audit_project.py

# 改完后
python formal_experiment/scripts/audit_project.py --with-tests
python formal_experiment/scripts/record_change.py `
  --purpose "..." `
  --gold audit_read_only `
  --llm-api not_called `
  --artifacts not_created_or_overwritten `
  --notes "..."
```

---

## 11. 一句话给未来 Agent

> "项目处于 v2 路线重锁中；研究目标 + 7 项用户决定 + 6 个新交付物已就位；B0 实施代码已授权但需 4 个设计文档先过审；真实 LLM/翻译/正式 Gold 仍单独授权；旧 pack 走 override 副本形式可审但结果不进 Gold。当前 8 个 blocker 全部健在，需按 §3 顺序逐个解锁；实验路线 4 条线并行 6 周排期见 §10。**任何代码改动前必跑 `audit_project.py --with-tests` + `record_change.py`**。"
