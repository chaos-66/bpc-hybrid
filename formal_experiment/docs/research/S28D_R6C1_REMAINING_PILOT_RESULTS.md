# S2.8D-R6C1: Complete the Remaining Frozen Pilot Calls (orders 6–10)

**Task**: S2.8D-R6C1 — 安全补完 R6 剩余 5 个冻结 plan（原 order 6–10），形成完整
10-plan pilot 证据。

**起始 commit**: `37ab7efb4fe08603ac5a3c19f12bdf54dc287451`
**授权**: 只调用从未调用过的原 order 6–10；模型 `deepseek-v4-flash`；新增真实调用
硬上限 5；每 plan 至多 1 次；retry=0；禁止再次调用 order 1–5；禁止补选/扩大/
重跑原 10-call 命令；禁止读取 Gold/Layer E、计算 P/R。

**Safety**: Gold / Layer E / `.env` 未读；父 frozen plan、B0、trigger、risk、
prompt、canonicalizer、validator、schema、model gate、early-stop 合同、R1–R6
历史产物均未修改；`outputs/development/`、capture、telemetry、predictions、运行
manifest 未提交；P/R = not_computed。

---

## 1. 阶段 A：游标修复验证 + continuation 绑定（fail closed）

- 游标修复（R6 37ab7ef 已含）：frozen-order 游标在每个 selected plan 开始处理时
  统一推进，不再只在成功分支推进；zero-match / canonical-invalid / accepted 后的
  顺序均正确，真正 plan-key 不一致仍 fail closed。已由新增回归测试覆盖。
- 新 `--continuation-plan PATH`（`schema_version=h1_pilot_continuation@1.0.0`）：
  调用前强制验证父 frozen plan hash/keys、prior R6 manifest/capture hash、
  prior telemetry 恰好 order 1–5 各一次、无 order 6–10 先例、continuation 恰好
  order 6–10、与 prior 交集为空、并集恰为父 10 plan、5 个不同 sample、model/
  prompt/B0 hash、risk/repair_fields/reasons、`--max-calls=5`、与
  `--frozen-plan`/`--exclude-plan` 互斥；任一失败 API calls=0 并拒绝。

## 2. 阶段 B：0 API plan-only 证明（只选 order 6–10）

| 项 | 值 |
|---|---|
| 输出目录 | `outputs/development/s28d_r6c1_remaining_plan_check_v1/` |
| selected_plan_count / selected_sample_count | 5 / 5 |
| original orders | `[6,7,8,9,10]` |
| actual API calls / real_api | 0 / false |
| prior called intersection | 空 |
| parent plan coverage | 10/10（并集验证通过） |
| patch proposed / accepted / changed | 0 / 0 / 0 |
| H1 vs B0 | 150 样本逐位一致 |
| 重复运行 | predictions/telemetry/manifest 同路径 byte-identical |

## 3. 阶段 C：唯一一次真实 continuation 调用

命令即任务指定命令（`--continuation-plan ... --allow-llm --model deepseek-v4-flash
--max-calls 5 --inter-call-delay 0.5 --development`），只执行一次，无 `--overwrite`。

| 项 | 值 |
|---|---|
| 输出目录 | `outputs/development/s28d_r6c1_h1_remaining_pilot_v1/` |
| **actual new API calls** | **5** |
| order 1–5 新调用 | **0** |
| order 6–10 新调用 | 5（estg_000232/000285/000302/000414/000716 各 1 次） |
| 未冻结调用 / 重复调用 | 0 / 0 |
| retry | 0 |
| early stop | 否（游标修复生效，无误报） |
| requested/resolved/returned model | 5/5 `deepseek-v4-flash` |
| transport / extraction | 5/5（HTTP 200） / 5/5（ok_message_content） |
| usage tokens | prompt=8000 / completion=1652 / total=9652 |
| manifest SHA-256 | `38421f74a5fc7cf5702b82c36c9abad55070c57a4b71ac8e8d17114d528b2f6a` |
| transport capture SHA-256 | `0e48bcb5b4bf5866c1d1cc1c1fd32cf4ca0f2d578d51e5c8cfd56e5dc2c250ed` |

## 4. order 6–10 逐项脱敏结果

| orig | cont | sample | clause | called | http | extraction | model | usage(p/c/t) | content len | content sha | proposed | cc status | spans(total/valid/rean/zero/amb/contract) | merge | rej codes | eff | chg | changed fields | B0 sha | H1 sha |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 1 | `estg_000232` | `estg_000232.c1` | 是 | 200 | ok_message_content | `deepseek-v4-flash` | 1415/290/1705 | 1120 | `d1f6f0f91ae9` | 1 | reanchored | 2/0/2/0/0/0 | rejected | canonical_invalid,reference_mismatch | 0 | 0 | `–` | `93bf9b83ea3f` | `93bf9b83ea3f` |
| 7 | 2 | `estg_000285` | `estg_000285.c1` | 是 | 200 | ok_message_content | `deepseek-v4-flash` | 1526/350/1876 | 1153 | `05b874d56c48` | 1 | reanchored | 3/1/2/0/0/0 | rejected | canonical_invalid,reference_mismatch | 0 | 0 | `–` | `f11a4aad1c15` | `f11a4aad1c15` |
| 8 | 3 | `estg_000302` | `estg_000302.c1` | 是 | 200 | ok_message_content | `deepseek-v4-flash` | 1506/270/1776 | 915 | `dcf68b4510db` | 1 | reanchored | 2/0/2/0/0/0 | rejected | canonical_invalid,reference_mismatch | 0 | 0 | `–` | `77048709e11b` | `77048709e11b` |
| 9 | 4 | `estg_000414` | `estg_000414.c1` | 是 | 200 | ok_message_content | `deepseek-v4-flash` | 1967/255/2222 | 876 | `e5a283cf44b1` | 1 | reanchored | 2/0/2/0/0/0 | rejected | canonical_invalid,reference_mismatch | 0 | 0 | `–` | `4bd40ec7b73a` | `4bd40ec7b73a` |
| 10 | 5 | `estg_000716` | `estg_000716.c3` | 是 | 200 | ok_message_content | `deepseek-v4-flash` | 1586/487/2073 | 1693 | `62eb609f1f27` | 1 | reanchored | 4/0/4/0/0/0 | accepted | – | 1 | 1 | `modality,actors,actor_action_map` | `379166a3fbaa` | `05099c9697fd` |

## 5. Continuation 离线 replay

`outputs/development/s28d_r6c1_h1_remaining_pilot_replay_v1/`（0 API calls，
使用本次 sanitized capture 全量重放 5 个响应）：

- 每个已调用 plan 的 H1/B0 hash 与真实运行逐位一致；
- accepted / effective / changed / rejection codes 一致；
- coordinate canonicalization 一致；identity fields 一致；
- 聚合计数一致（calls=5、accepted=1、rejected=4、effective=1、changed=1、gate=true）；
- 同路径重复 replay predictions/telemetry/manifest **byte-identical**。

## 6. 完整 10-plan 合并证据（纯离线、fail-closed）

新 `scripts/combine_h1_pilot_runs.py`（受测实现），输出
`outputs/development/s28d_r6_complete_h1_small_pilot_v1/`：

| 检查 | 结果 |
|---|---|
| 两 run 同一 B0 attempts/manifest hash | 通过 |
| prompt/model/父 frozen plan 一致 | 通过 |
| plan key 集合互斥 | 通过（R6 ∩ R6C1 = 空） |
| 前一批恰为 order 1–5 / 后一批恰为 order 6–10 | 通过 |
| 并集恰覆盖父 10 plan | 通过（called keys sha `bb8d73b2…` = 父计划 keys sha） |
| 每 plan 真实调用恰好一次 | 通过（10 plan / 10 调用 / 10 不同 sample） |
| identity 无冲突、无双重修改 | 通过（每 sample 至多被一个 run 修改） |
| 组合 predictions 从同一 B0 构建 | 通过 |
| 聚合 telemetry 保留来源 | 通过（`source_run` 标记：R6=5、R6C1=5、neither=140） |
| hash 可追溯 / 重复合并 byte-identical | 通过（predictions sha `5b953293…`） |

## 7. 完整 10-plan 合并指标（P/R 仍 not_computed）

| 指标 | 值 |
|---|---|
| 总计划数 / 总实际调用数 | 10 / 10 |
| transport / extraction 成功 | 10/10 |
| proposed / accepted / rejected | 10 / 4 / 6 |
| effective / changed / called-but-unchanged | 4 / 4 / 6 |
| H1 != B0 样本数 | 4 |
| effective patch rate | 4/10 = 0.40 |
| coordinate unchanged / reanchored / failed | 0 / 9 / 1 |
| already-valid / reanchored spans | 2 / 19 |
| zero / ambiguous / contract | 1 / 0 / 0 |
| rejection code 分布 | `coordinate_canonicalization_zero_match`=1、`canonical_invalid`=5、`reference_mismatch`=5 |
| changed fields 分布 | modality=4、actors=4、actor_action_map=4 |
| identity violation count | **0** |
| 总 token usage | prompt=15634 / completion=2994 / total=18628 |
| 完整覆盖 10/10 | **是**（status=complete） |

## 8. 下一步判断

完整覆盖达成：10/10 plans called exactly once、identity_violation_count=0。

```text
S2.8D-R7：完整 10-plan Gold-blind 结果审计与受控 P/R 评价解锁准备
```

本轮不读取 Gold、不计算 P/R。
