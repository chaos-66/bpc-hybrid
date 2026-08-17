# S2.13 → S3.7 Transition Readiness Ledger v2

**Schema**: `s2_13_s3_7_transition_readiness@5.0.0`
**Report ID**: `s2_13_s3_7_transition_readiness_v5`

## Determinism

Every state judgment in this report is re-derived from current on-disk assets, manifests, hashes, or executed independent verifiers; no hardcoded existence conclusions and no wall-clock timestamps. v2 added the three-state Gold-Rule-Record probe, exact in-memory reconstruction of the manifest and the export index (no entry-level iteration that could miss missing or extra entries), and the strict non-JSON verifier verdict; v3/v4 carry those guarantees forward. v4 derives the S2.11 adjudication workload from the closed 40/4/36 review population (blank pack) instead of the 29-candidate run, and reports the S2.12 execution readiness (frozen plan, synthetic runner/evaluator readiness, zero-call API budget dry-run). v5 supersedes v4's S2.11 judgment with the CANONICAL v2 model (unresolved/absent/present, modality label + byte-verified evidence spans, multi-span fields, actor-action map, order relations; proposal v1 superseded/not approvable; proposal v2 unadjudicated; importer v2 dry-run blocked=0) and the S2.12 judgment with the formal-contract-aligned evaluator v2 (parity verified), plan/readiness v2 and API readiness v2 (cost_cap_unresolved; no final authorization sentence). Rebuilding on identical inputs produces byte-identical outputs; existing outputs with different bytes are refused.

## Superseded current-state judgments (historical files preserved unmodified)

- `outputs/reports/s2_13_stage2_freeze_gap_capsule.json` (sha256 `eb934910c2e0…`): 2026-08-11 current-state judgment predates the S1.7 freeze (2026-08-13) and still lists S1.7 as blocked ('true Gold Process Records'); the remaining-items list is superseded by this v2 ledger while the historical file stays unmodified.
- `outputs/reports/s2_13_stage2_freeze_gap_capsule.md` (sha256 `ca369600d594…`): 2026-08-11 Markdown rendering of the same superseded gap capsule; preserved unmodified as historical provenance.
- `outputs/reports/s3_7_oracle_readiness_v2.json` (sha256 `0e79232bb17b…`): 2026-08-11 current-state judgment is stale: it hardcodes gold_process_records.exist=false with 'S1.5 human Process Gold not started', which the 2026-08-13 Stage 1 Process Gold publication and S1.7 freeze invalidated; superseded by this v2 ledger, historical content preserved.
- `outputs/reports/s37_oracle_readiness_v1.json` (sha256 `7bd3e8dec72b…`): 2026-08-09 current-state judgment is stale: 'true Gold Process Records not present' and the S1.7 gap no longer hold after 2026-08-13; its Gold-Rule-Records absence finding remains true and is carried forward; superseded by this v2 ledger, historical content preserved.
- `outputs/reports/formal_benchmark_release_v2.manifest.json` (sha256 `8b3cbd2e6081…`): Its publication-time exclusions block ('gold_process_records DO NOT EXIST', 'gold_rule_records DO NOT EXIST') is a historical snapshot: the gold_process_records exclusion is now stale (Stage 1 Process Gold published 2026-08-13) while the gold_rule_records exclusion remains true; the release manifest file itself stays unmodified.
- `scripts/build_s1_5_s3_7_readiness_v1.py` (sha256 `dc474b80485d…`): Historical builder that hardcodes the pre-freeze conclusion 'true Gold Process Records DO NOT EXIST (S1.5 human Process Gold not started)'; preserved unmodified as provenance; its current-state output logic is superseded by this deterministic v2 builder.
- `scripts/build_s3_7_oracle_readiness.py` (sha256 `71881cb446e1…`): Historical builder for s37_oracle_readiness_v1.json that hardcodes 'true Gold Process Records ... NOT present'; preserved unmodified as provenance; its current-state output logic is superseded by this deterministic v2 builder.
- `configs/schemas/s2_13_s3_7_transition_readiness.schema.json` (sha256 `df270ee8ee27…`): v1 schema; kept byte-exact. v2 supersedes v1's verifier-completeness guarantees (v1 schema cannot express the three-state Gold-Rule-Record probe, the exact manifest/export reconstruction checks, or the strict verifier verdict).
- `scripts/build_s2_13_s3_7_transition_readiness_v1.py` (sha256 `38b9d2f9c2e9…`): v1 builder; kept byte-exact. Its Gold-Rule-Record probe computed candidates but unconditionally returned exist=false, its manifest and export checks only iterated existing entries, and its non-JSON verifier verdict accepted the bare 'VERIFIED' substring (which 'NOT VERIFIED' also contains); these v1 fail-closed gaps are superseded by the v2 builder.
- `scripts/verify_s2_13_s3_7_transition_readiness_v1.py` (sha256 `5ee35fa837c0…`): v1 verifier; kept byte-exact. Its manifest/export checks only re-verified entries already present in the files (missing or empty maps escaped), so v2 supersedes that completeness guarantee.
- `tests/test_s2_13_s3_7_transition_readiness_v1.py` (sha256 `f85c0bcf0e00…`): v1 focused tests; kept byte-exact. v2 adds the three-state Gold-Rule-Record candidate, exact manifest/export reconstruction and strict verdict negative cases.
- `outputs/reports/s2_13_s3_7_transition_readiness_v1.json` (sha256 `10913862225b…`): v1 transition ledger report; its current-state conclusions remain basically correct and are carried forward by v2, while its verifier-completeness / fail-closed guarantees are superseded by v2; the file stays byte-exact.
- `outputs/reports/s2_13_s3_7_transition_readiness_v1.md` (sha256 `589fc8cee52c…`): v1 Markdown rendering; preserved byte-exact as historical provenance; the current-state report is superseded by the v2 report.
- `outputs/reports/s2_13_s3_7_transition_readiness_v1.manifest.json` (sha256 `d399e2c9f98d…`): v1 manifest; preserved byte-exact; v2's manifest is independently re-constructed and compared exactly (v1 manifest structure is not modified).
- `outputs/reports/s2_13_s3_7_transition_readiness_v1_export_index.json` (sha256 `37289ac54f6f…`): v1 export index; preserved byte-exact; v2's export index is exactly re-constructed from disk bytes and compared (no entry-level iteration that could miss missing or extra entries).
- `configs/schemas/s2_13_s3_7_transition_readiness_v2.schema.json` (sha256 `2b0d9418e748…`): v2 schema; kept byte-exact (historical lifecycle semantics).
- `scripts/build_s2_13_s3_7_transition_readiness_v2.py` (sha256 `c20c8a1f198a…`): v2 builder; kept byte-exact; its S2.11 current-state judgment (blocked on authorization) is superseded by v3.
- `scripts/verify_s2_13_s3_7_transition_readiness_v2.py` (sha256 `b9639016634a…`): v2 verifier; kept byte-exact; its active-verification role is superseded by v3.
- `tests/test_s2_13_s3_7_transition_readiness_v2.py` (sha256 `b39b8fe3b2da…`): v2 pytest file: CORRECTED lifecycle test semantics only (v3); the v2 core assets are untouched.
- `outputs/reports/s2_13_s3_7_transition_readiness_v2.json` (sha256 `6fca5c03349d…`): v2 transition ledger report; byte-exact historical provenance; its S2.11=blocked judgment is superseded by v3.
- `outputs/reports/s2_13_s3_7_transition_readiness_v2.md` (sha256 `7f598664d732…`): v2 Markdown rendering; byte-exact historical provenance.
- `outputs/reports/s2_13_s3_7_transition_readiness_v2.manifest.json` (sha256 `d86494ffd03a…`): v2 manifest; byte-exact historical provenance.
- `outputs/reports/s2_13_s3_7_transition_readiness_v2_export_index.json` (sha256 `71b418a958e6…`): v2 export index; byte-exact historical provenance.
- `configs/schemas/s2_13_s3_7_transition_readiness_v3.schema.json` (sha256 `ed823a755439…`): v3 schema; kept byte-exact (historical lifecycle semantics).
- `scripts/build_s2_13_s3_7_transition_readiness_v3.py` (sha256 `f412eaf553b5…`): v3 builder; kept byte-exact; its S2.11/S2.12 current-state judgments are superseded by v4.
- `scripts/verify_s2_13_s3_7_transition_readiness_v3.py` (sha256 `d9f9094f44b2…`): v3 verifier; kept byte-exact; its active-verification role is superseded by v4.
- `tests/test_s2_13_s3_7_transition_readiness_v3.py` (sha256 `d397735df92d…`): v3 pytest file: lifecycle test semantics only (v4); the v3 core assets are untouched.
- `outputs/reports/s2_13_s3_7_transition_readiness_v3.json` (sha256 `496b5e142f8b…`): v3 transition ledger report; byte-exact historical provenance; its S2.11 workload (29-candidate run) and S2.12 retrospective-only judgments are superseded by v4.
- `outputs/reports/s2_13_s3_7_transition_readiness_v3.md` (sha256 `f50b31bf76f9…`): v3 Markdown rendering; byte-exact historical provenance.
- `outputs/reports/s2_13_s3_7_transition_readiness_v3.manifest.json` (sha256 `dab6a0440974…`): v3 manifest; byte-exact historical provenance.
- `outputs/reports/s2_13_s3_7_transition_readiness_v3_export_index.json` (sha256 `945f12e89136…`): v3 export index; byte-exact historical provenance.
- `configs/schemas/s2_13_s3_7_transition_readiness_v4.schema.json` (sha256 `5ed63a9cb2e0…`): v4 schema; kept byte-exact (historical lifecycle semantics).
- `scripts/build_s2_13_s3_7_transition_readiness_v4.py` (sha256 `7b3c88bec031…`): v4 builder; kept byte-exact; its S2.11/S2.12 current-state judgments are superseded by v5.
- `scripts/verify_s2_13_s3_7_transition_readiness_v4.py` (sha256 `92460b61d7de…`): v4 verifier; kept byte-exact; its active-verification role is superseded by v5.
- `tests/test_s2_13_s3_7_transition_readiness_v4.py` (sha256 `fff583d99775…`): v4 pytest file: lifecycle test semantics only (v5); the v4 core assets are untouched.
- `outputs/reports/s2_13_s3_7_transition_readiness_v4.json` (sha256 `57a2153cfee1…`): v4 transition ledger report; byte-exact historical provenance; its S2.11 (v1 proposals) and S2.12 (v1 evaluator) judgments are superseded by v5.
- `outputs/reports/s2_13_s3_7_transition_readiness_v4.md` (sha256 `6468e83c7aee…`): v4 Markdown rendering; byte-exact historical provenance.
- `outputs/reports/s2_13_s3_7_transition_readiness_v4.manifest.json` (sha256 `a22be0eeacc7…`): v4 manifest; byte-exact historical provenance.
- `outputs/reports/s2_13_s3_7_transition_readiness_v4_export_index.json` (sha256 `e5a001170e09…`): v4 export index; byte-exact historical provenance.

## Dependency matrix

### Stage 1

- **S1.5 = verified** — Stage 1 Process Gold frozen and published (user-authorized 2026-08-13; 7/7 records, 135/135 label fields, 7/7 structure decisions); independent verifier scripts/verify_stage1_process_gold.py VERIFIED.
  - evidence [disk_asset]: `data/gold/stage1/process_records/stage1_process_gold_v1.json`, sha256 `f33aa857a079…`
  - evidence [manifest]: `data/gold/stage1/manifest.json`, sha256 `1885dad26f43…`
  - evidence [manifest]: `outputs/reports/s1_5_process_gold_freeze_authorization_v1.manifest.json`, sha256 `4b97762cfe3c…`
  - evidence [independent_verifier]: `scripts/verify_stage1_process_gold.py`, sha256 `26deb38f9b4b…`
- **S1.6 = verified** — Fixed-GDPR-7 formal descriptive component evaluation (target-aware claim: post-Gold development, strict_test_blind=false, no held-out generalization claim); P2 config/implementation/runtime, predictions and ORIGINAL metrics byte-unchanged.
  - evidence [disk_asset]: `data/predictions/stage1_formal_v1/formal_predictions_v1.json`, sha256 `79a9b2c17185…`
  - evidence [disk_asset]: `data/results/stage1_formal_v1/stage1_formal_evaluation_v1.json`, sha256 `a072db39b371…`
  - evidence [disk_asset]: `outputs/reports/stage1_formal_evaluation_v2.json`, sha256 `954122d4ed89…`
  - evidence [manifest]: `outputs/reports/stage1_formal_evaluation_v2.manifest.json`, sha256 `0d7736f81a3c…`
- **S1.7 = frozen** — Formal Stage 1 freeze APPLIED (user-authorized 2026-08-13): non-tuned P2 method, existing P0/P1/P2 predictions, ORIGINAL metrics, Stage 1 Process Gold and the verified evaluation capsule are frozen; zero LLM/API; the freeze does NOT auto-authorize the Stage 3 Oracle.
  - evidence [manifest]: `outputs/reports/s1_7_freezer_authorization_v1.manifest.json`, sha256 `7712176c877c…`
  - evidence [disk_asset]: `outputs/reports/s1_7_freezer_readiness_dry_run_v2.json`, sha256 `be5d4b80d807…`
  - evidence [independent_verifier]: `scripts/verify_s1_7_freezer_authorization.py`, sha256 `e7fb0005e4ed…`

### Stage 2

- **S2.10 = verified** — Three-method formal capsules, hash-consistent shared comparison capsule and the formal three-method comparison report are published and independently verified (authorized G0.4 evaluation views; new LLM calls 0).
  - evidence [disk_asset]: `data/predictions/b0_formal_arm_v1/predictions.json`, sha256 `fa94991d246d…`
  - evidence [disk_asset]: `data/results/b0_formal_arm_v1/evaluation_coarse.json`, sha256 `abd2b7972fe5…`
  - evidence [manifest]: `outputs/reports/b0_formal_arm_v1.manifest.json`, sha256 `095a839fe7a9…`
  - evidence [independent_verifier]: `outputs/reports/verify_b0_formal_arm_v1.py`, sha256 `01e20bd01173…`
  - evidence [disk_asset]: `data/predictions/direct_llm_formal_arm_v1/predictions.json`, sha256 `bbadb6834572…`
  - evidence [disk_asset]: `data/results/direct_llm_formal_arm_v1/evaluation_coarse.json`, sha256 `471447b0494d…`
  - evidence [manifest]: `outputs/reports/direct_llm_formal_arm_v1.manifest.json`, sha256 `f0f86318259d…`
  - evidence [independent_verifier]: `outputs/reports/verify_direct_llm_formal_arm_v1.py`, sha256 `e48bba8919e8…`
  - evidence [disk_asset]: `data/predictions/sun_llm_fallback_formal_arm_v1/predictions.json`, sha256 `65286d86ddb9…`
  - evidence [disk_asset]: `data/results/sun_llm_fallback_formal_arm_v1/evaluation_coarse.json`, sha256 `31e7afbb0139…`
  - evidence [manifest]: `outputs/reports/sun_llm_fallback_formal_arm_v1.manifest.json`, sha256 `0b5e32852028…`
  - evidence [independent_verifier]: `outputs/reports/verify_sun_llm_fallback_formal_arm_v1.py`, sha256 `932d13273ee5…`
  - evidence [disk_asset]: `outputs/reports/stage2_formal_three_method_comparison_v1.json`, sha256 `c9d76544a36c…`
  - evidence [manifest]: `outputs/reports/stage2_formal_three_method_comparison_v1.manifest.json`, sha256 `dc41eb4bee6b…`
  - evidence [independent_verifier]: `outputs/reports/verify_stage2_formal_comparison_v1.py`, sha256 `22c23331ad68…`
- **S2.11 = in_progress_human_adjudication** — Complex legal corpus ACTIVATED under the user-authorized local read-only non-redistributive containment policy: Checkpoint A applied G1/G2/G3/G4/G6 and froze G0.5; Checkpoint B generated candidates and opened the blank review surface; Checkpoint C closed the review population to 40/4/36 (29 available / 7 unavailable); Checkpoint E1 established the CANONICAL v2 model (unresolved/absent/present, modality label + byte-verified evidence spans, multi-span fields, actor-action map, order relations) with 36 re-reviewed offline proposals (deepseek_offline_proposal_v2; human_approved=false, gold=false, reviewer never the user; proposal v1 declared superseded and NOT approvable). artifact license remains unknown (never claimed verified); raw third-party text is never committed.
  - blocker: 36 review items require ONE user content confirmation bound to the proposal v2 SHA (canonical v2 model; importer v2 dry-run: blocked=0 / unresolved=0 / adjudicable=36; reviewer only from the confirmation event)
  - blocker: 7 of the 36 review items carry no candidate (stable error codes in the blank pack); 11 records quarantined overall (see the candidate run report)
  - evidence [disk_asset]: `outputs/reports/s2_11_candidate_run_v1.json`, sha256 `5fe8225f6be5…`
  - evidence [disk_asset]: `outputs/reports/s2_11_g5_review_surface_v1.json`, sha256 `571ba7ae3c39…`
  - evidence [disk_asset]: `data/development/human_review/s2_11_blank_review_v2.json`, sha256 `ddf9b3cf3bd0…`
  - evidence [disk_asset]: `data/development/human_review/s2_11_review_decisions_v2.json`, sha256 `75d593120abf…`
  - evidence [disk_asset]: `outputs/reports/s2_11_corpus_membership_v1.json`, sha256 `a63c50ea3164…`
  - evidence [disk_asset]: `outputs/reports/s2_11_proposal_report_v2.json`, sha256 `5f596d54391e…`
  - evidence [disk_asset]: `outputs/reports/s2_11_batch_import_dry_run_v2.json`, sha256 `1abf220b9507…`
  - evidence [derivation]: `derived: S2.11 = in_progress_human_adjudication from the canonical v2 blank pack population (36 = 29 + 7), the unadjudicated proposal v2 and the importer v2 dry-run (blocked=0); no Gold created`
- **S2.12 = partial** — Execution-ready v2 (Checkpoint E3): the S2.12 execution plan v2 is FROZEN (pre-registered G0.5 L1/L2/L3 stratification; supersedes the v1 plan whose evaluator/Gold-shape contract was corrected); the stratified evaluator v2 reuses the Stage 2 FORMAL contract (modality label accuracy/macro-F1/per-class + five-field Sun literal-overlap span P/R/F1) with an in-process parity check against the formal evaluator; API readiness v2 derives exact model ids (deepseek-v4-pro both arms), call bounds (36/72/108), output token cap 4096, input cap unresolved, cost_cap_unresolved - NO final authorization sentence is issued; the REAL run stays blocked on the user S2.11 adjudication (36/36) and the API authorization.
  - evidence [disk_asset]: `outputs/reports/s2_12_formal_descriptive_error_analysis_v1.json`, sha256 `9f6c734002fd…`
  - evidence [manifest]: `outputs/reports/s2_12_formal_descriptive_error_analysis_v1.manifest.json`, sha256 `89b3f1209c19…`
  - evidence [disk_asset]: `configs/s2_12_execution_plan_v2.json`, sha256 `0fde9dec2bed…`
  - evidence [disk_asset]: `outputs/reports/s2_12_execution_plan_v2.json`, sha256 `7130f9bd4ec2…`
  - evidence [disk_asset]: `outputs/reports/s2_12_execution_readiness_v2.json`, sha256 `38be851dc25a…`
  - evidence [disk_asset]: `outputs/reports/s2_12_api_readiness_v2.json`, sha256 `d9c3c5e24ec9…`
  - evidence [independent_verifier]: `scripts/verify_s2_12_execution_ready_v2.py`, sha256 `f908572ef8e3…`
  - evidence [derivation]: `derived: S2.12 = partial + execution-ready v2 from the frozen plan v2 (status=frozen, supersedes_v1), the readiness v2 (real_run_refused, gates pending, parity passed) and the executed independent S2.12 verifier v2`
- **S2.13 = blocked** — Stage 2 freeze NOT complete. DoD unchanged (S2.1-S2.12 full DoD); NOT decomposed into new formal tasks and NOT modified this round; final_experiment_ready=true does NOT complete S2.13.
  - blocker: S2.11 in_progress_human_adjudication (36 review items pending the ONE user confirmation bound to the proposal v2 SHA)
  - blocker: S2.12 full DoD not met (execution-ready v2 but the real stratified run is blocked on the user adjudication and the API authorization)
  - evidence [derivation]: `derived: S2.11 in_progress_human_adjudication AND S2.12 partial -> S2.13 blocked; Stage 2 freeze DoD unchanged this round (see this round's change event)`
  - evidence [disk_asset]: `outputs/reports/s2_13_stage2_freeze_gap_capsule.json`, sha256 `eb934910c2e0…`
  - evidence [disk_asset]: `outputs/reports/s2_11_license_adapter_readiness_v2.json`, sha256 `8d271f59e2c6…`

### Stage 3

- **S3.2 = verified** — 25 matching decision Gold frozen and published (data/gold/stage3/stage3_matching_gold_v1.json); these relevance decisions are NOT Gold Rule Records.
  - evidence [disk_asset]: `data/gold/stage3/stage3_matching_gold_v1.json`, sha256 `55dffbcaf7d6…`
  - evidence [disk_asset]: `data/development/human_review/stage3_gold_annotation_human_correction_v1.json`, sha256 `3310d624b03d…`
  - evidence [manifest]: `outputs/reports/s32_s33_gold_annotation_freeze_v1.manifest.json`, sha256 `f37ae1164b19…`
  - evidence [manifest]: `outputs/reports/formal_benchmark_release_v2.manifest.json`, sha256 `8b3cbd2e6081…`
  - evidence [independent_verifier]: `scripts/verify_formal_benchmark_release_v2.py`, sha256 `b9e1b9e29468…`
- **S3.3 = verified** — 33 violation decision Gold frozen and published (data/gold/stage3/stage3_violation_gold_v1.json); these type/evidence decisions are NOT Gold Rule Records.
  - evidence [disk_asset]: `data/gold/stage3/stage3_violation_gold_v1.json`, sha256 `54245ef0d102…`
  - evidence [disk_asset]: `data/development/human_review/stage3_gold_annotation_human_correction_v1.json`, sha256 `3310d624b03d…`
  - evidence [manifest]: `outputs/reports/s32_s33_gold_annotation_freeze_v1.manifest.json`, sha256 `f37ae1164b19…`
  - evidence [manifest]: `outputs/reports/formal_benchmark_release_v2.manifest.json`, sha256 `8b3cbd2e6081…`
  - evidence [independent_verifier]: `scripts/verify_formal_benchmark_release_v2.py`, sha256 `b9e1b9e29468…`
- **S3.4 = development_only** — Winter wrapper development evidence only; formal completion still blocked: S1.7 dependency is now SATISFIED (frozen 2026-08-13), S2.13 remains blocked.
  - evidence [manifest]: `outputs/development/s34_winter_stage3_development_v3_clean/manifest.json`, sha256 `74b918548d0e…`
  - evidence [manifest]: `outputs/development/s34_winter_stage3_development_v3_prototype_literal/manifest.json`, sha256 `91dda78fedc3…`
- **S3.5 = development_only** — Sun Stage 3 method-level reconstruction development evidence only; formal completion still blocked on S2.13 (S1.7 dependency now satisfied).
  - evidence [manifest]: `outputs/development/s35_sun_stage3_development_v2/manifest.json`, sha256 `48c61dbc85a0…`
- **S3.6 = development_only** — BM25 v3 + TF-IDF/SVD development baselines only; formal completion still blocked on S2.13 (S1.7 dependency now satisfied); threshold 0.5 remains a fixed development setting.
  - evidence [manifest]: `outputs/development/s36_bm25_stage3_development_v3/manifest.json`, sha256 `f81988c5522d…`
  - evidence [manifest]: `outputs/development/s36_tfidf_svd_stage3_development_v2/manifest.json`, sha256 `56e40e3e81a9…`
- **S3.7 = blocked** — Formal Oracle NOT started and NOT authorized; development Stage 3 numbers must not be promoted; the oracle_control block records the fail-closed flags.
  - blocker: Formal, user-adjudicated and frozen GDPR Gold Rule Records for the 9 rule IDs do not exist
  - blocker: S2.13 blocked
  - blocker: S3.4/S3.5/S3.6 formal completion pending
  - evidence [disk_asset]: `outputs/reports/s37_oracle_readiness_v1.json`, sha256 `7bd3e8dec72b…`
  - evidence [disk_asset]: `outputs/reports/s3_7_oracle_readiness_v2.json`, sha256 `0e79232bb17b…`
  - evidence [derivation]: `derived: no oracle authorization manifest and no formal oracle run/result assets found on disk`

## Stage 1 Process Gold

- exists: **True**
- path: `data/gold/stage1/process_records/stage1_process_gold_v1.json` (sha256 `f33aa857a079…`)
- manifest: `data/gold/stage1/manifest.json` (sha256 `1885dad26f43…`)
- counts: {'process_records': 7, 'label_fields': 135, 'structure_decisions': 7}
- independent verifier `scripts/verify_stage1_process_gold.py` VERIFIED (see verifiers_executed)

## Stage 3 decision Gold

- matching: `data/gold/stage3/stage3_matching_gold_v1.json` (count 25, sha256 `55dffbcaf7d6…`)
- violation: `data/gold/stage3/stage3_violation_gold_v1.json` (count 33, sha256 `54245ef0d102…`)
- frozen correction: `data/development/human_review/stage3_gold_annotation_human_correction_v1.json`
- consistency_with_frozen_correction: **True**
- The published matching/violation decisions are DECISION Gold only; they are NOT complete Rule/Process Gold and must never be used as Gold Rule Records.

## Gold Rule Records (three-state probe)

- exist: **False**
- absence derived from: no file under data/gold/ or outputs/reports/ matches a Gold Rule Record artifact name pattern (rule_record / rule-record) and no concrete rule-record path mentioned by the historical readiness reports exists on disk; data/gold/stage2/estg150_formal_gold_v1.json was explicitly checked and bound below - it is the EStG-150 Stage 2 six-element span Gold and is NOT a GDPR Rule Record
- candidate probe patterns:
  - data/gold/** file name contains rule_record or rule-record (case-insensitive; known non-Gold assets excluded)
  - outputs/reports/** file name contains rule_record or rule-record (defensive)
  - concrete rule-record paths mentioned by historical readiness reports (s37_oracle_readiness_v1 / s3_7_oracle_readiness_v2) that exist on disk
- candidate probe history sources: outputs/reports/s37_oracle_readiness_v1.json, outputs/reports/s3_7_oracle_readiness_v2.json
- candidate probe found: []
- the 9 GDPR rule IDs covered by the matching/violation decision packs (derived from disk): article6, article7, article15, article16, article17, article20, article22, article33, article34
- rule_ids_derived_from: data/gold/stage3/stage3_matching_gold_v1.json, data/gold/stage3/stage3_violation_gold_v1.json
- stage2 EStG-150 Gold is NOT GDPR Rule Records: **True**
- checked Stage 2 EStG-150 Gold: `data/gold/stage2/estg150_formal_gold_v1.json` (sha256 `c31a514a6b58…`) - checked and bound, NOT a GDPR Rule Record
- Formal, user-adjudicated and frozen GDPR Gold Rule Records for the 9 rule IDs do NOT exist. This round did NOT create, infer, or auto-fill any Gold Rule Record; their production remains a user-owned adjudication + freeze task, and exist=true would require a separate user-authorized freeze/publication path with formal schema, manifest and independent verifier (NOT implemented by v2).

## S3.4–S3.6 development-only

- **s3_4**: development_only — Winter wrapper development evidence only; formal completion still blocked on S2.13 (S1.7 dependency now satisfied by the 2026-08-13 freeze).
  - evidence [manifest]: `outputs/development/s34_winter_stage3_development_v3_clean/manifest.json` sha256 `74b918548d0e…`
  - evidence [manifest]: `outputs/development/s34_winter_stage3_development_v3_prototype_literal/manifest.json` sha256 `91dda78fedc3…`
- **s3_5**: development_only — Sun Stage 3 development evidence only; formal completion still blocked on S2.13 (S1.7 dependency now satisfied).
  - evidence [manifest]: `outputs/development/s35_sun_stage3_development_v2/manifest.json` sha256 `48c61dbc85a0…`
- **s3_6**: development_only — BM25 v3 + TF-IDF/SVD development baselines only; formal completion still blocked on S2.13 (S1.7 dependency now satisfied).
  - evidence [manifest]: `outputs/development/s36_bm25_stage3_development_v3/manifest.json` sha256 `f81988c5522d…`
  - evidence [manifest]: `outputs/development/s36_tfidf_svd_stage3_development_v2/manifest.json` sha256 `56e40e3e81a9…`

## Oracle control (fail-closed)

- formal_oracle_started: **False**
- formal_oracle_authorized: **False**
- ready_for_oracle_authorization: **False** (Substantive dependencies remain, so readiness is NOT reducible to a single authorization: S2.13 is blocked, formal user-adjudicated frozen GDPR Gold Rule Records for the 9 rule IDs do not exist, and S3.4/S3.5/S3.6 formal completion is pending.)
- authorization_sentence: **None** (No 'directly start the formal Oracle' authorization sentence may be generated now: substantive dependencies remain (S2.13 freeze; formal, user-adjudicated and frozen GDPR Gold Rule Records for the 9 rule IDs; S3.4-S3.6 formal promotion). Oracle readiness is not reducible to a single authorization.)
- no_pseudo_oracle: **True**
- probe: probe outputs/reports/*oracle_authorization* -> no matches
- probe: probe data/results/*oracle* + outputs/evidence/*oracle* -> no matches

## Prohibitions

1. Stage 2 method predictions must NOT be treated as Gold Rule Records.
2. Parser candidates must NOT be treated as Gold Process Records.
3. Stage 3 matching/violation decision labels must NOT be treated as complete Rule/Process Gold.
4. Development Stage 3 numbers must NOT be promoted to formal results.
5. audit_project.py --require-final-ready returning 0 must NOT bypass the MASTER_PIPELINE S2.13 / S3.7 dependencies.

## Audit consistency

- final_experiment_ready: **True**
- semantics: final_experiment_ready=true means ONLY that the Stage 2 three-method formal evaluation / final-metric MACHINE gates are ready (three verified formal capsules, hash-consistent shared comparison capsule, user-authorized G0.4 contract); it does NOT mean S2.13, S3.7, or full MASTER_PIPELINE completion.
- derived from: formal_experiment.audit.collect_project_audit() run in-process at build time
- claim_boundary_contradiction_free: **True**

## Verification scope (v2 fail-closed guarantees)

- exact_manifest_reconstruction: **True**
- exact_export_reconstruction: **True**
- strict_verifier_verdict: **True**
- gold_rule_record_three_state_probe: **True**
- markdown_single_eof_newline: **True**

## Independent verifiers executed

- `scripts/verify_stage1_process_gold.py`: verified=True, exit_code=0, checks 21
- `scripts/verify_s1_7_freezer_authorization.py`: verified=True, exit_code=0, checks 16
- `scripts/verify_formal_benchmark_release_v2.py`: verified=True, exit_code=0, checks 53
- `scripts/verify_s2_12_execution_ready.py`: verified=True, exit_code=0, checks 15
- `scripts/verify_s2_12_execution_ready_v2.py`: verified=True, exit_code=0, checks 14
- `outputs/reports/verify_b0_formal_arm_v1.py`: verified=True, exit_code=0
- `outputs/reports/verify_direct_llm_formal_arm_v1.py`: verified=True, exit_code=0
- `outputs/reports/verify_sun_llm_fallback_formal_arm_v1.py`: verified=True, exit_code=0
- `outputs/reports/verify_stage2_formal_comparison_v1.py`: verified=True, exit_code=0

## Zero API

- new_llm_api_calls: **0**
