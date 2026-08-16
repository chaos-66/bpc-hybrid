# S2.11 / G0.5 Pre-Authorization User Decision Capsule v3

**Schema**: `s2_11_g0_5_pre_authorization@3.0.0`
**Report ID**: `s2_11_g0_5_pre_authorization_v3`

## Determinism & safety

Deterministic S2.11 / G0.5 pre-authorization decision capsule; every state judgment is re-derived from current on-disk assets, manifests, hashes or executed independent verifiers; the license audit is read-only (names + hashes + sizes only); authorization sentences are DRY-RUN text and nothing is applied; no gate is flipped and no Gold is created.
- gates_unchanged: **True**
- gold_predictions_results_contract_methods_unchanged: **True**
- g0_5_frozen: **False**
- references_read_only_not_activated: **True**

## Superseded decision entries (files preserved unmodified)

- `outputs/reports/s2_11_license_adapter_readiness_v2.json` (sha256 `8d271f59e2c6…`): 2026-08-11 license/adapter readiness v2; its current-state judgment is superseded by the v3 decision capsule (v3 adds the executable synthetic/shadow adapter, the G0.5 draft contract and the separated user gates); the historical file stays unmodified.
- `outputs/reports/s2_11_data_qualification_mapping_dry_run.json` (sha256 `9a8835ec27c3…`): 2026-08-11 data-qualification & mapping dry-run; superseded as the decision entry by v3 (which carries concrete mapping options with dry-run authorization sentences); the historical file stays unmodified.
- `outputs/reports/g0_7_barrientos_adapter_registry_dry_run.json` (sha256 `bb65cca291aa…`): 2026-08-11 G0.7 adapter registry dry-run; superseded by v3 which reports the synthetic/shadow adapter implementation verified by real execution tests; the historical file stays unmodified.
- `outputs/reports/g0_7_barrientos_adapter_registry_dry_run.md` (sha256 `04029f864ae0…`): Markdown rendering of the same superseded registry dry-run; preserved unmodified as historical provenance.

## State matrix (unchanged facts)

- **S1.5 = verified** — Stage 1 Process Gold frozen and published (user-authorized 2026-08-13; 7/7 records, 135/135 label fields, 7/7 structure decisions).
  - evidence [disk_asset]: `data/gold/stage1/process_records/stage1_process_gold_v1.json`, sha256 `f33aa857a079…`
  - evidence [manifest]: `data/gold/stage1/manifest.json`, sha256 `1885dad26f43…`
  - evidence [manifest]: `outputs/reports/s1_5_process_gold_freeze_authorization_v1.manifest.json`, sha256 `4b97762cfe3c…`
- **S1.6 = verified** — Fixed-GDPR-7 formal descriptive component evaluation; post-Gold, target-aware, NOT held-out generalization evidence; P2/predictions/metrics byte-unchanged.
  - evidence [disk_asset]: `data/predictions/stage1_formal_v1/formal_predictions_v1.json`, sha256 `79a9b2c17185…`
  - evidence [disk_asset]: `data/results/stage1_formal_v1/stage1_formal_evaluation_v1.json`, sha256 `a072db39b371…`
- **S1.7 = frozen** — Formal Stage 1 freeze APPLIED (2026-08-13); does NOT auto-authorize the Stage 3 Oracle.
  - evidence [manifest]: `outputs/reports/s1_7_freezer_authorization_v1.manifest.json`, sha256 `7712176c877c…`
- **S2.10 = verified** — Three-method formal capsules and the formal three-method comparison are published and independently verified; new LLM calls 0.
  - evidence [manifest]: `outputs/reports/b0_formal_arm_v1.manifest.json`, sha256 `095a839fe7a9…`
  - evidence [manifest]: `outputs/reports/direct_llm_formal_arm_v1.manifest.json`, sha256 `f0f86318259d…`
  - evidence [manifest]: `outputs/reports/sun_llm_fallback_formal_arm_v1.manifest.json`, sha256 `0b5e32852028…`
  - evidence [disk_asset]: `outputs/reports/stage2_formal_three_method_comparison_v1.json`, sha256 `c9d76544a36c…`
- **S2.11 = blocked** — Complex legal corpus NOT frozen and NOT activated; license unknown_pending_confirmation, activation NOT authorized, mapping policy NOT approved, human Gold NOT started, G0.5 draft_not_frozen, adapter synthetic_shadow_only; the v3 decision capsule is the current decision entry for this gate.
  - blocker: license: unknown_pending_confirmation (no local declaration; external evidence pending)
  - blocker: data activation authorization: NOT granted (references/ stays read-only)
  - blocker: mapping decision: modality 3->4 mapping table / adjudication not decided
  - blocker: human Gold: required for external-label qualification; not started
  - blocker: G0.5 complexity rules: not frozen before results (retrospective only today)
  - blocker: Barrientos adapter (S2-BARR-2): not implemented (only the contract dry-run exists)
  - evidence [disk_asset]: `outputs/reports/s2_11_license_adapter_readiness_v2.json`, sha256 `8d271f59e2c6…`
  - evidence [disk_asset]: `outputs/reports/s2_11_data_qualification_mapping_dry_run.json`, sha256 `9a8835ec27c3…`
  - evidence [disk_asset]: `src/bpc_hybrid/s2_11_barrientos_adapter.py`, sha256 `5141c473ed36…`
- **S2.12 = partial** — Formal descriptive common error analysis delivered as RETROSPECTIVE/EXPLORATORY; full DoD blocked on S2.11.
  - evidence [disk_asset]: `outputs/reports/s2_12_formal_descriptive_error_analysis_v1.json`, sha256 `9f6c734002fd…`
  - evidence [manifest]: `outputs/reports/s2_12_formal_descriptive_error_analysis_v1.manifest.json`, sha256 `89b3f1209c19…`
- **S2.13 = blocked** — Stage 2 freeze NOT complete; DoD unchanged; final_experiment_ready=true does NOT complete S2.13.
  - blocker: S2.11 blocked
  - blocker: S2.12 full DoD not met (partial/retrospective only)
  - evidence [derivation]: `derived: S2.11 blocked AND S2.12 partial -> S2.13 blocked; DoD unchanged this round`
  - evidence [disk_asset]: `outputs/reports/s2_13_stage2_freeze_gap_capsule.json`, sha256 `eb934910c2e0…`
- **S3.2 = verified** — 25 matching decision Gold published; decisions are NOT Gold Rule Records.
  - evidence [disk_asset]: `data/gold/stage3/stage3_matching_gold_v1.json`, sha256 `55dffbcaf7d6…`
  - evidence [disk_asset]: `data/development/human_review/stage3_gold_annotation_human_correction_v1.json`, sha256 `3310d624b03d…`
  - evidence [manifest]: `outputs/reports/s32_s33_gold_annotation_freeze_v1.manifest.json`, sha256 `f37ae1164b19…`
- **S3.3 = verified** — 33 violation decision Gold published; decisions are NOT Gold Rule Records.
  - evidence [disk_asset]: `data/gold/stage3/stage3_violation_gold_v1.json`, sha256 `54245ef0d102…`
- **S3.4 = development_only** — Winter wrapper development evidence only; formal completion still blocked on S2.13 (S1.7 satisfied).
  - evidence [manifest]: `outputs/development/s34_winter_stage3_development_v3_clean/manifest.json`, sha256 `74b918548d0e…`
  - evidence [manifest]: `outputs/development/s34_winter_stage3_development_v3_prototype_literal/manifest.json`, sha256 `91dda78fedc3…`
- **S3.5 = development_only** — Sun Stage 3 development evidence only; formal completion still blocked on S2.13.
  - evidence [manifest]: `outputs/development/s35_sun_stage3_development_v2/manifest.json`, sha256 `48c61dbc85a0…`
- **S3.6 = development_only** — BM25 v3 + TF-IDF/SVD development baselines only; formal completion still blocked on S2.13.
  - evidence [manifest]: `outputs/development/s36_bm25_stage3_development_v3/manifest.json`, sha256 `f81988c5522d…`
  - evidence [manifest]: `outputs/development/s36_tfidf_svd_stage3_development_v2/manifest.json`, sha256 `56e40e3e81a9…`
- **S3.7 = blocked** — Formal Oracle NOT started and NOT authorized; no Oracle authorization sentence is generated by this capsule.
  - blocker: 9 GDPR Gold Rule Records do not exist
  - blocker: S2.13 blocked
  - blocker: S3.4/S3.5/S3.6 formal completion pending
  - evidence [disk_asset]: `outputs/reports/s37_oracle_readiness_v1.json`, sha256 `7bd3e8dec72b…`
  - evidence [disk_asset]: `outputs/reports/s3_7_oracle_readiness_v2.json`, sha256 `0e79232bb17b…`

## License audit (read-only)

- references path: `references/barrientos_2026`
- read_only_verified: **True**
- file_count: 91
- license_status: **unknown_pending_confirmation**
- ready_for_data_activation: **False**
- activation_authorization_sentence: **None**
- four-state:
  - paper_readable: not_established_without_authoritative_evidence
  - code_usable: not_established_without_authoritative_evidence
  - data_reusable: not_established_without_authoritative_evidence
  - activation_granted: False
- license-evidence-named files: []
- note: inventory records file names, SHA-256 and sizes only; no content is copied into this report and no notebook/script/tool under references/ is executed
- note: file presence, downloadability, search snippets or citation are NOT license evidence
- note: no authoritative LICENSE/COPYING/NOTICE/README/metadata file was found
- inventoried files: 91 (path/sha256/byte_size bound in the manifest; contents not copied)

## Mapping options (NOT applied)

### Option M1: identity_candidate_mapping

- before: External Barrientos labels are unavailable to the project: license unknown, activation not authorized, no mapping policy, adapter synthetic/shadow only.
- after: After G1+G2+G3: obligation/permission/prohibition map by identity to candidate-only values with per-field provenance for the human Gold review; definition is never produced; external ground truth stays a review aid.
- risk: identity assumes the nominal semantics of the three shared modality classes align between Barrientos and Sun; unverified semantics are caught by the mandatory human Gold adjudication before anything becomes Gold
- risk: no definition-class records can be produced from this source; definition coverage must come from other corpora or separate adjudication
- confirmation sentence: `I select mapping option M1 (identity candidate mapping for obligation/permission/prohibition; definition is never auto-produced and requires separate human adjudication) as the S2.11 Barrientos 3->4 modality mapping policy.`

### Option M2: conservative_no_mapping

- before: Same as M1: external labels unavailable.
- after: After G1+G2+G3: no external label is mapped at all; every source element enters the human Gold review as review aid and all decisions are made from scratch by the user.
- risk: largest human workload (no candidate values to start from)
- risk: most conservative with respect to label-semantics drift
- confirmation sentence: `I select mapping option M2 (conservative no-mapping: external labels are review aids only and every decision is made from scratch by human adjudication).`

**Recommended**: M1 — The three shared modality classes are nominally identical (obligation/permission/prohibition) and the G0.7 registry dry-run documented the 3-class set; an identity candidate mapping minimizes human workload while the mandatory human Gold adjudication still guards against label-semantics drift, and the fail-closed adapter never promotes candidates to Gold. M2 is the conservative fallback if the user distrusts nominal label alignment.
- applied: **False**
- definition_handling: never auto-produced; definition-class records require separate human adjudication
- external_ground_truth_role: provenance or review aid only; never project Gold

## Human Gold protocol readiness (blank only)

- ready: **True**
- blank_schema_provided: **True**
- decision fields: sample_id, source_text, approved_text_en, modality, actor, action, condition, constraint, exception, evidence_span, review_state
- review_surface_separated: **True**
- adjudication_separated: **True**
- freeze_separated: **True**
- publication_separated: **True**
- final_adjudication_by: **user_only**
- estimated_workload: to be sized once the corpus is activated and the review surface is opened (G5); sizing is part of the G5 scope, not this round
- gold_files_created: **False**
- decision_prefill: **False**

## G0.5 candidate contract (draft, NOT frozen)

- config: `configs/g05_complexity_candidate_draft_v1.json` (sha256 `61938c99a012…`)
- status: **draft_not_frozen**
- frozen: **False**

## Adapter status (synthetic/shadow only)

- implementation: **synthetic_shadow_only**
- verified (real execution tests): **True**
- source: `src/bpc_hybrid/s2_11_barrientos_adapter.py`; tests: `tests/test_g07_barrientos_adapter_contract.py`
- formal activation blocked on: license qualification (unknown_pending_confirmation)
- formal activation blocked on: data activation authorization
- formal activation blocked on: 3->4 mapping policy approval
- formal activation blocked on: human Gold adjudication for the external complex corpus

## User gates (separated; dry-run only)

### G1: provide/confirm authoritative license evidence for references/barrientos_2026

- ready_for_authorization: **False**
- authorization_sentence: **None**
- missing: authoritative license file (LICENSE/COPYING/NOTICE) or publisher/author official statement for references/barrientos_2026; file presence, downloadability, search snippets or citation are NOT sufficient

### G2: authorize external data activation (after license qualification)

- ready_for_authorization: **False**
- authorization_sentence: **None**
- missing: G1 license qualified (currently unknown_pending_confirmation)
- missing: user activation authorization

### G3: select the 3->4 modality mapping policy

- ready_for_authorization: **True**
- authorization_sentence: **I select mapping option M1 (identity candidate mapping for obligation/permission/prohibition; definition is never auto-produced and requires separate human adjudication) as the S2.11 Barrientos 3->4 modality mapping policy.**

### G4: authorize freezing the G0.5 candidate complexity contract

- ready_for_authorization: **True**
- authorization_sentence: **I authorize freezing configs/g05_complexity_candidate_draft_v1.json as the G0.5 complexity contract (experiment-contract / gate change, status frozen) BEFORE any new complex-corpus results are produced.**

### G5: authorize opening the blank S2.11 human Gold review surface

- ready_for_authorization: **True**
- authorization_sentence: **I authorize opening the blank S2.11 human Gold review surface (blank schema + decision fields + separated review/adjudication/freeze/publication workflow); no decision may be prefilled and final adjudication is user-only.**

## Oracle control (fail-closed)

- formal_oracle_started: **False**
- formal_oracle_authorized: **False**
- ready_for_oracle_authorization: **False**
- authorization_sentence: **None**
- no_pseudo_oracle: **True**

## Independent verifiers executed

- `scripts/verify_stage1_process_gold.py`: verified=True, exit_code=0, checks 21
- `scripts/verify_s1_7_freezer_authorization.py`: verified=True, exit_code=0, checks 16
- `scripts/verify_formal_benchmark_release_v2.py`: verified=True, exit_code=0, checks 53
- `outputs/reports/verify_b0_formal_arm_v1.py`: verified=True, exit_code=0
- `outputs/reports/verify_direct_llm_formal_arm_v1.py`: verified=True, exit_code=0
- `outputs/reports/verify_sun_llm_fallback_formal_arm_v1.py`: verified=True, exit_code=0
- `outputs/reports/verify_stage2_formal_comparison_v1.py`: verified=True, exit_code=0

## Zero API

- new_llm_api_calls: **0**
