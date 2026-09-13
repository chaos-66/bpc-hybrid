# s3_semantic_grounding_v4 (offline implementation evidence)

本 revision 修复 LLM 结果的逐字段应用、匿名活动 ID 反向映射、动作解决后的局部检查重跑、
以及证据与目标动作范围的程序化绑定。全部为零 API 的离线构造验证。

## Candidate pack (v4)

- Fallback items: **20**
- All advertised evidence ids visible in payload: **True**
- Semantic rule fields preserved: **True**

## Offline chain cases

- Cases passed: **5/5**
- Status: **OFFLINE_IMPLEMENTATION_EVIDENCE_NOT_LLM_PERFORMANCE**

| Case | Expectation |
|---|---|
| action_and_condition_progress_ambiguous_constraint_abstains | one ambiguous field does not block the resolved field |
| action_id_reversed_and_prohibited_check_updated | action resolution updates the consuming prohibited_action_present check |
| negative_claim_requires_closed_program_scope | an absence claim without complete program scope keeps abstention |
| irrelevant_or_hallucinated_evidence_rejected | high confidence is not enough without bound evidence |
| truncated_context_never_advertises_cut_off_evidence | allowed evidence ids are derived after truncation |

## Boundary

Constructed cases prove input -> semantic response -> anonymous-id reverse mapping -> program node/evidence binding -> local check re-execution -> decision wiring.  They do not establish real LLM accuracy or improvement.
