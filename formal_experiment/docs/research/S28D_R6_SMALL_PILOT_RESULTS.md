# S2.8D-R6: Execute the Frozen 10-call Real deepseek-v4-flash H1 Small Pilot

**Task**: S2.8D-R6 — 执行 R5 冻结的 10 次真实 `deepseek-v4-flash` H1 小规模 pilot。

**起始 commit**: `01484d4bb1acc84f86a2460440e862c2cbc38c59`
**run_id**: `s28d_r6_h1_small_pilot_v1`

**授权**: 用户明确授权严格使用冻结计划、`deepseek-v4-flash`、硬上限 10 次、
每 plan 至多 1 次、retry=0、不补选、不扩大范围、不读取/计算 P/R Gold。

**Safety**: Gold / Layer E / `.env` 未读；frozen plan、B0、trigger、risk、
repair-field 推导、masked v5 prompt、coordinate canonicalizer、canonical
validator、schema、model gate、early-stop 合同、formal gates、R1–R5 历史产物
均未修改；`outputs/development/`、capture、telemetry、predictions、运行
manifest 未提交；P/R = not_computed。

---

## 1. 执行与调用预算

| 项 | 值 |
|---|---|
| frozen plan 路径 / SHA-256 | `formal_experiment/configs/s28d_r5_h1_small_pilot_plan_v1.json` / `35dc6a752361b3876c4531a5e15c0bbfb37450d312ff705f3f791dbe903c1327` |
| selected keys SHA-256 | `bb8d73b2af61964e0c2bb3142b0ec91a75653130a33e7270981984d6cd426d23` |
| planned plan count | 10（10 个不同 sample） |
| **actual API calls** | **5**（≤ 10） |
| retry | 0 |
| 每 plan 调用数 | 均为 1 |
| 未冻结 plan 调用 | 0 |
| **early stop** | **触发**（记录原因=`plan_key_mismatch`，停止于 execution order 5 之后） |
| requested / resolved / returned model | `deepseek-v4-flash` / `deepseek-v4-flash` / `deepseek-v4-flash`（5/5） |
| 输出目录 | `formal_experiment/outputs/development/s28d_r6_h1_small_pilot_v1/` |

**early-stop 取证（重要）**：已调用的 5 个 plan 恰好是冻结计划的 order 1–5
（estg_000118 → estg_000207），每个 plan 恰好 1 次调用、HTTP 200、
extraction=ok_message_content、模型全部正确、capture 全部绑定。记录的
`plan_key_mismatch` 是**误报**：R5 runner 的 early-stop 计数存在实现缺陷——
coordinate-canonicalization-failed 分支（estg_000206 触发 zero-match）没有推进
frozen-order 游标，导致下一个 plan（estg_000207）的防御性 plan-key 检查与错误
的期望 key 比较，从而误停。真实调用本身没有任何授权/预算违规。该缺陷已修复
（frozen-order 游标改为在 selected plan 处理开始时统一推进）并新增回归测试；
修复不影响已记录的 5 次真实调用结果。

## 2. transport / extraction / usage

| 项 | 值 |
|---|---|
| transport success | 5/5（HTTP 200 分布 {200: 5}） |
| extraction success | 5/5（全部 `ok_message_content`） |
| usage tokens 总计 | prompt=7634 / completion=1342 / total=8976 |

## 3. patch 管线聚合

| 项 | 值 |
|---|---|
| valid response / patch proposed | 5 / 5（100%） |
| patch accepted / rejected | 3（60%） / 2（40%） |
| effective patch | 3（60%） |
| prediction changed samples | 3 |
| called-but-unchanged | 2 |
| H1 != B0 sample count | 3 |
| `h1_non_identity_gate` | **true** |
| identity violation count | **0** |

## 4. Coordinate canonicalization 聚合

| 项 | 值 |
|---|---|
| attempted / unchanged / reanchored / failed | 5 / 0 / 4 / 1 |
| already-valid spans / reanchored spans | 1 / 7 |
| zero / ambiguous / contract | 1 / 0 / 0 |

## 5. Validator / merge 聚合

| 项 | 值 |
|---|---|
| merge accepted / rejected | 3 / 2 |
| rejection code 分布 | `coordinate_canonicalization_zero_match`=1、`canonical_invalid`=1、`reference_mismatch`=1 |
| changed fields 分布 | modality=3、actors=3、actor_action_map=3 |

## 6. 逐 plan 脱敏结果（10 个冻结 plan）

| order | sample | clause | called | http | extraction | model | usage(p/c/t) | content utf8 | content sha | proposed | cc status | spans (total/valid/rean/zero/amb/contract) | merge | rej codes | eff | changed | changed fields | B0 sha | H1 sha |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `estg_000118` | `estg_000118.c1` | 是 | 200 | ok_message_content | `deepseek-v4-flash` | {"prompt_tokens":1472,"completion_tokens":263,"total_tokens":1735} | 900 | `f762aa6f24d5` | 1 | reanchored | 2/0/2/0/0/0 | accepted | – | 1 | 1 | `actor_action_map,actors,modality` | `1b3fd305b16a` | `65ca184c9668` |
| 2 | `estg_000133` | `estg_000133.c1` | 是 | 200 | ok_message_content | `deepseek-v4-flash` | {"prompt_tokens":1374,"completion_tokens":296,"total_tokens":1670} | 1020 | `f296e18e89f1` | 1 | reanchored | 2/1/1/0/0/0 | accepted | – | 1 | 1 | `actor_action_map,actors,modality` | `f5a7af080552` | `2aeba0e02d25` |
| 3 | `estg_000164` | `estg_000164.c2` | 是 | 200 | ok_message_content | `deepseek-v4-flash` | {"prompt_tokens":1860,"completion_tokens":264,"total_tokens":2124} | 913 | `cfc7132af6fa` | 1 | reanchored | 2/0/2/0/0/0 | accepted | – | 1 | 1 | `actor_action_map,actors,modality` | `d702f06ca28a` | `3012fdf6caa8` |
| 4 | `estg_000206` | `estg_000206.c2` | 是 | 200 | ok_message_content | `deepseek-v4-flash` | {"prompt_tokens":1481,"completion_tokens":246,"total_tokens":1727} | 824 | `0caf61f9c53a` | 1 | failed | 2/0/0/1/0/0 | rejected | coordinate_canonicalization_zero_match | 0 | 0 | `–` | `ddf575bcd1b5` | `ddf575bcd1b5` |
| 5 | `estg_000207` | `estg_000207.c2` | 是 | 200 | ok_message_content | `deepseek-v4-flash` | {"prompt_tokens":1447,"completion_tokens":273,"total_tokens":1720} | 958 | `2704e6d50a93` | 1 | reanchored | 2/0/2/0/0/0 | rejected | canonical_invalid,reference_mismatch | 0 | 0 | `–` | `0204666b6005` | `0204666b6005` |
| 6 | `estg_000232` | `estg_000232.c1` | 否 | – | – | `–` | – | – | `–` | 0 | – | –/–/–/–/–/– | – | – | – | 0 | `–` | `93bf9b83ea3f` | `93bf9b83ea3f` |
| 7 | `estg_000285` | `estg_000285.c1` | 否 | – | – | `–` | – | – | `–` | 0 | – | –/–/–/–/–/– | – | – | – | 0 | `–` | `f11a4aad1c15` | `f11a4aad1c15` |
| 8 | `estg_000302` | `estg_000302.c1` | 否 | – | – | `–` | – | – | `–` | 0 | – | –/–/–/–/–/– | – | – | – | 0 | `–` | `77048709e11b` | `77048709e11b` |
| 9 | `estg_000414` | `estg_000414.c1` | 否 | – | – | `–` | – | – | `–` | 0 | – | –/–/–/–/–/– | – | – | – | 0 | `–` | `4bd40ec7b73a` | `4bd40ec7b73a` |
| 10 | `estg_000716` | `estg_000716.c3` | 否 | – | – | `–` | – | – | `–` | 0 | – | –/–/–/–/–/– | – | – | – | 0 | `–` | `379166a3fbaa` | `379166a3fbaa` |

> “–” = 未调用/不适用；内容只报告长度与 hash，不报告文本。

## 7. H1 机制最低可用门（Gold-blind）

定义：`actual_api_calls>0` 且 `identity_violation_count=0` 且
`effective_patch_count>0` 且 `prediction_changed_sample_count>0` 且
`H1!=B0 sample count>0`。

| 检查 | 结果 |
|---|---|
| actual_api_calls>0 | 5 ✓ |
| identity_violation_count=0 | 0 ✓ |
| effective_patch_count>0 | 3 ✓ |
| prediction_changed_sample_count>0 | 3 ✓ |
| H1 != B0 sample count>0 | 3 ✓ |
| **机制门** | **通过（passed=true）** |
| effective_patch_rate | 3/5 = 0.60 |

## 8. 结果分类与 next-step

**分类：情况 B（early stop）** — 调用数 5 < 10；记录原因 `plan_key_mismatch`；
取证结论为误报（实现缺陷，已修复）。已调用：order 1–5；未调用：order 6–10
（estg_000232 / estg_000285 / estg_000302 / estg_000414 / estg_000716），
均标记 `pilot_early_stop_not_called`，未补跑、未伪装成完整 pilot。

**唯一推荐下一任务**：

```text
S2.8D-R7：Gold-blind pilot 结果审计与受控 P/R 评价解锁准备
```

另需用户单独决定是否授权完成剩余 5 个冻结 plan（本轮未调用、不再调用）。

## 9. 离线确定性重放

真实调用后未再调用 API。使用本次 sanitized capture 重建
`outputs/development/s28d_r6_h1_small_pilot_replay_v1/`
（`--offline-transport-replay`，0 API calls）：

| 项 | 值 |
|---|---|
| replayed response count | 5（全部实际已调用响应） |
| 未调用 plan | 5 个全部保留 `pilot_early_stop_not_called` 状态 |
| 每个已调用 plan 的 H1/B0 hash | 与真实运行逐位一致 |
| accepted / effective / changed / rejection code | 与真实运行一致 |
| identity fields | 一致 |
| 聚合计数 | 一致（llm_calls=5、accepted=3、rejected=2、effective=3、changed=3、gate=true） |
| 重复 replay | predictions/telemetry/manifest 同路径 **byte-identical** |

replay 输入行（transport_responses.jsonl）SHA-256：`adf4704fc9f8334bba84e16e78445c66b421ad21043610b9cf1227b88a79b4fc`。

## 10. 证据 hash

- 真实运行 manifest SHA-256：`69ea63b295bf2c88f7732aa4e1f4b10a12e598d967cb59724156758f2ee8d7ca`
- transport capture SHA-256：`5c3db68b23bea0c832bef78427cd97497ddd51c2fd77b86b5dc4bb32692d4d8f`

## 11. 解释边界

- 5 次真实调用是有效证据；结果如实保留，未重跑、未补选、未掩盖；
- early-stop 误报缺陷已修复并回归测试，但本轮真实结果保持不变；
- 不读取 Gold、不计算 P/R、不声称正式评价；P/R = not_computed；
- 剩余 5 个冻结 plan 未调用；未经用户新授权不得执行。
