# B0/D1/H1 Formal Readiness v2 (zero-API audit)

- formal input v2: 150 records (sha256 52a73aa1109970b6...)
- Stage 2 Gold: sha256 c31a514a6b58b640...

## sun_rule_only (formal_candidate_v1 (run by run_estg150_b0_formal.py))
- binding_ok: True
- zero-API re-evaluation allowed: True
- verdict: zero-API by construction; formal candidate run required
- [PASS] B0 method is zero-API (llm_used=false)
- [PASS] B0 formal candidate runner exists
- [PASS] B0 historical attempts 150 rows 150 rows (development provenance only)
- [PASS] B0 historical ids == formal v2 ids
- [PASS] B0 history is development-only (not formal)

## direct_llm (s27_d1_v6_r3_clean_rerun_150_hist56d_v1)
- binding_ok: True
- zero-API re-evaluation allowed: True
- verdict: bound_to_formal_input_v2; zero-API candidate re-evaluation allowed
- [PASS] D1 snapshot exists (input/predictions/manifest)
- [PASS] D1 predictions 150 rows 150 rows
- [PASS] D1 prediction ids == formal input v2 ids
- [PASS] D1 predictions schema-valid 150/150
- [PASS] D1 input text == formal v2 text (150/150) 0 mismatches
- [PASS] D1 prompt hash == registry lock registry=3aa64877cd4c4dae
- [PASS] D1 prompt file == registry lock disk=3aa64877cd4c4dae
- [PASS] D1 run manifest prompt == lock manifest=3aa64877cd4c4dae
- [PASS] D1 model == deepseek-v4-pro deepseek-v4-pro
- [PASS] D1 sampling t0/top1/4096 {'temperature': 0.0, 'top_p': 1.0, 'seed': 'unsupported_or_omitted', 'max_tokens': 4096}
- [PASS] D1 no gold read by runner
- [PASS] D1 evaluator config == registry lock disk=352113b568c6075c

## sun_llm_fallback (s28d_h1_150_v4pro_v1)
- binding_ok: True
- zero-API re-evaluation allowed: True
- verdict: bound_to_formal_input_v2; zero-API candidate re-evaluation allowed
- [PASS] H1 snapshot exists (predictions/manifest)
- [PASS] H1 predictions 150 rows 150 rows
- [PASS] H1 prediction ids == formal input v2 ids
- [PASS] H1 predictions schema-valid 150/150
- [PASS] H1 source_text == formal v2 text (150/150) 0 mismatches
- [PASS] H1 prompt hash == locked prompt manifest=00fe02996914e17f
- [PASS] H1 prompt file == locked prompt disk=00fe02996914e17f
- [PASS] H1 model == deepseek-v4-pro deepseek-v4-pro
- [PASS] H1 sampling t0/top1 {'temperature': 0.0, 'top_p': 1.0, 'seed': 'unsupported_or_omitted', 'max_tokens': 4096}
- [PASS] H1 b0 binding verified

## Summary
- D1 historical predictions reusable zero-API: True
- H1 historical predictions reusable zero-API: True
- new LLM API call required: False
