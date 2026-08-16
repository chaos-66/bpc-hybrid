# S2.11 / G0.5 Pre-Authorization User Decision Capsule v6

**Schema**: `s2_11_g0_5_pre_authorization@6.0.0`
**Report ID**: `s2_11_g0_5_pre_authorization_v6`

## Determinism & safety

Deterministic S2.11 / G0.5 corrective decision capsule v6; every state judgment is re-derived from current on-disk assets, manifests, hashes or executed independent verifiers. v5's full audit WAS green (final receipt 2118 passed / 24 skipped / 19 warnings in 941.91s) and v5 is NOT a red checkpoint; its historical events stay preserved. However v5's caller-supplied validation-result protection was OVERTURNED by v6 counterexamples: a hand-built dict with a well-formed 64-hex token and the correct frozen hash could unlock classify_frozen. v6 removes the validation-result parameter entirely: classify_frozen re-verifies the draft/frozen configs, the authorization manifest, the append-only authorization event and the prior-results evidence scan from disk raw bytes on every call; prior results are derived from disk evidence (never a caller bool); the authorization manifest must fully bind the approved scope/sentence/event/checkpoint. v6 also adds adapter formal_evidence_provenance (re-verified evidence context, controlled scope enums, resolved-path containment) and fixes the historical capsule anchors to the v3/v4/v5 ORIGIN COMMITS (hardcoded SHA-256 maps, independent of HEAD). Article license CC BY 4.0 (article-only) stays separated from artifact code/data license (unknown_pending_confirmation); G0.5 stays draft_not_frozen and its authorization hash domain is the raw file bytes; G4 authorizes only a future gate-application checkpoint; G5 is not authorization-ready; authorization sentences are DRY-RUN text, nothing is applied, no gate is flipped and no Gold is created.
- gates_unchanged: **True**
- gold_predictions_results_contract_methods_unchanged: **True**
- g0_5_frozen: **False**
- references_read_only_not_activated: **True**
- no_authorization_applied: **True**

## v5 audit facts (honest record)

- v5_audit_green: **True** — v5's full audit WAS green; it is NOT a red checkpoint
- v5_final_receipt: `2118 passed, 24 skipped, 19 warnings in 941.91s`
- v5_handbuilt_validation_claim_overturned: **True** (a hand-built dict with a well-formed 64-hex token and the correct frozen hash could unlock v5's classify_frozen)
- v5_not_a_red_checkpoint: **True**
- v5_historical_events_preserved: **True**
- v6 counterexamples now rejected:
  - hand-built validation result {frozen_application_valid: True, validation_token: <any 64 lowercase hex>, approved_frozen_config_sha256: <real frozen hash>} -> REJECTED: classify_frozen has NO validation-result parameter; it re-verifies the full chain from disk on every call
  - validation token copied from another authorization manifest -> REJECTED: the token is re-derived from THIS manifest's raw bytes
  - manifest modified after validation (stale token reuse) -> REJECTED: re-validation hashes the CURRENT manifest/event bytes
  - manifest bound to a different draft/frozen config (path or raw-byte hash mismatch) -> REJECTED: G05_FROZEN_APPLICATION_MANIFEST_BINDING
  - authorization sentence / scope / event / event-path replaced -> REJECTED: G05_FROZEN_APPLICATION_SENTENCE_MISMATCH / SCOPE_MISMATCH / EVENT_MISMATCH (exact approved sentence + scope enum + event raw bytes required)
  - results produced BEFORE the authorization files -> REJECTED: prior results are derived from the project root by deterministic path/manifest rules (derive_prior_results), never from a caller bool
  - caller claims verified with bare booleans or forged hashes -> REJECTED: only on-disk re-verification of the manifest + append-only event counts; a content hash proves byte-identity only, never user authorization
  - G0.5 hash-domain mismatch: the raw-byte config hash 61938c99… is the only authorization hash; the semantic re-serialization hash 51a6e4fe… is rejected
  - adapter formal evidence scope mismatch (article_only does NOT cover artifact code/data) -> LICENSE_SCOPE_NOT_ARTIFACT_COVERING; resolved-path (symlink/junction) escape -> EVIDENCE_PATH_ESCAPE

## Fixed origin anchors (v3/v4/v5, independent of HEAD)

- **v3** origin commit `31ac757d821b7e451650edbd70b1899ed0104616`:
  - schema: sha256 `50d0efd0432f…`, 12895 bytes
  - builder: sha256 `89ce3684fddc…`, 50127 bytes
  - verifier: sha256 `830f6aad3e3e…`, 18962 bytes
  - json: sha256 `7c380a171423…`, 43589 bytes
  - md: sha256 `557f30b92534…`, 14990 bytes
  - manifest: sha256 `cf2b7b577d8f…`, 24117 bytes
  - export_index: sha256 `72c41725bc81…`, 945 bytes
- **v4** origin commit `8e8b488ea6d91ef0e6d0cf942ff9729e3e6776f6`:
  - schema: sha256 `4f52d45a530d…`, 14889 bytes
  - builder: sha256 `3dfc2bbcd85a…`, 60374 bytes
  - verifier: sha256 `69ed77a73468…`, 21887 bytes
  - json: sha256 `e4bc4f7d799b…`, 26890 bytes
  - md: sha256 `ac76e0f6a328…`, 20563 bytes
  - manifest: sha256 `9d9098a4df77…`, 8997 bytes
  - export_index: sha256 `424ea8ddac8a…`, 944 bytes
- **v5** origin commit `78837391167639da1bdef74faf67b817fa604813`:
  - schema: sha256 `c5dc45d2e2a3…`, 15998 bytes
  - builder: sha256 `630be461ddb6…`, 63915 bytes
  - verifier: sha256 `2ebc47f9af2c…`, 23540 bytes
  - json: sha256 `01334b80f22d…`, 29805 bytes
  - md: sha256 `8aa3cd622f0e…`, 22721 bytes
  - manifest: sha256 `e6aaf0bb6572…`, 10126 bytes
  - export_index: sha256 `7263df3015ee…`, 945 bytes

## Superseded decision entries (files preserved unmodified)

- `outputs/reports/s2_11_license_adapter_readiness_v2.json` (sha256 `8d271f59e2c6…`): 2026-08-11 license/adapter readiness v2; superseded as a decision entry by v3/v4/v5/v6; historical file stays unmodified.
- `outputs/reports/s2_11_data_qualification_mapping_dry_run.json` (sha256 `9a8835ec27c3…`): 2026-08-11 data-qualification & mapping dry-run; superseded as the decision entry by v3/v4/v5/v6; historical file stays unmodified.
- `outputs/reports/g0_7_barrientos_adapter_registry_dry_run.json` (sha256 `bb65cca291aa…`): 2026-08-11 G0.7 adapter registry dry-run; superseded by v3/v4/v5/v6 synthetic/shadow adapter reports; historical file stays unmodified.
- `outputs/reports/g0_7_barrientos_adapter_registry_dry_run.md` (sha256 `04029f864ae0…`): Markdown rendering of the same superseded registry dry-run; preserved unmodified.
- `configs/schemas/s2_11_g0_5_pre_authorization_v3.schema.json` (sha256 `50d0efd0432f…`): v3 schema; kept byte-exact (fixed origin anchor 31ac757d…; historical lifecycle semantics).
- `scripts/build_s2_11_g0_5_pre_authorization_v3.py` (sha256 `89ce3684fddc…`): v3 builder; kept byte-exact; its current-state judgments are superseded by v6.
- `scripts/verify_s2_11_g0_5_pre_authorization_v3.py` (sha256 `830f6aad3e3e…`): v3 verifier; kept byte-exact; its active-verification role is superseded by v6 (historical drift is the expected behavior).
- `tests/test_s2_11_g0_5_pre_authorization_v3.py` (sha256 `07f6666882b2…`): v3 pytest file: CORRECTED lifecycle test semantics only (v6); the v3 core assets are untouched.
- `outputs/reports/s2_11_g0_5_pre_authorization_v3.json` (sha256 `7c380a171423…`): v3 decision report; byte-exact historical provenance.
- `outputs/reports/s2_11_g0_5_pre_authorization_v3.md` (sha256 `557f30b92534…`): v3 Markdown rendering; byte-exact historical provenance.
- `outputs/reports/s2_11_g0_5_pre_authorization_v3.manifest.json` (sha256 `cf2b7b577d8f…`): v3 manifest; byte-exact historical provenance.
- `outputs/reports/s2_11_g0_5_pre_authorization_v3_export_index.json` (sha256 `72c41725bc81…`): v3 export index; byte-exact historical provenance.
- `configs/schemas/s2_11_g0_5_pre_authorization_v4.schema.json` (sha256 `4f52d45a530d…`): v4 schema; kept byte-exact (fixed origin anchor 8e8b488e…; historical lifecycle semantics).
- `scripts/build_s2_11_g0_5_pre_authorization_v4.py` (sha256 `3dfc2bbcd85a…`): v4 builder; kept byte-exact; its current-state judgments are superseded by v6.
- `scripts/verify_s2_11_g0_5_pre_authorization_v4.py` (sha256 `69ed77a73468…`): v4 verifier; kept byte-exact; its active-verification role is superseded by v6 (historical drift is the expected behavior).
- `tests/test_s2_11_g0_5_pre_authorization_v4.py` (sha256 `04073f58edcc…`): v4 pytest file: CORRECTED lifecycle test semantics only (v6); the v4 core assets are untouched.
- `outputs/reports/s2_11_g0_5_pre_authorization_v4.json` (sha256 `e4bc4f7d799b…`): v4 decision report; byte-exact historical provenance; its change event recorded 3 failed / 2057 passed / test_returncode=1 / integrity_pass=false (see v4_red_test_facts in the v5 report).
- `outputs/reports/s2_11_g0_5_pre_authorization_v4.md` (sha256 `ac76e0f6a328…`): v4 Markdown rendering; byte-exact historical provenance.
- `outputs/reports/s2_11_g0_5_pre_authorization_v4.manifest.json` (sha256 `9d9098a4df77…`): v4 manifest; byte-exact historical provenance.
- `outputs/reports/s2_11_g0_5_pre_authorization_v4_export_index.json` (sha256 `424ea8ddac8a…`): v4 export index; byte-exact historical provenance.
- `configs/schemas/s2_11_g0_5_pre_authorization_v5.schema.json` (sha256 `c5dc45d2e2a3…`): v5 schema; kept byte-exact (fixed origin anchor 7883739…; historical lifecycle semantics).
- `scripts/build_s2_11_g0_5_pre_authorization_v5.py` (sha256 `630be461ddb6…`): v5 builder; kept byte-exact; its current-state judgments are superseded by v6.
- `scripts/verify_s2_11_g0_5_pre_authorization_v5.py` (sha256 `2ebc47f9af2c…`): v5 verifier; kept byte-exact; its active-verification role is superseded by v6 (historical drift is the expected behavior).
- `tests/test_s2_11_g0_5_pre_authorization_v5.py` (sha256 `efe7946d768d…`): v5 pytest file: CORRECTED lifecycle test semantics only (v6); the v5 core assets are untouched.
- `outputs/reports/s2_11_g0_5_pre_authorization_v5.json` (sha256 `01334b80f22d…`): v5 decision report; byte-exact historical provenance; v5 audit WAS green (final receipt 2118 passed / 24 skipped / 19 warnings in 941.91s), NOT a red checkpoint.
- `outputs/reports/s2_11_g0_5_pre_authorization_v5.md` (sha256 `8aa3cd622f0e…`): v5 Markdown rendering; byte-exact historical provenance.
- `outputs/reports/s2_11_g0_5_pre_authorization_v5.manifest.json` (sha256 `e6aaf0bb6572…`): v5 manifest; byte-exact historical provenance.
- `outputs/reports/s2_11_g0_5_pre_authorization_v5_export_index.json` (sha256 `7263df3015ee…`): v5 export index; byte-exact historical provenance.

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
- **S2.11 = blocked** — Complex legal corpus NOT frozen and NOT activated; article license CC BY 4.0 (article-only) is confirmed, artifact code/data license still unknown_pending_confirmation, activation NOT authorized, mapping policy NOT approved, human Gold NOT started, G0.5 draft_not_frozen, adapter hardened synthetic/shadow only; the v6 decision capsule is the current decision entry for this gate (v3/v4/v5 historical).
  - blocker: license: unknown_pending_confirmation (no local declaration; external evidence pending)
  - blocker: data activation authorization: NOT granted (references/ stays read-only)
  - blocker: mapping decision: modality 3->4 mapping table / adjudication not decided
  - blocker: human Gold: required for external-label qualification; not started
  - blocker: G0.5 complexity rules: not frozen before results (retrospective only today)
  - blocker: Barrientos adapter (S2-BARR-2): not implemented (only the contract dry-run exists)
  - evidence [disk_asset]: `outputs/reports/s2_11_license_adapter_readiness_v2.json`, sha256 `8d271f59e2c6…`
  - evidence [disk_asset]: `outputs/reports/s2_11_data_qualification_mapping_dry_run.json`, sha256 `9a8835ec27c3…`
  - evidence [disk_asset]: `src/bpc_hybrid/s2_11_barrientos_adapter.py`, sha256 `283c2b1843b4…`
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

## License audit (article vs artifact separated)

- article PDF: `references/papers/Barrientos_2026_Impact_analysis.pdf` (sha256 `6ce91fd29557…`, 1822940 bytes)
- title: Impact analysis of regulatory requirement changes on business process compliance
- DOI: https://doi.org/10.1016/j.infsof.2026.108079
- CC BY statement (publisher PDF): 0950-5849/© 2026 The Authors. Published by Elsevier B.V. This is an open access article under the CC BY license (http://creativecommons.org/licenses/by/4.0/).
- CC BY URL: http://creativecommons.org/licenses/by/4.0/
- artifact URL (paper footnote): https://anonymous.4open.science/r/Requirements_Change_for_Business_Process_Compliance
- TUM reference (cross-check, not fetched): https://portal.fis.tum.de/en/publications/impact-analysis-of-regulatory-requirement-changes-on-business-pro/
- paper_readable: **True**
- article_license: **CC-BY-4.0** (scope: article_only)
- article_license_does_not_auto_cover_artifact: **True**
- code_usable: **unknown_pending_confirmation**
- data_reusable: **unknown_pending_confirmation**
- project_activatable: **False**
- ready_for_data_activation: **False**
- activation_authorization_sentence: **None**
- artifact files inventoried: 91 (names/hashes/sizes only)
- artifact license-evidence-named files: []
- note: article evidence chain: publisher PDF (references/papers/Barrientos_2026_Impact_analysis.pdf, sha256 6ce91fd29557..., 1822940 bytes) contains the DOI https://doi.org/10.1016/j.infsof.2026.108079, the Elsevier open-access statement 'This is an open access article under the CC BY license' (http://creativecommons.org/licenses/by/4.0/) and the artifact link https://anonymous.4open.science/r/Requirements_Change_for_Business_Process_Compliance; extracted read-only 2026-08-15
- note: article license CC BY 4.0 applies to the ARTICLE ONLY and does NOT auto-cover the code/data artifact; artifact code/data license stays unknown_pending_confirmation
- note: web-search snippets, file presence or downloadability are NOT license evidence; the TUM portal page is a cross-check reference only (not fetched this round)
- note: no artifact license-evidence-named file was found

## Mapping options (NOT applied; M1 = modality identity candidate ONLY)

### Option M1: modality_identity_candidate_only

- scope: authorizes ONLY identity CANDIDATE mapping for the three shared modality classes (obligation/permission/prohibition); it does NOT authorize any precondition/norm/temporal_validity -> actor/action/condition/constraint/exception structural mapping
- before: External Barrientos labels are unavailable to the project: artifact license unknown, activation not authorized, no mapping policy, adapter hardened synthetic/shadow only.
- after: After G1+G2+G3: obligation/permission/prohibition map by identity to candidate-only modality values with field-level provenance for the human Gold review; without a separately approved field mapping policy the structural fields stay blank; definition is never produced; external ground truth stays a review aid.
- risk: identity assumes nominal modality-label alignment between Barrientos and Sun; unverified semantics are caught by the mandatory human Gold adjudication
- risk: no structural candidate values are produced until a separate field-mapping gate (G6) is decided
- confirmation sentence: `I select mapping option M1 for the S2.11 Barrientos 3->4 modality mapping: identity candidate mapping for obligation/permission/prohibition ONLY; this does NOT authorize any precondition/norm/temporal_validity -> actor/action/condition/constraint/exception structural mapping (a separate field-mapping gate is required); definition is never auto-produced and requires separate human adjudication.`

### Option M2: conservative_no_mapping

- scope: maps NO external label at all; all external content enters the human Gold review as review aid only
- before: Same as M1: external labels unavailable.
- after: After G1+G2+G3: no external label is mapped; every source element enters the human Gold review as review aid and all decisions are made from scratch by the user.
- risk: largest human workload (no candidate values to start from)
- risk: most conservative with respect to label-semantics drift
- confirmation sentence: `I select mapping option M2 (conservative no-mapping: external labels are review aids only and every decision is made from scratch by human adjudication).`

**Recommended**: M1 — The three shared modality classes are nominally identical and the G0.7 registry dry-run documented the 3-class set; M1 minimizes human workload while the mandatory human Gold adjudication still guards against label-semantics drift and the hardened adapter never promotes candidates to Gold. M1 explicitly does NOT authorize structural field mapping (G6 remains a separate gate). M2 is the conservative fallback.
- applied: **False**
- definition_handling: never auto-produced; definition-class records require separate human adjudication
- external_ground_truth_role: provenance or review aid only; never project Gold
- structure_mapping_requires_separate_gate: **True**

## Human Gold protocol readiness (blank only)

- protocol_ready: **True**
- blank_schema_provided: **True**
- decision fields: sample_id, source_text, approved_text_en, modality, actor, action, condition, constraint, exception, evidence_span, review_state
- review_surface_separated: **True**
- adjudication_separated: **True**
- freeze_separated: **True**
- publication_separated: **True**
- final_adjudication_by: **user_only**
- gold_files_created: **False**
- decision_prefill: **False**

## G0.5 candidate contract + promotion readiness

- config: `configs/g05_complexity_candidate_draft_v1.json` (RAW BYTE sha256 `61938c99a012…` = 61938c99… authorization hash domain)
- status: **draft_not_frozen**; frozen: **False**
- g0_5_status: **draft_not_frozen**
- promotion_ready_for_application: **False**
- missing: user authorization manifest (G4 dry-run sentence is NOT applied)
- preregistration_claim_allowed: **False** (existing S2.10 results are never re-labeled preregistered)

## Adapter status (hardened v6 synthetic/shadow only)

- implementation: **synthetic_shadow_only**
- hardened (strict mode enum, real file-backed evidence bindings, verifiable field-level provenance): **True**
- verified (real execution tests): **True**
- source: `src/bpc_hybrid/s2_11_barrientos_adapter.py`; tests: `tests/test_g07_barrientos_adapter_contract.py`
- formal activation blocked on: artifact code/data license qualification (unknown_pending_confirmation; article CC BY 4.0 does NOT cover the artifact)
- formal activation blocked on: data activation authorization
- formal activation blocked on: 3->4 modality mapping policy approval (G3)
- formal activation blocked on: structural field mapping policy approval (G6)
- formal activation blocked on: human Gold adjudication for the external complex corpus (G5)

## User gates (separated; dry-run only)

### G1: confirm authoritative license evidence for references/barrientos_2026 artifact code/data

- ready_for_authorization: **False**
- authorization_sentence: **None**
- missing: ARTICLE license resolved: CC BY 4.0 (article-only, publisher statement hash-bound) — this does NOT cover the artifact
- missing: artifact code/data license evidence: authoritative LICENSE/COPYING/NOTICE/README/metadata on the artifact repository root or a publisher/author statement, versioned with URL/scope/license identifier/hash

### G2: authorize external data activation (after artifact license qualification)

- ready_for_authorization: **False**
- authorization_sentence: **None**
- missing: G1 artifact code/data license qualified (currently unknown_pending_confirmation)
- missing: user activation authorization

### G3: select the 3->4 modality mapping policy (modality identity candidate ONLY)

- ready_for_authorization: **True**
- authorization_sentence: **I select mapping option M1 for the S2.11 Barrientos 3->4 modality mapping: identity candidate mapping for obligation/permission/prohibition ONLY; this does NOT authorize any precondition/norm/temporal_validity -> actor/action/condition/constraint/exception structural mapping (a separate field-mapping gate is required); definition is never auto-produced and requires separate human adjudication.**

### G4: authorize a FUTURE G0.5 freeze gate-application checkpoint (raw-byte config hash-bound)

- ready_for_authorization: **True**
- authorization_sentence: **I authorize a future gate-application checkpoint that freezes configs/g05_complexity_candidate_draft_v1.json (RAW BYTE sha256 61938c99a012f36b2b3b3d66a346b31a6c33fdd3f14be0179291ef1982a97586) as the G0.5 complexity contract (scope: future external complex corpora only; retrospective_use_forbidden=true; must take effect before any new complex-corpus results are produced). This sentence authorizes ONLY that future gate-application checkpoint; it does NOT freeze G0.5 this round.**

### G5: authorize opening the blank S2.11 human Gold review surface

- ready_for_authorization: **False**
- authorization_sentence: **None**
- future_authorization_sentence_after_prerequisites (conditional, NOT current): `Future sentence, only after G1 artifact code/data license is qualified, G2 data activation is authorized, the actual corpus membership/hash is fixed and the review workload is sized: I authorize opening the blank S2.11 human Gold review surface; no decision may be prefilled and final adjudication is user-only.`
- missing: G1 artifact code/data license qualified
- missing: G2 data activation authorized
- missing: actual corpus membership/hash fixed
- missing: review workload sized (corpus-dependent)

### G6: authorize a structural field mapping policy (source element -> canonical Sun span field)

- ready_for_authorization: **False**
- authorization_sentence: **None**
- missing: a complete, evidence-based field mapping policy option set (source elements -> actor/action/condition/constraint/exception); v6 does NOT select one on its own

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
