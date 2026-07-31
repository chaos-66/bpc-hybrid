# S2.8D-R3: Fail-closed Unique Exact-Text Coordinate Canonicalization

**Task**: S2.8D-R3 — 把 R2 诊断证明的“文本正确、坐标错误”span 修复逻辑实现为
正式、可复用、fail-closed 的 H1 管线机制。

**起始 commit**: `ef3fe486824fd0491c4deed7361acf0a47cdfea6`
**实现 commit**: 见本报告 `.json` 与 Git log（提交后回填）

**Safety**: 0 real API calls；Gold / Layer E / `.env` 未读；真实 R1 canary 未重跑、
未修改；prompt、validator、canonical schema、B0/trigger/risk/budget 均未改；
P/R = not_computed。

---

## 1. 算法规则（精确，无猜测）

坐标系统：Python/Unicode code point，0-based，end-exclusive，相对于**完整
source_text**。搜索窗口严格限制为 `source_text[clause_span.start:clause_span.end]`。

对每个 proposed span（`modality.evidence[*]`、`actors/actions/conditions/
constraints/exceptions[*]`；relation 字段不处理）：

| 情况 | 条件 | 动作 | 状态 |
|---|---|---|---|
| 1 已正确 | `clause_start <= start <= end <= clause_end` 且 `source_text[start:end] == text` | 不修改 | `unchanged` |
| 2 唯一匹配 | clause 窗口内 exact occurrence == 1 | 只改 start/end | `reanchored` |
| 3 zero match | occurrence == 0 | 整 patch fail closed | `failed` → `coordinate_canonicalization_zero_match` |
| 4 ambiguous | occurrence > 1（含重叠） | 整 patch fail closed | `failed` → `coordinate_canonicalization_ambiguous_match` |
| 5 非法结构 | text 非非空字符串 / start/end 非 int（bool 拒绝）/ start>end / clause_span 非法 / source_text 非 str / 容器非法 | 整 patch fail closed | `failed` → `coordinate_canonicalization_contract_violation` |

匹配为纯 exact：大小写、空格、标点、Unicode 完全一致；无 strip/normalize/
lower/token/模糊/语义匹配。

**原子性**：任一 span 失败 ⇒ 整个 canonicalization 失败，返回原始 envelope，
绝不产生部分修复；后续系统保留原始 B0 prediction。

**只修改 start/end**：canonicalized envelope 是深拷贝；除 start/end 外任何值
（sample_id、clause_id、repair_fields、reason、patches key set、label、text、
id、normalized、relations、absent 标记、列表/字段顺序语义）均不变。测试用
“删除全部 start/end 后 JSON 语义完全一致”验证。

## 2. 接入位置

单一共享路径（不复制逻辑）：

```text
decoder → parser → coordinate canonicalizer → existing apply_patch_envelope
         → existing canonical validator → existing atomic merge
```

接入点在 `_parse_patch_response` 之后、`apply_patch_envelope` 之前，覆盖全部
执行模式：`--offline-patches`、`--offline-replay`、`--offline-transport-replay`、
`--allow-llm`（本轮未运行 `--allow-llm`）。

canonicalization 成功后**仍必须**通过现有 `validate_canonical`；重锚后任何
schema/cross-field/ID/relation/unauthorized/no-semantic-change 错误仍整体拒绝。

## 3. 审计与 telemetry

每个 patch event 新增 `coordinate_canonicalization` 审计：attempted、status
（unchanged/reanchored/failed）、span_count、already_valid_count、
reanchored_count、failed_count、original/canonicalized patch SHA-256、
reason_codes、corrections（每项仅 field_path、proposed/corrected start/end、
text_char/utf8_length、text_sha256、clause_start/end、exact_occurrence_count）。

manifest 新增聚合：attempted_patch_count、unchanged/reanchored/failed_patch_count、
already_valid_span_count、reanchored_span_count、zero_match_count、
ambiguous_match_count、contract_violation_count。

审计中无 span text / source text / prompt text / reasoning / raw response /
凭据。

## 4. 测试

- 新增 `tests/test_h1_span_canonicalizer.py`：26 项（25 项要求全覆盖 + absent
  标记/空列表跳过、非法容器、非法 clause_span 等）。
- 更新 `tests/test_h1_effective_fallback.py` 的 span-mismatch 测试：invented
  text 现在是 canonicalization 的 zero match（整体拒绝、B0 保留、prediction 不
  变），断言改为 `coordinate_canonicalization_zero_match`；其余行为不变。
- 集成测试证明 offline replay 与 offline transport replay 走同一 canonicalizer；
  重锚成功但 relation/ID 错误仍被现有 validator 拒绝（canonical_invalid）；
  未授权字段仍被现有 merge 拒绝（unauthorized_fields）。

## 5. R1 历史 strict 结果（不变）

R1 真实 canary 与 R2 strict replay（无 canonicalizer）：
accepted=0、effective=0、changed=0、gate=false、H1==B0、
`canonical_invalid` + `reference_mismatch`。R1 产物 hash 未变（capture
`f8807841…`、manifest `022d31a1…`）。本任务未重写该历史事实。

## 6. R3 离线 replay（同一真实 capture，canonicalizer 启用）

输出目录：`outputs/development/s28d_r3_coordinate_canonicalization_replay_v1/`
（新目录，未覆盖任何 R1/R2 产物；transport replay 行 SHA-256
`96f8bbdc…`，来自 R2 取证重建的 byte-identical message.content）。

| 项 | 结果 |
|---|---|
| extraction_status | `ok_message_content` |
| proposed | 1 |
| canonicalization status | `reanchored` |
| reanchored_span_count | 3（zero=0, ambiguous=0, contract=0） |
| 修正 | modality.evidence[0] [0,99]→[0,95]；actors[0] [55,99]→[49,95]；conditions[0] [100,211]→[97,207]（均 exact_occurrence_count=1） |
| canonical validator | 通过（schema + cross-field valid） |
| merge | accepted；effective_patch=true |
| changed_fields | actor_action_map / actors / conditions / constraints / modality |
| prediction_changed | 1 |
| h1_non_identity_gate | **true** |
| H1 vs B0 | **H1 != B0**（H1 prediction SHA-256 `5bcf26d7…`，与 R2 counterfactual merged hash 完全一致） |
| identity 字段 | 不变（sample_id/source_id/source_text/clause_id/clause_span） |
| 重放确定性 | 同参数重复运行 manifest/predictions byte-identical |
| manifest SHA-256 | `f2c8c1fd…` |

original patch SHA-256 `e5079e29…`（= R1 manifest 记录的 proposed hash）；
canonicalized patch SHA-256 `8f2842be…`（= R2 counterfactual proposed hash）。
R3 replay 结果与 R2 diagnostic-only counterfactual 逐位一致，证明该机制就是
R2 诊断逻辑的正式实现。

## 7. 结果解释边界

R3 只证明：H1 fallback 现在能接受这次机械性坐标错误；同一 capture 下 H1 不再
与 B0 相同；LLM patch 能产生 effective change。不得声称 P/R 优于 B0、正式评估
完成、模型未来稳定、formal S2.8 解锁、可自动运行 pilot。P/R = not_computed。

## 8. 下一步建议

机制已在离线 replay 中验证；下一步由用户决定是否授权**单次真实 canary
（硬上限 1、0 retry）**，以观察 canonicalizer 在真实模型输出上的行为。真实
canary 需要新的明确授权与新的 experiment_run 事件；未经授权不得调用。
