# SEP-C4 anchor/evidence-scope repaired candidate v2 (v7 eligible consensus)

`s3_semantic_grounding_v7` fixes the committed v6 bug where retrieved
candidates without effective grounding evidence were merged into a
definite violation. Frozen v2 saved candidates/similarities and panel
BPMN are reused. real API=0, no model inference, no similarity recompute.
The committed v6 artifacts are not overwritten.

## Process Record checker-context consistency

- Checker-used compact local context: **80/80** rows identical to the
Stage-1 derived v2 context; mismatches=0.
- Compared fields: nodes / sequence flows / condition / constraint / exception evidence.
- Stage-1 parse contract unchanged.

## Four-type target-paired results (40 pairs / 80 rows, full denominator)

| Type | V7 variant TP/FN_obs/FN_unknown | V7 control TN/FP/unknown | V7 F1 | V6 F1 | V2 F1 | Pair success |
|---|---|---:|---:|---:|---:|---:|
| prohibited_action_present | 10/0/0 | 8/0/2 | 1.0 | 1.0 | 1.0 | 8/10 |
| required_condition_not_enforced | 7/0/3 | 6/1/3 | 0.7778 | 0.9 | 0.9 | 6/10 |
| constraint_violated | 1/0/9 | 1/0/9 | 0.1818 | 0.1818 | 0.3333 | 1/10 |
| exception_not_handled | 3/0/7 | 5/0/5 | 0.4615 | 0.8235 | 0.4615 | 2/10 |

- V7 target-paired macro-F1: **0.6053**
- V6 candidate macro-F1: **0.7263**
- V2 baseline macro-F1: **0.6737**
- V7 pair success: **17/40** (0.425)
- V7 target-field unknown rate: **0.475**
- V7 control target-field FP rate: **0.025**

## Fate of the four v6 exception TPs

| Item | v6 effective_support | V6 outcome/violation | V6 lower action status | V7 outcome/violation | V7 reason |
|---|---|---|---|---|---|
| syn_v2_exception_not_handled_04 | 0 | positive/True | resolved | unknown/None | ambiguous_no_evidence_supported_action_candidate |
| syn_v2_exception_not_handled_07 | 0 | positive/True | resolved | unknown/None | ambiguous_no_evidence_supported_action_candidate |
| syn_v2_exception_not_handled_08 | 0 | positive/True | resolved | unknown/None | ambiguous_no_evidence_supported_action_candidate |
| syn_v2_exception_not_handled_09 | 0 | positive/True | resolved | unknown/None | ambiguous_no_evidence_supported_action_candidate |

All four rows had `effective_support={}` in v6 but were merged into
`not_handled` because every retrieved candidate lacked a handler. v7 sees
no evidence-eligible candidate and returns `unknown`; they are no longer TP.

## TP / unknown / control FP change (v6 -> v7)

- prohibited_action_present: variant TP 10->10; lost []; gained []; variant unknown 0->0; control FP 0->0; control unknown 2->2
- required_condition_not_enforced: variant TP 9->7; lost ['syn_v2_required_condition_06:variant', 'syn_v2_required_condition_07:variant']; gained []; variant unknown 1->3; control FP 1->1; control unknown 0->3
- constraint_violated: variant TP 1->1; lost []; gained []; variant unknown 9->9; control FP 0->0; control unknown 9->9
- exception_not_handled: variant TP 7->3; lost ['syn_v2_exception_not_handled_04:variant', 'syn_v2_exception_not_handled_07:variant', 'syn_v2_exception_not_handled_08:variant', 'syn_v2_exception_not_handled_09:variant']; gained []; variant unknown 3->7; control FP 0->0; control unknown 7->5

## TP / unknown / control FP change (v2 -> v7)

- prohibited_action_present: variant TP 10->10; variant unknown 0->0; control FP 0->0; control unknown 2->2
- required_condition_not_enforced: variant TP 9->7; variant unknown 1->3; control FP 1->1; control unknown 0->3
- constraint_violated: variant TP 2->1; variant unknown 8->9; control FP 0->0; control unknown 8->9
- exception_not_handled: variant TP 3->3; variant unknown 7->7; control FP 0->0; control unknown 1->5

## Row-level changes

- Changed rows (v2 -> v7): **32** / **80**

## Boundary

- When grounding is ambiguous and `effective_support` is empty, definite
  condition/constraint/exception verdicts stay unknown; missing local
  structure in a retrieved candidate is not treated as an anchor fact.
- Evidence-eligible candidates still reach a defined verdict when their
  observed candidate scopes agree; disagreement/incomplete surface stays unknown.
- Unique exact match, resolved single-anchor evidence, unreachable-evidence
  isolation and the prohibited existence check are unchanged.
- Upstream action extraction, abstract constraint semantics, the Stage 2
  validator and the Stage 3 prompt are out of scope this round.
- An F1 drop (if any) withdraws unsupported TPs; it is not a repair failure.
  This candidate does not claim a proven performance improvement.

## Sources

- v2 predictions SHA-256: `b17b859465e6ee5ebbdefcfc7e4ecb93a5b4d58ada5baca6cfd9746e8bdd2092`
- v6 predictions SHA-256: `9877cb7a91f3f77a9091c339c33e110c01a441481200cdf6510393ad82053163`
- panel SHA-256: `6a23adbdbc0d8930ff2a33411c52fed7fbbf581fdd101f830c29b2e3373e2e81`
- implementation: `{'module': 'src/bpc_hybrid/s3_semantic_grounding_v7.py', 'module_sha256': 'a96563d390913691779a1622ce6ff78bc8654b0ec91f9a16dc4de4a21deb3e44', 'base_module': 'src/bpc_hybrid/s3_semantic_grounding_v6.py', 'base_module_sha256': '48f3f675145387b3351e3566a524475869814d2b9c09100755cd813205882a44', 'runner': 'scripts/run_sep_c4_action_anchor_scope_v2.py', 'runner_sha256': '6f772701883963a5e235d490c5244a4e53538c9687d102f9057d4dbf94ec75d5', 'tests': 'tests/test_s3_semantic_grounding_v7.py', 'tests_sha256': '76e5f23ce94be442fd41981e6c1f143e55e9a571af401a69e751017c6e9dbee8'}`
