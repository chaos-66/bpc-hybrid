# S2.8D-R4: Single Real deepseek-v4-flash Canary (Coordinate Canonicalization Enabled)

**Task**: S2.8D-R4 — 在 coordinate canonicalization（S2.8D-R3）启用后执行一次真实
`deepseek-v4-flash` canary，验证 transport → 非空 patch → canonicalizer →
validator → atomic merge → `H1 != B0` 的完整链路。

**起始 commit**: `e9c3bd521a06c323d5854c22b5a842fb35717a7c`
**run_id**: `s28d_r4_h1_canary_v1`

**Safety**: 用户明确授权恰好 1 次 `deepseek-v4-flash` 真实调用；retry=0；未进入
pilot；Gold / Layer E / `.env` 未读；prompt、validator、canonical schema、B0 /
trigger / risk / budget、model gate 均未改；R1/R3 历史结果未改；P/R = not_computed。

---

## 1. 唯一真实调用（hard cap 1，retry 0）

| 项 | 值 |
|---|---|
| 输出目录 | `formal_experiment/outputs/development/s28d_r4_h1_canary_v1/` |
| canary manifest SHA-256 | `9734c2edc3a7c0bc6170f83d6553cc385b426b3d649233c1be1497082e8a338c` |
| transport capture SHA-256 | `92df6817fcb410bbe7a9054527cee61d3c46c280c09bad1149cecd25eb86c6e4` |
| B0 hash（estg_000021 per-record） | `57f3564baa573735b55bc252554698236b3eb744a657090abe849cd772b4bcb4` |
| prompt variant / SHA-256 | `masked_selected_v5` / `065005189ced3179ff4069d016c7d0ca892ce4992707834e09142efc0472c391` |
| requested / resolved / returned model | `deepseek-v4-flash` / `deepseek-v4-flash` / `deepseek-v4-flash` |
| API call count / retry | 1 / 0 |
| HTTP status | 200 |
| extraction status / source | `ok_message_content` / `message.content` |
| finish_reason | `stop` |
| reasoning presence / tool-call count | false / 0 |
| usage tokens | prompt=1305, completion=405, total=1710 |
| response body SHA-256 | `5a6681bbe35c90d0f12dfdd12e0dacf5adb03194942c1045033bba1c0cea299e` |
| message.content SHA-256 / char length / utf8 length | `e7514386…` / 1531 / 1531 |
| request policy sent | stream=false；thinking={type:disabled}；response_format={type:json_object}；tools_sent=false |

样本：`estg_000021` / `estg_000021.c1`（rank-1 冻结 plan，clause_span=[0,212]），
selected=1、triggered=135、samples=150。

## 2. 结果分类与核心计数

| 项 | 值 |
|---|---|
| patch proposed / accepted / rejected | 1 / 1 / 0 |
| accepted effective patch | 1 |
| prediction changed samples | 1 |
| `h1_non_identity_gate` | **true** |
| H1 vs B0 | **H1 != B0**（B0=`57f3564b…` → H1=`5bcf26d7…`） |
| identity fields | 不变（source_text / sample_id / source_id / clause_id / clause_span 全等） |

成功条件全部满足（情况 1：真实 canary 成功）。

## 3. Coordinate canonicalization

| 项 | 值 |
|---|---|
| status | `reanchored` |
| attempted / unchanged / reanchored / failed patch | 1 / 0 / 1 / 0 |
| span_count / already-valid / reanchored | 3 / 0 / 3 |
| zero / ambiguous / contract | 0 / 0 / 0 |
| original patch SHA-256 | `810a433c78c6dcb7803c45628b6102f2d5c19f7dd34cf1bc9ae6be7e63fc9024` |
| canonicalized patch SHA-256 | `c9014f7ca4c0b670d9a82afdd1d495f195746974c29e0faa70b6dfe5bbde30b0` |

脱敏 corrections（仅 offset / 长度 / 计数 / hash）：

| field_path | proposed [start,end] | corrected [start,end] | char / utf8 len | exact occurrence | text SHA-256 |
|---|---|---|---|---|---|
| modality.evidence[0] | [0,99] | [0,95] | 95 / 95 | 1 | `147907cf…` |
| actors[0] | [55,99] | [49,95] | 46 / 46 | 1 | `381a79d8…` |
| conditions[0] | [100,211] | [97,207] | 110 / 110 | 1 | `aa23d19d…` |

## 4. Validator 与 atomic merge

| 项 | 值 |
|---|---|
| canonical validator | 通过（schema + cross-field） |
| merge status | `accepted`；rejection codes 空 |
| semantic_changed | true |
| effective_patch | true |
| changed fields | actor_action_map / actors / conditions / constraints / modality |
| requested fields | actor_action_map / actors / conditions / constraints / exceptions / modality |
| rejected fields | exceptions（patch 中为 absent 标记，不构成改动） |

## 5. 离线确定性重放

输出目录：`formal_experiment/outputs/development/s28d_r4_h1_canary_replay_v1/`
（新目录；输入 `transport_responses.jsonl` 由本次 sanitized capture 重建，
message.content 与真实运行 byte-identical，SHA-256=`e7514386…`）。

| 项 | 值 |
|---|---|
| extraction status | `ok_message_content` |
| proposed / accepted / rejected | 1 / 1 / 0 |
| effective / changed / gate | 1 / 1 / true |
| H1 prediction SHA-256 | `5bcf26d7…`（与真实 canary 完全一致） |
| B0 prediction SHA-256 | `57f3564b…`（一致） |
| canonicalization | reanchored 3；zero/ambiguous/contract=0 |
| 重复运行 | 同参数同目标重放 predictions/telemetry/manifest **byte-identical** |

Replay 不计入 API calls（API calls 仍为 1）。

## 6. 结果解释边界

- transport 正常；模型返回非空可解析 patch；
- coordinate canonicalizer 正常执行（reanchored 3/3，无 zero/ambiguous/contract）；
- 现有 validator 与 atomic merge 接受；
- 真实 canary 得到 `H1 != B0`、identity 不变、gate=true；
- 不声称 P/R 优于 B0、正式评估完成、模型未来稳定、formal S2.8 解锁、可自动
  运行 pilot；P/R = not_computed；未进入 pilot。

## 7. 下一步建议

满足真实 canary 成功条件（accepted=1、effective=1、changed=1、gate=true、
H1 != B0、identity 不变），唯一推荐下一任务：

```text
S2.8D-R5：冻结小规模 pilot 计划与调用预算
```

本轮不运行 pilot、不计算 P/R。
