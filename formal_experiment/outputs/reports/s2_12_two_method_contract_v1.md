# S2.12 Two-Method Execution Contract (SEP-C2)

- status: **partial_two_method_contract_pending_direct_llm**
- active methods: `sun_rule_only`, `direct_llm`
- cancelled: `sun_llm_fallback` (Rules+LLM-Repair); 27 F-1/F-2/F-3 calls removed and not reassignable
- remaining Direct calls: S2.12 36 + GDPR 74 = **110**; calls made by this contract build: **0**
- S2.12 two-method evidence complete: **False**
- S2.13 freeze checkpoint complete: **False** (eligible: **False**)

## Comparison evidence

- status: `pending_direct_llm`
- two-method comparison complete: **False**
- Direct-LLM dependency on the cancelled repair ledger/results: **false**
- `sun_rule_only`: verified=True, input_binding_ok=True, all_36_rows=True, metrics_valid=True
- `direct_llm`: verified=False, input_binding_ok=False, all_36_rows=False, metrics_valid=False
  - failed checks: all files exist
- blockers: direct_llm_evaluation_missing_or_not_complete

## Remaining real evidence

- S2.12 Direct-LLM D-CAL/D-REST real responses (36 calls; no fake substitution)
- S2.12 Direct-LLM finalized prediction capsule at data/predictions/s2_12_direct_llm_v1
- S2.12 Direct-LLM evaluation at data/results/s2_12_direct_llm_v1/evaluation.json
- S2.12 two-method Rules-Only vs Direct-LLM comparison
- GDPR-7 Direct-LLM real 74-call capsule/promotion (fake v1 74 rows excluded)
- successor two-method external-send authorization and automatic approval (only if remaining calls reveal a new external-send blocker)

## Boundary

This contract and its evidence are implementation/readiness work only. No complete real S2.12 Direct-LLM or GDPR API result is recorded here; S2.12 and S2.13 are not complete. The cancelled Rules+LLM-Repair arm is not a dependency and must not be restarted.
