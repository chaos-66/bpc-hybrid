# S2.8D-R5: Freeze Gold-blind Small-scale H1 Pilot Plan (10 calls)

**Task**: S2.8D-R5 — 冻结 Gold-blind 小规模 H1 pilot 计划（10 次真实调用）、
调用预算与执行门禁。只做选样、预算冻结、精确绑定、early-stop 合同、离线验证、
脱敏报告与 Git checkpoint；**本轮不运行真实 pilot（API calls = 0）**。

**起始 commit**: `a3045241867f8605e7f39cfb3b767bf037964a30`

**Safety**: API calls=0；retry=0；pilot 未运行；Gold / Layer E / `.env` 未读；
B0 / trigger / risk / repair-field 推导 / masked v5 prompt / coordinate
canonicalizer / canonical validator / patch-canonical schema / model gate /
formal gates 均未修改；R1–R4 历史产物未覆盖；P/R = not_computed。

---

## 1. 冻结规模与预算

| 项 | 值 |
|---|---|
| pilot plan 数 | 10 |
| 不同 sample 数 | 10（每个 sample 至多 1 个 plan） |
| hard API call cap | 10 |
| retry per plan | 0 |
| max calls per plan | 1 |
| 模型 | `deepseek-v4-flash`（model gate 冻结值） |
| prompt variant / SHA-256 | `masked_selected_v5` / `065005189ced3179ff4069d016c7d0ca892ce4992707834e09142efc0472c391` |
| B0 attempts SHA-256 | `79dc457cdf933cb9fbb29030bab3673b9af645dd0138d8e97f5d1b6dfa6b4792` |
| B0 manifest SHA-256 | `88070fab4da3f7c708f055f6bc391b78cc888761c3d6fe117d17673c2c382315` |
| frozen plan 配置路径 | `formal_experiment/configs/s28d_r5_h1_small_pilot_plan_v1.json` |
| frozen plan 配置 SHA-256 | `35dc6a752361b3876c4531a5e15c0bbfb37450d312ff705f3f791dbe903c1327` |

## 2. 历史真实调用集合（只读恢复）

来源（全部 `real_api=true` 的 H1 manifest/telemetry）：

| run | calls |
|---|---|
| `s28d_h1_real_pilot/canary`（v4-flash canary） | 1 |
| `s28d_h1_real_pilot/pilot_v4flash`（v4-flash pilot） | 19 |
| `s28d_h1_real_pilot_deviation/v4pro_exploratory_run`（v4-pro 偏差） | 20 |
| `s28d_r1_h1_canary_v1`（S2.8D-R1） | 1 |
| `s28d_r4_h1_canary_v1`（S2.8D-R4） | 1 |
| **合计真实调用** | **42** |

- 去重后唯一 plan keys：**20**
- plan keys SHA-256：`c813a384265973dae416c6f458338caa08a2505d6c29b44b67cf7831ac2ed68a`
- 规则：只要某 sample/clause 曾向真实 provider 发送过 H1 请求（无论模型偏差、
  响应为空、patch 拒绝或未产生修改）都视为已调用，不得进入本次 pilot。

## 3. Gold-blind 确定性选样

规则（未重写 trigger/risk/排序，全部复用现有 `build_repair_plans` 与
`allocate_repair_calls` 排序：risk score 降序 → sample_id → clause_index）：

1. 从冻结 B0 v10a 生成全部 repair plans（221 triggered plans / 135 samples）；
2. 排除历史已调用 20 个 plan keys；
3. 按排序依次扫描，每个 sample 只保留第一个 plan；
4. 取前 10 个 plan（10 个不同 sample）；
5. 不查看 Gold / Layer E / 任何评价结果。

**结果**：10 个 plan、10 个不同 sample；与历史已调用集合交集为空。

| order | sample_id | clause_id | idx | risk | repair_fields | reasons |
|---|---|---|---|---|---|---|
| 1 | `estg_000118` | `estg_000118.c1` | 0 | 160 | `modality, actors, actor_action_map` | `non_definition_missing_actor; classifier_marker_disagreement; alignment_confidence_below_0_65` |
| 2 | `estg_000133` | `estg_000133.c1` | 0 | 160 | `modality, actors, actor_action_map` | `non_definition_missing_actor; classifier_marker_disagreement; alignment_confidence_below_0_65` |
| 3 | `estg_000164` | `estg_000164.c2` | 1 | 160 | `modality, actors, actor_action_map` | `non_definition_missing_actor; classifier_marker_disagreement; alignment_confidence_below_0_65` |
| 4 | `estg_000206` | `estg_000206.c2` | 1 | 160 | `modality, actors, actor_action_map` | `non_definition_missing_actor; classifier_marker_disagreement; alignment_confidence_below_0_65` |
| 5 | `estg_000207` | `estg_000207.c2` | 1 | 160 | `modality, actors, actor_action_map` | `non_definition_missing_actor; classifier_marker_disagreement; alignment_confidence_below_0_65` |
| 6 | `estg_000232` | `estg_000232.c1` | 0 | 160 | `modality, actors, actor_action_map` | `non_definition_missing_actor; classifier_marker_disagreement; alignment_confidence_below_0_65` |
| 7 | `estg_000285` | `estg_000285.c1` | 0 | 160 | `modality, actors, actor_action_map` | `non_definition_missing_actor; classifier_marker_disagreement; alignment_confidence_below_0_65` |
| 8 | `estg_000302` | `estg_000302.c1` | 0 | 160 | `modality, actors, actor_action_map` | `non_definition_missing_actor; classifier_marker_disagreement; alignment_confidence_below_0_65` |
| 9 | `estg_000414` | `estg_000414.c1` | 0 | 160 | `modality, actors, actor_action_map` | `non_definition_missing_actor; classifier_marker_disagreement; alignment_confidence_below_0_65` |
| 10 | `estg_000716` | `estg_000716.c3` | 2 | 160 | `modality, actors, actor_action_map` | `non_definition_missing_actor; classifier_marker_disagreement; alignment_confidence_below_0_65` |

- selected plan keys SHA-256：`bb8d73b2af61964e0c2bb3142b0ec91a75653130a33e7270981984d6cd426d23`

## 4. Frozen-plan 执行绑定（fail closed）

新增 `--frozen-plan PATH` 与 `src/bpc_hybrid/h1_pilot_plan.py`（纯函数模块）。
绑定校验（任一不一致 → 调用前拒绝，API calls=0，不自动重生成、不回退普通
ranking）：

- schema version / task / development_only / gold_visible=false；
- B0 attempts SHA 与 manifest SHA 完全一致；
- prompt variant 与 prompt SHA 一致；
- model == `deepseek-v4-flash`；
- 每个冻结 plan 存在于当前 plans，且 sample_id / clause_id / clause_index /
  risk_score / repair_fields / reasons 完全一致；
- b0_prediction_sha256、clause_identity_hash、rendered_masked_context_hash 一致；
- 无重复 plan、无重复 sample、数量恰为 10、execution_order 恰为 1–10；
- 所有 plan 均不在冻结的历史已调用集合中；
- `--max-calls` 必须为 10；`--exclude-plan` 与 `--frozen-plan` 互斥。

默认行为（不提供 `--frozen-plan`）完全不变。

## 5. Early-stop 合同（已实现并测试，本轮不触发）

必须立即停止剩余调用：

* requested/resolved/provider-returned 模型不一致或模型 != `deepseek-v4-flash`
  （`provider_model_mismatch`）；
* capture 无法写入/绑定（`capture_binding_failure`）；
* 调用计数超过冻结预算（`authorization_or_call_count_violation`）；
* 执行 plan key 与冻结顺序不一致（`plan_key_mismatch`）；
* 连续 3 次 transport/extraction 失败（`consecutive_transport_or_extraction_failures`）。

停止后：未调用剩余 plan 在 telemetry 标记 `pilot_early_stop_not_called`；
不得补选其他 plan；每个 plan 最多 1 次调用，绝不 retry。

记录后继续（科学结果，不终止 pilot）：JSON/patch contract rejection、
coordinate zero/ambiguous/contract violation、canonical validator rejection、
unauthorized/no-op/relation/ID rejection。

## 6. 离线 plan-only 验证

命令（`--plan-only`，0 API calls）：

```text
python formal_experiment/scripts/run_sun_llm_fallback.py --b0-predictions
  formal_experiment/outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json
  --b0-manifest .../manifest.json --frozen-plan
  formal_experiment/configs/s28d_r5_h1_small_pilot_plan_v1.json --output
  .../s28d_r5_h1_small_pilot_plan_check_v1/h1_predictions.jsonl --telemetry ...
  --manifest ... --prompt-variant masked_selected_v5 --plan-only --max-calls 10
  --development
```

| 项 | 值 |
|---|---|
| selected_plan_count / selected_sample_count | 10 / 10 |
| llm_calls / real_api | 0 / false |
| patch proposed / accepted / rejected | 0 / 0 / 0 |
| changed / `h1_non_identity_gate` | 0 / false |
| H1 vs B0 | 全部 150 样本逐位一致（H1 == B0） |
| execution order | 与 frozen plan 1–10 完全一致 |
| selected keys hash | 一致（`bb8d73b2…`） |
| 历史交集 | 空 |
| 重复运行 | predictions/telemetry/manifest 同路径 byte-identical |

## 7. 测试

- 新增 `tests/test_h1_pilot_plan.py`：29 项测试覆盖任务要求的 30 个验收点
  （结构校验、绑定 fail-closed、plan-only 0 calls、默认行为不变、early-stop
  五类触发 + 不补选 + not-called 标记 + 调用上限、byte-identical、脱敏检查）；
- 全离线 synthetic fixture；不联网、不读 `.env`、不读 Gold/Layer E；
- H1 相关 focused 套件：106 passed。

## 8. 结果解释边界

- 只冻结并验证计划；pilot 未运行、API calls=0；
- 不得宣称 pilot 成功或 H1 P/R 提升；P/R = not_computed；
- 未来 S2.8D-R6 十次真实 pilot 需要用户**单独授权**。

## 9. 未来 R6 精确命令模板（本轮未执行）

```text
NOT AUTHORIZED IN S2.8D-R5
python formal_experiment/scripts/run_sun_llm_fallback.py   --b0-predictions formal_experiment/outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json   --b0-manifest formal_experiment/outputs/development/s27_estg150_b0_enhanced_v10a/manifest.json   --frozen-plan formal_experiment/configs/s28d_r5_h1_small_pilot_plan_v1.json   --output formal_experiment/outputs/development/s28d_r6_h1_small_pilot_v1/h1_predictions.jsonl   --telemetry formal_experiment/outputs/development/s28d_r6_h1_small_pilot_v1/h1_telemetry.jsonl   --manifest formal_experiment/outputs/development/s28d_r6_h1_small_pilot_v1/manifest.json   --transport-capture formal_experiment/outputs/development/s28d_r6_h1_small_pilot_v1/transport_capture.jsonl   --prompt-variant masked_selected_v5 --allow-llm --model deepseek-v4-flash   --max-calls 10 --inter-call-delay 0.5 --development
```
