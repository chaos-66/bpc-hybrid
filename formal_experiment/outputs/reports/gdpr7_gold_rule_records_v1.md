# GDPR-7 正式 Gold Rule Records（Oracle 标准答案）

**状态**：published_gold_rule_records
**来源**：用户 2026-09-09 已确认的人工核对包（9 条款 / 74 句 / 92 条规范 / 320 处原文锚点）
**转换**：`gdpr7_gold_rule_record_converter@1.0.0` —— 机械、无损，未新增/推断/改写/归一化/丢弃任何值

## 计数

| 项 | 值 |
|---|---:|
| 条款 | 9 |
| 句子 | 74 |
| 规范条目 | 92 |
| 要素 span | 235 |
| 情态证据 span | 85 |
| 关联条目（actor-action + order） | 38 |

## 情态分布（按条目）

| 情态 | 条目数 |
|---|---:|
| obligation | 30 |
| permission | 36 |
| prohibition | 4 |
| definition | 22 |

## 表示约定

- **一条规范 = 一个 clause**（不是一句一个 clause）；多情态句保留每条规范自己的情态标签。
- 坐标为**句内相对坐标** `0..len(sentence_text)`，与冻结输入 `data/input/gdpr7_stage2_input_v1.json` 一致。
- `actor_action_map` 与 `order_relations` 逐字复制自人工确认条目：不推断、不增删任何边。
- 第三阶段胶囊（`data/predictions/gdpr7_human_rule_record_v1/`）由本 Gold 派生，供现有 `gdpr_capsule_converter` 直接消费。

## 产物

| 路径 | sha256 |
|---|---|
| `data/gold/stage3/gdpr7_gold_rule_records_v1.json` | `7cf896abdb6e420e46efd297a8e183bcdc4c15834aa9567eb88d1af60eec627a` |
| `data/predictions/gdpr7_human_rule_record_v1/manifest.json` | `281f7cb6c8ee8d608eee11991cc3266a2caa48992d2b5927e32e58aca5f03a8d` |
| `data/predictions/gdpr7_human_rule_record_v1/predictions.json` | `9d86e1b4360a8ef2d9acfacdda4cd3b5d7e2e35f7f3de68eeebaa0a793432500` |
| `outputs/reports/gdpr7_human_rule_record_capsule_v1.json` | `70aa687919da1a26f1cd97fd6cf450b847f73719474f209a700487ac3e9b0dff` |

## 复现与验证

```powershell
python formal_experiment/scripts/build_gdpr7_gold_rule_records_v1.py --check
python formal_experiment/scripts/verify_gdpr7_gold_rule_records_v1.py
```

## 边界

- 第三方法规原文不提交（`raw_third_party_text_committed=false`）。
- 不改动既有 Stage 3 matching/violation decision Gold。
- 本轮不启动 Oracle、不调用 LLM/API。
