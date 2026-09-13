# s3_semantic_grounding_v5 (zero API, read-only prediction reuse)

本 revision 从 v2 冻结预测中定位 constraint/exception 失败链，并加入 action-anchor consistency guard：当已解决动作节点的标签强烈匹配非 action 规则字段且不匹配 action 时，锚定在该节点上的 condition/constraint 判定 降级为 unknown，不把信息缺失误判为违规。

## Guard change report

- Changed checks: **2**
- Removed control false alarms: **2**
- Demoted target-paired positives: **0**
- Target-paired Macro-F1 before/after: **0.6737 / 0.6737**
- Pair success before/after: **21 / 21**
- Target-field unknown rate before/after: **0.3375 / 0.3375**
- Legacy control check false positives before/after: **26 / 24**

## Failure chains

- Constraint: **FIXED_BY_PROGRAM_ANCHOR_GUARD** (syn_v2_exception_not_handled_06 control)
- Exception: **CAPABILITY_BOUNDARY_UNFIXABLE_WITH_CURRENT_PROCESS** (syn_v2_exception_not_handled_02 variant)

## Boundary

The guard changes detection behaviour only through a program consistency rule; it does not tune per-sample thresholds or use Gold/expected labels. F1 is not required to increase. The v2 predictions are reused read-only after hash verification. No real API call is made.
