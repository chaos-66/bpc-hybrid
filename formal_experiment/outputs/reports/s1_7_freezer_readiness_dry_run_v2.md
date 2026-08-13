# S1.7 冻结 readiness / 授权 dry-run 包 v2（2026-08-13 纠错版）

> 状态：**`dry_run_not_applied`**；目标 `S1.7 ready_for_user_freeze_authorization`
> 机器可读：`outputs/reports/s1_7_freezer_readiness_dry_run_v2.json`（sha
> `be5d4b80…`）
> verifier：`scripts/verify_s1_7_freezer_dry_run_v2.py`（VERIFIED）
> **v1 已标记 superseded**（`superseded_due_to_target_fixture_overlap_and_formal_path_semantics`），保留为历史 provenance。

## 1. 本版纠错绑定

- **target-overlap audit**（历史 3 条重合、当前 0 条）已绑定
- **claim correction v2**（target-aware 结构化状态）已绑定
- **200/200 词表**修正已绑定
- **正式 v2 路径**（`data/predictions/stage1_formal_v1/`、
  `data/results/stage1_formal_v1/`、`stage1_formal_evaluation_v2.*`）为权威入口；
  旧 development 路径为 historical provenance
- **P2 config/implementation/runtime 未变**（hash 逐位）
- **predictions 未变**（`79a9b2c1…`，权威副本逐位一致）
- **metrics 未变**（数值主体 canonical `19002346…`）
- **Stage 1 Gold 未变**（`f33aa857…`）

## 2. 独立 verifier 实际运行（7/7 全过）

adjudication 链 / Process Gold / P2 lock / predictions / evaluation capsule /
**overlap audit** / **formal v2**——全部从磁盘重算并真实运行。

## 3. Pipeline 状态（诚实）

S1.3 verified（target-aware post-Gold reconstruction，非 strict blind）；
S1.5 verified（Gold 不变）；S1.6 verified（**fixed-GDPR7 描述性组件评价**，
无 held-out 泛化声明）；S1.7 **ready_for_user_freeze_authorization**（未冻结）；
S3.7 未启动（Oracle 仅经 Stage 3 独立门禁）。

## 4. 授权句（**仅供用户选择；未被应用**）

> I acknowledge that the P2 method was developed AFTER the Stage 1 Process
> Gold was formed and that at least three target activity labels
> ("Communication with data subject", "Rectify data", "Retrieve data")
> entered the development test fixtures, with at least one asserted triple
> matching the human Gold; I acknowledge that the S1.6 metrics are a
> fixed-GDPR-7 formal descriptive component evaluation and NOT held-out
> generalization evidence. I authorize the formal S1.7 freeze of the
> existing, non-tuned-after-evaluation P2 method (locked config,
> implementation and offline runtime), the existing locked P0/P1/P2
> predictions and the ORIGINAL metrics, together with the frozen Stage 1
> Process Gold and the verified evaluation capsule. The freeze shall NOT
> modify P2, shall NOT recompute selective results, shall NOT add any LLM/API
> call, and shall NOT modify the Stage 2/Stage 3 Gold or the experiment
> contract. The formal Stage 3 Oracle is NOT auto-authorized by this packet
> and advances only through its own independent gates.
