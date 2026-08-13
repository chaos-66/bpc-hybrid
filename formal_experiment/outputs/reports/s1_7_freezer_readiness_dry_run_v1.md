# S1.7 冻结 readiness / 授权 dry-run 包（2026-08-13）

> 状态：**`dry_run_not_applied`**。本包只读呈现 S1.7 正式冻结的授权前证据与
> 边界。**未应用任何 freeze、未自我授权**；文末授权句仅供用户选择。
> 机器可读：`outputs/reports/s1_7_freezer_readiness_dry_run_v1.json`
> verifier：`scripts/verify_s1_7_freezer_dry_run.py`

## 1. Pipeline 状态（诚实）

| 阶段 | 状态 |
|---|---|
| S1.3 | **verified**（P0/P1/P2 锁定；P2=Sun/Leopold-style 方法级独立重建；正式推断+一次性评价完成） |
| S1.5 | **verified**（7/7 人工裁决 → 用户授权 → 正式 Process Gold 冻结发布） |
| S1.6 | **verified**（P0/P1/P2 一次性正式评价 capsule，独立 verifier 通过） |
| S1.7 | **`ready_for_user_freeze_authorization`（未冻结、未应用）** |
| S3.7 | 未启动（正式 Oracle 须经 Stage 3 独立门禁，本包**不自动授权**） |

## 2. 冻结范围（仅已验证资产）

- 7 BPMN source + membership（输入层；7 BPMN / 45 activities / 135 label fields，payload `e88caf81…`）
- canonical Process Record schema + 冻结 records
- P0/P1/P2 方法（P2 config/implementation/offline runtime 锁定）
- P0/P1/P2 正式 predictions（锁定、Gold-blind）
- Stage 1 Process Gold（`data/gold/stage1`，已冻结发布）
- S1.6 评价结果 + capsule（一次性、未调优）

## 3. 独立 verifier 真实运行结果（5/5 全过）

| verifier | 结果 |
|---|---|
| `verify_stage1_human_adjudication.py`（七批链） | VERIFIED |
| `verify_stage1_process_gold.py`（Gold 发布） | VERIFIED |
| `verify_stage1_p2.py`（P2 锁定） | VERIFIED |
| `verify_stage1_predictions.py`（predictions/Gold 隔离） | VERIFIED |
| `verify_stage1_formal_evaluation.py`（评价 capsule） | VERIFIED |

全部 hash 在包内记录并从磁盘重算一致（见 JSON `hashes` 节）。

## 4. 一致性声明

- 新增 LLM/API 调用：**0**
- P2 在锁定后**未改变**（config+implementation hash 绑定）
- Gold **未用于**方法调优
- Stage 3 **未启动**
- 限制声明全部存在（candidate-assisted Gold、无显著性推断、post-Gold lock、不与 Sun 绝对分数硬比较）

## 5. 回滚 / fail-closed

- 冻结前：本包 hash + git 历史即备份
- 冻结应用：必须用户授权句；**无自我应用**
- 冻结后：**先独立验证**，任何不一致 fail closed

## 6. Stage 3 边界

S1.7 冻结仅解锁 Stage 3 正式路径的**前置条件**；正式 Stage 3 Oracle 仍须
按其独立门禁（S2.13、S3.x formal 要求）推进，本包**不自动授权**。

## 7. 授权句（**仅供用户选择；未被应用**）

> I authorize the formal S1.7 freeze of the already-verified Stage 1 assets:
> the frozen seven-BPMN membership and source hashes, the canonical Process
> Record schema and records, the Sun/Leopold-style P2 method (locked config,
> implementation and offline runtime), the P0/P1/P2 formal predictions, the
> frozen Stage 1 Process Gold, the S1.6 one-shot evaluation results and the
> evaluation capsule. The freeze shall NOT modify P2 or recompute selective
> results, shall NOT add any LLM/API call, and shall NOT modify the Stage
> 2/Stage 3 Gold or the experiment contract. After the S1.7 freeze, the
> formal Stage 3 Oracle still advances only through its own independent
> gates.
