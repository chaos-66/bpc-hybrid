# Stage 2 → Stage 3 下游配对比较（S3.10 核心，零 API）

**run_id**：`s3_downstream_paired_v1`
**状态**：`Stage-2-source paired comparison on the frozen Stage-3 evaluation surface; NOT a formal end-to-end result (S2.13 freeze and the authorized real Direct-LLM batch are still pending)`

## 问题

**同一个冻结的 Stage 3 检查器**，只更换 Stage 2 的规则来源，最终检查结果如何变化？这是“Stage 2 改进能否传导到最终合规检查”的直接证据。

## 规则来源（只有这一项变化）

| 臂 | 状态 | 说明 | 胶囊 sha256 |
|---|---|---|---|
| rules_only | available | locked non-LLM Stage-2 capsule (B0 v10a); the project's non-LLM baseline rule source | `a993ef533489b727` |
| human_rules | available | formal GDPR-7 Gold Rule Records (user-confirmed human adjudication); the Stage-2 quality ceiling | `9d86e1b4360a8ef2` |
| direct_llm | blocked | Direct-LLM Stage-2 capsule; requires the authorized real run and explicit promotion (absent -> reported as blocked) | `-` |

共享且冻结：7 个 GDPR 流程、阈值（tau/gamma/theta=0.8）、evaluator、Gold。

## 1. 原三类（33 条人工 violation Gold）

| 规则来源 | macro-F1 | exact | detected | missed | wrong-type | unobservable |
|---|---:|---:|---:|---:|---:|---:|
| rules_only | 0.3333 | 0.3333 | 11 | 22 | 0 | 11 |
| human_rules | 0.3333 | 0.3333 | 11 | 22 | 0 | 11 |
| direct_llm | - | - | - | - | - | - |

### 逐类型 F1

| 类型 | rules_only | human_rules | direct_llm |
|---|---:|---:|---:|
| missing_action | 1.000 | 1.000 | - |
| incorrect_actor | 0.000 | 0.000 | - |
| out_of_order | 0.000 | 0.000 | - |

### 变化量（相对 rules_only）

| 指标 | Δ |
|---|---:|
| human_rules_minus_rules_only.macro_f1 | +0.0000 |
| human_rules_minus_rules_only.exact_type_accuracy | +0.0000 |
| human_rules_minus_rules_only.detected | +0.0000 |
| human_rules_minus_rules_only.missed | +0.0000 |
| human_rules_minus_rules_only.wrong_type | +0.0000 |
| human_rules_minus_rules_only.unobservable | +0.0000 |
| human_rules_minus_rules_only.missing_action | +0.0000 |
| human_rules_minus_rules_only.incorrect_actor | +0.0000 |
| human_rules_minus_rules_only.out_of_order | +0.0000 |

## 2. 四类扩展面板（40 变体 + 40 合规对照）

| 规则来源 | 后端 | variant exact | macro | control FP rate | paired acc |
|---|---|---:|---:|---:|---:|
| rules_only | Winter-style extension | 0.3750 | 0.5208 | 0.4500 | 0.1500 |
| rules_only | Sun-style extension | 0.1500 | 0.1875 | 0.0500 | 0.1500 |
| rules_only | BM25 extension | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| rules_only | TF-IDF/SVD extension | 0.2750 | 0.3510 | 0.3750 | 0.2250 |
| human_rules | Winter-style extension | 0.2250 | 0.3409 | 0.2500 | 0.1000 |
| human_rules | Sun-style extension | 0.0250 | 0.0454 | 0.0000 | 0.0250 |
| human_rules | BM25 extension | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| human_rules | TF-IDF/SVD extension | 0.1250 | 0.2063 | 0.1750 | 0.1000 |
| direct_llm | - | - | - | - | - |

> 四类扩展为 development-only 合成受控面板；Winter/Sun 原论文未定义这四类，一律写 `Winter-style extension` / `Sun-style extension`。

> **面板偏差提示**：The 40-variant synthetic panel binds its locked rule elements to data/development/human_review/stage3_gold_inference_v1.json (the S3.5 development extraction).  The panel was therefore built around the development adapter's own six-element reading and its first-valid-span projection keeps only the FIRST confirmed item of a multi-item sentence (11/40 variants sit on multi-item sentences).  Panel numbers are consequently a biased-comparison surface for the human-rule arm; the unbiased Oracle surface is the 33-item human Gold reported in section 1 and in outputs/reports/s3_oracle_gold_rules_v1.json.

## 3. 结论边界

- Reported per arm; the human-rule arm is the Stage-2 quality ceiling and the Rules-Only arm is the non-LLM baseline, so the delta isolates the effect of the rule source on the frozen checker.
- The Direct-LLM arm stays blocked until the authorized real batch runs and its capsule is promoted; no value is imputed.
- The 40-variant synthetic panel binds its locked rule elements to data/development/human_review/stage3_gold_inference_v1.json (the S3.5 development extraction).  The panel was therefore built around the development adapter's own six-element reading and its first-valid-span projection keeps only the FIRST confirmed item of a multi-item sentence (11/40 variants sit on multi-item sentences).  Panel numbers are consequently a biased-comparison surface for the human-rule arm; the unbiased Oracle surface is the 33-item human Gold reported in section 1 and in outputs/reports/s3_oracle_gold_rules_v1.json.
- 合成面板与 33 条人工 Gold 分表，从不合并。

## 4. 复现

```powershell
python formal_experiment/scripts/run_s3_downstream_paired_v1.py
```

零 LLM/API/网络；未修改 Gold、阈值、流程或既有预测。
