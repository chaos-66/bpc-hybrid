# S1 P2 target-overlap 审计（2026-08-13 纠错任务）

> 机器可读：`outputs/reports/s1_p2_target_overlap_audit_v1.json`（sha
> `948d268a…`）
> verifier：`scripts/verify_s1_p2_target_overlap_audit.py`（VERIFIED）
> 本审计是**历史事实审计**：不修改任何 P2 资产、不重算指标。
> 历史测试文件绑定：`c704bbc` blob（sha `fbddce03…`）

## 1. 标签重合（对 GDPR-7 的 45 个 activity raw label 实例 / 41 个唯一标签）

### 历史（c704bbc 时的开发测试，13 个 synthetic labels）

| 口径 | 数量 | 清单 |
|---|---|---|
| exact string | **3** | `Communication with data subject`、`Rectify data`、`Retrieve data` |
| Unicode whitespace 折叠 | 3 | 同上 |
| casefold（NFKC） | 3 | 小写形式 |
| punctuation 归一化 | 3 | 同上 |

### 当前（纠错后，13 个 synthetic labels）

| 口径 | 数量 |
|---|---|
| exact / whitespace / casefold / punctuation | **0**（全部不重合） |

## 2. 重合标签的测试期望 vs 人工 Process Gold（历史）

| 重合标签 | 测试期望（actor/action/object） | Gold（actor/action/object） | 三元组 |
|---|---|---|---|
| `Communication with data subject`（gdpr_1 / gdpr_7） | – / Communication / data subject | Data Controller / Communication / data subject | ✗（actor 无断言） |
| `Rectify data`（gdpr_6） | （fixture 存在但无断言） | Data Controller / Rectify / data | ✗ |
| `Retrieve data`（gdpr_7） | Data Controller / Retrieve / data | Data Controller / Retrieve / data | **✓** |

结论：至少一条测试断言（`Retrieve data`）与人工 Gold **三元组完全相同**。

## 3. 动词表覆盖（200 / 200 修正）

- 总条目：**200**；唯一：**200**（旧报告“199 词”已纠正；词表内容未修改）
- Gold action 首词 13 个；词表覆盖 10 个（Add/Check/Collect/Communicate/Handle/Inform/Notify/Rectify/Retrieve/Stop）；未覆盖 3 个（Ask、Communication、limitation）
- 硬编码检查：无完整 activity label、无 process_id/activity_id、无多词条目进入词表
- **覆盖本身≠逐样本硬编码**；但纳入 target-aware 披露

## 4. 时间与读取边界

- Gold 形成/发布：`661f20b`（2026-08-13T19:16:34+08:00）
- P2 lock + synthetic tests：`c704bbc`（2026-08-13T20:47:39+08:00）→ **开发测试发生在 Gold 形成之后**
- 正式评分：`9372a54`（2026-08-13T21:59:02+08:00）
- P2 正式 runner 输入白名单：7 BPMN、membership、冻结 Process Records、P2 config/schema；**运行时未读 Gold**
- 正式评分后 P2 implementation/config 未变（hash 绑定）

## 5. 审计结论

- **历史 P2 开发是 target-aware**（post-Gold reconstruction）
- 不能支持 strict test-blind / developer-blind 声明
- 不能支持独立 held-out generalization 声明
- **runtime Gold isolation 仍成立**（runner 未读 Gold）
- **no post-evaluation tuning 仍成立**（评分后方法未变）
- target overlap 影响 claim strength，**不证明指标计算错误**
- 现有指标可保留为**固定 GDPR-7 描述性组件评价**

## 6. 结构性状态

- `runtime_gold_read=false`
- `target_labels_seen_during_development=true`
- `strict_test_blind=false`；`developer_blind=false`
- `held_out_generalization_claim_allowed=false`
- `implementation_locked_before_scoring=true`；`post_evaluation_tuning=false`
- `exact_reproduction_claim_allowed=false`；`sun_original_implementation_claim_allowed=false`；`stage1_innovation_claim_allowed=false`
- `evaluation_role=formal_descriptive_component_evaluation_on_fixed_GDPR7`
